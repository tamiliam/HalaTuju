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
        self.assertEqual(r['status'], 'suspect')
        self.assertFalse(r['markers']['has_face_photo'])
        self.assertEqual(r['reason'], 'typed text')

    def test_genuine_maps_to_likely_genuine(self):
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'genuine', 'has_face_photo': True}):
            self.assertEqual(vision.ic_genuineness(b'img', 'image/png')['status'], 'genuine')

    def test_not_an_ic(self):
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'not_an_ic', 'reason': 'a shopping list'}):
            self.assertEqual(vision.ic_genuineness(b'img', 'image/png')['status'], 'not_ic')

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
        doc = self._ic(auth={'status': 'low_confidence', 'reason': 'typed'})   # legacy stored value
        self.assertEqual(ApplicantDocumentSerializer().get_authenticity(doc),
                         {'status': 'suspect', 'reason': 'typed', 'doc_seen': ''})   # → canonical

    def test_serializer_null_when_absent(self):
        self.assertIsNone(ApplicantDocumentSerializer().get_authenticity(self._ic()))


class TestSupportingDocGenuineness(_Base):
    """Sprint 2 — genuineness + wrong-type for the standardised supporting documents."""

    def _doc(self, doc_type, auth=None):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'{self.app.id}/{doc_type}/x',
            vision_fields={'authenticity': auth} if auth else {})

    def test_engine_maps_verdicts(self):
        for verdict, status in {'genuine': 'genuine', 'suspect': 'suspect',
                                'wrong_type': 'not_str'}.items():
            with patch('apps.scholarship.vision._call_gemini_json',
                       return_value={'verdict': verdict, 'is_official': verdict == 'genuine',
                                     'is_expected_type': verdict != 'wrong_type', 'doc_seen': 'X', 'reason': 'r'}):
                self.assertEqual(vision.doc_genuineness(b'img', 'image/png', 'str')['status'], status)

    def test_engine_unsupported_type_empty(self):
        self.assertEqual(vision.doc_genuineness(b'img', 'image/png', 'photo'), {})

    def test_engine_ai_outage_empty(self):
        with patch('apps.scholarship.vision._call_gemini_json', return_value={'_error': 'down'}):
            self.assertEqual(vision.doc_genuineness(b'img', 'image/png', 'str'), {})

    def test_officer_flag_on_wrong_type(self):
        self._doc('str', auth={'status': 'wrong_type', 'doc_seen': 'an identity card'})
        flags = {a['code']: a for a in detect_anomalies(self.app)}
        self.assertIn('document_not_genuine', flags)
        self.assertEqual(flags['document_not_genuine']['params']['doc'], 'STR')

    def test_officer_flag_on_low_confidence(self):
        self._doc('birth_certificate', auth={'status': 'low_confidence', 'doc_seen': 'typed text'})
        self.assertIn('document_not_genuine', [a['code'] for a in detect_anomalies(self.app)])

    def test_no_flag_when_genuine(self):
        self._doc('epf', auth={'status': 'likely_genuine'})
        self.assertNotIn('document_not_genuine', [a['code'] for a in detect_anomalies(self.app)])

    def test_serializer_for_supporting_doc(self):
        doc = self._doc('birth_certificate',
                        auth={'status': 'low_confidence', 'reason': 'typed', 'doc_seen': 'typed text'})
        self.assertEqual(ApplicantDocumentSerializer().get_authenticity(doc),
                         {'status': 'suspect', 'reason': 'typed', 'doc_seen': 'typed text'})


class TestVerdictCaps(_Base):
    """Sprint 2 — a suspect/wrong-type supporting doc lowers its fact (soft), never upgrades.
    Income caps are ROUTE-AWARE: only the docs REQUIRED to prove income on the route can cap it
    (the STR on the STR route), so an optional EPF/salary slip never pulls the verdict down."""

    def setUp(self):
        super().setUp()
        self.app.income_route = 'str'          # STR route, father earner → STR is the proof
        self.app.income_earner = 'father'
        self.app.save(update_fields=['income_route', 'income_earner'])

    def _doc(self, doc_type, auth):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'{self.app.id}/{doc_type}/x',
            vision_fields={'authenticity': auth})

    def test_cap_appends_caveat_to_income(self):
        self._doc('str', {'status': 'wrong_type'})
        income = next(f for f in build_verdict(self.app) if f['fact'] == 'income')
        self.assertIn('document_not_genuine', [i['code'] for i in income['unresolved']])

    def test_optional_epf_does_not_cap_income(self):
        # #72: a future-dated/typed EPF is OPTIONAL on the STR route — it must NOT pull income
        # down (the STR is the proof). The suspicion still raises the officer flag elsewhere.
        self._doc('str', {'status': 'likely_genuine'})
        self._doc('epf', {'status': 'low_confidence'})
        income = next(f for f in build_verdict(self.app) if f['fact'] == 'income')
        self.assertNotIn('document_not_genuine', [i['code'] for i in income['unresolved']])

    def test_optional_bc_does_not_cap_income_for_father_earner(self):
        # A birth certificate isn't required when the earner is the father (patronymic proof) →
        # its genuineness must not cap income.
        self._doc('birth_certificate', {'status': 'low_confidence'})
        income = next(f for f in build_verdict(self.app) if f['fact'] == 'income')
        self.assertNotIn('document_not_genuine', [i['code'] for i in income['unresolved']])

    def test_cap_downgrades_verified_to_review(self):
        from apps.scholarship.verdict_engine import _apply_genuineness_caps
        self._doc('results_slip', {'status': 'low_confidence'})
        facts = _apply_genuineness_caps(self.app, [{'fact': 'academic', 'status': 'verified',
                                                    'evidence': [], 'unresolved': []}])
        self.assertEqual(facts[0]['status'], 'review')
        self.assertIn('document_not_genuine', [i['code'] for i in facts[0]['unresolved']])

    def test_cap_never_upgrades_a_gap(self):
        from apps.scholarship.verdict_engine import _apply_genuineness_caps
        self._doc('str', {'status': 'wrong_type'})
        facts = _apply_genuineness_caps(self.app, [{'fact': 'income', 'status': 'gap',
                                                    'evidence': [], 'unresolved': []}])
        self.assertEqual(facts[0]['status'], 'gap')

    def test_genuine_doc_no_cap(self):
        self._doc('epf', {'status': 'likely_genuine'})
        income = next(f for f in build_verdict(self.app) if f['fact'] == 'income')
        self.assertNotIn('document_not_genuine', [i['code'] for i in income['unresolved']])
