# Pre-University Courses Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 6 pre-university courses (4 matric tracks + 2 STPM bidangs) as real `Course` + `CourseRequirement` rows with `merit_type` field for separate merit calculation formulas.

**Architecture:** Extend `CourseRequirement` with a `merit_type` CharField. Insert 6 courses + requirements via data migration. In `views.py`, branch merit calculation by `merit_type` — reusing formulas from `pathways.py`. Engine (`engine.py`) is untouched; eligibility checks use existing boolean fields + `complex_requirements` JSON.

**Tech Stack:** Django 5.x, PostgreSQL (Supabase), Pandas DataFrame, pytest

---

### Task 1: Add `merit_type` field and `matric`/`stpm` source_type choices

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:87-97` (source_type choices) and add `merit_type` field after line 103
- Create: `halatuju_api/apps/courses/migrations/0016_add_merit_type_and_preu_source_types.py` (auto-generated)

**Step 1: Add `merit_type` field and expand `source_type` choices in models.py**

In `halatuju_api/apps/courses/models.py`, update `CourseRequirement`:

```python
# source_type choices — add 'matric' and 'stpm' after 'pismp'
source_type = models.CharField(
    max_length=20,
    choices=[
        ('poly', 'Polytechnic'),
        ('kkom', 'Community College'),
        ('tvet', 'TVET/ILKBS/ILJTM'),
        ('ua', 'University/Asasi'),
        ('pismp', 'PISMP/Teacher Training'),
        ('matric', 'Matriculation'),
        ('stpm', 'STPM/Form 6'),
    ],
    default='poly'
)

# After merit_cutoff (line 103), add:
merit_type = models.CharField(
    max_length=20,
    choices=[
        ('standard', 'Standard SPM merit'),
        ('matric', 'Matriculation grade points'),
        ('stpm_mata_gred', 'STPM mata gred'),
    ],
    default='standard',
    help_text="Merit calculation formula to use"
)
```

**Step 2: Generate the migration**

Run: `cd halatuju_api && python manage.py makemigrations courses -n add_merit_type_and_preu_source_types`

Expected: `migrations/0016_add_merit_type_and_preu_source_types.py` created.

**Step 3: Verify migration applies locally**

Run: `cd halatuju_api && python manage.py migrate --run-syncdb`

Expected: Migration applies without errors.

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/0016_*.py
git commit -m "feat: add merit_type field and matric/stpm source_type choices"
```

---

### Task 2: Data migration — insert 6 courses + 6 requirements

**Files:**
- Create: `halatuju_api/apps/courses/migrations/0017_insert_preu_courses.py` (manual data migration)

**Step 1: Write the data migration**

Create `halatuju_api/apps/courses/migrations/0017_insert_preu_courses.py`:

