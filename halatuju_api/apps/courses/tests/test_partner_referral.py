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
