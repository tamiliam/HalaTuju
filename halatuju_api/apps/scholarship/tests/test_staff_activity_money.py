"""Common profile S4 (2026-10-31): the money, contract and request doors of the staff activity list.

Every S4 verb, through the door(s) that perform it, writes EXACTLY ONE row whose actor is the person
who pressed the button. The money paths must behave EXACTLY as before when the write fails (a real
database error, or the writer raising): the same status, the same rows, the same response. A system
path (the monthly invoice cron, a management command) writes nothing.
"""
import datetime
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import (
    bursary, contracts, disbursement, invoicing, merchant_flags, payment_declarations, payments,
    spend_report, sponsorship, staff_activity,
)
from apps.scholarship.models import (
    BursaryAgreement, Disbursement, Donation, MerchantFlag, OrgRequest, PaymentRun, Sponsor,
    SponsorProgrammeMembership, StaffActivity,
)
from apps.scholarship.tests.contract_helpers import make_deployable
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)
from apps.scholarship.tests.test_invoice_endpoints import _Doors
from apps.scholarship.tests.test_invoicing import SEPT_15
from apps.scholarship.tests.test_on_hold_money import _PaidCohort
from apps.scholarship.tests.test_staff_activity import _a_real_db_error, _the_writer_itself_raising

V = staff_activity.V


def _rows():
    return list(StaffActivity.objects.order_by('id'))


class _Asserts:
    def assertRows(self, expected):
        """``expected`` = [(verb, actor, subject_type, subject_id), ...] — the WHOLE table."""
        got = [(r.verb, r.actor_id, r.subject_type, r.subject_id) for r in _rows()]
        self.assertEqual(got, [(str(v), a.pk, t, s) for v, a, t, s in expected],
                         [(r.verb, r.meta) for r in _rows()])

    def assertNoRows(self):
        self.assertEqual(_rows(), [])


# ── payment runs: created and signed (maker / approver), and the money path untouched ─────────
class TestPaymentRuns(_Asserts, _PaidCohort):

    def setUp(self):
        super().setUp()
        self.maker = make_admin('admin', owning_org=self.org, name='Maker One')
        self.approver = make_admin('org_admin', owning_org=self.org, name='Approver One')

    def _signed_run(self, **kw):
        run = payments.create_run(self.org, self.programme, self.pay_on, self.period,
                                  by_email=self.maker.email, actor=self.maker)
        payments.sign(run, self.maker, 'Maker One')
        payments.sign(run, self.approver, 'Approver One')
        return run

    def test_created_then_signed_by_the_maker_then_the_approver(self):
        run = self._signed_run()
        self.assertRows([(V.PAYMENT_RUN_CREATED, self.maker, 'payment_run', run.pk),
                         (V.PAYMENT_RUN_SIGNED, self.maker, 'payment_run', run.pk),
                         (V.PAYMENT_RUN_SIGNED, self.approver, 'payment_run', run.pk)])
        self.assertEqual([r.meta.get('role') for r in _rows()], [None, 'maker', 'approver'])
        self.assertEqual({r.organisation_id for r in _rows()}, {self.org.pk})

    def test_the_payouts_are_the_runs_approval_and_write_no_tranche_rows(self):
        self._signed_run()
        self.assertEqual(Disbursement.objects.filter(status='released').count(), 2)
        self.assertFalse(StaffActivity.objects.filter(verb=V.TRANCHE_RELEASED).exists())

    def test_a_refused_signature_writes_nothing(self):
        run = payments.create_run(self.org, self.programme, self.pay_on, self.period)
        with self.assertRaises(payments.PaymentsError):
            payments.sign(run, self.maker, 'Somebody Else')
        self.assertNoRows()

    def test_an_approval_that_rolls_back_leaves_no_row(self):
        from apps.scholarship import maintenance
        run = payments.create_run(self.org, self.programme, self.pay_on, self.period)
        payments.sign(run, self.maker, 'Maker One')
        StaffActivity.objects.all().delete()
        maintenance.set_substate(self.held, 'on_hold', by_email='o@example.test')
        run = PaymentRun.objects.get(pk=run.pk)
        if run.status == 'admin_signed':        # the hold may already have reverted the run
            with self.assertRaises(payments.PaymentsError):
                with mock.patch('apps.scholarship.payments._is_on_hold', return_value=True):
                    payments.sign(run, self.approver, 'Approver One')
            self.assertEqual(PaymentRun.objects.get(pk=run.pk).status, 'admin_signed')
        self.assertFalse(StaffActivity.objects.filter(verb=V.PAYMENT_RUN_SIGNED).exists())

    def test_the_money_is_paid_exactly_the_same_when_the_write_fails(self):
        for label, failure in (('db error', _a_real_db_error),
                               ('writer raising', _the_writer_itself_raising)):
            with self.subTest(label):
                Disbursement.objects.all().delete()
                PaymentRun.objects.all().delete()
                with failure():
                    run = self._signed_run()
                run.refresh_from_db()
                self.assertEqual(run.status, 'completed')
                self.assertEqual(sorted(Disbursement.objects.filter(status='released')
                                        .values_list('application_id', flat=True)),
                                 sorted([self.held.pk, self.other.pk]))
        self.assertNoRows()


