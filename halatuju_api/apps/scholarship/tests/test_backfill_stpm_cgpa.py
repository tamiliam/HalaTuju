"""`backfill_stpm_cgpa` — STPM CGPA sprint C2 (2026-10-28): preview by default, `--apply` writes.

Owner ruling: CGPA = the PNGK of the grades; merit = overall_from(CGPA, koko) / 4 x 100, so the
co-curriculum score the server never stored is DERIVED for existing students:
koko = (stored stpm_cgpa - 0.9 x the old plain average of all grades) / 0.04, half-up to 0.01,
clamped to 0-10, reported when it does not land cleanly.

All grades are made up. The command prints ids and figures only, never a name, an NRIC or a
profile id.
"""
from io import StringIO
from types import SimpleNamespace

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.management.commands.backfill_stpm_cgpa import derive_koko

from .factories import make_application, make_cohort, make_student

# PNGK (PA + best three) = (4 + 4 + 3.67 + 3.33) / 4 = 3.75; plain average of all five = 3.40.
GRADES = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+', 'BIOLOGY': 'C'}
# The old calculator's overall with koko 3.75: round(0.9 x 3.40 + 0.04 x 3.75, 2) = 3.21.
STPM = dict(exam_type='stpm', results_exam_type='stpm', stpm_grades=GRADES, stpm_cgpa=3.21,
            completed_qualifications=['spm', 'stpm'], grades={'bm': 'A'})


def _p(**kw):
    return SimpleNamespace(**{'stpm_koko': None, 'stpm_cgpa': None, 'stpm_grades': {}, **kw})


class TestDeriveKoko(SimpleTestCase):
    def test_a_calculator_figure_lands_cleanly(self):
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.21)), (3.75, True))

    def test_koko_zero_and_ten_are_reached_exactly(self):
        # 0.9 x 3.40 = 3.06 (koko 0); + 0.04 x 10 = 3.46 (koko 10)
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.06)), (0.0, True))
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.46)), (10.0, True))

    def test_a_figure_the_calculator_could_not_have_given_is_clamped_and_not_clean(self):
        """Typed by hand, or the grades changed after it was stored: above 10 or below 0."""
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.75)), (10.0, False))
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=2.90)), (0.0, False))

    def test_rounding_is_half_up_to_the_koko_step(self):
        # (3.07 - 3.06) / 0.04 = 0.25 exactly; (3.11 - 3.06) / 0.04 = 1.25
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.11)), (1.25, True))
        # all-A: average 4.00, 0.9 x 4 = 3.60; 3.90 typed (#173's shape) -> 7.50, reproduces 3.90
        all_a = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'}
        self.assertEqual(derive_koko(_p(stpm_grades=all_a, stpm_cgpa=3.90)), (7.5, True))

    def test_nothing_to_derive_from(self):
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES)), (None, False))
        self.assertEqual(derive_koko(_p(stpm_cgpa=3.2)), (None, False))
        self.assertEqual(derive_koko(_p(stpm_grades={'PA': 'X'}, stpm_cgpa=3.2)), (None, False))

    def test_a_stored_score_is_kept(self):
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.21, stpm_koko=6.0)), (6.0, True))


