"""The no-template payment schedule mirrors contract 10 (owner, 2026-10-29) — `default_schedule.py`.

No contract template was ever activated, so this default is what every live student is paid by.
Pinned here: it matches the seed fixture row for row, a diploma student skips November, an STPM
student skips December, a schedule ends, and an unknown pathway takes the 'default' row.
"""
import json
import os
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.scholarship import default_schedule, payments
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import make_application, make_cohort

_FIXTURE = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'brightpath_contract_v1.json')


def _reasons(app, year, month):
    period = date(year, month, 1)
    return payments.eligibility(app, period, period_month=period)['reasons']


class TestDefaultMirrorsTheSeedFixture(TestCase):
    def test_every_row_matches_the_fixture_schedule(self):
        with open(_FIXTURE, encoding='utf-8') as fh:
            fixture = json.load(fh)['schedule']
        self.assertEqual(len(fixture), 8)        # floor: a fixture that lost its rows proves nothing
        expected = [(r['pathway'], r['variant'], r['start_month'], r['paid_offsets'],
                     Decimal(r['monthly_amount'])) for r in fixture]
        actual = [(r.pathway, r.variant, r.start_month, r.paid_offsets, r.monthly_amount)
                  for r in default_schedule.default_rows()]
        self.assertEqual(actual, expected)


class TestDefaultScheduleGovernsPayments(TestCase):
    def setUp(self):
        self.cohort = make_cohort(year=2026)

    def _app(self, pathway):
        return make_application('awarded', cohort=self.cohort, chosen_pathway=pathway,
                                reporting_date=date(2026, 6, 8))

    def test_a_diploma_student_skips_november_only(self):
        for pathway in ('poly', 'university'):
            app = self._app(pathway)
            self.assertIn('gap_month', _reasons(app, 2026, 11), pathway)
            for year, month in ((2026, 10), (2026, 12), (2027, 6)):
                self.assertNotIn('gap_month', _reasons(app, year, month), (pathway, month))
            self.assertIn('schedule_complete', _reasons(app, 2027, 7), pathway)

    def test_an_stpm_student_skips_december_and_june(self):
        app = self._app('stpm')
        self.assertIn('gap_month', _reasons(app, 2026, 12))
        self.assertIn('gap_month', _reasons(app, 2027, 6))
        self.assertNotIn('gap_month', _reasons(app, 2027, 1))
        self.assertIn('schedule_complete', _reasons(app, 2027, 12))

    def test_a_continuing_stpm_student_is_paid_jul_to_nov_only(self):
        app = make_application('awarded', cohort=self.cohort, chosen_pathway='stpm',
                               reporting_date=date(2025, 6, 10))     # started a year early
        self.assertEqual(payments._schedule_row(app).variant, 'continuing')
        self.assertNotIn('schedule_complete', _reasons(app, 2026, 11))
        self.assertIn('schedule_complete', _reasons(app, 2026, 12))

    def test_a_november_run_leaves_out_diplomas_and_pays_matric(self):
        apps = {p: make_application(
            'awarded', cohort=self.cohort, chosen_pathway=p, reporting_date=date(2026, 6, 8),
            vircle_id=payments.vircle_id_prefix() + str(73000 + i))
            for i, p in enumerate(('matric', 'poly', 'university'))}
        self.assertEqual(ScholarshipApplication.objects.filter(cohort=self.cohort).count(), 3)
        nov = date(2026, 11, 1)
        rows = {r['application'].chosen_pathway: r for r in payments.eligible_rows(
            self.cohort.owning_organisation, nov, period_month=nov, programme=self.cohort.programme)}
        self.assertEqual(set(rows), set(apps))
        self.assertTrue(rows['matric']['eligible'], rows['matric']['reasons'])
        self.assertEqual(payments.default_amount(apps['matric']), Decimal('200.00'))
        for p in ('poly', 'university'):
            self.assertFalse(rows[p]['eligible'])
            self.assertIn('gap_month', rows[p]['reasons'])

    def test_matric_ends_after_april(self):
        app = self._app('matric')
        self.assertEqual(_reasons(app, 2027, 4).count('schedule_complete'), 0)
        self.assertIn('schedule_complete', _reasons(app, 2027, 5))

    def test_an_unknown_pathway_takes_the_default_row(self):
        row = payments._schedule_row(self._app('something_new'))
        self.assertEqual((row.pathway, row.start_month, len(row.paid_offsets), row.total),
                         ('default', 7, 10, Decimal('2000.00')))

    def test_the_start_month_floor_comes_from_the_row(self):
        app = self._app('pismp')
        self.assertFalse(payments._has_started(app, date(2026, 8, 1)))
        self.assertTrue(payments._has_started(app, date(2026, 9, 1)))
