"""Matric/Diploma exact-read M2 — the deterministic Matriculation transcript reader (`matric_parse`).

Synthetic twins only: the SHAPE of the KPM academic transcript (Bahagian Matrikulasi header, one
block per semester closed by PNGS / GPA, the average box, one PNGK / CGPA, the STATUS line), never a
real student's data. Owner facts (2026-10-29): 1 year = 2 semesters, 2 years = 4; the FINAL CGPA is
the last cumulative figure after the last semester and may sit on the last page; production OCRs
page 1 of a scan only.
"""
import re

from django.test import SimpleTestCase, TestCase

from apps.scholarship import matric_parse
from apps.scholarship.higher_results import extract
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

NL = '\n'
HEADER = """KEMENTERIAN PENDIDIKAN MALAYSIA
MINISTRY OF EDUCATION MALAYSIA
BAHAGIAN MATRIKULASI
MATRICULATION DIVISION
TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT
NAMA / NAME : SITI AMINAH BINTI ALI
KOLEJ / COLLEGE : KOLEJ MATRIKULASI PERAK NO . KP / IC NO . : 050101141234
PERAK MATRICULATION COLLEGE NO . MATRIK / MATRIC NO . : MS2515110001
JURUSAN / MAJOR : SAINS JANTINA / GENDER : PEREMPUAN
SESI / SESSION : {session}
KOD KURSUS KREDIT GRED MATA NILAIAN
CODE COURSE CREDIT GRADE VALUE POINT"""

#: Semester I and II of a science programme: core 5-credit courses with points, English with a band.
SEM = {
    1: ['SEMESTER I', 'SB015 BIOLOGY 1 5 B+ 3.33', 'SC015 COMPUTER SCIENCE 1 5 A 4.00',
        'SK015 CHEMISTRY 1 5 B+ 3.33', 'SM015 MATHEMATICS 1 5 C+ 2.33', 'WE013 ENGLISH 1 3 B2',
        'WK002 KOKURIKULUM / CO - CURRICULUM 2 A', 'PNGS / GPA : 3.25'],
    2: ['SEMESTER II', 'SB025 BIOLOGY 2 5 A 4.00', 'SC025 COMPUTER SCIENCE 2 5 B+ 3.33',
        'SK025 CHEMISTRY 2 5 B 3.00', 'SM025 MATHEMATICS 2 5 B 3.00', 'WE023 ENGLISH 2 3 C1',
        'WM001 PENDIDIKAN MORAL / MORAL EDUCATION 1 A',
        'WP001 PENGAJIAN AM MATRIKULASI / MATRICULATION GENERAL STUDIES 1 A', 'PNGS / GPA : 3.33'],
    3: ['SEMESTER III', 'SB015 BIOLOGY 1 5 A- 3.67', 'SC015 COMPUTER SCIENCE 1 5 A- 3.67',
        'SK015 CHEMISTRY 1 5 B+ 3.33', 'SM015 MATHEMATICS 1 5 B+ 3.33', 'WE013 ENGLISH 1 3 B2',
        'PNGS / GPA : 3.50'],
    4: ['SEMESTER IV', 'SB025 BIOLOGY 2 5 A 4.00', 'SC025 COMPUTER SCIENCE 2 5 B+ 3.33',
        'SK025 CHEMISTRY 2 5 A- 3.67', 'SM025 MATHEMATICS 2 5 B+ 3.33', 'WE023 ENGLISH 2 3 C1',
        'WI001 PENDIDIKAN ISLAM / ISLAMIC EDUCATION 1 A', 'PNGS / GPA : 3.58'],
}
TAIL = ['PURATA GRED BAGI KURSUS TERAS DAN ENGLISH', 'AVERAGE GRADE FOR CORE COURSES AND ENGLISH',
        'BIOLOGY A-', 'ENGLISH B2', 'PNGK / CGPA : {cgpa}', 'STATUS : LULUS DAN TAMAT PROGRAM MATRIKULASI',
        'PASS AND COMPLETED MATRICULATION PROGRAMME', 'PENGARAH / DIRECTOR']
NOTE = ['Nota : PNGK dikira berdasarkan keputusan Semester III dan IV',
        'Note : CGPA is calculated based on Semester III and IV']


def two_sem(cgpa='3.29', **edit):
    """A 1-year (2-semester) transcript, one page. CGPA = (12.99 + 13.33) / 8 = 3.29."""
    lines = HEADER.format(session='2025/2026').splitlines() + SEM[1] + SEM[2] + [t.format(cgpa=cgpa) for t in TAIL]
    text = '\n'.join(lines)
    for old, new in edit.items():
        text = text.replace(old.replace('_', ' '), new)
    return text


