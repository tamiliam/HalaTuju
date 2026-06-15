"""Academic slip fixes:
 #1 An undeclared extra subject on the slip is a SOFT discrepancy (Gopal nudges /profile,
    Academic tile 'review', Check 2 follows up) — NOT a document mismatch / submission block.
 #2 A leaked 'NAMA :' label no longer turns a genuine slip into a false name_mismatch.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.resolution import doc_match_verdict
from apps.scholarship.verdict_engine import build_verdict
from apps.scholarship.vision import doc_student_verdict, _strip_name_label


class TestNameLabelStrip(TestCase):
    def test_strips_leaked_label(self):
        self.assertEqual(_strip_name_label('NAMA : SANJANA A/P KALIANA KUMAR'),
                         'SANJANA A/P KALIANA KUMAR')
        self.assertEqual(_strip_name_label('NAME - HARISH A/L SANGGAR'), 'HARISH A/L SANGGAR')

    def test_leaves_real_name_untouched(self):
        self.assertEqual(_strip_name_label('SANJANA A/P KALIANAKUMAR'), 'SANJANA A/P KALIANAKUMAR')

    def test_verdict_ok_despite_label_and_spacing(self):
        # #2 end-to-end: 'NAMA :' prefix + a surname OCR-split ('KALIANA KUMAR') vs the typed
        # 'KALIANAKUMAR' → still 'ok' (was a false name_mismatch).
        v = doc_student_verdict('results_slip', {'candidate_name': 'NAMA : SANJANA A / P KALIANA KUMAR'},
                                names=['SANJANA A/P KALIANAKUMAR'])
        self.assertEqual(v, 'ok')

    def test_genuine_wrong_name_still_mismatches(self):
        v = doc_student_verdict('results_slip', {'candidate_name': 'NAMA : SOMEONE ELSE BINTI OTHER'},
                                names=['SANJANA A/P KALIANAKUMAR'])
        self.assertEqual(v, 'name_mismatch')


class _SlipBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'slip-{self.id()}', name='HARISH A/L SANGGAR',
            nric='080101-10-1234', grades={'bm': 'A'})       # declared ONLY Bahasa Melayu
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='profile_complete',
            profile_completed_at=timezone.now())

    def _slip(self, results, sv='ok'):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='results_slip', storage_path=f'{self.app.id}/rs/x',
            vision_run_at=timezone.now(),
            vision_fields={'student_verdict': sv,
                           'fields': {'candidate_name': 'HARISH A/L SANGGAR', 'results': results}})


class TestUndeclaredSubjectIsSoft(_SlipBase):
    # Slip lists Bahasa Melayu (declared, grade matches) + Biologi (NOT in profile).
    EXTRA = [{'subject': 'BAHASA MELAYU', 'grade': 'A'}, {'subject': 'BIOLOGI', 'grade': 'B'}]

    def test_doc_not_a_mismatch(self):
        # #1: the document must NOT be a mismatch (no submission block) on an undeclared subject.
        self.assertEqual(doc_match_verdict(self._slip(self.EXTRA)), 'ok')

    def test_academic_tile_is_soft_review_with_caveat(self):
        self._slip(self.EXTRA)
        ac = next(f for f in build_verdict(self.app) if f['fact'] == 'academic')
        self.assertEqual(ac['status'], 'review')                 # soft, never 'gap'
        self.assertIn('academic_missing_subjects', [i['code'] for i in ac['unresolved']])

    def test_grade_mismatch_still_blocks(self):
        # Regression: a real GRADE disagreement on a declared subject is still a doc mismatch.
        slip = self._slip([{'subject': 'BAHASA MELAYU', 'grade': 'C'}])   # declared A, slip C
        self.assertEqual(doc_match_verdict(slip), 'mismatch')

    def test_name_mismatch_still_blocks(self):
        self.assertEqual(doc_match_verdict(self._slip(self.EXTRA, sv='name_mismatch')), 'mismatch')