```python
"""Insert 6 pre-university courses and their requirements."""
from django.db import migrations


def insert_preu_courses(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    CourseRequirement = apps.get_model('courses', 'CourseRequirement')

    courses_data = [
        {
            'course_id': 'matric-sains',
            'course': 'Matrikulasi — Sains',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Sains & Teknologi',
            'frontend_label': 'Sains & Teknologi',
        },
        {
            'course_id': 'matric-kejuruteraan',
            'course': 'Matrikulasi — Kejuruteraan',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Kejuruteraan',
            'frontend_label': 'Kejuruteraan',
        },
        {
            'course_id': 'matric-sains-komputer',
            'course': 'Matrikulasi — Sains Komputer',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Teknologi Maklumat',
            'frontend_label': 'Teknologi Maklumat',
        },
        {
            'course_id': 'matric-perakaunan',
            'course': 'Matrikulasi — Perakaunan',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Perakaunan & Kewangan',
            'frontend_label': 'Perakaunan & Kewangan',
        },
        {
            'course_id': 'stpm-sains',
            'course': 'Tingkatan 6 — Sains',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Sains & Teknologi',
            'frontend_label': 'Sains & Teknologi',
        },
        {
            'course_id': 'stpm-sains-sosial',
            'course': 'Tingkatan 6 — Sains Sosial',
            'level': 'Pra-U',
            'department': 'KPM',
            'field': 'Sains Sosial',
            'frontend_label': 'Sains Sosial',
        },
    ]

    requirements_data = [
        # Matric Sains
        {
            'course_id': 'matric-sains',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'B', 'subjects': ['math']},
                    {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                    {'count': 1, 'grade': 'C', 'subjects': ['chem']},
                    {'count': 1, 'grade': 'C', 'subjects': ['phy', 'bio']},
                ],
            },
            'min_credits': 5,
        },
        # Matric Kejuruteraan
        {
            'course_id': 'matric-kejuruteraan',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'B', 'subjects': ['math']},
                    {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                    {'count': 1, 'grade': 'C', 'subjects': ['phy']},
                ],
            },
            'min_credits': 5,
        },
        # Matric Sains Komputer
        {
            'course_id': 'matric-sains-komputer',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'C', 'subjects': ['math']},
                    {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                    {'count': 1, 'grade': 'C', 'subjects': ['comp_sci']},
                ],
            },
            'min_credits': 5,
        },
        # Matric Perakaunan
        {
            'course_id': 'matric-perakaunan',
            'source_type': 'matric',
            'merit_type': 'matric',
            'merit_cutoff': 94,
            'credit_bm': True,
            'pass_history': True,
            'complex_requirements': {
                'or_groups': [
                    {'count': 1, 'grade': 'C', 'subjects': ['math']},
                ],
            },
            'min_credits': 5,
        },
        # STPM Sains
        {
            'course_id': 'stpm-sains',
            'source_type': 'stpm',
            'merit_type': 'stpm_mata_gred',
            'merit_cutoff': 18,
            'credit_bm': True,
            'pass_history': True,
            'min_credits': 3,
        },
        # STPM Sains Sosial
        {
            'course_id': 'stpm-sains-sosial',
            'source_type': 'stpm',
            'merit_type': 'stpm_mata_gred',
            'merit_cutoff': 18,
            'credit_bm': True,
            'pass_history': True,
            'min_credits': 3,
        },
    ]

    for cd in courses_data:
        Course.objects.create(**cd)

    for rd in requirements_data:
        course_id = rd.pop('course_id')
        CourseRequirement.objects.create(course_id=course_id, **rd)


def remove_preu_courses(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    Course.objects.filter(course_id__in=[
        'matric-sains', 'matric-kejuruteraan', 'matric-sains-komputer',
        'matric-perakaunan', 'stpm-sains', 'stpm-sains-sosial',
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0016_add_merit_type_and_preu_source_types'),
    ]

    operations = [
        migrations.RunPython(insert_preu_courses, remove_preu_courses),
    ]
```

**Step 2: Run the data migration**

Run: `cd halatuju_api && python manage.py migrate`

Expected: Migration applies, 6 courses + 6 requirements created.

**Step 3: Verify data exists**

Run: `cd halatuju_api && python manage.py shell -c "from apps.courses.models import Course, CourseRequirement; print(Course.objects.filter(course_id__startswith='matric').count(), Course.objects.filter(course_id__startswith='stpm-s').count()); print(CourseRequirement.objects.filter(merit_type='matric').count(), CourseRequirement.objects.filter(merit_type='stpm_mata_gred').count())"`

Expected: `4 2` and `4 2`

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/migrations/0017_insert_preu_courses.py
git commit -m "feat: insert 6 pre-university courses via data migration"
```

---

### Task 3: Update `apps.py` to map pre-U courses in `course_pathway_map`

**Files:**
- Modify: `halatuju_api/apps/courses/apps.py:149-163` (non-TVET mapping block)

**Step 1: Update the pathway mapping logic**

In `halatuju_api/apps/courses/apps.py`, update the non-TVET block (around line 149) to handle `matric` and `stpm` source types:

```python
        # Non-TVET courses
        for req in CourseRequirement.objects.exclude(
            source_type='tvet'
        ).select_related('course').values(
            'course_id', 'source_type', 'course__level'
        ):
            cid = req['course_id']
            st = req['source_type']
            level = req['course__level'] or ''
            if st == 'ua':
                course_pathway_map[cid] = (
                    'asasi' if level.lower() == 'asasi' else 'university'
                )
            elif st in ('matric', 'stpm'):
                course_pathway_map[cid] = st
            else:
                course_pathway_map[cid] = st  # poly, kkom, pismp
