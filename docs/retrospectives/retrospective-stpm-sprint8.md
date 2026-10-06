# Retrospective — STPM Sprint 8: Polish & Dashboard Upgrade

**Date:** 2026-03-13
**Branch:** `main` (direct commits)
**Duration:** Single session

## What Was Built

1. **Proper case STPM programme names** — Converted 1,080 ALL CAPS names in Supabase to proper title case (e.g. "BACELOR KEJURUTERAAN ELEKTRIK" → "Bacelor Kejuruteraan Elektrik dan Elektronik dengan Kepujian"). Malay/English connector words correctly lowercased. Postgres function created, applied, and cleaned up.

2. **STPM detail page fix** — Fixed React error #438 (hydration crash) on `/stpm/[id]` by replacing `use(params)` with `useParams()`, matching the SPM detail page pattern.

3. **STPM dashboard card upgrade** — Replaced inline custom STPM cards with the same `CourseCard` component used by SPM. STPM dashboard now shows field images, source type/level badges, merit progress bars, bookmark icons, and institution names.

4. **Merit-based ranking** — Implemented sort order: High Chance (highest merit descending) → Fair (smallest gap first, no-rating in middle) → Low (smallest gap first). Gap = merit_cutoff − student_merit.

5. **Backend: field in eligibility API** — Added `field` to STPM eligibility response so frontend can display field images and labels.

6. **Cleanup** — Deleted `feature/stpm-entrance` branch (local + remote). Removed "Browse All Programmes" link. Added "Take Quiz" button to STPM header.

## What Went Well

- Systematic debugging of proper casing: identified that `fix_stpm_names` ran against local SQLite, not Supabase. Fixed by creating a temporary Postgres function directly in Supabase.
- The CourseCard component required zero changes — STPM data mapped cleanly to EligibleCourse.
- All deploys (4 total: 2 API + 2 web) succeeded first time.

## What Went Wrong

1. **fix_stpm_names silently ran against wrong database**
   - *Symptom:* Command reported "All names already properly cased" but Supabase still had ALL CAPS.
   - *Root cause:* No `DATABASE_URL` in local `.env`, so Django defaulted to SQLite. The command had no guard to verify it was running against production.
   - *Fix:* For future data-migration commands, always verify the target database before running. Consider adding a `--confirm-production` flag or printing the database host at startup.

2. **STPM detail page crash was pre-existing and undetected**
   - *Symptom:* Clicking any STPM course from search caused React error #438.
   - *Root cause:* `use(params)` requires a Suspense boundary (Next.js 15 async params). The SPM page used `useParams()` correctly, but the STPM page was written with a different pattern and never E2E tested.
   - *Fix:* Add E2E test for STPM detail page click-through. When creating new route pages, copy the pattern from existing working pages.

3. **Previous session's React hydration diagnosis was wrong**
   - *Symptom:* Previous session concluded React wasn't hydrating on `/search`.
   - *Root cause:* Playwright snapshot was taken before API response arrived, showing "0 of 0 courses" and "Loading...". `hasReact: false` was a red herring (React DevTools hook, not React itself).
   - *Fix:* When debugging hydration, always wait for network idle before taking snapshots. Check `__NEXT_DATA__` or router state, not devtools hooks.

## Design Decisions

- **Map STPM → EligibleCourse client-side** rather than creating a new component: Maximises reuse of CourseCard and its image/badge/merit logic.
- **Sort by merit gap (not CGPA gap)** for Fair/Low: Merit is the UPU ranking metric, making it the most meaningful comparison for students.
- **No-rating courses placed in middle of Fair**: Treats unknown merit as roughly average, avoiding unfair penalisation.

## Numbers

- Backend tests: 218 collected, 205 passing (13 pre-existing auth/JWT failures)
- STPM names fixed: 1,080 of 1,113 (33 were already proper case)
- Deploys: 4 (2 API, 2 web) — all successful
- Files changed: 4 (stpm_engine.py, api.ts, dashboard/page.tsx, stpm/[id]/page.tsx)
