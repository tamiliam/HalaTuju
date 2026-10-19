"""Request #39 Sprint 2 — Finance APPROVES payment runs (owner, 2026-10-19, option A).

*"Finance role currently doesn't have clear action items. I would like the role to be able to approve
payment — the work that Suresh does today."* So: an Admin PREPARES (signs as maker), FINANCE APPROVES
and that completes the run; the organisation admin (Suresh) stops countersigning, and approves only
under the per-run FALLBACK, when nobody else can. Roadmap: docs/plans/2026-10-19-staff-permissions-roadmap.md
("The payment chain after the change", "In-flight runs on deploy day").

Pinned here: the four in-flight rows of the roadmap's table, each as a test; every way a run could
strand; the email routing per case; `next_step_for` (the one predicate behind the gate and the
screen); the row lock; the service's own organisation fence; and wallet credits, which keep TODAY's
finance-role chain, byte for byte (owner question 6).
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import payments
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Disbursement, Donation, PaymentRun, Programme, Sponsor, SponsorProgrammeMembership,
)
from apps.scholarship.tests.test_payments import _make_app, _make_cohort, _make_org, _run

_APPROVAL = 'awaits your approval'


def _person(org, role, name, email, **kw):
    kw.setdefault('first_seen_at', timezone.now())     # has signed in (fix 4); override with None
    return PartnerAdmin.objects.create(
        supabase_user_id=f'fa-{email}', role=role, is_active=True, owning_organisation=org,
        name=name, email=email, **kw)


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class _Chain(TestCase):
    """BrightPath's shape: an Admin (Kulaly) prepares, a Finance person, the org admin (Suresh)."""

    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org(code='fa-bp')
        cls.cohort = _make_cohort(cls.org, code='fa-c')
        cls.maker = _person(cls.org, 'admin', 'Kulaly Maker', 'kulaly@x.com')
        cls.finance = _person(cls.org, 'finance', 'Fina Approver', 'fina@x.com')
        cls.suresh = _person(cls.org, 'org_admin', 'Suresh Lead', 'suresh@x.com')
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='fa-su', is_super_admin=True, is_active=True, name='Super One',
            email='super@x.com')

    def _run(self):
        _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            return _run(self.org, date(2026, 8, 1), date(2026, 8, 1), by_email='kulaly@x.com')

    def _sign(self, run, who):
        return payments.sign(run, who, who.name)

    def _refused(self, run, who):
        with self.assertRaises(payments.PaymentsError) as cm:
            self._sign(run, who)
        return cm.exception.code

    def _approval_to(self):
        return sorted(to for m in mail.outbox if _APPROVAL in m.subject for to in m.to)