```

**Step 2: Run tests to verify data loading**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_data_loading.py -v`

Expected: All data loading tests pass.

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/apps.py
git commit -m "feat: map matric/stpm source types in course_pathway_map"
```

---

### Task 4: Add matric/stpm merit calculation in `views.py`

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:288-297` (merit calculation) and `:349-355` (merit label)

**Step 1: Import pathways functions at top of views.py**

Add to the imports in `halatuju_api/apps/courses/views.py`:

```python
from .pathways import check_matric_track, check_stpm_bidang, MATRIC_GRADE_POINTS, STPM_MATA_GRED
```

**Step 2: Add merit branching in the eligibility loop**

In `views.py`, after the eligibility check passes (around line 349 where `merit_label` is computed), replace the merit label computation block with logic that branches by `merit_type`:

```python
                # Compute merit traffic light for this course
                merit_label = None
                merit_color = None
                merit_display_student = None
                merit_display_cutoff = None
                merit_type = req.get('merit_type', 'standard')

                if merit_type == 'matric':
                    # Matric: use pathways.py formula
                    track_id_map = {
                        'matric-sains': 'sains',
                        'matric-kejuruteraan': 'kejuruteraan',
                        'matric-sains-komputer': 'sains_komputer',
                        'matric-perakaunan': 'perakaunan',
                    }
                    track_id = track_id_map.get(course_id)
                    if track_id:
                        coq = data.get('coq_score', 5.0)
                        matric_result = check_matric_track(track_id, student.grades, coq)
                        if matric_result['eligible'] and matric_result['merit'] is not None:
                            matric_merit = matric_result['merit']
                            if matric_merit >= 94:
                                merit_label, merit_color = "High", "#2ecc71"
                            elif matric_merit >= 89:
                                merit_label, merit_color = "Fair", "#f1c40f"
                            else:
                                merit_label, merit_color = "Low", "#e74c3c"
                            # Override student_merit for this course
                            eligible_courses[-1] if False else None  # placeholder
                            student_merit_for_course = matric_merit
                        else:
                            # Pathways says not eligible — skip this course
                            continue

                elif merit_type == 'stpm_mata_gred':
                    # STPM: use pathways.py mata gred formula
                    bidang_id_map = {
                        'stpm-sains': 'sains',
                        'stpm-sains-sosial': 'sains_sosial',
                    }
                    bidang_id = bidang_id_map.get(course_id)
                    if bidang_id:
                        stpm_result = check_stpm_bidang(bidang_id, student.grades)
                        if stpm_result['eligible'] and stpm_result['mata_gred'] is not None:
                            mata_gred = stpm_result['mata_gred']
                            max_mg = stpm_result['max_mata_gred']
                            if mata_gred <= 12:
                                merit_label, merit_color = "High", "#2ecc71"
                            elif mata_gred <= max_mg:
                                merit_label, merit_color = "Fair", "#f1c40f"
                            else:
                                merit_label, merit_color = "Low", "#e74c3c"
                            # For STPM, override merit fields with mata gred values
                            merit_display_student = str(mata_gred)
                            merit_display_cutoff = str(max_mg)
                            student_merit_for_course = (27 - mata_gred) / 24 * 100
                        else:
                            continue

                else:
                    # Standard SPM merit
                    student_merit_for_course = student_merit
                    if merit_cutoff and source_type != 'tvet':
                        merit_label, merit_color = check_merit_probability(
                            student_merit, merit_cutoff
                        )
```

Then update the `eligible_courses.append(...)` block to include the new fields:

```python
                eligible_courses.append({
                    'course_id': course_id,
                    'course_name': course_name,
                    'level': course_level,
                    'field': course_field,
                    'source_type': source_type,
                    'pathway_type': pathway_type,
                    'merit_cutoff': merit_cutoff,
                    'student_merit': student_merit_for_course if 'student_merit_for_course' in dir() else student_merit,
                    'merit_label': merit_label,
                    'merit_color': merit_color,
                    'merit_display_student': merit_display_student,
                    'merit_display_cutoff': merit_display_cutoff,
                })
```

