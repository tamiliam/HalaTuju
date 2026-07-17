"""Payments module — Sprint P1 (docs/plans/2026-07-16-payments-module-plan.md).

Service-level tests (no API — that's P2): the Vircle-ID validator (D9), the eligibility
matrix (D4), the flat-rate + credit formula against the three real regularisation cases (D6),
the run lifecycle + maker→checker sign-off state machine (D2), completion ledger writes +
credit decrement (D3/D6), and the CSV backfill (dry-run reconciliation + idempotency + the
simulated 1 Aug 2026 run) (D8). Fixtures use INVENTED data only (never the owner's CSV/PII).
"""
import csv
import io
import os
import tempfile
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import payments
from apps.scholarship.models import (
    Disbursement, PaymentRun, PaymentRunItem, ScholarshipApplication, ScholarshipCohort,
)

D = Decimal


def _make_org(code='pay-bp', name='BrightPath'):
    return PartnerOrganisation.objects.create(code=code, name=name)


def _make_cohort(org, code='pay-c', year=2026):
    return ScholarshipCohort.objects.create(code=code, name='B40', year=year, owning_organisation=org)


_SEQ = {'n': 0}


def _make_app(cohort, org, *, pathway='matric', award='2000', reporting=None,
              status='awarded', vircle_suffix='0001', substate='on_track', nric=None, name=None):
    _SEQ['n'] += 1
    i = _SEQ['n']
    prof = StudentProfile.objects.create(
        supabase_user_id=f'pay-stud-{i}',
        nric=nric or f'{i:06d}-14-{i:04d}',
        name=name or f'Student {i}',
        contact_phone=f'01{i:08d}',
    )
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=prof, owning_organisation=org, status=status,
        chosen_pathway=pathway, award_amount=D(award), reporting_date=reporting,
        maintenance_substate=substate,
        vircle_id=(payments.vircle_id_prefix() + vircle_suffix) if vircle_suffix else '',
    )
    return app