class TestInFlightOnDeployDay(_Chain):
    """The roadmap's four rows. No data changes on deploy; each row's behaviour is the live rule."""

    def test_draft_the_maker_signs_and_the_email_goes_to_finance(self):
        run = self._run()
        mail.outbox = []
        self._sign(run, self.maker)
        self.assertEqual(self._approval_to(), ['fina@x.com'])          # not Suresh
        self.assertFalse([m for m in mail.outbox if 'finance check' in m.subject])

    def test_admin_signed_with_no_finance_person_the_org_admin_approves_as_before(self):
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(is_active=False)
        run = self._run()
        mail.outbox = []
        self._sign(run, self.maker)
        self.assertEqual(self._approval_to(), ['suresh@x.com'])        # the fallback is told
        self.assertTrue(payments.approver_fallback(run))
        self.assertEqual(payments.next_step_for(run, self.suresh), 'approve')
        self._sign(run, self.suresh)
        run.refresh_from_db()
        self.assertEqual((run.status, run.org_admin_signed_email), ('completed', 'suresh@x.com'))

    def test_admin_signed_waiting_for_the_old_finance_check_finance_now_approves_directly(self):
        # Before deploy this run waited for Finance's CHECK; after it, Finance's signature APPROVES
        # and completes it. Suresh's countersignature is skipped — the change the owner asked for.
        run = self._run()
        self._sign(run, self.maker)
        self.assertEqual(self._refused(run, self.suresh), 'wrong_role')
        mail.outbox = []
        self._sign(run, self.finance)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.org_admin_signed_email, 'fina@x.com')    # the APPROVER triple
        self.assertEqual(run.finance_signed_email, '')                 # no check was taken
        disb = Disbursement.objects.get(reference=f'vircle:{run.reference}')
        self.assertEqual((disb.status, disb.actioned_by), ('released', 'fina@x.com'))
        vircle = [m for m in mail.outbox if m.to == ['gokula@vircle.com']]
        self.assertEqual(len(vircle), 1)
        self.assertEqual(vircle[0].cc, ['fina@x.com'])                 # the approver is copied
        self.assertIn('prepared by Kulaly Maker and approved by Fina Approver', vircle[0].body)
        # A reader of the released money, unchanged: the Programme Overview's "paid" counts the
        # disbursement Finance's approval wrote, exactly as it counted Suresh's.
        from apps.scholarship import programme_overview
        paid = programme_overview.money(programme_overview.application_scope(self.org))['paid']
        self.assertEqual(paid, disb.amount)

    def test_finance_checked_by_the_only_finance_person_the_org_admin_approves(self):
        # A run Finance CHECKED before deploy: distinctness bars Finance from approving it too,
        # nobody else holds the approval, so the fallback lets Suresh approve — as today.
        run = self._run()
        self._sign(run, self.maker)
        PaymentRun.objects.filter(pk=run.pk).update(
            status='finance_checked', finance_signed_name='Fina Approver',
            finance_signed_email='fina@x.com')
        run.refresh_from_db()
        self.assertIsNone(payments.next_step_for(run, self.finance))
        self.assertEqual(self._refused(run, self.finance), 'same_signer')
        self.assertTrue(payments.approver_fallback(run))
        self.assertEqual(payments.next_step_for(run, self.suresh), 'approve')
        self._sign(run, self.suresh)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')
        self.assertEqual(Disbursement.objects.filter(status='released').count(), 1)


class TestNothingStrands(_Chain):
    """The per-run fallback: when nobody ELIGIBLE holds the approval, the org admin approves."""

    def test_the_sole_approver_who_prepared_the_run(self):
        both = _person(self.org, 'finance', 'Both Hats', 'both@x.com',
                       permissions=['payments_prepare', 'payments_approve'])
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(is_active=False)
        run = self._run()
        self._sign(run, both)                                          # signs as MAKER
        self.assertIsNone(payments.next_step_for(run, both))
        self.assertEqual(self._refused(run, both), 'same_signer')
        self._sign(run, self.suresh)                                   # the fallback
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_the_last_approver_revoked_mid_run(self):
        run = self._run()
        self._sign(run, self.maker)
        self.assertFalse(payments.approver_fallback(run))
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(is_active=False)
        self.assertTrue(payments.approver_fallback(run))
        self._sign(run, self.suresh)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_the_last_approver_switched_to_admin_mid_run(self):
        run = self._run()
        self._sign(run, self.maker)
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(role='admin')
        self.assertEqual(payments.next_step_for(run, self.suresh), 'approve')
        self._sign(run, self.suresh)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_appointing_finance_mid_run_takes_the_approval_back_from_the_org_admin(self):
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(is_active=False)
        run = self._run()
        self._sign(run, self.maker)
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(is_active=True)
        self.assertEqual(self._refused(run, self.suresh), 'wrong_role')
        self._sign(run, self.finance)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')


class TestTheCheckStaysOnePermissionAway(_Chain):
    def test_granting_the_check_mid_run_arms_it_and_routes_the_emails(self):
        run = self._run()
        self._sign(run, self.maker)
        checker = _person(self.org, 'admin', 'Third Signer', 'third@x.com',
                          permissions=['payments_check'])
        self.assertTrue(payments.finance_check_required(self.org))
        self.assertEqual(self._refused(run, self.finance), 'finance_check_required')
        # Suresh is NOT waiting for the check — Finance approves after it, so he is told plainly
        # that the step is not his (review nit, 2026-10-19).
        self.assertEqual(self._refused(run, self.suresh), 'wrong_role')
        self.assertEqual(payments.next_step_for(run, checker), 'check')
        mail.outbox = []
        self._sign(run, checker)
        self.assertEqual(self._approval_to(), ['fina@x.com'])
        self._sign(run, self.finance)
        run.refresh_from_db()
        self.assertEqual((run.status, run.finance_signed_email, run.org_admin_signed_email),
                         ('completed', 'third@x.com', 'fina@x.com'))

    def test_with_the_check_armed_the_maker_s_email_goes_to_the_checkers_only(self):
        _person(self.org, 'admin', 'Third Signer', 'third@x.com', permissions=['payments_check'])
        run = self._run()
        mail.outbox = []
        self._sign(run, self.maker)
        self.assertEqual([to for m in mail.outbox for to in m.to], ['third@x.com'])
        self.assertIn('finance check', mail.outbox[0].subject)


