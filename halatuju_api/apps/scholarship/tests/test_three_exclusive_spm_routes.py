"""Request #62, owner ruling 2026-11-06: "There are three routes: SPM, STPM, Matric/etc. Keep them
exclusive. Do not combine."

* An SPM holder's SPM slip is compared with the SPM grades she entered (`profile.grades`).
* An STPM / Matriculation / Asasi / Diploma holder's SPM slip is compared ONLY with the SPM prereq
  she entered (`profile.spm_prereq_grades`); her `grades` (an earlier SPM-page entry) are never read.
* A prereq that does not match the slip raises the alert exactly as for an SPM holder, and the
  Academic check is not verified until resolved.
* No prereq: nothing to compare — no tick and no SPM warning (D9: the slip stays optional).

Supersedes S2a/S3b's `grades`-over-prereq merge ("grades wins a clash")."""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.tests.test_third_route_s4 import (
    SPM, SPM_READ, _academic,
)
from apps.scholarship.verdict_engine import _verdict_academic
from apps.scholarship.verdict_ladder import _academic_red_chips

CORE = [{'subject': 'BAHASA MELAYU', 'grade': 'A'}, {'subject': 'BAHASA INGGERIS', 'grade': 'A'},
        {'subject': 'MATEMATIK', 'grade': 'A'}, {'subject': 'SEJARAH', 'grade': 'B'}]
CORE_TYPED = {'bm': 'A', 'eng': 'A', 'math': 'A', 'hist': 'B'}
#: An earlier SPM-page entry that DIFFERS from the slip: a wrong grade (bm C) and a subject the
#: slip does not show (Fizik). For a tertiary holder neither may matter.
OLD_GRADES = {'bm': 'C', 'eng': 'A', 'math': 'A', 'hist': 'B', 'phy': 'A'}
MATRIC = dict(exam_type='matric', results_exam_type='matric', higher_cgpa=3.5, higher_koko=8,
              completed_qualifications=['spm', 'matric'])
STPM = dict(exam_type='stpm', results_exam_type='stpm', stpm_cgpa=3.71, stpm_grades={'PA': 'A'},
            completed_qualifications=['spm', 'stpm'])
SPM_CODES = ('academic_missing_subjects', 'academic_extra_subjects', 'academic_grade_mismatch',
             'academic_grade_band_mismatch', 'academic_grade_uncertain', 'grades_unverified',
             'grades_verified')


def _slip_app(profile, results=None):
    app = make_application('submitted', student=make_student(**profile))
    doc = ApplicantDocument.objects.create(
        application=app, doc_type='results_slip', storage_path=f'{app.id}/rs/x',
        vision_run_at=timezone.now(),
        vision_fields={'student_verdict': 'ok', 'fields': {
            'candidate_name': 'X', 'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2023', 'results': results or CORE}})
    return app, doc


def _codes(fact):
    return {i['code'] for i in fact['unresolved']} | {i['code'] for i in fact['evidence']}


class TertiaryReadsThePrereqOnly(TestCase):
    def test_grades_are_not_compared_when_the_prereq_matches(self):
        # a subject only in `grades` is neither missing nor extra; a grade that differs only in
        # `grades` does not mismatch
        for kind, fields in (('stpm', STPM), ('matric', MATRIC)):
            with self.subTest(kind=kind):
                app, doc = _slip_app({**fields, 'grades': OLD_GRADES, 'spm_prereq_grades': CORE_TYPED})
                chk = student_slip_check(doc)
                self.assertEqual((chk['subjects'], chk['results']), ('match', 'match'))
                self.assertEqual((chk['missing'], chk['extra'], chk['mismatched']), ([], [], []))
                self.assertEqual(_academic_red_chips(app), 0)
                self.assertFalse(_codes(_verdict_academic(app, True)) & set(SPM_CODES[:6]))

    def test_a_prereq_that_does_not_match_the_slip_raises_the_alert(self):
        prereq = {'bm': 'C', 'eng': 'A', 'math': 'A', 'phy': 'A'}     # bm wrong, hist not entered, phy extra
        app, doc = _slip_app({**MATRIC, 'grades': CORE_TYPED, 'spm_prereq_grades': prereq})
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('mismatch', 'mismatch'))
        self.assertEqual((chk['missing'], chk['extra']), ([], ['Fizik']))   # entered-only (11-06.3)
        self.assertEqual([m['subject'] for m in chk['mismatched']], ['BAHASA MELAYU'])
        fact = _verdict_academic(app, True)
        self.assertNotEqual(fact['status'], 'verified')
        self.assertIn('academic_extra_subjects', _codes(fact))
        self.assertNotIn('academic_missing_subjects', _codes(fact))
        self.assertTrue(_codes(fact) & {'academic_grade_mismatch', 'academic_grade_band_mismatch'})
        self.assertGreaterEqual(_academic_red_chips(app), 2)          # Subjects + Results chips

    def test_no_prereq_means_nothing_to_compare_no_tick_no_warning(self):
        # her `grades` match the slip exactly — and are still not read
        app, doc = _slip_app({**STPM, 'grades': CORE_TYPED, 'spm_prereq_grades': {}})
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('not_compared', 'pending'))
        self.assertEqual((chk['missing'], chk['extra'], chk['mismatched']), ([], [], []))
        self.assertEqual(doc_match_verdict(doc), 'ok')                # an officer's slip request closes
        fact = _verdict_academic(app, True)
        self.assertNotEqual(fact['status'], 'verified')               # no tick
        self.assertFalse(_codes(fact) & set(SPM_CODES))               # and no SPM warning
        self.assertEqual(_academic_red_chips(app), 0)


