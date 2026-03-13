# STPM Sprint 6 — Merit Scoring + UX Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add UPU merit scoring (High/Fair/Low) to STPM programmes using real purata markah merit data, fix the CGPA formula, fix the zero-courses bug, and polish the grade entry page UX.

**Architecture:** Load merit percentages from existing source CSVs into a new `merit_score` field on StpmCourse. Backend exposes merit in eligibility/ranking responses. Frontend converts student CGPA to merit % and compares against course merit to classify High/Fair/Low. Grade page UX fixes are frontend-only.

**Tech Stack:** Django (migration, model, loader, engine), Next.js 14 (grade page, dashboard cards)

**Baseline:** 320 tests (287 pass, 9 JWT failures), SPM GM: 8283, STPM GM: 1811

---

## Task Overview

| Task | What | Files |
|------|------|-------|
| 1 | Add `merit_score` field to StpmCourse model + migration | models.py, migration |
| 2 | Load merit data from source CSVs | load_stpm_data.py |
| 3 | Expose merit in eligibility + ranking API responses | stpm_engine.py, stpm_ranking.py, views.py |
| 4 | Fix CGPA formula: koko 0-10 scale, merit % conversion | stpm-grades/page.tsx, stpm.ts |
| 5 | Fix zero-courses bug on dashboard | dashboard/page.tsx |
| 6 | Add merit traffic lights to STPM course cards | dashboard/page.tsx |
| 7 | Elective follows SPM "Add" button pattern | stpm-grades/page.tsx |
| 8 | ICT stream fix + subject dedup in dropdowns | subjects.ts |
| 9 | i18n + final polish | en.json, ms.json, ta.json |

---

### Task 1: Add `merit_score` field to StpmCourse model

**Files:**
- Modify: `halatuju_api/apps/courses/models.py:502-524`
- Create: `halatuju_api/apps/courses/migrations/0014_stpmcourse_merit_score.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_models.py`

**Step 1: Write the failing test**

```python
# In test_stpm_models.py, add:
def test_stpm_course_merit_score(self):
    """StpmCourse stores merit_score as nullable float."""
    course = StpmCourse.objects.create(
        program_id='MERIT001',
        program_name='Test Merit Programme',
        university='Test University',
        stream='science',
        merit_score=96.04,
    )
    course.refresh_from_db()
    assert course.merit_score == 96.04

def test_stpm_course_merit_score_null(self):
    """StpmCourse merit_score can be null (Tiada)."""
    course = StpmCourse.objects.create(
        program_id='MERIT002',
        program_name='No Merit Programme',
        university='Test University',
        stream='arts',
    )
    course.refresh_from_db()
    assert course.merit_score is None
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py -v -k "merit"`
Expected: FAIL — `merit_score` field doesn't exist

**Step 3: Add field to model + run migration**

In `models.py`, inside `class StpmCourse`, add after `stream`:
```python
merit_score = models.FloatField(null=True, blank=True, help_text='UPU average merit percentage (0-100)')
```

Then:
```bash
cd halatuju_api && python manage.py makemigrations courses --name stpmcourse_merit_score
```

**Step 4: Run test to verify it passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_models.py -v -k "merit"`
Expected: PASS

**Step 5: Run golden masters to confirm no regression**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_golden_master.py apps/courses/tests/test_golden_master.py -v`
Expected: PASS (8283 + 1811)

**Step 6: Commit**

```bash
git add apps/courses/models.py apps/courses/migrations/0014_*.py apps/courses/tests/test_stpm_models.py
git commit -m "feat: add merit_score field to StpmCourse model"
```

---

### Task 2: Load merit data from source CSVs

**Files:**
- Modify: `halatuju_api/apps/courses/management/commands/load_stpm_data.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_data_loading.py`

**Context:** The merit data lives in the **original source CSVs** (not the parsed ones):
- `C:\Users\tamil\Python\Archived\Random\data\stpm_science\mohe_programs_merged.csv`
- `C:\Users\tamil\Python\Archived\Random\data\stpm_arts\mohe_programs_merged.csv`

Column `merit` has values like `99.43%`, `83.61%`, or `Tiada`. Column `code` = `program_id`.

1,113 unique program_ids, 1,080 have numeric merit, 33 have "Tiada".

**Step 1: Write the failing test**

