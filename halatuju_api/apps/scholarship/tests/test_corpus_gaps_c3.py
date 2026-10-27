"""Corpus-gaps C3 (MODEL_VERSION 1.9.0): the STPM results family (Majlis Peperiksaan Malaysia), slip
and certificate, beside the untouched SPM pair — in the results slot and the semester-result slot.

The documents below are SYNTHETIC, built from the fixed printed wording of ten real STPM documents
(PII-free, roadmap C0): no name, NRIC, index number, subject or grade of any candidate. The real OCR
texts were checked by hand against the same scorer (every slip and certificate genuine; the online
results-checker page not a results document; all 96 cached SPM documents unchanged) — they are
gitignored PII and never collected here.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import misfiled_as, signature_genuineness
from apps.scholarship.genuineness.bands import band_for
from apps.scholarship.genuineness.results_doc import (CERT_SIGNATURES, MODEL_VERSION, SLIP_SIGNATURES,
                                                      _VISUAL_PROMPT, _norm_fold_upper_alnum, _score_list)
from apps.scholarship.genuineness.stpm_doc import STPM_TYPES, stpm_semester_genuineness
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests import test_doc_signatures as spm
from apps.scholarship.tests import test_signature_genuineness_wiring as wiring
from apps.scholarship.tests.factories import make_application

STPM_SLIP = """MPM
MAJLIS PEPERIKSAAN MALAYSIA
SIJIL TINGGI PERSEKOLAHAN MALAYSIA (STPM)
Slip Keputusan Peperiksaan STPM 2025
Nama : No. Kad Pengenalan : Angka Giliran : No. Siri :
Bil. Mata Pelajaran Didaftarkan :
Purata Nilai Gred Keseluruhan (PNGK) :
KOD MATA PELAJARAN WAJARAN (%) GRED KERTAS GRED MATA PELAJARAN NILAI GRED MATA PELAJARAN
Nota: Keputusan gred kertas yang dicatatkan ialah keputusan yang terbaik.
Ketua Eksekutif
Majlis Peperiksaan Malaysia
Tarikh Keputusan Dikeluarkan :
Nota Penting:
1. Slip keputusan ini bukan sijil STPM. Keputusan muktamad adalah seperti yang tercatat dalam sijil.
2. Pencapaian gred kertas diberikan gred A hingga F. Lulus sebahagian diberikan gred C- hingga D.
"""
STPM_CERTIFICATE = """MPM
MAJLIS PEPERIKSAAN MALAYSIA (MALAYSIAN EXAMINATIONS COUNCIL)
SIJIL TINGGI PERSEKOLAHAN MALAYSIA (MALAYSIA HIGHER SCHOOL CERTIFICATE)
Dengan ini disahkan bahawa (This is to certify that)
No. Kad Pengenalan (Identity Card No.)
telah menduduki peperiksaan (sat for the)
seperti yang tercatat bagi mata pelajaran yang ditunjukkan di bawah: (for the subjects shown below:)
Angka Giliran: (Index No.) Tahun Peperiksaan: (Year of Examination)
Mata Pelajaran (Subject) Gred (Grade) Nilai Gred (Grade Point)
(LULUS PENUH) (FULL PASS)
Bilangan Mata Pelajaran Lulus: (Number of Subjects Passed)
Purata Nilai Gred Keseluruhan: (Cumulative Grade Point Average)
Pengerusi (Chairman) Ketua Eksekutif (Chief Executive)
Tarikh keputusan diumumkan: (Results released on)
"""
# Owner ruling 2A: a CERTIFIED photocopy — the certificate's text, a "Salinan Disahkan Benar" stamp,
# no crest showing. Accepted: it scores like the certificate.
CERTIFIED_COPY = 'SALINAN DISAHKAN BENAR\nPejabat Pendidikan Daerah\n' + STPM_CERTIFICATE
# Owner ruling 1A: a screenshot / print of the ONLINE results-checker page — no issuer, no signature,
# no disclaimer. Not a result document.
ONLINE_CHECKER_PAGE = """MAKLUMAT CALON
NAMA PENUH
NOMBOR KAD PENGENALAN
TAHUN STPM
MATA PELAJARAN GRED NILAI GRED
BACK MUAT TURUN/CETAK
"""
# A university semester slip in the semester-result slot: no STPM issuer — stays unscored.
UNIVERSITY_SEMESTER_SLIP = """UNIVERSITI MALAYSIA SABAH
KEPUTUSAN PEPERIKSAAN SEMESTER 1 SESI 2025/2026
Nama : No. Matrik :
PNGS : PNGK :
"""


def _spm_only(text, qr=False, crest=False):
    """The 1.8.2 results scorer — the SPM pair only, banded — so "SPM unchanged" is a diff."""
    tn = _norm_fold_upper_alnum(text)
    scores = {k: _score_list(v, tn, qr, crest) for k, v in (('results_slip', SLIP_SIGNATURES),
                                                           ('certificate', CERT_SIGNATURES))}
    best = max(scores, key=lambda k: scores[k]['probability'])
    status = band_for(scores[best]['probability'])
    return ('not_' + best if status == 'not_type' else status), best, scores[best]['probability']


class TheSTPMFamily(TestCase):

    def test_an_stpm_slip_is_a_genuine_stpm_slip(self):
        self.assertEqual(_spm_only(STPM_SLIP)[0], 'not_results_slip')            # what 1.8.2 said
        g = signature_genuineness(STPM_SLIP)
        self.assertEqual((g['status'], g['type'], g['model_version']), ('genuine', 'stpm_slip', MODEL_VERSION))
        # The full fixed wording finds every signature — the forge-hard disclaimer among them.
        self.assertEqual(g['probability'], 1.0)
        self.assertIn('disclaimer (bukan sijil STPM)', g['present'])

    def test_the_spm_lists_come_first_so_a_tie_goes_to_spm(self):
        from apps.scholarship.genuineness.results_doc import _RESULTS_LISTS
        self.assertEqual(list(_RESULTS_LISTS)[:2], ['results_slip', 'certificate'])
        self.assertEqual(set(_RESULTS_LISTS) - {'results_slip', 'certificate'}, set(STPM_TYPES))

    def test_an_stpm_certificate_is_genuine_without_the_crest_and_with_it(self):
        for crest in (False, True):
            with self.subTest(crest=crest):
                g = signature_genuineness(STPM_CERTIFICATE, has_crest=crest)
                self.assertEqual((g['status'], g['type']), ('genuine', 'stpm_certificate'))

    def test_ruling_2a_a_certified_photocopy_scores_like_the_certificate(self):
        g = signature_genuineness(CERTIFIED_COPY)
        self.assertEqual((g['status'], g['type']), ('genuine', 'stpm_certificate'))
        self.assertEqual(g['probability'], signature_genuineness(STPM_CERTIFICATE)['probability'])

    def test_ruling_1a_the_online_checker_page_is_not_a_results_document(self):
        for qr, crest in ((False, False), (True, True)):
            with self.subTest(visuals=(qr, crest)):
                g = signature_genuineness(ONLINE_CHECKER_PAGE, has_qr=qr, has_crest=crest)
                self.assertTrue(g['status'].startswith('not_'), g)

    def test_every_spm_document_scores_exactly_as_before(self):
        for name in ('GENUINE_SLIP', 'GENUINE_CERT', 'CROPPED_SLIP', 'TYPED_FAKE'):
            text = getattr(spm, name)
            for qr, crest in ((False, False), (True, True), (True, False), (False, True)):
                with self.subTest(fixture=name, visuals=(qr, crest)):
                    g = signature_genuineness(text, has_qr=qr, has_crest=crest)
                    self.assertEqual((g['status'], g['type'], g['probability']), _spm_only(text, qr, crest))
        for text in (wiring.GENUINE_SLIP, wiring.TYPED_FAKE, wiring.BORDERLINE_SLIP):
            with self.subTest(text=text[:20]):
                g = signature_genuineness(text)
                self.assertEqual((g['status'], g['type'], g['probability']), _spm_only(text))

    def test_an_stpm_document_in_the_school_leaving_slot_is_a_misfile(self):
        self.assertEqual(misfiled_as('school_leaving_cert', STPM_SLIP)['doc_seen'], 'stpm_slip')

    def test_the_picture_check_asks_about_spm_or_stpm(self):
        self.assertIn('SPM or STPM', _VISUAL_PROMPT)

    def test_the_stpm_types_are_results_types(self):
        from apps.scholarship.genuineness import assess
        self.assertEqual(STPM_TYPES, {'stpm_slip', 'stpm_certificate'})
        for t in STPM_TYPES:
            self.assertEqual(assess(t, ocr_text=STPM_SLIP)['type'], 'stpm_slip')

    def test_the_model_version(self):
        self.assertGreaterEqual(tuple(map(int, MODEL_VERSION.split('.'))), (1, 11, 0))   # C3 1.9.0; S2 1.10.0; S3


class TheSemesterResultSlot(TestCase):

    def test_an_stpm_slip_in_the_semester_slot_is_scored_as_stpm(self):
        g = stpm_semester_genuineness(STPM_SLIP)
        self.assertEqual((g['status'], g['type']), ('genuine', 'stpm_slip'))

    def test_anything_else_in_the_semester_slot_stays_unscored(self):
        for text in (UNIVERSITY_SEMESTER_SLIP, ONLINE_CHECKER_PAGE, spm.GENUINE_SLIP):
            with self.subTest(text=text[:20]):
                self.assertEqual(stpm_semester_genuineness(text), {})


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TheDoors(TestCase):

    def setUp(self):
        self.app = make_application('profile_complete')

    def _results_upload(self, text, markers=None):
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='results_slip',
                                               storage_path=f'{self.app.id}/rs/x')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             patch('apps.scholarship.vision._extract_slip_deterministic', return_value=(None, {'reason': 'x'})), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': text, 'error': None}), \
             patch('apps.scholarship.genuineness.results_doc.results_visual_markers', return_value=markers or {}):
            doc.vision_fields = vision.run_field_extraction_for_document(doc, names=[])
        doc.save(update_fields=['vision_fields'])
        return doc

    def test_an_uploaded_stpm_slip_is_stored_genuine_stpm(self):
        auth = self._results_upload(STPM_SLIP).vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen'], auth['model_version']),
                         ('genuine', 'stpm_slip', MODEL_VERSION))

    def test_a_genuine_stpm_document_costs_the_academic_card_no_band(self):
        from apps.scholarship.verdict_engine import _apply_genuineness_ladder
        self._results_upload(STPM_CERTIFICATE)
        facts = _apply_genuineness_ladder(self.app, [{'fact': 'academic', 'status': 'verified',
                                                      'evidence': [], 'unresolved': []}])
        self.assertEqual(facts[0]['status'], 'verified')
        self.assertNotIn('document_not_genuine', [i['code'] for i in facts[0]['unresolved']])

    def test_the_online_checker_page_is_stored_as_not_a_results_document(self):
        from apps.scholarship.verdict_engine import _apply_genuineness_ladder
        auth = self._results_upload(ONLINE_CHECKER_PAGE).vision_fields['authenticity']
        self.assertTrue(auth['status'].startswith('not_'))
        facts = _apply_genuineness_ladder(self.app, [{'fact': 'academic', 'status': 'verified',
                                                      'evidence': [], 'unresolved': []}])
        self.assertIn('document_not_genuine', [i['code'] for i in facts[0]['unresolved']])

    def _semester_upload(self, text):
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='semester_result',
                                               storage_path=f'{self.app.id}/sr/x')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': text, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            return vision.run_field_extraction_for_document(doc, names=[])

    def test_the_semester_slot_scores_an_stpm_slip_and_leaves_a_university_slip_alone(self):
        self.assertEqual(self._semester_upload(STPM_SLIP)['authenticity']['doc_seen'], 'stpm_slip')
        self.assertNotIn('authenticity', self._semester_upload(UNIVERSITY_SEMESTER_SLIP))
