"""Tests for the seed_b40_2026_cohort management command (S12b deploy prep)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.scholarship.models import ScholarshipCohort


class TestSeedB40Cohort(TestCase):
    def test_creates_cohort_with_settled_thresholds(self):
        out = StringIO()
        call_command('seed_b40_2026_cohort', stdout=out)
        c = ScholarshipCohort.objects.get(code='b40-2026')
        self.assertEqual(c.year, 2026)
        self.assertTrue(c.is_active)
        self.assertTrue(c.is_open)
        self.assertEqual(c.income_ceiling, 5860)
        # Settled thresholds (model defaults) — verify they're what the engine will use.
        self.assertEqual(c.min_spm_a_count, 4)
        self.assertEqual(c.min_spm_bplus_count, 5)
        self.assertEqual(c.min_stpm_pngk, 2.9)
        self.assertEqual(c.per_capita_ceiling, 1584)
        self.assertEqual(c.success_delay_hours, 48)
        self.assertEqual(c.decline_delay_hours, 48)
        self.assertIn('Created', out.getvalue())

    def test_idempotent_second_run_is_noop(self):
        call_command('seed_b40_2026_cohort')
        out = StringIO()
        call_command('seed_b40_2026_cohort', stdout=out)
        self.assertEqual(ScholarshipCohort.objects.filter(code='b40-2026').count(), 1)
        self.assertIn('already exists', out.getvalue())

    def test_closed_flag_creates_not_open(self):
        call_command('seed_b40_2026_cohort', '--closed')
        c = ScholarshipCohort.objects.get(code='b40-2026')
        self.assertTrue(c.is_active)
        self.assertFalse(c.is_open)
