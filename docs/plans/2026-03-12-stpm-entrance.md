# STPM Entrance — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow STPM (Form 6) graduates to check which degree programmes they qualify for, based on their STPM grades, CGPA, MUET band, and SPM prerequisites.

**Architecture:** New user flow parallel to the existing SPM flow. STPM students enter their STPM grades + MUET band + SPM grades → new STPM eligibility engine checks against ~1,680 degree programmes loaded from CSV into new Django models → results ranked and displayed on the existing dashboard. The current SPM flow is untouched — exam type selection at onboarding routes to the correct engine.

**Tech Stack:** Django REST (models, management command, engine, views), Supabase PostgreSQL, Next.js 14 (onboarding pages, grade entry), existing quiz + ranking infrastructure.

---

## Data Overview

- **Source CSVs:** `stpm_science_requirements_parsed.csv` (1,003 rows), `stpm_arts_requirements_parsed.csv` (677 rows)
- **Total:** ~1,680 degree programmes across ~20 public universities
- **Key columns:** `program_id`, `program_name`, `university`, `stream` (science/arts/both), `min_cgpa`, `stpm_min_subjects`, `stpm_min_grade`, individual STPM subject requirements (`stpm_req_pa`, `stpm_req_math_t`, etc.), `stpm_subject_group` (JSON), SPM prerequisites (`spm_credit_bm`, `spm_pass_sejarah`, etc.), `spm_subject_group` (JSON), `min_muet_band`, `req_interview`, `no_colorblind`, `req_medical_fitness`, `req_malaysian`, `req_bumiputera`
- **STPM subjects:** 20 subjects (PA compulsory + 19 electives), grades A+ to G
- **CGPA:** Calculated from STPM grades (4.0 scale: A=4.0, A-=3.67, B+=3.33, B=3.0, C+=2.67, C=2.33, C-=2.0, D=1.67, E=1.0, F=0)
- **MUET:** Malaysian University English Test, bands 1-6

## Sprint Breakdown

| Sprint | Deliverable | Tasks |
|--------|-------------|-------|
| Sprint 1 | Data models + CSV loader + golden master | Tasks 1-5 |
| Sprint 2 | STPM eligibility engine + API endpoint | Tasks 6-10 |
| Sprint 3 | Frontend onboarding + grade entry | Tasks 11-14 |
| Sprint 4 | Dashboard integration + ranking | Tasks 15-18 |
| Sprint 5 | Search/filter, course detail, polish | Tasks 19-22 |

---

## Sprint 1: Data Models + CSV Loader

### Task 1: StpmCourse and StpmRequirement models

**Files:**
- Modify: `halatuju_api/apps/courses/models.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_models.py`

**Step 1: Write the failing test**

```python
# test_stpm_models.py
import pytest
from apps.courses.models import StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmModels:
    def test_stpm_course_creation(self):
        course = StpmCourse.objects.create(
            program_id='UP6314001',
            program_name='BACELOR EKONOMI DENGAN KEPUJIAN',
            university='Universiti Putra Malaysia',
            stream='both',
        )
        assert course.program_id == 'UP6314001'
        assert str(course) == 'UP6314001: BACELOR EKONOMI DENGAN KEPUJIAN'

    def test_stpm_requirement_creation(self):
        course = StpmCourse.objects.create(
            program_id='UP6314001',
            program_name='BACELOR EKONOMI DENGAN KEPUJIAN',
            university='Universiti Putra Malaysia',
            stream='both',
        )
        req = StpmRequirement.objects.create(
            course=course,
            min_cgpa=2.0,
            stpm_min_subjects=2,
            stpm_min_grade='C',
            stpm_req_pa=True,
            min_muet_band=2,
            spm_credit_bm=True,
            spm_pass_sejarah=True,
            spm_credit_bi=True,
            spm_credit_math=True,
            spm_credit_addmath=True,
            req_malaysian=True,
        )
        assert req.min_cgpa == 2.0
        assert req.stpm_req_pa is True

    def test_stpm_requirement_subject_group_json(self):
        course = StpmCourse.objects.create(
            program_id='TEST001',
            program_name='Test Course',
            university='Test Uni',
            stream='science',
        )
        req = StpmRequirement.objects.create(
            course=course,
            min_cgpa=3.0,
            stpm_subject_group={
                "min_count": 2,
                "min_grade": "B+",
                "subjects": ["PHYSICS", "CHEMISTRY", "BIOLOGY"]
            },
        )
        assert req.stpm_subject_group['min_count'] == 2
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'StpmCourse'`

**Step 3: Write minimal implementation**

Add to `models.py` after `AdmissionOutcome`:

