"""Matric/Diploma M4b — the owner's rulings (2026-10-29) on Matriculation / polytechnic pages in the
higher-results slot (`genuineness/matric_poly_doc.py`, MODEL_VERSION 1.22.0):
  A. only the FINAL result counts — the final academic transcript;
  B. a NON-FINAL document (a semester result slip, the polytechnic portal, a transcript with no
     completion status) does not count: read as if the final results are NOT YET UPLOADED —
     Academic capped at Probable, the final transcript asked for — never the −2 step;
  C. a PROVISIONAL transcript that prints its completion status and final CGPA counts as final;
  D. a Matriculation OFFER LETTER here is "not a results document" (the −2 step); no suspect band.
Synthetic twins of each page's fixed wording; a real final transcript is never asked to re-upload.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import matric_poly_doc as m
from apps.scholarship.genuineness.bands import NOT_CHECKED, NOT_FINAL_SEEN
from apps.scholarship.genuineness.matric_poly_doc import matric_poly_higher_genuineness as score
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.test_matric_parse import four_sem_pages
from apps.scholarship.tests.test_matric_poly_doc import KPM_LETTER, MATRIC, MATRIC_OFFER, POLY, PORTAL
from apps.scholarship.tests.test_poly_diploma_parse import NL, UITM
from apps.scholarship.tests.test_third_route_s3 import DEGREE, MATRIC_HELD, _app

#: A Matriculation semester result slip: the KPM header, ONE semester, the slip's title and disclaimer.
SLIP_HEAD = ['KEMENTERIAN PENDIDIKAN', 'BAHAGIAN MATRIKULASI', 'MATRICULATION DIVISION',
             'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP', '{sem} SESI 2025/2026',
             'NAMA / NAME : SITI AMINAH BINTI ALI', 'KOLEJ / COLLEGE : KOLEJ MATRIKULASI PERAK',
             'SC025 COMPUTER SCIENCE 2 5 A 4.00', 'PNGS / GPA : 4.00', 'PNGK / CGPA : 4.00']
DISCLAIMER = ['Slip keputusan ini bukan transkrip akademik. Keputusan muktamad adalah seperti yang tercatat',
              'sebelum transkrip akademik sebenar dikeluarkan.',
              'This result slip is not an academic transcript. The final result is as appeared in the academic transcript.']


def matric_slip(sem='SEMESTER II', final=True):
    lines = [ln.format(sem=sem) for ln in SLIP_HEAD]
    if final:
        lines.append('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI')
    return NL.join(lines + DISCLAIMER)


#: A polytechnic semester result slip (the shape of the two corpus slips).
POLY_SLIP = NL.join(['SLIP KEPUTUSAN PENILAIAN AKHIR', 'KEPUTUSAN PENILAIAN AKHIR SEMESTER', 'SESI I : 2025/2026',
                     'PROGRAM DIPLOMA PENGURUSAN LOGISTIK', 'POLITEKNIK CONTOH',
                     'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI', 'SEMESTER : TIGA', 'KELAS SEMASA : DLS3C',
                     'KOD NAMA KURSUS JAM KREDIT GRED NILAI MATA MATA KREDIT STATUS',
                     'DPB10063 PRINCIPLES OF MANAGEMENT 3.0 A 4.00 12.00', 'PNM : 3.53 HPNM : 3.16'])


class TestTheRulings(SimpleTestCase):
    def assertRuled(self, text, seen, status):
        sg = score(text)
        self.assertEqual((sg.get('status'), sg.get('type')), (status, seen))
        self.assertIn('owner ruling', sg['reason'])
        self.assertIn('2026-10-29', sg['reason'])

    def test_b_a_matriculation_semester_result_slip_is_not_final(self):
        self.assertRuled(matric_slip(), m.MATRIC_SLIP, NOT_CHECKED)                  # final "Lulus dan Tamat" slip
        self.assertRuled(matric_slip('SEMESTER I', final=False), m.MATRIC_SLIP, NOT_CHECKED)
        self.assertRuled(matric_slip('SEMESTER IV'), m.MATRIC_SLIP, NOT_CHECKED)      # a 2-year programme's
        self.assertIn('final academic transcript is still owed', score(matric_slip())['reason'])

    def test_b_a_polytechnic_semester_result_slip_is_not_final(self):
        self.assertRuled(POLY_SLIP, m.POLY_SLIP, NOT_CHECKED)

    def test_b_the_polytechnic_student_portal_is_not_final(self):
        self.assertRuled(PORTAL, m.POLY_PORTAL, NOT_CHECKED)

    def test_b_a_transcript_with_no_completion_status_is_not_final(self):
        no_status = MATRIC.replace('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', '').replace(
            'PASS AND COMPLETED MATRICULATION PROGRAMME', '')
        self.assertRuled(no_status, m.MATRIC_NOT_FINAL, NOT_CHECKED)
        self.assertRuled(POLY.replace('STATUS  : COMPLETED', 'STATUS  : ACTIVE'), m.POLY_NOT_FINAL, NOT_CHECKED)

    def test_a_transcript_is_genuine_only_with_its_completion_status(self):
        """No status, no end on the page (no average box, no PNGK): never genuine, only unsure."""
        cut = MATRIC
        for line in ('STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI', 'PASS AND COMPLETED MATRICULATION PROGRAMME',
                     'PURATA GRED BAGI KURSUS TERAS DAN ENGLISH', 'AVERAGE GRADE FOR CORE COURSES AND ENGLISH',
                     'PNGK / CGPA : 3.29'):
            cut = cut.replace(line, '')
        self.assertEqual(score(cut), {})

    def test_b_a_page_one_view_that_cannot_see_the_end_stays_unsure(self):
        """A missing status is only "missing" when the END of the transcript is on the page."""
        self.assertEqual(score(four_sem_pages()[0]), {})
        no_end = POLY.replace('~~~~~End of results~~~~~', '').replace('STATUS  : COMPLETED', 'STATUS  : ACTIVE')
        self.assertEqual(score(no_end), {})

    def test_c_a_provisional_transcript_with_status_and_final_cgpa_counts_as_final(self):
        """3926's shape: "ACADEMIC TRANSCRIPT (PROVISIONAL)", STATUS COMPLETED, the final CGPA."""
        self.assertIn('ACADEMIC TRANSCRIPT (PROVISIONAL)', POLY)
        self.assertEqual(score(POLY)['status'], 'genuine')

    def test_d_a_matriculation_offer_letter(self):
        self.assertRuled(MATRIC_OFFER, m.MATRIC_OFFER, 'not_matric_result')
        self.assertIn('not a results document', score(MATRIC_OFFER)['reason'])

    def test_the_non_final_codes_have_one_home(self):
        self.assertEqual(NOT_FINAL_SEEN, {m.MATRIC_SLIP, m.POLY_SLIP, m.POLY_PORTAL, m.MATRIC_NOT_FINAL,
                                          m.POLY_NOT_FINAL})

    def test_a_real_transcript_is_never_asked_to_re_upload(self):
        """Even one that carries an offer letter's or a slip's word somewhere on it."""
        for text in (MATRIC, POLY, MATRIC + NL + 'TAHNIAH ATAS KEMASUKAN', POLY + NL + 'HPNM JAM KREDIT'):
            self.assertEqual(score(text).get('status'), 'genuine')
        self.assertEqual(score(four_sem_pages()[0]), {})                # page 1 of a 2-year transcript: unsure

    def test_a_transcript_is_never_ruled_whatever_else_it_prints(self):
        """The guard before every ruling: a page that passes a transcript's own gates is a transcript."""
        portal_words = NL.join(['KEPUTUSAN PEPERIKSAAN MENGIKUT SEMESTER', 'DAFTAR HHP', 'STATUS DAFTAR LATIHAN INDUSTRI'])
        self.assertEqual(score(MATRIC + NL + portal_words).get('status'), 'genuine')

    def test_an_offer_is_told_only_on_a_matric_page_with_no_transcript_grid(self):
        import re
        cropped = re.sub(r'SEMESTER II\n.*?PNGS / GPA : 3\.33\n', '', MATRIC, flags=re.S)
        self.assertEqual(score(cropped + NL + 'TAWARAN KEMASUKAN'), {})       # a grid: not an offer, unsure
        two_ways = NL.join(['BAHAGIAN MATRIKULASI', 'TAWARAN KEMASUKAN KE PROGRAM DIPLOMA'])
        self.assertEqual(score(two_ways), {})                                  # Matriculation AND Diploma: no kind

    def test_unsure_stays_not_checked(self):
        """One slip phrase only, one portal phrase, one offer word, a letter of no ruled kind."""
        one_phrase = NL.join([ln.format(sem='SEMESTER II') for ln in SLIP_HEAD]).replace(
            'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP', 'SLIP KEPUTUSAN PEPERIKSAAN')
        for text in (one_phrase, NL.join(['POLITEKNIK CONTOH', 'SEMAKAN BUTIRAN PELAJAR', 'DIPLOMA X', 'HPNM 3.1']),
                     NL.join(['BAHAGIAN MATRIKULASI', 'TAWARAN PROGRAM MATRIKULASI']), KPM_LETTER):
            self.assertEqual(score(text), {})

    def test_the_rulings_stay_in_their_families(self):
        for text in (UITM, UITM + NL + 'SLIP KEPUTUSAN PEPERIKSAAN EXAMINATION RESULT SLIP',
                     'PUSAT ASASI SAINS ' + NL.join(DISCLAIMER), 'SIJIL PELAJARAN MALAYSIA 2024 BAHASA MELAYU A TAWARAN'):
            self.assertEqual(score(text), {}, text[:30])
        kk_slip = POLY_SLIP.replace('POLITEKNIK CONTOH', 'KOLEJ KOMUNITI CONTOH')
        self.assertEqual(score(kk_slip), {})                            # no polytechnic's own name

    def test_4_no_suspect_is_ever_stored(self):
        for text in (MATRIC, POLY, matric_slip(), POLY_SLIP, PORTAL, MATRIC_OFFER, KPM_LETTER, four_sem_pages()[0]):
            self.assertNotEqual(score(text).get('status'), 'suspect')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestTheLivePath(TestCase):
    READ = {'candidate_name': 'PRIYA', 'cgpa': '3.50', 'cgpa_label': 'PNGK'}

    def _upload(self, text, stage='shortlisted', **kw):
        app = _app(MATRIC_HELD, DEGREE, stage=stage, **kw)
        doc = ApplicantDocument.objects.create(application=app, doc_type='higher_results', results_kind='matric',
                                               storage_path='test/hr-m4b', content_type='image/jpeg')
        with patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': dict(self.READ), 'warnings': [], 'error': ''}):
            vision.run_field_extraction_for_document(
                doc, names=['Priya'], ocr={'text': text, 'words': None, 'image': b'img', 'error': None})
        doc.refresh_from_db()
        return app, doc

    def _academic(self, app):
        from apps.scholarship.verdict_engine import build_verdict
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        return next(f for f in build_verdict(fresh) if f['fact'] == 'academic')

    def test_b_a_slip_reads_as_not_yet_uploaded_probable_and_asked_for(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        app, doc = self._upload(matric_slip())
        auth = doc.vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen']), (NOT_CHECKED, m.MATRIC_SLIP))
        academic = self._academic(app)
        codes = {i['code'] for i in academic['unresolved']}
        self.assertIn('higher_results_not_final', codes)
        self.assertNotIn('document_not_genuine', codes)                     # never the -2 step
        self.assertEqual(academic['status'], 'review')                       # Probable, as "not yet uploaded"
        self.assertEqual(ApplicantDocumentSerializer(doc).data['authenticity']['status'], 'final_owed')
        self.assertEqual(higher_owed.ask_codes(ScholarshipApplication.objects.get(pk=app.pk)), set())  # not submitted

    def test_b_once_submitted_the_final_transcript_is_asked_for_until_a_final_one_answers(self):
        from apps.scholarship import higher_owed
        from apps.scholarship.tests.test_third_route_s4 import HIGHER_FROZEN
        # Frozen WITH the higher results required, so the #388 pre-S3 path does not fire: only ruling B asks.
        app, _doc = self._upload(matric_slip(), stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        self.assertEqual(higher_owed._owed(fresh), '')
        self.assertEqual(higher_owed.ask_codes(fresh), {higher_owed.ASK_CODE})
        self.assertEqual(higher_owed.ask_params(fresh, higher_owed.ASK_CODE), {'results_kind': 'matric'})
        self.assertFalse(higher_owed.answered(fresh))
        final_app, _final = self._upload(MATRIC, stage='profile_complete', requirements_snapshot=HIGHER_FROZEN)
        self.assertEqual(higher_owed.final_owed_kind(ScholarshipApplication.objects.get(pk=final_app.pk)), '')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_b_a_non_final_upload_is_never_certain_even_with_the_check_off(self):
        """The TD-114 floor is inert with the check off: the not-final rule must hold the card itself."""
        app = _app(MATRIC_HELD, DEGREE)
        ApplicantDocument.objects.create(
            application=app, doc_type='higher_results', results_kind='matric', storage_path='test/hr-m4b-off',
            vision_fields={'fields': dict(self.READ, results_kind_detected='matric'), 'student_verdict': 'ok',
                           'error': '', 'authenticity': {'status': NOT_CHECKED, 'doc_seen': m.MATRIC_SLIP,
                                                         'reason': ''}})
        self.assertEqual(self._academic(app)['status'], 'review')

    def test_c_a_final_transcript_answers_and_reads_certain(self):
        app, doc = self._upload(MATRIC.replace('PNGK / CGPA : 3.29', 'PNGK / CGPA : 3.50'))
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'genuine')
        academic = self._academic(app)
        self.assertNotIn('higher_results_not_final', {i['code'] for i in academic['unresolved']})

    def test_d_an_offer_letter_still_takes_the_not_a_result_step(self):
        app, doc = self._upload(MATRIC_OFFER)
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'not_matric_result')
        self.assertIn('document_not_genuine', {i['code'] for i in self._academic(app)['unresolved']})

    def test_the_versions_moved(self):
        import re
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in MODEL_VERSION.split('.')), (1, 22, 0))
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'[-.]', VERDICT_ENGINE_VERSION)), (2026, 10, 29, 3))
