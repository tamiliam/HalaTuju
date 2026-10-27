"""Owner ruling D16c (2026-10-27) — a blank `min_stpm_pngk` makes the intake SPM-ONLY, at the gate.

Before: an STPM / Matriculation / Asasi / Diploma holder on an intake with no STPM floor passed the
academic test outright ("this programme sets no STPM requirement"). Now they are tested on the
intake's SPM bars, on their SPM grades (`exam_questions.spm_grades_for`: `grades` over the STPM
page's SPM block), and a failure says "SPM-only intake: …". Pinned here:

1. each tertiary qualification on a blank floor faces the SPM bars — passes when they clear them,
   fails (category 'merit') when they do not, and reads the STPM page's SPM block;
2. that door tests the GRADE bars only — `min_merit_score` stays SPM-only (D3) — and no SPM grades
   at all against a set grade bar is "SPM grades not provided";
3. with a floor set, the STPM and third-route branches are unchanged (floor tests, reasons);
4. an SPM holder is unchanged on either floor (no prefix, same reasons);
5. D5 (a private-college Diploma is ineligible) still runs first on a blank floor — pinned already
   by `test_third_route.test_a_private_college_diploma_is_ineligible_D5` (`min_stpm_pngk=None`).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.courses.models import StudentProfile
from apps.scholarship.shortlisting import _academic_ok

SPM_STRONG = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A'}
SPM_WEAK = {'bm': 'C', 'eng': 'D', 'math': 'C', 'hist': 'E', 'moral': 'C'}

STPM = dict(exam_type='stpm', stpm_cgpa=3.2, results_exam_type='stpm',
            completed_qualifications=['spm', 'stpm'])
MATRIC = dict(exam_type='matric', higher_cgpa=3.5, higher_koko=8, results_exam_type='matric',
              completed_qualifications=['spm', 'matric'])
ASASI = dict(exam_type='asasi', higher_cgpa=3.5, higher_koko=8, results_exam_type='asasi',
             completed_qualifications=['spm', 'asasi'])
DIPLOMA = dict(exam_type='diploma', higher_cgpa=3.5, higher_institution_type='public',
               results_exam_type='diploma', completed_qualifications=['spm', 'diploma'])
TERTIARY = {'stpm': STPM, 'matric': MATRIC, 'asasi': ASASI, 'diploma': DIPLOMA}


def _p(grades, **fields):
    return StudentProfile(supabase_user_id='d16c', grades=grades, **fields)


def _cohort(**floors):
    """The intake's SPM bars: 3 at A-, 5 at B+ or better; floors overridable."""
    base = dict(min_stpm_pngk=None, min_spm_a_count=3, min_spm_bplus_count=5,
                min_spm_credit_count=None, min_merit_score=None)
    base.update(floors)
    return SimpleNamespace(**base)


