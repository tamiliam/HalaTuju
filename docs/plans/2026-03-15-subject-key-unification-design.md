# Subject Key Unification — Design Document

**Date:** 2026-03-15
**Tech Debt Item:** TD-013
**Goal:** Eliminate the SPM subject key fork between frontend and backend by making `subjects.ts` the single source of truth.

## Problem

The SPM grades entry page (`grades/page.tsx`) uses uppercase abbreviated keys (`MAT`, `BI`, `SEJ`, `PHY`, etc.) while the backend engine uses lowercase keys (`math`, `eng`, `hist`, `phy`, etc.). A serializer `GRADE_KEY_MAP` bridges the gap, but this means:

- Adding a new subject requires changes in 5+ places
- Three different key conventions coexist (frontend uppercase, engine lowercase, report engine yet another set)
- The mapping is invisible — developers must know it exists

## Scope

**In scope:**
1. SPM grades page — switch from uppercase to backend (engine) keys
2. `subjects.ts` — add stream/category metadata, export structured arrays
3. Serializer — remove `GRADE_KEY_MAP` and `validate_grades` mapping
4. Report engine — fix `SUBJECT_LABELS` to use correct engine keys

**Out of scope:**
- STPM subject keys — frontend and backend already agree on uppercase (`PA`, `MATH_T`, `PHYSICS`). Not debt.
- SPM prerequisite grades for STPM students — already use lowercase engine keys.
- localStorage migration — beta testers only, they'll re-enter grades.

## Design

### 1. `subjects.ts` as single source of truth

Add an `SpmSubject` interface with stream/category metadata:

```typescript
export interface SpmSubject {
  id: string  // Engine key: 'math', 'eng', 'phy', etc.
  category: 'core' | 'science' | 'arts' | 'technical' | 'elective'
}

export const SPM_SUBJECTS: SpmSubject[] = [
  { id: 'bm', category: 'core' },
  { id: 'eng', category: 'core' },
  { id: 'math', category: 'core' },
  { id: 'hist', category: 'core' },
  { id: 'phy', category: 'science' },
  { id: 'chem', category: 'science' },
  // ... all subjects with their category
]

export const CORE_SUBJECTS = SPM_SUBJECTS.filter(s => s.category === 'core')
export const STREAM_POOLS = {
  science: SPM_SUBJECTS.filter(s => s.category === 'science'),
  arts: SPM_SUBJECTS.filter(s => s.category === 'arts'),
  technical: SPM_SUBJECTS.filter(s => s.category === 'technical'),
}
```

Display names come from the existing `SUBJECT_NAMES` dict via `getSubjectName(id, locale)`. No duplication.

### 2. Grades page changes

`grades/page.tsx` removes all inline subject arrays (`CORE_SUBJECTS`, `STREAM_POOLS`, `ALL_SUBJECTS`). Imports from `subjects.ts` instead. Grade dropdowns use `getSubjectName(subject.id, locale)` for bilingual display.

Grades stored to localStorage as `{ "math": "A+", "eng": "B" }`.

### 3. Serializer cleanup

Remove `GRADE_KEY_MAP` dict and `validate_grades` method from `EligibilityCheckSerializer`. The `grades` DictField stays for type validation. Keys pass through as-is.

### 4. Report engine fix

Align `SUBJECT_LABELS` in `report_engine.py` to use engine keys:
- `'sc'` → `'sci'`
- `'phys'` → `'phy'`
- `'add_math'` → `'addmath'`
- `'acc'` → `'poa'`
- `'econ'` → `'ekonomi'`

Add missing subjects that exist in the engine but not in the labels dict.

## Testing

1. **Backend** — full test suite after serializer change. Update serializer tests that send uppercase keys.
2. **Frontend** — manual test: enter grades, verify localStorage keys, verify dashboard eligibility.
3. **Report engine** — update `_format_grades()` tests to verify engine keys produce correct labels.

## Files Affected

| File | Change |
|------|--------|
| `halatuju-web/src/lib/subjects.ts` | Add `SpmSubject` interface, `SPM_SUBJECTS` array, derived exports |
| `halatuju-web/src/app/onboarding/grades/page.tsx` | Remove inline arrays, import from subjects.ts |
| `halatuju_api/apps/courses/serializers.py` | Remove `GRADE_KEY_MAP` and `validate_grades` |
| `halatuju_api/apps/reports/report_engine.py` | Fix `SUBJECT_LABELS` keys |
| `halatuju_api/apps/courses/tests/test_serializers.py` | Update test grade keys |
| `halatuju_api/apps/reports/tests/test_report_engine.py` | Update grade format tests |
