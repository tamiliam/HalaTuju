"""Matric/Diploma exact-read M4 — genuineness of a Matriculation / polytechnic transcript in the
higher-results slot (`genuineness/matric_poly_doc.py`, MODEL_VERSION 1.21.0).

Synthetic twins only (the fixed printed wording of each layout, never a student's data). What is
pinned: a transcript scores genuine; a thin Matriculation page scores suspect; a page below the
floor (a Matriculation OFFER letter), a semester result slip, a polytechnic page that is not
clearly genuine, a UiTM / Kolej Komuniti diploma, Asasi and SPM all stay UNSCORED ("not checked");
the slot call order; the TD-114 floor lifts only for a scored page.
"""
import re

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship.genuineness import matric_poly_doc
from apps.scholarship.genuineness.matric_poly_doc import matric_poly_higher_genuineness as score
from apps.scholarship.genuineness.stpm_doc import stpm_slot_genuineness
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.tests.test_matric_parse import two_sem
from apps.scholarship.tests.test_poly_diploma_parse import NL, UITM, transcript

#: The polytechnic transcript twin with the footer the real one prints.
POLY = transcript() + NL + NL.join([
    'MEDIUM OF INSTRUCTION : ENGLISH', 'COMPUTER GENERATED AND NO AUTHORIZED SIGNATURE IS REQUIRED.',
    'THE DETAILS ARE SUBJECT TO APPROVAL BY THE POLYTECHNIC BOARD OF', 'EXAMINATION AND AWARD FOR CERTIFICATION.',
    'ABBREVIATION', '[CE] - COURSE EXEMPTION', '[RIG] - REPEAT TO IMPROVE GRADE'])
MATRIC = two_sem() + NL + 'PUSAT PENTADBIRAN KERAJAAN PERSEKUTUAN 62604 PUTRAJAYA' + NL + 'www.moe.gov.my'
#: A Matriculation offer letter: the same division's header and college, none of a transcript's grid.
MATRIC_OFFER = NL.join([
    'KEMENTERIAN PENDIDIKAN MALAYSIA', 'BAHAGIAN MATRIKULASI', 'PUSAT PENTADBIRAN KERAJAAN PERSEKUTUAN',
    '62604 PUTRAJAYA', 'www.moe.gov.my', 'TAWARAN KEMASUKAN KE PROGRAM MATRIKULASI SESI 2026/2027',
    'NO. MATRIK : MS2615110001', 'KOLEJ MATRIKULASI PERAK', 'JURUSAN : SAINS', 'PENGARAH'])
#: A thin Matriculation page (cropped): the header and the grid's labels, no completion, no box.
MATRIC_THIN = NL.join(['BAHAGIAN MATRIKULASI', 'MATRICULATION DIVISION', 'TRANSKRIP AKADEMIK',
                       'KOLEJ MATRIKULASI PERAK', 'KOD KURSUS KREDIT GRED MATA NILAIAN'])


