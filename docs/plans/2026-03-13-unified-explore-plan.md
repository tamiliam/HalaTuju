# Unified Explore Page — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge SPM and STPM courses into a single `/search` page with a "Qualification" filter (SPM/STPM), AI-enriched STPM metadata, and a unified "Eligible only" toggle.

**Architecture:** Add `field`, `category`, `description` columns to `StpmCourse` via migration. Create a one-time Gemini batch script to classify all 1,113 STPM courses against the existing SPM field taxonomy. Extend `CourseSearchView` to query both `Course` and `StpmCourse` tables, returning a unified result set with a `qualification` discriminator. Frontend replaces `/stpm/search` with a qualification pill on `/search`.

**Tech Stack:** Django REST, Supabase PostgreSQL, Next.js 14, Google Gemini API, Pandas

**Design doc:** `docs/plans/2026-03-13-unified-explore-design.md`

---

### Task 1: Add metadata columns to StpmCourse model

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:502-524` (StpmCourse model)
- Create: `halatuju_api/apps/courses/migrations/NNNN_stpm_metadata_columns.py` (auto-generated)
- Test: `halatuju_api/apps/courses/tests/test_stpm_models.py`

**Step 1: Write the failing test**

In `test_stpm_models.py`, add a test that reads the new fields:

```python
def test_stpm_course_metadata_fields(self):
    """StpmCourse has field, category, and description columns."""
    course = StpmCourse.objects.create(
        program_id='TEST-META-001',
        program_name='Test Programme',
        university='Test University',
        stream='science',
        field='Engineering',
        category='Kejuruteraan',
        description='A test programme in engineering.',
    )
    course.refresh_from_db()
    self.assertEqual(course.field, 'Engineering')
    self.assertEqual(course.category, 'Kejuruteraan')
    self.assertEqual(course.description, 'A test programme in engineering.')

