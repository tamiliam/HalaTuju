"""Matric/Diploma exact-read M3 — the deterministic polytechnic Diploma transcript reader.

Synthetic twins only: the SHAPE of the JPPKK polytechnic academic transcript as production's text
layer (pypdf 5.9.0) lays it out — each header value printed BEFORE its label (" : VALUENAME"), and
the two-column page's summary boxes out of step with their semesters — never a real student's data.
Owner facts (2026-10-29): a polytechnic Diploma runs 5 or 6 semesters; the FINAL CGPA is the last
cumulative figure, never a semester GPA nor the first CGPA met.
"""
import re
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.scholarship import poly_diploma_parse
from apps.scholarship.higher_results import extract
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

NL = '\n'
POINTS = {'A+': '4.00', 'A': '4.00', 'A-': '3.67', 'B+': '3.33', 'B': '3.00', 'B-': '2.67'}
#: Five graded semesters (credits, grade) and a sixth of industrial training (9 credits).
SEMS = [
    [('DBM10133', 'MATHEMATICS FOR TECHNOLOGY', 3, 'A'), ('DBS10022', 'BIOLOGICAL SCIENCE', 2, 'B+'),
     ('DUE10012', 'COMMUNICATIVE ENGLISH 1', 2, 'A-'), ('MPU24651', 'PISPA 1', 1, 'A')],
    [('DYA20033', 'CROP PROTECTION', 3, 'A'), ('DYA20044', 'CROP PRODUCTION SYSTEM', 4, 'B'),
     ('MPU23042', 'NILAI MASYARAKAT MALAYSIA**', 2, 'A-')],
    [('DUE30022', 'COMMUNICATIVE ENGLISH 2', 2, 'B+'),
     ('DYA30083', 'BASIC ROBOTIC AND AUTOMATION IN AGRICULTURE', 3, 'A-'), ('MPU24850', 'PISPA 3', 0, 'A')],
    [('DYA40124', 'INDUSTRIAL CROP PRODUCTION SYSTEM', 4, 'A-'), ('DYA40133', 'PLANT TISSUE CULTURE', 3, 'B-')],
    [('DYA50154', 'AGRICULTURE PROJECT 2', 4, 'A+'), ('DYA50173', 'POST HARVEST TECHNOLOGY', 3, 'B+')],
]
ORD = ('FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH')
SESSIONS = ('I : 2021/2022', 'II : 2021/2022', 'I : 2022/2023', 'II : 2022/2023', 'I : 2023/2024',
            'II : 2023/2024')


