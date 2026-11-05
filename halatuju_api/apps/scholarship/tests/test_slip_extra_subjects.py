"""Request #62 (owner 2026-11-06): a subject the student TYPED that is not on the results slip.

The slip is the authoritative grade record (decisions.md 2026-06-02). Before this, the comparison
alerted on a slip subject that was not typed (`missing`) and on a different grade, but a typed
subject the slip does not show was never flagged, so the Subjects tick went green. The owner's
rulings, each pinned below:
  1. it is an unresolved Academic item (`academic_extra_subjects`), counted in the ladder exactly
     like a missing subject, shown on the chip / checklist / coach — and NEVER a submission block;
  2. the tone is "please check", not a confident claim;
  3. only on a COMPLETE read (names AND grades): a names-only read never asserts it;
  4. English slip names (MATHEMATICS, PHYSICS, ...) fold to the Malay subject BEFORE it is computed;
  5. no alias is invented: UPU lists Lukisan / Pendidikan Seni Visual, Reka Bentuk Grafik /
     Reka Bentuk Grafik Digital and Reka Bentuk Kraf / Reka Cipta as SEPARATE subjects.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship import help_engine
from apps.scholarship.academic_engine import compare_academics, read_slip, student_slip_check
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.services.blockers import document_red_blockers
from apps.scholarship.slip_coach import coach_detail
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.verdict_engine import build_verdict
from apps.scholarship.verdict_ladder import _academic_red_chips

CORE = [{'subject': 'BAHASA MELAYU', 'grade': 'A'}, {'subject': 'SEJARAH', 'grade': 'B'}]
CORE_TYPED = {'bm': 'A', 'hist': 'B'}


def _slip(results=None, subjects=None):
    fields = {'candidate_name': 'X'}
    if results is not None:
        fields['results'] = results
    if subjects is not None:
        fields['subjects'] = subjects
    return read_slip(SimpleNamespace(vision_fields={'fields': fields}))


def _doc(results, grades, sv='ok'):
    return SimpleNamespace(
        doc_type='results_slip', vision_name_match='found',
        vision_fields={'fields': {'results': results, 'candidate_name': 'X'}, 'student_verdict': sv},
        application=SimpleNamespace(profile=SimpleNamespace(grades=grades)))


class CompareExtra(SimpleTestCase):
    def test_a_typed_subject_not_on_a_complete_read_is_extra(self):
        cmp = compare_academics({**CORE_TYPED, 'phy': 'A'}, _slip(CORE))
        self.assertEqual(cmp['extra'], ['Fizik'])
        self.assertEqual(cmp['missing'], [])
        self.assertFalse(cmp['complete'])

    def test_every_typed_subject_on_the_slip_is_complete(self):
        cmp = compare_academics(CORE_TYPED, _slip(CORE))
        self.assertEqual(cmp['extra'], [])
        self.assertTrue(cmp['complete'])

    def test_a_names_only_read_never_asserts_extra(self):
        cmp = compare_academics({**CORE_TYPED, 'phy': 'A'}, _slip(subjects=['BAHASA MELAYU', 'SEJARAH']))
        self.assertEqual(cmp['extra'], [])
        self.assertTrue(cmp['complete'])

    def test_a_read_without_grades_never_asserts_extra(self):
        rows = [{'subject': r['subject'], 'grade': ''} for r in CORE]
        cmp = compare_academics({**CORE_TYPED, 'phy': 'A'}, _slip(rows))
        self.assertFalse(cmp['have_grades'])
        self.assertEqual(cmp['extra'], [])

    def test_english_slip_names_match_the_typed_malay_subjects(self):
        rows = CORE + [{'subject': n, 'grade': 'A'} for n in (
            'MATHEMATICS', 'ADDITIONAL MATHEMATICS', 'SCIENCE', 'PHYSICS', 'CHEMISTRY', 'BIOLOGY')]
        typed = {**CORE_TYPED, 'math': 'A', 'addmath': 'A', 'sci': 'A', 'phy': 'A', 'chem': 'A', 'bio': 'A'}
        cmp = compare_academics(typed, _slip(rows))
        self.assertEqual((cmp['missing'], cmp['extra']), ([], []))
        self.assertTrue(cmp['complete'] and cmp['accurate'])

    def test_an_english_row_with_its_subject_code_still_folds(self):
        cmp = compare_academics({**CORE_TYPED, 'addmath': 'A'},
                                _slip(CORE + [{'subject': '3472 ADDITIONAL MATHEMATICS', 'grade': 'A'}]))
        self.assertEqual((cmp['missing'], cmp['extra']), ([], []))

    def test_missing_and_extra_together_name_different_subjects(self):
        cmp = compare_academics({**CORE_TYPED, 'phy': 'A'},
                                _slip(CORE + [{'subject': 'KIMIA', 'grade': 'B'}]))
        self.assertEqual(cmp['missing'], ['KIMIA'])
        self.assertEqual(cmp['extra'], ['Fizik'])


class UpuSeparateSubjectsAreNeverFolded(SimpleTestCase):
    """UPU Online's SPM list holds each pair as two subjects (lead's check 2026-11-06; owner ruling
    for Lukisan / PSV), so a typed one against the other on the slip is missing AND extra."""
    PAIRS = (('lukisan', 'PENDIDIKAN SENI VISUAL', 'Lukisan'),
             ('psv', 'LUKISAN', 'Pendidikan Seni Visual'),
             ('lukisan', 'LUKISAN KEJURUTERAAN', 'Lukisan'),
             ('reka_bentuk_grafik', 'REKA BENTUK GRAFIK DIGITAL', 'Reka Bentuk Grafik'),
             ('reka_bentuk_grafik', 'GRAFIK KOMUNIKASI TEKNIKAL', 'Reka Bentuk Grafik'),
             ('reka_bentuk_kraf', 'REKA CIPTA', 'Reka Bentuk Kraf'),
             ('reka_cipta', 'REKA BENTUK KRAF', 'Reka Cipta'))

    def test_each_pair_stays_two_subjects(self):
        for key, printed, typed_name in self.PAIRS:
            with self.subTest(key=key, printed=printed):
                cmp = compare_academics({**CORE_TYPED, key: 'A'},
                                        _slip(CORE + [{'subject': printed, 'grade': 'A'}]))
                self.assertEqual(cmp['missing'], [printed])
                self.assertEqual(cmp['extra'], [typed_name])


class SlipCheckAndCoach(SimpleTestCase):
    def test_student_slip_check_reports_extra_as_a_subjects_mismatch(self):
        chk = student_slip_check(_doc(CORE, {**CORE_TYPED, 'phy': 'A'}))
        self.assertEqual(chk['subjects'], 'mismatch')
        self.assertEqual(chk['extra'], ['Fizik'])
        self.assertEqual(chk['missing'], [])
        self.assertEqual(chk['results'], 'match')

    def test_no_extra_is_a_subjects_match_with_an_empty_list(self):
        chk = student_slip_check(_doc(CORE, CORE_TYPED))
        self.assertEqual((chk['subjects'], chk['extra']), ('match', []))

    def test_the_coach_picks_the_extra_verdict_and_names_the_subject(self):
        doc = _doc(CORE, {**CORE_TYPED, 'phy': 'A'})
        verdict = help_engine.verdict_for_document(doc)
        self.assertEqual(verdict, 'slip_subjects_extra')
        self.assertEqual(coach_detail(doc, verdict), {'grade_diffs': [], 'extra_subjects': ['Fizik']})

    def test_missing_still_wins_the_coach_and_the_extra_is_still_named(self):
        doc = _doc(CORE + [{'subject': 'KIMIA', 'grade': 'B'}], {**CORE_TYPED, 'phy': 'A'})
        verdict = help_engine.verdict_for_document(doc)
        self.assertEqual(verdict, 'slip_subjects_missing')
        self.assertEqual(coach_detail(doc, verdict)['extra_subjects'], ['Fizik'])

    def test_the_coach_prompt_asks_them_to_check_never_says_wrong(self):
        p = help_engine._build_help_prompt('results_slip', 'slip_subjects_extra', 'Ravi',
                                           help_engine.DEFAULT_LANGUAGE)
        self.assertIn('could not find on the results slip', p)
        self.assertIn('Do NOT say they are wrong', p)


class VerdictLadderAndBlockers(TestCase):
    def setUp(self):
        self.app = make_application('submitted', student=make_student(grades={**CORE_TYPED, 'phy': 'A'}))

    def _upload(self, results):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='results_slip', storage_path=f'{self.app.id}/rs/x',
            vision_run_at=timezone.now(),
            vision_fields={'student_verdict': 'ok', 'fields': {'candidate_name': 'X', 'results': results}})

    def _academic(self):
        return next(f for f in build_verdict(self.app) if f['fact'] == 'academic')

    def test_extra_makes_the_academic_fact_review_with_its_own_item(self):
        self._upload(CORE)
        ac = self._academic()
        self.assertNotEqual(ac['status'], 'verified')
        items = {i['code']: i for i in ac['unresolved']}
        self.assertIn('academic_extra_subjects', items)
        self.assertEqual(items['academic_extra_subjects']['params']['subjects'], 'Fizik')
        self.assertNotIn('academic_missing_subjects', items)

    def test_the_control_with_the_subject_on_the_slip_is_verified(self):
        self._upload(CORE + [{'subject': 'FIZIK', 'grade': 'A'}])
        self.assertEqual(self._academic()['status'], 'verified')

    def test_the_ladder_counts_extra_like_missing(self):
        self._upload(CORE)
        self.assertEqual(_academic_red_chips(self.app), 1)

    def test_the_ladder_counts_one_subjects_chip_when_both_are_present(self):
        self._upload(CORE + [{'subject': 'KIMIA', 'grade': 'B'}])
        self.assertEqual(_academic_red_chips(self.app), 1)

    def test_extra_adds_no_submission_blocker_and_no_document_red(self):
        clean_app = make_application('submitted', student=make_student(grades=CORE_TYPED))
        ApplicantDocument.objects.create(
            application=clean_app, doc_type='results_slip', storage_path=f'{clean_app.id}/rs/x',
            vision_run_at=timezone.now(),
            vision_fields={'student_verdict': 'ok', 'fields': {'candidate_name': 'X', 'results': CORE}})
        slip = self._upload(CORE)
        self.assertEqual(student_slip_check(slip)['extra'], ['Fizik'])   # the case is real
        self.assertEqual(document_red_blockers(self.app), document_red_blockers(clean_app))
        self.assertEqual(doc_match_verdict(slip), 'ok')


#: The six English names (request #62), normalised: comparison-only, never in a reader table.
ENGLISH_KEYS = ('mathematics', 'additional mathematics', 'science', 'physics', 'chemistry', 'biology')


def _row(line):
    return [{'text': t} for t in line.split()]


class EnglishNamesNeverReachTheReaders(SimpleTestCase):
    """Review fix 1 (lead 2026-11-06): the English names fold at COMPARISON only. The slip readers
    (`_parse_grade_row`, `spm_cert_parse`) read exactly what origin/main reads — checked against
    main's own code at the time — so no stored or new read changes and no MODEL_VERSION bump."""

    def test_the_reader_tables_hold_no_english_name(self):
        from apps.scholarship import academic_engine, spm_cert_parse
        for key in ENGLISH_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(key, academic_engine._CANONICAL)
                self.assertNotIn(tuple(key.split()), spm_cert_parse._SUBJECT_SEQ)

    def test_grade_rows_read_as_on_main(self):
        from apps.scholarship.academic_engine import _parse_grade_row
        self.assertIsNone(_parse_grade_row(_row('6351 ENGLISH FOR SCIENCE AND TECHNOLOGY A- CEMERLANG')))
        self.assertIsNone(_parse_grade_row(_row('1449 MATHEMATICS A CEMERLANG')))
        self.assertIsNone(_parse_grade_row(_row('3472 ADDITIONAL MATHEMATICS B KEPUJIAN')))
        self.assertEqual(_parse_grade_row(_row('1449 MATEMATIK MATHEMATICS A CEMERLANG')),
                         {'subject': 'Matematik', 'grade': 'A-', 'band': 'cemerlang'})

    def test_an_est_row_on_a_lapan_slip_still_falls_to_gemini(self):
        from apps.scholarship.academic_engine import parse_spm_slip
        from apps.scholarship.tests.test_academic_engine import _slip_words
        header = [('SIJIL PELAJARAN MALAYSIA', 200), ('JUMLAH MATA PELAJARAN LAPAN', 900)]
        rows = [(s, 'A', 'CEMERLANG TINGGI') for s in (
            'BAHASA MELAYU', 'BAHASA INGGERIS', 'PENDIDIKAN MORAL', 'SEJARAH', 'MATEMATIK',
            'PERNIAGAAN', 'PERTANIAN', '6351 ENGLISH FOR SCIENCE AND TECHNOLOGY')]
        self.assertIsNone(parse_spm_slip(_slip_words(header, rows)))   # 7 of 8 read: never a fake Sains

    def test_comparison_does_not_read_est_as_sains(self):
        cmp = compare_academics({**CORE_TYPED, 'sci': 'A'},
                                _slip(CORE + [{'subject': 'ENGLISH FOR SCIENCE AND TECHNOLOGY', 'grade': 'A'}]))
        self.assertEqual(cmp['extra'], ['Sains'])
        self.assertEqual(cmp['missing'], ['ENGLISH FOR SCIENCE AND TECHNOLOGY'])

    def test_a_dual_language_cell_folds_at_comparison(self):
        cmp = compare_academics({**CORE_TYPED, 'math': 'A'},
                                _slip(CORE + [{'subject': '1449 MATEMATIK MATHEMATICS', 'grade': 'A'}]))
        self.assertEqual((cmp['missing'], cmp['extra']), ([], []))


