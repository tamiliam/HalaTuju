import pytest

from apps.courses.stpm_engine import (
    calculate_stpm_cgpa, meets_stpm_grade, check_stpm_eligibility,
)


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
        assert cgpa == 1.67  # C- = 1.67

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


@pytest.mark.django_db
class TestStpmEligibility:
    @pytest.fixture(autouse=True)
    def load_data(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())

    def test_strong_science_student_gets_results(self):
        """Perfect science student should qualify for many programmes."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+', 'addmath': 'A', 'sci': 'A'},
            cgpa=3.89, muet_band=4,
        )
        assert len(results) > 50  # Strong student should qualify for many

    def test_cgpa_filter(self):
        """Higher CGPA should yield more results than lower."""
        high = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4,
        )
        low = check_stpm_eligibility(
            stpm_grades={'PA': 'C', 'MATH_T': 'C', 'PHYSICS': 'C'},
            spm_grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C'},
            cgpa=2.0, muet_band=2,
        )
        assert len(high) > len(low)

    def test_muet_filter(self):
        """Results should respect MUET band requirement."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=2,
        )
        for r in results:
            assert r['min_muet_band'] <= 2

    def test_subject_requirement_check(self):
        """Arts-only student should not see programmes requiring Physics."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'ECONOMICS': 'A', 'ACCOUNTING': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4,
        )
        # No result should require physics since student doesn't have it
        # (the engine filters them out, so we just verify none slipped through)
        from apps.courses.models import StpmRequirement
        physics_ids = set(
            StpmRequirement.objects.filter(stpm_req_physics=True)
            .values_list('course_id', flat=True)
        )
        for r in results:
            assert r['program_id'] not in physics_ids, (
                f"{r['program_name']} requires Physics but student has none"
            )

    def test_result_shape(self):
        """Each result should have expected fields."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4,
        )
        assert len(results) > 0
        r = results[0]
        for key in ['program_id', 'program_name', 'university', 'stream',
                     'min_cgpa', 'min_muet_band', 'req_interview', 'no_colorblind']:
            assert key in r, f"Missing key: {key}"

    def test_colorblind_filter(self):
        """Colorblind students should see fewer or equal results."""
        all_results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'CHEMISTRY': 'A', 'BIOLOGY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
            cgpa=3.8, muet_band=4, colorblind='Tidak',
        )
        cb_results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'CHEMISTRY': 'A', 'BIOLOGY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
            cgpa=3.8, muet_band=4, colorblind='Ya',
        )
        assert len(all_results) >= len(cb_results)
