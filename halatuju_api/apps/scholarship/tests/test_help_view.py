"""Tests for the student document-help endpoint (Task 2).

GET /api/v1/scholarship/documents/<pk>/help/ — own-doc scoped, rate-capped, graceful.
The Gemini prose seam is mocked everywhere — no billable calls in CI.
"""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'help-user-a'
USER_B = 'help-user-b'
SEAM = 'apps.scholarship.profile_engine._call_gemini_text'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDocumentHelpView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile_a = StudentProfile.objects.create(
            supabase_user_id=USER_A, nric='030101-14-1234', name='Aisyah binti Rahman')
        cls.profile_b = StudentProfile.objects.create(supabase_user_id=USER_B, nric='040101-14-5678')
        cls.app_a = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile_a, status='shortlisted', locale='en')
        cls.app_b = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile_b, status='shortlisted')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _doc(self, app, **kw):
        kw.setdefault('doc_type', 'salary_slip')
        kw.setdefault('storage_path', f'{app.id}/x/abc')
        return ApplicantDocument.objects.create(application=app, **kw)

    def _url(self, doc):
        return f'/api/v1/scholarship/documents/{doc.id}/help/'

    # ── happy path ──────────────────────────────────────────────────────────
    def test_supporting_doc_mismatch_returns_ai_message(self):
        doc = self._doc(self.app_a, vision_fields={'fields': {}, 'warnings': [],
                                                    'student_verdict': 'name_mismatch', 'error': ''})
        self._auth(USER_A)
        with patch(SEAM, return_value={'markdown': 'No worries, Aisyah! Let me help.',
                                       'model_used': 'gemini-2.5-flash'}) as m:
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['source'], 'ai')
        self.assertIn('No worries', body['message'])
        self.assertEqual(body['verdict'], 'name_mismatch')
        m.assert_called_once()

    def test_ic_nric_mismatch_returns_ai_message(self):
        doc = self._doc(self.app_a, doc_type='ic', vision_nric='999999-99-9999',
                        vision_name='Aisyah binti Rahman', vision_run_at=timezone.now())
        self._auth(USER_A)
        with patch(SEAM, return_value={'markdown': 'Hi Aisyah, quick fix here.',
                                       'model_used': 'gemini-2.5-flash'}):
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['verdict'], 'nric_mismatch')
        self.assertEqual(resp.json()['source'], 'ai')

    # ── nothing to help with ─────────────────────────────────────────────────
    def test_good_supporting_verdict_returns_none_no_call(self):
        doc = self._doc(self.app_a, vision_fields={'student_verdict': 'ok'})
        self._auth(USER_A)
        with patch(SEAM) as m:
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['source'], 'none')
        m.assert_not_called()

    def test_unchecked_doc_returns_none_no_call(self):
        doc = self._doc(self.app_a, doc_type='results_slip')  # vision never ran
        self._auth(USER_A)
        with patch(SEAM) as m:
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.json()['source'], 'none')
        m.assert_not_called()

    # ── scoping + auth ───────────────────────────────────────────────────────
    def test_cross_user_cannot_get_help_404(self):
        doc = self._doc(self.app_a, vision_fields={'student_verdict': 'name_mismatch'})
        self._auth(USER_B)
        with patch(SEAM) as m:
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 404)
        m.assert_not_called()

    def test_unauthenticated_401(self):
        doc = self._doc(self.app_a, vision_fields={'student_verdict': 'name_mismatch'})
        resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 401)

    # ── rate cap → fallback, never a billable call ───────────────────────────
    @override_settings(DOC_HELP_RATE_LIMIT_PER_HOUR=0)
    def test_rate_cap_degrades_to_fallback_without_calling_gemini(self):
        doc = self._doc(self.app_a, vision_fields={'student_verdict': 'wrong_doc'})
        self._auth(USER_A)
        with patch(SEAM) as m:
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['source'], 'fallback')
        self.assertEqual(resp.json()['verdict'], 'wrong_doc')
        m.assert_not_called()

    def test_engine_error_degrades_to_fallback(self):
        doc = self._doc(self.app_a, vision_fields={'student_verdict': 'unreadable'})
        self._auth(USER_A)
        with patch(SEAM, return_value={'error': 'AI service not configured'}):
            resp = self.client.get(self._url(doc))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['source'], 'fallback')