def four_sem_pages(cgpa='3.54'):
    """A 2-year (4-semester) transcript over TWO pages: page 1 holds Semesters I-III, page 2
    Semester IV, the average box, the note and the FINAL CGPA = (14.00 + 14.33) / 8 = 3.54."""
    page1 = HEADER.format(session='2023/2024').splitlines() + ['SESI / SESSION 2022/2023'] + SEM[1] + SEM[2] + [
        'SESI / SESSION 2023/2024'] + SEM[3]
    page2 = SEM[4] + NOTE + [t.format(cgpa=cgpa) for t in TAIL]
    return '\n'.join(page1), '\n'.join(page2)


def as_words(text):
    """The same lines as Vision word boxes (a scan): one row per line, left to right."""
    words = []
    for i, line in enumerate(text.splitlines()):
        for j, tok in enumerate(line.split()):
            words.append({'text': tok, 'cx': 40 + j * 60, 'cy': 30 + i * 40, 'h': 20, 'angle': 0.0})
    return words


class TestTheReader(SimpleTestCase):
    def test_a_two_semester_transcript_reads_exact(self):
        got = matric_parse.parse(two_sem())
        self.assertEqual((got['candidate_name'], got['nric'], got['matric_no'], got['cgpa']),
                         ('SITI AMINAH BINTI ALI', '050101141234', 'MS2515110001', '3.29'))
        self.assertEqual(got['institution'], 'KOLEJ MATRIKULASI PERAK')
        self.assertEqual(got['cgpa_label'], 'PNGK/CGPA')
        # Review fix 1: only the CORE rows, each proven by its semester's sum — English's band and
        # the minor courses' letters count in no sum, so they are never read Exact.
        self.assertEqual([r['subject'] for r in got['results']][:4],
                         ['BIOLOGY 1', 'COMPUTER SCIENCE 1', 'CHEMISTRY 1', 'MATHEMATICS 1'])
        self.assertEqual(len(got['results']), 8)
        self.assertEqual(got['results'][3], {'subject': 'MATHEMATICS 1', 'grade': 'C+'})
        self.assertFalse([r for r in got['results'] if re.search(r'ENGLISH|KOKURIKULUM|MORAL|PENGAJIAN',
                                                                  r['subject'])])

    def test_a_scan_reads_the_same_from_word_boxes(self):
        self.assertEqual(matric_parse.parse('', as_words(two_sem()))['cgpa'], '3.29')

    def test_a_four_semester_transcript_over_two_pages_takes_the_final_cgpa(self):
        """A text layer is read whole: the CGPA on page 2, over Semesters III and IV as the note says."""
        p1, p2 = four_sem_pages()
        got = matric_parse.parse(p1 + '\n' + p2)
        self.assertEqual(got['cgpa'], '3.54')
        self.assertEqual(len(got['results']), 4 * 4)               # four core courses, four semesters

    def test_page_one_of_a_four_semester_scan_never_reports_a_semester_gpa(self):
        """Production OCRs page 1 of a scan: Semesters I-III, no final CGPA → None (Gemini)."""
        p1, _p2 = four_sem_pages()
        self.assertIsNone(matric_parse.parse('', as_words(p1)))
        self.assertIsNone(matric_parse.parse(p1))

    def test_the_final_cgpa_is_the_one_after_the_last_semester(self):
        p1, p2 = four_sem_pages()
        early = p1.replace('PNGS / GPA : 3.33', 'PNGS / GPA : 3.33\nPNGK / CGPA : 3.29')
        self.assertIsNone(matric_parse.parse(early + '\n' + p2))     # a cumulative mid-way: not this layout
        self.assertIsNone(matric_parse.parse(p1 + '\n' + p2.replace('PNGK / CGPA : 3.54',
                                                                    'PNGK / CGPA : 3.54 PNGK / CGPA : 3.50')))

    def test_four_semesters_need_the_note_that_names_the_counted_ones(self):
        p1, p2 = four_sem_pages()
        self.assertIsNone(matric_parse.parse(p1 + '\n' + p2.replace(NOTE[0], '').replace(NOTE[1], '')))
        # no note, and a CGPA that IS the mean of all four: still no guess at which semesters count
        no_note = four_sem_pages(cgpa='3.42')[1].replace(NOTE[0], '').replace(NOTE[1], '')
        self.assertIsNone(matric_parse.parse(p1 + '\n' + no_note))
        # 3.42 is the mean of all four semesters: not what the note says this CGPA counts
        self.assertIsNone(matric_parse.parse(p1 + '\n' + four_sem_pages(cgpa='3.42')[1]))

    def test_a_programme_is_two_or_four_semesters(self):
        p1, _p2 = four_sem_pages()
        # 3.29 is Semesters I + II: the sum would add up, the semester count does not
        three = p1 + '\n' + '\n'.join([t.format(cgpa='3.29') for t in TAIL])
        self.assertIsNone(matric_parse.parse(three))

    def test_a_completed_programme_only(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('LULUS DAN TAMAT', 'LULUS')))

    def test_an_unreadable_grade_falls_back(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('SK025 CHEMISTRY 2 5 B 3.00',
                                                               'SK025 CHEMISTRY 2 5 8 3.00')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('SK025 CHEMISTRY 2 5 B 3.00',
                                                               'SK025 CHEMISTRY 2 5 3.00')))

    def test_a_letter_and_point_that_disagree_fall_back(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('5 B 3.00', '5 B 3.33', 1)))
        # the point right and the letter misread: the GPA still adds up, the pair does not
        self.assertIsNone(matric_parse.parse(two_sem().replace('SK025 CHEMISTRY 2 5 B 3.00',
                                                               'SK025 CHEMISTRY 2 5 B+ 3.00')))

    def test_every_semester_gpa_and_the_cgpa_must_add_up(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('PNGS / GPA : 3.25', 'PNGS / GPA : 3.52')))
        self.assertIsNone(matric_parse.parse(two_sem(cgpa='3.28')))

    def test_grade_rules_per_course(self):
        """English carries a band and no point; a 1-2 credit course a letter and no point; a core
        course its point."""
        self.assertIsNone(matric_parse.parse(two_sem().replace('WE013 ENGLISH 1 3 B2', 'WE013 ENGLISH 1 3 A')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('2 A\n', '2 A 4.00\n', 1)))
        self.assertIsNone(matric_parse.parse(two_sem().replace('SC015 COMPUTER SCIENCE 1 5 A 4.00',
                                                               'SC015 COMPUTER SCIENCE 1 5 A')))

    def test_the_code_owns_the_credits_and_the_semester_number(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('SB015 BIOLOGY 1 5', 'SB015 BIOLOGY 1 4')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('SB015 BIOLOGY 1', 'SB015 BIOLOGY 2')))
        # a scan that drops the credit digit still reads; an O for 0 in the code is mended
        self.assertEqual(matric_parse.parse(two_sem().replace('SB025 BIOLOGY 2 5 A', 'SBO25 BIOLOGY 2 A'))['cgpa'],
                         '3.29')

    def test_a_semester_has_a_fixed_shape(self):
        """Review fix 2: a dropped row is refused even when the sum still adds up (straight A)."""
        straight = two_sem(cgpa='4.00').replace('B+ 3.33', 'A 4.00').replace('C+ 2.33', 'A 4.00').replace(
            'B 3.00', 'A 4.00').replace('PNGS / GPA : 3.25', 'PNGS / GPA : 4.00').replace(
            'PNGS / GPA : 3.33', 'PNGS / GPA : 4.00')
        self.assertEqual(matric_parse.parse(straight)['cgpa'], '4.00')
        self.assertIsNone(matric_parse.parse(straight.replace('SK015 CHEMISTRY 1 5 A 4.00' + NL, '')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('WE013 ENGLISH 1 3 B2' + NL, '')))
        self.assertIsNone(matric_parse.parse(two_sem().replace(
            'WE013 ENGLISH 1 3 B2', 'WE013 ENGLISH 1 3 B2' + NL + 'WE013 ENGLISH 1 3 B2')))

    def test_a_course_code_belongs_to_its_semester(self):
        """Odd semesters print xx01x codes, even ones xx02x; a minor xx00x course sits in either."""
        self.assertIsNone(matric_parse.parse(two_sem().replace('SB025 BIOLOGY 2', 'SB015 BIOLOGY 1')))
        kok = 'WK002 KOKURIKULUM / CO - CURRICULUM 2 A' + NL
        moved = two_sem().replace(kok, '').replace('WM001', kok + 'WM001')      # into Semester II
        self.assertEqual(matric_parse.parse(moved)['cgpa'], '3.29')

    def test_the_name_and_college_end_at_the_next_label(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace(
            'NAMA / NAME : SITI AMINAH BINTI ALI', 'NAMA / NAME : SITI AMINAH BINTI ALI PEREMPUAN')))
        got = matric_parse.parse(two_sem().replace(
            'KOLEJ / COLLEGE : KOLEJ MATRIKULASI PERAK NO . KP / IC NO . : 050101141234',
            'KOLEJ / COLLEGE : KOLEJ MATRIKULASI PERAK JANTINA / GENDER : PEREMPUAN' + NL
            + 'NO . KP / IC NO . : 050101141234'))
        self.assertEqual(got['institution'], 'KOLEJ MATRIKULASI PERAK')

    def test_a_second_page_that_repeats_the_header_falls_back(self):
        """A text layer whose page 2 prints the header again (a second NAMA row) reads two ways."""
        p1, p2 = four_sem_pages()
        repeat = NL.join(HEADER.format(session='2023/2024').splitlines()[:6])
        self.assertIsNone(matric_parse.parse(p1 + NL + repeat + NL + p2))

    def test_a_sign_vision_splits_into_its_own_box(self):
        words = as_words(two_sem())
        split = []
        for w in words:
            if w['text'] == 'B+':
                split += [{**w, 'text': 'B'}, {**w, 'text': '+', 'cx': w['cx'] + 15}]
            else:
                split.append(w)
        self.assertEqual(matric_parse.parse('', split)['results'][0], {'subject': 'BIOLOGY 1', 'grade': 'B+'})

    def test_an_unknown_course_falls_back(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('BIOLOGY 1', 'ASTRONOMY 1')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('BIOLOGY 1', 'BIOLOGY SALINAN 1')))

    def test_a_result_slip_is_not_a_transcript(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace(
            'TRANSKRIP AKADEMIK / ACADEMIC TRANSCRIPT',
            'SLIP KEPUTUSAN PEPERIKSAAN / EXAMINATION RESULT SLIP TRANSKRIP AKADEMIK')))

    def test_one_person_on_the_page(self):
        self.assertIsNone(matric_parse.parse(two_sem() + '\nDISAHKAN OLEH 800101015555'))
        self.assertIsNone(matric_parse.parse(two_sem().replace(
            'NAMA / NAME : SITI AMINAH BINTI ALI', 'NAMA / NAME : SITI AMINAH BINTI\nALI BIN ABU')))

    def test_the_header_fields_are_required(self):
        self.assertIsNone(matric_parse.parse(two_sem().replace('MS2515110001', 'MS25')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('KOLEJ MATRIKULASI PERAK', 'KOLEJ PERAK')))
        self.assertIsNone(matric_parse.parse(two_sem().replace('050101141234', '051399141234')))

    def test_never_raises(self):
        self.assertIsNone(matric_parse.parse(None, [{'bad': 1}]))


