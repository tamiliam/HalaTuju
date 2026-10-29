"""Student maintenance Sprint 4b — WHEN a funded student's result is due, and the "not submitted"
standing (`results_expectations.py`; the term model is in decisions.md, 2026-10-29, S4b).

Pinned from the harm:
  * NO BACK-DATED DEBT — a student funded two years before the feature starts with the term she is
    in, never with four terms already "overdue" on day one;
  * a term row is made once (the daily job is idempotent) and catches up after a quiet spell;
  * only an ACCEPTED result, submitted on or after a term began, meets that term; un-accepting it
    reopens the term;
  * "not submitted" is strictly past the due date AND the organisation's grace, and yields to a
    result waiting for the officer;
  * the organisation's settings move future terms; a stored due date is never moved.
"""
import datetime
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import OrganisationConfiguration
from apps.scholarship import results_expectations as rx
from apps.scholarship import results_review, standing
from apps.scholarship.models import ResultsExpectation, SemesterResult, StudentActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, record_result,
)

API = '/api/v1/admin/scholarship/scholars/'


def _at(y, m, d):
    return timezone.make_aware(datetime.datetime(y, m, d, 12, 0))


def _funded(on, cohort=None):
    return make_application('maintenance', cohort=cohort, active_at=_at(*on))


def _accept(app, cgpa='3.20'):
    return results_review.review(record_result(app, semester='S', cgpa=cgpa), decision='accepted')


class TestTheTermModel(TestCase):
    def test_terms_run_from_funding_six_months_each_due_45_days_after(self):
        app = _funded((2026, 1, 15))
        rx.ensure_expectations(app, today=datetime.date(2026, 3, 1))
        row = ResultsExpectation.objects.get(application=app)
        self.assertEqual((row.term_index, row.term_ends_on, row.due_on),
                         (1, datetime.date(2026, 7, 15), datetime.date(2026, 8, 29)))

    def test_no_back_dated_debt_and_a_catch_up_after_a_quiet_spell(self):
        app = _funded((2024, 1, 15))                     # funded long before the feature
        rx.ensure_expectations(app, today=datetime.date(2026, 3, 1))
        self.assertEqual(list(ResultsExpectation.objects.filter(application=app)
                              .values_list('term_index', flat=True)), [5])   # the term she is IN
        self.assertEqual(rx.ensure_expectations(app, today=datetime.date(2026, 3, 1)), 0)  # idempotent
        rx.ensure_expectations(app, today=datetime.date(2027, 2, 1))       # a year with no run
        self.assertEqual(list(ResultsExpectation.objects.filter(application=app)
                              .values_list('term_index', flat=True)), [5, 6, 7])

    def test_the_organisation_settings_move_future_terms_only(self):
        app = _funded((2026, 1, 15))
        rx.ensure_expectations(app, today=datetime.date(2026, 3, 1))
        OrganisationConfiguration.objects.create(
            organisation=app.owning_organisation,
            values={'results_terms_per_year': 3, 'results_due_days_after_term': 30})
        app.owning_organisation.refresh_from_db()
        rx.ensure_expectations(app, today=datetime.date(2026, 9, 1))
        first, second = ResultsExpectation.objects.filter(application=app).order_by('term_index')
        self.assertEqual(first.due_on, datetime.date(2026, 8, 29))          # promised: unmoved
        # Review H1: the next term CHAINS from the last one's end (no overlap), at the new length.
        self.assertEqual((second.term_starts_on, second.term_ends_on, second.due_on),
                         (first.term_ends_on, datetime.date(2026, 11, 15), datetime.date(2026, 12, 15)))

    def test_a_student_not_in_maintenance_has_no_terms(self):
        app = make_application('awarded')                                  # no live wallet
        self.assertEqual(rx.ensure_expectations(app), 0)
        self.assertFalse(ResultsExpectation.objects.exists())


