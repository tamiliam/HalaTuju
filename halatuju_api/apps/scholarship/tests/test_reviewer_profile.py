"""Tests for the reviewer-profile API (F6, Phase E/F Sprint 5).

A reviewer edits their OWN credentials + contact profile via a self-scoped
endpoint. Reviewer + super only; a viewer (read-only staff) is denied. The
sensitive PII (phone/address) lives in its own table and is reachable by no
outward (student/sponsor) serializer.
"""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import ReviewerProfile

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReviewerProfile(TestCase):
    URL = '/api/v1/admin/reviewer-profile/'

    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='reviewer-uid', role='reviewer', is_active=True,
            name='Reviewer One', email='reviewer1@example.com',
        )
        cls.other = PartnerAdmin.objects.create(
            supabase_user_id='reviewer2-uid', role='reviewer', is_active=True,
            name='Reviewer Two', email='reviewer2@example.com',
        )
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id='viewer-uid', role='admin', is_active=True,
            name='Viewer', email='viewer@example.com',
        )
        cls.superadmin = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    # --- auth / role gating ---------------------------------------------------

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_non_admin_forbidden(self):
        self._auth('not-an-admin')
        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_viewer_forbidden(self):
        """A read-only viewer has no reviewer profile to edit."""
        self._auth('viewer-uid')
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.assertEqual(self.client.patch(self.URL, {'phone': '012'}, format='json').status_code, 403)
        self.assertFalse(ReviewerProfile.objects.filter(partner_admin=self.viewer).exists())

    def test_super_allowed(self):
        self._auth('super-uid')
        self.assertEqual(self.client.get(self.URL).status_code, 200)

    # --- GET get-or-create ----------------------------------------------------

    def test_get_creates_own_blank_profile(self):
        self._auth('reviewer-uid')
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['highest_qualification'], '')
        self.assertIsNone(r.json()['graduation_year'])
        self.assertTrue(ReviewerProfile.objects.filter(partner_admin=self.reviewer).exists())

    # --- PATCH self-edit ------------------------------------------------------

    def test_patch_updates_own(self):
        self._auth('reviewer-uid')
        payload = {
            'highest_qualification': 'PhD', 'university': 'Universiti Malaya',
            'graduation_year': 2015, 'field_of_study': 'Education',
            'phone': '012-345 6789', 'address': '1 Jalan Ilmu, KL',
        }
        r = self.client.patch(self.URL, payload, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['university'], 'Universiti Malaya')
        prof = ReviewerProfile.objects.get(partner_admin=self.reviewer)
        self.assertEqual(prof.phone, '012-345 6789')
        self.assertEqual(prof.graduation_year, 2015)

    def test_patch_language_fluency(self):
        self._auth('reviewer-uid')
        r = self.client.patch(self.URL, {
            'english_fluency': 'fluent', 'bm_fluency': 'conversational', 'tamil_fluency': '',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['english_fluency'], 'fluent')
        self.assertEqual(r.json()['bm_fluency'], 'conversational')
        prof = ReviewerProfile.objects.get(partner_admin=self.reviewer)
        self.assertEqual(prof.english_fluency, 'fluent')
        self.assertEqual(prof.tamil_fluency, '')

    def test_assignable_admins_includes_languages(self):
        # A reviewer's conversational+ languages surface on the assignment endpoint for matching.
        ReviewerProfile.objects.create(
            partner_admin=self.reviewer, english_fluency='fluent',
            tamil_fluency='conversational', bm_fluency='')
        self._auth('super-uid')
        r = self.client.get('/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        me = next(a for a in r.json()['admins'] if a['id'] == self.reviewer.id)
        self.assertEqual(sorted(me['languages']), ['en', 'ta'])   # bm omitted (None)
        other = next(a for a in r.json()['admins'] if a['id'] == self.other.id)
        self.assertEqual(other['languages'], [])                  # no profile → none

    def test_assignable_admins_only_reviewers_and_supers(self):
        # The dropdown must list only assignable roles (reviewer + super), never a
        # read-only 'admin', a 'partner', or a 'viewer' — mirrors services._can_review.
        partner = PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            name='Partner', email='partner@example.com')
        self._auth('super-uid')
        r = self.client.get('/api/v1/admin/scholarship/assignable-admins/')
        self.assertEqual(r.status_code, 200)
        ids = {a['id'] for a in r.json()['admins']}
        self.assertIn(self.reviewer.id, ids)        # reviewer ✓
        self.assertIn(self.superadmin.id, ids)      # super ✓
        self.assertNotIn(self.viewer.id, ids)       # role 'admin' (read-only) ✗
        self.assertNotIn(partner.id, ids)           # partner ✗

    def test_patch_structured_address(self):
        self._auth('reviewer-uid')
        r = self.client.patch(self.URL, {
            'street_address': '12 Jalan Ilmu', 'postcode': '50480',
            'city': 'Kuala Lumpur', 'state': 'W.P. Kuala Lumpur',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        prof = ReviewerProfile.objects.get(partner_admin=self.reviewer)
        self.assertEqual((prof.street_address, prof.postcode, prof.city, prof.state),
                         ('12 Jalan Ilmu', '50480', 'Kuala Lumpur', 'W.P. Kuala Lumpur'))

    def test_patch_is_partial(self):
        ReviewerProfile.objects.create(partner_admin=self.reviewer, phone='OLD', university='UM')
        self._auth('reviewer-uid')
        r = self.client.patch(self.URL, {'phone': 'NEW'}, format='json')
        self.assertEqual(r.status_code, 200)
        prof = ReviewerProfile.objects.get(partner_admin=self.reviewer)
        self.assertEqual(prof.phone, 'NEW')
        self.assertEqual(prof.university, 'UM')  # untouched

    def test_patch_rejects_implausible_year(self):
        self._auth('reviewer-uid')
        r = self.client.patch(self.URL, {'graduation_year': 1850}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_fk_is_not_writable(self):
        """A reviewer cannot reassign their profile to another admin via the payload."""
        self._auth('reviewer-uid')
        r = self.client.patch(self.URL, {'partner_admin': self.other.id, 'phone': 'x'},
                              format='json')
        self.assertEqual(r.status_code, 200)
        prof = ReviewerProfile.objects.get(phone='x')
        self.assertEqual(prof.partner_admin_id, self.reviewer.id)

    # --- isolation: one reviewer never touches another's row ------------------

    def test_self_scoped_isolation(self):
        ReviewerProfile.objects.create(partner_admin=self.other, phone='OTHER-PHONE')
        self._auth('reviewer-uid')
        # GET returns my (blank) row, never the other reviewer's
        r = self.client.get(self.URL)
        self.assertEqual(r.json()['phone'], '')
        # PATCH writes only my row; the other reviewer's PII is untouched
        self.client.patch(self.URL, {'phone': 'MINE'}, format='json')
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=self.other).phone, 'OTHER-PHONE')
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=self.reviewer).phone, 'MINE')
