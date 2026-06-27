"""Wiring tests: the results-slip genuineness in the LIVE pipeline now comes from the
probabilistic signature scorer, and its 'suspect' band rides the same SOFT cap + officer flag.

Behaviour-changing step (results_slip only) — these pin the new behaviour; the relocation +
engine behaviour are covered by test_genuineness.py / test_doc_signatures.py.
"""
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship import vision
from apps.scholarship.verdict_engine import _apply_genuineness_caps
from apps.scholarship.anomaly_engine import detect_anomalies

GENUINE_SLIP = (
    "KEMENTERIAN PENDIDIKAN\nLEMBAGA PEPERIKSAAN\nSIJIL PELAJARAN MALAYSIA TAHUN 2025\n"
    "NO. PENGENALAN DIRI : 080101-10-1234\nANGKA GILIRAN : BA013A001\nSEKOLAH : SMK CONVENT\n"
    "JUMLAH MATA PELAJARAN : SEPULUH\nKOD NAMA MATA PELAJARAN GRED\n1103 BAHASA MELAYU A\n"
    "LAYAK MENDAPAT SIJIL\nUJIAN LISAN BAHASA MELAYU: CEMERLANG\n"
    "Slip keputusan ini bukan sijil/pernyataan.\nPENGARAH PEPERIKSAAN\n")
TYPED_FAKE = "Sijil Pelajaran Malaysia Tahun 2025\nElanjelian A/L Venugopal\n710829-02-5709\nBahasa Melayu A\n"
# A genuine slip whose OCR dropped the trailing lines (disclaimer + PENGARAH) — text-only it
# sits in 'review' (~0.60); crediting the visual QR + crest it actually has lifts it to genuine.
BORDERLINE_SLIP = (
    "KEMENTERIAN PENDIDIKAN\nLEMBAGA PEPERIKSAAN\nSIJIL PELAJARAN MALAYSIA TAHUN 2025\n"
    "NO. PENGENALAN DIRI : 080101-10-1234\nANGKA GILIRAN : BA013A001\nSEKOLAH : SMK CONVENT\n"
    "JUMLAH MATA PELAJARAN : SEPULUH\nKOD NAMA MATA PELAJARAN GRED\n1103 BAHASA MELAYU A\n"
    "LAYAK MENDAPAT SIJIL\nUJIAN LISAN BAHASA MELAYU: CEMERLANG\n")


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'sig-{self.id()}', name='SHANTHINI A/P RAJU', nric='080101-10-1234')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now())

    def _slip(self, auth):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='results_slip', storage_path=f'{self.app.id}/rs/x',
            vision_fields={'authenticity': auth})


class TestSuspectRidesSoftCapAndFlag(_Base):
    def test_suspect_caps_academic_to_review(self):
        self._slip({'status': 'suspect', 'probability': 0.04, 'reason': 'few signatures'})
        facts = _apply_genuineness_caps(self.app, [{'fact': 'academic', 'status': 'verified',
                                                    'evidence': [], 'unresolved': []}])
        self.assertEqual(facts[0]['status'], 'review')
        self.assertIn('document_not_genuine', [i['code'] for i in facts[0]['unresolved']])

    def test_suspect_never_upgrades_a_gap(self):
        self._slip({'status': 'suspect'})
        facts = _apply_genuineness_caps(self.app, [{'fact': 'academic', 'status': 'gap',
                                                    'evidence': [], 'unresolved': []}])
        self.assertEqual(facts[0]['status'], 'gap')      # soft: never fails on genuineness alone

    def test_suspect_fires_officer_flag(self):
        self._slip({'status': 'suspect', 'doc_seen': 'results_slip'})
        self.assertIn('document_not_genuine', [a['code'] for a in detect_anomalies(self.app)])

    def test_likely_genuine_no_cap_no_flag(self):
        self._slip({'status': 'likely_genuine', 'probability': 0.80})
        facts = _apply_genuineness_caps(self.app, [{'fact': 'academic', 'status': 'verified',
                                                    'evidence': [], 'unresolved': []}])
        self.assertEqual(facts[0]['status'], 'verified')
        self.assertNotIn('document_not_genuine', [a['code'] for a in detect_anomalies(self.app)])


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestResultsSlipUsesSignatureScorer(_Base):
    """run_field_extraction_for_document stores a SIGNATURE-derived authenticity for a slip."""

    def _run(self, ocr_text):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='results_slip', storage_path=f'{self.app.id}/rs/y')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': ocr_text, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            return vision.run_field_extraction_for_document(doc, names=[])

    def test_genuine_text_scores_genuine(self):
        auth = self._run(GENUINE_SLIP).get('authenticity')
        self.assertIsNotNone(auth)
        self.assertEqual(auth['status'], 'genuine')
        self.assertIn('probability', auth)

    def test_typed_fake_scores_not_type(self):
        # A typed reproduction scores <0.35 → not recognisably that document → not_<type>.
        auth = self._run(TYPED_FAKE).get('authenticity')
        self.assertTrue(auth['status'].startswith('not_'))

    def test_empty_ocr_gives_no_signal(self):
        # OCR failure is OUR failure → no authenticity, never a 'suspect' penalty.
        auth = self._run('').get('authenticity')
        self.assertIsNone(auth)


