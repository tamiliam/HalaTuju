"""Request #62, owner ruling 2026-11-06: "SPM applicants will onboard by filling SPM grades.
STPM/etc. applicants onboard by filing STPM or alternative routes. For these students, only SPM
prereq is available. SPM on its own will not be. As such, it is only right to keep it consistent:
wire all SPM related matters to SPM prereq."

Every scholarship reader of SPM grades goes through `exam_questions.spm_grades_for`: an SPM holder
reads `grades`; an STPM / Matriculation / Asasi / Diploma holder reads `spm_prereq_grades` ONLY (her
`grades` are never read). For each reader: SPM unchanged; tertiary with a prereq uses it; tertiary
with only `grades` reads as none declared; tertiary with both (differing) -> the prereq wins."""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship import gap_engine, offer_pathway as op, profile_engine
from apps.scholarship.emails.sending import english_only_email
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.pool import academic_band
from apps.scholarship.serializers import ApplicationReadSerializer
from apps.scholarship.serializers_admin import (
    AdminApplicationDetailSerializer, AdminApplicationListSerializer,
)
from apps.scholarship.services import autofill_pathway_from_offer
from apps.scholarship.services.profile_sync import build_intake_snapshot
from apps.scholarship.tests.factories import make_application, make_student

NOT_DECLARED = 'not declared (optional for this route)'
STPM = dict(exam_type='stpm', results_exam_type='stpm', stpm_cgpa=3.71, stpm_grades={'PA': 'A'},
            completed_qualifications=['spm', 'stpm'])
MATRIC = dict(exam_type='matric', results_exam_type='matric', higher_cgpa=3.5, higher_koko=8,
              completed_qualifications=['spm', 'matric'])
SPM = dict(exam_type='spm', results_exam_type='spm', completed_qualifications=['spm'])
#: The prereq: 3 A's, English A+, a science elective, Bahasa Tamil.
PREREQ = {'bm': 'A', 'eng': 'A+', 'math': 'A', 'phy': 'B', 'bahasa_tamil': 'B'}
#: An earlier SPM-page entry that DIFFERS: 1 A, English C, no science elective, no vernacular.
OLD = {'bm': 'A', 'eng': 'C', 'math': 'B', 'geo': 'B'}


def _app(route, *, grades=None, prereq=None, **app_over):
    student = make_student(**route, grades=grades or {}, spm_prereq_grades=prereq or {})
    return make_application('submitted', student=student, **app_over)


def _line(prompt, label):
    return next(ln for ln in prompt.splitlines() if ln.startswith(label))


class ProfilePromptSpmLine(TestCase):
    def _spm_line(self, app):
        return _line(profile_engine._build_prompt(app), 'SPM grades:').split('    STPM PNGK')[0]

    def test_spm_holder_unchanged(self):
        self.assertEqual(self._spm_line(_app(SPM, grades=OLD)),
                         'SPM grades: 1 A-grade subjects out of 4 (1 A) spanning languages')
        self.assertEqual(self._spm_line(_app(SPM)), 'SPM grades: not provided')

    def test_tertiary_reads_the_prereq_only(self):
        for route in (STPM, MATRIC):
            with self.subTest(route=route['exam_type']):
                want = 'SPM grades: 3 A-grade subjects out of 5 (1 A+, 2 A)'
                self.assertTrue(self._spm_line(_app(route, prereq=PREREQ)).startswith(want))
                # both on file, differing: the prereq wins, `grades` ignored
                self.assertTrue(self._spm_line(_app(route, grades=OLD, prereq=PREREQ)).startswith(want))
                # only `grades`: none declared, optional on her route (not "not provided")
                self.assertEqual(self._spm_line(_app(route, grades=OLD)), f'SPM grades: {NOT_DECLARED}')

    def test_prompt_version_bumped(self):
        self.assertEqual(profile_engine.PROMPT_VERSION, '2026-11-06.1')


