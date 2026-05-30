"""Sponsor-interest lead capture (public submit + admin list)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import SponsorInterest

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'si-admin-uid'


def _token(uid, anonymous=False):
    payload = {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'}
    if anonymous:
        payload['is_anonymous'] = True
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorInterest(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('apps.scholarship.views.send_sponsor_interest_admin_email')
    def test_public_submit_creates_row_and_emails(self, mock_email):
        # No auth at all — public lead form.
        r = self.client.post('/api/v1/sponsor-interest/', {
            'name': 'Jane Donor', 'email': 'jane@example.com',
            'organisation': 'Acme Foundation', 'message': 'Keen to fund 5 students.',
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(SponsorInterest.objects.count(), 1)
        row = SponsorInterest.objects.first()
        self.assertEqual(row.email, 'jane@example.com')
        self.assertEqual(row.status, 'new')
        mock_email.assert_called_once()

    def test_missing_email_400(self):
        r = self.client.post('/api/v1/sponsor-interest/', {'name': 'No Email'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SponsorInterest.objects.count(), 0)

    def test_missing_name_400(self):
        r = self.client.post('/api/v1/sponsor-interest/',
                             {'email': 'x@example.com', 'name': '  '}, format='json')
        self.assertEqual(r.status_code, 400)

    @patch('apps.scholarship.views.send_sponsor_interest_admin_email')
    def test_nric_gate_does_not_block_authenticated_no_nric_user(self, _mock):
        # An authenticated (non-anonymous) user WITHOUT an NRIC would normally be
        # 403'd by the gate on protected endpoints; this public path is whitelisted.
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("some-user")}')
        r = self.client.post('/api/v1/sponsor-interest/',
                             {'name': 'A', 'email': 'a@example.com'}, format='json')
        self.assertEqual(r.status_code, 201)

    def test_admin_list_requires_admin(self):
        r = self.client.get('/api/v1/admin/sponsor-interest/')
        self.assertEqual(r.status_code, 401)  # no auth

    def test_admin_list_returns_rows(self):
        SponsorInterest.objects.create(name='A', email='a@example.com')
        PartnerAdmin.objects.create(supabase_user_id=ADMIN, is_super_admin=True,
                                    is_active=True, name='Admin', email='admin@si.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(ADMIN)}')
        r = self.client.get('/api/v1/admin/sponsor-interest/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['interests']), 1)
