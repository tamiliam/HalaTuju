from django.http import HttpResponse
from django.test import TestCase, RequestFactory

from halatuju.middleware.supabase_auth import NricGateMiddleware
from apps.courses.models import StudentProfile


class NricGateMiddlewareTest(TestCase):
    """Middleware blocks non-anonymous users without NRIC from protected endpoints."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = NricGateMiddleware(lambda req: HttpResponse(status=200))

    def test_allows_anonymous_users(self):
        """Anonymous JWT (is_anonymous=true) should pass through."""
        request = self.factory.get('/api/v1/saved-courses/')
        request.user_id = 'anon-123'
        request.supabase_user = {'is_anonymous': True}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_whitelisted_endpoints(self):
        """Profile GET and claim-nric should work without NRIC."""
        for path in ['/api/v1/profile/', '/api/v1/profile/claim-nric/']:
            request = self.factory.get(path)
            request.user_id = 'user-123'
            request.supabase_user = {'is_anonymous': False}
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200, f'Failed for {path}')

    def test_blocks_user_without_nric(self):
        """Non-anonymous user without NRIC should get 403."""
        StudentProfile.objects.create(supabase_user_id='user-no-nric', nric='')
        request = self.factory.post('/api/v1/saved-courses/')
        request.user_id = 'user-no-nric'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_allows_user_with_nric(self):
        """Non-anonymous user WITH NRIC should pass through."""
        StudentProfile.objects.create(supabase_user_id='user-with-nric', nric='010101-01-1234')
        request = self.factory.post('/api/v1/saved-courses/')
        request.user_id = 'user-with-nric'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_public_endpoints(self):
        """Unauthenticated requests (user_id=None) pass through — views decide."""
        request = self.factory.post('/api/v1/eligibility/check/')
        request.user_id = None
        request.supabase_user = None
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_profile_sync(self):
        """Profile sync is whitelisted (called right after NRIC claim)."""
        request = self.factory.post('/api/v1/profile/sync/')
        request.user_id = 'user-123'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_allows_admin_endpoints(self):
        """Admin endpoints are not subject to NRIC gate."""
        request = self.factory.get('/api/v1/admin/role/')
        request.user_id = 'admin-123'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_blocks_user_without_profile(self):
        """Non-anonymous user with no profile at all should get 403."""
        request = self.factory.post('/api/v1/saved-courses/')
        request.user_id = 'user-no-profile'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)
