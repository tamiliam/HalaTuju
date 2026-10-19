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
    """A `?ref=` code resolves to a REFERRAL PARTNER only (two columns, decisions.md 2026-10-09).

    Rewritten from the old rule — "link ANY active row with that code" — which the
    sources-and-referrals Sprint A replaced: a source or any other organisation row is no longer
    linked by a `?ref=` code, and the bursary answer lives on each application (sources Sprint C;
    Sprint D removed the profile's `source` column). The full matrix is
    `apps/scholarship/tests/test_two_referral_columns.py`."""

    def setUp(self):
        self.partner = PartnerOrganisation.objects.create(
            code='cumig', name='CUMIG', is_referral_partner=True)

    def _ref(self, uid, code):
        from apps.courses.referral_links import apply_ref_code
        profile = StudentProfile.objects.create(supabase_user_id=uid)
        apply_ref_code(profile, code)
        profile.refresh_from_db()
        return profile

    def test_referral_resolves_to_partner(self):
        """A referral partner's code sets referred_by_org and the chip (the code itself)."""
        profile = self._ref('resolve-1', 'cumig')
        self.assertEqual(profile.referred_by_org, self.partner)
        self.assertEqual(profile.referral_source, 'cumig')

    def test_referral_generic_no_partner(self):
        """A code with no row leaves referred_by_org null."""
        self.assertIsNone(self._ref('resolve-2', 'whatsapp').referred_by_org)

    def test_an_organisation_that_is_not_a_referral_partner_is_not_linked(self):
        """The old rule linked any active row; a source is no longer linked by a `?ref=` code."""
        PartnerOrganisation.objects.create(code='smc', name='SMC')
        self.assertIsNone(self._ref('resolve-4', 'smc').referred_by_org)

    def test_referral_inactive_partner_ignored(self):
        """Inactive partners are not resolved."""
        self.partner.is_active = False
        self.partner.save()
        self.assertIsNone(self._ref('resolve-3', 'cumig').referred_by_org)


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
