# MASCO Career Mappings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Every course detail page (except Matric/STPM pre-U) shows ~3 relevant MASCO career titles linking to the eMASCO portal.

**Architecture:** Load 4,854 MASCO codes into DB, add M2M to StpmCourse, use field_key pre-filtering + Gemini to match ~3 careers per course, extract shared CareerPathways frontend component.

**Tech Stack:** Django ORM, Gemini API (google-genai), Next.js/React, TailwindCSS

**Design doc:** `docs/plans/2026-03-16-masco-career-mappings-design.md`

---

## Sprint Sizing

This is a multi-sprint effort. Suggested breakdown:

- **Sprint A (this plan):** Backend foundation — load MASCO data, StpmCourse M2M, API, shared frontend component
- **Sprint B (separate plan):** AI mapping pipeline — field_key→MASCO digit map, Gemini matcher, review CSV, apply
- **Sprint C (separate plan):** Review + apply mappings for all ~1,275 courses

This plan covers **Sprint A only**.

---

### Task 1: Load Full MASCO Dataset

**Files:**
- Create: `halatuju_api/apps/courses/management/commands/load_masco_full.py`
- Data: `halatuju_api/data/masco_full.csv` (already exists)
- Test: `halatuju_api/apps/courses/tests/test_data_loading.py` (append)

**Step 1: Write the failing test**

Add to `test_data_loading.py`:

```python
class TestLoadMascoFull(TestCase):
    """Test loading full MASCO dataset from CSV."""

    def test_load_creates_records(self):
        """Loading CSV should create MascoOccupation records."""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command('load_masco_full', stdout=out)
        output = out.getvalue()

        # Should load records
        count = MascoOccupation.objects.count()
        self.assertGreater(count, 4000, f"Expected 4000+ records, got {count}")
        self.assertIn('Loaded', output)

    def test_emasco_url_generated(self):
        """Each record should have emasco_url from kod_masco."""
        from django.core.management import call_command
        from io import StringIO

        call_command('load_masco_full', stdout=StringIO())

        # Check a specific-code record has correct URL
        specific = MascoOccupation.objects.filter(
            masco_code__contains='-'
        ).first()
        if specific:
            expected = f'https://emasco.mohr.gov.my/masco/{specific.masco_code}'
            self.assertEqual(specific.emasco_url, expected)

    def test_idempotent(self):
        """Running twice should not create duplicates."""
        from django.core.management import call_command
        from io import StringIO

        call_command('load_masco_full', stdout=StringIO())
        count1 = MascoOccupation.objects.count()
        call_command('load_masco_full', stdout=StringIO())
        count2 = MascoOccupation.objects.count()
        self.assertEqual(count1, count2)

    def test_duplicate_kod_masco_handled(self):
        """Duplicate kod_masco values in CSV should not crash."""
        from django.core.management import call_command
        from io import StringIO

        # Should complete without error
        call_command('load_masco_full', stdout=StringIO())
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_data_loading.py::TestLoadMascoFull -v`
Expected: FAIL — command does not exist

**Step 3: Write the management command**

Create `halatuju_api/apps/courses/management/commands/load_masco_full.py`:

```python
"""Load full MASCO 2020 dataset (4,854 jobs) into MascoOccupation table."""
import csv
import os
from django.core.management.base import BaseCommand
from apps.courses.models import MascoOccupation

EMASCO_BASE = 'https://emasco.mohr.gov.my/masco'


class Command(BaseCommand):
    help = 'Load full MASCO 2020 occupations from masco_full.csv'

    def handle(self, *args, **options):
        csv_path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'masco_full.csv'
        )
        csv_path = os.path.normpath(csv_path)

        if not os.path.exists(csv_path):
            self.stderr.write(f'CSV not found: {csv_path}')
            return

        # Read all rows, deduplicating by kod_masco (keep first civilian entry)
        seen = {}
        with open(csv_path, encoding='latin-1') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row['kod_masco'].strip()
                title = row['tajuk_pekerjaan'].strip()
                if code and code not in seen:
                    seen[code] = title

        # Bulk create/update
        created = 0
        updated = 0
        for code, title in seen.items():
            url = f'{EMASCO_BASE}/{code}'
            obj, was_created = MascoOccupation.objects.update_or_create(
                masco_code=code,
                defaults={'job_title': title, 'emasco_url': url},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            f'Loaded {created + updated} MASCO occupations '
            f'({created} created, {updated} updated)'
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_data_loading.py::TestLoadMascoFull -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add apps/courses/management/commands/load_masco_full.py apps/courses/tests/test_data_loading.py
git commit -m "feat: add load_masco_full command — loads 4,854 MASCO 2020 occupations"
```

---

### Task 2: Add career_occupations M2M to StpmCourse

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:578-619` (StpmCourse model)
- Create: new migration via `makemigrations`
- Test: `halatuju_api/apps/courses/tests/test_stpm_models.py` (append)

**Step 1: Write the failing test**

Add to `test_stpm_models.py`:

```python
class TestStpmCourseCareerOccupations(TestCase):
    """Test M2M relationship between StpmCourse and MascoOccupation."""

    def setUp(self):
        self.course = StpmCourse.objects.create(
            course_id='test-stpm-career',
            course_name='Test Programme',
            university='Universiti Test',
        )
        self.occ = MascoOccupation.objects.create(
            masco_code='2512-03',
            job_title='Jurutera Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-03',
        )

    def test_can_add_career_occupation(self):
        """StpmCourse should support M2M career_occupations."""
        self.course.career_occupations.add(self.occ)
        self.assertEqual(self.course.career_occupations.count(), 1)

    def test_reverse_relation(self):
        """MascoOccupation should have reverse relation to StpmCourse."""
        self.course.career_occupations.add(self.occ)
        self.assertIn(self.course, self.occ.stpm_courses.all())

    def test_multiple_occupations(self):
        """StpmCourse should support multiple career_occupations."""
        occ2 = MascoOccupation.objects.create(
            masco_code='2513-01',
            job_title='Pembangun Web',
            emasco_url='https://emasco.mohr.gov.my/masco/2513-01',
        )
        self.course.career_occupations.add(self.occ, occ2)
        self.assertEqual(self.course.career_occupations.count(), 2)
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py::TestStpmCourseCareerOccupations -v`
Expected: FAIL — `StpmCourse has no field named 'career_occupations'`

**Step 3: Add the M2M field**

In `halatuju_api/apps/courses/models.py`, add to `StpmCourse` class (after line 612, before `class Meta`):

```python
    # Career pathway: links to MASCO occupation codes
    career_occupations = models.ManyToManyField(
        'MascoOccupation',
        related_name='stpm_courses',
        blank=True,
        help_text="MASCO occupation codes this programme leads to"
    )
```

**Step 4: Create migration**

Run: `cd halatuju_api && python manage.py makemigrations courses -n add_stpm_career_occupations`

**Step 5: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py::TestStpmCourseCareerOccupations -v`
Expected: PASS (all 3 tests)

**Step 6: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All 544+ tests pass, golden masters unchanged

**Step 7: Commit**

```bash
git add apps/courses/models.py apps/courses/migrations/
git add apps/courses/tests/test_stpm_models.py
git commit -m "feat: add career_occupations M2M to StpmCourse model"
```

---

