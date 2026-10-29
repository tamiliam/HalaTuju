"""Student maintenance Sprint 1 — ONE predicate for "in maintenance" (owner ruling 2026-10-29).

What it holds:
  * the predicate's truth table, and that the queryset form and the single-record form AGREE on
    every status x wallet x funded-stamp x closure-reason combination (two forms of one rule are
    a drift waiting to happen);
  * an `awarded` student with a live wallet (the 65 live students) can now record a result, be
    given a sub-state, be on hold, and reach the in-programme page; one WITHOUT a wallet cannot;
  * a closed case keeps a file only when it was in maintenance — never a stalled pre-award close
    whose wallet stamp survived an award that fell through (TD-352);
  * the sponsor-visible consequence: an on-hold awarded student now reads `paused`.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship import closure, in_programme, maintenance
from apps.scholarship.in_programme import InProgrammeError
from apps.scholarship.maintenance import MaintenanceError
from apps.scholarship.maintenance_scope import (
    POST_AWARD_ONLY_REASONS, has_file, has_file_q, in_maintenance_q, is_in_maintenance,
)
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.serializers import ApplicationReadSerializer
from apps.scholarship.tests.factories import make_application, make_cohort, record_result

STAGES = ('submitted', 'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected',
          'expired')


class TestPredicateTruthTable(TestCase):
    @classmethod
    def setUpTestData(cls):
        cohort = make_cohort()
        now = timezone.now()
        cls.rows = []
        for stage in STAGES:
            reasons = [r for r, _ in ScholarshipApplication.CLOSURE_REASONS] if stage == 'closed' \
                else [None]
            for wallet in (False, True):
                for funded in (False, True):
                    for reason in reasons:
                        over = {'vircle_activated_at': now if wallet else None,
                                'active_at': now if funded else None}
                        if reason:
                            over['closure_reason'] = reason
                        app = make_application(stage, cohort=cohort, **over)
                        cls.rows.append((stage, wallet, funded, reason, app))

    def test_the_queryset_and_the_record_agree_for_in_maintenance(self):
        by_q = set(ScholarshipApplication.objects.filter(in_maintenance_q())
                   .values_list('id', flat=True))
        by_record = {app.id for *_, app in self.rows if is_in_maintenance(app)}
        self.assertEqual(by_q, by_record)

    def test_the_queryset_and_the_record_agree_for_has_file(self):
        by_q = set(ScholarshipApplication.objects.filter(has_file_q()).values_list('id', flat=True))
        by_record = {app.id for *_, app in self.rows if has_file(app)}
        self.assertEqual(by_q, by_record)

    def test_the_truth_table(self):
        for stage, wallet, funded, reason, app in self.rows:
            want_in = stage in ('active', 'maintenance') or (stage == 'awarded' and wallet)
            want_file = want_in or (stage == 'closed' and (
                funded or (wallet and reason in POST_AWARD_ONLY_REASONS)))
            with self.subTest(stage=stage, wallet=wallet, funded=funded, reason=reason or ''):
                self.assertEqual(is_in_maintenance(app), want_in)
                self.assertEqual(has_file(app), want_file)

    def test_post_award_only_reasons_exclude_every_pre_award_reason(self):
        self.assertEqual(set(POST_AWARD_ONLY_REASONS),
                         set(closure.POST_AWARD_REASONS) - set(closure.PRE_AWARD_REASONS))
        self.assertEqual(set(POST_AWARD_ONLY_REASONS),
                         {'graduated', 'completed', 'lapsed', 'terminated'})

    def test_none_is_not_in_maintenance(self):
        self.assertFalse(is_in_maintenance(None))
        self.assertFalse(has_file(None))


class TestAwardedWithAWalletIsInMaintenance(TestCase):
    """The 65 live students: `awarded`, wallet live, sub-state on_track."""

    def setUp(self):
        self.cohort = make_cohort()
        self.live = make_application('awarded', cohort=self.cohort,
                                     vircle_activated_at=timezone.now())
        self.no_wallet = make_application('awarded', cohort=self.cohort)

    def test_results_open_to_the_predicate_since_s4a_and_start_pending(self):
        """S4a: recording widens to the maintenance predicate now that every result is REVIEWED
        before it counts; without a live wallet she still cannot record one."""
        row = record_result(self.live, semester='Sem 1', cgpa='3.40')
        self.assertEqual(row.review_status, 'pending')
        with self.assertRaises(InProgrammeError) as ctx:
            record_result(self.no_wallet, semester='Sem 1', cgpa='3.40')
        self.assertEqual(ctx.exception.code, 'not_in_programme')

    def test_promotional_consent_follows_the_predicate(self):
        with self.assertRaises(InProgrammeError):
            in_programme.grant_promotional_consent(self.no_wallet)
        self.assertTrue(in_programme.can_record_results(self.live))
        self.assertFalse(in_programme.can_record_results(self.no_wallet))

    def test_is_given_a_substate_and_can_be_on_hold(self):
        maintenance.set_substate(self.live, 'on_hold', by_email='officer@example.test')
        self.live.refresh_from_db()
        self.assertEqual(self.live.maintenance_substate, 'on_hold')
        self.assertTrue(maintenance.is_on_hold(self.live))

    def test_without_a_live_wallet_has_no_substate(self):
        with self.assertRaises(MaintenanceError) as ctx:
            maintenance.set_substate(self.no_wallet, 'on_hold')
        self.assertEqual(ctx.exception.code, 'not_in_maintenance')
        self.assertFalse(maintenance.is_on_hold(self.no_wallet))

    def test_the_sponsor_reads_paused_for_an_on_hold_awarded_student(self):
        """The sponsor-visible consequence of the ruling: `support_status` and the portfolio
        badge read `paused` (they read `maintenance.is_on_hold`). Before, this read None."""
        from apps.scholarship import pool
        maintenance.set_substate(self.live, 'on_hold')
        self.assertEqual(maintenance.sponsor_support_status(self.live), 'paused')
        self.assertEqual(pool.sponsor_portfolio_status(self.live), 'paused')
        maintenance.set_substate(self.live, 'ready_to_close')
        self.assertEqual(maintenance.sponsor_support_status(self.live), 'completing')
        self.assertIsNone(maintenance.sponsor_support_status(self.no_wallet))

    def test_the_sponsor_band_reads_the_predicate_and_only_accepted_results(self):
        """S4a: `derive_progress_state` is on the maintenance predicate (an awarded student with a
        live wallet reads on_track, not None), and a PENDING result never moves it."""
        from apps.scholarship import pool, results_review
        self.assertEqual(pool.derive_progress_state(self.live), 'on_track')
        self.assertIsNone(pool.derive_progress_state(self.no_wallet))
        row = record_result(self.live, semester='Sem 1', cgpa='1.50')
        self.assertEqual(pool.derive_progress_state(self.live), 'on_track')       # pending: no move
        results_review.review(row, decision='accepted')
        self.assertEqual(pool.derive_progress_state(self.live), 'needs_attention')

    def test_ready_to_close_worklist_includes_the_awarded_student(self):
        maintenance.set_substate(self.live, 'ready_to_close')
        self.no_wallet.maintenance_substate = 'ready_to_close'   # a stray value, out of scope
        self.no_wallet.save(update_fields=['maintenance_substate'])
        ids = set(maintenance.ready_to_close_queryset().values_list('id', flat=True))
        self.assertIn(self.live.id, ids)
        self.assertNotIn(self.no_wallet.id, ids)

    def test_a_stored_hold_on_a_payable_status_is_a_hold_without_the_wallet_stamp(self):
        """The MONEY hold is not the file predicate (lead review): a stored hold on a status a run
        pays holds, whatever the wallet stamp says."""
        self.no_wallet.maintenance_substate = 'on_hold'
        self.no_wallet.save(update_fields=['maintenance_substate'])
        self.assertTrue(maintenance.is_on_hold(self.no_wallet))
        self.assertEqual(maintenance.sponsor_support_status(self.no_wallet), 'paused')
        closed = make_application('closed', cohort=self.cohort, maintenance_substate='on_hold')
        self.assertFalse(maintenance.is_on_hold(closed))   # not a payable status

    def test_the_student_payload_serves_the_two_answers(self):
        keys = ('in_maintenance', 'has_file', 'can_record_results', 'support_paused')
        data = ApplicationReadSerializer(self.live).data
        self.assertEqual(tuple(data[k] for k in keys), (True, True, True, False))   # S4a widened
        self.assertNotIn('maintenance_substate', data)
        data = ApplicationReadSerializer(self.no_wallet).data
        self.assertEqual(tuple(data[k] for k in keys), (False, False, False, False))
        maintenance.set_substate(self.live, 'on_hold')
        self.assertTrue(ApplicationReadSerializer(self.live).data['support_paused'])
        active = make_application('active', cohort=self.cohort)
        self.assertTrue(ApplicationReadSerializer(active).data['can_record_results'])


class TestClosedFile(TestCase):
    def setUp(self):
        self.cohort = make_cohort()

    def test_a_funded_close_keeps_its_file_and_its_thank_you(self):
        app = make_application('closed', cohort=self.cohort)          # active_at stamped
        self.assertTrue(has_file(app))
        self.assertFalse(is_in_maintenance(app))
        in_programme.submit_graduation_message(app, raw_text='Thank you for everything.')
        with self.assertRaises(InProgrammeError):
            record_result(app, semester='Sem 9', cgpa='3.00')

    def test_a_stalled_close_after_a_fallen_through_award_has_no_file(self):
        """`revert_to_pool` keeps the wallet stamp; the later pre-award close records `stalled`."""
        app = make_application('closed', cohort=self.cohort, active_at=None,
                               vircle_activated_at=timezone.now(), closure_reason='stalled')
        self.assertFalse(has_file(app))
        with self.assertRaises(InProgrammeError) as ctx:
            in_programme.submit_graduation_message(app, raw_text='Thank you.')
        self.assertEqual(ctx.exception.code, 'not_in_programme')
        self.assertFalse(ApplicationReadSerializer(app).data['has_file'])

    def test_a_graduated_close_from_awarded_keeps_its_file(self):
        app = make_application('closed', cohort=self.cohort, active_at=None,
                               vircle_activated_at=timezone.now(), closure_reason='graduated')
        self.assertTrue(has_file(app))
        in_programme.submit_graduation_message(app, raw_text='Thank you for everything.')