def test_stpm_course_metadata_defaults_blank(self):
    """Metadata fields default to empty string."""
    course = StpmCourse.objects.create(
        program_id='TEST-META-002',
        program_name='Test Programme 2',
        university='Test University',
    )
    self.assertEqual(course.field, '')
    self.assertEqual(course.category, '')
    self.assertEqual(course.description, '')
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/courses/tests/test_stpm_models.py::StpmCourseModelTest::test_stpm_course_metadata_fields -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'field'`

**Step 3: Add columns to StpmCourse model**

In `halatuju_api/apps/courses/models.py`, add to `StpmCourse` class (after `merit_score`):

```python
field = models.CharField(max_length=255, blank=True, default='', help_text='AI-assigned field category')
category = models.CharField(max_length=255, blank=True, default='', help_text='AI-assigned category (Malay)')
description = models.TextField(blank=True, default='', help_text='AI-generated programme description')
```

**Step 4: Generate and apply migration**

Run:
```bash
cd halatuju_api
python manage.py makemigrations courses --name stpm_metadata_columns
python manage.py migrate
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest apps/courses/tests/test_stpm_models.py -v`
Expected: PASS

**Step 6: Apply migration to Supabase**

Use `mcp__claude_ai_Supabase__apply_migration` to add the three columns:

```sql
ALTER TABLE stpm_courses
ADD COLUMN field VARCHAR(255) NOT NULL DEFAULT '',
ADD COLUMN category VARCHAR(255) NOT NULL DEFAULT '',
ADD COLUMN description TEXT NOT NULL DEFAULT '';
```

Then run Security Advisor to verify 0 errors.

**Step 7: Commit**

```bash
git add apps/courses/models.py apps/courses/migrations/*stpm_metadata* apps/courses/tests/test_stpm_models.py
git commit -m "feat: add field/category/description columns to StpmCourse"
```

---

### Task 2: AI metadata enrichment script

**Files:**
- Create: `halatuju_api/apps/courses/management/commands/enrich_stpm_metadata.py`
- Reference: `halatuju_api/apps/courses/models.py` (StpmCourse)
- Reference: existing SPM field list from `Course.frontend_label` values

**Step 1: Get the existing SPM field taxonomy**

Run: `python manage.py shell -c "from apps.courses.models import Course; print(sorted(set(Course.objects.exclude(frontend_label='').values_list('frontend_label', flat=True))))"` to get the ~30 categories.

**Step 2: Write the enrichment management command**

Create `enrich_stpm_metadata.py`:

```python
"""
One-time Gemini batch job to classify STPM courses.

Usage:
    python manage.py enrich_stpm_metadata          # Dry run (print, don't save)
    python manage.py enrich_stpm_metadata --save    # Save to DB
    python manage.py enrich_stpm_metadata --save --batch-size 20  # Custom batch size
    python manage.py enrich_stpm_metadata --only-empty --save     # Skip already-classified
"""
import json
import os
import time

from django.core.management.base import BaseCommand
from apps.courses.models import Course, StpmCourse

import google.generativeai as genai


class Command(BaseCommand):
    help = 'Classify STPM courses with field/category/description using Gemini'

    def add_arguments(self, parser):
        parser.add_argument('--save', action='store_true', help='Save results to DB')
        parser.add_argument('--batch-size', type=int, default=25, help='Courses per Gemini call')
        parser.add_argument('--only-empty', action='store_true', help='Skip courses with existing field')

    def handle(self, *args, **options):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            self.stderr.write('GEMINI_API_KEY not set')
            return

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Get existing SPM field taxonomy
        spm_fields = sorted(set(
            Course.objects.exclude(frontend_label='')
            .values_list('frontend_label', flat=True)
        ))
        self.stdout.write(f'SPM field taxonomy ({len(spm_fields)} categories): {spm_fields}')

        # Get STPM courses to classify
        qs = StpmCourse.objects.all().order_by('program_id')
        if options['only_empty']:
            qs = qs.filter(field='')
        courses = list(qs.values_list('program_id', 'program_name', 'university', 'stream'))
        self.stdout.write(f'Courses to classify: {len(courses)}')

        batch_size = options['batch_size']
        updated = 0

        for i in range(0, len(courses), batch_size):
            batch = courses[i:i + batch_size]
            course_list = '\n'.join(
                f'- {pid}: {name} ({uni}, {stream})'
                for pid, name, uni, stream in batch
            )

            prompt = f"""You are classifying Malaysian university degree programmes.

Existing field categories (use these first, add new ones only if no existing category fits):
{json.dumps(spm_fields, ensure_ascii=False)}

For each programme below, return a JSON array with one object per programme:
- "program_id": the ID exactly as given
- "field": best matching field from the list above, or a new category if none fits (in English)
- "category": the field name in Malay
- "description": 1-2 sentence description of what the programme covers (in English)

Programmes:
{course_list}

Return ONLY valid JSON array, no markdown fences."""

            try:
                response = model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                results = json.loads(text)

                for item in results:
                    pid = item.get('program_id', '')
                    if options['save']:
                        StpmCourse.objects.filter(program_id=pid).update(
                            field=item.get('field', ''),
                            category=item.get('category', ''),
                            description=item.get('description', ''),
                        )
                    else:
                        self.stdout.write(f"  {pid}: field={item.get('field')}")
                    updated += 1

            except Exception as e:
                self.stderr.write(f'Batch {i // batch_size} failed: {e}')
                # Continue with next batch

            if i + batch_size < len(courses):
                time.sleep(2)  # Rate limit

        self.stdout.write(f'Done. {updated} courses {"saved" if options["save"] else "previewed"}.')
```

**Step 3: Test the command locally (dry run)**

Run: `python manage.py enrich_stpm_metadata --batch-size 5`
Expected: Prints field assignments for 5 courses without saving.

**Step 4: Run with --save to populate DB**

Run: `python manage.py enrich_stpm_metadata --save`
Expected: All 1,113 courses classified and saved.

**Step 5: Review results**

Run: `python manage.py shell -c "from apps.courses.models import StpmCourse; print(StpmCourse.objects.exclude(field='').count())"` — should be ~1,113.

Check for new categories: `python manage.py shell -c "from apps.courses.models import StpmCourse; print(sorted(set(StpmCourse.objects.values_list('field', flat=True))))"`

**Step 6: Sync to Supabase**

Use Supabase MCP to batch-update the `field`, `category`, `description` columns. Generate SQL UPDATE batches from the local DB values.

**Step 7: Commit**

```bash
git add apps/courses/management/commands/enrich_stpm_metadata.py
git commit -m "feat: add Gemini enrichment script for STPM course metadata"
```

---

### Task 3: Unified search backend endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:56-186` (CourseSearchView)
- Test: `halatuju_api/apps/courses/tests/test_api.py` (add unified search tests)

**Step 1: Write failing tests for unified search**

Add to `test_api.py`:

```python
def test_search_returns_both_spm_and_stpm(self):
    """Search with no qualification filter returns both SPM and STPM courses."""
    response = self.client.get('/api/v1/courses/search/')
    self.assertEqual(response.status_code, 200)
    qualifications = {c['qualification'] for c in response.data['courses']}
    self.assertIn('SPM', qualifications)
    self.assertIn('STPM', qualifications)

def test_search_qualification_filter_spm(self):
    """qualification=SPM returns only SPM courses."""
    response = self.client.get('/api/v1/courses/search/?qualification=SPM')
    self.assertEqual(response.status_code, 200)
    for course in response.data['courses']:
        self.assertEqual(course['qualification'], 'SPM')

def test_search_qualification_filter_stpm(self):
    """qualification=STPM returns only STPM courses."""
    response = self.client.get('/api/v1/courses/search/?qualification=STPM')
    self.assertEqual(response.status_code, 200)
    for course in response.data['courses']:
        self.assertEqual(course['qualification'], 'STPM')

def test_search_stpm_has_course_card_fields(self):
    """STPM courses in unified search have all CourseCard fields."""
    response = self.client.get('/api/v1/courses/search/?qualification=STPM')
    self.assertEqual(response.status_code, 200)
    if response.data['courses']:
        course = response.data['courses'][0]
        self.assertIn('course_id', course)
        self.assertIn('course_name', course)
        self.assertIn('level', course)
        self.assertIn('field', course)
        self.assertIn('source_type', course)
        self.assertIn('merit_cutoff', course)
        self.assertIn('institution_count', course)
        self.assertIn('institution_name', course)
        self.assertIn('qualification', course)

def test_search_text_filter_across_qualifications(self):
    """Text search finds matches in both SPM and STPM."""
    response = self.client.get('/api/v1/courses/search/?q=kejuruteraan')
    self.assertEqual(response.status_code, 200)
    self.assertGreater(response.data['total_count'], 0)

def test_search_filters_include_qualification(self):
    """Filter metadata includes qualification options."""
    response = self.client.get('/api/v1/courses/search/')
    self.assertEqual(response.status_code, 200)
    self.assertIn('qualifications', response.data['filters'])
    self.assertIn('SPM', response.data['filters']['qualifications'])
    self.assertIn('STPM', response.data['filters']['qualifications'])

def test_search_field_filter_works_for_stpm(self):
    """Field filter works for STPM courses (AI-assigned field)."""
    # First get an STPM course's field
    response = self.client.get('/api/v1/courses/search/?qualification=STPM&limit=1')
    if response.data['courses']:
        field = response.data['courses'][0]['field']
        if field:
            response2 = self.client.get(f'/api/v1/courses/search/?field={field}')
            self.assertEqual(response2.status_code, 200)

def test_search_total_count_includes_both(self):
    """total_count reflects combined result set."""
    resp_all = self.client.get('/api/v1/courses/search/')
    resp_spm = self.client.get('/api/v1/courses/search/?qualification=SPM')
    resp_stpm = self.client.get('/api/v1/courses/search/?qualification=STPM')
    self.assertEqual(
        resp_all.data['total_count'],
        resp_spm.data['total_count'] + resp_stpm.data['total_count'],
    )
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/courses/tests/test_api.py -k "qualification" -v`
Expected: FAIL — no `qualification` field in response, no STPM courses in results.

**Step 3: Implement unified search in CourseSearchView**

Modify `CourseSearchView.get()` in `views.py` to:

1. Accept `qualification` query param (`SPM`, `STPM`, or empty for both)
2. Query `Course` table for SPM results (existing logic)
3. Query `StpmCourse` table for STPM results
4. Map STPM fields to CourseCard shape:
   - `course_id` ← `program_id`
   - `course_name` ← `program_name`
   - `level` ← `"Ijazah Sarjana Muda"` (hardcoded)
   - `field` ← `StpmCourse.field` (AI-assigned)
   - `source_type` ← `"University"` (hardcoded)
   - `merit_cutoff` ← `merit_score`
   - `institution_count` ← `1`
   - `institution_name` ← `university`
   - `institution_state` ← `""` (derive later)
   - `qualification` ← `"STPM"`
5. Add `qualification: "SPM"` to all existing SPM results
6. Merge both lists, apply text/field filters across both
7. Paginate across combined set
8. Add `qualifications: ["SPM", "STPM"]` to filters response

```python
def get(self, request):
    qualification = request.query_params.get('qualification', '').strip().upper()
    q = request.query_params.get('q', '').strip()
    level = request.query_params.get('level', '').strip()
    field = request.query_params.get('field', '').strip()
    source_type = request.query_params.get('source_type', '').strip()
    state = request.query_params.get('state', '').strip()

    try:
        limit = min(int(request.query_params.get('limit', 24)), 100)
    except (ValueError, TypeError):
        limit = 24
    try:
        offset = max(int(request.query_params.get('offset', 0)), 0)
    except (ValueError, TypeError):
        offset = 0

    results = []
    spm_count = 0
    stpm_count = 0

    # --- SPM courses ---
    if qualification in ('', 'SPM'):
        spm_qs = Course.objects.select_related('requirement').all()
        if q:
            spm_qs = spm_qs.filter(course__icontains=q)
        if level:
            spm_qs = spm_qs.filter(level__iexact=level)
        if field:
            spm_qs = spm_qs.filter(frontend_label__iexact=field)
        if source_type:
            spm_qs = spm_qs.filter(requirement__source_type=source_type)
        if state:
            spm_qs = spm_qs.filter(offerings__institution__state__iexact=state).distinct()

        spm_count = spm_qs.count()

        # Subquery for primary institution
        first_offering = CourseInstitution.objects.filter(
            course=OuterRef('pk')
        ).order_by('institution__institution_name')

        spm_courses = list(spm_qs.annotate(
            institution_count=Count('offerings'),
            primary_institution_name=Subquery(
                first_offering.values('institution__institution_name')[:1]
            ),
            primary_institution_state=Subquery(
                first_offering.values('institution__state')[:1]
            ),
        ).order_by('course'))

        for c in spm_courses:
            req = getattr(c, 'requirement', None)
            st = req.source_type if req else 'poly'
            merit_cutoff = req.merit_cutoff if req else None
            results.append({
                'course_id': c.course_id,
                'course_name': c.course,
                'level': c.level,
                'field': c.frontend_label or c.field,
                'source_type': st,
                'merit_cutoff': merit_cutoff,
                'institution_count': c.institution_count,
                'institution_name': c.primary_institution_name or '',
                'institution_state': c.primary_institution_state or '',
                'qualification': 'SPM',
            })

    # --- STPM courses ---
    if qualification in ('', 'STPM'):
        stpm_qs = StpmCourse.objects.all()
        # Exclude bumiputera-only (UiTM) at runtime
        stpm_qs = stpm_qs.exclude(
            requirement__req_bumiputera=True
        )
        if q:
            stpm_qs = stpm_qs.filter(program_name__icontains=q)
        if field:
            stpm_qs = stpm_qs.filter(field__iexact=field)
        # level filter: STPM is always "Ijazah Sarjana Muda", skip if filter doesn't match
        if level and level.lower() != 'ijazah sarjana muda':
            stpm_count = 0
        else:
            # source_type filter: STPM is always "University", skip if filter doesn't match
            if source_type and source_type.lower() != 'university':
                stpm_count = 0
            else:
                stpm_count = stpm_qs.count()

                for prog in stpm_qs.order_by('university', 'program_name'):
                    results.append({
                        'course_id': prog.program_id,
                        'course_name': prog.program_name,
                        'level': 'Ijazah Sarjana Muda',
                        'field': prog.field,
                        'source_type': 'University',
                        'merit_cutoff': prog.merit_score,
                        'institution_count': 1,
                        'institution_name': prog.university,
                        'institution_state': '',
                        'qualification': 'STPM',
                    })

    total_count = spm_count + stpm_count

    # Sort: qualification-agnostic, credential > source_type > merit > name
    SOURCE_TYPE_ORDER = {'University': 5, 'ua': 4, 'pismp': 3, 'poly': 2, 'kkom': 1, 'tvet': 0}
    results.sort(key=lambda r: (
        -get_credential_priority(r['course_name'], r.get('source_type', '')),
        -SOURCE_TYPE_ORDER.get(r['source_type'], 0),
        -(r['merit_cutoff'] or 0),
        r['course_name'],
    ))

    # Paginate combined results
    paginated = results[offset:offset + limit]

    # Build filters from full DB
    filters = {
        'levels': sorted(set(
            list(Course.objects.values_list('level', flat=True).distinct()) +
            ['Ijazah Sarjana Muda']
        )),
        'fields': sorted(set(
            list(Course.objects.exclude(frontend_label='')
                .values_list('frontend_label', flat=True).distinct()) +
            list(StpmCourse.objects.exclude(field='')
                .values_list('field', flat=True).distinct())
        )),
        'source_types': sorted(set(
            list(CourseRequirement.objects.values_list('source_type', flat=True).distinct()) +
            ['University']
        )),
        'states': sorted(
            Institution.objects.exclude(state='')
            .values_list('state', flat=True)
            .distinct().order_by('state')
        ),
        'qualifications': ['SPM', 'STPM'],
    }

    return Response({
        'courses': paginated,
        'total_count': total_count,
        'filters': filters,
    })
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/courses/tests/test_api.py -k "search" -v`
Expected: All search tests PASS (existing + new).

**Step 5: Run full test suite to check for regressions**

Run: `python -m pytest apps/courses/tests/ -v`
Expected: 293+ tests pass, golden masters unchanged (8283 SPM, 1811 STPM).

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/tests/test_api.py
git commit -m "feat: unified search endpoint returning both SPM and STPM courses"
```

---

### Task 4: Eligible toggle with STPM fallback

**Files:**
- Modify: `halatuju_api/apps/courses/views.py` (EligibilityCheckView or CourseSearchView)
- Modify: `halatuju-web/src/app/search/page.tsx`
- Modify: `halatuju-web/src/lib/api.ts`
- Test: `halatuju_api/apps/courses/tests/test_api.py`

**Step 1: Write failing tests**

```python
def test_search_eligible_stpm_first(self):
    """Eligible toggle checks STPM eligibility when STPM grades exist."""
    # POST with STPM grades → returns eligible STPM programme IDs
    response = self.client.post('/api/v1/courses/search/eligible/', {
        'stpm_grades': {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'B'},
        'spm_grades': {'BM': 'A', 'BI': 'A', 'SEJ': 'B+', 'MAT': 'A'},
        'cgpa': 3.5,
        'muet_band': 4,
        'gender': 'male',
        'nationality': 'malaysian',
    }, format='json')
    self.assertEqual(response.status_code, 200)
    self.assertIn('eligible_ids', response.data)
    # Should include STPM programme IDs
    quals = {item['qualification'] for item in response.data['eligible_ids']}
    self.assertIn('STPM', quals)

def test_search_eligible_spm_fallback(self):
    """Eligible toggle falls back to SPM when no STPM grades."""
    response = self.client.post('/api/v1/courses/search/eligible/', {
        'spm_grades': {'BM': 'A', 'BI': 'A', 'SEJ': 'B+', 'MAT': 'A'},
        'gender': 'male',
        'nationality': 'malaysian',
    }, format='json')
    self.assertEqual(response.status_code, 200)
    self.assertIn('eligible_ids', response.data)
    quals = {item['qualification'] for item in response.data['eligible_ids']}
    self.assertIn('SPM', quals)
    self.assertNotIn('STPM', quals)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/courses/tests/test_api.py::CourseSearchTest::test_search_eligible_stpm_first -v`
Expected: FAIL — endpoint doesn't exist.

**Step 3: Implement eligible endpoint**

Add a new `UnifiedEligibleView` at `/api/v1/courses/search/eligible/`:

```python
class UnifiedEligibleView(APIView):
    """
    POST /api/v1/courses/search/eligible/
    Returns eligible course/programme IDs for the "Eligible only" toggle.
    Checks STPM first if STPM grades present, falls back to SPM.
    """

    def post(self, request):
        eligible_ids = []

        stpm_grades = request.data.get('stpm_grades')
        spm_grades = request.data.get('spm_grades', {})
        cgpa = request.data.get('cgpa')
        muet_band = request.data.get('muet_band')

        # Check STPM eligibility if STPM grades exist
        if stpm_grades and cgpa is not None:
            stpm_results = check_stpm_eligibility(
                stpm_grades=stpm_grades,
                spm_grades=spm_grades,
                cgpa=float(cgpa),
                muet_band=int(muet_band or 1),
                gender=request.data.get('gender', ''),
                nationality=request.data.get('nationality', 'malaysian'),
                colorblind=request.data.get('colorblind', False),
            )
            for prog in stpm_results:
                eligible_ids.append({
                    'course_id': prog['program_id'],
                    'qualification': 'STPM',
                })

        # Always check SPM eligibility (SPM grades from profile)
        if spm_grades:
            # Use existing eligibility engine
            serializer = EligibilityRequestSerializer(data=request.data)
            if serializer.is_valid():
                student = EngineStudentProfile(**serializer.validated_data)
                config = apps.get_app_config('courses')
                df = config.requirements_df

                for _, row in df.iterrows():
                    eligible, _ = check_eligibility(student, row.to_dict())
                    if eligible:
                        eligible_ids.append({
                            'course_id': row['course_id'],
                            'qualification': 'SPM',
                        })

        return Response({'eligible_ids': eligible_ids})
```

Wire up the URL in `urls.py`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/courses/tests/test_api.py -k "eligible" -v`
Expected: PASS

**Step 5: Update frontend search page**

In `halatuju-web/src/app/search/page.tsx`, modify the "Eligible only" toggle handler:
- When toggled on, POST to `/api/v1/courses/search/eligible/` with STPM grades (from profile) first, SPM grades as fallback
- Filter displayed cards to only show IDs in the response

In `halatuju-web/src/lib/api.ts`, add:

```typescript
export interface EligibleItem {
  course_id: string
  qualification: 'SPM' | 'STPM'
}

export async function getEligibleCourses(grades: {
  stpm_grades?: Record<string, string>
  spm_grades?: Record<string, string>
  cgpa?: number
  muet_band?: number
  gender?: string
  nationality?: string
}): Promise<EligibleItem[]> {
  const response = await apiClient.post('/api/v1/courses/search/eligible/', grades)
  return response.data.eligible_ids
}
```

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_api.py
git commit -m "feat: unified eligible endpoint with STPM-first, SPM-fallback logic"
```

---

### Task 5: Frontend — qualification filter pill and CourseCard mapping

**Files:**
- Modify: `halatuju-web/src/app/search/page.tsx`
- Modify: `halatuju-web/src/lib/api.ts` (SearchCourse interface)
- Modify: `halatuju-web/src/components/CourseCard.tsx` (if needed for qualification badge)

**Step 1: Update SearchCourse interface**

In `api.ts`, add `qualification` field:

```typescript
export interface SearchCourse {
  course_id: string
  course_name: string
  level: string
  field: string
  source_type: string
  merit_cutoff: number | null
  institution_count: number
  institution_name: string
  institution_state: string
  qualification: 'SPM' | 'STPM'  // NEW
}
```

**Step 2: Add SearchFilters qualification**

```typescript
export interface SearchFilters {
  levels: string[]
  fields: string[]
  source_types: string[]
  states: string[]
  qualifications: string[]  // NEW
}
```

**Step 3: Add qualification filter pill to search page**

In `search/page.tsx`, add a new filter pill alongside existing Level, Field, Type, State pills:

```tsx
{/* Qualification filter */}
<div className="flex gap-2">
  {filters.qualifications?.map(qual => (
    <button
      key={qual}
      onClick={() => setQualification(qualification === qual ? '' : qual)}
      className={`px-3 py-1 rounded-full text-sm ${
        qualification === qual
          ? 'bg-blue-600 text-white'
          : 'bg-gray-100 text-gray-700'
      }`}
    >
      {qual}
    </button>
  ))}
