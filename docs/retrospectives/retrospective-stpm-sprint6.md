# STPM Sprint 6 Retrospective — Merit Scoring + UX Polish

**Date:** 2026-03-13
**Branch:** `feature/stpm-entrance`

## What Was Built

1. **Merit score model + data pipeline** — Added `merit_score` field to `StpmCourse`, slim CSV files for science (1,003) and arts (677) programmes, and a loader method that handles "Tiada" as null and strips `%` from values.
2. **API exposure** — `merit_score` included in eligibility response dict and passes through the ranking pipeline unchanged.
3. **CGPA formula fix** — Koko score corrected from 0–4 scale to 0–10 scale. Formula: `(academicCgpa × 0.9) + (kokoScore × 0.04)`. Max CGPA: 3.60 + 0.40 = 4.00.
4. **Merit traffic lights** — Dashboard cards show High/Fair/Low badges based on student merit vs course merit. Summary counts in header (302 High, 75 Fair, 77 Low for test student).
5. **Zero-courses bug fix** — Dashboard no longer crashes when API returns empty results; shows empty state with i18n'd message.
6. **Elective UX** — Replaced permanent 4th dropdown with add-button pattern (dashed border, "+ Add Elective").
7. **ICT stream fix** — Reclassified from `'both'` to `'arts'` in subjects.ts.
8. **i18n cleanup** — Replaced hardcoded "degree programmes" with `t('dashboard.qualifyCourses')`, updated koko hint text in EN/BM/TA.
9. **Supabase data load** — 1,080 merit scores loaded via 22 SQL batches into production `stpm_courses` table.

## What Went Well

- **Subagent-driven development worked smoothly** — 9 tasks completed with fresh subagent per task + two-stage review (spec compliance then code quality). Reviews caught real issues: hardcoded English text, unused export.
- **Merit classification logic is simple and correct** — `studentMerit >= courseMerit → High`, `within 5% → Fair`, `else → Low`. Easy to explain to students.
- **Data pipeline is robust** — "Tiada" handling, `%` stripping, null-safe throughout API→frontend chain.
- **Deployed and verified with screenshots** — Tagged revision confirmed working with real merit data.

## What Went Wrong

1. **Supabase table name mismatch delayed SQL execution**
   - *Symptom:* `ALTER TABLE courses_stpmcourse` returned "relation does not exist"
   - *Root cause:* Assumed Django's default table naming (`app_model`) but HalaTuju uses `class Meta: db_table = 'stpm_courses'`. Didn't check the model before writing SQL.
   - *Fix:* Queried `information_schema.tables` to discover actual table name `stpm_courses`.
   - *Prevention:* Always check `class Meta: db_table` in Django models before writing raw SQL against Supabase.

2. **Merit SQL batches exhausted context window**
   - *Symptom:* Conversation ran out of context after generating 22 batch files with 50 UPDATE statements each.
   - *Root cause:* Each batch read + MCP execute consumed ~2KB of context. 22 batches × 2 rounds (read + execute) = ~88KB. Combined with 9 subagent task contexts already in the window.
   - *Fix:* Continued in a new session. Generated batch files to disk first, then read and executed sequentially.
   - *Prevention:* For bulk data loads >500 rows, generate a single SQL file and execute via `psql` or a management command rather than MCP batches.

3. **Tagged frontend called main API, not tagged API**
   - *Symptom:* After loading merit data, tagged frontend still showed "0 High, 0 Fair, 0 Low"
   - *Root cause:* `NEXT_PUBLIC_API_URL` is baked into the frontend at build time and points to the main API URL. The tagged API revision had fresh data but the frontend never called it.
   - *Fix:* Forced a new main API revision via `gcloud run services update` with a dummy env var, then routed 100% traffic to it.
   - *Prevention:* When using Cloud Run revision tags for E2E testing, remember that `NEXT_PUBLIC_*` env vars are build-time constants. Either rebuild the frontend with the tagged API URL, or update the main API revision.

## Design Decisions

1. **Merit classification thresholds** — High (≥ course merit), Fair (within 5% below), Low (>5% below). The 5% threshold was chosen as a meaningful "borderline" zone — students within 5% have a realistic chance if they improve slightly.

2. **Student merit = (CGPA/4.0) × 100** — Converts CGPA to a percentage scale matching UPU's purata markah merit format. This makes comparison straightforward: both values are 0–100 percentages.

3. **Koko 0–10 scale with 4% weight** — The actual STPM system uses koko marks out of 10, contributing 10% of overall CGPA. Formula: `(academic × 0.9) + (koko × 0.04)`. Max contribution: 10 × 0.04 = 0.40, giving max CGPA = 3.60 + 0.40 = 4.00.

## Numbers

- **Tests:** 326 collected, 293 passing (+6 from Sprint 5), 9 pre-existing JWT failures, 24 skipped
- **Golden masters:** SPM = 8283, STPM = 1811 (both preserved)
- **Merit data:** 1,080 courses with scores (range 59.33%–100.00%, avg 86.94%), 33 "Tiada"
- **Files changed:** 14 (7 backend, 7 frontend)
- **New tests:** 6 (merit model, data loading, engine exposure, ranking pipeline, cgpaToMeritPercent)
- **Deployed:** Both API and web with `--tag stpm`, then main API updated for merit data
