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
import copy
import hashlib
import json
from pathlib import Path

import pytest
from apps.courses.engine import StudentProfile, check_eligibility
from apps.courses.tests.conftest import load_requirements_df

# Bumi coverage Sprint D1 appended the 84 UiTM rows of `data/spm/spm_new_courses_D1.json` to the
# fixtures. The ORIGINAL catalogue is everything else, frozen here by count and digest so that a
# later fixture edit cannot quietly redefine "original".
_D1_FILE = Path(__file__).resolve().parents[3] / 'data' / 'spm' / 'spm_new_courses_D1.json'
ORIGINAL_COURSE_COUNT = 389
ORIGINAL_IDS_SHA256 = '2f0ca09dd6aa47ddc89b34134577b09672376658cb86e99a546619ccb0d2d89b'
#: Every golden student's eligible set over the ORIGINAL catalogue, as one digest.
ORIGINAL_SETS_SHA256 = '2b53c316f36b752b24422ebd7de50d3545a1bf08df9a2afae4b57bf34e9e9684'
GOLDEN_BASELINE = 5319                 # original catalogue, and the full one for a non-Bumi student
GOLDEN_BASELINE_BUMI = 5865   # full catalogue, the same 50 students as Bumiputera (strict reading)


def _digest(lines):
    return hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()


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

    @staticmethod
    def _eligible_sets(students):
        from django.apps import apps
        rows = [row.to_dict() for _, row in apps.get_app_config('courses').requirements_df.iterrows()]
        return [{r['course_id'] for r in rows if check_eligibility(s, r)[0]} for s in students]

    @staticmethod
    def _original_ids():
        from apps.courses.models import Course
        d1 = {c['course_id'] for c in json.loads(_D1_FILE.read_text(encoding='utf-8'))['courses']}
        return set(Course.objects.values_list('course_id', flat=True)) - d1

    def test_the_original_catalogue_is_frozen(self):
        ids = self._original_ids()
        assert len(ids) == ORIGINAL_COURSE_COUNT
        assert _digest(sorted(ids)) == ORIGINAL_IDS_SHA256

    def test_total_eligibility_count(self):
        """Total eligible matches must equal the golden baseline — over the ORIGINAL catalogue,
        with every student's eligible set identical to the frozen one (Bumi Sprint D1)."""
        original = self._original_ids()
        sets = [s & original for s in self._eligible_sets(GOLDEN_STUDENTS)]
        total = sum(len(s) for s in sets)
        # Baseline from DB fixtures (389 courses incl. 6 pre-U).
        # Differs from old CSV-based 8283 because DB data was refined during
        # data integrity sprint (MOHE audit, field corrections).
        assert total == GOLDEN_BASELINE, (
            f"Golden master mismatch: expected {GOLDEN_BASELINE}, got {total}. "
            f"Per student: {[len(s) for s in sets]}"
        )
        lines = [f'{i}:{cid}' for i, s in enumerate(sets, 1) for cid in sorted(s)]
        assert _digest(lines) == ORIGINAL_SETS_SHA256, "a golden student's eligible set changed"

    def test_a_non_bumi_student_gains_nothing_from_the_new_rows(self):
        """Every D1 row is Bumiputera-only, so the FULL catalogue gives the same 5,319."""
        assert sum(len(s) for s in self._eligible_sets(GOLDEN_STUDENTS)) == GOLDEN_BASELINE

    def test_the_bumi_baseline(self):
        bumi = []
        for student in GOLDEN_STUDENTS:
            twin = copy.copy(student)
            twin.bumiputera = True
            bumi.append(twin)
        sets = self._eligible_sets(bumi)
        assert sum(len(s) for s in sets) == GOLDEN_BASELINE_BUMI, [len(s) for s in sets]
        original = self._original_ids()
        assert [s & original for s in sets] == [s & original for s in self._eligible_sets(GOLDEN_STUDENTS)]
