"""Model + helper tests for the B40 Assistance Programme."""
from django.db import IntegrityError
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import count_spm_a_grades


class TestScholarshipModels(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(
            code='b40-2026', name='B40 Assistance Programme 2026', year=2026,
        )
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='u1', nric='080101-14-1234',
        )

    def test_cohort_str_and_defaults(self):
        self.assertIn('b40-2026', str(self.cohort))
        # Criteria Sprint 3b (TD-772): no silent bars - a cohort created without them has none.
        self.assertIsNone(self.cohort.min_spm_a_count)
        self.assertIsNone(self.cohort.min_spm_bplus_count)
        self.assertIsNone(self.cohort.min_stpm_pngk)
        self.assertIsNone(self.cohort.per_capita_ceiling)
        self.assertEqual(self.cohort.success_delay_hours, 48)
        self.assertEqual(self.cohort.decline_delay_hours, 48)
        self.assertTrue(self.cohort.is_open)

    def test_application_defaults(self):
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile,
        )
        self.assertEqual(app.status, 'submitted')
        self.assertEqual(app.bucket, '')
        self.assertTrue(app.intends_tertiary_2026)
        self.assertEqual(app.form_data, {})
        self.assertEqual(app.intake_snapshot, {})
        self.assertIsNone(app.acknowledged_at)
        self.assertIn(str(app.pk), str(app))

    def test_unique_application_per_cohort(self):
        ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile)
        with self.assertRaises(IntegrityError):
            ScholarshipApplication.objects.create(cohort=self.cohort, profile=self.profile)

    def test_count_spm_a_grades(self):
        self.assertEqual(
            count_spm_a_grades({'a': 'A+', 'b': 'A', 'c': 'A-', 'd': 'B+', 'e': 'C'}),
            3,
        )
        self.assertEqual(count_spm_a_grades({}), 0)
        self.assertEqual(count_spm_a_grades(None), 0)
        # Case-insensitive + whitespace tolerant
        self.assertEqual(count_spm_a_grades({'a': 'a+', 'b': ' A '}), 2)


class TestTheFlagshipSeedStatesItsBars(TestCase):
    """Sprint 3b review: the model has no silent bars any more, so the flagship's 2026-05-24 bars
    (4 A- / 5 B+ / PNGK 2.9 / RM5,860 / RM1,584) must come from the seed itself, and the tree it
    stores must read back the same values the gate reads."""

    def test_the_seed_gives_the_settled_bars_and_a_tree_that_says_them(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.scholarship import criteria, criteria_read
        call_command('seed_b40_2026_cohort', stdout=StringIO())
        c = ScholarshipCohort.objects.get(code='b40-2026')
        bars = ('min_spm_a_count', 'min_spm_bplus_count', 'min_stpm_pngk', 'income_ceiling',
                'per_capita_ceiling')
        self.assertEqual(tuple(getattr(c, f) for f in bars), (4, 5, 2.9, 5860, 1584))
        self.assertIsNotNone(c.criteria)
        self.assertEqual(criteria.validate_tree(c.criteria), [])
        values = criteria_read.column_values(c)
        self.assertEqual(tuple(values[f] for f in bars), (4, 5, 2.9, 5860, 1584))
