"""`backfill_stpm_cgpa` — STPM CGPA sprint C2 (2026-10-28): preview by default, `--apply` writes.

All grades are made up. The command prints ids and figures only, never a name or an NRIC.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import StudentProfile

from .factories import make_application, make_cohort, make_student

GRADES = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'B+', 'BIOLOGY': 'C'}   # PNGK 3.75
STPM = dict(exam_type='stpm', results_exam_type='stpm', stpm_grades=GRADES, stpm_cgpa=3.21,
            completed_qualifications=['spm', 'stpm'], grades={'bm': 'A'})


class TestBackfillStpmCgpa(TestCase):
    def setUp(self):
        cohort = make_cohort(min_stpm_pngk=3.5)
        self.flips = make_application('submitted', cohort=cohort, student=make_student(**STPM))
        self.short = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_grades': {'PA': 'A', 'MATH_T': 'B'}}))
        self.same = make_application('submitted', cohort=cohort, student=make_student(
            **{**STPM, 'stpm_cgpa': 3.75}))
        self.spm = make_application('submitted', cohort=cohort, student=make_student(
            exam_type='spm', results_exam_type='spm', grades={'bm': 'A'}))
        # A course-guide profile with no application: its column is rewritten too.
        self.loose = make_student(**STPM)

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_stpm_cgpa', *args, stdout=out)
        return out.getvalue()

    def _line(self, text, app):
        return next(line for line in text.splitlines() if line.startswith(f'#{app.id}\t'))

    def test_preview_lists_before_and_after_and_writes_nothing(self):
        text = self._run()
        flips = self._line(text, self.flips)
        self.assertIn('3.21\t3.75', flips)
        self.assertIn('80.25 -> 93.75', flips)
        self.assertIn('REJECT (PNGK 3.21 below 3.5) -> PASS', flips)
        self.assertIn('GATE FLIPS', flips)
        self.assertIn('not calculated', self._line(text, self.short))
        self.assertNotIn('GATE FLIPS', self._line(text, self.same))
        self.assertFalse(any(line.startswith(f'#{self.spm.id}\t') for line in text.splitlines()))
        self.assertIn('3 STPM application(s): 1 change CGPA, 1 not calculated (fewer than PA + 3), '
                      '1 gate result(s) flip.', text)
        self.assertIn('2 profile(s) would have stpm_cgpa rewritten', text)
        self.assertIn('PREVIEW', text)
        self.assertEqual(StudentProfile.objects.get(pk=self.flips.profile.pk).stpm_cgpa, 3.21)

    def test_no_name_or_nric_is_printed(self):
        text = self._run()
        for p in (self.flips.profile, self.short.profile, self.loose):
            self.assertNotIn(p.name, text)
            self.assertNotIn(p.nric, text)

    def test_apply_writes_the_pngk_and_only_where_it_differs(self):
        self.assertIn('Applied: 2 profile(s) updated.', self._run('--apply'))
        get = lambda p: StudentProfile.objects.get(pk=p.pk).stpm_cgpa
        self.assertEqual((get(self.flips.profile), get(self.loose)), (3.75, 3.75))
        self.assertEqual(get(self.short.profile), 3.21)        # too few grades: untouched
        self.assertIn('0 profile(s) would have stpm_cgpa rewritten', self._run())   # idempotent
