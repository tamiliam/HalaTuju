"""Tests for the MyNadi admin API + AI profile drafting (Sprint 6a)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort, SponsorProfile

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'admin-uid'
STUDENT = 'student-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminScholarship(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
            name='Admin', email='admin@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud-prof', nric='030101-14-1234', name='Priya', school='SMK X',
        )
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted', bucket='A',
            spm_a_count=10, household_income=2500, receives_str=True,
            aspirations='Become an auditor', justification='Low income family',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_non_admin_forbidden(self):
        self._auth(STUDENT)
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 403)

    def test_requires_auth(self):
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 401)

    def test_admin_list(self):
        self._auth(ADMIN)
        r = self.client.get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['total_count'], 1)
        self.assertEqual(r.json()['applications'][0]['name'], 'Priya')

    def test_admin_list_filter_bucket(self):
        self._auth(ADMIN)
        r = self.client.get('/api/v1/admin/scholarship/applications/?bucket=B')
        self.assertEqual(r.json()['total_count'], 0)

    def test_admin_detail(self):
        self._auth(ADMIN)
        r = self.client.get(f'/api/v1/admin/scholarship/applications/{self.app.id}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['aspirations'], 'Become an auditor')
        self.assertEqual(body['name'], 'Priya')
        self.assertIn('documents', body)
        self.assertIn('referees', body)
        self.assertIsNone(body['sponsor_profile'])

    @patch('apps.scholarship.views_admin.generate_sponsor_profile',
           return_value={'markdown': '# Priya\nA strong candidate.', 'model_used': 'gemini-2.5-flash'})
    def test_generate_profile(self, _mock):
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/generate-profile/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['status'], 'draft')
        self.assertIn('strong candidate', body['draft_markdown'])
        self.assertEqual(body['model_used'], 'gemini-2.5-flash')

    @patch('apps.scholarship.views_admin.generate_sponsor_profile', return_value={'error': 'AI down'})
    def test_generate_profile_ai_error(self, _mock):
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/generate-profile/')
        self.assertEqual(r.status_code, 503)

    def test_edit_and_publish(self):
        SponsorProfile.objects.create(application=self.app, draft_markdown='draft text')
        self._auth(ADMIN)
        r = self.client.put(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/profile/',
            {'edited_markdown': 'edited text', 'status': 'approved'}, format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['edited_markdown'], 'edited text')
        self.assertEqual(r.json()['status'], 'approved')
        self.assertEqual(r.json()['current_markdown'], 'edited text')
        r2 = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/publish/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'published')

    def test_publish_nothing_400(self):
        SponsorProfile.objects.create(application=self.app)  # empty draft + edited
        self._auth(ADMIN)
        r = self.client.post(f'/api/v1/admin/scholarship/applications/{self.app.id}/publish/')
        self.assertEqual(r.status_code, 400)