def _r(x):
    return str(Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _row_lines(code, name, cr, grade):
    if len(name) > 36:                       # a long name wraps, its credit + grade on their own line
        head, tail = name.rsplit(' ', 1)
        return [f'{code} {head}', tail, f'{cr}.0 {grade}']
    return [f'{code} {name} {cr}.0 {grade}']


def boxes(sems=SEMS, training=9):
    """The summary boxes, recomputed: [(gpa or None, cgpa, earned, running total)]."""
    out, pts, crs, run = [], Decimal(0), Decimal(0), Decimal(0)
    for rows in sems:
        sp = sum(Decimal(cr) * Decimal(POINTS[g]) for _c, _n, cr, g in rows)
        sc = sum(Decimal(cr) for _c, _n, cr, _g in rows)
        pts, crs, run = pts + sp, crs + sc, run + sc
        out.append((_r(sp / sc), _r(pts / crs), sc, run))
    if training:
        run += training
        out.append((None, _r(pts / crs), Decimal(training), run))
    return out


def _box_lines(box, programme):
    gpa, cgpa, earned, total = box
    return ([f': {gpa}Grade Point Average (GPA)'] if gpa else []) + [
        'Cumulative Grade Point Average (CGPA)', 'Credit Earned', 'Total Credits',
        f': {cgpa}', f': {earned:.1f}', f': {total:.1f} / {programme:.1f}']


def transcript(sems=SEMS, training=9, title='ACADEMIC TRANSCRIPT (PROVISIONAL)', boxes_at_end=False,
               status='COMPLETED', programme=None, edit=None):
    """The text layer production reads. Boxes sit BEFORE their semester header (as the real one's
    left column), or all at the end (`boxes_at_end`) — the reader pairs them by running total."""
    bx = boxes(sems, training)
    programme = programme if programme is not None else bx[-1][3]
    lines = ['PROVISIONAL', title, ' : SITI AMINAH BINTI ALINAME', ' : 21DAG21F1001REG.NO',
             ' : 030101-12-1234IC NO', 'PROGRAMME', 'INTAKE SESSION', f'STATUS  : {status}',
             ' : DIPLOMA AGROTECHNOLOGY', ' : I : 2021/2022', 'POLITEKNIK CONTOH SABAH',
             'JALAN CONTOH, 90000, SANDAKAN, SABAH', 'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI',
             'CODE COURSE CREDIT GRADE REMARK']
    for k, rows in enumerate(sems):
        if not boxes_at_end:
            lines += _box_lines(bx[k], programme)
        lines.append(f'{ORD[k]} SEMESTER ({SESSIONS[k]})')
        for row in rows:
            lines += _row_lines(*row)
    if training:
        if not boxes_at_end:
            lines += _box_lines(bx[-1], programme)
        lines += [f'{ORD[len(sems)]} SEMESTER ({SESSIONS[len(sems)]}) - INDUSTRIAL TRAINING',
                  ': CONTOH SDN BHD, SANDAKAN', 'Company', 'Duration : 05 JANUARI 2024 - 22 MEI 2024.',
                  'Remarks : EXCELLENT']
    if boxes_at_end:
        lines = lines[:lines.index('CODE COURSE CREDIT GRADE REMARK') + 1] + [
            ln for b in bx for ln in _box_lines(b, programme)] + lines[lines.index('CODE COURSE CREDIT GRADE REMARK') + 1:]
    lines += ['~~~~~End of results~~~~~', 'NO ALTERATION OR ADDITION IS HEREBY AUTHORIZED.']
    text = NL.join(lines)
    for old, new in (edit or {}).items():
        text = text.replace(old, new)
    return text


class TestTheReader(SimpleTestCase):
    def test_the_synthetic_sums_are_what_a_hand_works_out(self):
        # S1: 3x4.00 + 2x3.33 + 2x3.67 + 1x4.00 = 30.00 / 8 = 3.75; the final 127.69 / 36 = 3.55.
        self.assertEqual(boxes()[0][0], '3.75')
        self.assertEqual(boxes()[-1][1], '3.55')

    def test_a_polytechnic_transcript_reads_exact(self):
        got = poly_diploma_parse.read_poly_transcript(transcript())
        self.assertEqual((got['candidate_name'], got['nric'], got['reg_no'], got['cgpa']),
                         ('SITI AMINAH BINTI ALI', '030101121234', '21DAG21F1001', '3.55'))
        self.assertEqual((got['institution'], got['cgpa_label'], got['exam']),
                         ('POLITEKNIK CONTOH SABAH', 'CGPA', 'ACADEMIC TRANSCRIPT (PROVISIONAL)'))
        subjects = [r['subject'] for r in got['results']]
        self.assertIn('BASIC ROBOTIC AND AUTOMATION IN AGRICULTURE', subjects)   # a wrapped name
        self.assertIn('PISPA 1', subjects)                                      # 1 credit: proven
        self.assertNotIn('PISPA 3', subjects)                                   # 0 credits: no sum proves it
        self.assertEqual(len(subjects), 14 - 1)

    def test_the_boxes_pair_by_running_total_not_position(self):
        self.assertEqual(poly_diploma_parse.read_poly_transcript(transcript(boxes_at_end=True))['cgpa'], '3.55')

    def test_a_final_transcript_and_a_five_semester_programme(self):
        self.assertEqual(poly_diploma_parse.read_poly_transcript(transcript(title='ACADEMIC TRANSCRIPT'))['cgpa'], '3.55')
        self.assertEqual(poly_diploma_parse.read_poly_transcript(transcript(training=0))['cgpa'], '3.55')

    def test_a_scan_is_never_read(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(), [{'text': 'X', 'cx': 1, 'cy': 1, 'h': 1}]))

    def test_a_dropped_row_refuses(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            'DYA40133 PLANT TISSUE CULTURE 3.0 B-' + NL: ''})))
        # straight A: every GPA and CGPA is 4.00 with or without the row — only the credits catch it
        straight = [[(c, n, cr, 'A') for c, n, cr, _g in rows] for rows in SEMS]
        self.assertEqual(poly_diploma_parse.read_poly_transcript(transcript(sems=straight))['cgpa'], '4.00')
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(sems=straight, edit={
            'DYA40133 PLANT TISSUE CULTURE 3.0 A' + NL: ''})))

    def test_the_running_totals_must_rise_by_each_credit_earned(self):
        total2 = boxes()[1][3]
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            f': {total2:.1f} / 45.0': f': {total2 + 2:.1f} / 45.0'})))

    def test_every_sum_must_add_up(self):
        gpa1, cgpa2 = boxes()[0][0], boxes()[1][1]
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={f': {gpa1}Grade': ': 3.80Grade'})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            'COMMUNICATIVE ENGLISH 1 2.0 A-': 'COMMUNICATIVE ENGLISH 1 2.0 A'})))      # a lost sign
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={f': {cgpa2}' + NL: ': 3.10' + NL})))

    def test_the_final_cgpa_is_the_completed_total(self):
        """A box short of the programme's credits is a running figure, never the final one."""
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(training=0, programme=Decimal(45))))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(status='ACTIVE')))
        final = boxes()[-1][1]
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            f': {final}' + NL + ': 9.0': ': 3.40' + NL + ': 9.0'})))

    def test_a_programme_is_five_or_six_semesters(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(sems=SEMS[:3], training=9)))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(sems=SEMS[:4], training=0)))
        self.assertEqual(poly_diploma_parse.read_poly_transcript(transcript(sems=SEMS[:4], training=9))['cgpa'],
                         boxes(SEMS[:4])[-1][1])                     # 4 graded + training = 5

    def test_industrial_training_only_last(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            'THIRD SEMESTER (I : 2022/2023)': 'THIRD SEMESTER (I : 2022/2023) - INDUSTRIAL TRAINING'})))
        # the training semester's lines are free text; a sixth graded semester's are not
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={' - INDUSTRIAL TRAINING': ''})))

    def test_a_row_read_whole_or_not_at_all(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={'CROP PROTECTION 3.0 A': 'CROP PROTECTION 3.0 A [CE]'})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={'CROP PROTECTION 3.0 A': 'CROP PROTECTION 3.0 E'})))
        # a line the reader does not know, inside a semester, even one that changes no sum
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            'MPU24850 PISPA 3 0.0 A': 'MPU24850 PISPA 3 0.0 A' + NL + '[CE] - COURSE EXEMPTION'})))

    def test_the_header(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={'BINTI ALINAME': 'BINTI ALI PEREMPUANNAME'})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={'21DAG21F1001REG.NO': '21DAG21REG.NO'})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript() + NL + 'SAKSI 800101-01-5555'))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={'POLITEKNIK CONTOH SABAH': 'KOLEJ CONTOH'})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            'POLITEKNIK CONTOH SABAH': 'POLITEKNIK CONTOH SABAH' + NL + 'POLITEKNIK LAIN'})))

    def test_not_a_polytechnic_transcript(self):
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(title='KEPUTUSAN PENILAIAN AKHIR SEMESTER')))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={      # two documents in one upload
            'PROVISIONAL' + NL: 'ACADEMIC TRANSCRIPT' + NL})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(transcript(edit={
            'JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI': 'UNIVERSITI CONTOH'})))
        self.assertIsNone(poly_diploma_parse.read_poly_transcript(None))