# ── tranches ───────────────────────────────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestTranches(_Asserts, TestCase):

    def setUp(self):
        self.cohort = make_cohort()
        self.org = self.cohort.owning_organisation
        self.officer = make_admin('super', super_admin=True)
        self.app = make_application('maintenance', cohort=self.cohort)

    def _tranche(self):
        return disbursement.schedule_tranche(self.app, amount=500)

    def _post(self, d, action):
        return authed_client(self.officer).post(
            f'/api/v1/admin/scholarship/disbursements/{d.pk}/{action}/', {}, format='json')

    def test_release_withhold_and_return_through_the_endpoint(self):
        a, b = self._tranche(), self._tranche()
        self.assertEqual(self._post(a, 'release').status_code, 200)
        self.assertEqual(self._post(b, 'withhold').status_code, 200)
        self.assertEqual(self._post(a, 'return').status_code, 200)
        self.assertRows([(V.TRANCHE_RELEASED, self.officer, 'application', self.app.pk),
                         (V.TRANCHE_WITHHELD, self.officer, 'application', self.app.pk),
                         (V.TRANCHE_RETURNED, self.officer, 'application', self.app.pk)])
        self.assertEqual([r.meta for r in _rows()],
                         [{'tranche': a.pk}, {'tranche': b.pk}, {'tranche': a.pk}])

    def test_mark_due_is_not_an_act_and_writes_nothing(self):
        self.assertEqual(self._post(self._tranche(), 'mark_due').status_code, 200)
        self.assertNoRows()

    def test_a_release_with_no_actor_writes_nothing(self):
        disbursement.release_tranche(self._tranche(), by_email='ops@example.test')
        self.assertNoRows()

    def test_the_release_is_the_same_when_the_write_fails(self):
        for label, failure in (('db error', _a_real_db_error),
                               ('writer raising', _the_writer_itself_raising)):
            with self.subTest(label):
                d = self._tranche()
                with failure():
                    resp = self._post(d, 'release')
                self.assertEqual(resp.status_code, 200)
                d.refresh_from_db()
                self.assertEqual(d.status, 'released')
        self.assertNoRows()


# ── credits: the maker records, finance checks, the approver confirms ──────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCredits(_Asserts, TestCase):

    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.programme = self.cohort.programme
        self.sponsor = Sponsor.objects.create(supabase_user_id='cr-sp', name='Ben', email='b@x.test',
                                              status='approved')
        SponsorProgrammeMembership.objects.create(sponsor=self.sponsor, programme=self.programme,
                                                  status='approved')
        self.maker = make_admin('admin', owning_org=self.org, name='Maker One')
        self.finance = make_admin('finance', owning_org=self.org, name='Fin One')
        self.approver = make_admin('org_admin', owning_org=self.org, name='Approver One')

    def _credit(self):
        return sponsorship.record_admin_credit(sponsor=self.sponsor, programme=self.programme,
                                               amount=Decimal('100'), external_reference='MBB-1',
                                               admin=self.maker)

    def _sign(self, credit, who, name):
        return authed_client(who).post(f'/api/v1/admin/scholarship/credits/{credit.pk}/sign/',
                                       {'typed_name': name}, format='json')

    def test_recorded_checked_confirmed_through_the_endpoint(self):
        credit = self._credit()
        self.assertNoRows()                     # a DRAFT is not yet a credit: the maker's signature is
        for who, name in ((self.maker, 'Maker One'), (self.finance, 'Fin One'),
                          (self.approver, 'Approver One')):
            self.assertEqual(self._sign(credit, who, name).status_code, 200)
        self.assertRows([(V.CREDIT_RECORDED, self.maker, 'credit', credit.pk),
                         (V.CREDIT_CHECKED, self.finance, 'credit', credit.pk),
                         (V.CREDIT_CONFIRMED, self.approver, 'credit', credit.pk)])
        self.assertEqual({r.organisation_id for r in _rows()}, {self.org.pk})

    def test_a_confirmed_credit_is_spendable_when_the_write_fails(self):
        credit = self._credit()
        with _a_real_db_error():
            for who, name in ((self.maker, 'Maker One'), (self.finance, 'Fin One'),
                              (self.approver, 'Approver One')):
                self.assertEqual(self._sign(credit, who, name).status_code, 200)
        credit.refresh_from_db()
        self.assertEqual(credit.status, Donation.STATUS_CONFIRMED)
        self.assertNoRows()


