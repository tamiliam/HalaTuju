"""
Tests for authentication enforcement on protected endpoints.

Covers:
- Protected endpoints return 401 without auth token
- Protected endpoints work with valid Supabase JWT
- Public endpoints remain accessible without auth
"""
import jwt
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import StudentProfile

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
TEST_USER_ID = 'test-user-abc-123'


def _make_token(user_id=TEST_USER_ID, secret=TEST_JWT_SECRET):
    """Create a valid JWT token for testing."""
    return jwt.encode(
        {'sub': user_id, 'aud': 'authenticated', 'role': 'authenticated'},
        secret,
        algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestProtectedEndpointsRejectAnonymous(TestCase):
    """Protected endpoints must reject unauthenticated requests."""

    def setUp(self):
        self.client = APIClient()

    def test_saved_courses_get_rejected(self):
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(response.status_code, 401)

    def test_saved_courses_post_rejected(self):
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'FAKE'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_saved_course_delete_rejected(self):
        response = self.client.delete('/api/v1/saved-courses/FAKE/')
        self.assertEqual(response.status_code, 401)

    def test_profile_get_rejected(self):
        response = self.client.get('/api/v1/profile/')
        self.assertEqual(response.status_code, 401)

    def test_profile_put_rejected(self):
        response = self.client.put(
            '/api/v1/profile/',
            {'gender': 'Lelaki'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_profile_sync_rejected(self):
        response = self.client.post(
            '/api/v1/profile/sync/',
            {'name': 'Test'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestProtectedEndpointsAcceptAuth(TestCase):
    """Protected endpoints must accept requests with valid Supabase JWT."""

    def setUp(self):
        self.client = APIClient()
        # Patch both jwt.get_unverified_header (called first to detect algorithm)
        # and jwt.decode (called second to verify token) in the middleware.
        self._header_patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.get_unverified_header',
            return_value={'alg': 'HS256'},
        )
        self._decode_patcher = patch(
            'halatuju.middleware.supabase_auth.jwt.decode',
            return_value={
                'sub': TEST_USER_ID,
                'aud': 'authenticated',
                'role': 'authenticated',
            },
        )
        self._header_patcher.start()
        self._decode_patcher.start()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')

    def tearDown(self):
        self._decode_patcher.stop()
        self._header_patcher.stop()

    def test_saved_courses_get_accepted(self):
        # Profile with NRIC needed to pass NricGateMiddleware
        StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID, nric='010101-01-1234',
        )
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(response.status_code, 200)

    def test_profile_get_accepted(self):
        response = self.client.get('/api/v1/profile/')
        self.assertEqual(response.status_code, 200)

    def test_profile_put_accepted(self):
        # Profile must exist — protected views use .get() not get_or_create
        StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID, nric='010101-01-1234',
        )
        response = self.client.put(
            '/api/v1/profile/',
            {'gender': 'Lelaki'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_profile_sync_creates_profile(self):
        # User must have NRIC to pass NricGateMiddleware (sync not whitelisted)
        StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID, nric='010101-01-1234',
        )
        response = self.client.post(
            '/api/v1/profile/sync/',
            {
                'name': 'Siti Aminah',
                'school': 'SMK Damansara Jaya',
                'grades': {'bm': 'A', 'eng': 'B+'},
                'gender': 'Perempuan',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['created'])  # Profile already exists from NRIC claim
        # Verify data persisted
        get_resp = self.client.get('/api/v1/profile/')
        self.assertEqual(get_resp.data['name'], 'Siti Aminah')
        self.assertEqual(get_resp.data['school'], 'SMK Damansara Jaya')
        self.assertEqual(get_resp.data['grades'], {'bm': 'A', 'eng': 'B+'})

    def test_profile_sync_updates_existing(self):
        # Create profile with NRIC (required by NricGateMiddleware)
        StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID, nric='010101-01-1234',
            name='Original Name', school='Original School',
        )
        # Update with sync
        response = self.client.post(
            '/api/v1/profile/sync/',
            {'name': 'Updated Name'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['created'])
        # Verify name updated, school preserved
        get_resp = self.client.get('/api/v1/profile/')
        self.assertEqual(get_resp.data['name'], 'Updated Name')
        self.assertEqual(get_resp.data['school'], 'Original School')

    def test_profile_put_accepts_name_school(self):
        # Create profile with NRIC
        StudentProfile.objects.create(
            supabase_user_id=TEST_USER_ID, nric='010101-01-1234',
            name='Test',
        )
        # Update via PUT
        response = self.client.put(
            '/api/v1/profile/',
            {'name': 'New Name', 'school': 'New School'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        get_resp = self.client.get('/api/v1/profile/')
        self.assertEqual(get_resp.data['name'], 'New Name')
        self.assertEqual(get_resp.data['school'], 'New School')


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPublicEndpointsRemainOpen(TestCase):
    """Public endpoints must NOT require authentication."""

    def setUp(self):
        self.client = APIClient()

    def test_eligibility_no_auth_required(self):
        response = self.client.post(
            '/api/v1/eligibility/check/',
            {'grades': {'bm': 'A'}, 'gender': 'male'},
            format='json',
        )
        self.assertNotIn(response.status_code, [401, 403])

    def test_courses_no_auth_required(self):
        response = self.client.get('/api/v1/courses/')
        self.assertEqual(response.status_code, 200)

    def test_institutions_no_auth_required(self):
        response = self.client.get('/api/v1/institutions/')
        self.assertEqual(response.status_code, 200)
