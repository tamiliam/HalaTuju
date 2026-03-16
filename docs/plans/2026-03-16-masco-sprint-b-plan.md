# MASCO Career Mappings Sprint B — AI Mapping Pipeline

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a management command that uses field_key pre-filtering + Gemini to map ~3 MASCO career codes to each unmapped course, with human review before applying.

**Architecture:** Deterministic `FIELD_KEY_TO_MASCO` dict maps each field_key to 1-3 MASCO 2-digit groups. For each unmapped course, filter MASCO jobs to those groups, send the filtered list + course name to Gemini, ask for ~3 best matches. Output a review CSV. A separate `--apply` flag reads the reviewed CSV and writes M2M links to DB.

**Tech Stack:** Django management command, Gemini API (google-genai), CSV I/O

**Design doc:** `docs/plans/2026-03-16-masco-career-mappings-design.md`

**Prerequisite:** Sprint A complete (load_masco_full, StpmCourse.career_occupations M2M, CareerPathways component)

---

## Reference: MASCO 2-Digit Groups

| Code | Group |
|------|-------|
| 11-16 | Managers (admin, production, hospitality, IT, services) |
| 21 | Professionals — Science & Engineering |
| 22 | Professionals — Health |
| 23 | Professionals — Teaching |
| 24 | Professionals — Business & Admin |
| 25 | Professionals — IT & Communications |
| 26 | Professionals — Legal |
| 27 | Professionals — Hospitality |
| 28 | Professionals — Social & Cultural |
| 31 | Associate Professionals — Science & Engineering |
| 32 | Associate Professionals — Health |
| 33 | Associate Professionals — Business & Admin |
| 34 | Associate Professionals — Legal |
| 35 | Technicians — IT & Communications |
| 36 | Associate Professionals — Social & Cultural |
| 41-44 | Clerical workers |
| 51-54 | Service & Sales workers |
| 61-63 | Skilled agricultural workers |
| 71-76 | Craft & trades workers |
| 81-83 | Machine operators & assemblers |
| 91-96 | Elementary occupations |

---

### Task 1: Create FIELD_KEY_TO_MASCO mapping

**Files:**
- Create: `halatuju_api/apps/courses/masco_mapping.py`
- Test: `halatuju_api/apps/courses/tests/test_masco_mapping.py`

**Step 1: Write the failing test**

Create `halatuju_api/apps/courses/tests/test_masco_mapping.py`:

```python
from django.test import TestCase
from apps.courses.masco_mapping import FIELD_KEY_TO_MASCO


class TestFieldKeyToMasco(TestCase):
    """Test the field_key → MASCO 2-digit group mapping."""

    def test_all_field_keys_covered(self):
        """Every active field_key should have a MASCO mapping."""
        active_keys = [
            'aero', 'alam-sekitar', 'automotif', 'elektrik', 'farmasi',
            'hospitaliti', 'it-perisian', 'it-rangkaian', 'kecantikan',
            'kejuruteraan-am', 'kimia-proses', 'kulinari', 'marin',
            'mekanikal', 'mekatronik', 'minyak-gas', 'multimedia',
            'pendidikan', 'pengajian-islam', 'pengurusan', 'perakaunan',
            'perniagaan', 'pertanian', 'perubatan', 'sains-hayat',
            'sains-sosial', 'senibina', 'senireka', 'sivil',
            'umum', 'undang-undang',
        ]
        for key in active_keys:
            self.assertIn(key, FIELD_KEY_TO_MASCO, f"Missing mapping for {key}")

    def test_mapping_returns_list_of_strings(self):
        """Each mapping should be a list of 2-digit MASCO group prefixes."""
        for key, groups in FIELD_KEY_TO_MASCO.items():
            self.assertIsInstance(groups, list, f"{key} should map to a list")
            self.assertGreater(len(groups), 0, f"{key} should have at least one group")
            for g in groups:
                self.assertIsInstance(g, str, f"{key} groups should be strings")

    def test_engineering_maps_to_relevant_groups(self):
        """Engineering fields should map to engineering MASCO groups."""
        eng_keys = ['mekanikal', 'elektrik', 'sivil', 'kejuruteraan-am']
        for key in eng_keys:
            groups = FIELD_KEY_TO_MASCO[key]
            # Should include professional (21) or associate professional (31)
            # engineering groups, plus possibly craft/operator groups
            has_eng = any(g in ('21', '31', '71', '72', '74', '81') for g in groups)
            self.assertTrue(has_eng, f"{key} should map to engineering MASCO groups")

    def test_health_maps_to_health_groups(self):
        """Health fields should map to health MASCO groups."""
        for key in ['perubatan', 'farmasi']:
            groups = FIELD_KEY_TO_MASCO[key]
            has_health = any(g in ('22', '32') for g in groups)
            self.assertTrue(has_health, f"{key} should map to health MASCO groups")

    def test_education_maps_to_teaching(self):
        """Education field should map to teaching group."""
        self.assertIn('23', FIELD_KEY_TO_MASCO['pendidikan'])
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py -v`
Expected: FAIL — `No module named 'apps.courses.masco_mapping'`

