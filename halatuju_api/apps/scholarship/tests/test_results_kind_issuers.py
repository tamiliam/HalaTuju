"""Matric/Diploma exact-read M1 (2026-10-29) — a transcript whose title names no kind ("ACADEMIC
TRANSCRIPT") is still told by its fixed issuer / subject markers; and the blank-kind backfill.

Roadmap: docs/plans/2026-10-29-matric-diploma-exact-read-roadmap.md §M1. BrightPath #49's shape: a
Matriculation transcript in the SPM card, read by the SPM slip's schema — title "ACADEMIC
TRANSCRIPT", subject rows, no CGPA, no institution — named nothing, so it was SPM-compared.

Synthetic text only: the shapes of the corpus pages, never their data.
"""
import io

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.scholarship import results_kind, wrong_slip
from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.genuineness.stpm_doc import stpm_higher_genuineness
from apps.scholarship.higher_results import extract, student_higher_check
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

MATRIC_TRANSCRIPT = ('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT\nKOLEJ MATRIKULASI LABUAN\n'
                     'MATHEMATICS 1 A\nPENGAJIAN AM MATRIKULASI/ MATRICULATION GENERAL STUDIES A-\n'
                     'PNGK/CGPA 3.54')
POLY_TRANSCRIPT = ('ACADEMIC TRANSCRIPT (PROVISIONAL)\nPOLITEKNIK SANDAKAN SABAH\n'
                   'MATHEMATICS FOR TECHNOLOGY A\nCUMULATIVE GRADE POINT AVERAGE (CGPA) 3.66')
#: #49: the SPM card's read of a Matriculation transcript (the SPM slip schema has no institution).
MATRIC_IN_SPM_CARD = {'candidate_name': 'PRIYA', 'exam': 'ACADEMIC TRANSCRIPT',
                      'results': [{'subject': 'BIOLOGY 1', 'grade': 'A', 'band': ''},
                                  {'subject': 'PENGAJIAN AM MATRIKULASI/ MATRICULATION GENERAL STUDIES',
                                   'grade': 'A-', 'band': ''}]}
SPM = {f'sub{i}': 'A' for i in range(10)}


class TestTheIssuerTier(SimpleTestCase):
    def test_a_matric_transcript_read_names_its_college_red_first(self):
        """Blank before M1: the read's title says only "ACADEMIC TRANSCRIPT"."""
        self.assertEqual(results_kind.detect_from_fields(
            {'exam': 'ACADEMIC TRANSCRIPT', 'institution': 'KOLEJ MATRIKULASI LABUAN'}), 'matric')
        self.assertEqual(results_kind.detect_from_fields(
            {'exam': 'ACADEMIC TRANSCRIPT', 'institution': 'LABUAN MATRICULATION COLLEGE'}), 'matric')

    def test_49_shape_the_fixed_subject_names_a_matric_transcript(self):
        self.assertEqual(results_kind.detect_from_fields(MATRIC_IN_SPM_CARD), 'matric')

    def test_a_polytechnic_transcript_with_no_diploma_word(self):
        self.assertEqual(results_kind.detect(POLY_TRANSCRIPT), 'diploma')
        self.assertEqual(results_kind.detect('ACADEMIC TRANSCRIPT\nSANDAKAN POLYTECHNIC\nCGPA 3.1'), 'diploma')
        self.assertEqual(results_kind.detect_from_fields(
            {'exam': 'ACADEMIC TRANSCRIPT (PROVISIONAL)', 'institution': 'POLITEKNIK KOTA KINABALU'}),
            'diploma')

    def test_the_matric_transcript_text_still_reads_matric(self):
        self.assertEqual(results_kind.detect(MATRIC_TRANSCRIPT), 'matric')

    def test_a_kind_marker_beats_an_issuer(self):
        """The tier is read only when no kind marker is printed: an STPM page naming a polytechnic
        stays STPM — so the STPM genuineness gate (`detect(...) == 'stpm'`) never moves."""
        stpm = 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025\nPUSAT: POLITEKNIK X\nPNGK 3.50'
        self.assertEqual(results_kind.detect(stpm), 'stpm')
        self.assertEqual(results_kind.detect('ASASI SAINS\nPOLITEKNIK X\nCGPA 3.2'), 'asasi')

    def test_an_spm_page_never_flips_to_an_issuer(self):
        """An SPM slip printing a polytechnic (an exam centre) stays SPM; with a CGPA, cannot tell."""
        self.assertEqual(results_kind.detect('SIJIL PELAJARAN MALAYSIA 2024\nPOLITEKNIK X\nBAHASA MELAYU A'),
                         'spm')
        self.assertEqual(results_kind.detect('SIJIL PELAJARAN MALAYSIA\nPOLITEKNIK X\nCGPA 3.0'), '')
        self.assertEqual(results_kind.detect_from_fields(
            {'exam': 'SIJIL PELAJARAN MALAYSIA 2024',
             'results': [{'subject': 'MATRICULATION GENERAL STUDIES'}]}), 'spm')

    def test_two_issuers_cannot_tell(self):
        self.assertEqual(results_kind.detect_from_fields(
            {'exam': 'ACADEMIC TRANSCRIPT', 'institution': 'POLITEKNIK X',
             'results': [{'subject': 'MATRICULATION GENERAL STUDIES'}]}), '')

    def test_subject_rows_feed_the_fixed_subject_only(self):
        """A subject name is never read for KIND words: "FOUNDATION MATHEMATICS" on a diploma is
        not Asasi, "DIPLOMA PROJECT" not a Diploma marker."""
        for subject in ('FOUNDATION MATHEMATICS', 'DIPLOMA PROJECT'):
            self.assertEqual(results_kind.detect_from_fields(
                {'exam': 'ACADEMIC TRANSCRIPT', 'results': [{'subject': subject}]}), '', subject)

    def test_whole_words_and_nothing_to_read(self):
        self.assertEqual(results_kind.detect('ACADEMIC TRANSCRIPT POLITEKNIKAL'), '')
        self.assertEqual(results_kind.detect('ACADEMIC TRANSCRIPT CGPA 3.0'), '')
        self.assertEqual(results_kind.detect_from_fields({'exam': 'ACADEMIC TRANSCRIPT',
                                                          'results': 'not a list'}), '')
        self.assertEqual(results_kind.detect_from_fields(None), '')

    def test_no_issuer_tier_answers_stpm(self):
        self.assertNotIn('stpm', results_kind._ISSUERS)
        self.assertNotIn('stpm', results_kind._FIXED_SUBJECTS)

    def test_a_polytechnic_page_is_not_scored_as_stpm(self):
        self.assertEqual(stpm_higher_genuineness(POLY_TRANSCRIPT), {})