class TestTheScore(SimpleTestCase):
    def test_a_matric_transcript_is_genuine(self):
        sg = score(MATRIC)
        self.assertEqual((sg['status'], sg['type']), ('genuine', 'matric_transcript'))
        self.assertEqual(sg['probability'], 1.0)
        self.assertEqual(sg['model_version'], '1.21.0')

    def test_a_thin_matric_page_is_suspect(self):
        sg = score(MATRIC_THIN)
        self.assertEqual(sg['status'], 'suspect', sg['probability'])
        self.assertTrue(0.35 <= sg['probability'] < 0.70)

    def test_below_the_floor_is_not_scored_an_owner_question(self):
        """A Matriculation offer letter in this slot: below 0.35, left "not checked" — never fake."""
        from apps.scholarship.genuineness.results_doc import _norm_fold_upper_alnum, _score_list
        p = _score_list(matric_poly_doc.MATRIC_TRANSCRIPT_SIGNATURES, _norm_fold_upper_alnum(MATRIC_OFFER),
                        False, False)['probability']
        self.assertLess(p, 0.35)
        self.assertEqual(score(MATRIC_OFFER), {})

    def test_a_matric_result_slip_is_not_scored(self):
        slip = MATRIC.replace('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT',
                              'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP')
        self.assertEqual(score(slip), {})
        self.assertEqual(score(MATRIC + NL + 'Slip keputusan ini bukan transkrip akademik.'), {})

    def test_a_polytechnic_transcript_is_genuine(self):
        sg = score(POLY)
        self.assertEqual((sg['status'], sg['type']), ('genuine', 'poly_transcript'))

    def test_a_polytechnic_page_is_genuine_or_nothing(self):
        """One corpus sample: below genuine it is never suspect or fake — it stays unscored."""
        thin = NL.join(['ACADEMIC TRANSCRIPT', 'POLITEKNIK CONTOH SABAH',
                        'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI', 'DIPLOMA AGROTECHNOLOGY',
                        'CODE COURSE CREDIT GRADE REMARK', 'CGPA 3.40'])
        self.assertEqual(score(thin), {})
        slip = POLY.replace('ACADEMIC TRANSCRIPT (PROVISIONAL)', 'KEPUTUSAN PENILAIAN AKHIR SEMESTER')
        self.assertEqual(score(slip.replace('ACADEMIC TRANSCRIPT', 'KEPUTUSAN')), {})

    def test_other_diplomas_asasi_and_spm_are_not_scored(self):
        kk = POLY.replace('POLITEKNIK CONTOH SABAH', 'KOLEJ KOMUNITI CONTOH')
        for text in (UITM, kk, 'PUSAT ASASI SAINS ACADEMIC TRANSCRIPT CGPA 3.10',
                     'SIJIL PELAJARAN MALAYSIA 2024 BAHASA MELAYU A'):
            self.assertEqual(score(text), {}, text[:30])

    def test_a_diploma_that_names_no_polytechnic_is_not_scored(self):
        """The transcript's wording alone is not enough: the page must print a polytechnic's name."""
        other = POLY.replace('POLITEKNIK CONTOH SABAH', 'INSTITUT CONTOH').replace('POLYTECHNIC BOARD OF', 'BOARD OF')
        self.assertEqual(score(other), {})

    def test_the_lists_score_their_own_family_only(self):
        self.assertEqual(score(POLY)['type'], 'poly_transcript')
        self.assertNotIn('POLITEKNIK', MATRIC)
        self.assertEqual(score(MATRIC)['type'], 'matric_transcript')


class _Doc:
    def __init__(self, doc_type):
        self.doc_type = doc_type


class TestTheSlotCall(SimpleTestCase):
    def test_the_higher_slot_scores_matric_and_polytechnic(self):
        self.assertEqual(stpm_slot_genuineness(_Doc('higher_results'), MATRIC)['type'], 'matric_transcript')
        self.assertEqual(stpm_slot_genuineness(_Doc('higher_results'), POLY)['type'], 'poly_transcript')

    def test_the_semester_slot_stays_stpm_only(self):
        self.assertEqual(stpm_slot_genuineness(_Doc('semester_result'), MATRIC), {})

    def test_an_stpm_page_still_reads_stpm(self):
        stpm = 'MAJLIS PEPERIKSAAN MALAYSIA SIJIL TINGGI PERSEKOLAHAN MALAYSIA SLIP KEPUTUSAN PEPERIKSAAN STPM 2025'
        self.assertNotEqual(stpm_slot_genuineness(_Doc('higher_results'), stpm).get('type'), 'matric_transcript')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TestTheFloor(TestCase):
    """The TD-114 floor (never-scored anchor → Probable at best) lifts only for a SCORED page."""

    def _app_with(self, authenticity):
        student = make_student(name='Siti Aminah', nric='050101-14-1234', exam_type='matric',
                               results_exam_type='matric', higher_cgpa=3.29,
                               completed_qualifications=['spm', 'matric'])
        app = make_application('shortlisted', student=student)
        vf = {'fields': {'candidate_name': 'SITI AMINAH BINTI ALI', 'cgpa': '3.29'}, 'student_verdict': 'ok',
              'error': ''}
        if authenticity:
            vf['authenticity'] = authenticity
        ApplicantDocument.objects.create(application=app, doc_type='higher_results', results_kind='matric',
                                         storage_path='test/higher/m4', vision_fields=vf)
        return app

    def test_unscored_holds_the_floor_and_a_score_lifts_it(self):
        from apps.scholarship.higher_results import _scored
        from apps.scholarship.verdict_ladder import _genuineness_unscored
        before = self._app_with(None)
        self.assertTrue(_genuineness_unscored(before, ['higher_results']))
        sg = score(MATRIC)
        after = self._app_with({'status': sg['status'], 'reason': sg['reason'], 'doc_seen': sg['type'],
                                'probability': sg['probability'], 'model_version': sg['model_version']})
        self.assertFalse(_genuineness_unscored(after, ['higher_results']))
        self.assertTrue(_scored(after.documents.get(doc_type='higher_results')))

    def test_the_versions_moved(self):
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in MODEL_VERSION.split('.')), (1, 21, 0))
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'[-.]', VERDICT_ENGINE_VERSION)), (2026, 10, 29, 2))
