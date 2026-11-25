"""TD-735 (25 Nov 2026): the year on a Matriculation, Asasi or Diploma student's merit bracket.

Owner defaults: the year is the session's END year ("2024/2025" gives 2025); free sources only (the
upload's OCR text, else the document's own title); no guess. Stored beside the read as
`vision_fields.exam_year_read`, never in its fields, and DISPLAY ONLY. STPM and SPM do not change.
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.exam_years import (TRANSCRIPT_YEAR_READER, read_transcript_year, stored_transcript_year,
                                         title_year, transcript_year)
from apps.scholarship.higher_results import extract, student_higher_check
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.read_errors import EMPTY_ANSWER
from apps.scholarship.tests.factories import create_document, make_application, make_cohort, make_student
from apps.scholarship.tests.test_matric_parse import four_sem_pages, two_sem
from apps.scholarship.tests.test_poly_diploma_parse import transcript
from apps.scholarship.vision.field_extraction import _build_read_result, _empty_answer_failed

READER = f'transcript_year {TRANSCRIPT_YEAR_READER}'


class TestTheReader(SimpleTestCase):
    def test_a_matric_session_gives_its_end_year(self):
        self.assertEqual(transcript_year('SESI / SESSION : 2024/2025'), ('2025', 'session'))
        self.assertEqual(transcript_year('SESI AKADEMIK 2024/2025'), ('2025', 'session'))
        self.assertEqual(transcript_year('Academic Session: 2024/25'), ('2025', 'session'))
        self.assertEqual(transcript_year(two_sem()), ('2026', 'session'))

    def test_conflicting_sessions_take_the_latest(self):
        page1, page2 = four_sem_pages()
        self.assertEqual(transcript_year(page1 + '\n' + page2), ('2024', 'session'))
        self.assertEqual(transcript_year('SESI 2024/2025\nSESI 2022/2023'), ('2025', 'session'))

    def test_a_polytechnic_takes_its_last_semester(self):
        self.assertEqual(transcript_year(transcript()), ('2024', 'semester'))
        self.assertEqual(transcript_year('FIRST SEMESTER (I : 2021/2022)\nTHIRD SEMESTER (I : 2022/2023)'),
                         ('2023', 'semester'))

    def test_an_intake_session_alone_is_no_year(self):
        for text in ('INTAKE SESSION : 2021/2022', 'SESI AMBILAN 2024/2025', 'Sesi Kemasukan 2023/2024',
                     'INTAKE SESSION\nPROGRAMME : DIPLOMA\n : I : 2021/2022'):
            with self.subTest(text=text):
                self.assertEqual(transcript_year(text), ('', ''))

    def test_a_print_date_or_a_bare_year_is_no_year(self):
        for text in ('TARIKH / DATE : 12/03/2025', 'Printed 2025', 'CGPA 3.50 2024 2025', '2024/2025',
                     'SESSION 2024/2027', ''):
            with self.subTest(text=text):
                self.assertEqual(transcript_year(text), ('', ''))
        self.assertEqual(transcript_year(None), ('', ''))

    def test_a_span_of_two_session_pairs_is_no_year(self):
        self.assertEqual(transcript_year('SESI 2023/2024 - 2024/2025'), ('', ''))
        self.assertEqual(transcript_year('SESI 2023/2024 – 2024/2025'), ('', ''))
        self.assertEqual(title_year('MATRIKULASI 2024/2025 - 2025/2026'), ('', ''))
        self.assertEqual(transcript_year('SESI 2024/2025'), ('2025', 'session'))      # a single pair still reads
        self.assertEqual(title_year('MATRIKULASI 2024/2025'), ('2025', 'title'))

    def test_the_title_reads_a_session_pair_only(self):
        self.assertEqual(title_year('KEPUTUSAN PROGRAM MATRIKULASI SESI 2024/2025'), ('2025', 'title'))
        self.assertEqual(title_year('ASASI SAINS 2023/24'), ('2024', 'title'))
        for title in ('TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT', 'MATRIKULASI 2025', '', None):
            with self.subTest(title=title):
                self.assertEqual(title_year(title), ('', ''))

    def test_the_stored_read_takes_the_text_first_then_the_title(self):
        self.assertEqual(read_transcript_year('SESI 2024/2025', 'X 2020/2021'),
                         {'year': '2025', 'label': 'session', 'reader': READER})
        self.assertEqual(read_transcript_year('no year here', 'X 2020/2021'),
                         {'year': '2021', 'label': 'title', 'reader': READER})
        self.assertEqual(read_transcript_year('', ''), {'year': '', 'label': '', 'reader': READER})

    def test_the_served_year_is_the_stored_read_else_the_stored_title(self):
        self.assertEqual(stored_transcript_year({'exam_year_read': {'year': '2025'}}, {}), '2025')
        self.assertEqual(stored_transcript_year({}, {'exam': 'MATRIKULASI 2024/2025'}), '2025')   # read before TD-735
        self.assertEqual(stored_transcript_year({'exam_year_read': {'year': ''}}, {'exam': 'X'}), '')
        self.assertEqual(stored_transcript_year({'exam_year_read': {'year': 'junk'}}, {}), '')
        self.assertEqual(stored_transcript_year(None, None), '')


def _wiring_doc(kind):
    student = make_student(name='Siti Aminah', nric='050101-14-1234', exam_type=kind, results_exam_type=kind,
                           higher_cgpa=3.29, completed_qualifications=['spm', kind])
    app = make_application('shortlisted', student=student)
    return ApplicantDocument.objects.create(application=app, doc_type='higher_results',
                                            storage_path=f'test/higher/{kind}', results_kind=kind)


def _no_gemini(*a, **kw):
    raise AssertionError('no AI call')


class TestTheExtractStoresTheYear(TestCase):
    def test_an_exact_matric_read(self):
        ex = extract(_wiring_doc('matric'), {'text': two_sem(), 'words': None}, lambda: None, _no_gemini)
        self.assertEqual(ex['capture'], 'deterministic')
        self.assertEqual(ex['exam_year_read'], {'year': '2026', 'label': 'session', 'reader': READER})
        self.assertNotIn('exam_year_read', ex['fields'])

    def test_an_exact_polytechnic_read(self):
        ex = extract(_wiring_doc('diploma'), {'text': transcript(), 'words': None}, lambda: None, _no_gemini)
        self.assertEqual(ex['exam_year_read']['year'], '2024')

    def test_an_ai_read_with_the_year_in_its_title(self):
        def gem(text, dt, **kw):
            return {'fields': {'cgpa': '3.10', 'exam': 'KEPUTUSAN ASASI 2024/2025', 'candidate_name': 'SITI'},
                    'warnings': [], 'error': ''}
        ex = extract(_wiring_doc('asasi'), {'text': 'ASASI SAINS CGPA 3.10', 'words': None}, lambda: None, gem)
        self.assertEqual(ex['capture'], 'ai')
        self.assertEqual(ex['exam_year_read'], {'year': '2025', 'label': 'title', 'reader': READER})

    def test_an_ai_read_with_no_year_stores_an_empty_stamped_read(self):
        def gem(text, dt, **kw):
            return {'fields': {'cgpa': '3.10'}, 'warnings': [], 'error': ''}
        ex = extract(_wiring_doc('asasi'), {'text': 'ASASI SAINS CGPA 3.10 2025', 'words': None}, lambda: None, gem)
        self.assertEqual(ex['exam_year_read'], {'year': '', 'label': '', 'reader': READER})

    def test_a_blank_ai_answer_stores_nothing(self):
        def gem(text, dt, **kw):
            return {'fields': {}, 'warnings': [], 'error': ''}
        ex = extract(_wiring_doc('matric'), {'text': 'SESI 2024/2025', 'words': None}, lambda: None, gem)
        self.assertNotIn('exam_year_read', ex)

    def test_stpm_is_untouched(self):
        def gem(text, dt, **kw):
            return {'fields': {'cgpa': '3.50', 'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025'},
                    'warnings': [], 'error': ''}
        ex = extract(_wiring_doc('stpm'), {'text': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025 PNGK 3.50 SESI 2024/2025',
                                           'words': None}, lambda: None, gem)
        self.assertEqual(ex['fields']['results_kind_detected'], 'stpm')
        self.assertNotIn('exam_year_read', ex)

    def test_the_read_result_keeps_it_beside_the_fields(self):
        stored = {'year': '2025', 'label': 'session', 'reader': READER}
        ex = {'fields': {'candidate_name': 'SITI AMINAH', 'cgpa': '3.29'}, 'warnings': [], 'error': '',
              'capture': 'deterministic', 'exam_year_read': stored}
        vf = _build_read_result(ApplicantDocument(doc_type='higher_results'), ex, names=['SITI AMINAH'],
                                postcode='', city='', street='', check_address=False)
        self.assertEqual(vf['exam_year_read'], stored)
        self.assertNotIn('exam_year_read', vf['fields'])

    def test_an_all_blank_answer_stays_an_empty_read(self):
        """The stored year sits outside the fields, so it never makes a blank AI answer count as read."""
        ex = {'fields': {'candidate_name': '', 'cgpa': ''}, 'warnings': [], 'error': '', 'capture': 'ai',
              'exam_year_read': {'year': '2025', 'label': 'title', 'reader': READER}}
        failed = _empty_answer_failed(ex)
        self.assertEqual((failed['fields'], failed['error']), ({}, EMPTY_ANSWER))


def _app(route, cohort_year=2026):
    return make_application('profile_complete', cohort=make_cohort(year=cohort_year),
                            student=make_student(results_exam_type=route))


def _doc(app, kind, fields=None, **vf):
    fields = {'candidate_name': 'SITI', 'cgpa': '3.29', 'results_kind_detected': kind, **(fields or {})}
    return create_document(application=app, doc_type='higher_results', storage_path=f'{app.id}/h/x',
                           vision_run_at=timezone.now(), results_kind=kind,
                           vision_fields={'fields': fields, 'student_verdict': 'ok', 'warnings': [], 'error': '', **vf})


def _year(doc):
    chk = student_higher_check(doc)
    return chk['exam_year'], chk['exam_year_status']


def _read(year):
    return {'exam_year_read': {'year': year, 'label': 'session', 'reader': READER}}


class TestTheServe(TestCase):
    def test_matric_and_asasi_expect_the_cohort_year(self):
        for kind in ('matric', 'asasi'):
            with self.subTest(kind=kind):
                app = _app(kind)
                self.assertEqual(_year(_doc(app, kind, **_read('2026'))), ('2026', 'current'))
                self.assertEqual(_year(_doc(app, kind, **_read('2025'))), ('2025', 'off'))

    def test_a_diploma_accepts_either_year(self):
        app = _app('diploma')
        self.assertEqual([_year(_doc(app, 'diploma', **_read(y))) for y in ('2025', '2026', '2024')],
                         [('2025', 'current'), ('2026', 'current'), ('2024', 'off')])

    def test_no_year_read_is_bare(self):
        app = _app('matric')
        self.assertEqual(_year(_doc(app, 'matric', **_read(''))), ('', ''))
        self.assertEqual(_year(_doc(app, 'matric', {'exam': 'TRANSKRIP AKADEMIK'})), ('', ''))

    def test_a_document_read_before_td735_falls_back_to_its_title(self):
        app = _app('matric')
        self.assertEqual(_year(_doc(app, 'matric', {'exam': 'PROGRAM MATRIKULASI SESI 2025/2026'})),
                         ('2026', 'current'))

    def test_an_unreadable_read_serves_no_year(self):
        app = _app('matric')
        doc = create_document(application=app, doc_type='higher_results', storage_path=f'{app.id}/h/u',
                              vision_run_at=timezone.now(), results_kind='matric',
                              vision_fields={'fields': {'results_kind_detected': 'matric'}, 'student_verdict': 'ok',
                                             'warnings': [], 'error': '', **_read('2026')})
        self.assertEqual(_year(doc)[0], '')

    def test_stpm_serve_is_unchanged(self):
        app = _app('stpm')
        doc = _doc(app, 'stpm', {'exam': 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025'}, **_read('2019'))
        self.assertEqual(_year(doc), ('2025', 'current'))     # the stored transcript read is never consulted


class TestTheServeNeedsTheHeldKind(TestCase):
    def test_a_different_detected_kind_serves_no_year(self):
        for held, detected in (('matric', 'stpm'), ('stpm', 'matric'), ('stpm', 'diploma'), ('matric', 'diploma')):
            with self.subTest(held=held, detected=detected):
                doc = _doc(_app(held), held, {'results_kind_detected': detected}, **_read('2026'))
                self.assertEqual(_year(doc)[0], '')

    def test_matching_kinds_serve_the_year(self):
        for kind in ('matric', 'asasi', 'diploma'):
            with self.subTest(kind=kind):
                self.assertEqual(_year(_doc(_app(kind), kind, **_read('2026')))[0], '2026')