class TestVisualMarkers(TestCase):
    def test_maps_booleans(self):
        from apps.scholarship.genuineness.results_doc import results_visual_markers
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'has_qr_code': True, 'has_jata_negara_crest': False}):
            self.assertEqual(results_visual_markers(b'img', 'image/png'),
                             {'has_qr': True, 'has_crest': False})

    def test_ai_outage_empty(self):
        from apps.scholarship.genuineness.results_doc import results_visual_markers
        with patch('apps.scholarship.vision._call_gemini_json', return_value={'_error': 'down'}):
            self.assertEqual(results_visual_markers(b'img', 'image/png'), {})


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestVisualCreditLiftsBorderline(_Base):
    def _run(self, ocr_text, markers):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='results_slip', storage_path=f'{self.app.id}/rs/v')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             patch('apps.scholarship.vision._extract_slip_deterministic', return_value=(None, {'reason': 'x'})), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': ocr_text, 'error': None}), \
             patch('apps.scholarship.genuineness.results_doc.results_visual_markers', return_value=markers):
            return vision.run_field_extraction_for_document(doc, names=[]).get('authenticity')

    def test_borderline_is_suspect_without_visual_credit(self):
        auth = self._run(BORDERLINE_SLIP, {})            # no QR/crest credited
        self.assertEqual(auth['status'], 'suspect')

    def test_qr_and_crest_lift_borderline_to_genuine(self):
        auth = self._run(BORDERLINE_SLIP, {'has_qr': True, 'has_crest': True})
        self.assertEqual(auth['status'], 'genuine')


GENUINE_STPM_OFFER = (
    "SEKTOR OPERASI SEKOLAH\nTAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2026\n"
    "2.1 BIDANG : SAINS\n2.2 PUSAT TINGKATAN ENAM : SMK CONTOH\n2.3 TARIKH LAPOR DIRI : 08 JUN 2026\n"
    "2.5 DOKUMEN DIPERLUKAN\nKeputusan ini adalah muktamad berdasarkan syarat kemasukan ke tingkatan enam.\n"
    "Tawaran ini terbatal serta-merta jika murid berstatus bukan warganegara Malaysia.\n")