#: A UiTM "ACADEMIC MINI TRANSCRIPT" twin: a diploma, a faculty, a CGPA — and no polytechnic.
UITM = (f'ACADEMIC MINI TRANSCRIPT{NL}FAKULTI SAINS PENTADBIRAN DAN PENGAJIAN POLISI{NL}'
        f'DIPLOMA IN PUBLIC ADMINISTRATION{NL}CGPA 3.40{NL}FINAL CGPA 3.40')


class TestTheWiring(TestCase):
    def _doc(self):
        student = make_student(name='Siti Aminah', nric='030101-12-1234', exam_type='diploma',
                               results_exam_type='diploma', higher_cgpa=3.55,
                               completed_qualifications=['spm', 'diploma'])
        app = make_application('shortlisted', student=student)
        return ApplicantDocument.objects.create(application=app, doc_type='higher_results',
                                                storage_path='test/higher/poly', results_kind='diploma')

    @staticmethod
    def _gemini(text, dt, **kw):
        return {'fields': {'cgpa': '3.40'}, 'warnings': [], 'error': ''}

    def test_a_polytechnic_transcript_is_read_exact_without_gemini(self):
        calls = []
        ex = extract(self._doc(), {'text': transcript(), 'words': None}, lambda: None,
                     lambda *a, **kw: calls.append('gemini'))
        self.assertEqual(calls, [])
        self.assertEqual((ex['capture'], ex['parser_version']),
                         ('deterministic', f'poly_diploma_parse {poly_diploma_parse.PARSER_VERSION}'))
        self.assertEqual((ex['fields']['cgpa'], ex['fields']['results_kind_detected']), ('3.55', 'diploma'))

    def test_uitm_stpm_and_matric_pages_never_reach_the_polytechnic_reader(self):
        from apps.scholarship.tests.test_matric_parse import two_sem
        for text in (UITM, 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA 2025 PNGK 3.50', two_sem()):
            with patch('apps.scholarship.poly_diploma_parse.read_poly_transcript') as reader:
                extract(self._doc(), {'text': text, 'words': None}, lambda: None, self._gemini)
            reader.assert_not_called()
        with patch('apps.scholarship.poly_diploma_parse.read_poly_transcript', return_value=None) as reader:   # control
            extract(self._doc(), {'text': transcript(), 'words': None}, lambda: None, self._gemini)
        reader.assert_called_once()

    def test_the_model_version_moved(self):
        from apps.scholarship.genuineness.results_doc import MODEL_VERSION
        self.assertGreaterEqual(tuple(int(p) for p in re.split(r'\.', MODEL_VERSION)), (1, 20, 0))