**Step 3: Create the mapping module**

Create `halatuju_api/apps/courses/masco_mapping.py`:

```python
"""
Deterministic mapping from field_key to MASCO 2-digit occupation groups.

Used by map_course_careers command to pre-filter the 4,854-job MASCO list
down to a relevant subset (~200-400 jobs) before sending to Gemini.

MASCO 2-digit groups:
  21=Sci/Eng professionals, 22=Health, 23=Teaching, 24=Business,
  25=IT, 26=Legal, 27=Hospitality, 28=Social/Cultural,
  31=Sci/Eng associates, 32=Health associates, 33=Business associates,
  34=Legal associates, 35=IT technicians, 36=Social associates,
  71-76=Craft/trades, 81-83=Operators
"""

FIELD_KEY_TO_MASCO: dict[str, list[str]] = {
    # Engineering
    'mekanikal': ['21', '31', '72', '81'],
    'elektrik': ['21', '31', '74', '81'],
    'sivil': ['21', '31', '71'],
    'kejuruteraan-am': ['21', '31', '72', '81'],
    'mekatronik': ['21', '31', '74', '81'],
    'automotif': ['21', '31', '72', '83'],
    'aero': ['21', '31', '83'],
    'marin': ['21', '31', '83'],
    'minyak-gas': ['21', '31', '81'],
    'kimia-proses': ['21', '31', '81'],

    # IT
    'it-perisian': ['25', '35'],
    'it-rangkaian': ['25', '35'],
    'multimedia': ['25', '35', '28'],

    # Health
    'perubatan': ['22', '32'],
    'farmasi': ['22', '32'],

    # Business
    'perakaunan': ['24', '33', '41'],
    'pengurusan': ['24', '33', '12'],
    'perniagaan': ['24', '33', '52'],

    # Hospitality
    'hospitaliti': ['14', '27', '51'],
    'kulinari': ['27', '51', '75'],
    'kecantikan': ['51', '27'],

    # Education
    'pendidikan': ['23'],

    # Agriculture & Environment
    'pertanian': ['21', '31', '61', '62'],
    'alam-sekitar': ['21', '31'],

    # Design & Architecture
    'senibina': ['21', '31', '71'],
    'senireka': ['28', '36', '73'],

    # Sciences
    'sains-hayat': ['21', '31'],

    # Humanities & Social
    'sains-sosial': ['24', '28', '36'],
    'undang-undang': ['26', '34'],
    'pengajian-islam': ['23', '28'],

    # General catch-all
    'umum': ['24', '33', '28'],
}
```

**Step 4: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add halatuju_api/apps/courses/masco_mapping.py halatuju_api/apps/courses/tests/test_masco_mapping.py
git commit -m "feat: add FIELD_KEY_TO_MASCO mapping for career matching pre-filter"
```

---

### Task 2: Create filter_masco_by_field_key helper

This function takes a field_key and returns the filtered list of MASCO jobs from the database.

**Files:**
- Modify: `halatuju_api/apps/courses/masco_mapping.py` (add function)
- Test: `halatuju_api/apps/courses/tests/test_masco_mapping.py` (append)

**Step 1: Write the failing test**

Add to `test_masco_mapping.py`:

```python
from apps.courses.masco_mapping import FIELD_KEY_TO_MASCO, filter_masco_by_field_key
from apps.courses.models import MascoOccupation


