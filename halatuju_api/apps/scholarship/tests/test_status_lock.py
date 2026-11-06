"""Sprint A1.4 (TD-383 part 1) — no money moves on a status read earlier.

Every money writer now re-reads the application under its row lock (`status_lock`) before it pays:

  * TD-367: a payment run's completion refuses a student CLOSED after she was put on the run
    (`not_payable_in_run`, with the count; the approval rolls back and the run stays signed);
  * TD-365: a sponsor's fund and an officer's close of one `recommended` case cannot both win;
  * TD-420: a tranche release sees a hold (or a close) committed after the page loaded it, and two
    presses of Release cannot both pay one tranche.

HOW THE "TWO TRANSACTIONS" ARE STAGED. The test database is SQLite, which ignores
`select_for_update`, and the suite has no real-concurrency harness (no TransactionTestCase, no
threads; under xdist each worker owns one SQLite file). So, as the rest of the suite does
(`test_finance_approves.TestTheRowLock`, `test_source_witness`), each race is staged in its two
possible orders: the losing writer holds a copy read BEFORE the winner committed, and must refuse on
the re-read. On PostgreSQL the same re-read happens after the lock has waited for the winner.
"""
import inspect
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import closure, disbursement, maintenance, payments, status_lock
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Disbursement, Donation, ScholarshipApplication, Sponsor, Sponsorship, StudentActivity,
)
from apps.scholarship.models.activity import EVENT_PAYMENT_RELEASED
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, unique_suffix,
)
from apps.scholarship.tests.test_endpoints_disbursements import fund_through_the_product
from apps.scholarship.tests.test_on_hold_money import _paid_cohort_year_and_pathway

API = '/api/v1/admin/scholarship/'


def _next_period():
    today = timezone.localdate()
    return date(today.year + (today.month == 12), today.month % 12 + 1, 1)


def _funded_sponsor(app, amount=None):
    sponsor = Sponsor.objects.create(
        supabase_user_id=unique_suffix('a14-sponsor-'), name='Test Funder',
        email=f'{unique_suffix("a14-funder-")}@example.test', status='approved',
        consent_at=timezone.now())
    Donation.objects.create(sponsor=sponsor, amount=Decimal(amount or app.award_amount),
                            programme=app.programme)
    return sponsor


# ── the helper itself ───────────────────────────────────────────────────────────────────────────

class TestTheHelper(TestCase):
    def test_it_refuses_outside_a_transaction(self):
        app = make_application('recommended')
        # TestCase wraps each test in a transaction, so step outside it with the low-level flag.
        conn = transaction.get_connection()
        saved = conn.in_atomic_block
        conn.in_atomic_block = False
        try:
            with self.assertRaises(RuntimeError):
                status_lock.lock_application_for(app, ('recommended',))
        finally:
            conn.in_atomic_block = saved

    def test_it_refreshes_the_callers_copy_from_the_row(self):
        app = make_application('active')
        stale = ScholarshipApplication.objects.get(pk=app.pk)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            maintenance_substate='on_hold', payment_credit=Decimal('50'))
        with transaction.atomic():
            got = status_lock.lock_application_for(stale, ('active',))
        self.assertIs(got, stale)
        self.assertEqual((stale.maintenance_substate, stale.payment_credit),
                         ('on_hold', Decimal('50')))

    def test_it_refuses_a_status_the_caller_does_not_allow(self):
        app = make_application('closed')
        with transaction.atomic(), self.assertRaises(status_lock.StatusRefused) as cm:
            status_lock.lock_application_for(app, ('active', 'maintenance'))
        self.assertEqual(cm.exception.status, 'closed')

    def test_a_pk_returns_the_locked_row(self):
        app = make_application('active')
        with transaction.atomic():
            row = status_lock.lock_application_for(app.pk, ('active',))
        self.assertEqual((row.pk, row.status), (app.pk, 'active'))

    def test_a_missing_row_is_refused(self):
        with transaction.atomic(), self.assertRaises(status_lock.StatusRefused) as cm:
            status_lock.lock_application_for(987654321, ('active',))
        self.assertIsNone(cm.exception.status)

    def test_many_rows_report_the_refused_and_refresh_the_rest(self):
        a, b = make_application('active'), make_application('active')
        stale_a, stale_b = (ScholarshipApplication.objects.get(pk=x.pk) for x in (a, b))
        ScholarshipApplication.objects.filter(pk=b.pk).update(status='closed')
        with transaction.atomic():
            refused = status_lock.lock_applications_for([stale_a, stale_b], ('active',))
        self.assertEqual(refused, [stale_b])
        self.assertEqual(stale_b.status, 'closed')


