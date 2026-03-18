# STPM Pipeline Completion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the STPM data pipeline production-ready — test scrapers against live MOHE, add `is_active` deactivation mechanism, extend `audit_data` for STPM, and update stale workflow docs.

**Architecture:** Add `is_active` boolean to `StpmCourse` (default True), filter all STPM queries by it, wire `sync_stpm_mohe --apply` to deactivate removed courses. Extend `audit_data` with STPM-specific checks. Fix scraper selectors against live MOHE. Update workflow doc with current numbers.

**Tech Stack:** Django ORM, Playwright (scraper), pytest

---

## Context for Implementer

### Key Files

| File | Role |
|------|------|
| `apps/courses/models.py:670-718` | `StpmCourse` model — needs `is_active` field |
| `apps/courses/stpm_engine.py:382` | `check_stpm_eligibility()` — queries ALL `StpmRequirement` rows, no active filter |
| `apps/courses/views.py:226` | Unified search — queries ALL `StpmCourse` rows |
| `apps/courses/views.py:1447` | STPM search — queries ALL `StpmCourse` rows |
| `apps/courses/views.py:1493-1498` | STPM search filter options — queries ALL rows |
| `apps/courses/views.py:277,286,299` | Unified search filter options — queries ALL rows |
| `apps/courses/views.py:887` | Saved courses STPM lookup — single `.get()`, no active filter needed (user saved it) |
| `apps/courses/views.py:1680` | STPM detail view — single `.get()`, no active filter needed (direct link) |
| `apps/courses/management/commands/sync_stpm_mohe.py` | Sync script — warns about removed but can't deactivate |
| `apps/courses/management/commands/audit_data.py` | SPM-only audit — needs STPM sections |
| `apps/courses/management/commands/scrape_mohe_stpm.py` | Listing scraper — untested against live site |
| `Settings/_workflows/stpm-requirements-update.md` | Workflow doc — stale numbers |

### Current Test Count
- 775 backend tests, 0 failures
- SPM golden master: 5319, STPM golden master: 2026
- The `is_active` field must NOT change the golden master (all existing courses default to `is_active=True`)

### STPM Query Sites (exhaustive)
These are ALL places that query `StpmCourse.objects` or `StpmRequirement.objects` in production code (not tests, not migrations):

1. `stpm_engine.py:382` — `StpmRequirement.objects.select_related('course').all()` → **MUST filter**
2. `views.py:226` — unified search queryset → **MUST filter**
3. `views.py:277` — unified search: stpm_levels existence check → **MUST filter**
4. `views.py:286` — unified search: stpm field_keys filter options → **MUST filter**
5. `views.py:299` — unified search: stpm fields filter options → **MUST filter**
6. `views.py:887` — saved courses: single `.get()` by course_id → **NO filter** (user already saved it)
7. `views.py:1447` — STPM search queryset → **MUST filter**
8. `views.py:1493` — STPM search: university filter options → **MUST filter**
9. `views.py:1497` — STPM search: stream filter options → **MUST filter**
10. `views.py:1680` — STPM detail: single `.get()` by course_id → **NO filter** (direct link still works)
11. `sync_stpm_mohe.py:40` — sync command: loads all DB courses for comparison → **NO filter** (needs to see inactive too)
12. `validate_stpm_urls.py:45` — URL validator → **NO filter** (validates all URLs)
13. `classify_stpm_fields.py:567` — backfill command → **NO filter** (one-time admin tool)
14. `generate_stpm_headlines.py:56` — headline generator → **NO filter** (admin tool)
15. `map_course_careers.py:175,275` — career mapper → **NO filter** (admin tool)

---

### Task 1: Add `is_active` Field to StpmCourse

**Files:**
- Modify: `apps/courses/models.py:670-718`
- Create: `apps/courses/migrations/0044_stpmcourse_is_active.py` (auto-generated)
- Test: `apps/courses/tests/test_stpm_models.py`

**Step 1: Write the failing test**

Add to `apps/courses/tests/test_stpm_models.py`:

