from django.test import TestCase
from apps.courses.models import PartnerOrganisation, StudentProfile


class PartnerOrganisationModelTest(TestCase):
    def test_create_partner(self):
        partner = PartnerOrganisation.objects.create(
            code='cumig',
            name='CUMIG',
            contact_email='admin@cumig.org',
        )
        self.assertEqual(partner.code, 'cumig')
        self.assertEqual(str(partner), 'CUMIG (cumig)')
        self.assertTrue(partner.is_active)

    def test_code_unique(self):
        PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        with self.assertRaises(Exception):
            PartnerOrganisation.objects.create(code='cumig', name='CUMIG 2')


class StudentProfileReferralTest(TestCase):
    def test_referral_fields_nullable(self):
        profile = StudentProfile.objects.create(supabase_user_id='test-user-1')
        self.assertIsNone(profile.referral_source)
        self.assertIsNone(profile.referred_by_org)

    def test_referral_with_partner(self):
        partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        profile = StudentProfile.objects.create(
            supabase_user_id='test-user-2',
            referral_source='cumig',
            referred_by_org=partner,
        )
        self.assertEqual(profile.referral_source, 'cumig')
        self.assertEqual(profile.referred_by_org.code, 'cumig')

    def test_referral_without_partner(self):
        profile = StudentProfile.objects.create(
            supabase_user_id='test-user-3',
            referral_source='whatsapp',
        )
        self.assertEqual(profile.referral_source, 'whatsapp')
        self.assertIsNone(profile.referred_by_org)


class ReferralResolutionTest(TestCase):
    """Test that referral_source resolves to partner org."""

    def setUp(self):
        self.partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')

    def test_referral_resolves_to_partner(self):
        """When referral_source matches a partner code, referred_by_org is set."""
        profile = StudentProfile.objects.create(
            supabase_user_id='resolve-1',
            referral_source='cumig',
        )
        # Simulate what the view should do
        from apps.courses.models import PartnerOrganisation as PO
        try:
            org = PO.objects.get(code=profile.referral_source, is_active=True)
            profile.referred_by_org = org
            profile.save(update_fields=['referred_by_org'])
        except PO.DoesNotExist:
            pass
        profile.refresh_from_db()
        self.assertEqual(profile.referred_by_org, self.partner)

    def test_referral_generic_no_partner(self):
        """When referral_source doesn't match any partner, referred_by_org stays null."""
        profile = StudentProfile.objects.create(
            supabase_user_id='resolve-2',
            referral_source='whatsapp',
        )
        from apps.courses.models import PartnerOrganisation as PO
        try:
            org = PO.objects.get(code=profile.referral_source, is_active=True)
            profile.referred_by_org = org
            profile.save(update_fields=['referred_by_org'])
        except PO.DoesNotExist:
            pass
        profile.refresh_from_db()
        self.assertIsNone(profile.referred_by_org)

    def test_referral_inactive_partner_ignored(self):
        """Inactive partners are not resolved."""
        self.partner.is_active = False
        self.partner.save()
        profile = StudentProfile.objects.create(
            supabase_user_id='resolve-3',
            referral_source='cumig',
        )
        from apps.courses.models import PartnerOrganisation as PO
        try:
            org = PO.objects.get(code=profile.referral_source, is_active=True)
            profile.referred_by_org = org
            profile.save(update_fields=['referred_by_org'])
        except PO.DoesNotExist:
            pass
        profile.refresh_from_db()
        self.assertIsNone(profile.referred_by_org)


class PartnerAdminModelTest(TestCase):
    def setUp(self):
        self.partner = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        for i in range(3):
            StudentProfile.objects.create(
                supabase_user_id=f'student-{i}',
                name=f'Student {i}',
                nric=f'01010{i}-01-000{i}',
                exam_type='spm' if i < 2 else 'stpm',
                referral_source='cumig',
                referred_by_org=self.partner,
            )
        StudentProfile.objects.create(
            supabase_user_id='student-other',
            name='Other Student',
            referral_source='whatsapp',
        )

    def test_partner_students_count(self):
        students = StudentProfile.objects.filter(referred_by_org=self.partner)
        self.assertEqual(students.count(), 3)

    def test_other_student_not_included(self):
        students = StudentProfile.objects.filter(referred_by_org=self.partner)
        user_ids = list(students.values_list('supabase_user_id', flat=True))
        self.assertNotIn('student-other', user_ids)

    def test_views_exist(self):
        from apps.courses.views_admin import (
            PartnerDashboardView, PartnerStudentListView,
            PartnerStudentDetailView, PartnerStudentExportView,
        )
        self.assertTrue(hasattr(PartnerDashboardView, 'get'))
        self.assertTrue(hasattr(PartnerStudentListView, 'get'))
        self.assertTrue(hasattr(PartnerStudentDetailView, 'get'))
        self.assertTrue(hasattr(PartnerStudentExportView, 'get'))
