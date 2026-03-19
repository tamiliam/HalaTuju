"""
GOLDEN MASTER TEST — Eligibility Engine Verification
=====================================================

Verifies that engine.py produces a stable baseline of eligible matches
across 50 edge-case students × all courses in the database.

BASELINE: Set after first run with DB fixtures (replaces old CSV-based 8283).

To run:
    cd halatuju_api
    python -m pytest apps/courses/tests/test_golden_master.py -v
"""
import pytest
from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.tests.conftest import load_requirements_df


# 50 edge-case students — THE CONSTANTS (unchanged from original)
GOLDEN_STUDENTS = [
    # --- BASELINE (1-8) ---
    # 1. The Perfect Student
    StudentProfile(
        grades={'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+', 'sci': 'A+', 'phy': 'A+', 'chem': 'A+'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 2. The "No Math Credit"
    StudentProfile(
        grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'D', 'sci': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 3. The "Fail BM"
    StudentProfile(
        grades={'bm': 'G', 'eng': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 4. The Colorblind Engineer
    StudentProfile(
        grades={'bm': 'A', 'math': 'A', 'sci': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=True, disability=False
    ),
    # 5. The Non-Citizen
    StudentProfile(
        grades={'bm': 'A', 'math': 'A'},
        gender='Lelaki', nationality='Bukan Warganegara', colorblind=False, disability=False
    ),
    # 6. The "3M Only" Candidate
    StudentProfile(
        grades={'bm': 'G', 'math': 'G', 'hist': 'G', 'eng': 'G'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 7. The Ghost
    StudentProfile(
        grades={},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 8. The Female Student
    StudentProfile(
        grades={'bm': 'A', 'math': 'A', 'sci': 'A'},
        gender='Perempuan', nationality='Warganegara', colorblind=False, disability=False
    ),

    # --- ACADEMIC NUANCES (9-28) ---
    # 9. The Exact-Minimum Credits Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'math': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 10. The One-Extra Credit Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'math': 'C', 'eng': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 11. The All-Pass-No-Credit Student
    StudentProfile(
        grades={'bm': 'D', 'hist': 'D', 'math': 'D', 'eng': 'D', 'sci': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 12. The Science-Only Credit Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'phy': 'C', 'chem': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 13. The Technical-Only Credit Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'rc': 'C', 'cs': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 14. The Mixed Science + Tech
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'phy': 'C', 'rc': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 15. The Language-Heavy Student
    StudentProfile(
        grades={'bm': 'C', 'eng': 'C', 'lang': 'C', 'lit': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 16. The Math-Pass-Only Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'math': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 17. The AddMath-Only Credit Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'addmath': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 18. The English-Fail Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'math': 'C', 'eng': 'G'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 19. The History-Fail High Achiever
    StudentProfile(
        grades={'bm': 'A', 'math': 'A', 'sci': 'A', 'hist': 'G'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 20. The Disabled-But-Academic Star
    StudentProfile(
        grades={'bm': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=True
    ),
    # 21. The Female-in-Male-Heavy-Field
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'math': 'C', 'phy': 'C'},
        gender='Perempuan', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 22. The Colorblind-But-Non-Technical Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'eng': 'C', 'biz': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=True, disability=False
    ),
    # 23. The Interview-Only Candidate
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 24. The Medical-Restriction Flag Case
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'math': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 25. The Overqualified Academic
    StudentProfile(
        grades={'bm': 'A+', 'hist': 'A+', 'math': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 26. The Arts-Only Credit Student
    StudentProfile(
        grades={'bm': 'C', 'hist': 'C', 'psv': 'C', 'lit': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 27. The One-Subject Wonder
    StudentProfile(
        grades={'bm': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 28. The Everything-But-BM Student
    StudentProfile(
        grades={'hist': 'A', 'math': 'A', 'sci': 'A', 'eng': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),

    # --- TVET & VOCATIONAL SPECIALISTS (29-32) ---
    # 29. The "Hands-On" Specialist
    StudentProfile(
        grades={'bm': 'D', 'math': 'G', 'sci': 'G', 'rc': 'E'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 30. The "Agro" Expert
    StudentProfile(
        grades={'bm': 'C', 'math': 'D', 'sci': 'D', 'agro': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 31. The "Vocational Stream" Student
    StudentProfile(
        grades={'bm': 'C', 'math': 'D', 'sci': 'G'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False,
        other_voc=True
    ),
    # 32. The "Home Science" Student
    StudentProfile(
        grades={'bm': 'C', 'math': 'E', 'sci': 'E', 'srt': 'C'},
        gender='Perempuan', nationality='Warganegara', colorblind=False, disability=False
    ),

    # --- USER-DEFINED TVET EDGE CASES (33-42) ---
    # 33. The "3M Survivor"
    StudentProfile(
        grades={'bm': 'D', 'math': 'D', 'sci': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 34. The "Humanities vs STEM" Student
    StudentProfile(
        grades={'bm': 'C', 'math': 'D', 'sci': 'D', 'acc': 'C', 'geo': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 35. The "Science-but-no-Tech" Candidate
    StudentProfile(
        grades={'bm': 'C', 'math': 'G', 'sci': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 36. The "Tech-only Substitute"
    StudentProfile(
        grades={'bm': 'C', 'math': 'G', 'sci': 'G', 'rc': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 37. The "Agro Credit Override"
    StudentProfile(
        grades={'bm': 'C', 'math': 'D', 'sci': 'D', 'agro': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 38. The "English Trap"
    StudentProfile(
        grades={'bm': 'C', 'math': 'C', 'sci': 'C', 'eng': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 39. The "Pure Skills Entry"
    StudentProfile(
        grades={'rc': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False,
        other_voc=True
    ),
    # 40. The "Single-Subject Qualifier"
    StudentProfile(
        grades={'bm': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 41. The "Healthy but Colorblind" Reject
    StudentProfile(
        grades={'bm': 'D', 'math': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=True, disability=False
    ),
    # 42. The "Disability-Only Blocker"
    StudentProfile(
        grades={'rc': 'D'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=True,
        other_voc=True
    ),

    # --- UNIVERSITY (UA) REQUIREMENTS TESTING (43-50) ---
    # 43. The "Grade B Strong Candidate"
    StudentProfile(
        grades={'bm': 'B', 'eng': 'B', 'hist': 'C', 'math': 'B', 'addmath': 'B+', 'phy': 'A', 'chem': 'B', 'bio': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 44. The "Distinction Achiever"
    StudentProfile(
        grades={'bm': 'A', 'eng': 'B+', 'hist': 'C', 'math': 'A-', 'addmath': 'A+', 'phy': 'A', 'chem': 'A-', 'bio': 'A'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 45. The "Grade B Borderline Fail"
    StudentProfile(
        grades={'bm': 'C+', 'eng': 'C+', 'hist': 'C', 'math': 'C+', 'addmath': 'C+', 'phy': 'B', 'chem': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 46. The "Complex OR-Group Qualifier"
    StudentProfile(
        grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'A', 'chem': 'B', 'bio': 'D', 'comp_sci': 'B'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 47. The "Complex OR-Group Fail"
    StudentProfile(
        grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'B', 'chem': 'D', 'bio': 'E'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 48. The "Pendidikan Islam Qualifier"
    StudentProfile(
        grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'islam': 'B', 'phy': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 49. The "Pendidikan Moral Qualifier"
    StudentProfile(
        grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'moral': 'B', 'chem': 'C'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
    # 50. The "Mixed UA Requirements"
    StudentProfile(
        grades={'bm': 'A', 'eng': 'D', 'hist': 'C', 'math': 'B', 'phy': 'A-', 'chem': 'B'},
        gender='Lelaki', nationality='Warganegara', colorblind=False, disability=False
    ),
]


@pytest.mark.django_db
class TestGoldenMaster:
    """Golden Master: 50 students × all courses must produce stable baseline."""

    @pytest.fixture(autouse=True)
    def load_data(self):
        """Load course requirement fixtures into test DB and DataFrame."""
        from django.core.management import call_command
        from io import StringIO
        call_command('loaddata', 'courses', 'requirements', stdout=StringIO(), verbosity=0)
        load_requirements_df()

    def test_total_eligibility_count(self):
        """Total eligible matches must equal the golden baseline."""
        from django.apps import apps
        df_courses = apps.get_app_config('courses').requirements_df

        total = 0
        per_student = {}
        for i, student in enumerate(GOLDEN_STUDENTS, 1):
            count = 0
            for _, row in df_courses.iterrows():
                is_eligible, _ = check_eligibility(student, row.to_dict())
                if is_eligible:
                    count += 1
            per_student[i] = count
            total += count

        # Baseline from DB fixtures (389 courses incl. 6 pre-U).
        # Differs from old CSV-based 8283 because DB data was refined during
        # data integrity sprint (MOHE audit, field corrections).
        GOLDEN_BASELINE = 5319

        assert total == GOLDEN_BASELINE, (
            f"Golden master mismatch: expected {GOLDEN_BASELINE}, got {total}. "
            f"Per student: {per_student}"
        )
