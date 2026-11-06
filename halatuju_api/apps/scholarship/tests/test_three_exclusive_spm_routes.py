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


def _slip_app(profile):
    app = make_application('submitted', student=make_student(**profile))
    doc = ApplicantDocument.objects.create(
        application=app, doc_type='results_slip', storage_path=f'{app.id}/rs/x',
        vision_run_at=timezone.now(),
        vision_fields={'student_verdict': 'ok', 'fields': {
            'candidate_name': 'X', 'exam': 'SIJIL PELAJARAN MALAYSIA TAHUN 2023', 'results': CORE}})
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
        prereq = {'bm': 'C', 'eng': 'A', 'math': 'A', 'phy': 'A'}     # bm wrong, hist missing, phy extra
        app, doc = _slip_app({**MATRIC, 'grades': CORE_TYPED, 'spm_prereq_grades': prereq})
        chk = student_slip_check(doc)
        self.assertEqual((chk['subjects'], chk['results']), ('mismatch', 'mismatch'))
        self.assertEqual((chk['missing'], chk['extra']), (['SEJARAH'], ['Fizik']))
        self.assertEqual([m['subject'] for m in chk['mismatched']], ['BAHASA MELAYU'])
        fact = _verdict_academic(app, True)
        self.assertNotEqual(fact['status'], 'verified')
        self.assertTrue({'academic_missing_subjects', 'academic_extra_subjects'} <= _codes(fact))
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


class SpmHolderUnchanged(TestCase):
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
