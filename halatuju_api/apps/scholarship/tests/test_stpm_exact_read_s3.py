"""STPM exact-read S3 (MODEL_VERSION 1.11.0): STPM documents in the HIGHER-RESULTS slot get a real
genuineness check instead of the blanket "not checked", and owner ruling 1A applies there.

Owner rulings (2026-10-27): the certificate and the slip are judged the same way; the online
results-CHECKER page (its own heading / buttons) is NOT a results document (1A) — the student is
asked for the real slip or certificate; a printout of the MPM results web page is a slip in any form
(saved PDF, scan, photo, certified copy — ruling A); a certified copy (2A) is accepted;
Matriculation / Asasi / Diploma documents stay "not checked".

Every text below is SYNTHETIC — fixed printed wording only (no name, NRIC, index number or grade
of any candidate). The real corpus is measured by `eval/stpm_genuineness_check.py` (gitignored PII).
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness.results_doc import MODEL_VERSION
from apps.scholarship.genuineness.stpm_doc import (ONLINE_PAGE, is_checker_page, stpm_higher_genuineness,
                                                   stpm_slot_genuineness)
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.test_corpus_gaps_c3 import (CERTIFIED_COPY, ONLINE_CHECKER_PAGE, STPM_CERTIFICATE,
                                                        STPM_SLIP)
from apps.scholarship.tests.test_third_route_s3 import (DEGREE, MATRIC_HELD, MATRIC_PATHWAY, SPM_HELD, STPM_HELD,
                                                        STPM_READ, _app, _doc)

# The browser's print footer of the MPM results page (the result URL, a timestamp, "Page n of n").
FOOTER = '\nhttps://stpm.mpm.edu.my/stpmX/result.php\n18/06/2026, 1:01 PM\nPage 1 of 2\n'
PORTAL_PRINT = STPM_SLIP + FOOTER
# The checker page's candidate-details section title alone (the corpus's other checker page).
CHECKER_SECTION_ONLY = 'MAKLUMAT CALON' + chr(10) + STPM_SLIP
# The online checker page that prints most of the slip's wording (the corpus case that scores 0.92 on
# the signatures alone): its own heading and buttons give it away.
CHECKER_WITH_SLIP_WORDING = 'Halaman Keputusan\nKEPUTUSAN PEPERIKSAAN STPM 2025\n' + STPM_SLIP + \
    'Cetak\nKembali ke Carian STPM\n'
CERTIFIED_SLIP = STPM_SLIP + 'SALINAN DIAKUI SAH\n'
# The 2025 slip's e-Sijil note and an MPM e-mail: an MPM web address that is NOT the results page.
SLIP_WITH_ESIJIL = STPM_SLIP + ('4. Calon boleh memuat turun dan mencetak sijil STPM secara dalam talian '
                                '(e-Sijil) melalui pautan https://sijil.mpm.edu.my.\nE-mel: stpm@mpm.edu.my\n')
TRANSCRIPT = """MAJLIS PEPERIKSAAN MALAYSIA
TRANSKRIP 2025
Nama : No. Kad Pengenalan : Angka Giliran : No. Siri :
Bil. Mata Pelajaran Didaftarkan :
Purata Nilai Gred Keseluruhan (PNGK) :
KOD MATA PELAJARAN WAJARAN (%) GRED KERTAS GRED MATA PELAJARAN NILAI GRED MATA PELAJARAN
Ketua Eksekutif
E-mel: stpm@mpm.edu.my  Portal: https://www.mpm.edu.my
"""
# MPM's cover letter that comes with a transcript (in the same PDF): an MPM letter, not a results page.
TRANSCRIPT_LETTER = """MAJLIS PEPERIKSAAN MALAYSIA (MALAYSIAN EXAMINATIONS COUNCIL)
MALAYSIA HIGHER SCHOOL CERTIFICATE EXAMINATION
This is to inform you that the candidate has contacted the Council to obtain a transcript of the
Malaysia Higher School Certificate.
Chief Executive  Malaysian Examinations Council
"""
MATRIC = 'KEPUTUSAN PEPERIKSAAN PROGRAM MATRIKULASI\nKEMENTERIAN PENDIDIKAN MALAYSIA\nPNGK : 3.50\n'
DIPLOMA = 'TRANSKRIP AKADEMIK\nDIPLOMA KEJURUTERAAN\nPOLITEKNIK\nPNGK : 3.20\n'
ASASI = 'ASASI SAINS\nUNIVERSITI MALAYA\nCGPA : 3.40\n'
SPM_SLIP = 'LEMBAGA PEPERIKSAAN\nSIJIL PELAJARAN MALAYSIA\nKEPUTUSAN PEPERIKSAAN\n'
MUET = 'MAJLIS PEPERIKSAAN MALAYSIA\nMALAYSIAN UNIVERSITY ENGLISH TEST (MUET)\nBAND\n'



class TheScorer(SimpleTestCase):

    def test_the_slip_and_the_certificate_are_judged_the_same_way(self):
        for text, seen in ((STPM_SLIP, 'stpm_slip'), (STPM_CERTIFICATE, 'stpm_certificate')):
            with self.subTest(seen=seen):
                g = stpm_higher_genuineness(text)
                self.assertEqual((g['status'], g['type']), ('genuine', seen))

    def test_ruling_2a_certified_copies_are_accepted(self):
        for text in (CERTIFIED_COPY, CERTIFIED_SLIP):
            with self.subTest(text=text[:12]):
                self.assertEqual(stpm_higher_genuineness(text)['status'], 'genuine')

    def test_ruling_1a_the_checker_page_is_not_a_results_document(self):
        for text in (ONLINE_CHECKER_PAGE, CHECKER_WITH_SLIP_WORDING):
            with self.subTest(text=text[:12]):
                g = stpm_higher_genuineness(text)
                self.assertEqual(g['status'], 'not_stpm_result')
        g = stpm_higher_genuineness(CHECKER_WITH_SLIP_WORDING)
        self.assertGreaterEqual(g['probability'], 0.70)        # the signatures alone would pass it
        self.assertEqual(g['type'], ONLINE_PAGE)
        self.assertIn('ruling 1A', g['reason'])

    def test_ruling_a_a_printout_of_the_results_web_page_is_a_slip(self):
        for text in (PORTAL_PRINT, PORTAL_PRINT + 'SALINAN DIAKUI SAH\n'):     # any form, certified too
            with self.subTest(text=text[-12:]):
                g = stpm_higher_genuineness(text)
                self.assertEqual((g['status'], g['type']), ('genuine', 'stpm_slip'))
        self.assertFalse(is_checker_page(PORTAL_PRINT))

    def test_the_checker_page_is_known_by_its_own_furniture_only(self):
        self.assertTrue(is_checker_page(CHECKER_SECTION_ONLY))
        self.assertEqual(stpm_higher_genuineness(CHECKER_SECTION_ONLY)['status'], 'not_stpm_result')
        for generic in ('Cetak', 'Semakan Keputusan', 'Muat Turun'):              # never generic words
            with self.subTest(word=generic):
                self.assertFalse(is_checker_page(STPM_SLIP + generic))

    def test_other_mpm_addresses_are_not_the_results_page(self):
        self.assertEqual(stpm_higher_genuineness(SLIP_WITH_ESIJIL)['status'], 'genuine')

    def test_other_kinds_stay_not_checked(self):
        for text in (MATRIC, DIPLOMA, ASASI, SPM_SLIP, MUET, '', 'SOME OTHER PAGE'):
            with self.subTest(text=text[:12]):
                self.assertEqual(stpm_higher_genuineness(text), {})

    def test_an_mpm_transcript_stays_not_checked_until_it_has_a_list(self):
        for text in (TRANSCRIPT, TRANSCRIPT_LETTER, TRANSCRIPT_LETTER + TRANSCRIPT):
            with self.subTest(text=text[:40]):
                self.assertEqual(stpm_higher_genuineness(text), {})

    def test_the_semester_slot_is_routed_as_before(self):
        class Doc:
            doc_type, content_type = 'semester_result', 'image/jpeg'
        self.assertEqual(stpm_slot_genuineness(Doc(), STPM_SLIP)['status'], 'genuine')
        self.assertEqual(stpm_slot_genuineness(Doc(), CHECKER_WITH_SLIP_WORDING)['status'],
                         'genuine')                           # 1A is the higher-results slot's (S3)

    def test_the_model_version(self):
        self.assertGreaterEqual(tuple(map(int, MODEL_VERSION.split('.'))), (1, 11, 0))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TheUpload(TestCase):
    """The live read (`vision.run_field_extraction_for_document`) stores the score on the document."""

    def setUp(self):
        self.app = _app(STPM_HELD, DEGREE)

    def _upload(self, text, content_type='image/jpeg'):
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='higher_results',
                                               storage_path='test/hr', content_type=content_type)
        ocr = {'text': text, 'words': None, 'image': b'%PDF-x' if content_type.endswith('pdf') else b'img',
               'error': None}
        with patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {'candidate_name': 'PRIYA'}, 'warnings': [], 'error': ''}), \
             patch('apps.scholarship.genuineness.results_doc.results_visual_markers') as visual:
            vision.run_field_extraction_for_document(doc, names=[], ocr=ocr)
        visual.assert_not_called()                   # no new Gemini call on this path
        doc.refresh_from_db()
        return doc

    def test_an_stpm_slip_is_stored_in_the_results_slot_shape(self):
        auth = self._upload(STPM_SLIP).vision_fields['authenticity']
        self.assertEqual(set(auth), {'status', 'reason', 'doc_seen', 'probability', 'present', 'missing',
                                     'model_version'})
        self.assertEqual((auth['status'], auth['doc_seen'], auth['model_version']),
                         ('genuine', 'stpm_slip', MODEL_VERSION))

    def test_a_portal_printout_is_a_slip_in_any_form_and_the_checker_page_is_1a(self):
        for ct in ('image/jpeg', 'application/pdf'):
            with self.subTest(content_type=ct):
                self.assertEqual(self._upload(PORTAL_PRINT, ct).vision_fields['authenticity']['status'], 'genuine')
        self.assertEqual(self._upload(CHECKER_WITH_SLIP_WORDING).vision_fields['authenticity']['status'],
                         'not_stpm_result')

    def test_the_upload_is_never_fetched_again_for_the_score(self):
        with patch('apps.scholarship.vision._fetch_image_bytes') as fetch:
            self._upload(PORTAL_PRINT)
        fetch.assert_not_called()

    def test_a_matriculation_slip_is_not_scored(self):
        self.assertNotIn('authenticity', self._upload(MATRIC).vision_fields)

    def test_an_empty_read_gives_no_signal(self):
        self.assertNotIn('authenticity', self._upload('').vision_fields)

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_the_check_off_scores_nothing(self):
        self.assertNotIn('authenticity', self._upload(STPM_SLIP).vision_fields)


class TheDoors(TestCase):
    """Every reader of the stored score for a higher-results document."""

    def _app_with(self, auth, fields=STPM_READ, held=STPM_HELD):
        app = _app(held, DEGREE)
        doc = _doc(app, 'higher_results', fields)
        if auth is not None:
            doc.vision_fields = dict(doc.vision_fields, authenticity=auth)
            doc.save(update_fields=['vision_fields'])
        return ScholarshipApplication.objects.get(pk=app.pk), doc

    def _academic(self, app):
        from apps.scholarship.verdict_engine import build_verdict
        return next(f for f in build_verdict(app) if f['fact'] == 'academic')

    GENUINE = {'status': 'genuine', 'reason': '', 'doc_seen': 'stpm_slip', 'probability': 1.0}
    ONE_A = {'status': 'not_stpm_result', 'reason': 'ruling 1A', 'doc_seen': ONLINE_PAGE, 'probability': 0.9}

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_the_verdict_engine_reads_the_real_outcome(self):
        f = self._academic(self._app_with(None)[0])                     # unscored: as before
        self.assertIn('higher_results_not_checked', {i['code'] for i in f['evidence']})
        self.assertEqual(f['status'], 'review')
        f = self._academic(self._app_with(self.GENUINE)[0])             # scored genuine: Certain
        self.assertNotIn('higher_results_not_checked', {i['code'] for i in f['evidence']})
        self.assertEqual(f['status'], 'verified')
        f = self._academic(self._app_with(self.ONE_A)[0])               # 1A: the −2 step + the caveat
        self.assertNotIn('higher_results_not_checked', {i['code'] for i in f['evidence']})
        self.assertIn('document_not_genuine', {i['code'] for i in f['unresolved']})
        self.assertEqual(f['status'], 'recommend')

    def test_the_engine_version_moved(self):
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreater(VERDICT_ENGINE_VERSION, '2026-10-27.3')

    def test_a_stored_not_checked_status_is_still_not_checked(self):
        from apps.scholarship.genuineness.bands import NOT_CHECKED
        f = self._academic(self._app_with({'status': NOT_CHECKED})[0])
        self.assertIn('higher_results_not_checked', {i['code'] for i in f['evidence']})

    def test_the_student_and_the_reviewer_see_it_on_the_document(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        _, doc = self._app_with(self.ONE_A)
        auth = ApplicantDocumentSerializer().get_authenticity(doc)
        self.assertEqual(auth['status'], 'not_higher_results')      # GenuinenessNote + the cockpit chip
        _, plain = self._app_with(None)
        self.assertIsNone(ApplicantDocumentSerializer().get_authenticity(plain))

    def test_the_interview_flag_names_the_stpm_results(self):
        from apps.scholarship.anomaly_engine import detect_anomalies
        app, _ = self._app_with(self.ONE_A)
        hit = next(a for a in detect_anomalies(app) if a['code'] == 'document_not_genuine')
        self.assertEqual((hit['params']['doc'], hit['params']['seen']), ('STPM results', ONLINE_PAGE))
        app, _ = self._app_with(self.GENUINE)
        self.assertNotIn('document_not_genuine', [a['code'] for a in detect_anomalies(app)])

    def test_no_interview_flag_when_the_higher_results_do_not_anchor_academic(self):
        from apps.scholarship.anomaly_engine import detect_anomalies
        from apps.scholarship.higher_results import anchors_on_higher
        app = _app(SPM_HELD, MATRIC_PATHWAY)
        doc = _doc(app, 'higher_results', STPM_READ)
        doc.vision_fields = dict(doc.vision_fields, authenticity=self.ONE_A)
        doc.save(update_fields=['vision_fields'])
        app = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertFalse(anchors_on_higher(app))
        self.assertNotIn('document_not_genuine', [a['code'] for a in detect_anomalies(app)])

    def test_keep_better_prefers_the_genuine_slip_over_a_checker_page(self):
        from apps.scholarship.promotion import doc_quality
        app, page = self._app_with(self.ONE_A)
        slip = _doc(app, 'higher_results', STPM_READ)
        slip.vision_fields = dict(slip.vision_fields, authenticity=self.GENUINE)
        slip.save(update_fields=['vision_fields'])
        page.id, slip.id = 2, 1                     # the checker page is the NEWER upload
        self.assertGreater(doc_quality(slip), doc_quality(page))

    def test_a_1a_page_does_not_block_or_mismatch_like_the_spm_slot(self):
        from apps.scholarship.resolution import doc_match_verdict
        _, doc = self._app_with(self.ONE_A)
        self.assertEqual(doc_match_verdict(doc), 'ok')      # parity with a not_<type> SPM slip

    def test_a_reread_with_no_signal_keeps_the_stored_score(self):
        _, doc = self._app_with(self.ONE_A)
        with override_settings(DOC_GENUINENESS_CHECK_ENABLED=False), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {'candidate_name': 'PRIYA'}, 'warnings': [], 'error': ''}):
            vision.run_field_extraction_for_document(
                doc, names=[], ocr={'text': STPM_SLIP, 'words': None, 'image': b'img', 'error': None})
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'not_stpm_result')   # TD-407

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_a_matriculation_card_stays_not_checked(self):
        app, _ = self._app_with(None, {'candidate_name': 'PRIYA', 'cgpa': '3.5',
                                       'results_kind_detected': 'matric'}, held=MATRIC_HELD)
        self.assertIn('higher_results_not_checked', {i['code'] for i in self._academic(app)['evidence']})
