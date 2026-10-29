"""Matric/Diploma exact-read M4 — genuineness of a Matriculation / polytechnic transcript in the
higher-results slot (`genuineness/matric_poly_doc.py`, MODEL_VERSION 1.21.0).

Synthetic twins only (the fixed printed wording of each layout, never a student's data). GENUINE OR
NOTHING for both families (review, 2026-10-29): a transcript that passes its gates scores genuine;
EVERYTHING else — a genuine 2-year transcript seen page 1 only, a cropped photo, a noisy scan, half
a page, a semester result slip (however mangled), an offer letter, a KPM letter, the polytechnic
portal screen, a Kolej Komuniti / UiTM diploma, Asasi, SPM — stays UNSCORED ("not checked"), never
suspect, never "not_". The slot call order; the vision path and the Academic band.
"""
import re
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import matric_poly_doc
from apps.scholarship.genuineness.matric_poly_doc import matric_poly_higher_genuineness as score
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, _norm_fold_upper_alnum, _score_list
from apps.scholarship.genuineness.stpm_doc import stpm_higher_genuineness, stpm_slot_genuineness
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.test_corpus_gaps_c3 import STPM_SLIP
from apps.scholarship.tests.test_matric_parse import four_sem_pages, two_sem
from apps.scholarship.tests.test_poly_diploma_parse import NL, UITM, transcript
from apps.scholarship.tests.test_third_route_s3 import DEGREE, MATRIC_HELD, _app, _doc

#: The polytechnic transcript twin with the footer the real one prints.
POLY = transcript() + NL + NL.join([
    'MEDIUM OF INSTRUCTION : ENGLISH', 'COMPUTER GENERATED AND NO AUTHORIZED SIGNATURE IS REQUIRED.',
    'THE DETAILS ARE SUBJECT TO APPROVAL BY THE POLYTECHNIC BOARD OF', 'EXAMINATION AND AWARD FOR CERTIFICATION.',
    'ABBREVIATION', '[CE] - COURSE EXEMPTION', '[RIG] - REPEAT TO IMPROVE GRADE'])
MATRIC = two_sem() + NL + 'PUSAT PENTADBIRAN KERAJAAN PERSEKUTUAN 62604 PUTRAJAYA' + NL + 'www.moe.gov.my'
#: A Matriculation offer letter with the bilingual header: the division, the college, no grid.
MATRIC_OFFER = NL.join([
    'KEMENTERIAN PENDIDIKAN MALAYSIA', 'MINISTRY OF EDUCATION MALAYSIA', 'BAHAGIAN MATRIKULASI',
    'MATRICULATION DIVISION', '62604 PUTRAJAYA', 'www.moe.gov.my',
    'TAWARAN KEMASUKAN KE PROGRAM MATRIKULASI SESI 2026/2027', 'NO. MATRIK : MS2615110001',
    'KOLEJ MATRIKULASI PERAK', 'JURUSAN : SAINS', 'PENGARAH'])
#: A KPM letter that mentions the transcript and both semesters but prints no transcript.
KPM_LETTER = NL.join([
    'KEMENTERIAN PENDIDIKAN MALAYSIA', 'BAHAGIAN MATRIKULASI', 'MATRICULATION DIVISION',
    'Transkrip akademik bagi Semester I dan Semester II akan dikeluarkan selepas PNGS dimuktamadkan.',
    'PENGARAH'])
#: The polytechnic student-portal screen (shape of the corpus screenshot).
PORTAL = NL.join(['Semakan butiran pelajar mengikut No. Pendaftaran', 'DEP - DIPLOMA KEJURUTERAAN ELEKTRONIK',
                  'POLITEKNIK CONTOH', 'STATUS PENDAFTARAN', 'KEPUTUSAN PEPERIKSAAN MENGIKUT SEMESTER',
                  'Keputusan Semasa Keputusan Asasi TVET', 'KELAS SEMASA', 'HPNM 3.10'])
#: A page that passes every polytechnic gate but scores between the bands (0.48).
POLY_MID = NL.join(['ACADEMIC TRANSCRIPT', 'POLITEKNIK CONTOH SABAH',
                    'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI', 'DIPLOMA AGROTECHNOLOGY',
                    ' : 21DAG21F1001REG.NO', 'INTAKE SESSION', 'CODE COURSE CREDIT GRADE REMARK',
                    ': 3.40Grade Point Average (GPA)', 'Cumulative Grade Point Average (CGPA)'])


def raw(text, signatures):
    return _score_list(signatures, _norm_fold_upper_alnum(text), False, False)['probability']


