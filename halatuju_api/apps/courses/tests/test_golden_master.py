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
# fixtures, Sprint D2 the 66 rows of `spm_new_courses_D2.json`, and Sprint F1 the 35 public UP_TVET
# courses of `data/tvet/tvet_new_courses_F1.json`. The ORIGINAL catalogue is everything else, frozen
# here by count and digest so that a later fixture edit cannot quietly redefine "original".
_D1_FILE = Path(__file__).resolve().parents[3] / 'data' / 'spm' / 'spm_new_courses_D1.json'
_D2_FILE = _D1_FILE.with_name('spm_new_courses_D2.json')
_F1_FILE = _D1_FILE.parents[1] / 'tvet' / 'tvet_new_courses_F1.json'
_F1B_FILE = _D1_FILE.parents[1] / 'tvet' / 'held_flag_fix_F1b.json'
# Sprint F2 appended the 182 public MARA UP_TVET courses of `data/tvet/tvet_new_courses_F2.json`.
_F2_FILE = _D1_FILE.parents[1] / 'tvet' / 'tvet_new_courses_F2.json'
ORIGINAL_COURSE_COUNT = 389
ORIGINAL_IDS_SHA256 = '2f0ca09dd6aa47ddc89b34134577b09672376658cb86e99a546619ccb0d2d89b'
# Bumi F1b (2026-10-30) re-baselined the original catalogue ON PURPOSE: 63 held UP_TVET courses (84 held
# IJTM-* / IKBN-* rows are part of the original 389) took their pages' req_malaysian / no_colorblind /
# no_disability and an empty remark took F1's text (`data/tvet/held_flag_fix_F1b.json`). The 305 other
# original rows did not move (pinned below by digest), the remarks move nothing, and reversing the file
# gives back the frozen pre-F1b picture exactly.
#: Every golden student's eligible set over the ORIGINAL catalogue, as one digest.
ORIGINAL_SETS_SHA256 = 'a9b509e036a02b0d178da8b47768cd1ad2ed5271399a401f4fdf0884e7f94364'
GOLDEN_BASELINE = 5293                 # the original catalogue, for every student (5,319 before F1b)
#: The same over the original catalogue WITHOUT the 84 held TVET rows: identical before and after F1b.
ORIGINAL_NON_HELD_SETS_SHA256 = '23a7420c87261811ef71b7f7afbeb4ec2e21d22f1571781dd9de98a2be903a88'
ORIGINAL_NON_HELD_BASELINE = 2712
#: Before F1b (the file's `old` values): the frozen picture every earlier sprint pinned.
PRE_F1B_SETS_SHA256 = '2b53c316f36b752b24422ebd7de50d3545a1bf08df9a2afae4b57bf34e9e9684'
PRE_F1B_BASELINE = 5319
# Sprint F1: the non-MARA UP_TVET rows are mostly OPEN (no academic rule), so a non-Bumi student now
# gains EXACTLY those F1 rows she meets, and nothing else: pinned as a count and a digest.
GOLDEN_F1_NON_BUMI_GAIN = 1494        # 30-33 per citizen, 20 if colour-blind, 0 for the non-citizen
F1_NON_BUMI_GAIN_SHA256 = '07d39bf4539eecbf8a31d5652a6fea97e566cef3c6fbd393e15b0b6021c9eb85'
# Sprint F2: 178 of the 182 MARA courses are Bumi-only; the other 4 are GIATMARA campuses whose pages are
# silent on Bumiputera (3 also on citizenship). A non-Bumi student gains EXACTLY those 4 open rows she meets
# (49-50 x 4: the non-citizen meets the 3 that do not ask citizenship), pinned by count and digest.
GOLDEN_F2_NON_BUMI_GAIN = 199
F2_NON_BUMI_GAIN_SHA256 = 'b94db31749f0e4c7cf262c0c6e687e9f40bb303aa99f4c1d8cd29d07d1812780'
GOLDEN_BASELINE_FULL = GOLDEN_BASELINE + GOLDEN_F1_NON_BUMI_GAIN + GOLDEN_F2_NON_BUMI_GAIN   # 6,986 (6,787 before F2)
# Full catalogue, the same 50 students as Bumiputera: 5,293 + 546 (D1 UiTM, strict reading) + 121 (D2,
# after review round 1's strict reading of MARA's "any N subjects": 141 -> 121) + 1,592 (F1: the
# 1,494 above + the two Bumi-only KEMAS rows, 49 each) = 7,552 (7,578 before F1b), + the F2 rows below.
GOLDEN_BASELINE_BUMI_BEFORE_F2 = 7552
#: What the 50 Bumiputera twins gain over the ORIGINAL catalogue from D1 + D2 + F1 (the rows they meet), as
#: one digest, so a changed Bumi-only row cannot hide behind an unchanged total (review 2026-10-29).
BUMI_GAIN_SHA256 = '0f70a1c805d7e73077c1bf7b91e2e1665dd3850a7d6bfd2bf17e802e31748818'
#: Sprint F2: what the Bumiputera twins gain from the MARA rows, pinned by count and digest.
GOLDEN_F2_BUMI_GAIN = 5079
F2_BUMI_GAIN_SHA256 = '254c50a42800997e0a82eaf2f3e6274ac85aa246105a7803b5c7a8b1a57d9ec3'
GOLDEN_BASELINE_BUMI = GOLDEN_BASELINE_BUMI_BEFORE_F2 + GOLDEN_F2_BUMI_GAIN   # 12,631


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
    def _added_ids(path):
        return {c['course_id'] for c in json.loads(path.read_text(encoding='utf-8'))['courses']}

    def _original_ids(self):
        from apps.courses.models import Course
        added = self._added_ids(_D1_FILE) | self._added_ids(_D2_FILE) | self._added_ids(_F1_FILE) \
            | self._added_ids(_F2_FILE)
        return set(Course.objects.values_list('course_id', flat=True)) - added

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

    def test_a_non_bumi_student_gains_exactly_the_f1_and_f2_open_sets(self):
        """Every D1 row is Bumiputera-only and no golden student holds the Islamic subjects the 14 open
        D2 rows need, so D1 and D2 add nothing at bumi=False. Sprint F1's public UP_TVET rows are mostly
        open: a non-Bumi student gains exactly the F1 rows she meets (pinned by count and digest), never
        a Bumi-only row, and never a D1 / D2 row. Sprint F2's MARA rows are Bumi-only but for 4 GIATMARA
        campus pages that say nothing about it: she gains exactly those she meets (pinned the same way)."""
        from apps.courses.models import CourseRequirement
        sets = self._eligible_sets(GOLDEN_STUDENTS)
        original = self._original_ids()
        f1, f2 = self._added_ids(_F1_FILE), self._added_ids(_F2_FILE)
        gained = [s - original for s in sets]
        assert all(g <= f1 | f2 for g in gained), 'a non-Bumi student gained a non-F1 / F2 row'
        f1_gain = [g & f1 for g in gained]
        assert sum(len(g) for g in f1_gain) == GOLDEN_F1_NON_BUMI_GAIN, [len(g) for g in f1_gain]
        lines = [f'{i}:{cid}' for i, g in enumerate(f1_gain, 1) for cid in sorted(g)]
        assert _digest(lines) == F1_NON_BUMI_GAIN_SHA256, "a golden student's F1 gain changed"
        f2_gain = [g & f2 for g in gained]
        assert sum(len(g) for g in f2_gain) == GOLDEN_F2_NON_BUMI_GAIN, [len(g) for g in f2_gain]
        lines = [f'{i}:{cid}' for i, g in enumerate(f2_gain, 1) for cid in sorted(g)]
        assert _digest(lines) == F2_NON_BUMI_GAIN_SHA256, "a golden student's F2 (MARA) gain changed"
        assert sum(len(s) for s in sets) == GOLDEN_BASELINE_FULL
        bumi_only = set(CourseRequirement.objects.filter(req_bumiputera=True).values_list('course_id', flat=True))
        assert not any(s & bumi_only for s in sets)
        open_f2 = set(CourseRequirement.objects.filter(course_id__in=f2, req_bumiputera=False)
                      .values_list('course_id', flat=True))
        assert set().union(*f2_gain) == open_f2 and len(open_f2) == 4

    def _bumi_twins(self, students=GOLDEN_STUDENTS):
        twins = []
        for student in students:
            twin = copy.copy(student)
            twin.bumiputera = True
            twins.append(twin)
        return twins

    def test_the_bumi_baseline(self):
        sets = self._eligible_sets(self._bumi_twins())
        assert sum(len(s) for s in sets) == GOLDEN_BASELINE_BUMI, [len(s) for s in sets]
        original = self._original_ids()
        f2 = self._added_ids(_F2_FILE)
        assert [s & original for s in sets] == [s & original for s in self._eligible_sets(GOLDEN_STUDENTS)]
        lines = [f'{i}:{cid}' for i, s in enumerate(sets, 1) for cid in sorted(s - original - f2)]
        assert len(lines) == GOLDEN_BASELINE_BUMI_BEFORE_F2 - GOLDEN_BASELINE   # 2,259
        assert _digest(lines) == BUMI_GAIN_SHA256, "a Bumiputera twin's D1 / D2 / F1 gain changed"
        lines = [f'{i}:{cid}' for i, s in enumerate(sets, 1) for cid in sorted(s & f2)]
        assert len(lines) == GOLDEN_F2_BUMI_GAIN
        assert _digest(lines) == F2_BUMI_GAIN_SHA256, "a Bumiputera twin's F2 (MARA) gain changed"

    def test_a_foreign_student_who_says_bumiputera_still_meets_no_bumi_only_row(self):
        """A foreigner is never Bumi (owner): the API never sends it (`resolve_bumiputera`), and even if it
        did, every Bumi-only row is also citizens-only, so the engine refuses her anyway."""
        from apps.courses.models import CourseRequirement
        assert not CourseRequirement.objects.filter(req_bumiputera=True, req_malaysian=False).exists()
        foreign = [s for s in self._bumi_twins() if s.nationality != 'Warganegara']
        assert foreign
        bumi_only = set(CourseRequirement.objects.filter(req_bumiputera=True).values_list('course_id', flat=True))
        assert not any(s & bumi_only for s in self._eligible_sets(foreign))

    def _held_tvet_ids(self):
        return {cid for cid in self._original_ids() if cid.startswith(('IJTM-', 'IKBN-'))}

    def test_f1b_moved_only_the_held_tvet_rows(self):
        """Bumi F1b: over the original catalogue minus the 84 held TVET rows, every golden student's
        eligible set is exactly what it was before the fix."""
        held = self._held_tvet_ids()
        assert len(held) == 84
        sets = [s & (self._original_ids() - held) for s in self._eligible_sets(GOLDEN_STUDENTS)]
        assert sum(len(s) for s in sets) == ORIGINAL_NON_HELD_BASELINE
        lines = [f'{i}:{cid}' for i, s in enumerate(sets, 1) for cid in sorted(s)]
        assert _digest(lines) == ORIGINAL_NON_HELD_SETS_SHA256

    def test_reversing_f1b_gives_back_the_frozen_pre_f1b_picture(self):
        """The fix file's `old` values ARE the pre-F1b fixture: `--reverse --apply` restores the
        5,319 / digest every earlier sprint pinned, and the forward run returns to today's figures.
        Who moved (the 50 golden students, bumi False and True alike): the non-citizen (#5) loses 50
        held rows (req_malaysian), the two colour-blind students (#4, #41) lose 19 each
        (no_colorblind, any page that excludes colour blindness hides the course), and the OKU student
        #20 gains 62 (no_disability); nobody else moves. The frame is reloaded however the test ends."""
        from django.core.management import call_command
        from io import StringIO
        original = self._original_ids()
        after = [s & original for s in self._eligible_sets(GOLDEN_STUDENTS)]
        call_command('fix_held_tvet_flags', '--file', str(_F1B_FILE), '--reverse', '--apply', stdout=StringIO())
        try:
            load_requirements_df()
            before = [s & original for s in self._eligible_sets(GOLDEN_STUDENTS)]
            assert sum(len(s) for s in before) == PRE_F1B_BASELINE
            assert _digest([f'{i}:{cid}' for i, s in enumerate(before, 1) for cid in sorted(s)]) == PRE_F1B_SETS_SHA256
            moved = {i: (len(b - a), len(a - b)) for i, (b, a) in enumerate(zip(before, after), 1) if a != b}
            assert moved == {4: (19, 0), 5: (50, 0), 20: (0, 62), 41: (19, 0)}
            listed = {c['course_id'] for c in json.loads(_F1B_FILE.read_text(encoding='utf-8'))['courses']}
            assert all(cid in listed for b, a in zip(before, after) for cid in b ^ a)
        finally:
            call_command('fix_held_tvet_flags', '--file', str(_F1B_FILE), '--apply', stdout=StringIO())
            load_requirements_df()
        assert [s & original for s in self._eligible_sets(GOLDEN_STUDENTS)] == after

    def test_the_f1b_remarks_change_no_eligibility(self):
        """The remark is text (owner): blanking every remark F1b wrote moves no golden student, Bumi or not."""
        from apps.courses.models import CourseRequirement
        fix = json.loads(_F1B_FILE.read_text(encoding='utf-8'))
        listed = [c['course_id'] for c in fix['courses']]
        assert CourseRequirement.objects.filter(course_id__in=listed).exclude(remarks='').count() == 63
        twins = [copy.copy(s) for s in GOLDEN_STUDENTS]
        for twin in twins:
            twin.bumiputera = True
        with_remarks = self._eligible_sets(GOLDEN_STUDENTS + twins)
        CourseRequirement.objects.filter(course_id__in=listed).update(remarks='')
        try:
            load_requirements_df()
            assert self._eligible_sets(GOLDEN_STUDENTS + twins) == with_remarks
        finally:
            for course in fix['courses']:
                CourseRequirement.objects.filter(course_id=course['course_id']).update(remarks=course['new']['remarks'])
            load_requirements_df()