```python
class StpmCourse(models.Model):
    """
    STPM degree programme — a university course that STPM graduates can apply to.

    Source: stpm_science_requirements_parsed.csv + stpm_arts_requirements_parsed.csv
    (~1,680 programmes)
    """
    program_id = models.CharField(max_length=50, primary_key=True)
    program_name = models.CharField(max_length=500)
    university = models.CharField(max_length=255)
    stream = models.CharField(
        max_length=20,
        choices=[('science', 'Science'), ('arts', 'Arts'), ('both', 'Both')],
        default='both',
    )

    class Meta:
        db_table = 'stpm_courses'
        ordering = ['university', 'program_name']

    def __str__(self):
        return f"{self.program_id}: {self.program_name}"


class StpmRequirement(models.Model):
    """
    Eligibility requirements for STPM degree programmes.

    Maps directly to the parsed CSV columns.
    """
    course = models.OneToOneField(
        StpmCourse,
        on_delete=models.CASCADE,
        related_name='requirement',
        primary_key=True,
    )

    # CGPA threshold
    min_cgpa = models.FloatField(default=2.0)

    # Minimum STPM subjects with min grade
    stpm_min_subjects = models.IntegerField(default=2)
    stpm_min_grade = models.CharField(max_length=5, default='C')

    # Individual STPM subject requirements (True = must take this subject)
    stpm_req_pa = models.BooleanField(default=False)
    stpm_req_math_t = models.BooleanField(default=False)
    stpm_req_math_m = models.BooleanField(default=False)
    stpm_req_physics = models.BooleanField(default=False)
    stpm_req_chemistry = models.BooleanField(default=False)
    stpm_req_biology = models.BooleanField(default=False)
    stpm_req_economics = models.BooleanField(default=False)
    stpm_req_accounting = models.BooleanField(default=False)
    stpm_req_business = models.BooleanField(default=False)

    # STPM subject group requirement (JSON)
    stpm_subject_group = models.JSONField(
        null=True, blank=True,
        help_text='JSON: {"min_count": N, "min_grade": "X", "subjects": [...]}'
    )

    # SPM prerequisites
    spm_credit_bm = models.BooleanField(default=False)
    spm_pass_sejarah = models.BooleanField(default=False)
    spm_credit_bi = models.BooleanField(default=False)
    spm_pass_bi = models.BooleanField(default=False)
    spm_credit_math = models.BooleanField(default=False)
    spm_pass_math = models.BooleanField(default=False)
    spm_credit_addmath = models.BooleanField(default=False)
    spm_credit_science = models.BooleanField(default=False)
    spm_subject_group = models.JSONField(
        null=True, blank=True,
        help_text='JSON: {"min_count": N, "min_grade": "X", "subjects": [...]}'
    )

    # MUET requirement
    min_muet_band = models.IntegerField(default=1)

    # Demographic/physical requirements
    req_interview = models.BooleanField(default=False)
    no_colorblind = models.BooleanField(default=False)
    req_medical_fitness = models.BooleanField(default=False)
    req_malaysian = models.BooleanField(default=False)
    req_bumiputera = models.BooleanField(default=False)

    class Meta:
        db_table = 'stpm_requirements'
        indexes = [
            models.Index(fields=['min_cgpa']),
        ]

    def __str__(self):
        return f"STPM Requirements for {self.course_id}"
```

**Step 4: Generate and run migration**

Run:
```bash
cd halatuju_api
python manage.py makemigrations courses
python manage.py migrate
```

**Step 5: Run test to verify it passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add apps/courses/models.py apps/courses/migrations/ apps/courses/tests/test_stpm_models.py
git commit -m "feat: add StpmCourse and StpmRequirement models for ~1,680 degree programmes"
```

---

### Task 2: CSV loader management command

**Files:**
- Create: `halatuju_api/apps/courses/management/commands/load_stpm_data.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_data_loading.py`

**Step 1: Write the failing test**

```python
# test_stpm_data_loading.py
import pytest
from io import StringIO
from django.core.management import call_command
from apps.courses.models import StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmDataLoading:
    def test_load_creates_courses(self):
        """Loader should create StpmCourse and StpmRequirement records."""
        out = StringIO()
        call_command('load_stpm_data', stdout=out)
        assert StpmCourse.objects.count() > 0

    def test_load_creates_requirements(self):
        out = StringIO()
        call_command('load_stpm_data', stdout=out)
        assert StpmRequirement.objects.count() > 0
        # Every course should have a requirement
        assert StpmCourse.objects.count() == StpmRequirement.objects.count()

    def test_load_correct_count(self):
        """Should load ~1,680 programmes (science + arts)."""
        out = StringIO()
        call_command('load_stpm_data', stdout=out)
        count = StpmCourse.objects.count()
        assert 1600 < count < 1800, f"Expected ~1680, got {count}"

    def test_load_idempotent(self):
        """Running loader twice should not duplicate records."""
        out = StringIO()
        call_command('load_stpm_data', stdout=out)
        count1 = StpmCourse.objects.count()
        call_command('load_stpm_data', stdout=out)
        count2 = StpmCourse.objects.count()
        assert count1 == count2

    def test_load_parses_subject_group_json(self):
        """JSON subject group fields should be parsed correctly."""
        out = StringIO()
        call_command('load_stpm_data', stdout=out)
        # Find a course with subject group data
        req = StpmRequirement.objects.exclude(stpm_subject_group__isnull=True).first()
        assert req is not None
        assert 'min_count' in req.stpm_subject_group
        assert 'subjects' in req.stpm_subject_group

    def test_load_boolean_fields(self):
        """Boolean requirements should be correctly parsed from 0/1."""
        out = StringIO()
        call_command('load_stpm_data', stdout=out)
        # PA is required for most courses
        pa_required = StpmRequirement.objects.filter(stpm_req_pa=True).count()
        assert pa_required > 100, f"Expected many courses requiring PA, got {pa_required}"
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_data_loading.py -v`
Expected: FAIL — `Unknown command: 'load_stpm_data'`

**Step 3: Write the management command**

```python
# load_stpm_data.py
"""
Load STPM degree programme data from parsed CSVs into Django models.

Usage:
    python manage.py load_stpm_data
    python manage.py load_stpm_data --data-dir /path/to/csvs

Source CSVs:
    stpm_science_requirements_parsed.csv (1,003 rows)
    stpm_arts_requirements_parsed.csv (677 rows)
"""
import csv
import json
import os
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse, StpmRequirement


# Default data directory (where the parsed CSVs live)
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'stpm')


def parse_bool(val):
    """Parse 0/1 string to bool."""
    return str(val).strip() in ('1', 'True', 'true', 'yes')


