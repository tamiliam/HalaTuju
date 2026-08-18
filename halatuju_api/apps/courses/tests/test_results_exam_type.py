"""The server-side half of the results-completion marker (BrightPath request #14, states 1 and 4).

`results_exam_type` is only meaningful if it cannot be set by a selection. The browser enforces
that by writing it solely when a results form completes — but a promise kept only in the client is
not a guarantee, and this field exists precisely because `exam_type` had none. So the serializer
checks it is backed by results actually on file, against the payload MERGED with the stored row.

It DROPS an unbacked value rather than rejecting the request: the marker is a refinement, and
failing a student's whole profile sync over it would trade a display fault for a data-loss one.
"""
from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.courses.serializers import ProfileUpdateSerializer

SPM = {'bm': 'A', 'eng': 'A+', 'math': 'A'}
STPM = {'PA': 'A', 'MATH_T': 'A-'}


class TestResultsExamTypeGuard(TestCase):
    _n = 0

    def _profile(self, **fields):
        type(self)._n += 1
        return StudentProfile.objects.create(
            supabase_user_id=f'ret-{self._n}', name='A Student', **fields)

    def _save(self, profile, data):
        s = ProfileUpdateSerializer(profile, data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    def test_it_is_stored_when_the_results_arrive_in_the_same_payload(self):
        # The real shape: the onboarding sync sends the grades and the marker together.
        p = self._profile()
        saved = self._save(p, {'grades': SPM, 'exam_type': 'spm', 'results_exam_type': 'spm'})
        self.assertEqual(saved.results_exam_type, 'spm')

    def test_it_is_stored_when_the_results_are_already_on_the_row(self):
        p = self._profile(grades=SPM)
        self.assertEqual(self._save(p, {'results_exam_type': 'spm'}).results_exam_type, 'spm')

    def test_an_UNBACKED_claim_is_dropped_not_rejected(self):
        """⚠ The whole point. This is the Form Six shape — STPM claimed, no STPM results — and it
        must not be recordable, however it arrives."""
        p = self._profile(grades=SPM)
        saved = self._save(p, {'results_exam_type': 'stpm'})
        self.assertEqual(saved.results_exam_type, '')
        self.assertEqual(saved.grades, SPM, 'the rest of the sync still lands')

    def test_a_cgpa_alone_backs_an_stpm_claim(self):
        p = self._profile(grades=SPM, stpm_cgpa=3.4)
        self.assertEqual(self._save(p, {'results_exam_type': 'stpm'}).results_exam_type, 'stpm')

    def test_stpm_grades_alone_back_it_too(self):
        p = self._profile(stpm_grades=STPM)
        self.assertEqual(self._save(p, {'results_exam_type': 'stpm'}).results_exam_type, 'stpm')

    def test_an_spm_claim_with_no_grades_anywhere_is_dropped(self):
        p = self._profile()
        self.assertEqual(self._save(p, {'results_exam_type': 'spm'}).results_exam_type, '')

    def test_omitting_it_leaves_a_recorded_value_alone(self):
        # A partial sync from a browser that never completed a form must not blank it.
        p = self._profile(grades=SPM, results_exam_type='spm')
        self.assertEqual(self._save(p, {'school': 'SMK Contoh'}).results_exam_type, 'spm')

    def test_exam_type_is_UNTOUCHED_by_the_guard(self):
        # The declaration is still the student's own answer to a different question.
        p = self._profile(grades=SPM)
        saved = self._save(p, {'exam_type': 'stpm', 'results_exam_type': 'stpm'})
        self.assertEqual(saved.exam_type, 'stpm', 'the declaration stands')
        self.assertEqual(saved.results_exam_type, '', 'the unbacked marker does not')
