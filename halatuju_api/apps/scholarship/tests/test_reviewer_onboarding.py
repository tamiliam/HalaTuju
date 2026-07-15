"""Reviewer-profile onboarding gate (2026-07-15).

`reviewer_profile_complete` decides whether a reviewer is held on /admin/profile at first login.
The compulsory set is credentials (qualification, university, graduation year, field of study) +
at least one spoken language + phone + the PartnerAdmin name. It is surfaced on GET
/api/v1/admin/role/ (the landing + layout guard branch on it). Reviewer-only.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import ReviewerProfile
from apps.scholarship.reviewer_onboarding import reviewer_profile_complete

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _fill(rp, **over):
    """A fully-complete reviewer profile; override individual fields to make it incomplete."""
    rp.highest_qualification = over.get('highest_qualification', 'Degree')
    rp.university = over.get('university', 'UM')
    rp.field_of_study = over.get('field_of_study', 'Engineering')
    rp.graduation_year = over.get('graduation_year', 2015)
    rp.english_fluency = over.get('english_fluency', 'fluent')
    rp.bm_fluency = over.get('bm_fluency', '')
    rp.tamil_fluency = over.get('tamil_fluency', '')
    rp.phone = over.get('phone', '+60123456789')
    rp.save()
    return rp


class TestReviewerProfileComplete(TestCase):
    def setUp(self):
        self.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev', role='reviewer', is_active=True,
            name='Kaneswaran', email='rev@x.com')

    def _rp(self):
        rp, _ = ReviewerProfile.objects.get_or_create(partner_admin=self.reviewer)
        return rp

    def test_non_reviewer_always_complete(self):
        for role, sup in (('admin', False), ('qc', False), ('viewer', False),
                          ('partner', False), (None, True)):
            a = PartnerAdmin.objects.create(
                supabase_user_id=f'u-{role}-{sup}', role=(role or 'admin'),
                is_super_admin=sup, is_active=True, name='X', email=f'{role}{sup}@x.com')
            self.assertTrue(reviewer_profile_complete(a), role)

    def test_reviewer_with_no_profile_row_is_incomplete(self):
        self.assertFalse(reviewer_profile_complete(self.reviewer))

    def test_fully_filled_is_complete(self):
        _fill(self._rp())
        self.assertTrue(reviewer_profile_complete(self.reviewer))

    def test_blank_name_is_incomplete(self):
        _fill(self._rp())
        self.reviewer.name = ''
        self.reviewer.save()
        self.assertFalse(reviewer_profile_complete(self.reviewer))

    def test_each_missing_credential_is_incomplete(self):
        for field in ('highest_qualification', 'university', 'field_of_study', 'phone'):
            _fill(self._rp(), **{field: ''})
            self.assertFalse(reviewer_profile_complete(self.reviewer), field)

    def test_missing_graduation_year_is_incomplete(self):
        _fill(self._rp(), graduation_year=None)
        self.assertFalse(reviewer_profile_complete(self.reviewer))

    def test_no_spoken_language_is_incomplete(self):
        # All three unset ('' = "None") → no language to review in.
        _fill(self._rp(), english_fluency='', bm_fluency='', tamil_fluency='')
        self.assertFalse(reviewer_profile_complete(self.reviewer))

    def test_one_conversational_language_is_enough(self):
        _fill(self._rp(), english_fluency='', bm_fluency='conversational', tamil_fluency='')
        self.assertTrue(reviewer_profile_complete(self.reviewer))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestRoleEndpointExposesFlag(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _get_role(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return self.client.get('/api/v1/admin/role/')

    def test_incomplete_reviewer_flag_false(self):
        PartnerAdmin.objects.create(
            supabase_user_id='rev1', role='reviewer', is_active=True, name='R', email='r1@x.com')
        r = self._get_role('rev1')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['reviewer_profile_complete'])

    def test_complete_reviewer_flag_true(self):
        rev = PartnerAdmin.objects.create(
            supabase_user_id='rev2', role='reviewer', is_active=True, name='R', email='r2@x.com')
        _fill(ReviewerProfile.objects.create(partner_admin=rev))
        self.assertTrue(self._get_role('rev2').json()['reviewer_profile_complete'])

    def test_super_flag_true(self):
        PartnerAdmin.objects.create(
            supabase_user_id='sup', is_super_admin=True, is_active=True, name='S', email='s@x.com')
        self.assertTrue(self._get_role('sup').json()['reviewer_profile_complete'])