def parse_float(val, default=0.0):
    """Parse float, returning default if empty or invalid."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_int(val, default=0):
    """Parse int, returning default if empty or invalid."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def parse_json(val):
    """Parse JSON string, returning None if empty or invalid."""
    if not val or str(val).strip() in ('', 'nan', 'None'):
        return None
    try:
        return json.loads(str(val))
    except (json.JSONDecodeError, ValueError):
        return None


class Command(BaseCommand):
    help = 'Load STPM degree programme data from parsed CSVs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            default=DEFAULT_DATA_DIR,
            help='Directory containing stpm_*_requirements_parsed.csv files',
        )

    def handle(self, *args, **options):
        data_dir = options['data_dir']
        files = [
            os.path.join(data_dir, 'stpm_science_requirements_parsed.csv'),
            os.path.join(data_dir, 'stpm_arts_requirements_parsed.csv'),
        ]

        total_created = 0
        total_updated = 0

        for filepath in files:
            if not os.path.exists(filepath):
                self.stderr.write(f"File not found: {filepath}")
                continue

            self.stdout.write(f"Loading {filepath}...")
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    program_id = row['program_id'].strip()
                    if not program_id:
                        continue

                    course, created = StpmCourse.objects.update_or_create(
                        program_id=program_id,
                        defaults={
                            'program_name': row.get('program_name', '').strip(),
                            'university': row.get('university', '').strip(),
                            'stream': row.get('stream', 'both').strip().lower(),
                        }
                    )

                    StpmRequirement.objects.update_or_create(
                        course=course,
                        defaults={
                            'min_cgpa': parse_float(row.get('min_cgpa'), 2.0),
                            'stpm_min_subjects': parse_int(row.get('stpm_min_subjects'), 2),
                            'stpm_min_grade': row.get('stpm_min_grade', 'C').strip() or 'C',
                            'stpm_req_pa': parse_bool(row.get('stpm_req_pa')),
                            'stpm_req_math_t': parse_bool(row.get('stpm_req_math_t')),
                            'stpm_req_math_m': parse_bool(row.get('stpm_req_math_m')),
                            'stpm_req_physics': parse_bool(row.get('stpm_req_physics')),
                            'stpm_req_chemistry': parse_bool(row.get('stpm_req_chemistry')),
                            'stpm_req_biology': parse_bool(row.get('stpm_req_biology')),
                            'stpm_req_economics': parse_bool(row.get('stpm_req_economics')),
                            'stpm_req_accounting': parse_bool(row.get('stpm_req_accounting')),
                            'stpm_req_business': parse_bool(row.get('stpm_req_business')),
                            'stpm_subject_group': parse_json(row.get('stpm_subject_group')),
                            'spm_credit_bm': parse_bool(row.get('spm_credit_bm')),
                            'spm_pass_sejarah': parse_bool(row.get('spm_pass_sejarah')),
                            'spm_credit_bi': parse_bool(row.get('spm_credit_bi')),
                            'spm_pass_bi': parse_bool(row.get('spm_pass_bi')),
                            'spm_credit_math': parse_bool(row.get('spm_credit_math')),
                            'spm_pass_math': parse_bool(row.get('spm_pass_math')),
                            'spm_credit_addmath': parse_bool(row.get('spm_credit_addmath')),
                            'spm_credit_science': parse_bool(row.get('spm_credit_science')),
                            'spm_subject_group': parse_json(row.get('spm_subject_group')),
                            'min_muet_band': parse_int(row.get('min_muet_band'), 1),
                            'req_interview': parse_bool(row.get('req_interview')),
                            'no_colorblind': parse_bool(row.get('no_colorblind')),
                            'req_medical_fitness': parse_bool(row.get('req_medical_fitness')),
                            'req_malaysian': parse_bool(row.get('req_malaysian')),
                            'req_bumiputera': parse_bool(row.get('req_bumiputera')),
                        }
                    )

                    if created:
                        total_created += 1
                    else:
                        total_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done: {total_created} created, {total_updated} updated. "
            f"Total: {StpmCourse.objects.count()} programmes."
        ))
```

**Step 4: Copy CSVs to project data directory**

```bash
mkdir -p halatuju_api/data/stpm
cp "C:\Users\tamil\Python\Archived\Random\data\stpm_science_requirements_parsed.csv" halatuju_api/data/stpm/
cp "C:\Users\tamil\Python\Archived\Random\data\stpm_arts_requirements_parsed.csv" halatuju_api/data/stpm/
```

**Step 5: Run test to verify it passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_data_loading.py -v`
Expected: PASS (6 tests)

**Step 6: Commit**

```bash
git add apps/courses/management/commands/load_stpm_data.py apps/courses/tests/test_stpm_data_loading.py data/stpm/
git commit -m "feat: add STPM data loader — 1,680 degree programmes from parsed CSVs"
```

---

### Task 3: Supabase migration — create tables + load data

**Files:**
- Migration already generated in Task 1
- Run: `load_stpm_data` management command against Supabase

**Step 1: Apply migration to Supabase**

Via MCP `execute_sql` or Django migrate against production DB.

**Step 2: Load data**

```bash
cd halatuju_api
DATABASE_URL=$SUPABASE_DATABASE_URL python manage.py load_stpm_data
```

**Step 3: Enable RLS on new tables**

Via Supabase MCP:
```sql
ALTER TABLE stpm_courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE stpm_requirements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read stpm_courses" ON stpm_courses FOR SELECT USING (true);
CREATE POLICY "Public read stpm_requirements" ON stpm_requirements FOR SELECT USING (true);
```

**Step 4: Run Security Advisor**

Verify 0 errors via Supabase Dashboard or MCP `get_advisors`.

**Step 5: Commit**

```bash
git commit -m "chore: document Supabase STPM table setup and RLS policies"
```