**Important**: Initialize `student_merit_for_course = student_merit` at the top of the loop (before the merit branching) so it always has a value.

**Step 3: Run existing tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_api.py -v`

Expected: All existing tests pass (new courses may increase golden master count by 6 × qualifying students).

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/views.py
git commit -m "feat: branch merit calculation by merit_type for matric/stpm courses"
```

---

### Task 5: Write tests for pre-U course eligibility and merit

**Files:**
- Create: `halatuju_api/apps/courses/tests/test_preu_courses.py`

**Step 1: Write the test file**

Create `halatuju_api/apps/courses/tests/test_preu_courses.py`:

```python
"""
Tests for pre-university courses as real database entries.

Covers:
- Matric merit calculation via eligibility endpoint
- STPM mata gred calculation via eligibility endpoint
- Pre-U courses appear in search results
- Pre-U courses have correct badges/fields
"""
import os
import unittest
import pandas as pd
from django.test import TestCase, override_settings
from django.apps import apps
from rest_framework.test import APIClient
from apps.courses.models import Course, CourseRequirement


def _load_test_data():
    """Load CSV data + pre-U courses into DataFrame for testing."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    halatuju_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    data_dir = os.path.join(halatuju_root, 'data')

    if not os.path.exists(data_dir):
        return None

    REQ_FLAG_COLUMNS = [
        'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
        '3m_only', 'pass_bm', 'credit_bm', 'pass_history',
        'pass_eng', 'credit_english', 'pass_math', 'credit_math', 'pass_math_addmath',
        'pass_math_science', 'pass_science_tech', 'credit_math_sci',
        'credit_math_sci_tech', 'pass_stv', 'credit_sf', 'credit_sfmt',
        'credit_bmbi', 'credit_stv',
        'req_interview', 'single', 'req_group_diversity',
        'credit_bm_b', 'credit_eng_b', 'credit_math_b', 'credit_addmath_b',
        'distinction_bm', 'distinction_eng', 'distinction_math', 'distinction_addmath',
        'distinction_bio', 'distinction_phy', 'distinction_chem', 'distinction_sci',
        'credit_science_group', 'credit_math_or_addmath',
        'pass_islam', 'credit_islam', 'pass_moral', 'credit_moral',
        'pass_sci', 'credit_sci', 'credit_addmath',
    ]
    REQ_COUNT_COLUMNS = ['min_credits', 'min_pass', 'max_aggregate_units']

    file_source_map = [
        ('requirements.csv', 'poly'),
        ('tvet_requirements.csv', 'tvet'),
        ('university_requirements.csv', 'ua'),
        ('pismp_requirements.csv', 'pismp'),
    ]
    dfs = []
    for filename, source_type in file_source_map:
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            df = pd.read_csv(path, encoding='utf-8')
            df['source_type'] = source_type
            for col in REQ_FLAG_COLUMNS + REQ_COUNT_COLUMNS:
                if col not in df.columns:
                    df[col] = 0
            for col in REQ_FLAG_COLUMNS:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            dfs.append(df)

    if not dfs:
        return None

    combined = pd.concat(dfs, ignore_index=True)

    # Ensure merit_type column exists
    if 'merit_type' not in combined.columns:
        combined['merit_type'] = 'standard'

    return combined


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPreUEligibility(TestCase):
    """Test matric/stpm courses via eligibility endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        df = _load_test_data()
        if df is None:
            raise unittest.SkipTest("No data directory found")

        # Insert pre-U courses into Django DB (for course detail lookups)
        preu_courses = [
            ('matric-sains', 'Matrikulasi — Sains', 'Pra-U', 'Sains & Teknologi'),
            ('matric-kejuruteraan', 'Matrikulasi — Kejuruteraan', 'Pra-U', 'Kejuruteraan'),
            ('matric-sains-komputer', 'Matrikulasi — Sains Komputer', 'Pra-U', 'Teknologi Maklumat'),
            ('matric-perakaunan', 'Matrikulasi — Perakaunan', 'Pra-U', 'Perakaunan & Kewangan'),
            ('stpm-sains', 'Tingkatan 6 — Sains', 'Pra-U', 'Sains & Teknologi'),
            ('stpm-sains-sosial', 'Tingkatan 6 — Sains Sosial', 'Pra-U', 'Sains Sosial'),
        ]
        for cid, name, level, field in preu_courses:
            Course.objects.get_or_create(
                course_id=cid,
                defaults={
                    'course': name, 'level': level, 'department': 'KPM',
                    'field': field, 'frontend_label': field,
                }
            )

        # Add pre-U rows to DataFrame
        preu_reqs = [
            {
                'course_id': 'matric-sains', 'source_type': 'matric',
                'merit_type': 'matric', 'merit_cutoff': 94,
                'credit_bm': 1, 'pass_history': 1, 'min_credits': 5,
                'complex_requirements': {
                    'or_groups': [
                        {'count': 1, 'grade': 'B', 'subjects': ['math']},
                        {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                        {'count': 1, 'grade': 'C', 'subjects': ['chem']},
                        {'count': 1, 'grade': 'C', 'subjects': ['phy', 'bio']},
                    ],
                },
            },
            {
                'course_id': 'matric-kejuruteraan', 'source_type': 'matric',
                'merit_type': 'matric', 'merit_cutoff': 94,
                'credit_bm': 1, 'pass_history': 1, 'min_credits': 5,
                'complex_requirements': {
                    'or_groups': [
                        {'count': 1, 'grade': 'B', 'subjects': ['math']},
                        {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                        {'count': 1, 'grade': 'C', 'subjects': ['phy']},
                    ],
                },
            },
            {
                'course_id': 'matric-sains-komputer', 'source_type': 'matric',
                'merit_type': 'matric', 'merit_cutoff': 94,
                'credit_bm': 1, 'pass_history': 1, 'min_credits': 5,
                'complex_requirements': {
                    'or_groups': [
                        {'count': 1, 'grade': 'C', 'subjects': ['math']},
                        {'count': 1, 'grade': 'C', 'subjects': ['addmath']},
                        {'count': 1, 'grade': 'C', 'subjects': ['comp_sci']},
                    ],
                },
            },
            {
                'course_id': 'matric-perakaunan', 'source_type': 'matric',
                'merit_type': 'matric', 'merit_cutoff': 94,
                'credit_bm': 1, 'pass_history': 1, 'min_credits': 5,
                'complex_requirements': {
                    'or_groups': [
                        {'count': 1, 'grade': 'C', 'subjects': ['math']},
                    ],
                },
            },
            {
                'course_id': 'stpm-sains', 'source_type': 'stpm',
                'merit_type': 'stpm_mata_gred', 'merit_cutoff': 18,
                'credit_bm': 1, 'pass_history': 1, 'min_credits': 3,
            },
            {
                'course_id': 'stpm-sains-sosial', 'source_type': 'stpm',
                'merit_type': 'stpm_mata_gred', 'merit_cutoff': 18,
                'credit_bm': 1, 'pass_history': 1, 'min_credits': 3,
            },
        ]

        # Fill missing columns with defaults
        for req in preu_reqs:
            for col in df.columns:
                if col not in req:
                    req[col] = 0

        preu_df = pd.DataFrame(preu_reqs)
        cls.combined_df = pd.concat([df, preu_df], ignore_index=True)

        courses_config = apps.get_app_config('courses')
        courses_config.requirements_df = cls.combined_df

        # Set up pathway map for pre-U courses
        courses_config.course_pathway_map = getattr(courses_config, 'course_pathway_map', {})
        for cid in ['matric-sains', 'matric-kejuruteraan', 'matric-sains-komputer', 'matric-perakaunan']:
            courses_config.course_pathway_map[cid] = 'matric'
        for cid in ['stpm-sains', 'stpm-sains-sosial']:
            courses_config.course_pathway_map[cid] = 'stpm'

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/eligibility/check/'

    def test_matric_sains_eligible(self):
        """Science student with good grades should be eligible for matric sains."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A', 'BI': 'A', 'SEJ': 'B', 'MAT': 'A',
                'AMT': 'B', 'CHE': 'B+', 'PHY': 'A-', 'SN': 'A',
            },
            'gender': 'male',
            'nationality': 'malaysian',
            'colorblind': False,
            'disability': False,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        matric = [c for c in data['eligible_courses'] if c['course_id'] == 'matric-sains']
        self.assertEqual(len(matric), 1, "matric-sains should appear in eligible courses")
        self.assertEqual(matric[0]['source_type'], 'matric')
        self.assertIn(matric[0]['merit_label'], ['High', 'Fair', 'Low'])

    def test_matric_merit_values(self):
        """Verify matric merit is calculated using grade points formula."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A+',
                'AMT': 'A+', 'CHE': 'A+', 'PHY': 'A+', 'SN': 'A+',
            },
            'gender': 'male',
            'nationality': 'malaysian',
            'coq_score': 10,
        }, format='json')

        data = response.json()
        matric = [c for c in data['eligible_courses'] if c['course_id'] == 'matric-sains']
        self.assertEqual(len(matric), 1)
        # 4x A+ = 4*25 = 100, academic = 90, coq=10 → merit = 100
        self.assertEqual(matric[0]['student_merit'], 100)
        self.assertEqual(matric[0]['merit_label'], 'High')

    def test_stpm_sains_eligible(self):
        """Student with BM credit + 3 science credits should qualify for STPM sains."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'B', 'BI': 'B', 'SEJ': 'C', 'MAT': 'A',
                'PHY': 'B+', 'CHE': 'A-', 'SN': 'B',
            },
            'gender': 'male',
            'nationality': 'malaysian',
        }, format='json')

        data = response.json()
        stpm = [c for c in data['eligible_courses'] if c['course_id'] == 'stpm-sains']
        self.assertEqual(len(stpm), 1, "stpm-sains should appear")
        self.assertEqual(stpm[0]['source_type'], 'stpm')
        # Should have mata gred display values
        self.assertIsNotNone(stpm[0].get('merit_display_student'))
        self.assertIsNotNone(stpm[0].get('merit_display_cutoff'))

    def test_stpm_mata_gred_values(self):
        """Verify STPM uses mata gred, not standard merit."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A+',
                'PHY': 'A+', 'CHE': 'A+',
            },
            'gender': 'male',
        }, format='json')

        data = response.json()
        stpm = [c for c in data['eligible_courses'] if c['course_id'] == 'stpm-sains']
        self.assertEqual(len(stpm), 1)
        # math A+=1, phy A+=1, chem A+=1 → mata_gred = 3
        self.assertEqual(stpm[0]['merit_display_student'], '3')
        self.assertEqual(stpm[0]['merit_display_cutoff'], '18')
        self.assertEqual(stpm[0]['merit_label'], 'High')

    def test_matric_not_eligible_bad_grades(self):
        """Student without required grades should not get matric courses."""
        response = self.client.post(self.url, {
            'grades': {'BM': 'D', 'SEJ': 'E'},
            'gender': 'male',
        }, format='json')

        data = response.json()
        matric = [c for c in data['eligible_courses']
                  if c['course_id'].startswith('matric-')]
        self.assertEqual(len(matric), 0, "Weak student should not qualify for matric")

    def test_preu_courses_appear_in_stats(self):
        """Pre-U courses should contribute to eligibility stats."""
        response = self.client.post(self.url, {
            'grades': {
                'BM': 'A', 'BI': 'A', 'SEJ': 'A', 'MAT': 'A',
                'AMT': 'A', 'CHE': 'A', 'PHY': 'A', 'SN': 'A',
            },
            'gender': 'male',
        }, format='json')

        data = response.json()
        stats = data['stats']
        # Strong student should qualify for both matric and stpm
        self.assertIn('matric', stats)
        self.assertIn('stpm', stats)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestPreUSearch(TestCase):
    """Test pre-U courses appear in search."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        preu_courses = [
            ('matric-sains', 'Matrikulasi — Sains', 'Pra-U', 'Sains & Teknologi'),
            ('stpm-sains', 'Tingkatan 6 — Sains', 'Pra-U', 'Sains & Teknologi'),
        ]
        for cid, name, level, field in preu_courses:
            c = Course.objects.create(
                course_id=cid, course=name, level=level,
                department='KPM', field=field, frontend_label=field,
            )
            CourseRequirement.objects.create(
                course=c, source_type='matric' if 'matric' in cid else 'stpm',
                merit_type='matric' if 'matric' in cid else 'stpm_mata_gred',
            )

    def setUp(self):
        self.client = APIClient()

    def test_search_by_level_preu(self):
        """Filtering by level=Pra-U should return pre-U courses."""
        response = self.client.get('/api/v1/courses/search/', {'level': 'Pra-U'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        course_ids = [c['course_id'] for c in data['results']]
        self.assertIn('matric-sains', course_ids)
        self.assertIn('stpm-sains', course_ids)

    def test_search_by_text_matrikulasi(self):
        """Text search for 'Matrikulasi' should return matric courses."""
        response = self.client.get('/api/v1/courses/search/', {'q': 'Matrikulasi'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        course_ids = [c['course_id'] for c in data['results']]
        self.assertIn('matric-sains', course_ids)

    def test_search_by_source_type_matric(self):
        """Filtering by source_type=matric should return matric courses."""
        response = self.client.get('/api/v1/courses/search/', {'source_type': 'matric'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        course_ids = [c['course_id'] for c in data['results']]
        self.assertIn('matric-sains', course_ids)
```

