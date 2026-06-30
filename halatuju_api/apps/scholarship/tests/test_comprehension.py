"""Test the post-award comprehension-quiz pass endpoint (defensibility stamp)."""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/scholarship/award/comprehension/'


def _tok(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'}, SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=SECRET)
class TestComprehensionPass(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _make(self, uid, status='awarded'):
        p = StudentProfile.objects.create(supabase_user_id=uid, name='X A/P Y', nric='080214-08-1234',
            preferred_state='Perak', household_income=1500, household_size=4)
        return ScholarshipApplication.objects.create(cohort=self.cohort, profile=p, status=status,
            profile_completed_at=timezone.now())

    def _client(self, uid):
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f'Bearer {_tok(uid)}'); return c

    def test_awarded_stamps_passed_at_idempotently(self):
        app = self._make('cq1')
        r = self._client('cq1').post(URL, {}, format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertIsNotNone(app.comprehension_passed_at)
        first = app.comprehension_passed_at
        self._client('cq1').post(URL, {}, format='json')   # idempotent — no overwrite
        app.refresh_from_db()
        self.assertEqual(app.comprehension_passed_at, first)

    def test_not_awarded_is_refused(self):
        self._make('cq2', status='recommended')
        r = self._client('cq2').post(URL, {}, format='json')
        self.assertEqual(r.status_code, 403)