def _released(app, amount, *, when=None, seq=1):
    return Disbursement.objects.create(
        application=app, amount=D(str(amount)), status='released', sequence=seq,
        released_at=when or timezone.now(), reference='vircle:test')


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestVircleId(TestCase):
    def test_valid_prefixed_13_digit(self):
        self.assertTrue(payments.valid_vircle_id('8000400175123'))

    def test_rejects_wrong_length(self):
        self.assertFalse(payments.valid_vircle_id('800040017512'))    # 12
        self.assertFalse(payments.valid_vircle_id('80004001751234'))  # 14

    def test_rejects_wrong_prefix(self):
        self.assertFalse(payments.valid_vircle_id('9000400175123'))

    def test_nine_digit_prefix_headroom(self):
        # Owner 2026-07-17: the fixed prefix is 9 digits (800040017) + 4 typed digits — so an
        # account numbered past …175999 (e.g. …176xxx) is now valid, but a different 9-prefix isn't.
        self.assertTrue(payments.valid_vircle_id('8000400176123'))
        self.assertFalse(payments.valid_vircle_id('8000400169999'))

    def test_rejects_non_digits_and_blank(self):
        self.assertFalse(payments.valid_vircle_id('80004001751az'))
        self.assertFalse(payments.valid_vircle_id(''))
        self.assertFalse(payments.valid_vircle_id(None))


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestEligibility(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)
        cls.pay_date = date(2026, 8, 1)

    def _elig(self, app):
        return payments.eligibility(app, self.pay_date)

    def test_started_via_reporting_date(self):
        app = _make_app(self.cohort, self.org, reporting=date(2026, 7, 1))
        self.assertTrue(self._elig(app)['eligible'])

    def test_not_started_reporting_after_payment_date(self):
        app = _make_app(self.cohort, self.org, reporting=date(2026, 9, 1))
        e = self._elig(app)
        self.assertFalse(e['started'])
        # not-started rows are excluded from eligible_rows entirely
        self.assertNotIn(app.id, {r['application'].id for r in payments.eligible_rows(self.org, self.pay_date)})

    def test_pathway_payment_start_months(self):
        # Owner 2026-07-16: STPM/Matric/Asasi → July; Poly/UA Diploma (university) → Aug; PISMP → Sep.
        for pathway, start in [('stpm', date(2026, 7, 1)), ('matric', date(2026, 7, 1)),
                               ('asasi', date(2026, 7, 1)), ('poly', date(2026, 8, 1)),
                               ('university', date(2026, 8, 1)), ('pismp', date(2026, 9, 1))]:
            app = _make_app(self.cohort, self.org, pathway=pathway, reporting=None)
            self.assertEqual(payments._pathway_payment_start(app), start, pathway)
            self.assertTrue(payments.eligibility(app, start)['started'], pathway)
            # the month BEFORE the floor is never started, even for a null reporting date
            before = date(start.year, start.month - 1, 1)
            self.assertFalse(payments.eligibility(app, before)['started'], pathway)

    def test_floor_applies_even_with_an_early_reporting_date(self):
        # A poly student who reported in June is still NOT paid before the August floor.
        app = _make_app(self.cohort, self.org, pathway='poly', reporting=date(2026, 6, 20))
        self.assertFalse(payments.eligibility(app, date(2026, 7, 1))['started'])   # July < Aug floor
        self.assertTrue(payments.eligibility(app, date(2026, 8, 1))['started'])

    def test_continuing_pismp_not_paid_before_september(self):
        # Tavanisah case: a continuing PISMP student (reported a prior year) is excluded from an
        # August run and only appears in September (the PISMP floor).
        app = _make_app(self.cohort, self.org, pathway='pismp', reporting=date(2024, 8, 26))
        self.assertFalse(payments.eligibility(app, date(2026, 8, 1))['started'])
        self.assertTrue(payments.eligibility(app, date(2026, 9, 1))['started'])

    def test_reporting_date_still_gates_a_late_arrival(self):
        # The floor is necessary but not sufficient — a student who hasn't reported isn't paid.
        app = _make_app(self.cohort, self.org, pathway='matric', reporting=date(2026, 9, 15))
        self.assertFalse(payments.eligibility(app, date(2026, 8, 1))['started'])   # floor OK, not reported

    def test_open_vircle_setup_task_greyed_unconfirmed(self):
        # Emailed the setup task but not resolved → excluded with 'vircle_unconfirmed'.
        from apps.scholarship.models import ResolutionItem
        from apps.scholarship.resolution import VIRCLE_CODE
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        ResolutionItem.objects.create(application=app, code=VIRCLE_CODE, status='open')
        e = self._elig(app)
        self.assertFalse(e['eligible'])
        self.assertFalse(e['vircle_ready'])
        self.assertIn('vircle_unconfirmed', e['reasons'])
        self.assertNotIn('no_vircle_id', e['reasons'])   # it HAS an id — just unconfirmed

    def test_resolved_vircle_setup_task_is_ready(self):
        from apps.scholarship.models import ResolutionItem
        from apps.scholarship.resolution import VIRCLE_CODE
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        ResolutionItem.objects.create(application=app, code=VIRCLE_CODE, status='resolved')
        self.assertTrue(self._elig(app)['eligible'])

    def test_legacy_no_setup_task_is_ready(self):
        # The 8 legacy students have no vircle_setup_pending item at all → the id alone suffices.
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        self.assertFalse(app.resolution_items.exists())
        self.assertTrue(self._elig(app)['eligible'])

    def test_status_filter_excludes_recommended(self):
        app = _make_app(self.cohort, self.org, status='recommended', reporting=date(2026, 6, 1))
        self.assertNotIn(app.id, {r['application'].id for r in payments.eligible_rows(self.org, self.pay_date)})

    def test_no_vircle_id_greyed(self):
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1), vircle_suffix='')
        e = self._elig(app)
        self.assertFalse(e['eligible'])
        self.assertIn('no_vircle_id', e['reasons'])

    def test_on_hold_greyed(self):
        app = _make_app(self.cohort, self.org, status='maintenance', substate='on_hold',
                        reporting=date(2026, 6, 1))
        e = self._elig(app)
        self.assertFalse(e['eligible'])
        self.assertIn('on_hold', e['reasons'])

    def test_no_balance_greyed(self):
        app = _make_app(self.cohort, self.org, award='200', reporting=date(2026, 6, 1))
        _released(app, 200)
        e = self._elig(app)
        self.assertFalse(e['eligible'])
        self.assertIn('no_balance', e['reasons'])

    def test_org_fenced(self):
        other = _make_org(code='pay-other', name='Other')
        other_cohort = _make_cohort(other, code='pay-c2')
        mine = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        theirs = _make_app(other_cohort, other, reporting=date(2026, 6, 1))
        ids = {r['application'].id for r in payments.eligible_rows(self.org, self.pay_date)}
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids)


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestPeriodDedup(TestCase):
    """A month is never paid twice, even when run dates differ (owner 2026-07-16)."""
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)

    def _completed_run(self, app, period_month, amount='200', ref=None):
        run = PaymentRun.objects.create(
            organisation=self.org, payment_date=period_month, period_month=period_month,
            status='completed', reference=ref or f'done-{period_month}-{app.id}')
        PaymentRunItem.objects.create(run=run, application=app, included=True, amount=D(amount))
        return run

    def test_already_paid_for_month_greyed(self):
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))  # matric, July floor
        self._completed_run(app, date(2026, 7, 1))
        e = payments.eligibility(app, date(2026, 7, 17), period_month=date(2026, 7, 1))
        self.assertFalse(e['eligible'])
        self.assertIn('already_paid', e['reasons'])

    def test_paid_july_still_eligible_in_august(self):
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        self._completed_run(app, date(2026, 7, 1))
        self.assertTrue(payments.eligibility(app, date(2026, 8, 1), period_month=date(2026, 8, 1))['eligible'])

    def test_only_completed_runs_block(self):
        app = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        run = PaymentRun.objects.create(organisation=self.org, payment_date=date(2026, 7, 1),
                                        period_month=date(2026, 7, 1), status='draft', reference='draft-x')
        PaymentRunItem.objects.create(run=run, application=app, included=True, amount=D('200'))
        self.assertTrue(payments.eligibility(app, date(2026, 7, 17), period_month=date(2026, 7, 1))['eligible'])

    def test_create_run_excludes_already_paid_for_the_month(self):
        paid = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        fresh = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        self._completed_run(paid, date(2026, 7, 1))
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 10)):
            run = payments.create_run(self.org, date(2026, 7, 17), date(2026, 7, 1), by_email='m@x.com')
        ids = set(run.items.values_list('application_id', flat=True))
        self.assertIn(fresh.id, ids)
        self.assertNotIn(paid.id, ids)

    def test_reference_carries_the_pay_date(self):
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 10)):
            run = payments.create_run(self.org, date(2026, 7, 17), date(2026, 7, 20), by_email='m@x.com')
        self.assertEqual(run.reference, 'PR-2026-07-17')
        self.assertEqual(run.period_month, date(2026, 7, 1))   # normalised to the 1st


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestAmountAndCredit(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)

    def test_flat_rate_no_credit(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1))
        self.assertEqual(payments.default_amount(app), D('200'))

    def test_overpayment_credit_100(self):
        # The two RM300 regularisations: a credit of 100 → next run defaults to RM100.
        app = _make_app(self.cohort, self.org, award='3000', reporting=date(2026, 6, 1))
        _released(app, 300)
        app.payment_credit = D('100'); app.save()
        self.assertEqual(payments.default_amount(app), D('100'))
        self.assertEqual(payments._credit_applied(app), D('100'))

    def test_advance_credit_200_zeroes_the_run(self):
        # SHAARVESHWAAR: paid before starting, credit 200 → next run defaults to RM0.
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 7, 19))
        _released(app, 200)
        app.payment_credit = D('200'); app.save()
        self.assertEqual(payments.default_amount(app), D('0'))
        self.assertEqual(payments._credit_applied(app), D('200'))

    def test_capped_at_remaining_award(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1))
        _released(app, 1900)   # remaining 100 < rate 200
        self.assertEqual(payments.default_amount(app), D('100'))

    def test_paid_to_date_sums_only_released(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1))
        _released(app, 200, seq=1)
        Disbursement.objects.create(application=app, amount=D('200'), status='scheduled', sequence=2)
        self.assertEqual(payments.paid_to_date(app), D('200'))


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestRunLifecycle(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)

    def _create(self, pay_date=date(2026, 8, 1)):
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            return payments.create_run(self.org, pay_date, pay_date.replace(day=1), by_email='maker@x.com')

    def test_past_date_rejected(self):
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 8, 5)):
            with self.assertRaises(payments.PaymentsError) as cm:
                payments.create_run(self.org, date(2026, 8, 1), date(2026, 8, 1))
        self.assertEqual(cm.exception.code, 'past_date')

    def test_create_run_items_only_for_eligible(self):
        elig = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        greyed = _make_app(self.cohort, self.org, reporting=date(2026, 6, 1), vircle_suffix='')  # no vircle
        run = self._create()
        app_ids = set(run.items.values_list('application_id', flat=True))
        self.assertIn(elig.id, app_ids)
        self.assertNotIn(greyed.id, app_ids)   # greyed-out students are not items

    def test_create_run_snapshots_and_amount(self):
        app = _make_app(self.cohort, self.org, award='3000', reporting=date(2026, 6, 1))
        _released(app, 300)
        app.payment_credit = D('100'); app.save()
        run = self._create()
        item = run.items.get(application=app)
        self.assertEqual(item.amount, D('100'))
        self.assertEqual(item.credit_applied, D('100'))
        self.assertEqual(item.award_amount_snapshot, D('3000'))
        self.assertEqual(item.paid_to_date_snapshot, D('300'))
        self.assertEqual(item.vircle_id_snapshot, app.vircle_id)

    def test_set_item_exclude_requires_reason(self):
        _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        run = self._create()
        item = run.items.first()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.set_item(item, included=False, exclude_reason='')
        self.assertEqual(cm.exception.code, 'reason_required')
        payments.set_item(item, included=False, exclude_reason='semester break')
        item.refresh_from_db()
        self.assertFalse(item.included)
        self.assertEqual(item.exclude_reason, 'semester break')

    def test_set_item_amount_capped_at_remaining(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1))
        _released(app, 1900)
        run = self._create()
        item = run.items.get(application=app)
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.set_item(item, amount='150')   # remaining is 100
        self.assertEqual(cm.exception.code, 'amount_over_cap')
        payments.set_item(item, amount='75')
        item.refresh_from_db()
        self.assertEqual(item.amount, D('75'))

    def test_cancel_draft(self):
        _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        run = self._create()
        payments.cancel(run)
        run.refresh_from_db()
        self.assertEqual(run.status, 'cancelled')


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestSignOff(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)
        cls.maker = PartnerAdmin.objects.create(
            supabase_user_id='mk', role='admin', is_active=True, owning_organisation=cls.org,
            name='Poongulali Veeran', email='maker@x.com')
        cls.approver = PartnerAdmin.objects.create(
            supabase_user_id='ap', role='org_admin', is_active=True, owning_organisation=cls.org,
            name='Suresh Thiru', email='approver@x.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rv', role='reviewer', is_active=True, owning_organisation=cls.org,
            name='Rev Iewer', email='rev@x.com')
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='su', is_super_admin=True, is_active=True, name='Super One', email='super@x.com')

    def _run(self):
        _make_app(self.cohort, self.org, reporting=date(2026, 6, 1))
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            return payments.create_run(self.org, date(2026, 8, 1), date(2026, 8, 1), by_email='maker@x.com')

    def test_maker_sign_notifies_org_admin(self):
        from django.core import mail
        mail.outbox = []
        run = self._run()
        payments.sign(run, self.maker, 'Poongulali Veeran')
        notes = [m for m in mail.outbox if 'countersignature' in m.subject]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].to, ['approver@x.com'])
        self.assertIn(run.reference, notes[0].subject)
        self.assertIn('Poongulali Veeran', notes[0].body)
        self.assertIn('gokula@vircle.com', notes[0].body)   # names where the instruction goes

    def test_countersign_emails_vircle_with_csv_attached(self):
        from django.core import mail
        run = self._run()
        payments.sign(run, self.maker, 'Poongulali Veeran')
        mail.outbox = []
        payments.sign(run, self.approver, 'Suresh Thiru')
        vircle = [m for m in mail.outbox if m.to == ['gokula@vircle.com']]
        self.assertEqual(len(vircle), 1)
        msg = vircle[0]
        self.assertIn('payment instruction', msg.subject)
        self.assertIn('Suresh Thiru', msg.body)
        # Owner 2026-07-17: the countersigning approver is CC'd on the Vircle instruction.
        self.assertEqual(msg.cc, ['approver@x.com'])
        fname, content, mime = msg.attachments[0]
        self.assertEqual(fname, f'{run.reference}.csv')
        self.assertEqual(mime, 'text/csv')
        self.assertIn('Wallet ID', content)
        self.assertNotIn('Phone', content)

    def test_payment_csv_columns(self):
        # Owner 2026-07-16: 'Wallet ID' (not 'Vircle ID'), and no Phone column.
        from apps.scholarship import sheets
        run = self._run()
        rows = sheets.payment_csv_rows(run)
        self.assertEqual(rows[0], ['No', 'Student NRIC', 'Wallet ID', 'Student Name',
                                   'Amount', 'Payment date', 'Run reference'])
        # Excel-safe Wallet ID: ="8000400175001" renders as text, never 8.0004E+12.
        self.assertRegex(rows[1][2], r'^="\d{13}"$')

    def test_maker_then_approver_completes(self):
        run = self._run()
        payments.sign(run, self.maker, 'Poongulali Veeran')
        run.refresh_from_db()
        self.assertEqual(run.status, 'admin_signed')
        self.assertEqual(run.admin_signed_email, 'maker@x.com')
        payments.sign(run, self.approver, 'suresh thiru')   # case-insensitive
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')
        self.assertEqual(run.org_admin_signed_email, 'approver@x.com')

    def test_name_mismatch(self):
        run = self._run()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.sign(run, self.maker, 'Wrong Name')
        self.assertEqual(cm.exception.code, 'name_mismatch')

    def test_maker_must_be_admin(self):
        run = self._run()
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.sign(run, self.reviewer, 'Rev Iewer')
        self.assertEqual(cm.exception.code, 'wrong_role')

    def test_approver_must_be_org_admin(self):
        run = self._run()
        payments.sign(run, self.maker, 'Poongulali Veeran')
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.sign(run, self.reviewer, 'Rev Iewer')
        self.assertEqual(cm.exception.code, 'wrong_role')

    def test_same_signer_blocked(self):
        # A super signs as maker; the SAME super cannot countersign.
        run = self._run()
        payments.sign(run, self.superadmin, 'Super One')
        with self.assertRaises(payments.PaymentsError) as cm:
            payments.sign(run, self.superadmin, 'Super One')
        self.assertEqual(cm.exception.code, 'same_signer')

    def test_super_can_fill_either_slot(self):
        run = self._run()
        payments.sign(run, self.superadmin, 'Super One')   # maker
        run.refresh_from_db()
        self.assertEqual(run.status, 'admin_signed')
        payments.sign(run, self.approver, 'Suresh Thiru')  # approver
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')

    def test_edit_after_admin_signed_reverts_to_draft(self):
        run = self._run()
        payments.sign(run, self.maker, 'Poongulali Veeran')
        item = run.items.first()
        payments.set_item(item, amount='150')
        run.refresh_from_db()
        self.assertEqual(run.status, 'draft')
        self.assertEqual(run.admin_signed_email, '')   # signature cleared
        self.assertIsNone(run.admin_signed_at)


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestComplete(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)
        cls.maker = PartnerAdmin.objects.create(
            supabase_user_id='mk', role='admin', is_active=True, owning_organisation=cls.org,
            name='Maker One', email='maker@x.com')
        cls.approver = PartnerAdmin.objects.create(
            supabase_user_id='ap', role='org_admin', is_active=True, owning_organisation=cls.org,
            name='Approver One', email='approver@x.com')

    def _complete_run(self):
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            run = payments.create_run(self.org, date(2026, 8, 1), date(2026, 8, 1), by_email='maker@x.com')
        payments.sign(run, self.maker, 'Maker One')
        payments.sign(run, self.approver, 'Approver One')
        run.refresh_from_db()
        return run

    def test_completion_writes_released_disbursements(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1))
        run = self._complete_run()
        self.assertEqual(run.status, 'completed')
        disb = app.disbursements.filter(status='released')
        self.assertEqual(disb.count(), 1)
        self.assertEqual(disb.first().amount, D('200'))
        self.assertEqual(disb.first().reference, f'vircle:{run.reference}')
        self.assertEqual(disb.first().scheduled_for, date(2026, 8, 1))

    def test_completion_decrements_credit_and_zero_item_writes_no_disbursement(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 7, 19))
        _released(app, 200)
        app.payment_credit = D('200'); app.save()
        run = self._complete_run()
        app.refresh_from_db()
        self.assertEqual(app.payment_credit, D('0'))                     # credit cleared
        self.assertEqual(app.disbursements.filter(status='released').count(), 1)  # the RM0 item added none

    def test_completion_does_not_flip_status(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1), status='awarded')
        self._complete_run()
        app.refresh_from_db()
        self.assertEqual(app.status, 'awarded')   # D3 — module never flips status

    def test_excluded_item_produces_no_disbursement(self):
        app = _make_app(self.cohort, self.org, award='2000', reporting=date(2026, 6, 1))
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            run = payments.create_run(self.org, date(2026, 8, 1), date(2026, 8, 1), by_email='maker@x.com')
        payments.set_item(run.items.get(application=app), included=False, exclude_reason='break')
        payments.sign(run, self.maker, 'Maker One')
        payments.sign(run, self.approver, 'Approver One')
        self.assertEqual(app.disbursements.filter(status='released').count(), 0)