**Step 2: Run the new tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_preu_courses.py -v`

Expected: All tests pass.

**Step 3: Run the full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`

Expected: All existing tests still pass. Golden master may increase by ~6 (one per qualifying student per new course).

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/tests/test_preu_courses.py
git commit -m "test: add pre-university course eligibility and search tests"
```

---

### Task 6: Update golden master baseline

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_golden_master.py` (update baseline number)

**Step 1: Run golden master to see new baseline**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_golden_master.py -v 2>&1 | tail -20`

Expected: Test fails with new count > 8283 (6 new courses × qualifying students added).

**Step 2: Update the baseline number**

Read the failure message for the new count. Update the assertion in `test_golden_master.py` to match.

**Step 3: Re-run golden master**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_golden_master.py -v`

Expected: PASS with new baseline.

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/tests/test_golden_master.py
git commit -m "test: update golden master baseline for 6 new pre-U courses"
```

---

### Task 7: Update `SOURCE_TYPE_ORDER` and add `merit_display` fields to API response

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:81-83` (SOURCE_TYPE_ORDER)
- Modify: `halatuju-web/src/lib/api.ts` (EligibleCourse interface)

**Step 1: Add matric/stpm to SOURCE_TYPE_ORDER in views.py**

```python
SOURCE_TYPE_ORDER = {
    'ua': 5, 'matric': 4, 'stpm': 4, 'pismp': 3, 'poly': 2, 'kkom': 1,
}
```