---

### Task 4: STPM golden master baseline

**Files:**
- Create: `halatuju_api/apps/courses/tests/test_stpm_golden_master.py`
- Reference: `halatuju_api/data/stpm/` CSVs

**Step 1: Write the golden master test**

```python
# test_stpm_golden_master.py
"""
STPM Golden Master Test

Baseline: established on first run (recorded in this file).
Purpose: detect any unintentional changes to STPM eligibility logic.
"""
import pytest
from apps.courses.models import StpmCourse, StpmRequirement
from apps.courses.stpm_engine import check_stpm_eligibility


# 10 representative STPM student profiles
STPM_TEST_STUDENTS = [
    {
        'id': 'stpm_strong_science',
        'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'A'},
        'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+', 'addmath': 'A', 'sci': 'A'},
        'cgpa': 3.89,
        'muet_band': 4,
        'gender': 'Lelaki',
        'nationality': 'Warganegara',
        'colorblind': 'Tidak',
    },
    {
        'id': 'stpm_moderate_arts',
        'stpm_grades': {'PA': 'B+', 'ECONOMICS': 'B', 'ACCOUNTING': 'B+', 'BUSINESS': 'B'},
        'spm_grades': {'bm': 'B+', 'eng': 'B', 'hist': 'B', 'math': 'B+', 'addmath': 'C', 'sci': 'B'},
        'cgpa': 3.17,
        'muet_band': 3,
        'gender': 'Perempuan',
        'nationality': 'Warganegara',
        'colorblind': 'Tidak',
    },
    {
        'id': 'stpm_minimum',
        'stpm_grades': {'PA': 'C', 'MATH_T': 'C', 'PHYSICS': 'C'},
        'spm_grades': {'bm': 'C', 'eng': 'D', 'hist': 'D', 'math': 'C', 'sci': 'C'},
        'cgpa': 2.0,
        'muet_band': 2,
        'gender': 'Lelaki',
        'nationality': 'Warganegara',
        'colorblind': 'Tidak',
    },
    # ... (7 more profiles covering edge cases: low MUET, colorblind, non-citizen, etc.)
]

# Will be set on first run
STPM_GOLDEN_BASELINE = None  # Replace with actual number after first run


@pytest.mark.django_db
class TestStpmGoldenMaster:
    @pytest.fixture(autouse=True)
    def load_data(self):
        """Load STPM data for all tests."""
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())

    def test_golden_master(self):
        """Total eligible course count across all test students must match baseline."""
        total = 0
        for student in STPM_TEST_STUDENTS:
            results = check_stpm_eligibility(
                stpm_grades=student['stpm_grades'],
                spm_grades=student['spm_grades'],
                cgpa=student['cgpa'],
                muet_band=student['muet_band'],
                gender=student['gender'],
                nationality=student['nationality'],
                colorblind=student['colorblind'],
            )
            total += len(results)

        if STPM_GOLDEN_BASELINE is None:
            pytest.skip(f"First run — record baseline: {total}")
        else:
            assert total == STPM_GOLDEN_BASELINE, (
                f"Golden master mismatch: expected {STPM_GOLDEN_BASELINE}, got {total}"
            )
```

**Step 2: Run to establish baseline**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_golden_master.py -v`
Expected: SKIP with baseline number. Record it.

**Step 3: Update baseline constant and re-run**

Replace `STPM_GOLDEN_BASELINE = None` with the recorded number.

**Step 4: Commit**

```bash
git add apps/courses/tests/test_stpm_golden_master.py
git commit -m "test: add STPM golden master baseline"
```

---

### Task 5: Sprint 1 close

**Step 1: Run full test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```

Expected: All existing 250 tests still pass + new STPM tests pass.

**Step 2: Update CHANGELOG.md**

**Step 3: Commit and push**

---

## Sprint 2: STPM Eligibility Engine + API

### Task 6: STPM CGPA calculator

**Files:**
- Create: `halatuju_api/apps/courses/stpm_engine.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_engine.py`

**Step 1: Write failing tests for CGPA calculation**

```python
# test_stpm_engine.py
import pytest
from apps.courses.stpm_engine import calculate_stpm_cgpa


class TestStpmCgpa:
    def test_perfect_cgpa(self):
        grades = {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'}
        assert calculate_stpm_cgpa(grades) == 4.0

    def test_mixed_grades(self):
        grades = {'PA': 'B+', 'ECONOMICS': 'B', 'ACCOUNTING': 'C+'}
        cgpa = calculate_stpm_cgpa(grades)
        assert 2.5 < cgpa < 3.5

    def test_minimum_pass(self):
        grades = {'PA': 'C-', 'MATH_T': 'C-', 'PHYSICS': 'C-'}
        cgpa = calculate_stpm_cgpa(grades)
        assert cgpa == 2.0

    def test_with_fail(self):
        grades = {'PA': 'A', 'MATH_T': 'F', 'PHYSICS': 'B'}
        cgpa = calculate_stpm_cgpa(grades)
        # F = 0 should drag down average
        assert cgpa < 3.0

    def test_empty_grades(self):
        assert calculate_stpm_cgpa({}) == 0.0
```

**Step 2: Run to verify fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py::TestStpmCgpa -v`
Expected: FAIL — `ImportError`

**Step 3: Implement CGPA calculator**

```python
# stpm_engine.py
"""
STPM eligibility engine — checks STPM student grades against degree programme requirements.

Input: STPM grades, SPM grades, CGPA, MUET band, demographics.
Output: List of eligible programmes.
"""

