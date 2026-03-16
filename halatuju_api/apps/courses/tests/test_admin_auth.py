from django.test import TestCase
from apps.courses.models import PartnerOrganisation, PartnerAdmin


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