**Step 2: Add `merit_display_*` fields to the frontend EligibleCourse interface**

In `halatuju-web/src/lib/api.ts`, add to the `EligibleCourse` interface:

```typescript
merit_display_student?: string;
merit_display_cutoff?: string;
```

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/views.py halatuju-web/src/lib/api.ts
git commit -m "feat: add matric/stpm to sort order and merit_display fields to API"
```

---

### Task 8: Run Supabase migration and verify RLS

**Step 1: Run migration on Supabase**

Use Supabase MCP to apply the migration:

```sql
-- Add merit_type column
ALTER TABLE course_requirements
ADD COLUMN IF NOT EXISTS merit_type varchar(20) NOT NULL DEFAULT 'standard';

-- Insert 6 pre-U courses
INSERT INTO courses (course_id, course, level, department, field, frontend_label)
VALUES
  ('matric-sains', 'Matrikulasi — Sains', 'Pra-U', 'KPM', 'Sains & Teknologi', 'Sains & Teknologi'),
  ('matric-kejuruteraan', 'Matrikulasi — Kejuruteraan', 'Pra-U', 'KPM', 'Kejuruteraan', 'Kejuruteraan'),
  ('matric-sains-komputer', 'Matrikulasi — Sains Komputer', 'Pra-U', 'KPM', 'Teknologi Maklumat', 'Teknologi Maklumat'),
  ('matric-perakaunan', 'Matrikulasi — Perakaunan', 'Pra-U', 'KPM', 'Perakaunan & Kewangan', 'Perakaunan & Kewangan'),
  ('stpm-sains', 'Tingkatan 6 — Sains', 'Pra-U', 'KPM', 'Sains & Teknologi', 'Sains & Teknologi'),
  ('stpm-sains-sosial', 'Tingkatan 6 — Sains Sosial', 'Pra-U', 'KPM', 'Sains Sosial', 'Sains Sosial')
