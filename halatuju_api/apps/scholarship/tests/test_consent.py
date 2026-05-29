"""Tests for consent + minor/guardian gate (Sprint 5a)."""
import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import Consent, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import CONSENT_VERSION, age_from_nric, is_minor

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT = 'consent-adult'
MINOR = 'consent-minor'


def _token(uid, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


class TestAgeMinor(TestCase):
    def test_age_parses_valid_nric(self):
        self.assertIsInstance(age_from_nric('030101-14-1234'), int)

    def test_age_none_for_unparseable(self):
        self.assertIsNone(age_from_nric(''))
        self.assertIsNone(age_from_nric('xx'))

    def test_is_minor_distinguishes(self):
        self.assertFalse(is_minor(StudentProfile(nric='030101-14-1234')))  # 2003 -> adult
        self.assertTrue(is_minor(StudentProfile(nric='110101-14-1234')))   # 2011 -> minor
        self.assertFalse(is_minor(None))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestConsentApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.adult = StudentProfile.objects.create(supabase_user_id=ADULT, nric='030101-14-1234')
        cls.minor = StudentProfile.objects.create(supabase_user_id=MINOR, nric='110101-14-5678')
        cls.app_adult = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.adult, status='shortlisted',
        )
        cls.app_minor = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.minor, status='shortlisted',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_adult_self_consent(self):
        self._auth(ADULT)
        resp = self.client.post('/api/v1/scholarship/consent/', {'locale': 'en'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['version'], CONSENT_VERSION)
        self.assertEqual(resp.json()['granted_by'], 'self')

    def test_minor_requires_guardian(self):
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {'granted_by': 'self'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def _add_parent_ic_with_ocr(self, *, nric='700101-14-1234', name='Parent Name'):
        """S19 helper: parent_ic doc with Vision OCR fields populated so the
        view's hard-gate name+NRIC match has something to compare against."""
        from django.utils import timezone
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.create(
            application=self.app_minor, doc_type='parent_ic', storage_path='x/p',
            vision_nric=nric, vision_name=name,
            vision_run_at=timezone.now(), vision_error='',
        )

    def test_minor_with_guardian_ok(self):
        # S17/S19: parent_ic uploaded with OCR; typed name + NRIC must match.
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent Name',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['guardian_name'], 'Parent Name')
        self.assertEqual(resp.json()['guardian_nric'], '700101-14-1234')

    def test_minor_rejected_without_parent_ic(self):
        """S17: blocking 400 + error code so the FE can route the student back to step 4."""
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_required')

    def test_minor_non_parent_rejected_without_letter(self):
        """S17: grandparent/legal_guardian/etc. need the guardianship letter on top of the IC."""
        self._add_parent_ic_with_ocr(nric='500101-14-1234', name='Grandma')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Grandma',
            'guardian_relationship': 'grandparent',
            'guardian_nric': '500101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'guardianship_letter_required')

    def test_minor_non_parent_ok_with_letter(self):
        """Both docs uploaded + non-parent relationship → 201 accept."""
        from apps.scholarship.models import ApplicantDocument
        self._add_parent_ic_with_ocr(nric='500101-14-1234', name='Grandma')
        ApplicantDocument.objects.create(
            application=self.app_minor, doc_type='guardianship_letter', storage_path='x/l',
        )
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Grandma',
            'guardian_relationship': 'grandparent',
            'guardian_nric': '500101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['guardian_relationship'], 'grandparent')

    def test_invalid_relationship_rejected(self):
        """Free-text gibberish is rejected by the serializer (400 with field error)."""
        self._add_parent_ic_with_ocr()
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'X',
            'guardian_relationship': 'random-typed-text',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('guardian_relationship', resp.json())

    # ─── S19 hard-gate tests ───────────────────────────────────────────────

    def test_minor_rejected_when_typed_nric_mismatches_parent_ic(self):
        """S19: typed parent NRIC must match the parent_ic Vision OCR.
        Was a soft anomaly flag in S17; lawyers won't accept anyone being
        able to type a fake parent NRIC in someone else's session."""
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent Name',
            'guardian_relationship': 'mother',
            'guardian_nric': '710101-14-9999',  # wrong NRIC
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_nric_mismatch')

    def test_minor_rejected_when_typed_name_mismatches_parent_ic(self):
        """S19: typed parent name must match (token-set) the parent_ic Vision OCR."""
        self._add_parent_ic_with_ocr(nric='700101-14-1234', name='Real Parent Name')
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Totally Different Person',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_name_mismatch')

    def test_minor_rejected_when_guardian_nric_missing(self):
        """S19: guardian_nric is now required alongside name + relationship."""
        self._add_parent_ic_with_ocr()
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent',
            'guardian_relationship': 'mother',
            # guardian_nric omitted
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        # The first guardian-required check fires (combined error message).
        self.assertIn('error', resp.json())

    def test_nric_match_strips_hyphens(self):
        """S19: typed NRIC with hyphens must match Vision-OCR NRIC without
        hyphens (and vice versa) — comparison strips non-digits."""
        self._add_parent_ic_with_ocr(nric='700101141234', name='Parent Name')  # no hyphens
        self._auth(MINOR)
        resp = self.client.post('/api/v1/scholarship/consent/', {
            'granted_by': 'guardian', 'guardian_name': 'Parent Name',
            'guardian_relationship': 'mother',
            'guardian_nric': '700101-14-1234',  # with hyphens
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_consent_supersedes_prior(self):
        self._auth(ADULT)
        self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(
            Consent.objects.filter(application=self.app_adult, is_active=True).count(), 1,
        )
        self.assertEqual(Consent.objects.filter(application=self.app_adult).count(), 2)

    def test_get_consent_status_minor(self):
        self._auth(MINOR)
        resp = self.client.get('/api/v1/scholarship/consent/')
        self.assertEqual(resp.status_code, 200)
        # S19: GET surfaces student context + parent_ic OCR values so the FE
        # can render parent-voice text + run the live mismatch check in one fetch.
        body = resp.json()
        self.assertIn('student_name', body)
        self.assertIn('student_nric', body)
        self.assertIn('student_gender', body)
        self.assertIn('parent_ic_vision_nric', body)
        self.assertIn('parent_ic_vision_name', body)
        self.assertTrue(resp.json()['is_minor'])
        self.assertEqual(resp.json()['consent_version'], CONSENT_VERSION)

    def test_consent_requires_auth(self):
        resp = self.client.post('/api/v1/scholarship/consent/', {}, format='json')
        self.assertEqual(resp.status_code, 401)