class TestFilterMascoByFieldKey(TestCase):
    """Test filtering MASCO records by field_key."""

    def setUp(self):
        """Create sample MASCO records across different groups."""
        MascoOccupation.objects.create(
            masco_code='2141-01', job_title='Jurutera Industri',
            emasco_url='https://emasco.mohr.gov.my/masco/2141-01')
        MascoOccupation.objects.create(
            masco_code='3113-01', job_title='Juruteknik Elektrik',
            emasco_url='https://emasco.mohr.gov.my/masco/3113-01')
        MascoOccupation.objects.create(
            masco_code='2512-01', job_title='Pembangun Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-01')
        MascoOccupation.objects.create(
            masco_code='2211-01', job_title='Doktor Perubatan',
            emasco_url='https://emasco.mohr.gov.my/masco/2211-01')

    def test_filter_returns_relevant_jobs(self):
        """Filtering by 'elektrik' should return engineering jobs, not health."""
        jobs = filter_masco_by_field_key('elektrik')
        codes = [j.masco_code for j in jobs]
        self.assertIn('2141-01', codes)  # engineering professional
        self.assertIn('3113-01', codes)  # engineering associate
        self.assertNotIn('2211-01', codes)  # health - not relevant

    def test_filter_unknown_key_returns_empty(self):
        """Unknown field_key should return empty queryset."""
        jobs = filter_masco_by_field_key('nonexistent-key')
        self.assertEqual(jobs.count(), 0)

    def test_filter_returns_queryset(self):
        """Should return a Django QuerySet."""
        from django.db.models import QuerySet
        jobs = filter_masco_by_field_key('it-perisian')
        self.assertIsInstance(jobs, QuerySet)
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py::TestFilterMascoByFieldKey -v`

**Step 3: Implement the function**

Add to `halatuju_api/apps/courses/masco_mapping.py`:

```python
from django.db.models import Q, QuerySet


def filter_masco_by_field_key(field_key: str) -> QuerySet:
    """
    Return MascoOccupation records matching the MASCO groups for a field_key.

    Only returns specific jobs (codes with '-', i.e. 4+ digit codes).
    Broad group headers (1-2 digit codes) are excluded.
    """
    from apps.courses.models import MascoOccupation

    groups = FIELD_KEY_TO_MASCO.get(field_key, [])
    if not groups:
        return MascoOccupation.objects.none()

    q = Q()
    for group in groups:
        q |= Q(masco_code__startswith=group)

    return MascoOccupation.objects.filter(q).filter(masco_code__contains='-')
```

**Step 4: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py -v`
Expected: All 8 tests pass

**Step 5: Commit**

```bash
git add halatuju_api/apps/courses/masco_mapping.py halatuju_api/apps/courses/tests/test_masco_mapping.py
git commit -m "feat: add filter_masco_by_field_key helper for career matching"
```

---

### Task 3: Create map_course_careers management command (generate mode)

This command iterates unmapped courses, calls Gemini for each, and writes a review CSV.

**Files:**
- Create: `halatuju_api/apps/courses/management/commands/map_course_careers.py`
- Test: `halatuju_api/apps/courses/tests/test_masco_mapping.py` (append)

**Step 1: Write the failing test**

Add to `test_masco_mapping.py`:

```python
from unittest.mock import patch, MagicMock


class TestMapCourseCareersCommand(TestCase):
    """Test the map_course_careers management command."""

    def setUp(self):
        from apps.courses.models import Course, CourseRequirement
        self.course = Course.objects.create(
            course_id='test-map-01',
            course='Diploma Kejuruteraan Mekanikal',
            level='Diploma',
            department='Kejuruteraan',
            field='Mekanikal',
            field_key_id='mekanikal',
        )
        CourseRequirement.objects.create(
            course=self.course, source_type='poly')
        # Create some MASCO records in relevant groups
        MascoOccupation.objects.create(
            masco_code='2141-01', job_title='Jurutera Industri',
            emasco_url='https://emasco.mohr.gov.my/masco/2141-01')
        MascoOccupation.objects.create(
            masco_code='7233-01', job_title='Mekanik Jentera Pertanian',
            emasco_url='https://emasco.mohr.gov.my/masco/7233-01')
        MascoOccupation.objects.create(
            masco_code='2141-03', job_title='Jurutera Mekanikal',
            emasco_url='https://emasco.mohr.gov.my/masco/2141-03')

    @patch('apps.courses.management.commands.map_course_careers.call_gemini')
    def test_generates_csv(self, mock_gemini):
        """Command should generate a review CSV."""
        mock_gemini.return_value = ['2141-01', '2141-03', '7233-01']

        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'review.csv')
            call_command(
                'map_course_careers',
                '--output', csv_path,
                '--source-type', 'poly',
                stdout=StringIO(),
            )
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path) as f:
                content = f.read()
            self.assertIn('test-map-01', content)
            self.assertIn('2141-01', content)

    @patch('apps.courses.management.commands.map_course_careers.call_gemini')
    def test_skips_already_mapped(self, mock_gemini):
        """Courses with existing career_occupations should be skipped."""
        occ = MascoOccupation.objects.get(masco_code='2141-01')
        self.course.career_occupations.add(occ)

        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'review.csv')
            call_command(
                'map_course_careers',
                '--output', csv_path,
                '--source-type', 'poly',
                stdout=StringIO(),
            )
            # Should not have called Gemini (course already mapped)
            mock_gemini.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py::TestMapCourseCareersCommand -v`