# STPM CGPA scale (official MQA scale)
STPM_CGPA_POINTS = {
    'A': 4.00, 'A-': 3.67,
    'B+': 3.33, 'B': 3.00, 'B-': 2.67,
    'C+': 2.33, 'C': 2.00, 'C-': 2.00,
    'D': 1.67, 'E': 1.00,
    'F': 0.00, 'G': 0.00,
}

# Grade hierarchy for "meets minimum grade" checks
STPM_GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'E', 'F', 'G']


def calculate_stpm_cgpa(grades):
    """Calculate CGPA from STPM grades dict.

    Args:
        grades: Dict mapping STPM subject codes to grade strings.
                e.g. {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'A-'}

    Returns:
        Float CGPA (0.0-4.0), rounded to 2 decimal places.
    """
    if not grades:
        return 0.0
    total_points = 0.0
    count = 0
    for grade in grades.values():
        pts = STPM_CGPA_POINTS.get(grade)
        if pts is not None:
            total_points += pts
            count += 1
    if count == 0:
        return 0.0
    return round(total_points / count, 2)


def meets_stpm_grade(grade, min_grade):
    """Check if a grade meets or exceeds the minimum threshold."""
    try:
        grade_idx = STPM_GRADE_ORDER.index(grade)
        min_idx = STPM_GRADE_ORDER.index(min_grade)
    except ValueError:
        return False
    return grade_idx <= min_idx
```

**Step 4: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py::TestStpmCgpa -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/courses/stpm_engine.py apps/courses/tests/test_stpm_engine.py
git commit -m "feat: add STPM CGPA calculator"
```

---

### Task 7: STPM eligibility checker — core logic

**Files:**
- Modify: `halatuju_api/apps/courses/stpm_engine.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_engine.py`

**Step 1: Write failing tests for eligibility checks**

```python
class TestStpmEligibility:
    @pytest.fixture(autouse=True)
    def load_data(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())

    def test_strong_science_student_gets_results(self):
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A-', 'CHEMISTRY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+', 'addmath': 'A', 'sci': 'A'},
            cgpa=3.89,
            muet_band=4,
        )
        assert len(results) > 0

    def test_cgpa_filter(self):
        """Student with low CGPA should get fewer results."""
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
        """Courses requiring MUET band 4 should reject band 2 students."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=2,
        )
        for r in results:
            assert r['min_muet_band'] <= 2

    def test_subject_requirement_check(self):
        """Courses requiring Physics should not appear for arts-only students."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'ECONOMICS': 'A', 'ACCOUNTING': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4,
        )
        for r in results:
            assert not r.get('stpm_req_physics'), f"{r['program_name']} requires Physics"

    def test_result_shape(self):
        """Each result should have expected fields."""
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4,
        )
        if results:
            r = results[0]
            assert 'program_id' in r
            assert 'program_name' in r
            assert 'university' in r
            assert 'min_cgpa' in r

    def test_colorblind_filter(self):
        """Colorblind students should not see no_colorblind courses."""
        all_results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'CHEMISTRY': 'A', 'BIOLOGY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4, colorblind='Tidak',
        )
        cb_results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'CHEMISTRY': 'A', 'BIOLOGY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            cgpa=3.8, muet_band=4, colorblind='Ya',
        )
        assert len(all_results) >= len(cb_results)
```

**Step 2: Implement `check_stpm_eligibility`**

Add to `stpm_engine.py`:

