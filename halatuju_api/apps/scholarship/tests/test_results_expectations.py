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

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import OrganisationConfiguration
from apps.scholarship import results_expectations as rx
from apps.scholarship import results_review, standing
from apps.scholarship.models import ResultsExpectation, SemesterResult
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
        self.assertEqual((second.term_ends_on, second.due_on),               # four-month terms now
                         (datetime.date(2026, 9, 15), datetime.date(2026, 10, 15)))

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
