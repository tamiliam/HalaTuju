"""Audit SEC-02 — a staff row is linked to a first sign-in only by an email the SERVER confirms.

A staff invitation creates a ``PartnerAdmin`` row with no login id; the first sign-in with that
email links it (``PartnerAdminMixin._find_admin``, and the withdrawn check in
``staff_reinvite.is_withdrawn``). The link used to trust ``email_verified`` from the token — and
the middleware fell back to ``user_metadata.email_verified``, which the account's own browser can
write. Anyone who could sign up with a staff member's address could set that flag and take the row.

Now the middleware reads the top-level claim only, and the link asks Supabase's admin API
(``supabase_admin.read_auth_user``) for ``email_confirmed_at`` — fail closed: an unreadable login
links nothing. The admin read is mocked throughout; nothing touches the network.
"""
from unittest.mock import patch

import jwt
from django.test import RequestFactory, TestCase, override_settings

from apps.courses import supabase_admin
from apps.courses.models import PartnerAdmin
from apps.scholarship.tests.factories import TEST_JWT_SECRET, make_admin, make_org
from halatuju.middleware.supabase_auth import SupabaseAuthMiddleware

ROLE = '/api/v1/admin/role/'
EMAIL = 'rohini@example.org'
SUB = 'first-login-uid'
CONFIRMED = {'id': SUB, 'email': EMAIL, 'email_confirmed_at': '2026-11-01T00:00:00Z'}
UNCONFIRMED = {'id': SUB, 'email': EMAIL, 'email_confirmed_at': None}
READ = 'apps.courses.supabase_admin.read_auth_user'


def _forged_token(sub=SUB, email=EMAIL):
    """What an attacker's own browser can mint: no top-level ``email_verified``, but the
    browser-writable ``user_metadata`` says verified."""
    return jwt.encode({'sub': sub, 'aud': 'authenticated', 'role': 'authenticated', 'email': email,
                       'user_metadata': {'email_verified': True, 'email': email}},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class MiddlewareIgnoresUserMetadata(TestCase):
    def test_user_metadata_email_verified_is_not_read(self):
        req = RequestFactory().get('/', HTTP_AUTHORIZATION=f'Bearer {_forged_token()}')
        SupabaseAuthMiddleware(lambda r: None)(req)
        self.assertEqual(req.supabase_user['email'], EMAIL)
        self.assertFalse(req.supabase_user['email_verified'])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class FirstSignInLinks(TestCase):
    def setUp(self):
        self.row = make_admin('reviewer', owning_org=make_org(), email=EMAIL, name='Rohini')
        PartnerAdmin.objects.filter(pk=self.row.pk).update(supabase_user_id=None)

    def _sign_in(self, read):
        with patch(READ, **read) as mock_read:
            r = self.client.get(ROLE, HTTP_AUTHORIZATION=f'Bearer {_forged_token()}')
        self.row.refresh_from_db()
        return r, mock_read

    def test_a_forged_user_metadata_flag_without_a_confirmed_email_does_not_link(self):
        r, read = self._sign_in({'return_value': UNCONFIRMED})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['is_admin'])
        self.assertIsNone(self.row.supabase_user_id)
        read.assert_called_with(SUB)

    def test_a_confirmed_login_links(self):
        r, _ = self._sign_in({'return_value': CONFIRMED})
        self.assertTrue(r.json()['is_admin'], r.content)
        self.assertEqual(self.row.supabase_user_id, SUB)

    def test_an_unreadable_login_is_refused_and_nothing_crashes(self):
        for read in ({'return_value': supabase_admin.FAILED}, {'return_value': supabase_admin.GONE},
                     {'return_value': supabase_admin.INERT}, {'side_effect': RuntimeError('boom')}):
            with self.subTest(read=read):
                r, _ = self._sign_in(read)
                self.assertEqual(r.status_code, 200, r.content)
                self.assertFalse(r.json()['is_admin'])
                self.assertIsNone(self.row.supabase_user_id)

    def test_a_confirmed_login_for_another_address_is_refused(self):
        other = dict(CONFIRMED, email='someone-else@example.org')
        r, _ = self._sign_in({'return_value': other})
        self.assertFalse(r.json()['is_admin'])
        self.assertIsNone(self.row.supabase_user_id)


class LinkRefusalUnit(TestCase):
    def test_reasons(self):
        cases = (
            ({'return_value': CONFIRMED}, None),
            ({'return_value': dict(CONFIRMED, email=' Rohini@Example.ORG ')}, None),
            ({'return_value': UNCONFIRMED}, 'email_unconfirmed'),
            ({'return_value': dict(CONFIRMED, email='x@example.org')}, 'email_mismatch'),
            ({'return_value': supabase_admin.FAILED}, 'login_unreadable'),
            ({'return_value': supabase_admin.INERT}, 'login_unreadable'),
            ({'side_effect': RuntimeError('boom')}, 'login_unreadable'),
        )
        for read, want in cases:
            with self.subTest(read=read), patch(READ, **read):
                self.assertEqual(supabase_admin.link_refusal(SUB, EMAIL), want)

    def test_a_refusal_logs_the_reason_never_the_address(self):
        with patch(READ, return_value=UNCONFIRMED), \
                self.assertLogs('apps.courses.supabase_admin', level='WARNING') as logs:
            supabase_admin.link_refusal(SUB, EMAIL)
        self.assertTrue(any('staff_link_refused reason=email_unconfirmed' in m for m in logs.output))
        self.assertFalse(any(EMAIL in m for m in logs.output))