### Task 3: Add career_occupations to STPM Detail API

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:1340-1354` (StpmCourseDetailView response)
- Test: `halatuju_api/apps/courses/tests/test_stpm_api.py` (append)

**Step 1: Write the failing test**

Add to `test_stpm_api.py` (or the file that tests STPM detail):

```python
class TestStpmCourseDetailCareerOccupations(TestCase):
    """Test career_occupations in STPM course detail endpoint."""

    def setUp(self):
        self.course = StpmCourse.objects.create(
            course_id='stpm-test-career',
            course_name='Ijazah Sarjana Muda Sains Komputer',
            university='Universiti Malaya',
        )
        StpmRequirement.objects.create(course=self.course)
        self.occ = MascoOccupation.objects.create(
            masco_code='2512-03',
            job_title='Jurutera Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-03',
        )
        self.course.career_occupations.add(self.occ)

    def test_career_occupations_included(self):
        """STPM detail should include career_occupations array."""
        resp = self.client.get(f'/api/v1/stpm/courses/{self.course.course_id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('career_occupations', data)
        self.assertEqual(len(data['career_occupations']), 1)

    def test_career_occupation_fields(self):
        """Each career occupation should have masco_code, job_title, emasco_url."""
        resp = self.client.get(f'/api/v1/stpm/courses/{self.course.course_id}/')
        occ = resp.json()['career_occupations'][0]
        self.assertEqual(occ['masco_code'], '2512-03')
        self.assertEqual(occ['job_title'], 'Jurutera Perisian')
        self.assertIn('emasco_url', occ)

    def test_empty_career_occupations(self):
        """Course with no careers should return empty array."""
        course2 = StpmCourse.objects.create(
            course_id='stpm-test-empty',
            course_name='Test Empty',
            university='UM',
        )
        StpmRequirement.objects.create(course=course2)
        resp = self.client.get(f'/api/v1/stpm/courses/{course2.course_id}/')
        self.assertEqual(resp.json()['career_occupations'], [])
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_api.py::TestStpmCourseDetailCareerOccupations -v`
Expected: FAIL — `career_occupations` not in response

**Step 3: Add career_occupations to STPM detail response**

In `halatuju_api/apps/courses/views.py`, in `StpmCourseDetailView.get()`, add after the existing response dict is built (around line 1340):

```python
from apps.courses.serializers import MascoOccupationSerializer

# Add to the response dict:
'career_occupations': MascoOccupationSerializer(
    prog.career_occupations.all(), many=True
).data,
```

**Step 4: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_api.py::TestStpmCourseDetailCareerOccupations -v`
Expected: PASS (all 3 tests)

**Step 5: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/tests/test_stpm_api.py
git commit -m "feat: include career_occupations in STPM course detail API"
```

---

### Task 4: Add career_occupations to StpmCourseDetail TypeScript type

**Files:**
- Modify: `halatuju-web/src/lib/api.ts:620` (StpmCourseDetail interface)

**Step 1: Update the interface**

In `halatuju-web/src/lib/api.ts`, add `career_occupations` to `StpmCourseDetail` interface (line ~620):

```typescript
export interface StpmCourseDetail {
  course_id: string; course_name: string; university: string;
  stream: string; field: string; category: string;
  description: string; headline: string;
  merit_score: number | null; mohe_url?: string;
  requirements: StpmRequirements;
  institution: StpmInstitutionDetail | null;
  career_occupations: MascoOccupation[];  // <-- add this
}
```

**Step 2: Verify build**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: No type errors

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/api.ts
git commit -m "feat: add career_occupations to StpmCourseDetail type"
```

---

### Task 5: Extract CareerPathways shared component

**Files:**
- Create: `halatuju-web/src/components/CareerPathways.tsx`
- Modify: `halatuju-web/src/app/course/[id]/page.tsx:106-132` (extract career section)
- Modify: `halatuju-web/src/app/stpm/[id]/page.tsx` (add career section)

**Step 1: Create the shared component**

Create `halatuju-web/src/components/CareerPathways.tsx`:

```tsx
'use client'

import { type MascoOccupation } from '@/lib/api'
import { useT } from '@/lib/i18n'

interface CareerPathwaysProps {
  occupations: MascoOccupation[]
}

export default function CareerPathways({ occupations }: CareerPathwaysProps) {
  const { t } = useT()

  if (!occupations || occupations.length === 0) return null

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-2">
        {t('courseDetail.careerPathways')}
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        {t('courseDetail.careerPathwaysDesc')}
      </p>
      <div className="flex flex-wrap gap-2">
        {occupations.map((occ) =>
          occ.emasco_url ? (
            <a
              key={occ.masco_code}
              href={occ.emasco_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium hover:bg-indigo-100 transition-colors"
            >
              {occ.job_title}
              <svg className="w-3.5 h-3.5 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          ) : (
            <span
              key={occ.masco_code}
              className="inline-flex items-center px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium"
            >
              {occ.job_title}
            </span>
          )
        )}
      </div>
    </section>
  )
}
```

**Step 2: Replace inline section in SPM course detail**

In `halatuju-web/src/app/course/[id]/page.tsx`, replace lines 106-132 (the Career Pathways section) with:

```tsx
import CareerPathways from '@/components/CareerPathways'

{/* Career Pathways */}
<CareerPathways occupations={career_occupations || []} />
```

Remove the `MascoOccupation` import from `@/lib/api` in this file if no longer used directly (the type is now used inside the component).

**Step 3: Add CareerPathways to STPM course detail**

In `halatuju-web/src/app/stpm/[id]/page.tsx`, add between the Description section and the Institution section (after line ~77, before line ~79):

```tsx
import CareerPathways from '@/components/CareerPathways'

{/* Career Pathways */}
<CareerPathways occupations={data.career_occupations || []} />
```

**Step 4: Verify build**

Run: `cd halatuju-web && npx tsc --noEmit && npm run build`
Expected: No errors

**Step 5: Verify visually (optional)**

Run: `cd halatuju-web && npm run dev`
- Check an SPM course with careers (e.g. a poly course) — should look identical to before
- Check an STPM course — should show no career section (empty array, component returns null)

**Step 6: Commit**

```bash
git add halatuju-web/src/components/CareerPathways.tsx
git add halatuju-web/src/app/course/\[id\]/page.tsx
git add halatuju-web/src/app/stpm/\[id\]/page.tsx
git commit -m "refactor: extract CareerPathways into shared component for SPM + STPM"
```

---

### Task 6: Run full test suite + update CHANGELOG

**Step 1: Run all backend tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: All tests pass (544 + new tests), golden masters unchanged

**Step 2: Run frontend build**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: No errors

**Step 3: Update CHANGELOG.md**

Add under current sprint heading:

```markdown
### MASCO Career Mappings — Sprint A (Backend Foundation)
- **Full MASCO 2020 dataset**: `load_masco_full` management command loads 4,854 occupations from CSV
- **eMASCO URLs**: Auto-generated from `kod_masco` pattern (`https://emasco.mohr.gov.my/masco/{code}`)
- **StpmCourse career_occupations**: New M2M field mirrors SPM Course model
- **STPM detail API**: Now returns `career_occupations` array (same shape as SPM)
- **CareerPathways component**: Extracted from SPM detail page into shared component used by both SPM and STPM
- No eligibility/ranking engine changes (golden masters safe)
```

**Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add MASCO Sprint A to changelog"
```

---

## Summary

| Task | What | Tests Added |
|------|------|-------------|
| 1 | Load 4,854 MASCO codes from CSV | 4 |
| 2 | StpmCourse.career_occupations M2M | 3 |
| 3 | STPM detail API returns careers | 3 |
| 4 | TypeScript type update | 0 (build check) |
| 5 | Shared CareerPathways component | 0 (visual + build) |
| 6 | Full suite + CHANGELOG | 0 |

**Total new tests:** ~10
**Files created:** 2 (management command, React component)
**Files modified:** 5 (models, views, api.ts, SPM page, STPM page)
**Migrations:** 1 (StpmCourse M2M)

**Next:** Sprint B plan covers the AI mapping pipeline (field_key→MASCO digit map, Gemini matcher, review CSV).