```python
class TestStpmCourseIsActive:
    def test_is_active_defaults_true(self):
        from apps.courses.models import StpmCourse, FieldTaxonomy
        ft = FieldTaxonomy.objects.get(field_key='sains_komputer')
        course = StpmCourse(
            course_id='TEST_ACTIVE_001',
            course_name='Test Active Course',
            university='Test University',
            field_key=ft,
        )
        assert course.is_active is True

    def test_can_set_inactive(self):
        from apps.courses.models import StpmCourse, FieldTaxonomy
        ft = FieldTaxonomy.objects.get(field_key='sains_komputer')
        course = StpmCourse.objects.create(
            course_id='TEST_INACTIVE_001',
            course_name='Inactive Course',
            university='Test University',
            field_key=ft,
            is_active=False,
        )
        course.refresh_from_db()
        assert course.is_active is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/courses/tests/test_stpm_models.py::TestStpmCourseIsActive -v`
Expected: FAIL with `AttributeError: 'StpmCourse' has no attribute 'is_active'`

**Step 3: Add the field and create migration**

In `apps/courses/models.py`, add after line 701 (after `mohe_url`):

```python
    is_active = models.BooleanField(
        default=True,
        help_text='False = removed from MOHE, hidden from search/eligibility'
    )
```

Then generate the migration:

```bash
cd halatuju_api && python manage.py makemigrations courses --name stpmcourse_is_active
```

**Step 4: Run migration and test**

```bash
cd halatuju_api && python manage.py migrate --run-syncdb
python -m pytest apps/courses/tests/test_stpm_models.py::TestStpmCourseIsActive -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/courses/models.py apps/courses/migrations/0044_stpmcourse_is_active.py apps/courses/tests/test_stpm_models.py
git commit -m "feat: add is_active field to StpmCourse (default True)"
```

---

### Task 2: Filter STPM Queries by `is_active=True`

**Files:**
- Modify: `apps/courses/stpm_engine.py:382`
- Modify: `apps/courses/views.py:226,277,286,299,1447,1493,1497`
- Test: `apps/courses/tests/test_stpm_engine.py` and `apps/courses/tests/test_stpm_search.py`

**Step 1: Write the failing tests**

Add to `apps/courses/tests/test_stpm_engine.py`:

```python
class TestStpmIsActiveFiltering:
    """Inactive courses must be excluded from eligibility checks."""

    @pytest.fixture(autouse=True)
    def setup_courses(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)

    def test_inactive_course_excluded_from_eligibility(self):
        """Mark a course inactive — it must disappear from results."""
        from apps.courses.models import StpmCourse
        # Pick any course and deactivate it
        course = StpmCourse.objects.first()
        original_id = course.course_id
        course.is_active = False
        course.save(update_fields=['is_active'])

        # Run eligibility with the strongest student (matches most courses)
        results = check_stpm_eligibility(
            stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'},
            spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'addmath': 'A', 'sci': 'A'},
            cgpa=4.0,
            muet_band=6,
        )
        result_ids = [r['course_id'] for r in results]
        assert original_id not in result_ids
```

Add to `apps/courses/tests/test_stpm_search.py`:

```python
class TestStpmSearchIsActive:
    """Inactive courses must be excluded from search."""

    @pytest.fixture(autouse=True)
    def setup_courses(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('loaddata', 'stpm_courses', 'stpm_requirements', stdout=StringIO(), verbosity=0)

    def test_inactive_course_excluded_from_search(self, client):
        from apps.courses.models import StpmCourse
        total_before = StpmCourse.objects.count()

        # Deactivate one course
        course = StpmCourse.objects.first()
        course.is_active = False
        course.save(update_fields=['is_active'])

        response = client.get('/api/v1/stpm/search/')
        assert response.status_code == 200
        assert response.data['total_count'] == total_before - 1

    def test_inactive_course_excluded_from_unified_search(self, client):
        from apps.courses.models import StpmCourse
        total_before = StpmCourse.objects.filter(is_active=True).count()

        # Deactivate one course
        course = StpmCourse.objects.first()
        course.is_active = False
        course.save(update_fields=['is_active'])

        response = client.get('/api/v1/search/?qualification=STPM')
        assert response.status_code == 200
        # Count should be one less than before
        stpm_results = [r for r in response.data['courses'] if r.get('qualification') == 'STPM']
        assert len(stpm_results) < total_before
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/courses/tests/test_stpm_engine.py::TestStpmIsActiveFiltering -v
python -m pytest apps/courses/tests/test_stpm_search.py::TestStpmSearchIsActive -v
```