ON CONFLICT (course_id) DO NOTHING;

-- Insert 6 pre-U requirements (with complex_requirements JSON)
INSERT INTO course_requirements (course_id, source_type, merit_type, merit_cutoff, credit_bm, pass_history, min_credits, complex_requirements)
VALUES
  ('matric-sains', 'matric', 'matric', 94, true, true, 5,
   '{"or_groups": [{"count": 1, "grade": "B", "subjects": ["math"]}, {"count": 1, "grade": "C", "subjects": ["addmath"]}, {"count": 1, "grade": "C", "subjects": ["chem"]}, {"count": 1, "grade": "C", "subjects": ["phy", "bio"]}]}'),
  ('matric-kejuruteraan', 'matric', 'matric', 94, true, true, 5,
   '{"or_groups": [{"count": 1, "grade": "B", "subjects": ["math"]}, {"count": 1, "grade": "C", "subjects": ["addmath"]}, {"count": 1, "grade": "C", "subjects": ["phy"]}]}'),
  ('matric-sains-komputer', 'matric', 'matric', 94, true, true, 5,
   '{"or_groups": [{"count": 1, "grade": "C", "subjects": ["math"]}, {"count": 1, "grade": "C", "subjects": ["addmath"]}, {"count": 1, "grade": "C", "subjects": ["comp_sci"]}]}'),
  ('matric-perakaunan', 'matric', 'matric', 94, true, true, 5,
   '{"or_groups": [{"count": 1, "grade": "C", "subjects": ["math"]}]}'),
  ('stpm-sains', 'stpm', 'stpm_mata_gred', 18, true, true, 3, NULL),
  ('stpm-sains-sosial', 'stpm', 'stpm_mata_gred', 18, true, true, 3, NULL)
