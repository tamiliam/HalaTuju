"""Pins for `apps/courses/public.py` (audit A3.12): the facade re-exports, it does not compute."""
from django.test import SimpleTestCase

from apps.courses import exam_questions, public


class TestTheFacadeIsTheSameObjects(SimpleTestCase):
    def test_every_listed_name_is_the_home_module_object(self):
        for name in public.__all__:
            if name == 'register_stpm_document_witness':
                continue
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