```python
from apps.courses.models import StpmCourse, StpmRequirement

# SPM grade mapping (frontend keys → engine keys already in serializers.py)
SPM_CREDIT_GRADES = {'A+', 'A', 'A-', 'B+', 'B', 'C+', 'C'}
SPM_PASS_GRADES = SPM_CREDIT_GRADES | {'D', 'E'}


def check_spm_prerequisites(req, spm_grades):
    """Check SPM prerequisites for an STPM degree programme."""
    if req.spm_credit_bm and spm_grades.get('bm') not in SPM_CREDIT_GRADES:
        return False
    if req.spm_pass_sejarah and spm_grades.get('hist') not in SPM_PASS_GRADES:
        return False
    if req.spm_credit_bi and spm_grades.get('eng') not in SPM_CREDIT_GRADES:
        return False
    if req.spm_pass_bi and spm_grades.get('eng') not in SPM_PASS_GRADES:
        return False
    if req.spm_credit_math and spm_grades.get('math') not in SPM_CREDIT_GRADES:
        return False
    if req.spm_pass_math and spm_grades.get('math') not in SPM_PASS_GRADES:
        return False
    if req.spm_credit_addmath and spm_grades.get('addmath') not in SPM_CREDIT_GRADES:
        return False
    if req.spm_credit_science and spm_grades.get('sci') not in SPM_CREDIT_GRADES:
        return False

    # SPM subject group check
    if req.spm_subject_group:
        sg = req.spm_subject_group
        min_count = sg.get('min_count', 0)
        min_grade = sg.get('min_grade', 'E')
        subjects = sg.get('subjects', [])
        # Map CSV subject codes to engine keys
        SPM_CODE_MAP = {
            'MATH': 'math', 'ADD_MATH': 'addmath', 'BM': 'bm', 'BI': 'eng',
            'SCIENCE': 'sci', 'PHYSICS_SPM': 'phy', 'CHEMISTRY_SPM': 'chem',
            'BIOLOGY_SPM': 'bio', 'ACCOUNTING_SPM': 'poa', 'ECONOMICS_SPM': 'ekonomi',
            'COMMERCE': 'business', 'GEOGRAPHY_SPM': 'geo',
        }
        count = 0
        for subj_code in subjects:
            engine_key = SPM_CODE_MAP.get(subj_code, subj_code.lower())
            grade = spm_grades.get(engine_key)
            if grade and meets_spm_grade(grade, min_grade):
                count += 1
        if count < min_count:
            return False

    return True


def meets_spm_grade(grade, min_grade):
    """Check if SPM grade meets minimum (credit = C or better, pass = E or better)."""
    spm_order = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']
    try:
        return spm_order.index(grade) <= spm_order.index(min_grade)
    except ValueError:
        return False


def check_stpm_subject_requirements(req, stpm_grades):
    """Check individual STPM subject requirements."""
    subject_checks = {
        'stpm_req_pa': 'PA',
        'stpm_req_math_t': 'MATH_T',
        'stpm_req_math_m': 'MATH_M',
        'stpm_req_physics': 'PHYSICS',
        'stpm_req_chemistry': 'CHEMISTRY',
        'stpm_req_biology': 'BIOLOGY',
        'stpm_req_economics': 'ECONOMICS',
        'stpm_req_accounting': 'ACCOUNTING',
        'stpm_req_business': 'BUSINESS',
    }
    for field, subj_code in subject_checks.items():
        if getattr(req, field, False) and subj_code not in stpm_grades:
            return False
    return True


def check_stpm_subject_group(req, stpm_grades):
    """Check STPM subject group requirement (JSON field)."""
    sg = req.stpm_subject_group
    if not sg:
        return True
    min_count = sg.get('min_count', 0)
    min_grade = sg.get('min_grade', 'E')
    subjects = sg.get('subjects', [])
    count = 0
    for subj_code in subjects:
        grade = stpm_grades.get(subj_code)
        if grade and meets_stpm_grade(grade, min_grade):
            count += 1
    return count >= min_count


def check_stpm_min_subjects(req, stpm_grades):
    """Check minimum number of STPM subjects with minimum grade."""
    min_grade = req.stpm_min_grade or 'C'
    min_count = req.stpm_min_subjects or 2
    count = 0
    for grade in stpm_grades.values():
        if meets_stpm_grade(grade, min_grade):
            count += 1
    return count >= min_count


def check_stpm_eligibility(stpm_grades, spm_grades, cgpa, muet_band,
                            gender='', nationality='Warganegara',
                            colorblind='Tidak', disability='Tidak'):
    """
    Check which STPM degree programmes a student qualifies for.

    Args:
        stpm_grades: Dict mapping STPM subject codes to grades.
                     e.g. {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'A-'}
        spm_grades: Dict mapping SPM engine keys to grades.
                    e.g. {'bm': 'A', 'eng': 'B+', 'math': 'A'}
        cgpa: STPM CGPA (float, 0.0-4.0)
        muet_band: MUET band (int, 1-6)
        gender: 'Lelaki' or 'Perempuan'
        nationality: 'Warganegara' or 'Bukan Warganegara'
        colorblind: 'Ya' or 'Tidak'
        disability: 'Ya' or 'Tidak'

    Returns:
        List of dicts, each representing an eligible programme.
    """
    eligible = []

    requirements = StpmRequirement.objects.select_related('course').all()

    for req in requirements:
        # 1. CGPA check
        if cgpa < req.min_cgpa:
            continue

        # 2. MUET check
        if muet_band < req.min_muet_band:
            continue

        # 3. Demographic checks
        if req.req_malaysian and nationality != 'Warganegara':
            continue
        if req.no_colorblind and colorblind == 'Ya':
            continue

        # 4. STPM subject requirements
        if not check_stpm_subject_requirements(req, stpm_grades):
            continue

        # 5. STPM minimum subjects with min grade
        if not check_stpm_min_subjects(req, stpm_grades):
            continue

        # 6. STPM subject group
        if not check_stpm_subject_group(req, stpm_grades):
            continue

        # 7. SPM prerequisites
        if not check_spm_prerequisites(req, spm_grades):
            continue

        course = req.course
        eligible.append({
            'program_id': course.program_id,
            'program_name': course.program_name,
            'university': course.university,
            'stream': course.stream,
            'min_cgpa': req.min_cgpa,
            'min_muet_band': req.min_muet_band,
            'stpm_req_physics': req.stpm_req_physics,
            'req_interview': req.req_interview,
            'no_colorblind': req.no_colorblind,
        })

    return eligible
```

**Step 3: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add apps/courses/stpm_engine.py apps/courses/tests/test_stpm_engine.py
git commit -m "feat: add STPM eligibility engine — CGPA, MUET, subject, SPM checks"
```

---

### Task 8: STPM eligibility API endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_api.py`

**Step 1: Write failing API tests**

```python
# test_stpm_api.py
import pytest
from django.test import TestCase
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestStpmEligibilityAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())
        self.client = APIClient()

    def test_endpoint_exists(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'cgpa': 3.8,
            'muet_band': 4,
        }, format='json')
        assert resp.status_code == 200

    def test_returns_eligible_programmes(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A+'},
            'cgpa': 3.89,
            'muet_band': 4,
        }, format='json')
        data = resp.json()
        assert 'eligible_programmes' in data
        assert len(data['eligible_programmes']) > 0

    def test_missing_required_fields(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {}, format='json')
        assert resp.status_code == 400

    def test_returns_count(self):
        resp = self.client.post('/api/v1/stpm/eligibility/check/', {
            'stpm_grades': {'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A'},
            'spm_grades': {'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
            'cgpa': 3.8,
            'muet_band': 4,
        }, format='json')
        data = resp.json()
        assert 'total_eligible' in data
        assert data['total_eligible'] == len(data['eligible_programmes'])
```

**Step 2: Implement the view and URL**