def _app(**profile):
    student = make_student(name='Priya', nric='030101-14-1234', **profile)
    return make_application('shortlisted', student=student)


def _doc(app, doc_type, fields, **kw):
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'test/{doc_type}/{len(str(fields))}',
        vision_fields={'fields': fields, 'student_verdict': 'ok', 'error': ''}, **kw)


class TestTheReaders(TestCase):
    def test_49_the_spm_card_names_a_matric_transcript_and_compares_nothing(self):
        app = _app(exam_type='spm', results_exam_type='spm', grades=SPM)
        doc = _doc(app, 'results_slip', MATRIC_IN_SPM_CARD)
        self.assertEqual(wrong_slip.higher_kind(doc), 'matric')
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results'], chk['higher_kind']),
                         ('not_spm', 'not_spm', 'matric'))
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        self.assertGreaterEqual(VERDICT_ENGINE_VERSION, '2026-10-29.1')    # the SPM card's band can move

    def test_the_upload_read_falls_back_to_the_institution(self):
        """No OCR text (an image the shared read missed): the Gemini read's institution decides."""
        app = _app(exam_type='diploma', results_exam_type='diploma', grades=SPM, higher_cgpa=3.66,
                   completed_qualifications=['spm', 'diploma'])
        doc = _doc(app, 'higher_results', {}, results_kind='diploma')
        ex = extract(doc, {'text': ''}, lambda: None, lambda text, dt, **kw: {
            'fields': {'candidate_name': 'PRIYA', 'exam': 'ACADEMIC TRANSCRIPT (PROVISIONAL)',
                       'institution': 'POLITEKNIK SANDAKAN SABAH', 'cgpa': '3.66'},
            'warnings': [], 'error': ''})
        self.assertEqual(ex['fields']['results_kind_detected'], 'diploma')
        doc.vision_fields = {'fields': ex['fields'], 'student_verdict': 'ok', 'error': ''}
        self.assertEqual(student_higher_check(doc)['kind_status'], 'match')


class TestTheBlankKindBackfill(TestCase):
    def _run(self, *args):
        out = io.StringIO()
        call_command('backfill_higher_results_kind', *args, stdout=out)
        return out.getvalue()

    def test_report_first_then_fills_from_the_results_held(self):
        app = _app(exam_type='stpm', results_exam_type='stpm', grades=SPM,
                   stpm_grades={'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-'},
                   completed_qualifications=['spm', 'stpm'])
        doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'stpm'})
        before = student_higher_check(doc)
        out = self._run()
        self.assertIn(f'doc {doc.id} app {app.id}: held=stpm detected=stpm -> fill', out)
        self.assertIn('REPORT ONLY', out)
        doc.refresh_from_db()
        self.assertEqual(doc.results_kind, '')
        self.assertIn('1 row(s) written', self._run('--apply'))
        doc.refresh_from_db()
        self.assertEqual(doc.results_kind, 'stpm')
        self.assertEqual(student_higher_check(doc), before)          # verdict-neutral
        self.assertIn('0 row(s) written', self._run('--apply'))      # idempotent

    def test_never_from_the_detection(self):
        """An SPM holder's polytechnic transcript (live #317's shape): '' IS its value (D13)."""
        app = _app(exam_type='spm', results_exam_type='spm', grades=SPM)
        doc = _doc(app, 'higher_results', {'candidate_name': 'PRIYA', 'results_kind_detected': 'diploma'})
        out = self._run('--apply')
        self.assertIn('held=- detected=diploma -> leave: holds no tertiary results (D13)', out)
        doc.refresh_from_db()
        self.assertEqual(doc.results_kind, '')

    def test_only_live_blank_higher_results_rows(self):
        app = _app(exam_type='matric', results_exam_type='matric', grades=SPM, higher_cgpa=3.5,
                   completed_qualifications=['spm', 'matric'])
        kept = _doc(app, 'higher_results', {}, results_kind='stpm')
        slip = _doc(app, 'results_slip', {})
        out = self._run('--apply')
        self.assertNotIn(f'doc {kept.id} ', out)
        self.assertNotIn(f'doc {slip.id} ', out)
        kept.refresh_from_db()
        self.assertEqual(kept.results_kind, 'stpm')