</div>
```

Add `qualification` to the search params sent to the API.

**Step 4: Add qualification badge to CourseCard**

In `CourseCard.tsx`, show a small "SPM" or "STPM" badge next to the type badge:

```tsx
{course.qualification && (
  <span className={`text-xs px-2 py-0.5 rounded ${
    course.qualification === 'STPM'
      ? 'bg-purple-100 text-purple-700'
      : 'bg-blue-100 text-blue-700'
  }`}>
    {course.qualification}
  </span>
)}
```

**Step 5: Handle STPM course card clicks**

STPM cards link to `/stpm/${course.course_id}` (existing detail page).
SPM cards link to `/courses/${course.course_id}` (existing detail page).

In the card's `Link` component, route based on qualification:

```tsx
const detailUrl = course.qualification === 'STPM'
  ? `/stpm/${course.course_id}`
  : `/courses/${course.course_id}`
```

**Step 6: Commit**

```bash
git add halatuju-web/src/app/search/page.tsx halatuju-web/src/lib/api.ts halatuju-web/src/components/CourseCard.tsx
git commit -m "feat: qualification filter pill and STPM cards in unified search"
```

---

### Task 6: Remove /stpm/search and add redirect

**Files:**
- Modify: `halatuju-web/src/app/stpm/search/page.tsx` (replace with redirect)
- Test: manual browser test

**Step 1: Replace STPM search page with redirect**

Replace the entire content of `halatuju-web/src/app/stpm/search/page.tsx` with:

```tsx
import { redirect } from 'next/navigation'