# ── TD-367: a payment run cannot pay a student closed after she was put on it ───────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class TestARunDoesNotPayAClosedStudent(TestCase):
    def setUp(self):
        self.period = _next_period()
        self.pay_on = max(timezone.localdate(), payments.earliest_payment_date(self.period))
        year, pathway = _paid_cohort_year_and_pathway(self.period)
        self.cohort = make_cohort(year=year)
        org = self.cohort.owning_organisation
        self.maker = make_admin('admin', owning_org=org, name='Maker One')
        self.approver = make_admin('org_admin', owning_org=org, name='Approver One')
        self.closing, self.other = (make_application(
            'awarded', cohort=self.cohort, vircle_activated_at=timezone.now(),
            vircle_id=payments.vircle_id_prefix() + suffix, chosen_pathway=pathway,
            reporting_date=date(year, 6, 8)) for suffix in ('74001', '74002'))
        self.run = payments.create_run(org, self.cohort.programme, self.pay_on, self.period,
                                       by_email=self.maker.email)
        self.assertEqual(self.run.items.filter(included=True).count(), 2)

    def _close(self):
        closure.close_application(self.closing, closure_reason='withdrawn', by_email='o@x.test')

    def test_complete_refuses_a_student_closed_after_the_run_was_made(self):
        self._close()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.complete(self.run)
        self.assertEqual((cm.exception.code, cm.exception.count), ('not_payable_in_run', 1))
        self.assertFalse(Disbursement.objects.filter(
            application__in=[self.closing, self.other]).exists())
        self.assertFalse(StudentActivity.objects.filter(event=EVENT_PAYMENT_RELEASED).exists())

    def test_the_approval_answers_400_with_the_count_and_the_run_stays_signed_and_unpaid(self):
        sign = f'{API}payment-runs/{self.run.id}/sign/'
        r = authed_client(self.maker).post(sign, {'typed_name': 'Maker One'}, format='json')
        self.assertEqual(r.json()['status'], 'admin_signed', r.content)
        self._close()                                   # lands between the two signatures
        r = authed_client(self.approver).post(sign, {'typed_name': 'Approver One'}, format='json')
        self.assertEqual((r.status_code, r.json()['code'], r.json()['count']),
                         (400, 'not_payable_in_run', 1))
        self.run.refresh_from_db()
        self.assertEqual((self.run.status, self.run.org_admin_signed_at), ('admin_signed', None))
        self.assertFalse(Disbursement.objects.exists())

    def test_once_excluded_the_rest_of_the_run_is_paid(self):
        self._close()
        payments.set_item(self.run.items.get(application=self.closing), included=False,
                          exclude_reason='Closed')
        payments.complete(self.run)
        self.assertFalse(Disbursement.objects.filter(application=self.closing).exists())
        self.assertTrue(Disbursement.objects.filter(application=self.other,
                                                    status='released').exists())

    def test_a_hold_committed_after_the_run_was_read_is_seen(self):
        stale_run = type(self.run).objects.get(pk=self.run.pk)
        ScholarshipApplication.objects.filter(pk=self.closing.pk).update(
            maintenance_substate='on_hold')
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.complete(stale_run)
        self.assertEqual(cm.exception.code, 'on_hold_in_run')

    def test_the_credit_is_decremented_from_the_locked_value(self):
        item = self.run.items.get(application=self.other)
        type(item).objects.filter(pk=item.pk).update(credit_applied=Decimal('30'))
        stale_run = type(self.run).objects.get(pk=self.run.pk)
        # A credit recorded after the run was read: the run must not overwrite it with a stale sum.
        ScholarshipApplication.objects.filter(pk=self.other.pk).update(payment_credit=Decimal('100'))
        payments.complete(stale_run)
        self.other.refresh_from_db()
        self.assertEqual(self.other.payment_credit, Decimal('70'))


# ── TD-365: a fund and a close cannot both win ─────────────────────────────────────────────────

class TestFundVersusClose(TestCase):
    def setUp(self):
        self.app = make_application('recommended')
        self.sponsor = _funded_sponsor(self.app)

    def test_close_first_then_a_fund_from_the_stale_copy_is_refused(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)        # the sponsor's page
        closure.close_application(self.app, closure_reason='stalled', by_email='o@x.test')
        with self.assertRaises(svc.SponsorshipError) as cm:
            svc.fund_student(self.sponsor, stale)
        self.assertEqual(cm.exception.code, 'not_fundable')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'closed')
        self.assertFalse(Sponsorship.objects.filter(application=self.app).exists())

    def test_fund_first_then_a_close_from_the_stale_copy_is_refused(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)        # the officer's page
        svc.fund_student(self.sponsor, self.app)
        with self.assertRaises(closure.ClosureError) as cm:
            closure.close_application(stale, closure_reason='stalled', by_email='o@x.test')
        self.assertEqual(cm.exception.code, 'sponsorship_open')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'awarded')
        self.assertEqual(Sponsorship.objects.filter(application=self.app,
                                                    status='offered').count(), 1)

    def test_two_funds_from_stale_copies_make_one_award(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)
        second = _funded_sponsor(self.app)
        svc.fund_student(self.sponsor, self.app)
        with self.assertRaises(svc.SponsorshipError) as cm:
            svc.fund_student(second, stale)
        self.assertEqual(cm.exception.code, 'not_fundable')
        self.assertEqual(Sponsorship.objects.filter(application=self.app).count(), 1)

    def test_the_fund_spends_the_award_amount_as_stored_now(self):
        stale = ScholarshipApplication.objects.get(pk=self.app.pk)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(award_amount=Decimal('1000'))
        sp = svc.fund_student(self.sponsor, stale)
        self.assertEqual(sp.amount, Decimal('1000'))
        self.assertEqual(stale.status, 'awarded')      # the caller's copy follows the write


