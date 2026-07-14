import datetime
from unittest.mock import MagicMock, patch

import jwt
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerOrganisation, PartnerAdmin, StudentProfile

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


class PartnerOrgFieldsTest(TestCase):
    def test_contact_fields(self):
        org = PartnerOrganisation.objects.create(
            code='cumig', name='CUMIG',
            contact_person='Encik Ali',
            phone='012-3456789',
        )
        self.assertEqual(org.contact_person, 'Encik Ali')
        self.assertEqual(org.phone, '012-3456789')

    def test_contact_fields_optional(self):
        org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        self.assertEqual(org.contact_person, '')
        self.assertEqual(org.phone, '')


class PartnerAdminModelTest(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')

    def test_create_partner_admin(self):
        admin = PartnerAdmin.objects.create(
            email='admin@cumig.org',
            name='Ali Ahmad',
            org=self.org,
        )
        self.assertEqual(admin.email, 'admin@cumig.org')
        self.assertEqual(admin.org, self.org)
        self.assertFalse(admin.is_super_admin)
        self.assertIsNone(admin.supabase_user_id)

    def test_create_super_admin(self):
        admin = PartnerAdmin.objects.create(
            email='super@halatuju.com',
            name='Super Admin',
            is_super_admin=True,
        )
        self.assertTrue(admin.is_super_admin)
        self.assertIsNone(admin.org)

    def test_email_unique(self):
        PartnerAdmin.objects.create(email='admin@cumig.org', name='Admin 1', org=self.org)
        with self.assertRaises(Exception):
            PartnerAdmin.objects.create(email='admin@cumig.org', name='Admin 2', org=self.org)

    def test_supabase_uid_backfill(self):
        admin = PartnerAdmin.objects.create(email='admin@cumig.org', name='Ali', org=self.org)
        self.assertIsNone(admin.supabase_user_id)
        admin.supabase_user_id = 'uid-123'
        admin.save()
        admin.refresh_from_db()
        self.assertEqual(admin.supabase_user_id, 'uid-123')

    def test_str(self):
        admin = PartnerAdmin.objects.create(email='admin@cumig.org', name='Ali', org=self.org)
        self.assertIn('Ali', str(admin))
        self.assertIn('CUMIG', str(admin))


class PartnerAdminMixinTest(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        self.partner_admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid-1',
            email='admin@cumig.org',
            name='Ali',
            org=self.org,
        )
        self.super_admin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid-1',
            email='super@halatuju.com',
            name='Super',
            is_super_admin=True,
        )
        for i in range(2):
            StudentProfile.objects.create(
                supabase_user_id=f'student-{i}',
                name=f'Student {i}',
                referred_by_org=self.org,
            )
        StudentProfile.objects.create(
            supabase_user_id='student-other',
            name='Other',
        )

    def test_get_admin_by_uid(self):
        admin = PartnerAdmin.objects.filter(supabase_user_id='admin-uid-1').first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.org, self.org)

    def test_get_admin_by_email_fallback(self):
        self.partner_admin.supabase_user_id = None
        self.partner_admin.save()
        admin = PartnerAdmin.objects.filter(email='admin@cumig.org').first()
        self.assertIsNotNone(admin)
        admin.supabase_user_id = 'new-uid'
        admin.save()
        admin.refresh_from_db()
        self.assertEqual(admin.supabase_user_id, 'new-uid')

    def test_partner_admin_sees_own_students(self):
        students = StudentProfile.objects.filter(referred_by_org=self.org)
        self.assertEqual(students.count(), 2)

    def test_super_admin_sees_all_students(self):
        students = StudentProfile.objects.all()
        self.assertEqual(students.count(), 3)

    def test_unverified_email_does_not_acquire_admin(self):
        """TD audit 2026-06-14 — defence-in-depth. A caller presenting an admin's email in a JWT
        whose email is NOT verified must NOT be linked to that admin row (no privilege grab)."""
        from types import SimpleNamespace
        from apps.courses.views_admin import PartnerAdminMixin
        self.partner_admin.supabase_user_id = None
        self.partner_admin.save()
        req = SimpleNamespace(
            user_id='attacker-uid',
            supabase_user={'email': 'admin@cumig.org', 'email_verified': False})
        self.assertIsNone(PartnerAdminMixin().get_admin(req))
        self.partner_admin.refresh_from_db()
        self.assertIsNone(self.partner_admin.supabase_user_id)  # not backfilled

    def test_verified_email_acquires_admin(self):
        """Positive control: a VERIFIED email claim still links + backfills the admin row."""
        from types import SimpleNamespace
        from apps.courses.views_admin import PartnerAdminMixin
        self.partner_admin.supabase_user_id = None
        self.partner_admin.save()
        req = SimpleNamespace(
            user_id='legit-uid',
            supabase_user={'email': 'admin@cumig.org', 'email_verified': True})
        admin = PartnerAdminMixin().get_admin(req)
        self.assertIsNotNone(admin)
        self.partner_admin.refresh_from_db()
        self.assertEqual(self.partner_admin.supabase_user_id, 'legit-uid')  # backfilled

    def test_admin_role_view_exists(self):
        from apps.courses.views_admin import AdminRoleView
        self.assertTrue(hasattr(AdminRoleView, 'get'))

    def test_invite_view_exists(self):
        from apps.courses.views_admin import AdminInviteView
        self.assertTrue(hasattr(AdminInviteView, 'post'))

    def test_orgs_view_exists(self):
        from apps.courses.views_admin import AdminOrgsView
        self.assertTrue(hasattr(AdminOrgsView, 'get'))


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class AdminInviteRoleTest(TestCase):
    """F5: the inviter picks the new admin's role (super|reviewer|viewer)."""

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@halatuju.com',
        )

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("super-uid")}')

    def _invite(self, email, role=None):
        payload = {'email': email, 'name': 'Invitee'}
        if role is not None:
            payload['role'] = role
        with patch('apps.courses.views_admin.http_requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200, text='ok', json=lambda: {'id': 'new-supabase-uid'})
            self.mock_post = mock_post
            return self.client.post('/api/v1/admin/invite/', payload, format='json')

    def test_invite_reviewer(self):
        r = self._invite('rev@example.com', 'reviewer')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['role'], 'reviewer')
        a = PartnerAdmin.objects.get(email='rev@example.com')
        self.assertEqual(a.role, 'reviewer')
        self.assertFalse(a.is_super_admin)

    def test_invite_viewer(self):
        self._invite('view@example.com', 'admin')
        a = PartnerAdmin.objects.get(email='view@example.com')
        self.assertEqual(a.role, 'admin')
        self.assertFalse(a.is_super_admin)

    def test_invite_existing_supabase_user_grants_without_password(self):
        # Supabase 422 email_exists (person already has an account) is NOT a failure:
        # create the admin row anyway — it links by email on their next sign-in. We must NOT
        # reset the password of an account we did not create.
        payload = {'email': 'existing@example.com', 'name': 'Existing User', 'role': 'admin'}
        with patch('apps.courses.views_admin.http_requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=422, text='exists',
                json=lambda: {'code': 422, 'error_code': 'email_exists', 'msg': 'already registered'})
            r = self.client.post('/api/v1/admin/invite/', payload, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()['already_registered'])
        a = PartnerAdmin.objects.get(email='existing@example.com')
        self.assertEqual(a.role, 'admin')
        self.assertIsNone(a.supabase_user_id)  # backfilled when they next sign in
        # They still get told they have access — but with no password in the mail.
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('temporary password', mail.outbox[0].body)

    def test_invite_genuine_supabase_failure_502(self):
        # Any other Supabase error is still a failure — 502, no admin row created.
        payload = {'email': 'fail@example.com', 'name': 'X', 'role': 'reviewer'}
        with patch('apps.courses.views_admin.http_requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=500, text='boom', json=lambda: {'error_code': 'unexpected'})
            r = self.client.post('/api/v1/admin/invite/', payload, format='json')
        self.assertEqual(r.status_code, 502)
        self.assertFalse(PartnerAdmin.objects.filter(email='fail@example.com').exists())

    def test_invite_super_not_allowed_falls_back_to_reviewer(self):
        # Super is NOT invitable (there is one super admin — the owner). An attempt
        # to invite 'super' falls back to the safe workhorse role.
        self._invite('sup2@example.com', 'super')
        a = PartnerAdmin.objects.get(email='sup2@example.com')
        self.assertEqual(a.role, 'reviewer')
        self.assertFalse(a.is_super_admin)

    def test_invite_defaults_to_reviewer(self):
        self._invite('def@example.com')  # no role sent
        self.assertEqual(PartnerAdmin.objects.get(email='def@example.com').role, 'reviewer')

    def test_invalid_role_falls_back_to_reviewer(self):
        self._invite('bad@example.com', 'wizard')
        self.assertEqual(PartnerAdmin.objects.get(email='bad@example.com').role, 'reviewer')

    def test_non_super_cannot_invite(self):
        PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rev', email='rev-actor@example.com',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("rev-uid")}')
        r = self._invite('x@example.com', 'reviewer')
        self.assertEqual(r.status_code, 403)

    def test_admin_list_returns_role(self):
        PartnerAdmin.objects.create(
            supabase_user_id='v-uid', role='admin', is_active=True,
            name='V', email='v@example.com',
        )
        r = self.client.get('/api/v1/admin/admins/')
        self.assertEqual(r.status_code, 200)
        roles = {a['email']: a['role'] for a in r.json()['admins']}
        self.assertEqual(roles['v@example.com'], 'admin')
        self.assertEqual(roles['super@halatuju.com'], 'super')


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class PartnerAccountCreationTest(TestCase):
    """2026-07-12: onboarding creates the Supabase account outright (temp password in OUR email)
    instead of sending a Supabase invite whose magic link expired in 24h and could never be
    re-sent — the failure that stranded a reviewer on 2026-07-10."""

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@halatuju.com',
        )

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("super-uid")}')
        mail.outbox = []

    def _invite(self, email='new@example.com', role='reviewer'):
        with patch('apps.courses.views_admin.http_requests.post') as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200, text='ok', json=lambda: {'id': 'created-uid'})
            r = self.client.post(
                '/api/v1/admin/invite/', {'email': email, 'name': 'New Partner', 'role': role},
                format='json')
        return r, mock_post

    def test_creates_the_supabase_account_rather_than_inviting(self):
        r, mock_post = self._invite()
        self.assertEqual(r.status_code, 201)
        url = mock_post.call_args[0][0]
        self.assertTrue(url.endswith('/auth/v1/admin/users'), url)
        self.assertNotIn('/invite', url)

    def test_account_is_created_with_a_password_and_a_verified_email(self):
        # email_confirm is load-bearing: get_admin only links a PartnerAdmin row by email when the
        # JWT's email_verified claim is true, so without it the partner would have no role.
        _, mock_post = self._invite()
        body = mock_post.call_args[1]['json']
        self.assertTrue(body['email_confirm'])
        self.assertTrue(body['password'])
        self.assertEqual(body['user_metadata']['name'], 'New Partner')
        self.assertTrue(body['user_metadata']['must_change_password'])

    def test_supabase_uid_is_stored_on_the_row(self):
        self._invite()
        self.assertEqual(
            PartnerAdmin.objects.get(email='new@example.com').supabase_user_id, 'created-uid')

    def test_the_email_carries_the_password_the_login_link_and_the_7_day_ttl(self):
        _, mock_post = self._invite()
        sent_password = mock_post.call_args[1]['json']['password']
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['new@example.com'])
        self.assertIn(sent_password, msg.body)
        self.assertIn('/admin/login', msg.body)
        self.assertIn('reviewer', msg.body)
        # The temp password now expires after 7 days (owner 2026-07-14), but onboarding still never
        # dead-ends — a Resend re-issues it — so the mail states the 7-day window + how to recover,
        # and carries none of the old 24h-magic-link language.
        body = msg.body.lower()
        self.assertIn('7 days', body)
        self.assertNotIn('24 hour', body)

    def test_the_create_body_stamps_the_temp_password_clock(self):
        # temp_password_issued_at starts the 7-day TTL the login gate + expire cron enforce.
        _, mock_post = self._invite()
        meta = mock_post.call_args[1]['json']['user_metadata']
        self.assertTrue(meta['must_change_password'])
        self.assertIn('temp_password_issued_at', meta)
        self.assertTrue(meta['temp_password_issued_at'])

    def test_the_password_never_reaches_the_caller(self):
        # The email is the only carrier — it must not leak into the API response body.
        r, mock_post = self._invite()
        sent_password = mock_post.call_args[1]['json']['password']
        self.assertNotIn(sent_password, str(r.json()))
        self.assertTrue(r.json()['emailed'])

    def test_a_failed_send_is_reported_not_swallowed(self):
        # A silent failure would strand the invitee with a password they never received.
        with patch('apps.courses.views_admin.http_requests.post') as mock_post, \
                patch('apps.courses.views_admin.send_partner_welcome_email', return_value=False):
            mock_post.return_value = MagicMock(
                status_code=200, text='ok', json=lambda: {'id': 'created-uid'})
            r = self.client.post(
                '/api/v1/admin/invite/',
                {'email': 'quiet@example.com', 'name': 'Q', 'role': 'reviewer'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.json()['emailed'])
        self.assertIn('Resend', r.json()['message'])

    def test_temp_passwords_are_unique_and_unambiguous(self):
        from apps.courses.views_admin import generate_temp_password
        pws = {generate_temp_password() for _ in range(50)}
        self.assertEqual(len(pws), 50)
        for ch in '0O1lI':
            self.assertNotIn(ch, ''.join(pws))

    def test_gmail_invite_creates_no_password_account(self):
        # Option 1 (owner 2026-07-14): a Google address signs in with Google — create ONLY the
        # PartnerAdmin row (no Supabase account, no temp password); the email routes to Google.
        with patch('apps.courses.views_admin.http_requests.post') as mock_post:
            r = self.client.post(
                '/api/v1/admin/invite/',
                {'email': 'alice@gmail.com', 'name': 'Alice', 'role': 'reviewer'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()['google'])
        mock_post.assert_not_called()                     # no Supabase account was created
        a = PartnerAdmin.objects.get(email='alice@gmail.com')
        self.assertIsNone(a.supabase_user_id)             # links on first Google sign-in
        self.assertEqual(a.role, 'reviewer')
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body.lower()
        self.assertIn('sign in with google', body)
        self.assertNotIn('temporary password', body)      # no password issued to a Google user


@override_settings(
    ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
)
class AdminResendTest(TestCase):
    """Resend exists because there was previously NO way to re-send an invite to anyone."""

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@halatuju.com',
        )
        cls.target = PartnerAdmin.objects.create(
            supabase_user_id='target-uid', role='reviewer', is_active=True,
            name='Goban', email='goban@example.com',
        )
        # Pre-existing account we did NOT create (no UID captured at invite time).
        cls.no_uid = PartnerAdmin.objects.create(
            role='reviewer', is_active=True, name='Prior', email='prior@example.com',
        )

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("super-uid")}')
        mail.outbox = []

    def test_resend_rotates_the_password_and_re_emails(self):
        with patch('apps.courses.views_admin.http_requests.put') as mock_put:
            mock_put.return_value = MagicMock(status_code=200, text='ok', json=lambda: {})
            r = self.client.post(f'/api/v1/admin/admins/{self.target.id}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(mock_put.call_args[0][0].endswith('/auth/v1/admin/users/target-uid'))
        new_password = mock_put.call_args[1]['json']['password']
        self.assertTrue(mock_put.call_args[1]['json']['user_metadata']['must_change_password'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(new_password, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['goban@example.com'])
        self.assertNotIn(new_password, str(r.json()))

    def test_resend_never_resets_a_password_we_did_not_issue(self):
        # No stored UID = the person signed up themselves (student/Google). Resetting their
        # password would lock them out of their own account.
        with patch('apps.courses.views_admin.http_requests.put') as mock_put:
            r = self.client.post(f'/api/v1/admin/admins/{self.no_uid.id}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        mock_put.assert_not_called()
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('temporary password', mail.outbox[0].body)

    def test_resend_reports_a_rotation_failure(self):
        with patch('apps.courses.views_admin.http_requests.put') as mock_put:
            mock_put.return_value = MagicMock(status_code=500, text='boom', json=lambda: {})
            r = self.client.post(f'/api/v1/admin/admins/{self.target.id}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 502)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_404_for_unknown_admin(self):
        r = self.client.post('/api/v1/admin/admins/99999/resend/', {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_non_super_cannot_resend(self):
        PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rev', email='rev-actor@example.com',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("rev-uid")}')
        r = self.client.post(f'/api/v1/admin/admins/{self.target.id}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 403)


@override_settings(
    SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co',
    PARTNER_TEMP_PASSWORD_TTL_DAYS=7,
)
class ExpireTempPasswordsTest(TestCase):
    """The daily job that makes the 7-day temp-password TTL a real boundary (owner 2026-07-14):
    it rotates an UNCHANGED temp password dead once it is past the TTL, and never touches a partner
    who has set their own password or who signs in with Google (no UID)."""

    _MOD = 'apps.courses.management.commands.expire_temp_passwords.http_requests'

    def _admin(self, uid, email):
        return PartnerAdmin.objects.create(
            supabase_user_id=uid, role='reviewer', is_active=True, name='X', email=email)

    def _run(self, metadata_by_uid):
        def fake_get(url, **kw):
            uid = url.rstrip('/').rsplit('/', 1)[-1]
            if uid not in metadata_by_uid:
                return MagicMock(status_code=404, text='nf', json=lambda: {})
            meta = metadata_by_uid[uid]
            return MagicMock(status_code=200, text='ok', json=lambda m=meta: {'user_metadata': m})
        with patch(f'{self._MOD}.get', side_effect=fake_get) as g, \
                patch(f'{self._MOD}.put') as p:
            p.return_value = MagicMock(status_code=200, text='ok')
            call_command('expire_temp_passwords')
        return g, p

    def _ago(self, days):
        return (timezone.now() - datetime.timedelta(days=days)).isoformat()

    def test_rotates_a_stale_unchanged_temp_password(self):
        self._admin('u-stale', 'stale@example.com')
        _, put = self._run({'u-stale': {'must_change_password': True,
                                        'temp_password_issued_at': self._ago(8)}})
        put.assert_called_once()
        body = put.call_args[1]['json']
        self.assertTrue(body['password'])                                  # rotated to a new secret
        self.assertTrue(body['user_metadata']['temp_password_expired'])    # marked expired
        self.assertNotIn('temp_password_issued_at', body['user_metadata'])  # clock cleared

    def test_skips_a_fresh_temp_password(self):
        self._admin('u-fresh', 'fresh@example.com')
        _, put = self._run({'u-fresh': {'must_change_password': True,
                                        'temp_password_issued_at': self._ago(1)}})
        put.assert_not_called()

    def test_skips_a_partner_who_set_their_own_password(self):
        self._admin('u-changed', 'changed@example.com')
        _, put = self._run({'u-changed': {'must_change_password': False,
                                          'temp_password_issued_at': self._ago(30)}})
        put.assert_not_called()

    def test_never_fetches_or_rotates_a_google_row_with_no_uid(self):
        PartnerAdmin.objects.create(supabase_user_id=None, role='reviewer', is_active=True,
                                    name='G', email='g@gmail.com')
        get, put = self._run({})
        get.assert_not_called()
        put.assert_not_called()
