"""Document genuineness fingerprint — verification-assurance Sprint 1 (IC).

The engine (`vision.ic_genuineness`) + its three soft surfaces: the Identity prediction
(caps at 'review', never auto-fails), the officer pre-interview flag, and the serializer
field that feeds the honest badge. Gemini seam is patched — never a live call.
"""
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship import vision
from apps.scholarship.verdict_engine import build_verdict
from apps.scholarship.anomaly_engine import detect_anomalies
from apps.scholarship.serializers import ApplicantDocumentSerializer


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'gen-{self.id()}', name='ELANJELIAN A/L VENUGOPAL',
            nric='710829-02-5709')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now())

    def _ic(self, auth=None):
        """A clean IC (name + NRIC match the profile) with an optional authenticity dict."""
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path=f'{self.app.id}/ic/x',
            vision_nric=self.profile.nric, vision_name=self.profile.name,
            vision_run_at=timezone.now(), vision_fields={'authenticity': auth} if auth else {})


class TestEngine(_Base):
    def test_suspect_maps_to_low_confidence(self):
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'suspect', 'has_face_photo': False,
                                 'has_chip': False, 'reason': 'typed text'}):
            r = vision.ic_genuineness(b'img', 'image/png')
        self.assertEqual(r['status'], 'low_confidence')
        self.assertFalse(r['markers']['has_face_photo'])
        self.assertEqual(r['reason'], 'typed text')

    def test_genuine_maps_to_likely_genuine(self):
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'genuine', 'has_face_photo': True}):
            self.assertEqual(vision.ic_genuineness(b'img', 'image/png')['status'], 'likely_genuine')

    def test_not_an_ic(self):
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'not_an_ic', 'reason': 'a shopping list'}):
            self.assertEqual(vision.ic_genuineness(b'img', 'image/png')['status'], 'not_an_ic')

    def test_ai_outage_returns_empty_no_signal(self):
        # We never penalise a student for OUR failure.
        with patch('apps.scholarship.vision._call_gemini_json', return_value={'_error': 'down'}):
            self.assertEqual(vision.ic_genuineness(b'img', 'image/png'), {})


class TestSurfaces(_Base):
    def test_low_confidence_caps_identity_at_review(self):
        # Name + NRIC match (would be 'verified'); a suspect card caps it at 'review'.
        self._ic(auth={'status': 'low_confidence', 'reason': 'no chip'})
        identity = next(f for f in build_verdict(self.app) if f['fact'] == 'identity')
        self.assertEqual(identity['status'], 'review')
        self.assertIn('ic_low_confidence', [i['code'] for i in identity['unresolved']])

    def test_not_an_ic_also_caps_but_never_fails(self):
        self._ic(auth={'status': 'not_an_ic'})
        identity = next(f for f in build_verdict(self.app) if f['fact'] == 'identity')
        self.assertEqual(identity['status'], 'review')      # never 'gap' on genuineness alone

    def test_likely_genuine_stays_verified(self):
        self._ic(auth={'status': 'likely_genuine'})
        identity = next(f for f in build_verdict(self.app) if f['fact'] == 'identity')
        self.assertEqual(identity['status'], 'verified')

    def test_absent_authenticity_unchanged(self):
        # Flag off / check didn't run → no authenticity → identity unaffected (verified).
        self._ic()
        identity = next(f for f in build_verdict(self.app) if f['fact'] == 'identity')
        self.assertEqual(identity['status'], 'verified')

    def test_officer_flag_fires_on_low_confidence(self):
        self._ic(auth={'status': 'low_confidence'})
        self.assertIn('ic_low_confidence', [a['code'] for a in detect_anomalies(self.app)])

    def test_no_officer_flag_when_genuine(self):
        self._ic(auth={'status': 'likely_genuine'})
        self.assertNotIn('ic_low_confidence', [a['code'] for a in detect_anomalies(self.app)])

    def test_serializer_exposes_authenticity(self):
        doc = self._ic(auth={'status': 'low_confidence', 'reason': 'typed'})
        self.assertEqual(ApplicantDocumentSerializer().get_authenticity(doc),
                         {'status': 'low_confidence', 'reason': 'typed'})

    def test_serializer_null_when_absent(self):
        self.assertIsNone(ApplicantDocumentSerializer().get_authenticity(self._ic()))
