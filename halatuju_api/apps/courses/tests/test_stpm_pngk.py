"""THE STPM CGPA FROM THE GRADES (`apps/courses/stpm_pngk.py`) — STPM CGPA sprint C2, 2026-10-28.

PNGK = round_half_up((Pengajian Am + best three others) / 4, 2) on the MQA scale; fewer than PA +
three graded subjects → None, and `stpm_cgpa_of` falls back to the stored figure. All grades here
are made up; none is a real student's.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.courses.stpm_engine import calculate_stpm_cgpa
from apps.courses.stpm_pngk import pngk_from_grades, stpm_cgpa_is_calculated, stpm_cgpa_of


class TestPngkFromGrades(SimpleTestCase):
    def test_all_a_is_four(self):
        """Roadmap case: all-A grades are 4.00 on the certificate, whatever was typed."""
        self.assertEqual(pngk_from_grades({'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A',
                                           'CHEMISTRY': 'A', 'BIOLOGY': 'A'}), 4.0)

    def test_pa_plus_exactly_three(self):
        # (4 + 3.67 + 3.67 + 3.33) / 4 = 3.6675 → 3.67
        self.assertEqual(pngk_from_grades({'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-',
                                           'CHEMISTRY': 'B+'}), 3.67)

    def test_best_three_others_count_and_the_fifth_does_not(self):
        """A five-subject candidate: the weakest non-PA subject is dropped. The plain average of
        all five — the old reading, and roadmap case #252's typed figure — is NOT the PNGK."""
        grades = {'PA': 'B', 'MATH_T': 'A', 'PHYSICS': 'B+', 'CHEMISTRY': 'C', 'BIOLOGY': 'A-'}
        # (3.00 + 4.00 + 3.67 + 3.33) / 4 = 3.50
        self.assertEqual(pngk_from_grades(grades), 3.5)
        self.assertNotEqual(calculate_stpm_cgpa(grades), 3.5)      # 3.20: the plain average

    def test_pa_always_counts_even_when_weaker_than_the_dropped_subject(self):
        grades = {'PA': 'D', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A', 'BIOLOGY': 'A'}
        self.assertEqual(pngk_from_grades(grades), 3.25)            # (1 + 4 + 4 + 4) / 4

    def test_rounds_half_up_not_to_the_float_below(self):
        # (4 + 3.67 + 3.67 + 3.00) / 4 = 3.585 exactly; a float round() gives 3.58
        self.assertEqual(pngk_from_grades({'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A-',
                                           'CHEMISTRY': 'B'}), 3.59)

    def test_all_f_is_zero_not_none(self):
        self.assertEqual(pngk_from_grades({'PA': 'F', 'A1': 'F', 'A2': 'F', 'A3': 'F'}), 0.0)

    def test_no_pngk_without_pengajian_am(self):
        self.assertIsNone(pngk_from_grades({'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A',
                                            'BIOLOGY': 'A'}))

    def test_no_pngk_with_only_two_others(self):
        self.assertIsNone(pngk_from_grades({'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'}))

    def test_blank_and_unknown_grades_do_not_count(self):
        """A blank cell, a grade off the scale and the legacy E / G aliases count as no grade."""
        self.assertIsNone(pngk_from_grades({'PA': 'A', 'MATH_T': 'A', 'PHYSICS': '',
                                            'CHEMISTRY': 'E', 'BIOLOGY': 'G', 'ICT': 'Z'}))
        self.assertIsNone(pngk_from_grades({'PA': '', 'MATH_T': 'A', 'PHYSICS': 'A',
                                            'CHEMISTRY': 'A'}))

    def test_case_and_spaces_in_a_grade_are_tolerated(self):
        self.assertEqual(pngk_from_grades({'PA': ' a ', 'MATH_T': 'b+', 'PHYSICS': 'B+',
                                           'CHEMISTRY': 'b+'}), 3.5)

    def test_not_a_dict(self):
        for value in (None, [], 'A', 3.5):
            with self.subTest(value=repr(value)):
                self.assertIsNone(pngk_from_grades(value))


class TestStpmCgpaOf(SimpleTestCase):
    FULL = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'}

    def test_the_grades_win_over_a_typed_figure(self):
        p = SimpleNamespace(stpm_grades=self.FULL, stpm_cgpa=3.9)
        self.assertEqual(stpm_cgpa_of(p), 4.0)
        self.assertTrue(stpm_cgpa_is_calculated(p))

    def test_too_few_grades_keep_the_stored_figure(self):
        p = SimpleNamespace(stpm_grades={'PA': 'A', 'MATH_T': 'B'}, stpm_cgpa=3.21)
        self.assertEqual(stpm_cgpa_of(p), 3.21)
        self.assertFalse(stpm_cgpa_is_calculated(p))

    def test_nothing_at_all(self):
        self.assertIsNone(stpm_cgpa_of(None))
        self.assertIsNone(stpm_cgpa_of(SimpleNamespace(stpm_grades={}, stpm_cgpa=None)))
        self.assertIsNone(stpm_cgpa_of(SimpleNamespace()))

    def test_a_stored_figure_is_returned_as_it_is_for_the_callers_guards(self):
        """No range guard here: `overall_cgpa` and the gate keep their own, as before."""
        self.assertEqual(stpm_cgpa_of(SimpleNamespace(stpm_grades={}, stpm_cgpa=0.0)), 0.0)
        self.assertIsNone(stpm_cgpa_of(SimpleNamespace(stpm_grades={}, stpm_cgpa='x')))