# ── TD-420: a tranche release reads the hold on a locked row ───────────────────────────────────

class TestTrancheReleaseUnderTheLock(TestCase):
    def setUp(self):
        self.app, _, _ = fund_through_the_product(make_cohort(), reviewer=make_admin('reviewer'))
        self.assertEqual(self.app.status, 'active')
        self.tranche = disbursement.schedule_tranche(self.app, amount='500')

    def _stale(self):
        return Disbursement.objects.select_related('application').get(pk=self.tranche.pk)

    def test_a_hold_placed_after_the_page_loaded_stops_the_release(self):
        stale = self._stale()
        maintenance.set_substate(self.app, 'on_hold', by_email='o@x.test')
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.release_tranche(stale, by_email='o@x.test')
        self.assertEqual(cm.exception.code, 'on_hold')
        self.tranche.refresh_from_db()
        self.assertEqual(self.tranche.status, 'scheduled')

    def test_a_close_after_the_page_loaded_stops_the_release(self):
        stale = self._stale()
        closure.close_application(self.app, closure_reason='withdrawn', by_email='o@x.test')
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.release_tranche(stale, by_email='o@x.test')
        self.assertEqual(cm.exception.code, 'not_in_programme')
        self.tranche.refresh_from_db()
        self.assertEqual(self.tranche.status, 'scheduled')

    def test_two_presses_from_stale_copies_pay_the_tranche_once(self):
        first, second = self._stale(), self._stale()
        disbursement.release_tranche(first, by_email='o@x.test')
        with self.assertRaises(disbursement.DisbursementError) as cm:
            disbursement.release_tranche(second, by_email='o@x.test')
        self.assertEqual(cm.exception.code, 'bad_state')
        self.assertEqual(StudentActivity.objects.filter(
            application=self.app, event=EVENT_PAYMENT_RELEASED).count(), 1)

    def test_the_callers_application_follows_the_first_release(self):
        stale = self._stale()
        disbursement.release_tranche(stale, by_email='o@x.test')
        self.assertEqual(stale.application.status, 'maintenance')   # the view serialises this


# ── the static pin: every money writer TD-383 names goes through the helper ─────────────────────

class TestEveryMoneyWriterUsesTheHelper(TestCase):
    """Every writer TD-383 names locks and re-reads before it writes (A1.4 money, A1.5 lifecycle).
    Each pattern is the writer's way into `status_lock` (directly, or through its module's one
    helper: `_lock_open_case`, `_lock_tranche`). A new status-dependent writer joins this list."""
    WRITERS = (   # (module, function name, the lock it must call)
        ('payments', 'complete', r'lock_applications?_for\('),
        ('sponsorship', 'fund_student', r'lock_applications?_for\('),
        ('sponsorship', 'fund_student', r'lock_sponsor_wallet\('),          # the wallet, A1.5
        ('sponsorship', 'reinstate_lapsed_sponsorship', r'lock_sponsor_wallet\('),
        ('disbursement', 'release_tranche', r'lock_applications?_for\('),
        ('disbursement', 'release_tranche', r'_lock_tranche\('),
        ('disbursement', 'withhold_tranche', r'_lock_tranche\('),
        ('disbursement', 'return_tranche', r'_lock_tranche\('),
        ('disbursement', 'mark_due', r'_lock_tranche\('),
        ('disbursement', '_lock_tranche', r'lock_application_for\('),
        ('services.decline', 'admin_reject', r'lock_application_for\('),   # TD-365 decline side
        ('services.intake', 'submit_application', r'select_for_update\(\)'),  # TD-348 / TD-351
        ('scheduling', '_lock_open_case', r'lock_application_for\('),      # TD-368
        ('scheduling', 'propose_slots', r'_lock_open_case\('),
        ('scheduling', 'book_slot', r'_lock_open_case\('),
    )

    def test_each_writer_locks_through_status_lock(self):
        import importlib
        for module, name, pattern in self.WRITERS:
            with self.subTest(writer=f'{module}.{name}', pattern=pattern):
                writer = getattr(importlib.import_module(f'apps.scholarship.{module}'), name, None)
                self.assertIsNotNone(writer, f'{module}.{name} is gone: move its pin with it')
                self.assertRegex(inspect.getsource(inspect.unwrap(writer)), pattern)
