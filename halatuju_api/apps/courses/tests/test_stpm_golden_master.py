"""
STPM Golden Master Test

Run across all STPM test students to establish a baseline count.
If the count changes, eligibility logic was modified.
"""
import pytest
from apps.courses.stpm_engine import check_stpm_eligibility


# 5 representative STPM students (diverse profiles)
STPM_TEST_STUDENTS = [
    {
        'id': 'strong_science',
        'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'A'},
        'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+', 'addmath': 'A', 'sci': 'A', 'phy': 'A', 'chem': 'A', 'bio': 'A'},
        'cgpa': 3.92,
        'muet_band': 4,
    },
    {
        'id': 'moderate_arts',
        'stpm_grades': {'PA': 'B+', 'ECONOMICS': 'B', 'ACCOUNTING': 'B+', 'BUSINESS': 'B'},
        'spm_grades': {'bm': 'B+', 'eng': 'B', 'hist': 'B', 'math': 'B+', 'addmath': 'C', 'sci': 'B', 'poa': 'A', 'ekonomi': 'B+'},
        'cgpa': 3.17,
        'muet_band': 3,
    },
    {
        'id': 'minimum_pass',
        'stpm_grades': {'PA': 'C', 'MATH_T': 'C', 'PHYSICS': 'C'},
        'spm_grades': {'bm': 'C', 'eng': 'D', 'hist': 'D', 'math': 'C', 'sci': 'C'},
        'cgpa': 2.0,
        'muet_band': 2,
    },
    {
        'id': 'arts_high_muet',
        'stpm_grades': {'PA': 'A-', 'ECONOMICS': 'A', 'GEOGRAPHY': 'B+', 'HISTORY': 'A-'},
        'spm_grades': {'bm': 'A', 'eng': 'A+', 'hist': 'A', 'math': 'A', 'geo': 'A', 'ekonomi': 'A'},
        'cgpa': 3.67,
        'muet_band': 5,
    },
    {
        'id': 'colorblind_science',
        'stpm_grades': {'PA': 'A', 'MATH_T': 'A-', 'PHYSICS': 'A', 'CHEMISTRY': 'B+'},
        'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'addmath': 'A', 'sci': 'A', 'phy': 'A'},
        'cgpa': 3.75,
        'muet_band': 4,
        'colorblind': 'Ya',
    },
]


@pytest.mark.django_db
class TestStpmGoldenMaster:
    @pytest.fixture(autouse=True)
    def load_data(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)

    def test_golden_master(self):
        """Total eligible count across all students must match baseline."""
        total = 0
        per_student = {}
        for student in STPM_TEST_STUDENTS:
            results = check_stpm_eligibility(
                stpm_grades=student['stpm_grades'],
                spm_grades=student['spm_grades'],
                cgpa=student['cgpa'],
                muet_band=student['muet_band'],
                colorblind=student.get('colorblind', 'Tidak'),
            )
            per_student[student['id']] = len(results)
            total += len(results)

        # FIRST RUN: Print the baseline and skip
        # After first run, replace None with the actual number
        GOLDEN_BASELINE = 1994

        if GOLDEN_BASELINE is None:
            for sid, count in per_student.items():
                print(f"  {sid}: {count} programmes")
            print(f"  TOTAL: {total}")
            pytest.skip(f"First run — record baseline: {total}")
        else:
            assert total == GOLDEN_BASELINE, (
                f"Golden master mismatch: expected {GOLDEN_BASELINE}, got {total}. "
                f"Per student: {per_student}"
            )