# A PRIVATE (IPTS) university — not one of the 20 UAs → unrecognised → holistic fallback.
UNIVERSITY_OFFER = "SWINBURNE UNIVERSITY OF TECHNOLOGY\nOFFER OF ADMISSION\nBachelor of Computer Science\n"


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestOfferLetterUsesSignatureScorer(_Base):
    """run_field_extraction_for_document scores the four standard offer issuers by signatures;
    an unrecognised issuer defers to the holistic read."""

    def _run(self, ocr_text):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/of/x')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': ocr_text, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            return vision.run_field_extraction_for_document(doc, names=[])

    def test_standard_issuer_scores_genuine_via_signatures(self):
        auth = self._run(GENUINE_STPM_OFFER).get('authenticity')
        self.assertIsNotNone(auth)
        self.assertEqual(auth['status'], 'genuine')
        self.assertEqual(auth['doc_seen'], 'stpm')

    def test_unrecognised_issuer_is_suspect_not_holistic(self):
        # Owner policy: a private/IPTS offer (not one of the supported public issuers) is NOT
        # holistic-rescued to genuine — it stays not-genuine ('unrecognised' surfaced as 'suspect')
        # so the pathway verdict + submission gate can act on it.
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/of/u')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': UNIVERSITY_OFFER, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            auth = vision.run_field_extraction_for_document(doc, names=[]).get('authenticity')
        self.assertEqual(auth['status'], 'suspect')

    def test_empty_ocr_no_image_gives_no_signal(self):
        auth = self._run('').get('authenticity')
        self.assertIsNone(auth)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestBcEpfUseSignatureScorer(_Base):
    """TD-122: birth_certificate + epf genuineness now comes from the signature scorer (not the
    holistic read); the EPF scorer doubles as the wrong-type backstop."""

    def _run(self, doc_type, ocr_text):
        from apps.scholarship.models import ApplicantDocument as _Doc
        doc = _Doc.objects.create(application=self.app, doc_type=doc_type,
                                  storage_path=f'{self.app.id}/{doc_type}/x')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': ocr_text, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            return vision.run_field_extraction_for_document(doc, names=[]).get('authenticity')

    def test_bc_scored_by_signatures(self):
        from apps.scholarship.tests.test_doc_signatures import GENUINE_BC
        auth = self._run('birth_certificate', GENUINE_BC)
        self.assertIsNotNone(auth)
        self.assertEqual(auth['doc_seen'], 'birth_certificate')
        self.assertIn('probability', auth)              # signature-derived, not holistic

    def test_epf_wrong_type_is_not_epf(self):
        from apps.scholarship.tests.test_doc_signatures import WRONG_TYPE_EPF
        auth = self._run('epf', WRONG_TYPE_EPF)
        self.assertTrue(auth['status'].startswith('not_'))   # wrong-type backstop (TD-117)


class TestFlagOffNoSignal(_Base):
    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_no_authenticity_when_flag_off(self):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='results_slip', storage_path=f'{self.app.id}/rs/z')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': GENUINE_SLIP, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            result = vision.run_field_extraction_for_document(doc, names=[])
        self.assertNotIn('authenticity', result)


GENUINE_STR_DASHBOARD = "Dashboard\nProfil\nStatus Permohonan STR\nLulus\nJumlah Telah Dibayar\nJumlah Bayaran Keseluruhan STR\n"
STR_SALINAN = "LHDN MALAYSIA\nSUMBANGAN TUNAI RAHMAH (STR)\nMAKLUMAT PEMOHON\nNo. MyKad\nSALINAN\n"


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestStrUsesSignatureScorer(_Base):
    """run_field_extraction_for_document scores the three STR approval forms by signatures;
    a SALINAN / SARA defers to the holistic read."""

    def test_dashboard_scores_genuine_via_signatures(self):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='str', storage_path=f'{self.app.id}/str/x')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': GENUINE_STR_DASHBOARD, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            auth = vision.run_field_extraction_for_document(doc, names=[]).get('authenticity')
        self.assertIsNotNone(auth)
        self.assertEqual(auth['status'], 'genuine')
        self.assertEqual(auth['doc_seen'], 'str_dashboard')

    def test_salinan_defers_to_holistic(self):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='str', storage_path=f'{self.app.id}/str/u')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': STR_SALINAN, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}), \
             patch('apps.scholarship.genuineness.doc_genuineness',
                   return_value={'status': 'genuine', 'doc_seen': 'MySTR screenshot', 'reason': 'real'}):
            auth = vision.run_field_extraction_for_document(doc, names=[]).get('authenticity')
        self.assertEqual(auth['status'], 'genuine')
        self.assertEqual(auth['doc_seen'], 'MySTR screenshot')
