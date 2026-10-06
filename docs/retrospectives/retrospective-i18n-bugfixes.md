# Retrospective — localStorage & Bug Fixes Sprint (2026-03-19)

## What Was Built

1. **Dashboard bug fix (BooleanField conversion)**: Converted `StudentProfile.colorblind` and `disability` from `CharField("Ya"/"Tidak")` to `BooleanField` across backend (model, engines, serializer, views, tests) and frontend (6 API call sites, 3 API types). Migration 0046 applied to Supabase.

2. **localStorage as cache, not source of truth**: `restoreProfileToLocalStorage()` now always overwrites from Supabase API on login, instead of only writing when localStorage is empty. This eliminates the entire class of stale-cache bugs — not just the colorblind/disability one.

3. **UI fixes**: Landing page stats (1,300+ / 800+), login button compact styling, profile incomplete count badge.

4. **Ranking improvements**: W4 (PISMP course tags — 73 courses backfilled) and W11 (STPM stream as pre-quiz signal).

## What Went Well

- **Root cause investigation paid off**: User's report of intermittent "Failed to load recommendations" led to finding the real bug — a CharField/BooleanField mismatch. The symptom (intermittent failures) was misleading; it only happened for logged-in users whose profile had been synced from the backend.
- **Golden masters unchanged**: Despite touching engine.py, stpm_engine.py, and ~50 test profiles, both golden masters (SPM=5319, STPM=2026) held — confirming the conversion was semantically identical.

## What Went Wrong

1. **Fixed the backend but forgot the frontend.**
   - *Symptom*: After deploying the BooleanField backend fix, dashboard still showed "Failed to load recommendations".
   - *Root cause*: Backend was converted to accept booleans, but 6 frontend call sites still converted `colorblind ? 'Ya' : 'Tidak'` before sending. The fix was applied to half the stack.
   - *Fix*: When changing a data type at a system boundary, grep BOTH sides (backend + frontend) for all references. A backend-only change at a serializer boundary is never complete.

2. **Applied a symptom-level fix (migrateProfile) before understanding the real cause.**
   - *Symptom*: After fixing the frontend API calls, the bug persisted because stale localStorage still had "Ya"/"Tidak" strings.
   - *Root cause*: Wrote a `migrateProfile()` function to convert "Ya"/"Tidak" → booleans in localStorage — a field-specific workaround. The actual problem was that `restoreProfileToLocalStorage()` treated localStorage as authoritative (only wrote when empty) instead of as a cache.
   - *Fix*: User correctly identified the architectural issue: "localStorage is a cache, Supabase is the source of truth. On login, always overwrite." This one-line conceptual change (`remove the !localStorage guard`) made the migration shim unnecessary and prevents all future stale-cache bugs, not just this one.

3. **Three deploys for one bug.**
   - *Symptom*: Pushed three separate commits for what should have been one fix.
   - *Root cause*: Didn't trace the full data flow (backend → API → frontend → localStorage → dashboard → API) before starting. Each push fixed one segment and revealed the next.
   - *Fix*: Before fixing a data-flow bug, draw the full pipeline on paper (or in a comment). Identify every touchpoint. Fix them all in one commit.

4. **Recorded the migration but never applied the DDL.**
   - *Symptom*: After all frontend/backend/localStorage fixes were deployed, all 222 poly/kkom/tvet courses were missing from the dashboard. ILJTM and ILKBS pathways showed 0 courses.
   - *Root cause*: Migration 0046 was inserted into `django_migrations` via raw SQL (to bypass `InconsistentMigrationHistory`), but the actual `ALTER TABLE` to change `colorblind`/`disability` from VARCHAR to BOOLEAN was never executed. The columns remained VARCHAR. Django's BooleanField read the VARCHAR string `"Tidak"` as truthy → `True`. Every course with `no_disability=true` (all poly, kkom, tvet) failed eligibility for every student.
   - *Fix*: Applied the DDL directly: add temp boolean columns, convert data ("Tidak"→false, "Ya"→true), drop old VARCHAR columns, rename. Verify column types match the Django model AFTER applying migrations via raw SQL — never trust the `django_migrations` record alone.

## Design Decisions

1. **localStorage as disposable cache**: `restoreProfileToLocalStorage()` always overwrites from Supabase on login. No conditional writes. Logout (`clearAll()`) wipes everything. This is the canonical architecture — Supabase is authoritative, localStorage is a performance cache.

2. **CharField → BooleanField (not serializer workaround)**: The model is the source of truth for data types. Booleans flow through unchanged from DB → API → frontend → localStorage → API calls. Zero conversion layers.

## Numbers

- Files changed: 28 (10 backend, 1 migration, 12 frontend, 3 i18n, 2 docs)
- Tests: 932 pass, 0 fail
- Golden masters: SPM 5319, STPM 2026 (unchanged)
- Supabase migration: 0046 applied (data converted in-place)
- Deploys: 3 (should have been 1) + 1 direct DB fix
- Post-deploy DB fix: VARCHAR→BOOLEAN column conversion (19 profiles corrected)