# ── contract templates and the countersign ─────────────────────────────────────────────────────
class TestContracts(_Asserts, TestCase):

    def test_created_vetted_submitted_deployed(self):
        super_ = make_admin('super', super_admin=True)
        template = make_deployable()               # created + vetted with no actor: no rows
        self.assertNoRows()
        draft = contracts.create_template(template.organisation, '2027-v1',
                                          programme=template.programme, actor=super_)
        contracts.record_vetting(draft, vetted_by_name='Lawyer', vetted_on=date(2026, 7, 1),
                                 attested_by_email=super_.email, actor=super_)
        contracts.submit_for_deployment(template, actor=super_)
        contracts.deploy(template, is_super=True, actor=super_)
        self.assertRows([(V.CONTRACT_TEMPLATE_CREATED, super_, 'contract_template', draft.pk),
                         (V.CONTRACT_TEMPLATE_VETTED, super_, 'contract_template', draft.pk),
                         (V.CONTRACT_TEMPLATE_SUBMITTED, super_, 'contract_template', template.pk),
                         (V.CONTRACT_TEMPLATE_DEPLOYED, super_, 'contract_template', template.pk)])

    @mock.patch('apps.scholarship.bursary._regenerate_artefact')
    @mock.patch('apps.scholarship.bursary.distribute_executed_agreement')
    def test_the_foundation_countersign(self, *_):
        super_ = make_admin('super', super_admin=True)
        app = make_application('awarded')
        agreement = BursaryAgreement.objects.create(application=app, version='2026-v1')
        bursary.countersign_foundation(agreement, by_name='Super', actor=super_)
        self.assertRows([(V.CONTRACT_COUNTERSIGNED, super_, 'application', app.pk)])
        self.assertEqual(_rows()[0].meta, {'agreement': agreement.pk})


# ── benefactor vetting ─────────────────────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestBenefactorVetting(_Asserts, TestCase):

    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.oa = make_admin('org_admin', owning_org=self.org)
        self.sponsor = Sponsor.objects.create(supabase_user_id='bv-sp', name='Ben', email='b@x.test',
                                              status='pending')

    def test_the_account_and_the_gift(self):
        r1 = authed_client(self.oa).post(f'/api/v1/admin/sponsors/{self.sponsor.pk}/review/',
                                         {'action': 'approve'}, format='json')
        r2 = authed_client(self.oa).post(f'/api/v1/admin/sponsors/{self.sponsor.pk}/membership/',
                                         {'programme_id': self.cohort.programme_id,
                                          'status': 'approved'}, format='json')
        self.assertEqual((r1.status_code, r2.status_code), (200, 200), (r1.content, r2.content))
        self.assertRows([(V.BENEFACTOR_VETTED, self.oa, 'sponsor', self.sponsor.pk)] * 2)
        account, gift = (r.meta for r in _rows())
        self.assertEqual(account, {'decision': 'approved', 'kind': 'account'})
        self.assertEqual(gift, {'decision': 'approved', 'kind': 'programme',
                                'programme': self.cohort.programme_id})
        self.assertEqual(_rows()[1].organisation_id, self.org.pk)

    def test_the_sponsors_own_registration_writes_nothing(self):
        sponsorship.sync_account_membership(self.sponsor, self.cohort.programme)
        self.assertNoRows()