# ── Backfill (D8) — 30-row fixture mirroring the prod structure (invented PII) ─────

def _backfill_specs():
    """30 specs mirroring the real batch structure: 8 paid on 30/6, 18 on 16/07, 4 not
    included; two RM300 overpayments; one paid-before-starting (RM200, reports after its
    batch). Everyone else RM200. Reproduces credits {overpay:100, overpay:100, advance:200}."""
    jun_batch, jul_batch = date(2026, 6, 30), date(2026, 7, 16)
    specs = []
    # two RM300 overpay (STPM), June batch
    specs.append(dict(kind='overpay', pathway='stpm', award='3000', reporting=date(2026, 6, 1), batch=jun_batch, monthly=300))
    specs.append(dict(kind='overpay', pathway='stpm', award='3000', reporting=date(2026, 6, 1), batch=jun_batch, monthly=300))
    # one paid-before-starting (university, reports 19 Jul, paid in the 16/07 batch)
    specs.append(dict(kind='advance', pathway='university', award='2000', reporting=date(2026, 7, 19), batch=jul_batch, monthly=200))
    # 6 more in the June batch (started by 30/6)
    for _ in range(6):
        specs.append(dict(kind='normal', pathway='matric', award='2000', reporting=date(2026, 6, 1), batch=jun_batch, monthly=200))
    # 17 more in the July batch (started by 16/07)
    for k in range(17):
        pathway = ['matric', 'asasi', 'poly', 'stpm'][k % 4]
        specs.append(dict(kind='normal', pathway=pathway, award='2000', reporting=date(2026, 7, 1), batch=jul_batch, monthly=200))
    # 4 not included (Monthly 0, no batch) — hadn't started by 16/07 (report Aug / late July)
    for k in range(4):
        pathway, rep = ('pismp', date(2026, 8, 1)) if k < 3 else ('poly', date(2026, 7, 20))
        specs.append(dict(kind='none', pathway=pathway, award='2000', reporting=rep, batch=None, monthly=0))
    return specs