```python
# In test_stpm_data_loading.py, add:
def test_merit_score_loaded(self):
    """Merit scores are loaded from source CSVs."""
    from apps.courses.models import StpmCourse
    # After loader runs, check a course has merit
    courses_with_merit = StpmCourse.objects.filter(merit_score__isnull=False)
    assert courses_with_merit.count() > 0

def test_merit_score_tiada_is_null(self):
    """Programmes with 'Tiada' merit have null merit_score."""
    from apps.courses.models import StpmCourse
    # Some courses should have null merit
    courses_without_merit = StpmCourse.objects.filter(merit_score__isnull=True)
    assert courses_without_merit.exists()
```

**Step 2: Implement merit loading**

Strategy: Add a `--merit` flag or a second pass in the loader that reads the merged CSVs and updates `merit_score` by `program_id`.

In `load_stpm_data.py`, add a new method `_load_merit_data(self)`:

```python
def _load_merit_data(self):
    """Load UPU merit percentages from source merged CSVs."""
    import os
    merit_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'stpm')
    merit_files = [
        os.path.join(merit_dir, 'stpm_science_merit.csv'),
        os.path.join(merit_dir, 'stpm_arts_merit.csv'),
    ]
    updated = 0
    for filepath in merit_files:
        if not os.path.exists(filepath):
            self.stdout.write(self.style.WARNING(f'Merit file not found: {filepath}'))
            continue
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                program_id = row.get('program_id', '').strip()
                merit_raw = row.get('merit', '').strip()
                if not program_id:
                    continue
                merit_val = None
                if merit_raw and merit_raw != 'Tiada':
                    try:
                        merit_val = float(merit_raw.replace('%', ''))
                    except ValueError:
                        pass
                StpmCourse.objects.filter(program_id=program_id).update(merit_score=merit_val)
                updated += 1
    self.stdout.write(self.style.SUCCESS(f'Updated {updated} merit scores'))
```

Call `self._load_merit_data()` at the end of `handle()`.

**Step 3: Create slim merit CSV files**

Extract just `program_id,merit` from the source merged CSVs into:
- `halatuju_api/data/stpm/stpm_science_merit.csv`
- `halatuju_api/data/stpm/stpm_arts_merit.csv`

Script to generate (run once):
```python
import csv
for stream in ['science', 'arts']:
    src = f'C:/Users/tamil/Python/Archived/Random/data/stpm_{stream}/mohe_programs_merged.csv'
    dst = f'halatuju_api/data/stpm/stpm_{stream}_merit.csv'
    with open(src) as fin, open(dst, 'w', newline='') as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=['program_id', 'merit'])
        writer.writeheader()
        for row in reader:
            writer.writerow({'program_id': row['code'], 'merit': row['merit']})
```

**Step 4: Run loader + tests**

```bash
cd halatuju_api && python manage.py load_stpm_data
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_data_loading.py -v -k "merit"
```

**Step 5: Verify merit counts in DB**

```bash
cd halatuju_api && python manage.py shell -c "
from apps.courses.models import StpmCourse
total = StpmCourse.objects.count()
with_merit = StpmCourse.objects.filter(merit_score__isnull=False).count()
print(f'{with_merit}/{total} courses have merit scores')
"
```
Expected: `1080/1113 courses have merit scores`

**Step 6: Run golden masters**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_golden_master.py apps/courses/tests/test_golden_master.py -v`
Expected: PASS (8283 + 1811 unchanged — merit is data-only, doesn't affect eligibility logic)

**Step 7: Commit**

```bash
git add apps/courses/management/commands/load_stpm_data.py apps/courses/tests/test_stpm_data_loading.py data/stpm/stpm_*_merit.csv
git commit -m "feat: load UPU merit scores for STPM programmes (1080/1113)"
```

---

### Task 3: Expose merit in eligibility + ranking API responses

**Files:**
- Modify: `halatuju_api/apps/courses/stpm_engine.py:242-251`
- Modify: `halatuju_api/apps/courses/stpm_ranking.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_engine.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_api.py`

**Step 1: Write the failing test**

```python
# In test_stpm_engine.py, add:
def test_eligible_programme_includes_merit(self):
    """Eligible programmes include merit_score field."""
    results = check_stpm_eligibility(
        stpm_grades={'PA': 'A', 'MATH_T': 'A', 'PHYSICS': 'A', 'CHEMISTRY': 'A'},
        spm_grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A'},
        cgpa=3.8, muet_band=5,
    )
    assert len(results) > 0
    # merit_score should be present (may be None for some)
    assert 'merit_score' in results[0]
