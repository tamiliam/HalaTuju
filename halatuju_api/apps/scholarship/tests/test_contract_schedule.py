"""Contract module — the seeded schedule reproduces today's payment behaviour,
and the schedule readers (schedule_row_for / is_paid_month / summaries).

The acceptance guard for money: the BrightPath v1 draft must reproduce today's
constants (RM200; start months 7/7/7/8/8/9; STPM 15 paid months with Dec+Jun
gaps; continuing 5; default 10) and the totals must cross-check award.py.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship import award, contracts
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

from apps.scholarship.tests.contract_helpers import seed_draft


def _cohort(year=2026):
    return ScholarshipCohort.objects.create(code='ct', name='B40', year=year)


def _app(cohort, *, pathway, suffix, reporting=None):
    p = StudentProfile.objects.create(supabase_user_id=f'cs-{suffix}', grades={'bm': 'A'}, exam_type='spm')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=p, status='awarded', chosen_pathway=pathway)
    if reporting is not None:
        app.reporting_date = reporting
        app.save(update_fields=['reporting_date'])
    return app


class TestSeededScheduleReproducesConstants(TestCase):
    def setUp(self):
        self.tmpl = seed_draft()
        self.rows = {(r.pathway, r.variant): r for r in self.tmpl.schedule_rows.all()}

    def test_all_expected_rows_present(self):
        for key in [('stpm', ''), ('stpm', 'continuing'), ('matric', ''), ('asasi', ''),
                    ('poly', ''), ('university', ''), ('pismp', ''), ('default', '')]:
            self.assertIn(key, self.rows)

    def test_monthly_rate_is_200_everywhere(self):
        for row in self.rows.values():
            self.assertEqual(row.monthly_amount, Decimal('200.00'))

    def test_start_months_match_payments_module(self):
        self.assertEqual(self.rows[('stpm', '')].start_month, 7)
        self.assertEqual(self.rows[('matric', '')].start_month, 7)
        self.assertEqual(self.rows[('asasi', '')].start_month, 7)
        self.assertEqual(self.rows[('poly', '')].start_month, 8)
        self.assertEqual(self.rows[('university', '')].start_month, 8)
        self.assertEqual(self.rows[('pismp', '')].start_month, 9)
        self.assertEqual(self.rows[('default', '')].start_month, 7)

    def test_stpm_fresh_15_paid_with_dec_jun_gaps(self):
        row = self.rows[('stpm', '')]
        self.assertEqual(len(row.paid_offsets), 15)
        # Dec of cohort year (offset 5) and Jun of the second year (offset 11) are gaps.
        self.assertNotIn(5, row.paid_offsets)
        self.assertNotIn(11, row.paid_offsets)
        self.assertEqual(row.total, Decimal('3000'))

    def test_stpm_continuing_5_paid(self):
        row = self.rows[('stpm', 'continuing')]
        self.assertEqual(len(row.paid_offsets), 5)
        self.assertEqual(row.total, Decimal('1000'))

    def test_default_10_paid(self):
        self.assertEqual(len(self.rows[('default', '')].paid_offsets), 10)
        self.assertEqual(self.rows[('default', '')].total, Decimal('2000'))

    def test_totals_cross_check_award(self):
        self.assertEqual(self.rows[('stpm', '')].total, award._STPM_AMOUNT)
        self.assertEqual(self.rows[('stpm', 'continuing')].total, award._STPM_CONTINUING_AMOUNT)
        for pathway in ('matric', 'asasi', 'poly', 'university', 'pismp', 'default'):
            self.assertEqual(self.rows[(pathway, '')].total, award._DEFAULT_AMOUNT)

    def test_every_row_total_is_an_allowed_amount(self):
        for row in self.rows.values():
            self.assertIn(row.total, award.ALLOWED_AMOUNTS)


class TestScheduleRowFor(TestCase):
    def setUp(self):
        self.tmpl = seed_draft()
        self.cohort = _cohort(2026)

    def test_matric_uses_matric_row(self):
        app = _app(self.cohort, pathway='matric', suffix='m')
        row = contracts.schedule_row_for(self.tmpl, app)
        self.assertEqual((row.pathway, row.variant), ('matric', ''))

    def test_stpm_fresh_uses_plain_row(self):
        app = _app(self.cohort, pathway='stpm', suffix='sf', reporting=datetime.date(2026, 6, 1))
        row = contracts.schedule_row_for(self.tmpl, app)
        self.assertEqual((row.pathway, row.variant), ('stpm', ''))

    def test_stpm_continuing_uses_continuing_row(self):
        # reporting year (2025) < cohort year (2026) → continuing.
        app = _app(self.cohort, pathway='stpm', suffix='sc', reporting=datetime.date(2025, 6, 1))
        self.assertTrue(award._stpm_continuing(app))
        row = contracts.schedule_row_for(self.tmpl, app)
        self.assertEqual((row.pathway, row.variant), ('stpm', 'continuing'))

    def test_unknown_pathway_falls_back_to_default(self):
        app = _app(self.cohort, pathway='someweird', suffix='u')
        row = contracts.schedule_row_for(self.tmpl, app)
        self.assertEqual((row.pathway, row.variant), ('default', ''))

    def test_none_template_returns_none(self):
        app = _app(self.cohort, pathway='matric', suffix='n')
        self.assertIsNone(contracts.schedule_row_for(None, app))


class TestIsPaidMonth(TestCase):
    def setUp(self):
        self.tmpl = seed_draft()
        self.rows = {(r.pathway, r.variant): r for r in self.tmpl.schedule_rows.all()}

    def test_stpm_pays_july_of_cohort_year(self):
        row = self.rows[('stpm', '')]
        self.assertTrue(contracts.is_paid_month(row, 2026, 7))

    def test_stpm_skips_december_of_cohort_year(self):
        row = self.rows[('stpm', '')]
        self.assertFalse(contracts.is_paid_month(row, 2026, 12))

    def test_stpm_skips_june_of_second_year(self):
        row = self.rows[('stpm', '')]
        self.assertFalse(contracts.is_paid_month(row, 2026, 6, year=2027))

    def test_stpm_pays_july_of_second_year(self):
        row = self.rows[('stpm', '')]
        self.assertTrue(contracts.is_paid_month(row, 2026, 7, year=2027))

    def test_default_pays_first_ten_months(self):
        row = self.rows[('default', '')]
        for month in (7, 8, 9, 10, 11, 12):
            self.assertTrue(contracts.is_paid_month(row, 2026, month))
        for month in (1, 2, 3, 4):
            self.assertTrue(contracts.is_paid_month(row, 2026, month, year=2027))
        # 11th month (May 2027) is beyond the 10-month schedule.
        self.assertFalse(contracts.is_paid_month(row, 2026, 5, year=2027))

    def test_none_row_is_never_paid(self):
        self.assertFalse(contracts.is_paid_month(None, 2026, 7))


class TestScheduleSummaries(TestCase):
    def setUp(self):
        self.tmpl = seed_draft()
        self.rows = {(r.pathway, r.variant): r for r in self.tmpl.schedule_rows.all()}

    def test_summary_text_names_amount_count_and_total(self):
        text = contracts.schedule_summary_text(self.rows[('stpm', '')])
        self.assertIn('RM200', text)
        self.assertIn('15', text)
        self.assertIn('3000', text)

    def test_schedule_table_has_a_row_per_schedule_row(self):
        table = contracts.schedule_table(self.tmpl, 'en')
        self.assertEqual(len(table), 8)
        stpm = next(r for r in table if r['pathway'] == 'stpm' and r['variant'] == '')
        self.assertEqual(stpm['months'], 15)
        self.assertEqual(stpm['total'], Decimal('3000'))
