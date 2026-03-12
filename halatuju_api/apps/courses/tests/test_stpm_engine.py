import pytest

from apps.courses.stpm_engine import calculate_stpm_cgpa, meets_stpm_grade


class TestStpmCgpa:
    def test_perfect_cgpa(self):
        grades = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'}
        assert calculate_stpm_cgpa(grades) == 4.0

    def test_mixed_grades(self):
        grades = {'PA': 'B+', 'ECONOMICS': 'B', 'ACCOUNTING': 'C+'}
        cgpa = calculate_stpm_cgpa(grades)
        # B+=3.33, B=3.00, C+=2.33 → avg = 2.89
        assert cgpa == 2.89

    def test_minimum_pass(self):
        grades = {'PA': 'C-', 'MATH_T': 'C-', 'PHYSICS': 'C-'}
        cgpa = calculate_stpm_cgpa(grades)
        assert cgpa == 2.0  # C- = 2.00

    def test_with_fail(self):
        grades = {'PA': 'A', 'MATH_T': 'F', 'PHYSICS': 'B'}
        cgpa = calculate_stpm_cgpa(grades)
        # A=4.0, F=0.0, B=3.0 → avg = 2.33
        assert cgpa == 2.33

    def test_empty_grades(self):
        assert calculate_stpm_cgpa({}) == 0.0


class TestMeetsStpmGrade:
    def test_exact_match(self):
        assert meets_stpm_grade('B', 'B') is True

    def test_better_than_min(self):
        assert meets_stpm_grade('A', 'C') is True

    def test_worse_than_min(self):
        assert meets_stpm_grade('D', 'B') is False

    def test_invalid_grade(self):
        assert meets_stpm_grade('X', 'B') is False
