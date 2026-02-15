"""
Tests for authentication enforcement on protected endpoints.

Covers:
- Protected endpoints return 403 without auth token
  (DRF returns 403 instead of 401 when no WWW-Authenticate header is configured)
- Protected endpoints work with valid Supabase JWT
- Public endpoints remain accessible without auth
"""
import jwt
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

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
        self.assertEqual(response.status_code, 403)

    def test_saved_courses_post_rejected(self):
        response = self.client.post(
            '/api/v1/saved-courses/',
            {'course_id': 'FAKE'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_saved_course_delete_rejected(self):
        response = self.client.delete('/api/v1/saved-courses/FAKE/')
        self.assertEqual(response.status_code, 403)

    def test_profile_get_rejected(self):
        response = self.client.get('/api/v1/profile/')
        self.assertEqual(response.status_code, 403)

    def test_profile_put_rejected(self):
        response = self.client.put(
            '/api/v1/profile/',
            {'gender': 'Lelaki'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestProtectedEndpointsAcceptAuth(TestCase):
    """Protected endpoints must accept requests with valid Supabase JWT."""

    def setUp(self):
        self.client = APIClient()
        # Patch jwt.decode in the middleware module to return a valid payload
        # (The middleware instance's jwt_secret is set at startup, before
        # override_settings takes effect, so we mock the decode call instead.)
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

    def test_saved_courses_get_accepted(self):
        response = self.client.get('/api/v1/saved-courses/')
        self.assertEqual(response.status_code, 200)

    def test_profile_get_accepted(self):
        response = self.client.get('/api/v1/profile/')
        self.assertEqual(response.status_code, 200)

    def test_profile_put_accepted(self):
        response = self.client.put(
            '/api/v1/profile/',
            {'gender': 'Lelaki'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPublicEndpointsRemainOpen(TestCase):
    """Public endpoints must NOT require authentication."""

    def setUp(self):
        self.client = APIClient()

    def test_eligibility_no_auth_required(self):
        response = self.client.post(
            '/api/v1/eligibility/check/',
            {'grades': {'BM': 'A'}, 'gender': 'male'},
            format='json',
        )
        self.assertNotIn(response.status_code, [401, 403])

    def test_courses_no_auth_required(self):
        response = self.client.get('/api/v1/courses/')
        self.assertEqual(response.status_code, 200)

    def test_institutions_no_auth_required(self):
        response = self.client.get('/api/v1/institutions/')
        self.assertEqual(response.status_code, 200)
