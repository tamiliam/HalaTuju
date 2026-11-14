"""Pins for `apps/courses/public.py` (audit A3.12): the facade re-exports, it does not compute."""
from django.test import SimpleTestCase

from apps.courses import exam_questions, public


# The F2 package 1 re-exports: public name -> (home module, name there).
_CATALOGUE_HOMES = {
    'course_pathway_type': ('course_pathway', 'course_pathway_type'),
    'csv_cell': ('csv_safe', 'csv_cell'),
    'calculate_merit_score': ('engine', 'calculate_merit_score'),
    'prepare_merit_inputs': ('engine', 'prepare_merit_inputs'),
    'aliran_of': ('pismp_taxonomy', 'aliran_of'),
    'digits_expr': ('search', '_digits_expr'),
    'apply_people_search': ('search', 'apply_people_search'),
    'people_search_term': ('search', 'people_search_term'),
    'STPM_CGPA_POINTS': ('stpm_engine', 'STPM_CGPA_POINTS'),
    'calculate_stpm_cgpa': ('stpm_engine', 'calculate_stpm_cgpa'),
    'pngk_from_grades': ('stpm_pngk', 'pngk_from_grades'),
    'stpm_cgpa_of': ('stpm_pngk', 'stpm_cgpa_of'),
    'family_of': ('tvet_families', 'family_of'),
    'HELD': ('tvet_institutions', 'HELD'),
    'tidy_parentage_marker': ('utils', 'tidy_parentage_marker'),
}


class TestTheFacadeIsTheSameObjects(SimpleTestCase):
    def test_every_catalogue_name_is_the_home_module_object(self):
        from importlib import import_module
        for name, (module, home_name) in _CATALOGUE_HOMES.items():
            with self.subTest(name=name):
                self.assertIn(name, public.__all__)
                home = import_module('apps.courses.' + module)
                self.assertIs(getattr(public, name), getattr(home, home_name))

    def test_every_listed_name_is_the_home_module_object(self):
        for name in public.__all__:
            if name in ('register_stpm_document_witness', 'StudentProfile', 'FieldTaxonomy'):
                continue            # not exam_questions names; pinned in test_scholarship_public_facade
            if name in _CATALOGUE_HOMES:
                continue            # catalogue / merit names; pinned in the next test
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