Add to `views.py`:
```python
from .stpm_engine import check_stpm_eligibility

class StpmEligibilityCheckView(APIView):
    """POST /api/v1/stpm/eligibility/check/ — check STPM degree eligibility."""

    def post(self, request):
        stpm_grades = request.data.get('stpm_grades')
        spm_grades = request.data.get('spm_grades', {})
        cgpa = request.data.get('cgpa')
        muet_band = request.data.get('muet_band')

        if not stpm_grades or cgpa is None or muet_band is None:
            return Response(
                {'error': 'stpm_grades, cgpa, and muet_band are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = check_stpm_eligibility(
            stpm_grades=stpm_grades,
            spm_grades=spm_grades,
            cgpa=float(cgpa),
            muet_band=int(muet_band),
            gender=request.data.get('gender', ''),
            nationality=request.data.get('nationality', 'Warganegara'),
            colorblind=request.data.get('colorblind', 'Tidak'),
        )

        return Response({
            'eligible_programmes': results,
            'total_eligible': len(results),
        })
```

Add to `urls.py`:
```python
path('stpm/eligibility/check/', views.StpmEligibilityCheckView.as_view(), name='stpm-eligibility-check'),
```

**Step 3: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_api.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_stpm_api.py
git commit -m "feat: add POST /api/v1/stpm/eligibility/check/ endpoint"
```

---

### Task 9: STPM programme search/browse endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_api.py` (add tests)

**Step 1: Write failing tests**

```python
    def test_search_endpoint(self):
        resp = self.client.get('/api/v1/stpm/programmes/search/', {'q': 'Ekonomi'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'results' in data

    def test_search_by_university(self):
        resp = self.client.get('/api/v1/stpm/programmes/search/', {'university': 'Universiti Putra Malaysia'})
        assert resp.status_code == 200
        for r in resp.json()['results']:
            assert 'Universiti Putra Malaysia' in r['university']

    def test_search_by_stream(self):
        resp = self.client.get('/api/v1/stpm/programmes/search/', {'stream': 'science'})
        assert resp.status_code == 200
        for r in resp.json()['results']:
            assert r['stream'] in ('science', 'both')

    def test_search_pagination(self):
        resp = self.client.get('/api/v1/stpm/programmes/search/', {'page': 1, 'page_size': 10})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['results']) <= 10
        assert 'total' in data
```

**Step 2: Implement search view**

```python
class StpmProgrammeSearchView(APIView):
    """GET /api/v1/stpm/programmes/search/ — search/browse STPM degree programmes."""

    def get(self, request):
        qs = StpmCourse.objects.all()

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(program_name__icontains=q)

        university = request.query_params.get('university', '').strip()
        if university:
            qs = qs.filter(university__icontains=university)

        stream = request.query_params.get('stream', '').strip()
        if stream:
            qs = qs.filter(Q(stream=stream) | Q(stream='both'))

        total = qs.count()
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        offset = (page - 1) * page_size

        results = []
        for course in qs[offset:offset + page_size]:
            results.append({
                'program_id': course.program_id,
                'program_name': course.program_name,
                'university': course.university,
                'stream': course.stream,
            })

        return Response({
            'results': results,
            'total': total,
            'page': page,
            'page_size': page_size,
        })
```

**Step 3: Run tests, commit**

---

### Task 10: Sprint 2 close

Run full test suite, update CHANGELOG, commit and push.

---

## Sprint 3: Frontend — Onboarding + Grade Entry

### Task 11: Exam type selection page update

**Files:**
- Modify: `halatuju-web/src/app/onboarding/exam-type/page.tsx`
- Modify: `halatuju-web/src/messages/en.json`, `ms.json`, `ta.json`

Currently the exam-type page has SPM as the only option. Add STPM as a second option.

**Step 1: Add i18n keys**

```json
{
  "onboarding": {
    "examType": {
      "stpm": "STPM (Form 6)",
      "stpmDescription": "I have completed STPM and want to find degree programmes"
    }
  }
}
```

**Step 2: Update exam-type page**

Add STPM card alongside SPM. When selected, route to `/onboarding/stpm-grades` instead of `/onboarding/grades`.

**Step 3: Test manually**

Navigate to onboarding, verify both options appear, STPM routes correctly.

**Step 4: Commit**

---

### Task 12: STPM grade entry page

**Files:**
- Create: `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`
- Modify: `halatuju-web/src/lib/subjects.ts` (add STPM subject list)
- Modify: `halatuju-web/src/messages/en.json`, `ms.json`, `ta.json`

**Step 1: Add STPM subject definitions**

In `subjects.ts`, add:
```typescript
export const STPM_SUBJECTS = [
  { id: 'PA', name: 'Pengajian Am', required: true },
  { id: 'MATH_T', name: 'Matematik T', stream: 'science' },
  { id: 'MATH_M', name: 'Matematik M', stream: 'arts' },
  { id: 'PHYSICS', name: 'Fizik', stream: 'science' },
  { id: 'CHEMISTRY', name: 'Kimia', stream: 'science' },
  { id: 'BIOLOGY', name: 'Biologi', stream: 'science' },
  { id: 'ECONOMICS', name: 'Ekonomi', stream: 'arts' },
  { id: 'ACCOUNTING', name: 'Perakaunan', stream: 'arts' },
  { id: 'BUSINESS', name: 'Pengajian Perniagaan', stream: 'arts' },
  // ... all 20 subjects from stpm_subject_codes.json
];

export const STPM_GRADES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'E', 'F'];

export const MUET_BANDS = [1, 2, 3, 4, 5, 6];
```

**Step 2: Build STPM grade entry page**

Page layout:
1. Select STPM subjects taken (PA is mandatory, pick 3 more)
2. Enter grade for each selected subject
3. Enter MUET band (dropdown 1-6)
4. Enter SPM grades for core subjects (BM, BI, Sejarah, Math) — these are prerequisites
5. CGPA auto-calculated from entered STPM grades
6. "Check Eligibility" button