class TestGenuineOrNothing(SimpleTestCase):
    def test_a_matric_transcript_is_genuine(self):
        sg = score(MATRIC)
        self.assertEqual((sg['status'], sg['type'], sg['probability']), ('genuine', 'matric_transcript', 1.0))
        self.assertEqual(sg['model_version'], MODEL_VERSION)

    def test_a_polytechnic_transcript_is_genuine(self):
        self.assertEqual((score(POLY)['status'], score(POLY)['type']), ('genuine', 'poly_transcript'))

    def test_review_b1_a_genuine_transcript_seen_in_part_is_never_suspect(self):
        """B1: page 1 of a 2-year transcript, a cropped photo, OCR noise, half a page — all genuine
        documents; between the bands (or below) they stay "not checked", never suspect / not_."""
        page1 = four_sem_pages()[0]
        self.assertTrue(0.35 <= raw(page1, matric_poly_doc.MATRIC_TRANSCRIPT_SIGNATURES) < 0.70)
        lines = MATRIC.split(NL)
        cropped = NL.join(lines[5:])
        noisy = (MATRIC.replace('BAHAGIAN MATRIKULASI', 'BAHAG1AN MATR1KULASI').replace('MATA NILAIAN', 'MATA NILA1AN')
                 .replace('LULUS DAN TAMAT', 'LULU5 DAN TAMAT').replace('PURATA GRED', 'PURATA GRE0'))
        bottom = NL.join(lines[len(lines) // 2:])
        for label, text in (('page 1', page1), ('cropped', cropped), ('noisy', noisy), ('bottom half', bottom)):
            self.assertIn(score(text).get('status', ''), ('', 'genuine'), label)

    def test_a_polytechnic_page_between_the_bands_is_not_scored(self):
        self.assertTrue(0.35 <= raw(POLY_MID, matric_poly_doc.POLY_TRANSCRIPT_SIGNATURES) < 0.70)
        self.assertEqual(score(POLY_MID), {})


class TestTheGates(SimpleTestCase):
    def test_review_s1_a_slip_however_mangled_is_never_scored(self):
        slip = MATRIC.replace('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT', 'SL1P KEPUTUSAN PEPERIKSAAN')
        self.assertEqual(score(slip), {})                                  # one semester shown
        one_sem = re.sub(r'SEMESTER I\n.*?PNGS / GPA : 3\.25\n', '', MATRIC, flags=re.S)
        self.assertEqual(score(one_sem), {})                               # a cropped slip: no "Semester I"
        # M4b re-review blocker (2026-10-30): a WHOLE final transcript (its bilingual heading, grid, both
        # semesters, completion status) scores as the transcript even with slip wording in the same upload
        # (a slip bundled in) — never "not final". A slip with no transcript in it stays unscored (above).
        self.assertEqual(score(MATRIC + NL + 'Slip keputusan ini bukan transkrip')['status'], 'genuine')
        self.assertEqual(score(MATRIC + NL + 'before the actual academic transcript is issued')['status'], 'genuine')

    def test_review_s1_a_letter_that_is_no_ruled_kind_is_never_scored(self):
        self.assertEqual(score(KPM_LETTER), {})                # neither an offer nor a transcript

    def test_the_matric_gates_each_hold(self):
        self.assertEqual(score(MATRIC.replace('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT', 'KEPUTUSAN')), {})
        no_grid = MATRIC.replace('MATA NILAIAN', '').replace('VALUE POINT', '').replace('PNGS', 'GPS')
        self.assertEqual(score(no_grid), {})

    def test_review_s2_no_kolej_komuniti_anywhere(self):
        self.assertEqual(score(POLY + NL + 'PROGRAMME OFFERED AT KOLEJ KOMUNITI SELAYANG'), {})
        self.assertEqual(score(POLY + NL + 'KOLEJ KOMUNlTI SELAYANG'), {})          # OCR l for I
        wrapped = POLY.replace('JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI',
                               'JABATAN PENDIDIKAN POLITEKNIK DAN' + NL + 'KOLEJ KOMUNITI')
        self.assertEqual(score(wrapped)['status'], 'genuine')                  # the department, wrapped

    def test_review_s3_a_negated_title_and_a_slip_are_never_a_transcript(self):
        negated = POLY.replace('ACADEMIC TRANSCRIPT', 'THIS IS NOT AN ACADEMIC TRANSCRIPT')
        self.assertEqual(score(negated), {})
        slip = POLY + NL + 'KEPUTUSAN PENILAIAN AKHIR SEMESTER'       # re-review: a whole final transcript
        self.assertEqual(score(slip)['status'], 'genuine')              # bundled with slip words still scores
        # a negation the slip lists do not name ("NOT ACADEMIC TRANSCRIPT"): only the title gate sees it
        self.assertEqual(score(POLY.replace('ACADEMIC TRANSCRIPT', 'NOT ACADEMIC TRANSCRIPT')), {})
        self.assertEqual(score(MATRIC.replace('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT', 'NOT ACADEMIC TRANSCRIPT')), {})

    def test_the_polytechnic_needs_its_name_and_grid(self):
        other = POLY.replace('POLITEKNIK CONTOH SABAH', 'INSTITUT CONTOH').replace('POLYTECHNIC BOARD OF', 'BOARD OF')
        self.assertEqual(score(other), {})
        self.assertEqual(score(POLY.replace('CODE COURSE CREDIT GRADE REMARK', 'CODE COURSE')), {})

    def test_other_diplomas_asasi_and_spm_are_not_scored(self):
        for text in (UITM, 'PUSAT ASASI SAINS ACADEMIC TRANSCRIPT CGPA 3.10',
                     'SIJIL PELAJARAN MALAYSIA 2024 BAHASA MELAYU A'):
            self.assertEqual(score(text), {}, text[:30])


class _Doc:
    def __init__(self, doc_type):
        self.doc_type = doc_type


class TestTheSlotCall(SimpleTestCase):
    def test_the_higher_slot_scores_matric_and_polytechnic(self):
        self.assertEqual(stpm_slot_genuineness(_Doc('higher_results'), MATRIC)['type'], 'matric_transcript')
        self.assertEqual(stpm_slot_genuineness(_Doc('higher_results'), POLY)['type'], 'poly_transcript')

    def test_the_semester_slot_stays_stpm_only(self):
        self.assertEqual(stpm_slot_genuineness(_Doc('semester_result'), MATRIC), {})

    def test_an_stpm_page_reads_exactly_as_before_m4(self):
        before = stpm_higher_genuineness(STPM_SLIP)            # the slot's whole answer before M4
        self.assertTrue(before)
        self.assertEqual(stpm_slot_genuineness(_Doc('higher_results'), STPM_SLIP), before)


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestTheLivePath(TestCase):
    """Through the real read (`vision.run_field_extraction_for_document`) to the Academic band."""

    READ = {'candidate_name': 'PRIYA', 'cgpa': '3.50', 'cgpa_label': 'PNGK'}

    def _upload(self, app, text):
        doc = ApplicantDocument.objects.create(application=app, doc_type='higher_results', results_kind='matric',
                                               storage_path='test/hr-m4', content_type='image/jpeg')
        with patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': dict(self.READ), 'warnings': [], 'error': ''}):
            vision.run_field_extraction_for_document(
                doc, names=[], ocr={'text': text, 'words': None, 'image': b'img', 'error': None})
        doc.refresh_from_db()
        return doc

    def _academic(self, app):
        from apps.scholarship.verdict_engine import build_verdict
        fresh = ScholarshipApplication.objects.get(pk=app.pk)
        return next(f for f in build_verdict(fresh) if f['fact'] == 'academic')

    def test_a_genuine_transcript_is_stored_and_lifts_the_floor(self):
        app = _app(MATRIC_HELD, DEGREE)
        doc = self._upload(app, MATRIC.replace('PNGK / CGPA : 3.29', 'PNGK / CGPA : 3.50'))
        self.assertEqual((doc.vision_fields['authenticity']['status'], doc.vision_fields['authenticity']['doc_seen']),
                         ('genuine', 'matric_transcript'))
        f = self._academic(app)
        self.assertNotIn('higher_results_not_checked', {i['code'] for i in f['evidence']})
        self.assertNotIn('document_not_genuine', {i['code'] for i in f['unresolved']})

    def test_a_page_one_view_stores_nothing_and_keeps_the_floor(self):
        app = _app(MATRIC_HELD, DEGREE)
        doc = self._upload(app, four_sem_pages()[0])
        self.assertNotIn('authenticity', doc.vision_fields)
        f = self._academic(app)
        self.assertIn('higher_results_not_checked', {i['code'] for i in f['evidence']})
        self.assertNotEqual(f['status'], 'verified')

    def test_a_stored_genuine_clean_card_reads_certain(self):
        app = _app(MATRIC_HELD, DEGREE)
        _doc(app, 'higher_results', dict(self.READ, results_kind_detected='matric'), results_kind='matric')
        doc = app.documents.get(doc_type='higher_results')
        doc.vision_fields = dict(doc.vision_fields, authenticity={'status': 'genuine', 'reason': '',
                                                                  'doc_seen': 'matric_transcript', 'probability': 1.0})
        doc.save(update_fields=['vision_fields'])
        self.assertEqual(self._academic(app)['status'], 'verified')

    def test_the_versions_moved(self):
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in MODEL_VERSION.split('.')), (1, 22, 0))
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'[-.]', VERDICT_ENGINE_VERSION)), (2026, 10, 29, 3))