@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestBackfillImport(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _make_org()
        cls.cohort = _make_cohort(cls.org)
        cls.specs = _backfill_specs()
        cls.apps = []
        for s in cls.specs:
            app = _make_app(cls.cohort, cls.org, pathway=s['pathway'], award=s['award'],
                            reporting=s['reporting'], vircle_suffix='')  # ID comes from the CSV import
            s['app'] = app
            cls.apps.append(app)

    def setUp(self):
        # Write the invented CSV to a temp file (never the repo).
        fd, self.csv_path = tempfile.mkstemp(suffix='.csv')
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(['No', 'Student NRIC', 'Vircle ID', 'Phone', 'Student Name',
                        'Monthly', 'Batch', 'Remarks', 'Remark'])
            for i, s in enumerate(self.specs, start=1):
                app = s['app']
                w.writerow([
                    i, app.profile.nric,
                    payments.vircle_id_prefix() + f'{i:04d}',
                    app.profile.contact_phone, app.profile.name,
                    s['monthly'],
                    s['batch'].strftime('%d/%m/%Y') if s['batch'] else '',
                    'Vircle ?' if s['batch'] else '', 'Paid' if s['batch'] else '',
                ])

    def tearDown(self):
        os.remove(self.csv_path)

    def _run_cmd(self, *args):
        out = io.StringIO()
        call_command('import_vircle_csv', self.csv_path, *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_dry_run_reconciles_all_and_writes_nothing(self):
        out = self._run_cmd('--dry-run')
        self.assertIn('matched: 30', out)
        self.assertIn('unmatched: 0', out)
        self.assertEqual(PaymentRun.objects.count(), 0)
        self.assertEqual(Disbursement.objects.count(), 0)
        self.assertFalse(ScholarshipApplication.objects.exclude(vircle_id='').exists())
        self.assertFalse(ScholarshipApplication.objects.exclude(payment_credit=0).exists())

    def test_live_import_creates_runs_stamps_ids_seeds_credits(self):
        self._run_cmd()
        # two completed backfill runs
        refs = set(PaymentRun.objects.values_list('reference', flat=True))
        self.assertEqual(refs, {'backfill-2026-06-30', 'backfill-2026-07-16'})
        self.assertTrue(all(r.status == 'completed' for r in PaymentRun.objects.all()))
        # released disbursements = number of PAID rows (26)
        self.assertEqual(Disbursement.objects.filter(status='released').count(), 26)
        # every application has a 13-digit vircle_id
        for app in ScholarshipApplication.objects.all():
            self.assertTrue(payments.valid_vircle_id(app.vircle_id), app.id)
        # exactly the three regularisation credits, everyone else 0
        credited = {a.id: a.payment_credit for a in ScholarshipApplication.objects.exclude(payment_credit=0)}
        overpay_ids = {s['app'].id for s in self.specs if s['kind'] == 'overpay'}
        advance_ids = {s['app'].id for s in self.specs if s['kind'] == 'advance'}
        self.assertEqual(set(credited), overpay_ids | advance_ids)
        for aid in overpay_ids:
            self.assertEqual(credited[aid], D('100'))
        for aid in advance_ids:
            self.assertEqual(credited[aid], D('200'))

    def test_import_is_idempotent(self):
        self._run_cmd()
        d1, r1 = Disbursement.objects.count(), PaymentRun.objects.count()
        credits1 = {a.id: a.payment_credit for a in ScholarshipApplication.objects.all()}
        self._run_cmd()   # again
        self.assertEqual(Disbursement.objects.count(), d1)
        self.assertEqual(PaymentRun.objects.count(), r1)
        credits2 = {a.id: a.payment_credit for a in ScholarshipApplication.objects.all()}
        self.assertEqual(credits1, credits2)

    def test_simulated_1_aug_run_matches_owner_expectations(self):
        """Acceptance: after backfill, a 1 Aug 2026 run defaults to RM100 for the two
        overpaid students, RM0 for the advance-paid student, RM200 for everyone else — and
        EXCLUDES PISMP (September floor, owner 2026-07-16)."""
        self._run_cmd()
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            run = payments.create_run(self.org, date(2026, 8, 1), date(2026, 8, 1), by_email='maker@x.com')
        by_app = {it.application_id: it.amount for it in run.items.all()}
        payable = [s for s in self.specs if s['pathway'] != 'pismp']   # PISMP not paid until September
        self.assertEqual(len(by_app), len(payable))   # 27 (the 3 PISMP excluded)
        for s in payable:
            expected = {'overpay': D('100'), 'advance': D('0')}.get(s['kind'], D('200'))
            self.assertEqual(by_app[s['app'].id], expected, f"{s['kind']} app {s['app'].id}")
        # every PISMP student is absent from the August run
        for s in self.specs:
            if s['pathway'] == 'pismp':
                self.assertNotIn(s['app'].id, by_app)