class GapPromptAcademicLine(TestCase):
    def _academic(self, app):
        prompt = gap_engine._build_gap_prompt(app)
        return prompt.split('ACADEMIC RECORD\n', 1)[1].splitlines()[0]

    def test_spm_holder_unchanged(self):
        self.assertEqual(self._academic(_app(SPM, grades=OLD)),
                         'bm: A, eng: C, math: B, geo: B  (A-grade count: 1)')
        self.assertEqual(self._academic(_app(SPM)), '(not provided)')

    def test_tertiary_reads_the_prereq_only(self):
        want = 'bm: A, eng: A+, math: A, phy: B, bahasa_tamil: B  (A-grade count: 3)'
        for route in (STPM, MATRIC):
            with self.subTest(route=route['exam_type']):
                self.assertEqual(self._academic(_app(route, prereq=PREREQ)), want)
                self.assertEqual(self._academic(_app(route, grades=OLD, prereq=PREREQ)), want)
                self.assertEqual(self._academic(_app(route, grades=OLD)), NOT_DECLARED)


class SpmACount(TestCase):
    def _counts(self, app):
        return (AdminApplicationListSerializer().get_spm_a_count(app),
                AdminApplicationDetailSerializer().get_spm_a_count(app),
                ApplicationReadSerializer().get_spm_a_count(app),
                build_intake_snapshot(app.profile, {})['profile']['spm_a_count'])

    def test_each_case(self):
        self.assertEqual(self._counts(_app(SPM, grades=OLD)), (1, 1, 1, 1))
        self.assertEqual(self._counts(_app(STPM, prereq=PREREQ)), (3, 3, 3, 3))
        self.assertEqual(self._counts(_app(STPM, grades=OLD)), (0, 0, 0, 0))
        self.assertEqual(self._counts(_app(MATRIC, grades=OLD, prereq=PREREQ)), (3, 3, 3, 3))

    def test_pool_label_spm_holder_unchanged(self):
        self.assertEqual(academic_band(_app(SPM, grades=OLD).profile), 'SPM · 1 A')


class EnglishOnlyEmail(TestCase):
    def _en(self, app):
        app.locale = 'en'
        return english_only_email(app)

    def test_each_case(self):
        self.assertTrue(self._en(_app(SPM, grades=PREREQ)))
        self.assertFalse(self._en(_app(SPM, grades=OLD)))
        self.assertTrue(self._en(_app(STPM, prereq=PREREQ)))
        # only `grades` (even an A+ there): not read -> no English grade -> bilingual (safe default)
        self.assertFalse(self._en(_app(STPM, grades={'eng': 'A+'})))
        self.assertFalse(self._en(_app(MATRIC, grades=OLD)))
        self.assertTrue(self._en(_app(MATRIC, grades=OLD, prereq=PREREQ)))
        self.assertFalse(self._en(_app(MATRIC, grades=PREREQ, prereq=OLD)))   # prereq wins


class OfferPathwayInference(TestCase):
    def test_pismp_aliran(self):
        self.assertEqual(op.infer_pismp_aliran(_app(SPM, grades=PREREQ).profile), 'sjkt')
        self.assertEqual(op.infer_pismp_aliran(_app(STPM, prereq=PREREQ).profile), 'sjkt')
        self.assertEqual(op.infer_pismp_aliran(_app(STPM, grades=PREREQ).profile), 'sk')
        self.assertEqual(op.infer_pismp_aliran(_app(STPM, grades=PREREQ, prereq=OLD).profile), 'sk')
        self.assertEqual(op.infer_pismp_aliran(None), 'sk')

    def _track(self, app):
        prof = app.profile
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {
                'candidate_name': prof.name, 'candidate_nric': prof.nric.replace('-', ''),
                'programme': 'Tingkatan Enam Semester 1',
                'institution': 'SEKOLAH MENENGAH KEBANGSAAN TUN HUSSEIN ONN'},
                'student_verdict': 'ok', 'warnings': [], 'error': ''},
            vision_run_at=timezone.now())
        self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        return app.pre_u_track

    def test_stpm_bidang_from_offer_sync(self):
        blank = dict(chosen_pathway='', pre_u_institution='', pre_u_track='',
                     pathway_certainty='uncertain', chosen_programme={})
        self.assertEqual(self._track(_app(SPM, grades=PREREQ, **blank)), 'sains')
        self.assertEqual(self._track(_app(STPM, prereq=PREREQ, **blank)), 'sains')
        self.assertEqual(self._track(_app(STPM, grades=PREREQ, **blank)), 'sains_sosial')
        self.assertEqual(self._track(_app(MATRIC, grades=PREREQ, prereq=OLD, **blank)), 'sains_sosial')