**Step 3: Add i18n strings**

**Step 4: Test manually, commit**

---

### Task 13: STPM profile sync to backend

**Files:**
- Modify: `halatuju-web/src/lib/api.ts`
- Modify: `halatuju_api/apps/courses/models.py` (add `exam_type` to StudentProfile)
- Modify: `halatuju_api/apps/courses/views.py` (profile sync handles STPM data)

**Step 1: Add `exam_type` field to StudentProfile**

```python
# In StudentProfile model
exam_type = models.CharField(
    max_length=10,
    choices=[('spm', 'SPM'), ('stpm', 'STPM')],
    default='spm',
)
stpm_grades = models.JSONField(
    default=dict, blank=True,
    help_text="STPM grades: {'PA': 'A', 'MATH_T': 'B+', ...}"
)
stpm_cgpa = models.FloatField(null=True, blank=True)
muet_band = models.IntegerField(null=True, blank=True)
```

**Step 2: Update profile sync view**

Accept `exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band` in profile sync.

**Step 3: Update frontend API client**

```typescript
// In api.ts
export async function checkStpmEligibility(data: StpmEligibilityRequest) {
  return apiPost('/api/v1/stpm/eligibility/check/', data);
}
```

**Step 4: Write tests, commit**

---

### Task 14: Sprint 3 close

Run full test suite, update CHANGELOG, commit and push.

---

## Sprint 4: Dashboard Integration + Ranking

### Task 15: STPM results on dashboard

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx`
- Modify: `halatuju-web/src/components/CourseCard.tsx`

**Step 1: Route dashboard by exam type**

If `profile.exam_type === 'stpm'`:
- Call STPM eligibility endpoint instead of SPM
- Display degree programmes instead of diploma/sijil courses
- Show university name, CGPA requirement, MUET requirement

**Step 2: Adapt CourseCard for STPM programmes**

- Programme name (not course name)
- University (not institution)
- Min CGPA badge
- MUET band badge
- Interview required badge

**Step 3: Test manually, commit**

---

### Task 16: STPM ranking engine

**Files:**
- Create or modify: `halatuju_api/apps/courses/stpm_ranking.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_ranking.py`

**Step 1: Write ranking tests**

Ranking for STPM should consider:
- CGPA margin (how far above min_cgpa)
- University prestige (UA type)
- Stream match
- Quiz signals (reuse existing quiz infrastructure)

**Step 2: Implement ranking**

Simple ranking based on:
1. CGPA margin (student CGPA - min CGPA) → higher margin = safer bet
2. University prestige bonus
3. Quiz field interest match (reuse FIELD_LABEL_MAP concept)

**Step 3: Run tests, commit**

---

### Task 17: STPM ranking API endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`

Add `POST /api/v1/stpm/ranking/` endpoint that takes STPM eligibility results + student signals → returns ranked programmes.

**Step 1: Write tests**
**Step 2: Implement view**
**Step 3: Run tests, commit**

---

### Task 18: Sprint 4 close

Run full test suite, update CHANGELOG, commit and push.

---

## Sprint 5: Search, Course Detail, Polish

### Task 19: STPM programme detail page

**Files:**
- Create: `halatuju-web/src/app/stpm/[id]/page.tsx`

Show:
- Programme name
- University
- All STPM requirements (subjects, grades, CGPA)
- SPM prerequisites
- MUET band
- Interview/colorblind/medical flags
- Link to university website (if available)

---

### Task 20: STPM search with filters

**Files:**
- Modify: `halatuju-web/src/app/search/page.tsx`

Add STPM tab or route to search page:
- Text search
- Filter by university
- Filter by stream (science/arts)
- Filter by min CGPA range
- Pagination

---

### Task 21: i18n completion for STPM

**Files:**
- Modify: `halatuju-web/src/messages/en.json`, `ms.json`, `ta.json`

Add all STPM-specific strings in all 3 languages. Run `scripts/check-i18n.js` to verify parity.

---

### Task 22: Sprint 5 close — full integration test + release

**Step 1: Full test suite**

```bash
# Backend
cd halatuju_api && python -m pytest apps/courses/tests/ -v

# Golden masters
python -m pytest apps/courses/tests/test_golden_master.py -v  # SPM: 8283
python -m pytest apps/courses/tests/test_stpm_golden_master.py -v  # STPM: TBD
```

**Step 2: Manual E2E test**

1. Fresh user → select STPM → enter grades → see dashboard
2. Verify programme count is reasonable
3. Verify search works
4. Verify programme detail shows correct requirements

**Step 3: Deploy to Cloud Run**

**Step 4: Update CHANGELOG, tag release, push**

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| CSV data quality (parse_confidence < 1.0) | Log low-confidence rows, manual review of edge cases |
| CGPA calculation differs from official MQA | Cross-check with 3 official university websites |
| Subject group JSON parsing errors | Validate all JSON on load, reject malformed rows |
| Performance: 1,680 programmes × N DB queries | Load into DataFrame at startup (same as SPM engine) |
| SPM flow regression | Existing 250 tests + golden master 8283 must pass unchanged |
| STPM subject code mismatch CSV↔frontend | Single source of truth in `stpm_subject_codes.json` |

## Dependencies

- Parsed CSV data files (already available at `Archived/Random/data/`)
- `stpm_subject_codes.json` (already available)
- Supabase project has capacity for 2 new tables (~1,680 rows each)
- No new external APIs or services needed

## Out of Scope

- STPM prediction ("will I pass STPM?") — this is post-STPM eligibility only
- Private university (IPTS) programmes — public universities only for now
- Matric → degree pathway (future feature)
- STPM student financial aid / scholarship matching