export default function StpmSearchRedirect() {
  redirect('/search?qualification=STPM')
}
```

**Step 2: Verify redirect works**

Run the Next.js dev server and navigate to `/stpm/search` — should redirect to `/search?qualification=STPM`.

**Step 3: Commit**

```bash
git add halatuju-web/src/app/stpm/search/page.tsx
git commit -m "feat: redirect /stpm/search to /search?qualification=STPM"
```

---

### Task 7: Add i18n keys for qualification filter

**Files:**
- Modify: `halatuju-web/src/lib/i18n.ts` (or equivalent i18n file)

**Step 1: Identify the i18n file**

Find the translations file and add keys for:
- `filter.qualification` → "Qualification" / "Kelayakan" / "தகுதி"
- `filter.qualification.all` → "All" / "Semua" / "அனைத்தும்"
- `badge.spm` → "SPM"
- `badge.stpm` → "STPM"

**Step 2: Add translations**

Add to each language block (en, ms, ta).

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/i18n.ts
git commit -m "feat: add i18n keys for qualification filter (3 languages)"
```

---

### Task 8: Update STPM search tests for unified endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_stpm_search.py`

**Step 1: Update tests to use unified endpoint**

The existing STPM search tests at `/api/v1/stpm/search/` should still work (keep `StpmSearchView` as a legacy endpoint for now, or update tests to use `/api/v1/courses/search/?qualification=STPM`).