**Step 3: Create the management command**

Create `halatuju_api/apps/courses/management/commands/map_course_careers.py`:

```python
"""
AI-assisted MASCO career mapping for courses.

Usage:
  # Generate review CSV (dry run — no DB changes)
  python manage.py map_course_careers --source-type poly --output review_poly.csv

  # Generate for STPM courses
  python manage.py map_course_careers --stpm --output review_stpm.csv

  # Apply reviewed CSV to DB
  python manage.py map_course_careers --apply review_poly.csv
"""
import csv
import os
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.courses.models import Course, MascoOccupation
from apps.courses.masco_mapping import filter_masco_by_field_key


def call_gemini(course_name: str, field_key: str, masco_list: list[dict]) -> list[str]:
    """
    Ask Gemini to pick ~3 most relevant MASCO codes for a course.

    Args:
        course_name: The course name (Malay)
        field_key: The field_key for context
        masco_list: List of dicts with 'code' and 'title' keys

    Returns:
        List of masco_code strings (up to 3)
    """
    from google import genai

    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in settings")

    client = genai.Client(api_key=api_key)

    # Format the MASCO list for the prompt
    jobs_text = '\n'.join(f"- {j['code']}: {j['title']}" for j in masco_list)

    prompt = f"""Anda pakar pekerjaan Malaysia. Untuk kursus berikut, pilih TEPAT 3 pekerjaan MASCO yang paling relevan.

Kursus: {course_name}
Bidang: {field_key}

Senarai pekerjaan MASCO yang berkaitan:
{jobs_text}

ARAHAN:
- Pilih TEPAT 3 kod MASCO yang paling relevan untuk graduan kursus ini
- Jawab HANYA dengan 3 kod MASCO, satu per baris
- Tiada penjelasan, tiada nombor, hanya kod
- Contoh jawapan:
2141-03
7233-01
3113-05"""

    models = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']
    last_error = None

    for model_name in models:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt
            )
            # Parse response — extract MASCO codes (pattern: digits with optional dash)
            import re
            codes = re.findall(r'\b(\d{4}-\d{2})\b', response.text)
            if not codes:
                # Try broader pattern for shorter codes
                codes = re.findall(r'\b(\d{2,4}(?:-\d{2})?)\b', response.text)
            # Validate codes exist in our filtered list
            valid_codes = {j['code'] for j in masco_list}
            codes = [c for c in codes if c in valid_codes]
            return codes[:3]
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"All Gemini models failed: {last_error}")


class Command(BaseCommand):
    help = 'Map courses to MASCO career codes using AI-assisted matching'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-type',
            help='Filter SPM courses by source_type (poly, kkom, tvet, ua, pismp)',
        )
        parser.add_argument(
            '--stpm', action='store_true',
            help='Map STPM courses instead of SPM',
        )
        parser.add_argument(
            '--output', '-o',
            help='Output CSV path for review (generate mode)',
        )
        parser.add_argument(
            '--apply',
            help='Apply a reviewed CSV to the database',
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help='Limit number of courses to process (0 = all)',
        )
        parser.add_argument(
            '--delay', type=float, default=1.0,
            help='Delay between Gemini calls in seconds (default: 1.0)',
        )

    def handle(self, *args, **options):
        if options['apply']:
            self._apply_csv(options['apply'])
            return

        if not options['output']:
            self.stderr.write("Error: --output required in generate mode")
            return

        if options['stpm']:
            self._generate_stpm(options)
        else:
            self._generate_spm(options)

    def _generate_spm(self, options):
        """Generate career mappings for SPM courses."""
        qs = Course.objects.filter(career_occupations__isnull=True).distinct()

        if options['source_type']:
            qs = qs.filter(requirement__source_type=options['source_type'])

        # Exclude matric/stpm pre-U courses
        qs = qs.exclude(requirement__source_type__in=['matric', 'stpm'])

        courses = list(qs.select_related('requirement'))
        self._generate(courses, options, is_stpm=False)

    def _generate_stpm(self, options):
        """Generate career mappings for STPM courses."""
        from apps.courses.models import StpmCourse
        qs = StpmCourse.objects.filter(career_occupations__isnull=True).distinct()
        courses = list(qs)
        self._generate(courses, options, is_stpm=True)

    def _generate(self, courses, options, is_stpm):
        """Core generation loop."""
        limit = options['limit']
        delay = options['delay']
        output_path = options['output']

        if limit:
            courses = courses[:limit]

        self.stdout.write(f"Processing {len(courses)} unmapped courses...")

        rows = []
        errors = 0
        for i, course in enumerate(courses):
            course_id = course.course_id
            course_name = course.course_name if is_stpm else course.course
            field_key = (course.field_key_id or 'umum')

            # Get filtered MASCO jobs
            filtered = filter_masco_by_field_key(field_key)
            if not filtered.exists():
                self.stderr.write(f"  SKIP {course_id}: no MASCO jobs for {field_key}")
                continue

            masco_list = [
                {'code': m.masco_code, 'title': m.job_title}
                for m in filtered
            ]

            try:
                codes = call_gemini(course_name, field_key, masco_list)
                for code in codes:
                    title = next(
                        (m['title'] for m in masco_list if m['code'] == code), '')
                    rows.append({
                        'course_id': course_id,
                        'course_name': course_name,
                        'field_key': field_key,
                        'masco_code': code,
                        'job_title': title,
                        'type': 'stpm' if is_stpm else 'spm',
                    })
                self.stdout.write(
                    f"  [{i+1}/{len(courses)}] {course_id}: {len(codes)} careers")
            except Exception as e:
                self.stderr.write(f"  ERROR {course_id}: {e}")
                errors += 1

            if delay and i < len(courses) - 1:
                time.sleep(delay)

        # Write CSV
        if rows:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=['course_id', 'course_name', 'field_key',
                                'masco_code', 'job_title', 'type'],
                )
                writer.writeheader()
                writer.writerows(rows)

        self.stdout.write(
            f"\nDone. {len(rows)} mappings written to {output_path} "
            f"({errors} errors)"
        )

    def _apply_csv(self, csv_path):
        """Read a reviewed CSV and write M2M links to DB."""
        if not os.path.exists(csv_path):
            self.stderr.write(f"CSV not found: {csv_path}")
            return

        from apps.courses.models import StpmCourse

        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        applied = 0
        skipped = 0
        for row in rows:
            course_id = row['course_id']
            masco_code = row['masco_code']
            course_type = row.get('type', 'spm')

            try:
                occ = MascoOccupation.objects.get(masco_code=masco_code)
            except MascoOccupation.DoesNotExist:
                self.stderr.write(f"  SKIP: MASCO {masco_code} not found")
                skipped += 1
                continue

            try:
                if course_type == 'stpm':
                    course = StpmCourse.objects.get(course_id=course_id)
                else:
                    course = Course.objects.get(course_id=course_id)
                course.career_occupations.add(occ)
                applied += 1
            except (Course.DoesNotExist, StpmCourse.DoesNotExist):
                self.stderr.write(f"  SKIP: Course {course_id} not found")
                skipped += 1

        self.stdout.write(
            f"Applied {applied} mappings ({skipped} skipped)"
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py -v`
Expected: All tests pass

