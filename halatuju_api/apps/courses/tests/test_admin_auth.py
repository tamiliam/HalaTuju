from unittest.mock import MagicMock, patch

import jwt
from django.test import TestCase, override_settings
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
            mock_post.return_value = MagicMock(status_code=200, text='ok')
            return self.client.post('/api/v1/admin/invite/', payload, format='json')

    def test_invite_reviewer(self):
        r = self._invite('rev@example.com', 'reviewer')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['role'], 'reviewer')
        a = PartnerAdmin.objects.get(email='rev@example.com')
        self.assertEqual(a.role, 'reviewer')
        self.assertFalse(a.is_super_admin)

    def test_invite_viewer(self):
        self._invite('view@example.com', 'viewer')
        a = PartnerAdmin.objects.get(email='view@example.com')
        self.assertEqual(a.role, 'viewer')
        self.assertFalse(a.is_super_admin)

    def test_invite_super_sets_legacy_flag(self):
        self._invite('sup2@example.com', 'super')
        a = PartnerAdmin.objects.get(email='sup2@example.com')
        self.assertEqual(a.role, 'super')
        self.assertTrue(a.is_super_admin)  # legacy flag kept in lockstep

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
            supabase_user_id='v-uid', role='viewer', is_active=True,
            name='V', email='v@example.com',
        )
        r = self.client.get('/api/v1/admin/admins/')
        self.assertEqual(r.status_code, 200)
        roles = {a['email']: a['role'] for a in r.json()['admins']}
        self.assertEqual(roles['v@example.com'], 'viewer')
        self.assertEqual(roles['super@halatuju.com'], 'super')
