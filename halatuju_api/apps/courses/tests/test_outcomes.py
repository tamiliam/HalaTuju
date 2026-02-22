"""
Tests for admission outcome CRUD endpoints.

Covers:
- Create outcome (201), duplicate (409)
- List own outcomes only
- Update outcome status
- Delete outcome
- Auth enforcement (403 without token)
- Cross-user isolation (can't see/edit other user's outcomes)
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import (
    Course, Institution, StudentProfile, AdmissionOutcome,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'user-a-123'
USER_B = 'user-b-456'


def _make_token(user_id, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': user_id, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestOutcomeEndpoints(TestCase):
    """CRUD tests for /api/v1/outcomes/."""

    @classmethod
    def setUpTestData(cls):
        cls.course = Course.objects.create(
            course_id='TEST001',
            course='Test Course',
            level='Diploma',
            department='Engineering',
            field='Mechanical',
            frontend_label='Engineering',
        )
        cls.course2 = Course.objects.create(
            course_id='TEST002',
            course='Test Course 2',
            level='Sijil',
            department='IT',
            field='Software',
            frontend_label='IT',
        )
        cls.institution = Institution.objects.create(
            institution_id='INST001',
            institution_name='Test Polytechnic',
            type='Politeknik',
            state='Selangor',
        )
        cls.profile_a = StudentProfile.objects.create(
            supabase_user_id=USER_A,
        )
        cls.profile_b = StudentProfile.objects.create(
            supabase_user_id=USER_B,
        )

    def setUp(self):
        self.client = APIClient()
        self.token_a = _make_token(USER_A)
        self.token_b = _make_token(USER_B)

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # --- CREATE ---

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_create_outcome(self):
        self._auth(self.token_a)
        resp = self.client.post('/api/v1/outcomes/', {
            'course_id': 'TEST001',
            'status': 'applied',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.json())

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_create_duplicate_returns_409(self):
        AdmissionOutcome.objects.create(
            student=self.profile_a,
            course=self.course,
            status='applied',
        )
        self._auth(self.token_a)
        resp = self.client.post('/api/v1/outcomes/', {
            'course_id': 'TEST001',
            'status': 'applied',
        }, format='json')
        self.assertEqual(resp.status_code, 409)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_create_missing_course_id(self):
        self._auth(self.token_a)
        resp = self.client.post('/api/v1/outcomes/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_create_with_institution(self):
        self._auth(self.token_a)
        resp = self.client.post('/api/v1/outcomes/', {
            'course_id': 'TEST002',
            'institution_id': 'INST001',
            'status': 'offered',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        outcome = AdmissionOutcome.objects.get(id=resp.json()['id'])
        self.assertEqual(outcome.institution_id, 'INST001')
        self.assertEqual(outcome.status, 'offered')

    # --- LIST ---

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_list_own_outcomes_only(self):
        AdmissionOutcome.objects.create(
            student=self.profile_a, course=self.course, status='applied',
        )
        AdmissionOutcome.objects.create(
            student=self.profile_b, course=self.course, status='offered',
        )
        self._auth(self.token_a)
        resp = self.client.get('/api/v1/outcomes/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['outcomes'][0]['status'], 'applied')

    # --- UPDATE ---

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_update_outcome_status(self):
        outcome = AdmissionOutcome.objects.create(
            student=self.profile_a, course=self.course, status='applied',
        )
        self._auth(self.token_a)
        resp = self.client.put(
            f'/api/v1/outcomes/{outcome.id}/',
            {'status': 'offered', 'outcome_at': '2026-05-01'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        outcome.refresh_from_db()
        self.assertEqual(outcome.status, 'offered')

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_update_other_user_returns_404(self):
        outcome = AdmissionOutcome.objects.create(
            student=self.profile_b, course=self.course, status='applied',
        )
        self._auth(self.token_a)
        resp = self.client.put(
            f'/api/v1/outcomes/{outcome.id}/',
            {'status': 'offered'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    # --- DELETE ---

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_delete_outcome(self):
        outcome = AdmissionOutcome.objects.create(
            student=self.profile_a, course=self.course, status='applied',
        )
        self._auth(self.token_a)
        resp = self.client.delete(f'/api/v1/outcomes/{outcome.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            AdmissionOutcome.objects.filter(id=outcome.id).exists()
        )

    # --- AUTH ---

    def test_outcomes_reject_anonymous(self):
        resp = self.client.get('/api/v1/outcomes/')
        self.assertEqual(resp.status_code, 403)

    def test_outcomes_post_reject_anonymous(self):
        resp = self.client.post('/api/v1/outcomes/', {
            'course_id': 'TEST001',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
