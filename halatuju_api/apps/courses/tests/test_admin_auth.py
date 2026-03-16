from django.test import TestCase
from apps.courses.models import PartnerOrganisation, PartnerAdmin, StudentProfile


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