```

**Step 2: Add merit_score to eligibility response**

In `stpm_engine.py`, line ~245, where the eligible programme dict is built, add:
```python
'merit_score': course.merit_score,  # UPU average merit % (nullable)
```

**Step 3: Run test**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_engine.py -v -k "merit"`
Expected: PASS

**Step 4: Run golden master**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_golden_master.py -v`
Expected: PASS (1811 unchanged — new field is data-only)

**Step 5: Commit**

```bash
git add apps/courses/stpm_engine.py apps/courses/stpm_ranking.py apps/courses/tests/test_stpm_engine.py
git commit -m "feat: expose merit_score in STPM eligibility and ranking API responses"
```

---

### Task 4: Fix CGPA formula — koko 0-10 scale + merit % conversion

**Files:**
- Modify: `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`
- Modify: `halatuju-web/src/lib/stpm.ts`

**Changes:**

1. **Co-curriculum input**: Change max from 4.0 to 10.0, placeholder from `0.00 – 4.00` to `0.00 – 10.00`
2. **CGPA formula**: `overallCgpa = (academicCgpa × 0.9) + (kokoScore / 10 × 4.0 × 0.1)` = `(academic × 0.9) + (koko × 0.04)`. Max: 3.60 + 0.40 = 4.00
3. **Merit % conversion** (new export in `stpm.ts`): `studentMerit = (overallCgpa / 4.0) × 100`

**Step 1: Update stpm.ts — add merit conversion**

```typescript
// In lib/stpm.ts, add:
export function cgpaToMeritPercent(cgpa: number): number {
  return Math.round((cgpa / 4.0) * 10000) / 100  // 2 decimal places
}
```

**Step 2: Update stpm-grades/page.tsx — koko input**

Change `max="4"` to `max="10"` on the koko input.
Change `placeholder="0.00 – 4.00"` to `"0.00 – 10.00"`.
Change `Math.min(koko, 4.0) * 0.1` to `koko / 10 * 4.0 * 0.1` (i.e., `koko * 0.04`).

New formula line:
```typescript
const overallCgpa = academicCgpa > 0
  ? Math.round((academicCgpa * 0.9 + Math.min(koko, 10) * 0.04) * 100) / 100
  : 0