# ── invoices and the payments against them ─────────────────────────────────────────────────────
class TestInvoices(_Asserts, _Doors):

    def test_issued_sent_voided_through_the_endpoints(self):
        c = self.client_for('super-uid')
        resp = c.post('/api/v1/admin/scholarship/billing/invoices/',
                      {'organisation_id': self.org.pk, 'period_month': '2026-08'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pk = resp.json()['id']
        self.assertEqual(c.post(f'/api/v1/admin/scholarship/billing/invoices/{pk}/send/', {},
                                format='json').status_code, 200)
        self.assertEqual(c.post(f'/api/v1/admin/scholarship/billing/invoices/{pk}/void/',
                                {'reason': 'wrong month'}, format='json').status_code, 200)
        self.assertRows([(V.INVOICE_ISSUED, self.super, 'invoice', pk),
                         (V.INVOICE_SENT, self.super, 'invoice', pk),
                         (V.INVOICE_VOIDED, self.super, 'invoice', pk)])

    def test_the_monthly_cron_issues_and_writes_nothing(self):
        invoicing.issue_month(today=SEPT_15)
        self.assertNoRows()

    def test_declared_rejected_declared_again_confirmed(self):
        inv = self.sent()
        d1 = payment_declarations.declare_payment(inv, paid_on='2026-09-15', reference='R1',
                                                  declared_by_email=self.oa.email, actor=self.oa)
        payment_declarations.reject_declaration(d1, reason='not found', actor=self.super)
        d2 = payment_declarations.declare_payment(inv, paid_on='2026-09-15', reference='R2',
                                                  actor=self.oa)
        receipt = payment_declarations.confirm_payment(d2, amount_myr=inv.total_myr, actor=self.super)
        self.assertRows([(V.PAYMENT_DECLARED, self.oa, 'invoice', inv.pk),
                         (V.PAYMENT_REJECTED, self.super, 'invoice', inv.pk),
                         (V.PAYMENT_DECLARED, self.oa, 'invoice', inv.pk),
                         (V.PAYMENT_CONFIRMED, self.super, 'invoice', inv.pk)])   # ONE row, not two
        self.assertEqual(_rows()[-1].meta, {'receipt': receipt.pk})

    def test_a_direct_receipt_is_one_payment_confirmed(self):
        inv = self.sent()
        resp = self.client_for('super-uid').post(
            f'/api/v1/admin/scholarship/billing/invoices/{inv.pk}/receipt/',
            {'received_on': '2026-09-15', 'amount_myr': str(inv.total_myr), 'reference': 'R9'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertRows([(V.PAYMENT_CONFIRMED, self.super, 'invoice', inv.pk)])

    def test_a_receipt_is_minted_the_same_when_the_write_fails(self):
        inv = self.sent()
        with _a_real_db_error():
            resp = self.client_for('super-uid').post(
                f'/api/v1/admin/scholarship/billing/invoices/{inv.pk}/receipt/',
                {'received_on': '2026-09-15', 'amount_myr': str(inv.total_myr), 'reference': 'R9'},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(inv.receipts.count(), 1)
        self.assertNoRows()


# ── org requests ───────────────────────────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class TestOrgRequests(_Asserts, TestCase):

    def setUp(self):
        self.org = make_org()
        self.oa = make_admin('org_admin', owning_org=self.org)

    def test_raised_approved_and_declined(self):
        c = authed_client(self.oa)
        resp = c.post('/api/v1/admin/scholarship/requests/',
                      {'kind': 'bug', 'title': 'A broken button', 'description': 'It is broken'},
                      format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        req = OrgRequest.objects.get()
        OrgRequest.objects.filter(pk=req.pk).update(status='quoted')
        self.assertEqual(c.post(f'/api/v1/admin/scholarship/requests/{req.pk}/approve/', {},
                                format='json').status_code, 200)
        other = OrgRequest.objects.create(organisation=self.org, submitted_by=self.oa, kind='bug',
                                          title='t', description='d')
        self.assertEqual(c.post(f'/api/v1/admin/scholarship/requests/{other.pk}/decline/', {},
                                format='json').status_code, 200)
        self.assertRows([(V.ORG_REQUEST_RAISED, self.oa, 'org_request', req.pk),
                         (V.ORG_REQUEST_APPROVED, self.oa, 'org_request', req.pk),
                         (V.ORG_REQUEST_DECLINED, self.oa, 'org_request', other.pk)])
        self.assertNotIn('broken', str([r.meta for r in _rows()]))


# ── shop flags ─────────────────────────────────────────────────────────────────────────────────
class TestMerchantFlags(_Asserts, TestCase):

    def test_opened_noted_and_closed(self):
        org = make_org()
        admin = make_admin('admin', owning_org=org)
        txns = mock.MagicMock()
        txns.filter.return_value.exists.return_value = True
        for action in ('open', 'note', 'close'):
            _, code = merchant_flags.change_flag(org.pk, 'KEDAI ABC', action, 'checked', admin.email,
                                                 txns, actor=admin)
            self.assertIsNone(code)
        flag = MerchantFlag.objects.get()
        self.assertRows([(V.MERCHANT_FLAG_OPENED, admin, 'merchant_flag', flag.pk),
                         (V.MERCHANT_FLAG_CLOSED, admin, 'merchant_flag', flag.pk)])   # a note is not
        self.assertEqual({r.organisation_id for r in _rows()}, {org.pk})
