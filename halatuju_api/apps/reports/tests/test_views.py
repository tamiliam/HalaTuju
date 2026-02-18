"""
Tests for report API views.

Covers:
- GET /api/v1/reports/ — list reports
- GET /api/v1/reports/<id>/ — get report detail
- POST /api/v1/reports/generate/ — validation (no real Gemini calls)
- FK bug regression: views must filter by student__supabase_user_id, not student_id
"""
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import StudentProfile
from apps.reports.models import GeneratedReport

TEST_USER_ID = 'test-user-report-456'
OTHER_USER_ID = 'other-user-report-789'


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestReportViews(TestCase):
    """Tests for report list, detail, and generate endpoints."""

    def setUp(self):
        self.client = APIClient()
        # Create test student profile
        self.profile = StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID,
            grades={'bm': 'A', 'eng': 'B+', 'math': 'A-'},
            gender='male',
            nationality='malaysian',
        )
        # Create a report for this user
        self.report = GeneratedReport.objects.create(
            student=self.profile,
            title='Laporan Kaunseling — Cikgu Gopal',
            content='# Report\n\nSalam sejahtera pelajar.',
            summary='Test summary',
            student_profile_snapshot={'grades': {'bm': 'A'}},
            eligible_courses_snapshot=[{'course_id': 'C001'}],
            model_used='gemini-2.5-flash',
            generation_time_ms=1500,
        )
        # Create another user's report (should NOT be visible)
        other_profile = StudentProfile.objects.create(
            supabase_user_id=OTHER_USER_ID,
            grades={'bm': 'B'},
        )
        self.other_report = GeneratedReport.objects.create(
            student=other_profile,
            title='Other Report',
            content='Other content',
            summary='Other summary',
            student_profile_snapshot={},
            eligible_courses_snapshot=[],
            model_used='gemini-2.0-flash',
        )
        # Patch JWT decode
        self._patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.decode',
            return_value={
                'sub': TEST_USER_ID,
                'aud': 'authenticated',
                'role': 'authenticated',
            },
        )
        self._patcher.start()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')

    def tearDown(self):
        self._patcher.stop()

    def test_list_reports_returns_own_reports_only(self):
        """GET /api/v1/reports/ returns only the authenticated user's reports."""
        response = self.client.get('/api/v1/reports/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['reports'][0]['report_id'], self.report.id)

    def test_get_report_detail_returns_own_report(self):
        """GET /api/v1/reports/<id>/ returns the report when it belongs to the user."""
        response = self.client.get(f'/api/v1/reports/{self.report.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['report_id'], self.report.id)
        self.assertIn('Salam sejahtera', data['markdown'])

    def test_get_report_detail_404_for_other_users_report(self):
        """GET /api/v1/reports/<id>/ returns 404 for another user's report."""
        response = self.client.get(f'/api/v1/reports/{self.other_report.id}/')
        self.assertEqual(response.status_code, 404)

    def test_generate_report_requires_eligible_courses(self):
        """POST /api/v1/reports/generate/ returns 400 without eligible_courses."""
        response = self.client.post(
            '/api/v1/reports/generate/',
            {'insights': {}},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('eligible_courses', response.json()['error'])