```

**Step 3: Update i18n hint**

Update `kokoHint` in all 3 locale files from `0.00–4.00` references to `0.00–10.00`.

**Step 4: Build and verify**

```bash
cd halatuju-web && npm run build
```

**Step 5: Commit**

```bash
git add halatuju-web/src/lib/stpm.ts halatuju-web/src/app/onboarding/stpm-grades/page.tsx halatuju-web/src/messages/*.json
git commit -m "fix: koko score 0-10 scale, CGPA formula (3.60 academic + 0.40 koko = 4.00)"
```

---

### Task 5: Fix zero-courses bug on dashboard

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx:57-84`

**Root cause investigation:** The STPM eligibility API requires `halatuju_profile` to be set with gender/nationality/colorblind. If the student completes onboarding but `halatuju_profile` isn't written, the API call fails silently.

**Step 1: Add console logging to trace the issue**

In `dashboard/page.tsx`, inside the STPM eligibility useEffect (line ~118), add logging:
```typescript
console.log('STPM eligibility check:', { stpmData, profile })
```

And in the `.catch`:
```typescript
.catch(err => {
  console.error('STPM eligibility/ranking failed:', err)
  setStpmResults([])  // Show 0 instead of spinner forever
})
```

**Step 2: Fix the profile loading**

The STPM path at line 69-84 reads `halatuju_profile` but if it's not set (user skipped or fresh), it defaults to `{}` which gives empty gender/nationality. The API then rejects or returns 0 results.

Fix: Ensure defaults are valid API values:
```typescript
setProfile({
  grades: {},
  gender: parsedProfile.gender || 'male',
  nationality: parsedProfile.nationality || 'malaysian',
  colorblind: parsedProfile.colorblind === true || parsedProfile.colorblind === 'true',
  disability: parsedProfile.disability || false,
})
```

Also check: Does the STPM grade page actually set `halatuju_exam_type` to `'stpm'`? Yes (line 136 of stpm-grades/page.tsx). Does it route to `/onboarding/profile`? Yes (line 137). The profile page should set `halatuju_profile`.

**Step 3: Add error state for STPM**

When `stpmResults` is an empty array `[]` (not null), show "0 programmes" instead of infinite spinner:
```typescript
// Change: stpmResults === null ? (spinner) to:
// stpmResults === null ? (spinner) : stpmResults.length === 0 ? (no results message)
```

**Step 4: Build and verify**

```bash
cd halatuju-web && npm run build
```

**Step 5: Commit**

```bash
git add halatuju-web/src/app/dashboard/page.tsx
git commit -m "fix: STPM dashboard zero-courses bug — error handling + profile defaults"
```

---

### Task 6: Add merit traffic lights to STPM course cards

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx:391-444`

**Logic:**
1. Calculate student merit %: `studentMerit = (overallCgpa / 4.0) * 100`
2. For each course with `merit_score`:
   - Student merit ≥ course merit → **High** (green)
   - Student merit within 5% below → **Fair** (amber)
   - Student merit > 5% below → **Low** (red)
   - Course has no merit data → **No data** (grey)

**Step 1: Calculate student merit % from stored CGPA**

```typescript
const studentMerit = stpmData ? (stpmData.cgpa / 4.0) * 100 : 0
```

**Step 2: Add merit classification function**

```typescript
function getMeritLevel(studentMerit: number, courseMerit: number | null): 'high' | 'fair' | 'low' | 'none' {
  if (courseMerit === null || courseMerit === undefined) return 'none'
  if (studentMerit >= courseMerit) return 'high'
  if (studentMerit >= courseMerit - 5) return 'fair'
  return 'low'
}
```

**Step 3: Replace fit score badge with merit traffic light**

Replace the current `Fit: {score}` badge with:
```tsx
{(() => {
  const level = getMeritLevel(studentMerit, prog.merit_score)
  const styles = {
    high: 'bg-green-100 text-green-800',
    fair: 'bg-amber-100 text-amber-800',
    low: 'bg-red-100 text-red-800',
    none: 'bg-gray-100 text-gray-600',
  }
  const labels = { high: 'High', fair: 'Fair', low: 'Low', none: '—' }
  return (
    <span className={`shrink-0 px-2 py-0.5 text-xs font-bold rounded-full ${styles[level]}`}>
      {labels[level]}
    </span>
  )
})()}
```

**Step 4: Add merit % to card if available**

Below the university name:
```tsx
{prog.merit_score && (
  <p className="text-xs text-gray-400">Merit: {prog.merit_score.toFixed(2)}%</p>
)}
```

**Step 5: Add summary counts (High/Fair/Low) in header**

Similar to SPM dashboard — show merit summary next to "You qualify for X degree programmes":
```tsx
<div className="flex items-center gap-3 text-sm">
  <span className="flex items-center gap-1.5">
    <span className="w-2 h-2 rounded-full bg-green-500" />
    <span className="text-gray-600">{highCount} High</span>
  </span>
  <span className="flex items-center gap-1.5">
    <span className="w-2 h-2 rounded-full bg-amber-400" />
    <span className="text-gray-600">{fairCount} Fair</span>
  </span>
  <span className="flex items-center gap-1.5">
    <span className="w-2 h-2 rounded-full bg-red-500" />
    <span className="text-gray-600">{lowCount} Low</span>
  </span>
</div>
```

**Step 6: Build and verify**

```bash
cd halatuju-web && npm run build
```

**Step 7: Commit**

```bash
git add halatuju-web/src/app/dashboard/page.tsx
git commit -m "feat: STPM merit traffic lights — High/Fair/Low based on UPU purata markah merit"
```

---

### Task 7: Elective follows SPM "Add" button pattern

**Files:**
- Modify: `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`

**Current:** Permanent dashed dropdown always visible for elective.
**Target:** Match SPM pattern — show a "+ Add Elective Subject" button. Clicking it reveals the dropdown. Max 1 elective.

**Step 1: Change elective from always-visible to add-on-click**

Replace the permanent elective dropdown (lines 261-298) with:

```tsx
{/* Elective slot — click to add */}
{electiveSubject ? (
  <div className="flex items-center gap-2 bg-white rounded-xl border border-dashed border-gray-300 hover:shadow-md transition-shadow p-3">
    <select
      value={electiveSubject}
      onChange={(e) => handleElectiveChange(e.target.value)}
      className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
    >
      <option value="">{t('onboarding.stpmElective')}</option>
      {allOptionalSubjects
        .filter(s => !allSelected.includes(s.id) || s.id === electiveSubject)
        .map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
    </select>
    {/* grade dropdown + remove button (existing code) */}
  </div>
) : (
  <button
    onClick={() => handleElectiveChange('__placeholder__')}
    className="w-full py-3 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-primary-400 hover:text-primary-600 hover:shadow-sm transition-all text-sm font-medium"
  >
    + {t('onboarding.addElective')}
  </button>
)}
```

Note: Use a placeholder value to show the dropdown, or just set a `showElective` state toggle.

**Step 2: Add i18n key `addElective` if not present**

Check if `onboarding.addElective` exists (it does for SPM). If STPM needs its own, add `stpmAddElective`.

**Step 3: Build and verify**

```bash
cd halatuju-web && npm run build
```

**Step 4: Commit**

```bash
git add halatuju-web/src/app/onboarding/stpm-grades/page.tsx halatuju-web/src/messages/*.json
git commit -m "fix: STPM elective uses SPM add-button pattern instead of permanent dropdown"
```

---

### Task 8: ICT stream fix + subject dedup in dropdowns

**Files:**
- Modify: `halatuju-web/src/lib/subjects.ts:169`

**Step 1: Change ICT stream from 'both' to 'arts'**

```typescript
// Change:
{ id: 'ICT', name: 'Sains Komputer / ICT', stream: 'both' },
// To:
{ id: 'ICT', name: 'Sains Komputer / ICT', stream: 'arts' },
```

**Step 2: Verify subject dedup in dropdowns**

The current code already filters with `allSelected`:
```typescript
const allSelected = [...selectedSubjects, electiveSubject].filter(Boolean)
// In dropdown: .filter(s => !allSelected.includes(s.id) || s.id === subjectId)
```

This should already prevent duplicates. Verify by testing: select a subject in slot 1, it should not appear in slot 2/3/elective.

**Step 3: Build and verify**

```bash
cd halatuju-web && npm run build
```

**Step 4: Commit**

```bash
git add halatuju-web/src/lib/subjects.ts
git commit -m "fix: ICT classified as arts stream, verify subject dedup in dropdowns"
```

---

### Task 9: i18n + final polish

**Files:**
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Update/add i18n keys**

Keys to update:
- `kokoHint`: Change scale reference from 4.00 to 10.00
- `cgpaFormula`: Update to reflect `90% academic + 10% co-curriculum (÷10 × 4)`

Keys to add (if not present):
- `stpmAddElective`: "Add Elective Subject" / "Tambah Subjek Elektif" / "தேர்வுப் பாடத்தைச் சேர்"
- `dashboard.meritHigh`, `dashboard.meritFair`, `dashboard.meritLow`: Already exist from SPM

**Step 2: Run i18n checker**

```bash
cd halatuju-web && node scripts/check-i18n.js
```
Expected: ALL PASSED

**Step 3: Build**

```bash
cd halatuju-web && npm run build
```

**Step 4: Run full backend test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```
Expected: 287+ pass, golden masters intact

**Step 5: Commit**

```bash
git add halatuju-web/src/messages/*.json
git commit -m "feat: i18n updates for STPM Sprint 6 — koko scale, merit labels"
```

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Merit data doesn't match program_ids in DB | Verified: 1,113 unique IDs, 100% overlap with parsed CSVs |
| Golden master breaks after adding merit field | Merit is data-only, doesn't change eligibility logic |
| Zero-courses bug has multiple causes | Add console logging first, then fix profile defaults |
| Koko formula change affects stored CGPAs | Only affects new entries; existing users need to re-enter |

## Dependencies

- Source CSVs with merit data: `Archived/Random/data/stpm_*/mohe_programs_merged.csv` (confirmed available)
- No new external APIs or services
- No Supabase migration needed (Django migration handles schema, Cloud Run deployment syncs)