def _stored(results, raw=None):
    fields = {'candidate_name': 'X', 'results': results}
    if raw is not None:
        fields['_debug_rows'] = raw
    return read_slip(SimpleNamespace(vision_fields={'fields': fields}))


class APrintedSubjectIsNeverExtra(SimpleTestCase):
    """Review fix 2: a stored local read that DROPPED a row it did not know (an English name) still
    keeps the printed line in `_debug_rows`; a typed subject on one of those lines is not extra."""
    RAW = ['SIJIL PELAJARAN MALAYSIA', '1103 BAHASA MELAYU A CEMERLANG TINGGI',
           '1249 SEJARAH B KEPUJIAN TINGGI', '3472 ADDITIONAL MATHEMATICS A CEMERLANG']

    def test_a_raw_printed_line_clears_the_extra(self):
        cmp = compare_academics({**CORE_TYPED, 'addmath': 'A'}, _stored(CORE, self.RAW))
        self.assertEqual(cmp['extra'], [])
        self.assertTrue(cmp['complete'])

    def test_without_the_raw_line_it_is_extra(self):
        cmp = compare_academics({**CORE_TYPED, 'addmath': 'A'}, _stored(CORE, self.RAW[:3]))
        self.assertEqual(cmp['extra'], ['Matematik Tambahan'])

    def test_a_gemini_read_keeps_no_raw_lines_so_extra_stands(self):
        cmp = compare_academics({**CORE_TYPED, 'addmath': 'A'}, _stored(CORE))
        self.assertEqual(cmp['extra'], ['Matematik Tambahan'])

    def test_a_noisy_raw_line_the_reader_dropped_still_counts(self):
        # Live shape: a watermark and a glued band ("ACEMERLANG") made the reader drop the row.
        cmp = compare_academics({**CORE_TYPED, 'sci': 'A'},
                                _stored(CORE, ['1511 SAINS امانه ACEMERLANG TINGGI']))
        self.assertEqual(cmp['extra'], [])

    def test_a_longer_subject_on_the_raw_line_does_not_clear_its_prefix(self):
        cmp = compare_academics({**CORE_TYPED, 'sci': 'A'}, _stored(CORE, ['3770 SAINS KOMPUTER C + KEPUJIAN ATAS']))
        self.assertEqual(cmp['extra'], ['Sains'])

    def test_a_raw_est_line_does_not_clear_a_typed_sains(self):
        cmp = compare_academics({**CORE_TYPED, 'sci': 'A'},
                                _stored(CORE, ['6351 ENGLISH FOR SCIENCE AND TECHNOLOGY A CEMERLANG']))
        self.assertEqual(cmp['extra'], ['Sains'])


class ThirdRouteSpmGrades(TestCase):
    """A tertiary holder's SPM grades come from `spm_prereq_grades` merged with `grades`
    (`spm_grades_for`); a subject typed only in the STPM page's SPM block is compared too."""
    STPM = dict(exam_type='stpm', results_exam_type='stpm', stpm_cgpa=3.71,
                stpm_grades={'PA': 'A'}, completed_qualifications=['spm', 'stpm'], grades=CORE_TYPED)

    def _check(self, prereq):
        app = make_application('submitted', student=make_student(**self.STPM, spm_prereq_grades=prereq))
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='results_slip', storage_path=f'{app.id}/rs/x',
            vision_run_at=timezone.now(),
            vision_fields={'student_verdict': 'ok', 'fields': {
                'candidate_name': 'X', 'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2023', 'results': CORE}})
        return student_slip_check(doc)

    def test_an_extra_subject_in_the_prereq_block_is_flagged(self):
        chk = self._check({'hist': 'B', 'phy': 'A'})
        self.assertEqual((chk['subjects'], chk['extra']), ('mismatch', ['Fizik']))

    def test_no_extra_subject_no_flag(self):
        chk = self._check({'hist': 'B'})
        self.assertEqual((chk['subjects'], chk['extra']), ('match', []))