class TestMeetingATerm(TestCase):
    def setUp(self):
        self.app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(self.app)
        self.term = ResultsExpectation.objects.get(application=self.app)

    def test_only_an_accepted_result_meets_the_term(self):
        row = record_result(self.app, semester='S1', cgpa='3.10')
        self.term.refresh_from_db()
        self.assertIsNone(self.term.satisfied_by_id)                      # pending meets nothing
        results_review.review(row, decision='accepted')
        self.term.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual((self.term.satisfied_by_id, row.term_index), (row.id, self.term.term_index))
        self.assertIsNone(rx.next_due(self.app))

    def test_un_accepting_it_reopens_the_term(self):
        row = _accept(self.app)
        results_review.review(row, decision='queried', note='This slip is for another semester.')
        self.term.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual((self.term.satisfied_by_id, row.term_index), (None, None))
        self.assertEqual(rx.next_due(self.app), self.term.due_on)

    def test_a_result_from_before_the_term_began_does_not_meet_it(self):
        old = _accept(self.app)
        SemesterResult.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=60), term_index=None)
        ResultsExpectation.objects.filter(pk=self.term.pk).update(satisfied_by=None)
        self.assertEqual(rx.reconcile(self.app), 0)


class TestNotSubmitted(TestCase):
    def setUp(self):
        self.app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(self.app)
        self.term = ResultsExpectation.objects.get(application=self.app)

    def _due(self, days_ago):
        ResultsExpectation.objects.filter(pk=self.term.pk).update(
            due_on=timezone.localdate() - timedelta(days=days_ago))

    def test_strictly_past_due_and_grace(self):
        self._due(14)                                                    # grace is 14: not yet
        self.assertNotEqual(standing.standing_of(self.app), 'not_submitted')
        self._due(15)
        self.assertEqual(standing.standing_of(self.app), 'not_submitted')

    def test_a_result_waiting_for_the_officer_is_not_her_lateness(self):
        self._due(30)
        record_result(self.app, semester='S1', cgpa='3.10')
        self.assertEqual(standing.standing_of(self.app), 'awaiting_review')

    def test_it_wins_over_a_good_cgpa(self):
        _accept(self.app, '3.80')
        ResultsExpectation.objects.create(application=self.app, term_index=9,
                                          term_starts_on=timezone.localdate() - timedelta(days=270),
                                          term_ends_on=timezone.localdate() - timedelta(days=90),
                                          due_on=timezone.localdate() - timedelta(days=45))
        self.assertEqual(standing.standing_of(self.app), 'not_submitted')


