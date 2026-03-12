# STPM Entrance Sprint 1 Retrospective

**Sprint:** STPM Entrance — Data Models + Engine
**Date:** 2026-03-12
**Branch:** feature/stpm-entrance

## What Was Built

- `StpmCourse` and `StpmRequirement` Django models for 1,113 unique STPM degree programmes
- `load_stpm_data` management command — loads science (1,003) + arts (677) CSVs with 567 overlapping programme IDs
- `stpm_engine.py` — CGPA calculator, grade comparison, full eligibility checker with 7 criteria (CGPA, MUET, demographics, STPM subjects, min subjects, subject groups, SPM prerequisites)
- `POST /api/v1/stpm/eligibility/check/` API endpoint
- STPM golden master baseline: 1811 across 5 test student profiles
- Implementation plan: `docs/plans/2026-03-12-stpm-entrance.md` (5 sprints, 22 tasks)

## What Went Well

- **Subagent-driven development** worked efficiently — fresh context per task prevented confusion, spec reviews caught a missing test assertion
- **CSV data investigation** revealed important data realities early: 567 overlapping programme IDs (unique count 1,113 not 1,680), 162 bumiputera-only UiTM programmes to exclude
- **TDD approach** — tests written before implementation, all 29 new tests passing
- **Zero regressions** — existing 250 SPM tests unaffected

## What Went Wrong

- **CSV overlap not discovered until runtime** — the plan assumed 1,680 unique programmes. The science and arts CSVs share 567 programme IDs (courses offered in both streams). Discovered during loader testing. No code impact (update_or_create handles it) but required test adjustment.
- **Bumiputera scope not clarified upfront** — the plan included bumiputera-only programmes. User clarified these are out of scope after Sprint 1 was mostly done. Fixed with a one-line filter, but could have been caught during planning.

## Design Decisions

1. **Separate models (StpmCourse/StpmRequirement) rather than extending existing Course/CourseRequirement** — STPM degree programmes are structurally different from SPM diploma/sijil courses. Different fields, different eligibility logic, different data source. Keeping them separate avoids polluting the SPM golden master.

2. **Engine imports model inside function** — `StpmRequirement` is imported inside `check_stpm_eligibility()` to keep the pure functions (CGPA calc, grade comparison) testable without Django.

3. **Unconditional bumiputera exclusion** — rather than checking the student's ethnicity, we simply skip all `req_bumiputera=True` programmes. HalaTuju's target users are non-Bumiputera.

4. **Islamic studies programmes kept** — Syariah, Usuluddin, Pengajian Islam programmes at IIUM/UKM/UM are legitimate open-entry university degrees, not STAM (religious school) entries.

## Numbers

| Metric | Value |
|--------|-------|
| New tests | 29 |
| Total tests | 288 collected, 255 passing |
| SPM golden master | 8283 (unchanged) |
| STPM golden master | 1811 |
| STPM programmes loaded | 1,113 unique |
| Bumiputera-only excluded | 162 (UiTM) |
| Commits | 9 |
| Files touched | ~12 |