Decision: Keep `StpmSearchView` as-is for backward compatibility. The frontend just stops using it. No test changes needed.

**Step 2: Run full test suite**

Run: `python -m pytest apps/courses/tests/ -v`
Expected: All 293+ tests pass. Golden masters unchanged (8283 SPM, 1811 STPM).

**Step 3: Commit (if any test updates needed)**

```bash
git commit -m "test: verify unified search doesn't break existing STPM search tests"
```

---

### Task 9: End-to-end verification and deploy

**Files:**
- No code changes — deployment and verification only.

**Step 1: Run full test suite locally**

Run: `python -m pytest apps/courses/tests/ -v`
Expected: All tests pass, golden masters intact.

**Step 2: Deploy backend to Cloud Run (tagged)**

```bash
cd halatuju_api
gcloud run deploy halatuju-api --source . --region asia-southeast1 --project gen-lang-client-0871147736 --account tamiliam@gmail.com --tag unified --no-traffic
```

**Step 3: Deploy frontend to Cloud Run (tagged)**

```bash
cd halatuju-web
gcloud run deploy halatuju-web --source . --region asia-southeast1 --project gen-lang-client-0871147736 --account tamiliam@gmail.com --tag unified --no-traffic
```

**Step 4: E2E verification on tagged URL**