**Step 5: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All 556+ tests pass

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/management/commands/map_course_careers.py halatuju_api/apps/courses/tests/test_masco_mapping.py
git commit -m "feat: add map_course_careers command with Gemini-assisted matching"
```

---

### Task 4: Create apply mode test

**Files:**
- Test: `halatuju_api/apps/courses/tests/test_masco_mapping.py` (append)

**Step 1: Write the test**

Add to `test_masco_mapping.py`:

```python
class TestMapCourseCareersApply(TestCase):
    """Test the --apply mode of map_course_careers."""

    def setUp(self):
        from apps.courses.models import Course, CourseRequirement
        self.course = Course.objects.create(
            course_id='test-apply-01',
            course='Diploma Kejuruteraan Elektrik',
            level='Diploma',
            department='Kejuruteraan',
            field='Elektrik',
            field_key_id='elektrik',
        )
        CourseRequirement.objects.create(
            course=self.course, source_type='poly')
        MascoOccupation.objects.create(
            masco_code='2151-01', job_title='Jurutera Elektrik',
            emasco_url='https://emasco.mohr.gov.my/masco/2151-01')
        MascoOccupation.objects.create(
            masco_code='3113-01', job_title='Juruteknik Elektrik',
            emasco_url='https://emasco.mohr.gov.my/masco/3113-01')

    def test_apply_creates_m2m_links(self):
        """--apply should create M2M links from CSV."""
        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'approved.csv')
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'course_id', 'course_name', 'field_key',
                    'masco_code', 'job_title', 'type',
                ])
                writer.writeheader()
                writer.writerow({
                    'course_id': 'test-apply-01',
                    'course_name': 'Diploma Kejuruteraan Elektrik',
                    'field_key': 'elektrik',
                    'masco_code': '2151-01',
                    'job_title': 'Jurutera Elektrik',
                    'type': 'spm',
                })
                writer.writerow({
                    'course_id': 'test-apply-01',
                    'course_name': 'Diploma Kejuruteraan Elektrik',
                    'field_key': 'elektrik',
                    'masco_code': '3113-01',
                    'job_title': 'Juruteknik Elektrik',
                    'type': 'spm',
                })

            out = StringIO()
            call_command('map_course_careers', '--apply', csv_path, stdout=out)

        self.assertEqual(self.course.career_occupations.count(), 2)
        codes = list(
            self.course.career_occupations.values_list('masco_code', flat=True))
        self.assertIn('2151-01', codes)
        self.assertIn('3113-01', codes)

    def test_apply_stpm_course(self):
        """--apply should work for STPM courses too."""
        from apps.courses.models import StpmCourse
        from django.core.management import call_command
        from io import StringIO
        import tempfile, os

        stpm = StpmCourse.objects.create(
            course_id='stpm-test-apply',
            course_name='BSc Sains Komputer',
            university='UM',
            field_key_id='it-perisian',
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, 'approved.csv')
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'course_id', 'course_name', 'field_key',
                    'masco_code', 'job_title', 'type',
                ])
                writer.writeheader()
                writer.writerow({
                    'course_id': 'stpm-test-apply',
                    'course_name': 'BSc Sains Komputer',
                    'field_key': 'it-perisian',
                    'masco_code': '2151-01',
                    'job_title': 'Jurutera Elektrik',
                    'type': 'stpm',
                })

            call_command('map_course_careers', '--apply', csv_path, stdout=StringIO())

        self.assertEqual(stpm.career_occupations.count(), 1)