class TestTheWiring(TestCase):
    def _doc(self):
        student = make_student(name='Siti Aminah', nric='050101-14-1234', exam_type='matric',
                               results_exam_type='matric', higher_cgpa=3.29,
                               completed_qualifications=['spm', 'matric'])
        app = make_application('shortlisted', student=student)
        return ApplicantDocument.objects.create(application=app, doc_type='higher_results',
                                                storage_path='test/higher/matric', results_kind='matric')

    def test_a_matric_transcript_is_read_exact_without_gemini(self):
        calls = []
        ex = extract(self._doc(), {'text': two_sem(), 'words': None}, lambda: calls.append('image'),
                     lambda *a, **kw: calls.append('gemini'))
        self.assertEqual(calls, [])
        self.assertEqual((ex['capture'], ex['parser_version']),
                         ('deterministic', f'matric_parse {matric_parse.PARSER_VERSION}'))
        self.assertEqual(ex['fields']['cgpa'], '3.29')
        self.assertEqual(ex['fields']['results_kind_detected'], 'matric')
        self.assertNotIn('stpm_rows_from_entry', ex)

    def test_an_unsure_read_falls_back_to_gemini(self):
        calls = []
        ex = extract(self._doc(), {'text': two_sem(cgpa='3.28'), 'words': None}, lambda: None,
                     lambda text, dt, **kw: calls.append('gemini') or {'fields': {'cgpa': '3.28'},
                                                                      'warnings': [], 'error': ''})
        self.assertEqual((calls, ex['capture']), (['gemini'], 'ai'))

    def test_an_stpm_or_diploma_page_never_reaches_the_matric_reader(self):
        from unittest.mock import patch
        def gem(text, dt, **kw):
            return {'fields': {'cgpa': '3.1'}, 'warnings': [], 'error': ''}
        for text in ('SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025 PNGK 3.50',
                     'ACADEMIC TRANSCRIPT POLITEKNIK SANDAKAN DIPLOMA CGPA 3.66'):
            with patch('apps.scholarship.matric_parse.parse') as reader:
                extract(self._doc(), {'text': text, 'words': None}, lambda: None, gem)
            reader.assert_not_called()
        with patch('apps.scholarship.matric_parse.parse', return_value=None) as reader:   # the control
            extract(self._doc(), {'text': two_sem(), 'words': None}, lambda: None, gem)
        reader.assert_called_once()

    def test_the_model_version_moved(self):
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'\.', MODEL_VERSION)), (1, 19, 0))
