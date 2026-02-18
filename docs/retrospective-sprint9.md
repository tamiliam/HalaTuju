# Sprint 9 Retrospective — Data Gap Filling

**Date**: 2026-02-18
**Duration**: Single session
**Deliverable**: 157 courses enriched with metadata, institution modifiers migrated to DB, audit command

## What Was Built

- **TVET course metadata loader** (`load_tvet_course_metadata`): Reads `tvet_courses.csv` (84 rows) and updates Course rows with full metadata — name, level, department, field, frontend_label, description, WBL flag, and semesters (converted from months).
- **PISMP course metadata enrichment** (`load_pismp_course_metadata`): Sets level ("Ijazah Sarjana Muda Pendidikan"), department/field ("Pendidikan"), semesters (8), and auto-generated Malay descriptions for all 73 PISMP courses.
- **Institution modifiers to DB**: Added `modifiers` JSONField to Institution model (migration 0004). `load_csv_data` now loads modifiers from `institutions.json` into the DB. `apps.py` reads modifiers from DB instead of filesystem — fixes a production bug where modifiers weren't available on Cloud Run.
- **`audit_data` management command**: Reports data completeness across courses, requirements, institutions, offerings, and tags.
- **5 new tests**: TVET enrichment, PISMP enrichment, institution modifiers (default, storage, retrieval).

## What Went Well

- **`tvet_courses.csv` already had perfect data**: All 84 TVET courses had complete metadata in an unused CSV file. Just needed a loader.
- **Clean discovery process**: Systematic investigation revealed the real gaps were different from assumptions — the 226 courses in `courses.csv` were complete; the gap was in the 157 courses created as stubs by `load_requirements`.
- **Institution modifiers bug fix**: Discovered that `institutions.json` was never accessible on Cloud Run (outside Docker build context). Simple migration to DB field fixed it.
- **All 124 tests passed on first run** — no bugs.
- **Golden master 8280 unchanged** — no eligibility logic touched.

## What Went Wrong

- Nothing. Clean sprint.

## Design Decisions

1. **JSONField for modifiers**: Rather than adding 6 individual boolean/char fields (urban, cultural_safety_net, etc.), used a single JSONField. This keeps the schema simple and matches how the ranking engine already consumes the data (as a dict).
2. **PISMP descriptions in Malay**: Auto-generated descriptions use the Malay course name and standard PISMP programme description. All HalaTuju content is in Malay.
3. **Months → semesters conversion**: `tvet_courses.csv` stores duration in months. Converted to semesters using `max(1, months // 6)` to match the Course model's `semesters` field.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 119 | 124 |
| Golden master | 8280 | 8280 |
| Courses with complete metadata | 226 | 383 |
| Institution modifiers in DB | 0 | 212 |
| Files modified | — | 4 (models.py, load_csv_data.py, apps.py, CLAUDE.md) |
| Files created | — | 3 (migration, audit_data.py, test_data_loading.py) |
