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
        self.assertEqual(self.cohort.min_spm_a_count, 4)
        self.assertEqual(self.cohort.min_spm_bplus_count, 5)
        self.assertEqual(self.cohort.min_stpm_pngk, 2.9)
        self.assertEqual(self.cohort.per_capita_ceiling, 1584)
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