class TestTheDailyJob(TestCase):
    def test_it_is_idempotent_and_covers_every_funded_student(self):
        a = make_application('maintenance', active_at=timezone.now() - timedelta(days=10))
        b = make_application('awarded', vircle_activated_at=timezone.now() - timedelta(days=10))
        make_application('awarded')                                        # not in maintenance
        out = StringIO()
        call_command('flag_results_overdue', stdout=out)
        self.assertIn('results terms made: 2', out.getvalue())
        call_command('flag_results_overdue', stdout=StringIO())
        self.assertEqual(sorted(ResultsExpectation.objects.values_list('application_id', flat=True)),
                         sorted([a.id, b.id]))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheScreens(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        self.org_admin = make_admin('org_admin', owning_org=self.cohort.owning_organisation)
        self.late = make_application('maintenance', cohort=self.cohort,
                                     active_at=timezone.now() - timedelta(days=30))
        self.fine = make_application('maintenance', cohort=self.cohort,
                                     active_at=timezone.now() - timedelta(days=30))
        rx.ensure_all()
        ResultsExpectation.objects.filter(application=self.late).update(
            due_on=timezone.localdate() - timedelta(days=20))

    def test_the_list_filter_tile_column_and_standing(self):
        body = authed_client(self.org_admin).get(API).json()
        by_id = {r['id']: r for r in body['results']}
        self.assertEqual(by_id[self.late.id]['standing'], 'not_submitted')
        self.assertEqual(by_id[self.late.id]['next_due'], str(timezone.localdate() - timedelta(days=20)))
        self.assertNotEqual(by_id[self.fine.id]['standing'], 'not_submitted')
        self.assertEqual(body['summary']['results_overdue'], 1)
        rows = authed_client(self.org_admin).get(API, {'standing': 'results_overdue'}).json()['results']
        self.assertEqual([r['id'] for r in rows], [self.late.id])

    def test_an_organisation_grace_moves_the_filter_with_no_deploy(self):
        OrganisationConfiguration.objects.create(organisation=self.cohort.owning_organisation,
                                                 values={'results_overdue_grace_days': 30})
        rows = authed_client(self.org_admin).get(API, {'standing': 'results_overdue'}).json()['results']
        self.assertEqual(rows, [])

    def test_the_file_and_her_hub_show_the_next_due_date(self):
        f = authed_client(self.org_admin).get(f'{API}{self.fine.id}/').json()
        self.assertEqual(f['next_due'], str(rx.next_due(self.fine)))
        hub = authed_client(self.fine.profile.supabase_user_id).get('/api/v1/scholarship/bursary/summary/').json()
        self.assertEqual(hub['next_result_due'], str(rx.next_due(self.fine)))


# ── S4b adversarial review (2026-10-29): one regression test per finding ─────────────────────────

def _cfg(app, **values):
    OrganisationConfiguration.objects.update_or_create(organisation=app.owning_organisation,
                                                       defaults={'values': values})
    app.owning_organisation.refresh_from_db()


def _rows(app):
    return list(ResultsExpectation.objects.filter(application=app).order_by('term_index'))


def _contiguous(rows):
    return all(b.term_starts_on == a.term_ends_on for a, b in zip(rows, rows[1:]))


class TestReviewH1TermsChain(TestCase):
    def test_two_to_four_terms_a_year_chains_with_no_overlap_and_nothing_past_due(self):
        app = _funded((2026, 1, 15))
        rx.ensure_expectations(app, today=datetime.date(2026, 3, 1))
        _cfg(app, results_terms_per_year=4)
        self.assertEqual(rx.ensure_expectations(app, today=datetime.date(2026, 7, 1)), 0)   # term 1 still running
        rx.ensure_expectations(app, today=datetime.date(2026, 7, 20))
        rows = _rows(app)
        self.assertTrue(_contiguous(rows))
        self.assertEqual((rows[1].term_starts_on, rows[1].term_ends_on),
                         (datetime.date(2026, 7, 15), datetime.date(2026, 10, 15)))
        self.assertTrue(all(r.due_on >= datetime.date(2026, 7, 20) for r in rows))

    def test_four_to_one_term_a_year(self):
        app = _funded((2026, 1, 15))
        _cfg(app, results_terms_per_year=4)
        rx.ensure_expectations(app, today=datetime.date(2026, 2, 1))
        _cfg(app, results_terms_per_year=1)
        rx.ensure_expectations(app, today=datetime.date(2026, 4, 20))
        rows = _rows(app)
        self.assertTrue(_contiguous(rows))
        self.assertEqual([(r.term_starts_on, r.term_ends_on) for r in rows],
                         [(datetime.date(2026, 1, 15), datetime.date(2026, 4, 15)),
                          (datetime.date(2026, 4, 15), datetime.date(2027, 4, 15))])

    def test_a_later_funding_stamp_change_cannot_back_date_a_term(self):
        app = _funded((2026, 1, 15))
        rx.ensure_expectations(app, today=datetime.date(2026, 3, 1))
        type(app).objects.filter(pk=app.pk).update(active_at=_at(2023, 1, 1))
        app.refresh_from_db()
        rx.ensure_expectations(app, today=datetime.date(2026, 3, 1))
        self.assertEqual([r.term_index for r in _rows(app)], [1])


class TestReviewM2FinishedAndClosed(TestCase):
    def _late(self, app):
        ResultsExpectation.objects.filter(application=app).update(
            due_on=timezone.localdate() - timedelta(days=40))

    def test_a_graduate_gets_no_more_terms_and_is_never_not_submitted(self):
        app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(app)
        ResultsExpectation.objects.create(application=app, term_index=2,
                                          term_starts_on=timezone.localdate() - timedelta(days=200),
                                          term_ends_on=timezone.localdate() - timedelta(days=100),
                                          due_on=timezone.localdate() - timedelta(days=60))
        results_review.review(record_result(app, semester='Final', cgpa='3.4', graduated=True),
                              decision='accepted')
        self.assertEqual(rx.ensure_expectations(app, today=timezone.localdate() + timedelta(days=400)), 0)
        self.assertEqual(standing.standing_of(app), 'performing')
        self.assertFalse(rx.late(app))

    def test_ready_to_close_gets_no_more_terms_and_no_flag(self):
        app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(app)
        self._late(app)
        type(app).objects.filter(pk=app.pk).update(maintenance_substate='ready_to_close')
        app.refresh_from_db()
        self.assertEqual(rx.ensure_expectations(app, today=timezone.localdate() + timedelta(days=400)), 0)
        self.assertEqual(rx.flag_overdue(), 0)

    def test_a_closed_file_is_never_late_and_has_no_next_due(self):
        app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(app)
        self._late(app)
        type(app).objects.filter(pk=app.pk).update(status='closed', closure_reason='completed')
        app.refresh_from_db()
        self.assertEqual((rx.next_due(app), rx.late(app)), (None, False))
        self.assertNotEqual(standing.standing_of(app), 'not_submitted')


class TestReviewM3PendingThisTerm(TestCase):
    def setUp(self):
        self.app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(self.app)
        self.term = ResultsExpectation.objects.get(application=self.app)
        ResultsExpectation.objects.filter(pk=self.term.pk).update(
            due_on=timezone.localdate() - timedelta(days=40))

    def test_a_result_waiting_from_before_the_term_began_does_not_excuse_her(self):
        old = record_result(self.app, semester='Old', cgpa='3.0')
        SemesterResult.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=90))
        self.assertTrue(rx.late(self.app))
        self.assertEqual(standing.standing_of(self.app), 'not_submitted')

    def test_one_sent_this_term_does(self):
        record_result(self.app, semester='S1', cgpa='3.0')
        self.assertFalse(rx.late(self.app))