- Open tagged frontend URL
- Verify `/search` shows both SPM and STPM courses
- Verify qualification filter pills work
- Verify text search finds courses across both qualifications
- Verify "Eligible only" toggle works (STPM first, SPM fallback)
- Verify STPM cards use CourseCard layout with correct field mapping
- Verify `/stpm/search` redirects to `/search?qualification=STPM`
- Verify STPM card clicks go to `/stpm/<id>` detail page

**Step 5: Route traffic**

Once verified:
```bash
gcloud run services update-traffic halatuju-api --to-latest --region asia-southeast1 --project gen-lang-client-0871147736 --account tamiliam@gmail.com
gcloud run services update-traffic halatuju-web --to-latest --region asia-southeast1 --project gen-lang-client-0871147736 --account tamiliam@gmail.com
```

**Step 6: Final commit + tag**

```bash
git tag -a v1.34.0 -m "Unified explore page: SPM + STPM merged search"
```

---

## Dependency Graph

```
Task 1 (StpmCourse columns) ──→ Task 2 (AI enrichment) ──→ Task 3 (Unified search endpoint)
                                                              │
                                              ┌───────────────┼───────────────┐
                                              ▼               ▼               ▼
                                         Task 4          Task 5          Task 6
                                      (Eligible)    (Frontend pills)   (Redirect)
                                              │               │
                                              └───────┬───────┘
                                                      ▼
                                                 Task 7 (i18n)
                                                      │
                                                      ▼
                                                 Task 8 (Tests)
                                                      │
                                                      ▼
                                                 Task 9 (Deploy)
```

Tasks 4, 5, 6 can be done in parallel after Task 3.
