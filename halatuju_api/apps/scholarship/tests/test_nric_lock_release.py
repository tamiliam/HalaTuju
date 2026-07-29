"""The IC-lock break-glass — super only, reason required (2026-07-29).

Why it exists, since the endpoint reads like an appeals process and is not one: somebody
uploads a card that is not theirs and types that card's details so the two agree, so it locks.
Their own results slip then fails the academic gate and the account is unusable, so it gets
abandoned — but it still holds a live claim on a REAL person's IC number. When the true owner
registers, uniqueness refuses them their own number, and nothing else in the product can free
it. This releases the claim.

The role boundary is the point of most of these tests: taking a lock is routine casework and
admits org_admin, qc and the assigned reviewer. Unsetting one does not.
"""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
NRIC = '080722-14-1140'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
                       'email': f'{uid}@x.com', 'is_anonymous': False},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestReleasingAnIcLock(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='rel-org', name='Rel')
        for uid, role, is_super in (('sup', 'super', True), ('oa', 'org_admin', False),
                                    ('qc', 'qc', False), ('adm', 'admin', False),
                                    ('rev', 'reviewer', False)):
            PartnerAdmin.objects.create(
                supabase_user_id=uid, role=role, is_super_admin=is_super, is_active=True,
                name=uid.upper(), email=f'{uid}@x.com', owning_organisation=cls.org,
            )
        cls.cohort = ScholarshipCohort.objects.create(
            code='c-rel', name='B40', year=2026, owning_organisation=cls.org)

    def setUp(self):
        self.client = APIClient()
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'rel-{self.id()}', name='THARANI A/P A.UDAYA KUMAR',
            nric=NRIC, nric_verified=True,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            owning_organisation=self.org,
        )

    def _post(self, uid, body):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/release-nric-lock/',
            body, format='json')

    def _locked(self):
        self.profile.refresh_from_db()
        return self.profile.nric_verified

    def test_a_super_releases_it(self):
        r = self._post('sup', {'reason': 'Card belongs to the applicant’s brother; freeing the '
                                         'number so its owner can register.'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(self._locked())

    def test_every_other_role_is_refused(self):
        """Deliberately narrower than verify-&-accept, which admits three of these four."""
        for uid in ('oa', 'qc', 'adm', 'rev'):
            with self.subTest(role=uid):
                r = self._post(uid, {'reason': 'let me in'})
                self.assertEqual(r.status_code, 403)
                self.assertTrue(self._locked(), 'a non-super released an identity lock')

    def test_a_reason_is_mandatory(self):
        for body in ({}, {'reason': ''}, {'reason': '   '}):
            with self.subTest(body=body):
                r = self._post('sup', body)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.json().get('code'), 'reason_required')
                self.assertTrue(self._locked())

    def test_releasing_an_unlocked_record_is_refused(self):
        """Not an error worth hiding: it means the caller is looking at the wrong record."""
        self.profile.nric_verified = False
        self.profile.save(update_fields=['nric_verified'])
        r = self._post('sup', {'reason': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('code'), 'not_locked')

    def test_it_frees_the_number_for_its_real_owner(self):
        """The whole point. While the claim stands, the true owner cannot verify their own
        number — the partial unique index refuses the second verified holder."""
        owner = StudentProfile.objects.create(
            supabase_user_id='real-owner', name='SOMEONE ELSE', nric=NRIC, nric_verified=False)
        self._post('sup', {'reason': 'orphaned claim'})
        owner.nric_verified = True
        owner.save(update_fields=['nric_verified'])       # must not raise now
        owner.refresh_from_db()
        self.assertTrue(owner.nric_verified)

    def test_it_does_not_blank_the_number_or_touch_the_application(self):
        """Release the CLAIM, change nothing else — this is housekeeping, not a reopening."""
        self._post('sup', {'reason': 'orphaned claim'})
        self.profile.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.profile.nric, NRIC)
        self.assertEqual(self.app.status, 'shortlisted')