class TestNextStepFor(_Chain):
    def test_each_person_at_each_status(self):
        reviewer = _person(self.org, 'reviewer', 'Rev', 'rev@x.com')
        run = self._run()
        expect_draft = {self.maker: 'sign', self.finance: None, self.suresh: None, reviewer: None,
                        self.superadmin: 'sign'}
        for who, step in expect_draft.items():
            self.assertEqual(payments.next_step_for(run, who), step, who.role)
        self._sign(run, self.maker)
        expect_signed = {self.maker: None, self.finance: 'approve', self.suresh: None,
                         reviewer: None, self.superadmin: 'approve'}
        for who, step in expect_signed.items():
            self.assertEqual(payments.next_step_for(run, who), step, who.role)
        self._sign(run, self.finance)
        run.refresh_from_db()
        for who in expect_signed:
            self.assertIsNone(payments.next_step_for(run, who))      # completed: nobody

    def test_a_super_fills_one_slot_only(self):
        run = self._run()
        self._sign(run, self.superadmin)                               # maker
        self.assertIsNone(payments.next_step_for(run, self.superadmin))
        self.assertEqual(self._refused(run, self.superadmin), 'same_signer')
        self._sign(run, self.finance)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_another_organisation_s_approver_is_refused_by_the_service_itself(self):
        other = _make_org(code='fa-other', name='Other')
        foreign = _person(other, 'finance', 'Foreign Fin', 'foreign@x.com')
        run = self._run()
        self._sign(run, self.maker)
        self.assertIsNone(payments.next_step_for(run, foreign))
        self.assertEqual(self._refused(run, foreign), 'wrong_role')

    def test_who_may_read_and_prepare(self):
        reviewer = _person(self.org, 'reviewer', 'Rev', 'rev2@x.com')
        self.assertEqual([payments.may_read(a) for a in (self.maker, self.finance, self.suresh,
                                                          reviewer, self.superadmin)],
                         [True, True, True, False, True])
        self.assertEqual([payments.may_prepare(a) for a in (self.maker, self.finance, self.suresh,
                                                             reviewer, self.superadmin)],
                         [True, False, True, False, True])


class TestTheRowLock(_Chain):
    def test_a_stale_copy_cannot_approve_a_run_already_completed(self):
        run = self._run()
        self._sign(run, self.maker)
        stale = PaymentRun.objects.get(pk=run.pk)                      # read while admin_signed
        self._sign(run, self.finance)                                  # completes and pays
        second = _person(self.org, 'finance', 'Second Fin', 'fin2@x.com')
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.sign(stale, second, second.name)
        self.assertEqual(cm.exception.code, 'bad_state')               # re-read under the lock
        self.assertEqual(Disbursement.objects.filter(status='released').count(), 1)


