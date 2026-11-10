"""Pins for `apps/courses/public.py` (audit A3.12): the facade re-exports, it does not compute."""
from django.test import SimpleTestCase

from apps.courses import exam_questions, public


class TestTheFacadeIsTheSameObjects(SimpleTestCase):
    def test_every_listed_name_is_the_home_module_object(self):
        for name in public.__all__:
            if name in ('register_stpm_document_witness', 'StudentProfile', 'FieldTaxonomy'):
                continue            # not exam_questions names; pinned in test_scholarship_public_facade
            with self.subTest(name=name):
                self.assertIs(getattr(public, name), getattr(exam_questions, name))

    def test_the_names_scholarship_uses_are_all_there(self):
        wanted = {'QUALIFICATION_LABELS', 'THIRD_ROUTE', 'ResultsHeldField', 'completed_qualifications',
                  'diploma_is_public', 'has_stpm_results', 'heading_for', 'held_summary',
                  'is_tertiary', 'merit_100', 'overall_cgpa', 'overall_from', 'results_held',
                  'spm_grades_for', 'spm_grades_none_label', 'spm_slip_comparable',
                  'third_route_overall'}
        self.assertTrue(wanted <= set(public.__all__), wanted - set(public.__all__))


class TestTheWitnessIsRegisteredThroughTheFacade(SimpleTestCase):
    def test_register_sets_the_attribute_results_held_reads(self):
        before = exam_questions.STPM_DOCUMENT_WITNESS
        try:
            def witness(profile):
                return True
            public.register_stpm_document_witness(witness)
            self.assertIs(exam_questions.STPM_DOCUMENT_WITNESS, witness)
        finally:
            exam_questions.STPM_DOCUMENT_WITNESS = before

    def test_scholarship_ready_registered_its_witness(self):
        from apps.scholarship.wrong_slip import stpm_results_on_file
        self.assertIs(exam_questions.STPM_DOCUMENT_WITNESS, stpm_results_on_file)


class TestPatchTargets(SimpleTestCase):
    """A from-import binds early, so WHERE a test patches decides whether the patch bites."""

    def test_a_patch_on_the_facade_reaches_a_caller_that_reads_it_through_the_module(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.scholarship.serializers_admin.application_list import _application_merit_score
        app = SimpleNamespace(profile=object())
        with mock.patch.object(public, 'merit_100', return_value=12.34) as m:
            self.assertEqual(_application_merit_score(app), 12.34)
        m.assert_called_once_with(app.profile)

    def test_a_patch_on_the_home_module_no_longer_reaches_through_the_facade(self):
        # Documents the trap: patch `public.X` (or the caller's own name), never `exam_questions.X`.
        from types import SimpleNamespace
        from unittest import mock

        from apps.scholarship.serializers_admin.application_list import _application_merit_score
        with mock.patch.object(exam_questions, 'merit_100', return_value=12.34):
            self.assertIsNone(_application_merit_score(SimpleNamespace(profile=None)))