#: An eight-subject slip (the four compulsory + four electives) — a full, complete read.
FULL = CORE + [{'subject': 'FIZIK', 'grade': 'B'}, {'subject': 'KIMIA', 'grade': 'C'},
               {'subject': 'BIOLOGI', 'grade': 'B'}, {'subject': 'MATEMATIK TAMBAHAN', 'grade': 'C'}]


class TertiaryChecksOnlyWhatSheEntered(TestCase):
    """Owner ruling 2026-11-06 (11-06.3): a tertiary holder's optional SPM prereq is checked on the
    subjects she ENTERED; a slip subject she did not enter is never missing for her."""

    def _tertiary(self, prereq, results=FULL):
        return _slip_app({**STPM, 'spm_prereq_grades': prereq}, results)

    def test_four_entered_all_on_the_slip_same_grades_is_a_match_and_tick_eligible(self):
        from apps.scholarship.academic_compare import spm_slip_compare
        from apps.scholarship.academic_engine import read_slip
        app, doc = self._tertiary(CORE_TYPED)
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('match', 'match'))
        self.assertEqual((chk['missing'], chk['extra'], chk['mismatched']), ([], [], []))
        self.assertEqual(chk['slip_count'], 8)
        cmp = spm_slip_compare(app.profile, read_slip(doc))
        self.assertTrue(cmp['complete'] and cmp['accurate'])            # the tick's two conditions
        self.assertEqual(cmp['checked_count'], 4)                       # "All 4 grades match"
        self.assertFalse(_codes(_verdict_academic(app, True)) & set(SPM_CODES[:6]))
        self.assertEqual(_academic_red_chips(app), 0)

    def test_a_wrong_grade_on_an_entered_subject_mismatches(self):
        app, doc = self._tertiary({**CORE_TYPED, 'phy': 'D'})          # slip: Fizik B
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('match', 'mismatch'))
        self.assertEqual([m['subject'] for m in chk['mismatched']], ['FIZIK'])
        self.assertTrue(_codes(_verdict_academic(app, True))
                        & {'academic_grade_mismatch', 'academic_grade_band_mismatch'})

    def test_an_entered_subject_not_on_a_complete_slip_is_extra(self):
        app, doc = self._tertiary({**CORE_TYPED, 'poa': 'A'})          # Prinsip Perakaunan: not on it
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['missing']), ('mismatch', []))
        self.assertEqual(len(chk['extra']), 1)
        codes = _codes(_verdict_academic(app, True))
        self.assertIn('academic_extra_subjects', codes)
        self.assertNotIn('academic_missing_subjects', codes)
        self.assertEqual(_academic_red_chips(app), 1)                   # the one Subjects chip


class SpmHolderUnchanged(TestCase):
    def test_an_spm_holder_who_typed_fewer_than_the_slip_is_still_missing(self):
        app, doc = _slip_app(dict(exam_type='spm', results_exam_type='spm', grades=CORE_TYPED), FULL)
        chk = student_slip_check(doc)
        self.assertEqual(chk['subjects'], 'mismatch')
        self.assertEqual(chk['missing'], ['BIOLOGI', 'FIZIK', 'KIMIA', 'MATEMATIK TAMBAHAN'])
        self.assertIn('academic_missing_subjects', _codes(_verdict_academic(app, True)))


    def test_an_spm_holder_is_compared_on_grades_and_never_on_the_prereq(self):
        spm = dict(exam_type='spm', results_exam_type='spm')
        _, doc = _slip_app({**spm, 'grades': CORE_TYPED, 'spm_prereq_grades': OLD_GRADES})
        self.assertEqual(student_slip_check(doc)['subjects'], 'match')
        _, doc = _slip_app({**spm, 'grades': OLD_GRADES, 'spm_prereq_grades': CORE_TYPED})
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['extra']), ('mismatch', ['Fizik']))
        # an SPM holder with no grades at all is still compared (every slip subject missing)
        _, doc = _slip_app({**spm, 'grades': {}})
        self.assertEqual(student_slip_check(doc)['subjects'], 'mismatch')


class TheHigherCardFold(TestCase):
    """On the higher-results card the SPM slip folds in only when there is something to compare.
    S3's clean STPM card (verified with no SPM slip, `test_third_route_s3`) is the control."""

    def _app(self, **profile):
        from apps.scholarship.tests import test_third_route_s3 as s3
        app = s3._app({**s3.STPM_FULL_HELD, **profile}, s3.DEGREE)
        s3._doc(app, 'higher_results', s3.STPM_FULL_READ)
        return app, s3

    def test_no_prereq_a_slip_on_file_changes_nothing(self):
        app, s3 = self._app(grades=SPM, spm_prereq_grades={})
        self.assertEqual(_academic(app)['status'], 'verified')         # the control: no slip
        s3._doc(app, 'results_slip', SPM_READ)
        f = _academic(app)
        self.assertEqual(f['status'], 'verified')                      # neither held back ...
        self.assertFalse(_codes(f) & set(SPM_CODES))                   # ... nor ticked / warned

    def test_a_mismatching_prereq_holds_the_card(self):
        app, s3 = self._app(grades=SPM, spm_prereq_grades={**SPM, 'bm': 'C'})
        s3._doc(app, 'results_slip', SPM_READ)
        f = _academic(app)
        self.assertEqual(f['status'], 'review')
        self.assertTrue(_codes(f) & {'academic_grade_mismatch', 'academic_grade_band_mismatch'})