class TestWalletCreditsKeepToday(TestCase):
    """Owner question 6: credits keep Admin records -> Finance CHECKS -> the org admin countersigns.
    The shared predicate was split (`credit_check_required`), so this chain is byte-identical."""

    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org(code='fa-cr')
        cls.gift = Programme.objects.create(organisation=cls.org, code='fa-cr-p', name_en='Gift')
        cls.sponsor = Sponsor.objects.create(supabase_user_id='fa-sp', name='Ben',
                                             email='ben@x.com', status='approved')
        SponsorProgrammeMembership.objects.create(sponsor=cls.sponsor, programme=cls.gift,
                                                  status='approved')
        cls.maker = _person(cls.org, 'admin', 'Kulaly Maker', 'kc@x.com')
        cls.suresh = _person(cls.org, 'org_admin', 'Suresh Lead', 'sc@x.com')

    def _credit(self):
        return svc.record_admin_credit(sponsor=self.sponsor, programme=self.gift,
                                       amount=Decimal('500'), external_reference='TRF-1',
                                       admin=self.maker)

    def test_a_finance_person_still_checks_credits_and_the_org_admin_still_confirms(self):
        fin = _person(self.org, 'finance', 'Fina Approver', 'fc@x.com')
        self.assertTrue(payments.credit_check_required(self.org))
        self.assertFalse(payments.finance_check_required(self.org))    # runs: no check
        credit = self._credit()
        svc.sign_admin_credit(credit, self.maker, self.maker.name)
        with self.assertRaises(svc.CreditError) as cm:
            svc.sign_admin_credit(credit, self.suresh, self.suresh.name)
        self.assertEqual(cm.exception.code, 'finance_check_required')
        svc.sign_admin_credit(credit, fin, fin.name)
        self.assertEqual(credit.status, Donation.STATUS_FINANCE_CHECKED)
        with self.assertRaises(svc.CreditError) as cm:
            svc.sign_admin_credit(credit, fin, fin.name)              # Finance never confirms
        self.assertEqual(cm.exception.code, 'wrong_role')
        svc.sign_admin_credit(credit, self.suresh, self.suresh.name)
        self.assertEqual(credit.status, Donation.STATUS_CONFIRMED)

    def test_a_custom_run_checker_does_not_arm_the_credit_check(self):
        _person(self.org, 'admin', 'Third Signer', 'tc@x.com', permissions=['payments_check'])
        self.assertTrue(payments.finance_check_required(self.org))     # runs: armed
        self.assertFalse(payments.credit_check_required(self.org))     # credits: today's rule
        credit = self._credit()
        svc.sign_admin_credit(credit, self.maker, self.maker.name)
        svc.sign_admin_credit(credit, self.suresh, self.suresh.name)   # two steps, as today
        self.assertEqual(credit.status, Donation.STATUS_CONFIRMED)

    def test_the_credit_rule_is_the_old_run_rule_verbatim(self):
        self.assertFalse(payments.credit_check_required(None))
        fin = _person(self.org, 'finance', 'Fina Approver', 'fv@x.com')
        self.assertTrue(payments.credit_check_required(self.org))
        PartnerAdmin.objects.filter(pk=fin.pk).update(is_active=False)
        self.assertFalse(payments.credit_check_required(self.org))


class TestEditAndCancelCannotReopenAPaidRun(_Chain):
    """Review fix 1 (2026-10-19, HIGH): an edit or a cancel from a STALE copy, landing after the
    approval, reopened a completed, paid run — and a second approval paid it again. `set_item` and
    `cancel` now re-read the run under the row lock and refuse; `_revert_to_draft` clears all three
    triples; `complete` refuses a run already paid."""

    def _paid_run_and_stale_copies(self):
        run = self._run()
        self._sign(run, self.maker)
        stale_run = PaymentRun.objects.get(pk=run.pk)                  # read while admin_signed
        stale_item = stale_run.items.select_related('run').first()
        self._sign(run, self.finance)                                  # completes and pays
        return run, stale_run, stale_item

    def test_a_stale_edit_after_the_approval_is_refused_and_pays_nothing_more(self):
        run, _, stale_item = self._paid_run_and_stale_copies()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.set_item(stale_item, amount='150')
        self.assertEqual(cm.exception.code, 'not_editable')
        run.refresh_from_db()
        self.assertEqual((run.status, run.org_admin_signed_email), ('completed', 'fina@x.com'))
        self.assertIsNotNone(run.items.first().disbursement_id)        # the link survives
        # The reviewer's sequence can no longer even start: nothing to re-sign, nothing to re-pay.
        self.assertEqual(self._refused(run, self.maker), 'bad_state')
        self.assertEqual(Disbursement.objects.filter(status='released').count(), 1)

    def test_a_stale_cancel_after_the_approval_is_refused(self):
        run, stale_run, _ = self._paid_run_and_stale_copies()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.cancel(stale_run)
        self.assertEqual(cm.exception.code, 'bad_state')
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_an_edit_reverting_a_signed_run_clears_all_three_signatures(self):
        run = self._run()
        self._sign(run, self.maker)
        PaymentRun.objects.filter(pk=run.pk).update(
            status='finance_checked', finance_signed_email='third@x.com',
            org_admin_signed_name='Ghost', org_admin_signed_email='ghost@x.com')
        payments.set_item(PaymentRun.objects.get(pk=run.pk).items.select_related('run').first(),
                          amount='150')
        run.refresh_from_db()
        self.assertEqual(run.status, 'draft')
        self.assertEqual((run.admin_signed_email, run.finance_signed_email,
                          run.org_admin_signed_email, run.org_admin_signed_name), ('', '', '', ''))
        self.assertIsNone(run.org_admin_signed_at)

    def test_an_edit_landing_after_the_maker_signed_reverts_rather_than_changing_a_signed_list(self):
        run = self._run()
        stale_item = PaymentRun.objects.get(pk=run.pk).items.select_related('run').first()  # 'draft'
        self._sign(run, self.maker)
        payments.set_item(stale_item, amount='150')     # sees admin_signed under the lock
        run.refresh_from_db()
        self.assertEqual((run.status, run.admin_signed_email), ('draft', ''))

    def test_complete_refuses_a_run_already_paid(self):
        run, _, _ = self._paid_run_and_stale_copies()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.complete(run)
        self.assertEqual(cm.exception.code, 'already_paid')
        self.assertEqual(Disbursement.objects.filter(status='released').count(), 1)


