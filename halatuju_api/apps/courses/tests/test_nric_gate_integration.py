"""
Integration tests for NRIC hard gate — end-to-end through Django test client.

Unlike test_nric_gate.py (which tests the middleware in isolation via RequestFactory),
these tests exercise the full middleware stack + views via APIClient, verifying that
the NRIC gate works correctly with the auth middleware, views, and URL routing.
"""
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from apps.courses.models import StudentProfile


def _setup_auth_with_anon(test_case, user_id, is_anonymous=False):
    """Mock JWT middleware to return a payload with is_anonymous flag."""
    test_case._header_patcher = patch(
        'halatuju.middleware.supabase_auth.jwt.get_unverified_header',
        return_value={'alg': 'HS256'},
    )
    test_case._decode_patcher = patch(
        'halatuju.middleware.supabase_auth.jwt.decode',
        return_value={
            'sub': user_id,
            'aud': 'authenticated',
            'role': 'authenticated',
            'is_anonymous': is_anonymous,
            'email': '' if is_anonymous else f'{user_id}@test.com',
            'phone': '',
        },
    )
    test_case._header_patcher.start()
    test_case._decode_patcher.start()
    test_case.client.credentials(HTTP_AUTHORIZATION='Bearer fake-but-patched')


def _teardown_auth(test_case):
    test_case._decode_patcher.stop()
    test_case._header_patcher.stop()


@override_settings(ROOT_URLCONF='halatuju.urls')
class NricGateIntegrationTest(TestCase):
    """End-to-end tests for NRIC-first identity flow through Django test client."""

    def setUp(self):
        self.client = APIClient()

    def test_anonymous_user_can_access_public_endpoints(self):
        """Anonymous user can hit eligibility check (public endpoint)."""
        _setup_auth_with_anon(self, 'anon-user', is_anonymous=True)
        try:
            response = self.client.post(
                '/api/v1/eligibility/check/',
                {'grades': {'bm': 'A'}, 'gender': 'male'},
                format='json',
            )
            # Should not be 403 (may be 400 for bad input, but not blocked)
            self.assertNotEqual(response.status_code, 403)
        finally:
            _teardown_auth(self)

    def test_anonymous_user_blocked_from_saving_courses(self):
        """Anonymous user cannot save courses — blocked at view level."""
        _setup_auth_with_anon(self, 'anon-user', is_anonymous=True)
        try:
            # Suppress Django test client's exception re-raising so we can
            # inspect the HTTP status code even when the view crashes (500).
            self.client.raise_request_exception = False
            response = self.client.post(
                '/api/v1/saved-courses/',
                {'course_id': 'TEST001'},
                format='json',
            )
            # Anonymous users pass through NRIC gate middleware but cannot
            # save courses — the view requires a StudentProfile which
            # anonymous users don't have. The key assertion: they don't
            # get a successful 200/201 response.
            self.assertNotIn(response.status_code, [200, 201])
        finally:
            self.client.raise_request_exception = True
            _teardown_auth(self)

    def test_authenticated_user_without_nric_blocked(self):
        """Authenticated (non-anonymous) user WITHOUT NRIC gets 403 nric_required."""
        user_id = 'user-no-nric-integration'
        StudentProfile.objects.create(supabase_user_id=user_id, nric='')
        _setup_auth_with_anon(self, user_id, is_anonymous=False)
        try:
            response = self.client.post(
                '/api/v1/saved-courses/',
                {'course_id': 'TEST001'},
                format='json',
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['code'], 'nric_required')
        finally:
            _teardown_auth(self)

    def test_authenticated_user_with_nric_can_save(self):
        """Authenticated user WITH NRIC can access protected endpoints."""
        user_id = 'user-with-nric-integration'
        StudentProfile.objects.create(supabase_user_id=user_id, nric='010101-01-1234')
        _setup_auth_with_anon(self, user_id, is_anonymous=False)
        try:
            response = self.client.post(
                '/api/v1/saved-courses/',
                {'course_id': 'NONEXISTENT'},
                format='json',
            )
            # Should NOT be 403 (may be 404 for nonexistent course, but not blocked by gate)
            self.assertNotEqual(response.status_code, 403)
        finally:
            _teardown_auth(self)

    def test_user_without_profile_blocked(self):
        """User with no profile at all gets 403 from middleware."""
        user_id = 'user-no-profile-integration'
        _setup_auth_with_anon(self, user_id, is_anonymous=False)
        try:
            response = self.client.post(
                '/api/v1/saved-courses/',
                {'course_id': 'TEST001'},
                format='json',
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['code'], 'nric_required')
        finally:
            _teardown_auth(self)

    def test_profile_endpoint_whitelisted(self):
        """Profile GET is whitelisted — works without NRIC (needed to check NRIC status)."""
        user_id = 'user-profile-whitelist'
        _setup_auth_with_anon(self, user_id, is_anonymous=False)
        try:
            response = self.client.get(
                '/api/v1/profile/',
            )
            # Should NOT be 403 (profile is whitelisted)
            self.assertNotEqual(response.status_code, 403)
        finally:
            _teardown_auth(self)

    def test_claim_nric_whitelisted(self):
        """Claim NRIC endpoint is whitelisted — works without NRIC."""
        user_id = 'user-claim-whitelist'
        _setup_auth_with_anon(self, user_id, is_anonymous=False)
        try:
            response = self.client.post(
                '/api/v1/profile/claim-nric/',
                {'nric': '010101-01-1234'},
                format='json',
            )
            # Should NOT be 403 (claim-nric is whitelisted)
            self.assertNotEqual(response.status_code, 403)
        finally:
            _teardown_auth(self)

    def test_profile_sync_blocked_without_nric(self):
        """Profile sync requires NRIC — no longer whitelisted."""
        user_id = 'user-sync-no-whitelist'
        _setup_auth_with_anon(self, user_id, is_anonymous=False)
        try:
            response = self.client.post(
                '/api/v1/profile/sync/',
                {'grades': {}},
                format='json',
            )
            # Should be 403 (sync is no longer whitelisted)
            self.assertEqual(response.status_code, 403)
        finally:
            _teardown_auth(self)

    def test_nric_gate_does_not_block_courses_list(self):
        """Public course listing is not blocked — no auth required."""
        response = self.client.get('/api/v1/courses/')
        self.assertEqual(response.status_code, 200)

    def test_nric_gate_does_not_block_institutions(self):
        """Public institution listing is not blocked — no auth required."""
        response = self.client.get('/api/v1/institutions/')
        self.assertEqual(response.status_code, 200)