class TestABlankFloorTestsTertiaryOnTheSpmBars(SimpleTestCase):
    def test_each_tertiary_holder_who_clears_the_spm_bars_passes(self):
        for kind, fields in TERTIARY.items():
            with self.subTest(kind=kind):
                self.assertEqual(_academic_ok(_p(SPM_STRONG, **fields), _cohort()), (True, ''))

    def test_each_tertiary_holder_below_the_spm_bars_fails_and_says_why(self):
        for kind, fields in TERTIARY.items():
            with self.subTest(kind=kind):
                ok, why = _academic_ok(_p(SPM_WEAK, **fields), _cohort())
                self.assertFalse(ok)
                self.assertEqual(why, 'SPM-only intake: 0 at A- (need 3); '
                                      '0 at B+ or better (need 3 at A- plus 2 more at B+)')

    def test_no_spm_grades_at_all_is_not_a_pass_and_says_so(self):
        self.assertEqual(_academic_ok(_p({}, **STPM), _cohort()),
                         (False, 'SPM-only intake: SPM grades not provided'))
        # only the credit bar set: the same plain reason
        only_credit = _cohort(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=5)
        self.assertEqual(_academic_ok(_p({}, **MATRIC), only_credit),
                         (False, 'SPM-only intake: SPM grades not provided'))

    def test_no_spm_grades_and_no_grade_bar_set_still_passes(self):
        bare = _cohort(min_spm_a_count=None, min_spm_bplus_count=None, min_merit_score=80)
        self.assertEqual(_academic_ok(_p({}, **STPM), bare), (True, ''))

    def test_the_stpm_pages_spm_block_is_read(self):
        # `grades` blank, the SPM grades only in `spm_prereq_grades` (live: 54 of 64 STPM holders)
        p = _p({}, spm_prereq_grades=SPM_STRONG, **STPM)
        self.assertEqual(_academic_ok(p, _cohort()), (True, ''))

    def test_the_merit_bar_is_not_applied_D3(self):
        # Good SPM grades, no co-curriculum score, blank STPM floor, merit bar 80: passes — an
        # STPM-level holder's coq / stream are written only by the SPM grades step (D3 stands).
        p = _p({}, spm_prereq_grades=SPM_STRONG, coq_score=None, **STPM)
        self.assertEqual(_academic_ok(p, _cohort(min_merit_score=80)), (True, ''))
        self.assertEqual(_academic_ok(_p(SPM_STRONG, **DIPLOMA),
                                      _cohort(min_spm_a_count=None, min_spm_bplus_count=None,
                                              min_merit_score=99.9)), (True, ''))

    def test_an_spm_holder_still_faces_the_merit_bar(self):
        ok, why = _academic_ok(_p(SPM_STRONG, exam_type='spm'),
                               _cohort(min_spm_a_count=None, min_spm_bplus_count=None,
                                       min_merit_score=99.9))
        self.assertFalse(ok)
        self.assertRegex(why, r'^merit point [\d.]+ below 99.9$')

    def test_no_bar_set_at_all_still_passes(self):
        # Every SPM bar and the STPM floor blank: no academic test, as before.
        bare = _cohort(min_spm_a_count=None, min_spm_bplus_count=None)
        self.assertEqual(_academic_ok(_p(SPM_WEAK, **STPM), bare), (True, ''))


class TestAFloorSetIsUnchanged(SimpleTestCase):
    def test_stpm_on_the_floor(self):
        self.assertEqual(_academic_ok(_p(SPM_WEAK, **STPM), _cohort(min_stpm_pngk=2.9)), (True, ''))
        self.assertEqual(_academic_ok(_p(SPM_STRONG, **STPM), _cohort(min_stpm_pngk=3.5)),
                         (False, 'PNGK 3.2 below 3.5'))
        self.assertEqual(_academic_ok(_p(SPM_STRONG, **{**STPM, 'stpm_cgpa': None}),
                                      _cohort(min_stpm_pngk=2.9))[1], 'STPM PNGK not provided')

    def test_the_third_route_on_the_floor(self):
        self.assertEqual(_academic_ok(_p(SPM_WEAK, **DIPLOMA), _cohort(min_stpm_pngk=2.9)), (True, ''))
        self.assertEqual(_academic_ok(_p(SPM_STRONG, **{**DIPLOMA, 'higher_cgpa': 2.8}),
                                      _cohort(min_stpm_pngk=2.9)),
                         (False, 'Diploma CGPA 2.80 below 2.90'))


class TestAnSpmHolderIsUnchanged(SimpleTestCase):
    def test_on_either_floor(self):
        for floor in (None, 2.9):
            with self.subTest(floor=floor):
                self.assertEqual(_academic_ok(_p(SPM_STRONG, exam_type='spm'),
                                              _cohort(min_stpm_pngk=floor)), (True, ''))
                self.assertEqual(_academic_ok(_p(SPM_WEAK, exam_type='spm'),
                                              _cohort(min_stpm_pngk=floor)),
                                 (False, '0 at A- (need 3); '
                                         '0 at B+ or better (need 3 at A- plus 2 more at B+)'))