```

**Step 2: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_masco_mapping.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/tests/test_masco_mapping.py
git commit -m "test: add apply-mode tests for map_course_careers command"
```

---

### Task 5: Full test suite + CHANGELOG

**Step 1: Run all backend tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All tests pass (556 + new tests)

**Step 2: Update CHANGELOG.md**

Add under current sprint heading:

```markdown
### MASCO Career Mappings — Sprint B (AI Mapping Pipeline)
- **FIELD_KEY_TO_MASCO mapping**: Deterministic mapping from 31 field_keys to MASCO 2-digit occupation groups
- **filter_masco_by_field_key**: Pre-filters 4,854 MASCO jobs to ~200-400 relevant jobs per field
- **map_course_careers command**: AI-assisted career mapping with Gemini
  - Generate mode: iterates unmapped courses, calls Gemini, outputs review CSV
  - Apply mode: reads reviewed CSV, writes M2M links to DB
  - Supports both SPM (`--source-type`) and STPM (`--stpm`) courses
  - Rate limiting (`--delay`), batch size (`--limit`), model cascade
- No eligibility/ranking engine changes (golden masters safe)
```

**Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add MASCO Sprint B to changelog"
```

---

## Summary

| Task | What | Tests Added |
|------|------|-------------|
| 1 | FIELD_KEY_TO_MASCO mapping dict | 5 |
| 2 | filter_masco_by_field_key helper | 3 |
| 3 | map_course_careers command (generate mode) | 2 |
| 4 | Apply mode tests | 2 |
| 5 | Full suite + CHANGELOG | 0 |

**Total new tests:** ~12
**Files created:** 3 (masco_mapping.py, test file, management command)
**Golden masters:** Untouched (no eligibility/ranking changes)

## After Sprint B

**Sprint C (manual session):** Actually run the command against real courses:
1. `python manage.py load_masco_full` (load all 4,854 MASCO codes)
2. `python manage.py map_course_careers --source-type ua --output review_ua.csv --limit 5` (test with 5 UA courses)
3. Review the CSV, approve
4. `python manage.py map_course_careers --apply review_ua.csv`
5. Repeat for pismp, then stpm (in batches)