ON CONFLICT (course_id) DO NOTHING;
```

**Step 2: Check RLS on new rows**

Use Supabase MCP: `get_advisors(project_id, type="security")` — must show 0 errors.

**Step 3: Verify data via query**

```sql
SELECT c.course_id, c.course, c.level, cr.source_type, cr.merit_type, cr.merit_cutoff
FROM courses c
JOIN course_requirements cr ON c.course_id = cr.course_id
WHERE c.level = 'Pra-U';
```

Expected: 6 rows with correct merit_type and merit_cutoff values.

---

### Task 9: Update CLAUDE.md and CHANGELOG

**Files:**
- Modify: `halatuju_api/CLAUDE.md` (golden master baseline, test count)
- Modify: `docs/CHANGELOG.md` (add sprint entry)

**Step 1: Update CLAUDE.md**

- Update golden master baseline number (from 8283 to new number)
- Update test count
- Add pre-U courses to "Pending work" → "Completed" or remove from pending

**Step 2: Update CHANGELOG**

Add entry under current sprint.

**Step 3: Commit**

```bash
git add halatuju_api/CLAUDE.md docs/CHANGELOG.md
git commit -m "docs: update golden master baseline and changelog for pre-U courses"
```

---

### Task 10: Final verification — full test suite

**Step 1: Run all tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`

Expected: All tests pass (previous count + new pre-U tests).

**Step 2: Verify no regressions**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_golden_master.py apps/courses/tests/test_stpm_golden_master.py -v`

Expected: Both golden masters pass.