Expected: FAIL (inactive course still appears)

**Step 3: Apply the filters**

In `apps/courses/stpm_engine.py:382`, change:
```python
all_reqs = StpmRequirement.objects.select_related('course').all()
```
to:
```python
all_reqs = StpmRequirement.objects.select_related('course').filter(course__is_active=True)
```

In `apps/courses/views.py`, apply these changes:

**Line 226** (unified search queryset):
```python
# Before:
stpm_qs = StpmCourse.objects.select_related('requirement', 'institution').all()
# After:
stpm_qs = StpmCourse.objects.select_related('requirement', 'institution').filter(is_active=True)
```

**Line 277** (unified search stpm_levels check):
```python
# Before:
stpm_levels = ['Ijazah Sarjana Muda'] if StpmCourse.objects.exists() else []
# After:
stpm_levels = ['Ijazah Sarjana Muda'] if StpmCourse.objects.filter(is_active=True).exists() else []
```

**Line 286** (unified search field_keys):
```python
# Before:
StpmCourse.objects.exclude(field_key__isnull=True)
# After:
StpmCourse.objects.filter(is_active=True).exclude(field_key__isnull=True)
```

**Line 299** (unified search fields):
```python
# Before:
StpmCourse.objects.exclude(field='')
# After:
StpmCourse.objects.filter(is_active=True).exclude(field='')
```

**Line 1447** (STPM search queryset):
```python
# Before:
qs = StpmCourse.objects.select_related('requirement').all()
# After:
qs = StpmCourse.objects.select_related('requirement').filter(is_active=True)
```

**Lines 1493-1498** (STPM search filter options):
```python
# Before:
StpmCourse.objects.values_list('university', flat=True)
StpmCourse.objects.values_list('stream', flat=True)
# After:
StpmCourse.objects.filter(is_active=True).values_list('university', flat=True)
StpmCourse.objects.filter(is_active=True).values_list('stream', flat=True)
```

**Step 4: Run tests**

```bash
python -m pytest apps/courses/tests/test_stpm_engine.py::TestStpmIsActiveFiltering apps/courses/tests/test_stpm_search.py::TestStpmSearchIsActive -v
```

Expected: PASS

**Step 5: Run the full test suite including golden masters**

```bash
python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

Expected: All 775+ tests pass. Golden masters unchanged (all fixtures have `is_active=True` by default).

**Step 6: Commit**

```bash
git add apps/courses/stpm_engine.py apps/courses/views.py apps/courses/tests/test_stpm_engine.py apps/courses/tests/test_stpm_search.py
git commit -m "feat: filter all STPM queries by is_active, exclude deactivated courses"
```

---

### Task 3: Wire `sync_stpm_mohe` to Deactivate Removed Courses

**Files:**
- Modify: `apps/courses/management/commands/sync_stpm_mohe.py`
- Test: `apps/courses/tests/test_stpm_sync.py` (new file)

**Step 1: Write the failing tests**

Create `apps/courses/tests/test_stpm_sync.py`:

```python
"""Tests for the sync_stpm_mohe management command."""
import csv
import tempfile
import pytest
from io import StringIO
from django.core.management import call_command
from apps.courses.models import StpmCourse, FieldTaxonomy


@pytest.fixture
def field_key():
    return FieldTaxonomy.objects.get(field_key='sains_komputer')


@pytest.fixture
def setup_courses(field_key):
    """Create 3 test courses."""
    StpmCourse.objects.create(
        course_id='UM0001', course_name='Course A',
        university='UM', field_key=field_key, merit_score=80.0,
        mohe_url='https://old.url/UM0001',
    )
    StpmCourse.objects.create(
        course_id='USM0002', course_name='Course B',
        university='USM', field_key=field_key, merit_score=70.0,
    )
    StpmCourse.objects.create(
        course_id='UKM0003', course_name='Course C',
        university='UKM', field_key=field_key, merit_score=60.0,
        is_active=True,
    )