class TestBackfillStpmCgpa(TestCase):
    def setUp(self):
        cohort = make_cohort(min_stpm_pngk=3.5)
        self.flips = make_application('submitted', cohort=cohort, student=make_student(**STPM))
        # PA + one other: not calculated. Average 3.50; koko (3.21 - 3.15) / 0.04 = 1.50.
        self.short = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_grades': {'PA': 'A', 'MATH_T': 'B'}}))
        # Stored figure already the PNGK: koko would be 17.25 -> clamped to 10, NOT CLEAN.
        self.same = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_cgpa': 3.75}))
        self.kept = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_koko': 6.0}))
        self.nokoko = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_cgpa': None}))
        self.spm = make_application('submitted', cohort=cohort, student=make_student(
            exam_type='spm', results_exam_type='spm', grades={'bm': 'A'}))
        # A course-guide profile with no application: its columns are written too.
        self.loose = make_student(**STPM)

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_stpm_cgpa', *args, stdout=out)
        return out.getvalue()

    def _line(self, text, app):
        return next(line for line in text.splitlines() if line.startswith(f'#{app.id}\t'))

    def test_preview_lists_cgpa_merit_and_gate_before_and_after_and_writes_nothing(self):
        text = self._run()
        flips = self._line(text, self.flips)
        self.assertIn('3.21 -> 3.75\t3.75\t', flips)                  # CGPA; derived koko 3.75
        # merit: 3.21 / 4 x 100 -> overall_from(3.75, 3.75) = 3.525 -> 3.52 (`overall_from` rounds
        # the float, as it always has) -> 88.00
        self.assertIn('80.25 -> 88.00', flips)
        self.assertIn('REJECT (PNGK 3.21 below 3.5) -> PASS', flips)
        self.assertIn('GATE FLIPS', flips)
        short = self._line(text, self.short)
        self.assertIn('3.21 -> 3.21 (not calculated)\t1.50\t80.25 -> 80.25', short)
        self.assertNotIn('GATE FLIPS', short)
        self.assertIn('10.00 KOKO NOT CLEAN', self._line(text, self.same))
        self.assertIn('6.00 (stored)', self._line(text, self.kept))
        # overall_from(3.75, 6) = 3.615 -> 3.62 (as Python rounds the float) -> 90.5
        self.assertIn('-> 90.50', self._line(text, self.kept))
        nokoko = self._line(text, self.nokoko)
        self.assertIn('- NO KOKO', nokoko)
        self.assertIn('- -> -', nokoko)                               # no merit before or after
        self.assertFalse(any(line.startswith(f'#{self.spm.id}\t') for line in text.splitlines()))
        self.assertIn('5 STPM application(s): 3 change CGPA, 1 not calculated (fewer than PA + 3), '
                      '3 gate result(s) flip, 1 koko not clean, 1 with no koko.', text)
        # 5: the no-koko profile is left alone — its stored figure is all a score could come from
        self.assertIn('5 profile(s) to write: 4 co-curriculum score(s) derived (1 not clean), '
                      '3 stpm_cgpa rewritten', text)
        self.assertIn('PREVIEW', text)
        p = StudentProfile.objects.get(pk=self.flips.profile.pk)
        self.assertEqual((p.stpm_cgpa, p.stpm_koko), (3.21, None))

    def test_no_name_nric_or_profile_id_is_printed(self):
        text = self._run()
        for p in (self.flips.profile, self.short.profile, self.loose):
            self.assertNotIn(p.name, text)
            self.assertNotIn(p.nric, text)
        for line in text.splitlines():
            if line.startswith('#'):
                self.assertEqual(len(line.split('\t')), 6, line)       # no profile column

    def test_apply_writes_both_columns_from_the_figures_before_the_run_and_is_idempotent(self):
        self.assertIn('Applied: 5 profile(s) updated.', self._run('--apply'))
        get = lambda p: (lambda r: (r.stpm_cgpa, r.stpm_koko))(StudentProfile.objects.get(pk=p.pk))
        self.assertEqual(get(self.flips.profile), (3.75, 3.75))
        self.assertEqual(get(self.loose), (3.75, 3.75))
        self.assertEqual(get(self.short.profile), (3.21, 1.5))        # not calculated: figure kept
        self.assertEqual(get(self.same.profile), (3.75, 10.0))
        self.assertEqual(get(self.kept.profile), (3.75, 6.0))         # stored koko untouched
        self.assertEqual(get(self.nokoko.profile), (None, None))      # readers read through: 3.75
        self.assertEqual(StudentProfile.objects.get(pk=self.nokoko.profile.pk).stpm_pngk, 3.75)
        self.assertIn('0 profile(s) to write', self._run())          # idempotent

    def test_koko_only_writes_the_score_and_leaves_every_cgpa_as_it_was(self):
        """The pre-deploy step: the image serving never reads `stpm_koko`, so nothing it shows moves —
        and the old figures survive for the CGPA pass after the deploy."""
        self.assertIn('Applied: 4 profile(s) updated.', self._run('--apply', '--koko-only'))
        get = lambda p: (lambda r: (r.stpm_cgpa, r.stpm_koko))(StudentProfile.objects.get(pk=p.pk))
        self.assertEqual(get(self.flips.profile), (3.21, 3.75))
        self.assertEqual(get(self.kept.profile), (3.21, 6.0))
        self.assertIn('Applied: 3 profile(s) updated.', self._run('--apply'))   # then the CGPAs
        self.assertEqual(get(self.flips.profile), (3.75, 3.75))
