"""BrightPath request #14 — a student is tagged by the results we hold, not the exam she declared.

The reported symptom was a label. The costly half was invisible: the same field decides where the
ranking score is taken from, so a Form Six student declaring STPM was ranked on an STPM CGPA that
does not exist, came out blank, and dropped out of the ordering altogether.

What this must NOT do carries as much weight:

* it must not promote a student to a qualification they never declared — application #15 carries a
  4.0 STPM CGPA and five STPM subjects and SAT NONE OF THEM (she took SPM in 2025 and is on a
  matriculation course). The profile is shared with the course guide, where anyone may type STPM
  grades to explore programmes, so STPM data on a profile is not evidence of STPM results;
* it must not touch the surfaces that read `exam_type` for their own good reasons — who is
  shortlisted, the sponsor-facing band, the semester-result gap, which slip parser runs.
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.serializers_admin import (
    AdminApplicationDetailSerializer, AdminApplicationListSerializer,
    _application_merit_score, held_qualification,
)

SPM = {'bm': 'A', 'eng': 'A', 'math': 'A+', 'hist': 'A', 'moral': 'A'}
STPM = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'}


class TestHeldQualification(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='hq', name='B40', year=2026)

    _n = 0

    def _app(self, **profile_fields):
        type(self)._n += 1
        p = StudentProfile.objects.create(
            supabase_user_id=f'hq-{self._n}', name='A Student', **profile_fields)
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='shortlisted')

    # ── the reported case ────────────────────────────────────────────────────────────────────

    def test_form_six_student_reads_SPM(self):
        # #106: declared STPM at sign-up, sitting it now, holds only SPM results.
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades={}, stpm_cgpa=None)
        self.assertEqual(held_qualification(app.profile), 'spm')

    def test_form_six_student_GAINS_a_merit_score(self):
        """The half nobody could see. A blank merit is not a low score — it is absence from the
        ordering, so she could not be sorted or compared with her peers."""
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades={}, stpm_cgpa=None)
        self.assertIsNotNone(_application_merit_score(app))

    def test_both_admin_surfaces_agree(self):
        # The tag is rendered from two serializers; a fix to one is a fix to half the console.
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades={}, stpm_cgpa=None)
        self.assertEqual(AdminApplicationListSerializer(app).data['qualification'], 'spm')
        self.assertEqual(AdminApplicationDetailSerializer(app).data['qualification'], 'spm')

    # ── what it must leave alone ─────────────────────────────────────────────────────────────

    def test_a_real_stpm_student_is_untouched(self):
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades=STPM, stpm_cgpa=3.7)
        self.assertEqual(held_qualification(app.profile), 'stpm')
        self.assertEqual(_application_merit_score(app), 3.7)

    def test_a_cgpa_alone_still_counts_as_stpm_results(self):
        # Grades can be absent while the CGPA is on file; that is still STPM held.
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades={}, stpm_cgpa=3.2)
        self.assertEqual(held_qualification(app.profile), 'stpm')

    def test_it_NEVER_promotes_a_student_who_declared_spm(self):
        """⚠ #15's shape, and the data is a MIRAGE. She carries a 4.0 CGPA and five STPM subjects
        and sat none of them — SPM in 2025, matriculation now (owner, 2026-08-18). The course guide
        shares this profile and lets anyone type STPM grades to explore programmes, so PRESENT STPM
        data proves nothing; only its ABSENCE is conclusive. A 'latest results we hold' rule would
        have re-labelled a matriculation student STPM on an AWARDED record. Do not widen this."""
        app = self._app(exam_type='spm', grades=SPM, stpm_grades=STPM, stpm_cgpa=4.0)
        self.assertEqual(held_qualification(app.profile), 'spm')
        self.assertNotEqual(_application_merit_score(app), 4.0)

    def test_a_plain_spm_student_is_untouched(self):
        app = self._app(exam_type='spm', grades=SPM, stpm_grades={}, stpm_cgpa=None)
        self.assertEqual(held_qualification(app.profile), 'spm')

    def test_no_results_at_all_repeats_what_the_student_declared(self):
        # Nothing to derive from, so we say what they told us rather than inventing an answer.
        app = self._app(exam_type='stpm', grades={}, stpm_grades={}, stpm_cgpa=None)
        self.assertEqual(held_qualification(app.profile), 'stpm')

    def test_no_profile_is_blank_not_an_error(self):
        self.assertEqual(held_qualification(None), '')

    def test_it_self_corrects_when_the_stpm_results_arrive(self):
        # The reason this is derived and not a stored column: nobody has to remember.
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades={}, stpm_cgpa=None)
        self.assertEqual(held_qualification(app.profile), 'spm')
        app.profile.stpm_cgpa = 3.5
        app.profile.save(update_fields=['stpm_cgpa'])
        app.refresh_from_db()
        self.assertEqual(held_qualification(app.profile), 'stpm')

    # ── the fence ────────────────────────────────────────────────────────────────────────────

    def test_the_DECLARED_field_is_left_alone_on_the_profile(self):
        """Nothing is rewritten. `exam_type` is the student's own answer and other surfaces
        depend on it — shortlisting, the sponsor band, the semester-result gap, the slip parser."""
        app = self._app(exam_type='stpm', grades=SPM, stpm_grades={}, stpm_cgpa=None)
        held_qualification(app.profile)
        app.profile.refresh_from_db()
        self.assertEqual(app.profile.exam_type, 'stpm')
