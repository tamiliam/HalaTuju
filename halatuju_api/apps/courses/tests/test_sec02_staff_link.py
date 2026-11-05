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


GMAIL = 'rohini.test@gmail.com'
GMAIL_PASSWORD = {'id': SUB, 'email': GMAIL, 'email_confirmed_at': '2026-11-01T00:00:00Z',
                  'app_metadata': {'provider': 'email', 'providers': ['email']},
                  'identities': [{'provider': 'email'}]}
GMAIL_GOOGLE = dict(GMAIL_PASSWORD, app_metadata={'provider': 'google', 'providers': ['google']},
                    identities=[{'provider': 'google'}])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class GoogleInviteLinksOnlyAGoogleLogin(TestCase):
    """L3: a Gmail invitee's row (no login id; the letter said "Sign in with Google", no password)
    links only a login whose server-side providers include ``google`` — with Supabase's "Confirm
    email" off, a password sign-up at that address is "confirmed" with no proof."""
    def setUp(self):
        self.row = make_admin('reviewer', owning_org=make_org(), email=GMAIL, name='Rohini')
        PartnerAdmin.objects.filter(pk=self.row.pk).update(supabase_user_id=None)

    def _sign_in(self, account):
        with patch(READ, return_value=account) as read:
            r = self.client.get(ROLE, HTTP_AUTHORIZATION=f'Bearer {_forged_token(email=GMAIL)}')
        self.row.refresh_from_db()
        return r, read

    def test_a_confirmed_password_login_does_not_take_a_google_invite(self):
        r, read = self._sign_in(GMAIL_PASSWORD)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['is_admin'])
        self.assertIsNone(self.row.supabase_user_id)
        read.assert_called_with(SUB)

    def test_a_google_login_links(self):
        r, _ = self._sign_in(GMAIL_GOOGLE)
        self.assertTrue(r.json()['is_admin'], r.content)
        self.assertEqual(self.row.supabase_user_id, SUB)

    def test_a_login_with_both_providers_links(self):
        both = dict(GMAIL_PASSWORD, app_metadata={'provider': 'email', 'providers': ['email', 'google']},
                    identities=[{'provider': 'email'}, {'provider': 'google'}])
        r, _ = self._sign_in(both)
        self.assertTrue(r.json()['is_admin'], r.content)

    def test_a_withdrawn_google_invite_is_reported_only_to_a_google_login(self):
        from apps.courses import staff_reinvite
        PartnerAdmin.objects.filter(pk=self.row.pk).update(is_active=False)
        su = {'email': GMAIL}
        with patch(READ, return_value=GMAIL_PASSWORD):
            self.assertFalse(staff_reinvite.is_withdrawn(SUB, su))
        with patch(READ, return_value=GMAIL_GOOGLE):
            self.assertTrue(staff_reinvite.is_withdrawn(SUB, su))

    def test_a_row_invited_with_a_login_of_ours_is_unchanged(self):
        """A non-Google invite we created a login for carries its login id from the invite, so the
        first sign-in matches by id and never reaches the email link (no admin read at all)."""
        other = make_admin('reviewer', owning_org=make_org(), email='mala@example.org', name='Mala')
        PartnerAdmin.objects.filter(pk=other.pk).update(supabase_user_id='invited-uid')
        token = _forged_token(sub='invited-uid', email='mala@example.org')
        with patch(READ) as read:
            r = self.client.get(ROLE, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertTrue(r.json()['is_admin'], r.content)
        read.assert_not_called()


class LinkRefusalUnit(TestCase):
    def test_a_google_address_needs_a_google_provider(self):
        cases = (
            (GMAIL_PASSWORD, 'google_invite_not_google_login'),
            (dict(GMAIL_PASSWORD, app_metadata={}, identities=[]), 'google_invite_not_google_login'),
            (dict(GMAIL_PASSWORD, user_metadata={'provider': 'google'}), 'google_invite_not_google_login'),
            (GMAIL_GOOGLE, None),
            (dict(GMAIL_PASSWORD, app_metadata={'providers': ['google']}, identities=[]), None),
            (dict(GMAIL_PASSWORD, app_metadata={}, identities=[{'provider': 'google'}]), None),
            (dict(GMAIL_PASSWORD, email='Rohini.Test@GoogleMail.com', app_metadata={}), 'email_mismatch'),
        )
        for account, want in cases:
            with self.subTest(account=account), patch(READ, return_value=account):
                self.assertEqual(supabase_admin.link_refusal(SUB, GMAIL), want)
        googlemail = dict(GMAIL_PASSWORD, email='rohini.test@googlemail.com')
        with patch(READ, return_value=googlemail):
            self.assertEqual(supabase_admin.link_refusal(SUB, 'rohini.test@googlemail.com'),
                             'google_invite_not_google_login')
        # A non-Google address keeps the SEC-02 rule alone: a confirmed password login links.
        with patch(READ, return_value=dict(CONFIRMED, app_metadata={'providers': ['email']})):
            self.assertIsNone(supabase_admin.link_refusal(SUB, EMAIL))

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