class TestReviewM5SameSemester(TestCase):
    def test_a_second_accepted_result_for_a_counted_semester_does_not_use_up_a_term(self):
        app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(app)
        ResultsExpectation.objects.create(application=app, term_index=2,
                                          term_starts_on=timezone.localdate() - timedelta(days=30),
                                          term_ends_on=timezone.localdate() + timedelta(days=200),
                                          due_on=timezone.localdate() + timedelta(days=245))
        _accept(app, '3.10')                                     # semester 'S'
        results_review.review(record_result(app, semester=' s ', cgpa='3.20'), decision='accepted')
        self.assertEqual(ResultsExpectation.objects.filter(application=app, satisfied_by__isnull=True).count(), 1)


@override_settings(MAINTENANCE_REMINDERS_ENABLED=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TestReviewJobs(TestCase):
    def setUp(self):
        self.app = make_application('maintenance', active_at=timezone.now() - timedelta(days=30),
                                    notify_email='s@example.test')
        rx.ensure_expectations(self.app)
        self.first = ResultsExpectation.objects.get(application=self.app)

    def _second(self):
        return ResultsExpectation.objects.create(
            application=self.app, term_index=self.first.term_index + 1,
            term_starts_on=self.first.term_ends_on, term_ends_on=self.first.term_ends_on + timedelta(days=180),
            due_on=self.first.due_on + timedelta(days=1))

    def test_l6_two_late_terms_make_one_line_and_one_email_and_stamp_both(self):
        self._second()
        ResultsExpectation.objects.filter(application=self.app).update(
            due_on=timezone.localdate() - timedelta(days=40))
        self.assertEqual(rx.flag_overdue(), 1)
        self.assertEqual(StudentActivity.objects.filter(application=self.app, event='results_overdue').count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        rows = ResultsExpectation.objects.filter(application=self.app)
        self.assertFalse(rows.filter(overdue_emailed_at__isnull=True).exists())
        self.assertFalse(rows.filter(overdue_flagged_at__isnull=True).exists())

    def test_l7_a_failed_send_gives_the_claim_back_and_one_reminder_per_student(self):
        self._second()
        ResultsExpectation.objects.filter(application=self.app).update(
            due_on=timezone.localdate() + timedelta(days=5))
        with mock.patch('apps.scholarship.student_comms.send_student_email', return_value=False):
            self.assertEqual(rx.send_due_reminders(), 0)
        self.assertFalse(ResultsExpectation.objects.filter(application=self.app, reminded_at__isnull=False).exists())
        self.assertEqual(rx.send_due_reminders(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_l8_one_failure_does_not_stop_the_run_and_a_failed_overdue_email_is_retried(self):
        other = make_application('maintenance', active_at=timezone.now() - timedelta(days=30),
                                 notify_email='o@example.test')
        rx.ensure_expectations(other)
        ResultsExpectation.objects.update(due_on=timezone.localdate() - timedelta(days=40))
        real = rx.late

        def boom(app, today=None):
            if app.id == self.app.id:
                raise RuntimeError('one bad row')
            return real(app, today)
        with mock.patch.object(rx, 'late', side_effect=boom):
            self.assertEqual(rx.flag_overdue(), 1)               # the other student still flagged
        with mock.patch('apps.scholarship.student_comms.send_student_email', return_value=False):
            rx.flag_overdue()                                    # self.app flagged; her email fails
        row = ResultsExpectation.objects.get(application=self.app)
        self.assertIsNotNone(row.overdue_flagged_at)
        self.assertIsNone(row.overdue_emailed_at)
        before = len(mail.outbox)
        rx.flag_overdue()                                        # retried — and no second line
        self.assertEqual(len(mail.outbox), before + 1)
        self.assertEqual(StudentActivity.objects.filter(application=self.app, event='results_overdue').count(), 1)

    def test_l9_on_hold_no_due_or_overdue_email_but_the_standing_still_moves(self):
        type(self.app).objects.filter(pk=self.app.pk).update(maintenance_substate='on_hold')
        self.app.refresh_from_db()
        ResultsExpectation.objects.filter(pk=self.first.pk).update(due_on=timezone.localdate() + timedelta(days=5))
        self.assertEqual(rx.send_due_reminders(), 0)
        ResultsExpectation.objects.filter(pk=self.first.pk).update(due_on=timezone.localdate() - timedelta(days=40))
        rx.flag_overdue()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(standing.standing_of(self.app), 'not_submitted')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReviewM4ListAgrees(TestCase):
    def test_tile_filter_standing_and_hub_agree_when_she_sent_one_this_term(self):
        cohort = make_cohort()
        admin = make_admin('org_admin', owning_org=cohort.owning_organisation)
        app = make_application('maintenance', cohort=cohort, active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(app)
        ResultsExpectation.objects.filter(application=app).update(
            due_on=timezone.localdate() - timedelta(days=40))
        record_result(app, semester='S1', cgpa='3.0')            # waiting: not her lateness
        body = authed_client(admin).get(API).json()
        self.assertEqual(body['summary']['results_overdue'], 0)
        self.assertNotEqual(body['results'][0]['standing'], 'not_submitted')
        self.assertEqual(authed_client(admin).get(API, {'standing': 'results_overdue'}).json()['results'], [])
        hub = authed_client(app.profile.supabase_user_id).get('/api/v1/scholarship/bursary/summary/').json()
        self.assertFalse(hub['next_result_overdue'])

    def test_a_closed_file_in_the_closed_list_has_no_next_due(self):
        cohort = make_cohort()
        admin = make_admin('org_admin', owning_org=cohort.owning_organisation)
        app = make_application('maintenance', cohort=cohort, active_at=timezone.now() - timedelta(days=30))
        rx.ensure_expectations(app)
        type(app).objects.filter(pk=app.pk).update(status='closed', closure_reason='completed')
        rows = authed_client(admin).get(API, {'closed': '1'}).json()['results']
        self.assertEqual([(r['id'], r['next_due']) for r in rows], [(app.id, None)])
        self.assertNotEqual(rows[0]['standing'], 'not_submitted')
