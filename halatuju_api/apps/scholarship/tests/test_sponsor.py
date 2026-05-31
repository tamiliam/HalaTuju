"""Phase E — Sprint E1: sponsor self-registration + admin vetting (no student data)."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import Sponsor

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid, email='', anon=False):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': anon},
        TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorRegister(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid, email='', anon=False):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, email, anon)}')

    FULL = {'name': 'Alice', 'phone': '012-345 6789', 'source': 'google', 'consent': True}

    def test_register_creates_pending(self):
        self._auth('spon-1', 'a@x.com')
        r = self.client.post('/api/v1/sponsor/register/', {**self.FULL, 'organisation': 'ACME'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        s = Sponsor.objects.get(supabase_user_id='spon-1')
        self.assertEqual((s.status, s.email, s.name, s.organisation), ('pending', 'a@x.com', 'Alice', 'ACME'))
        self.assertEqual((s.phone, s.source), ('012-345 6789', 'google'))
        self.assertIsNotNone(s.consent_at)
        self.assertTrue(s.consent_version)
        self.assertTrue(r.json()['profile_complete'])

    def test_register_idempotent_when_complete(self):
        self._auth('spon-2', 'b@x.com')
        self.client.post('/api/v1/sponsor/register/', {**self.FULL, 'name': 'Bob'}, format='json')
        r2 = self.client.post('/api/v1/sponsor/register/', {**self.FULL, 'name': 'Bob again'}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(Sponsor.objects.filter(supabase_user_id='spon-2').count(), 1)
        self.assertEqual(Sponsor.objects.get(supabase_user_id='spon-2').name, 'Bob')  # unchanged

    def test_register_completes_incomplete_sponsor(self):
        # A legacy/Google row with no phone/source/consent is completed in place.
        Sponsor.objects.create(supabase_user_id='spon-g', name='Gina', email='g@x.com', status='pending')
        self._auth('spon-g', 'g@x.com')
        r = self.client.post('/api/v1/sponsor/register/', {**self.FULL, 'name': 'Gina'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        s = Sponsor.objects.get(supabase_user_id='spon-g')
        self.assertEqual((s.phone, s.source, s.status), ('012-345 6789', 'google', 'pending'))
        self.assertIsNotNone(s.consent_at)
        self.assertEqual(Sponsor.objects.filter(supabase_user_id='spon-g').count(), 1)

    def test_register_missing_fields(self):
        self._auth('spon-3', 'c@x.com')
        r = self.client.post('/api/v1/sponsor/register/', {'name': 'NoPhone', 'consent': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'missing_fields')
        self.assertIn('phone', r.json()['fields'])
        self.assertIn('source', r.json()['fields'])

    def test_register_requires_consent(self):
        self._auth('spon-4', 'd@x.com')
        r = self.client.post('/api/v1/sponsor/register/',
                             {'name': 'NoConsent', 'phone': '0123456789', 'source': 'friend'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'consent_required')

    def test_anonymous_cannot_register(self):
        self._auth('anon-1', '', anon=True)
        r = self.client.post('/api/v1/sponsor/register/', {**self.FULL, 'name': 'Ghost'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'not_signed_in')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorMe(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid, email=''):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, email)}')

    def test_me_unregistered(self):
        self._auth('spon-4', 'd@x.com')
        r = self.client.get('/api/v1/sponsor/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'registered': False})

    def test_me_after_register(self):
        self._auth('spon-5', 'e@x.com')
        self.client.post('/api/v1/sponsor/register/',
                         {'name': 'Eve', 'phone': '0123456789', 'source': 'event', 'consent': True}, format='json')
        r = self.client.get('/api/v1/sponsor/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()['status'], r.json()['name']), ('pending', 'Eve'))
        self.assertTrue(r.json()['profile_complete'])

    def test_me_incomplete_profile_flag(self):
        # A row without phone/source/consent reports profile_complete=false.
        Sponsor.objects.create(supabase_user_id='spon-6', name='Ivan', email='i@x.com', status='pending')
        self._auth('spon-6', 'i@x.com')
        r = self.client.get('/api/v1/sponsor/me/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['profile_complete'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminSponsorVetting(TestCase):
    @classmethod
    def setUpTestData(cls):
        PartnerAdmin.objects.create(supabase_user_id='rev', role='reviewer', is_active=True, name='Rev', email='r@x.com')
        PartnerAdmin.objects.create(supabase_user_id='vie', role='viewer', is_active=True, name='Vie', email='v@x.com')
        cls.s = Sponsor.objects.create(supabase_user_id='sp', name='S', email='s@x.com', status='pending')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid, "x@x.com")}')

    def test_list_sponsors(self):
        self._auth('rev')
        r = self.client.get('/api/v1/admin/sponsors/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(x['id'] == self.s.id for x in r.json()['sponsors']))

    def test_list_filter_status(self):
        self._auth('rev')
        r = self.client.get('/api/v1/admin/sponsors/?status=approved')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['sponsors'], [])  # the only sponsor is pending

    def test_reviewer_approve(self):
        self._auth('rev')
        r = self.client.post(f'/api/v1/admin/sponsors/{self.s.id}/review/', {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.s.refresh_from_db()
        self.assertEqual(self.s.status, 'approved')
        self.assertEqual(self.s.reviewed_by, 'r@x.com')
        self.assertIsNotNone(self.s.reviewed_at)

    def test_reviewer_reject_and_suspend(self):
        self._auth('rev')
        self.assertEqual(self.client.post(f'/api/v1/admin/sponsors/{self.s.id}/review/', {'action': 'reject'}, format='json').status_code, 200)
        self.s.refresh_from_db(); self.assertEqual(self.s.status, 'rejected')

    def test_bad_action_400(self):
        self._auth('rev')
        r = self.client.post(f'/api/v1/admin/sponsors/{self.s.id}/review/', {'action': 'nope'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_viewer_forbidden(self):
        self._auth('vie')
        r = self.client.post(f'/api/v1/admin/sponsors/{self.s.id}/review/', {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, 403)
