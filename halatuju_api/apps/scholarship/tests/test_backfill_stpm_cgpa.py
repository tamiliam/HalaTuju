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
        """Typed by hand, or the grades changed after it was stored: below 0 is clamped."""
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=2.90)), (0.0, False))

    def test_a_figure_that_is_already_the_pngk_gives_nothing_after_the_deploy(self):
        """Review HIGH: once the C2 image serves, the writer stores the PNGK — nothing to recover.
        Before the deploy (`--koko-only`) an old figure equal to the PNGK is a coincidence and is used."""
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.75)), (None, False))
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.75), pre_deploy=True), (10.0, False))
        four = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'B+', 'CHEMISTRY': 'B'}     # PNGK 3.58
        self.assertEqual(derive_koko(_p(stpm_grades=four, stpm_cgpa=3.58)), (None, False))

    def test_a_figure_outside_0_to_4_is_not_a_calculator_answer(self):
        for stored in (0.0, 4.5):
            with self.subTest(stored=stored):
                self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=stored), pre_deploy=True),
                                 (None, False))

    def test_rounding_is_half_up_to_the_koko_step(self):
        # (3.11 - 3.06) / 0.04 = 1.25 exactly
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.11)), (1.25, True))
        # all-A: average 4.00, 0.9 x 4 = 3.60; 3.90 typed (#173's shape) -> 7.50, reproduces 3.90
        all_a = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'}
        self.assertEqual(derive_koko(_p(stpm_grades=all_a, stpm_cgpa=3.90)), (7.5, True))

    def test_nothing_to_derive_from(self):
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES)), (None, False))
        self.assertEqual(derive_koko(_p(stpm_cgpa=3.2)), (None, False))
        self.assertEqual(derive_koko(_p(stpm_grades={'PA': 'X'}, stpm_cgpa=3.2)), (None, False))

    def test_a_stored_score_stands_unless_the_figure_beside_it_is_still_old(self):
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.75, stpm_koko=6.0)), (6.0, True))
        short = {'PA': 'A', 'MATH_T': 'B'}                          # not calculated: the score stands
        self.assertEqual(derive_koko(_p(stpm_grades=short, stpm_cgpa=3.21, stpm_koko=6.0)), (6.0, True))
        # review 5: re-saved on the OLD image after --koko-only (a new old figure beside a PNGK):
        # the score is derived again from the figure the student just saved
        self.assertEqual(derive_koko(_p(stpm_grades=GRADES, stpm_cgpa=3.21, stpm_koko=6.0)), (3.75, True))


class TestBackfillStpmCgpa(TestCase):
    def setUp(self):
        cohort = make_cohort(min_stpm_pngk=3.5)
        self.flips = make_application('submitted', cohort=cohort, student=make_student(**STPM))
        # PA + one other: not calculated. Average 3.50; koko (3.21 - 3.15) / 0.04 = 1.50.
        self.short = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_grades': {'PA': 'A', 'MATH_T': 'B'}}))
        # Stored figure already the PNGK: nothing to derive after the deploy; before it (koko-only)
        # 17.25 -> clamped to 10, NOT CLEAN.
        self.same = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_cgpa': 3.75}))
        # Written by the C2 image: the PNGK and the student's own score.
        self.kept = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_cgpa': 3.75, 'stpm_koko': 6.0}))
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
        self.assertIn('- NO KOKO\t93.75 -> -', self._line(text, self.same))
        kept = self._line(text, self.kept)
        self.assertIn('6.00 (stored)', kept)
        self.assertIn('-> 90.50', kept)                # overall_from(3.75, 6) = 3.62 -> 90.50
        nokoko = self._line(text, self.nokoko)
        self.assertIn('- NO KOKO', nokoko)
        self.assertIn('- -> -', nokoko)                               # no merit before or after
        self.assertFalse(any(line.startswith(f'#{self.spm.id}\t') for line in text.splitlines()))
        self.assertIn('5 STPM application(s): 2 change CGPA, 1 not calculated (fewer than PA + 3), '
                      '2 gate result(s) flip, 0 koko not clean, 2 with no koko.', text)
        self.assertIn('3 profile(s) to write: 3 co-curriculum score(s) derived (0 not clean), '
                      '2 stpm_cgpa rewritten', text)
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
        self.assertIn('Applied: 3 profile(s) updated.', self._run('--apply'))
        self.assertEqual(self._get(self.flips.profile), (3.75, 3.75))
        self.assertEqual(self._get(self.loose), (3.75, 3.75))
        self.assertEqual(self._get(self.short.profile), (3.21, 1.5))   # not calculated: figure kept
        self.assertEqual(self._get(self.same.profile), (3.75, None))
        self.assertEqual(self._get(self.kept.profile), (3.75, 6.0))    # the student's own score
        self.assertEqual(self._get(self.nokoko.profile), (None, None))  # readers read through: 3.75
        self.assertEqual(StudentProfile.objects.get(pk=self.nokoko.profile.pk).stpm_pngk, 3.75)
        self.assertIn('0 profile(s) to write', self._run())          # idempotent

    def _get(self, p):
        r = StudentProfile.objects.get(pk=p.pk)
        return r.stpm_cgpa, r.stpm_koko

    def test_the_documented_order_koko_only_then_the_cgpa_pass(self):
        """`--koko-only` before the deploy writes only scores (the image serving never reads them);
        the CGPA pass after it. A re-save on the old image in between is re-derived (review 5)."""
        self.assertIn('Applied: 4 profile(s) updated.', self._run('--apply', '--koko-only'))
        self.assertEqual(self._get(self.flips.profile), (3.21, 3.75))
        self.assertEqual(self._get(self.same.profile), (3.75, 10.0))    # pre-deploy: clamped, flagged
        # the old image, live until the deploy: the student re-saves with koko 4.75 -> 3.25 stored
        StudentProfile.objects.filter(pk=self.flips.profile.pk).update(stpm_cgpa=3.25)
        self.assertIn('Applied: 2 profile(s) updated.', self._run('--apply'))
        self.assertEqual(self._get(self.flips.profile), (3.75, 4.75))
        self.assertEqual(self._get(self.loose), (3.75, 3.75))
        self.assertEqual(self._get(self.same.profile), (3.75, 10.0))
        self.assertIn('0 profile(s) to write', self._run())