def _write_csv(rows):
    """Write rows to a temp CSV and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8'
    )
    writer = csv.DictWriter(f, fieldnames=[
        'course_id', 'course_name', 'university', 'merit',
        'stream', 'mohe_url', 'badges', 'year',
    ])
    writer.writeheader()
    writer.writerows(rows)
    f.close()
    return f.name


@pytest.mark.django_db
class TestSyncStpmMohe:
    def test_dry_run_reports_removed(self, setup_courses):
        """Dry run should report removed courses but not change DB."""
        # CSV has only UM0001 — USM0002 and UKM0003 are "removed"
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '80.0',
            'stream': 'science', 'mohe_url': 'https://new.url/UM0001',
            'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'REMOVED (2)' in output
        # DB unchanged — courses still active
        assert StpmCourse.objects.filter(is_active=True).count() == 3

    def test_apply_deactivates_removed(self, setup_courses):
        """--apply should set is_active=False on removed courses."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '80.0',
            'stream': 'science', 'mohe_url': 'https://new.url/UM0001',
            'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, stdout=out)
        output = out.getvalue()

        # UM0001 still active
        assert StpmCourse.objects.get(course_id='UM0001').is_active is True
        # USM0002 and UKM0003 deactivated
        assert StpmCourse.objects.get(course_id='USM0002').is_active is False
        assert StpmCourse.objects.get(course_id='UKM0003').is_active is False
        assert 'Deactivated 2' in output

    def test_apply_reactivates_returned_course(self, setup_courses):
        """A previously deactivated course that reappears should be reactivated."""
        # First deactivate UKM0003
        StpmCourse.objects.filter(course_id='UKM0003').update(is_active=False)

        # CSV includes all 3 — UKM0003 is back
        csv_path = _write_csv([
            {'course_id': 'UM0001', 'course_name': 'Course A', 'university': 'UM',
             'merit': '80.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'USM0002', 'course_name': 'Course B', 'university': 'USM',
             'merit': '70.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'UKM0003', 'course_name': 'Course C', 'university': 'UKM',
             'merit': '60.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
        ])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, stdout=out)
        output = out.getvalue()

        assert StpmCourse.objects.get(course_id='UKM0003').is_active is True
        assert 'Reactivated 1' in output

    def test_apply_updates_url(self, setup_courses):
        """--apply should update mohe_url for matched courses."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '80.0',
            'stream': 'science', 'mohe_url': 'https://new.url/UM0001',
            'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, apply=True, stdout=out)

        course = StpmCourse.objects.get(course_id='UM0001')
        assert course.mohe_url == 'https://new.url/UM0001'

    def test_reports_merit_changes(self, setup_courses):
        """Merit changes should be reported."""
        csv_path = _write_csv([{
            'course_id': 'UM0001', 'course_name': 'Course A',
            'university': 'UM', 'merit': '85.5',
            'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026',
        }])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'MERIT CHANGES (1)' in output
        assert '80.00%' in output
        assert '85.50%' in output

    def test_reports_new_programmes(self, setup_courses):
        """New programmes in MOHE should be reported."""
        csv_path = _write_csv([
            {'course_id': 'UM0001', 'course_name': 'Course A', 'university': 'UM',
             'merit': '80.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'NEW0001', 'course_name': 'New Course', 'university': 'UPM',
             'merit': '75.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
        ])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'NEW (1)' in output
        assert 'NEW0001' in output

    def test_dry_run_count_summary(self, setup_courses):
        """Dry run should show the inactive count."""
        # Deactivate one course first
        StpmCourse.objects.filter(course_id='UKM0003').update(is_active=False)
        csv_path = _write_csv([
            {'course_id': 'UM0001', 'course_name': 'A', 'university': 'UM',
             'merit': '80.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'USM0002', 'course_name': 'B', 'university': 'USM',
             'merit': '70.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
            {'course_id': 'UKM0003', 'course_name': 'C', 'university': 'UKM',
             'merit': '60.0', 'stream': 'science', 'mohe_url': '', 'badges': '', 'year': '2026'},
        ])
        out = StringIO()
        call_command('sync_stpm_mohe', csv=csv_path, stdout=out)
        output = out.getvalue()
        assert 'Currently inactive: 1' in output
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/courses/tests/test_stpm_sync.py -v
```

Expected: FAIL

**Step 3: Rewrite `sync_stpm_mohe.py`**

Replace the full content of `apps/courses/management/commands/sync_stpm_mohe.py`:

```python
"""
Compare scraped MOHE data with DB and sync changes.

