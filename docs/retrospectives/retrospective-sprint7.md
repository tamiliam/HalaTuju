# Sprint 7 Retrospective — PISMP Integration

**Date**: 2026-02-18
**Duration**: Single session
**Deliverable**: 73 PISMP teacher training courses integrated into eligibility engine

## What Was Built

- **PISMP data file** (`data/pismp_requirements.csv`): Cleaned from draft — 73 programmes, all requiring 5 Cemerlang (A-/A/A+) minimum
- **Model migration**: `pismp` added to `source_type` choices (alongside poly, kkom, tvet, ua)
- **Engine fix**: `check_subject_group_logic` now handles empty `subjects: []` — counts from all student grades instead of skipping
- **NaN guard**: Both `check_subject_group_logic` and `check_complex_requirements` now reject non-string input (NaN from DataFrame concat)
- **Load command**: `pismp_requirements.csv` added to CSV loader
- **Frontend**: "Teacher Training" type label (amber badge), stat card, filter dropdown option
- **8 new tests**: Perfect student, weak student, borderline (5 A-), 4-A exclusion, Malaysian-only, stats, merit labels, subject-specific

## What Went Well

- **Existing plan document**: `docs/roadmap/pismp_integration_plan.md` gave a clear roadmap. Data was already parsed and available.
- **Engine extensibility**: The `subject_group_req` JSON format is the same for PISMP as for UA. `map_subject_code()` already handles all PISMP subject codes. No engine changes needed beyond the empty-subjects fix.
- **Frontend extensibility**: Adding a new `source_type` to CourseCard/dashboard was trivial — just add entries to `TYPE_LABELS`, `TYPE_COLORS`, and the filter dropdown.
- **All 8 new tests passed on first run** (after the NaN fix).

## What Went Wrong

- **NaN crash**: Adding PISMP's `subject_group_req` column to `pd.concat` introduced NaN values in all poly/TVET rows. NaN is truthy in Python, so `if not nan` is False — the engine tried to `.strip()` a float. This crashed ALL eligibility tests, not just PISMP ones. Fix: `isinstance(val, str)` guard in both check functions.
- **Latent bug in empty subjects**: The engine's `check_subject_group_logic` had `if not subjects: continue` — silently skipping rules with empty subject lists. This was never triggered by existing data (no poly/TVET/UA course uses `subjects: []`), but PISMP relies on it for the "5 Cemerlang from any subjects" gate. Without the fix, students with zero A grades would have qualified for PISMP.

## Design Decisions

1. **Golden master untouched**: PISMP data is loaded separately from the golden master test. The 8280 baseline only covers poly/TVET/UA.
2. **No merit labels for PISMP**: PISMP has no `merit_cutoff` data. Like TVET, merit traffic lights are `null`.
3. **`age_limit` deferred**: PISMP requires age <= 20, but the student profile has no age field. Documented as future enhancement.
4. **IPG institution data deferred**: PISMP courses are offered at 27 IPG campuses, but institution-course linking is Sprint 9 scope.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 106 | 114 |
| Golden master | 8280 | 8280 |
| PISMP courses | 0 | 73 |
| Files created | — | 2 (pismp_requirements.csv, migration) |
| Files modified | — | 8 (engine.py, models.py, load_csv_data.py, test_api.py, CourseCard.tsx, dashboard/page.tsx, CHANGELOG, roadmap) |
| Frontend routes | 16 | 16 |