class TestTheCheckIsArmedPerRun(_Chain):
    """Review fix 2: the check is required for a run only if somebody ELIGIBLE for THAT run holds it."""

    def test_a_maker_who_is_the_only_checker_goes_straight_to_approval(self):
        both = _person(self.org, 'admin', 'Both Hats', 'both@x.com',
                       permissions=['payments_prepare', 'payments_check'])
        run = self._run()
        mail.outbox = []
        self._sign(run, both)
        self.assertFalse(payments.check_required_for(run))
        self.assertEqual(self._approval_to(), ['fina@x.com'])          # no check email at all
        self.assertEqual(payments.next_step_for(run, self.finance), 'approve')
        self._sign(run, self.finance)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_another_checker_still_arms_it(self):
        both = _person(self.org, 'admin', 'Both Hats', 'both@x.com',
                       permissions=['payments_prepare', 'payments_check'])
        other = _person(self.org, 'admin', 'Other Checker', 'oc@x.com', permissions=['payments_check'])
        run = self._run()
        self._sign(run, both)
        self.assertTrue(payments.check_required_for(run))
        self.assertEqual(payments.next_step_for(run, self.finance), None)
        self.assertEqual(payments.next_step_for(run, other), 'check')


class TestAnApproverWhoHasNeverSignedIn(_Chain):
    """Review fix 4: production — BrightPath's only Finance person had never signed in. A holder who
    has never signed in is not eligible, so the fallback applies; the moment they sign in, they are."""

    def test_the_org_admin_approves_until_finance_first_signs_in(self):
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(first_seen_at=None)
        self.finance.refresh_from_db()
        run = self._run()
        mail.outbox = []
        self._sign(run, self.maker)
        # The "please approve" email goes to whoever CAN approve: the org admin, not Finance.
        self.assertEqual(self._approval_to(), ['suresh@x.com'])
        self.assertTrue(payments.approver_fallback(run))
        self.assertEqual(payments.next_step_for(run, self.suresh), 'approve')
        self.assertIsNone(payments.next_step_for(run, self.finance))
        # Finance signs in (get_admin stamps first_seen_at): the approval is theirs again.
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(first_seen_at=timezone.now())
        self.finance.refresh_from_db()
        self.assertFalse(payments.approver_fallback(run))
        self.assertIsNone(payments.next_step_for(run, self.suresh))
        self.assertEqual(payments.next_step_for(run, self.finance), 'approve')

    def test_a_checker_who_has_never_signed_in_does_not_arm_the_check(self):
        _person(self.org, 'admin', 'Silent Checker', 'sc@x.com', permissions=['payments_check'],
                first_seen_at=None)
        run = self._run()
        self._sign(run, self.maker)
        self.assertFalse(payments.check_required_for(run))
        self.assertFalse(payments.finance_check_required(self.org))
        self.assertEqual(payments.next_step_for(run, self.finance), 'approve')