Reads the CSV output from scrape_mohe_stpm and:
1. Reports new programmes (in MOHE but not in DB)
2. Reports removed programmes (in DB but not in MOHE)
3. Reports changed merit scores
4. Updates mohe_url for all matched courses
5. Deactivates removed courses / reactivates returned courses

Usage:
    python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv
    python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv --apply
"""
import csv
from django.core.management.base import BaseCommand
from apps.courses.models import StpmCourse


class Command(BaseCommand):
    help = 'Sync STPM course data from scraped MOHE CSV'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='Path to scraped CSV')
        parser.add_argument('--apply', action='store_true', help='Apply changes (default: report only)')

    def handle(self, *args, **options):
        csv_path = options['csv']
        apply = options['apply']

        # Load scraped data
        scraped = {}
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cid = row['course_id'].strip()
                if cid:
                    scraped[cid] = row

        # Load DB data (all courses, including inactive)
        db_courses = {c.course_id: c for c in StpmCourse.objects.all()}

        db_ids = set(db_courses.keys())
        mohe_ids = set(scraped.keys())

        # --- Report ---
        new_ids = mohe_ids - db_ids
        removed_ids = db_ids - mohe_ids
        common_ids = db_ids & mohe_ids

        inactive_count = StpmCourse.objects.filter(is_active=False).count()

        self.stdout.write(f'\n=== STPM MOHE Sync Report ===')
        self.stdout.write(f'MOHE programmes: {len(mohe_ids)}')
        self.stdout.write(f'DB courses:      {len(db_ids)}')
        self.stdout.write(f'Matched:         {len(common_ids)}')
        self.stdout.write(f'Currently inactive: {inactive_count}')

        # New programmes
        if new_ids:
            self.stdout.write(self.style.WARNING(f'\n--- NEW ({len(new_ids)}) ---'))
            for cid in sorted(new_ids):
                row = scraped[cid]
                self.stdout.write(f'  + {cid}: {row["course_name"]} ({row["university"]})')

        # Removed programmes (in DB but not in MOHE)
        if removed_ids:
            # Only flag active ones as needing deactivation
            active_removed = [cid for cid in removed_ids if db_courses[cid].is_active]
            already_inactive = [cid for cid in removed_ids if not db_courses[cid].is_active]

            if active_removed:
                self.stdout.write(self.style.ERROR(
                    f'\n--- REMOVED — will deactivate ({len(active_removed)}) ---'
                ))
                for cid in sorted(active_removed):
                    course = db_courses[cid]
                    self.stdout.write(f'  - {cid}: {course.course_name} ({course.university})')

            if already_inactive:
                self.stdout.write(
                    f'\n  ({len(already_inactive)} already inactive, unchanged)'
                )

        # Reactivation candidates (in MOHE and in DB but currently inactive)
        reactivate_ids = [
            cid for cid in common_ids
            if not db_courses[cid].is_active
        ]
        if reactivate_ids:
            self.stdout.write(self.style.SUCCESS(
                f'\n--- REACTIVATE ({len(reactivate_ids)}) ---'
            ))
            for cid in sorted(reactivate_ids):
                course = db_courses[cid]
                self.stdout.write(f'  ↑ {cid}: {course.course_name} ({course.university})')

        # Merit changes
        merit_changes = []
        url_updates = 0
        for cid in common_ids:
            row = scraped[cid]
            course = db_courses[cid]

            # Check merit change
            new_merit = None
            if row.get('merit'):
                try:
                    new_merit = float(row['merit'])
                except ValueError:
                    pass

            if new_merit is not None and course.merit_score is not None:
                if abs(new_merit - course.merit_score) > 0.01:
                    merit_changes.append((cid, course.merit_score, new_merit))

            # Check URL update needed
            if row.get('mohe_url') and row['mohe_url'] != course.mohe_url:
                url_updates += 1

        if merit_changes:
            self.stdout.write(self.style.WARNING(f'\n--- MERIT CHANGES ({len(merit_changes)}) ---'))
            for cid, old, new in sorted(merit_changes):
                self.stdout.write(f'  ~ {cid}: {old:.2f}% -> {new:.2f}%')

        self.stdout.write(f'\nURL updates needed: {url_updates}')

        # --- Apply ---
        if not apply:
            self.stdout.write(self.style.NOTICE(
                '\nDry run. Use --apply to write changes to DB.'
            ))
            return

        # Apply URL updates
        updated = 0
        for cid in common_ids:
            row = scraped[cid]
            course = db_courses[cid]
            changed = False

            if row.get('mohe_url') and row['mohe_url'] != course.mohe_url:
                course.mohe_url = row['mohe_url']
                changed = True

            if changed:
                course.save(update_fields=['mohe_url'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'\nApplied: {updated} URL updates'))

        # Deactivate removed courses
        active_removed = [cid for cid in removed_ids if db_courses[cid].is_active]
        if active_removed:
            deactivated = StpmCourse.objects.filter(
                course_id__in=active_removed
            ).update(is_active=False)
            self.stdout.write(self.style.WARNING(
                f'Deactivated {deactivated} removed courses'
            ))

        # Reactivate returned courses
        if reactivate_ids:
            reactivated = StpmCourse.objects.filter(
                course_id__in=reactivate_ids
            ).update(is_active=True)
            self.stdout.write(self.style.SUCCESS(
                f'Reactivated {reactivated} returned courses'
            ))

        if merit_changes:
            self.stdout.write(self.style.WARNING(
                f'{len(merit_changes)} merit changes detected but NOT auto-applied. '
                'Review the report above and update manually or extend this command.'
            ))

        if new_ids:
            self.stdout.write(self.style.WARNING(
                f'{len(new_ids)} new programmes detected. '
                'These need manual review — requirements must be parsed before adding to DB.'
            ))
```

**Step 4: Run tests**

```bash
python -m pytest apps/courses/tests/test_stpm_sync.py -v
```

Expected: All 7 tests PASS

**Step 5: Run full test suite**

```bash
python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

Expected: All tests pass, golden masters unchanged.

**Step 6: Commit**

```bash
git add apps/courses/management/commands/sync_stpm_mohe.py apps/courses/tests/test_stpm_sync.py
git commit -m "feat: sync_stpm_mohe deactivates removed courses, reactivates returned ones"
```

---

### Task 4: Extend `audit_data` for STPM

**Files:**
- Modify: `apps/courses/management/commands/audit_data.py`
- Test: Manual run (management command output)

**Step 1: Add STPM imports and audit methods**

Modify `apps/courses/management/commands/audit_data.py`. Add `StpmCourse`, `StpmRequirement`, and `MascoOccupation` to imports, add 3 new audit methods, and call them from `handle()`.

Updated imports (line 10-12):

```python
from apps.courses.models import (
    Course, CourseRequirement, CourseTag, Institution, CourseInstitution,
    StpmCourse, StpmRequirement, MascoOccupation
)
```

Add to `handle()` after `self.audit_tags()`:

```python
        self.audit_stpm_courses()
        self.audit_stpm_requirements()
        self.audit_stpm_careers()
```

Add 3 new methods after `audit_tags()`:

```python
    def audit_stpm_courses(self):
        total = StpmCourse.objects.count()
        active = StpmCourse.objects.filter(is_active=True).count()
        inactive = total - active
        no_desc = StpmCourse.objects.filter(description='').count()
        no_headline = StpmCourse.objects.filter(headline='').count()
        no_mohe = StpmCourse.objects.filter(mohe_url='').count()
        no_merit = StpmCourse.objects.filter(merit_score__isnull=True).count()
        no_institution = StpmCourse.objects.filter(institution__isnull=True).count()
        no_careers = StpmCourse.objects.filter(career_occupations__isnull=True).distinct().count()

        self.stdout.write(f'\nSTPM COURSES: {total} total ({active} active, {inactive} inactive)')
        self.stdout.write(f'  Missing description:    {no_desc}')
        self.stdout.write(f'  Missing headline:       {no_headline}')
        self.stdout.write(f'  Missing MOHE URL:       {no_mohe}')
        self.stdout.write(f'  Missing merit score:    {no_merit}')
        self.stdout.write(f'  Missing institution FK: {no_institution}')
        self.stdout.write(f'  Missing career links:   {no_careers}')

    def audit_stpm_requirements(self):
        total_courses = StpmCourse.objects.count()
        total_reqs = StpmRequirement.objects.count()
        orphaned = total_courses - total_reqs

        self.stdout.write(f'\nSTPN REQUIREMENTS: {total_reqs} / {total_courses} courses covered')
        self.stdout.write(f'  Courses without requirements: {orphaned}')

        if orphaned > 0:
            req_ids = set(StpmRequirement.objects.values_list('course_id', flat=True))
            all_ids = set(StpmCourse.objects.values_list('course_id', flat=True))
            missing = list(all_ids - req_ids)[:5]
            self.stdout.write(f'  Sample missing: {missing}')

        # Subject group coverage
        has_stpm_group = StpmRequirement.objects.exclude(
            stpm_subject_group__isnull=True
        ).count()
        has_spm_group = StpmRequirement.objects.exclude(
            spm_subject_group__isnull=True
        ).count()
        self.stdout.write(f'  With STPM subject groups: {has_stpm_group}')
        self.stdout.write(f'  With SPM subject groups:  {has_spm_group}')

    def audit_stpm_careers(self):
        total_stpm = StpmCourse.objects.count()
        with_careers = StpmCourse.objects.filter(
            career_occupations__isnull=False
        ).distinct().count()
        without = total_stpm - with_careers

        total_links = StpmCourse.career_occupations.through.objects.count()

        self.stdout.write(f'\nSTPM CAREER MAPPINGS: {with_careers} / {total_stpm} courses mapped')
        self.stdout.write(f'  Courses without career links: {without}')
        self.stdout.write(f'  Total M2M links: {total_links}')
```

**Step 2: Run the audit command to verify output**

```bash
cd halatuju_api && python manage.py audit_data
```

Expected: New STPM sections appear in output with non-zero numbers.

**Step 3: Run full test suite**

```bash
python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

Expected: All tests pass (audit_data has no dedicated tests — it's a reporting tool).

**Step 4: Commit**

```bash
git add apps/courses/management/commands/audit_data.py
git commit -m "feat: extend audit_data with STPM courses, requirements, and career mapping checks"
```

---

### Task 5: Test Scraper Against Live MOHE

**Files:**
- Modify: `apps/courses/management/commands/scrape_mohe_stpm.py` (if selectors need fixing)
- No test file — this is a live integration test

**Step 1: Run the scraper in test mode (first page only)**

```bash
cd halatuju_api && python manage.py scrape_mohe_stpm --output data/stpm/mohe_test.csv --category S --delay 2.0
```

Watch the output. If it hangs or returns 0 programmes, the selectors are broken.

**Step 2: Diagnose selector issues**

If the scraper returns 0 results:

1. Launch Playwright interactively to inspect the live page:
```bash
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://online.mohe.gov.my/epanduan/ProgramPengajian/kategoriCalon/S?jenprog=stpm&page=1')
    page.wait_for_load_state('networkidle')
    print('Title:', page.title())
    # Check if the heading exists
    h5 = page.query_selector('h5')
    print('H5:', h5.inner_text() if h5 else 'NOT FOUND')
    # Check card structure
    cards = page.query_selector_all('a[href=\"#\"]')
    print(f'Found {len(cards)} card links')
    input('Press Enter to close...')
    browser.close()
"
```

2. If the DOM structure changed, update `_parse_cards()` in `scrape_mohe_stpm.py` to match the new structure.

3. If the URL pattern changed, update `LISTING_URL` at line 19.

**Step 3: If selectors work, run full scrape**

```bash
cd halatuju_api && python manage.py scrape_mohe_stpm --output data/stpm/mohe_2026.csv --delay 1.5
```

Expected: ~1,100+ programmes in the CSV.

**Step 4: Run sync in dry-run mode to compare**

```bash
cd halatuju_api && python manage.py sync_stpm_mohe --csv data/stpm/mohe_2026.csv
```

Review the diff report. Expected: mostly matched, possibly a few new/removed/merit changes.

**Step 5: If selectors were fixed, commit**

```bash
git add apps/courses/management/commands/scrape_mohe_stpm.py
git commit -m "fix: update scraper selectors for current MOHE ePanduan DOM"
```

If no fixes were needed:

```bash
# No commit needed — scraper works as-is
```

**Step 6: Clean up test CSV**

```bash
rm data/stpm/mohe_test.csv
```

Keep `data/stpm/mohe_2026.csv` if the scrape was successful — it's the latest snapshot.

---

### Task 6: Update Workflow Documentation

**Files:**
- Modify: `Settings/_workflows/stpm-requirements-update.md`

**Step 1: Update stale numbers and add deactivation step**

Apply these changes to `Settings/_workflows/stpm-requirements-update.md`:

**Line 100** — Update test count and golden master:
```markdown
# Before:
- **Expected:** All 655+ tests pass. STPM golden master value = 2026.
# After:
- **Expected:** All 775+ tests pass. STPM golden master value = 2026.
```

**After Stage 4 (line 102)**, add a new Stage 5:

```markdown
### Stage 5: Sync with MOHE Listing (Deactivation)

After loading new requirements, run the MOHE listing sync to detect removed programmes:

**Commands:**

```bash
# 1. Scrape latest MOHE listing
cd Development/HalaTuju/halatuju_api && python manage.py scrape_mohe_stpm --output data/stpm/mohe_latest.csv --delay 1.5

# 2. Dry run — review changes
cd Development/HalaTuju/halatuju_api && python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv

# 3. Apply — updates URLs, deactivates removed, reactivates returned
cd Development/HalaTuju/halatuju_api && python manage.py sync_stpm_mohe --csv data/stpm/mohe_latest.csv --apply
```

- **Checkpoint:** Review the dry-run report. New programmes need manual requirement parsing. Removed programmes will be deactivated (hidden from search and eligibility, but data preserved in DB).
- **Reactivation:** If a previously removed programme reappears in MOHE, it is automatically reactivated.
```

**Update the failure modes table** — add a new row:

```markdown
| Deactivated course still appears | `is_active` filter missing from a query | Check all `StpmCourse.objects` queries in `views.py` and `stpm_engine.py` filter by `is_active=True` |
```

**Update the tool inventory table** — the `scrape_stpm_requirements.py` status:

```markdown
| `scrape_stpm_requirements.py` | `Settings/_tools/stpm_requirements/` | Scrapes MOHE portal for raw HTML requirements |
```

Remove "(planned — Sprint 5)" since we're completing this sprint now.

**Step 2: Verify the workflow doc is coherent**

Read through the full doc to ensure stages flow logically: 0→1→2→3→4→5.

**Step 3: Commit**

```bash
git add Settings/_workflows/stpm-requirements-update.md
git commit -m "docs: update STPM workflow with current test counts and deactivation stage"
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| `is_active` migration on production Supabase | Low — adds nullable-like boolean column with default | Django default handles it; verify RLS still works |
| Golden master changes | HIGH — means eligibility logic broke | Default `is_active=True` means no change to existing data |
| MOHE selectors broken | Medium — scraper returns empty | Interactive Playwright debugging in Task 5, Step 2 |
| Queries missed for `is_active` filter | Medium — inactive courses leak into results | Exhaustive query audit in Context section above; tests verify |
| Supabase RLS on new column | Low — column is on existing table with existing RLS | No new table created, existing policies cover it |

## Execution Order

Tasks 1→2→3 are sequential (each depends on the previous).
Task 4 is independent (can run after Task 1).
Task 5 is independent (live MOHE test).
Task 6 is independent (docs only).

Recommended: 1 → 2 → 3 → 4 → 5 → 6
