# HalaTuju Technical Debt Audit

**Date:** 2026-03-14
**Auditor:** Claude (comprehensive codebase read)
**Scope:** halatuju_api + halatuju-web (full codebase)

---

## Executive Summary

**Total issues found: 52** (High: 8, Medium: 22, Low: 22)

**Top 3 highest-risk items:**
1. **[TD-001] STPM SPM prerequisite fields not checked** — `spm_pass_bi` and `spm_pass_math` exist in the model but are silently ignored by the eligibility engine. Students may qualify for programmes they shouldn't.
2. **[TD-002] Client-side eligibility logic duplicated** — pathways.ts, merit.ts, and stpm.ts mirror backend logic using different subject key conventions. Any formula change must be made in two places with no automated cross-check.
3. **[TD-003] Zero frontend tests** — No test files in halatuju-web. LOW risk after TD-002 Sprint removed all frontend business logic.

**Category with most inconsistency:** Frontend-backend implicit contracts (11 items)

**Estimated fix sprints:** 6-8 sprints if addressed systematically (grouped by risk, not by category)

---

## API Response Format Consistency

### [TD-004] Mixed HTTP status code style ✅ RESOLVED (API Consistency Sprint, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/views.py`
**Resolution:** All raw integer status codes in `SavedCoursesView` and `SavedCourseDetailView` replaced with DRF constants (`status.HTTP_400_BAD_REQUEST`, `status.HTTP_201_CREATED`, `status.HTTP_404_NOT_FOUND`). Default 200 responses use no explicit status (DRF default).

### [TD-005] No standard error response envelope
**File(s):** `halatuju_api/apps/courses/views.py` (throughout), `halatuju_api/apps/reports/views.py`
**What it is:** Error responses use `{'error': 'message'}` but success responses have no consistent envelope. Some return `{'message': 'done'}`, others return the data directly. The frontend `api.ts` reads `error.message` from the response (line 30) but backend sends `error` key, not `message`.
**What consistent looks like:** All errors return `{'error': 'code', 'detail': 'human message'}` with a standard structure. Successes use a consistent data envelope.
**Risk if left:** Low — works because frontend catches errors by HTTP status, not response body.
**Dependencies:** Frontend api.ts error handling.

### [TD-006] Inconsistent success response keys
**File(s):** `halatuju_api/apps/courses/views.py`
**What it is:** Course list returns `{'courses': [...], 'count': N}` (line 772), eligibility returns `{'eligible_courses': [...], 'total_count': N}` (line 611), outcomes returns `{'outcomes': [...], 'count': N}` (line 1115). The count field name is either `count` or `total_count`.
**What consistent looks like:** Pick one: always `total_count` or always `count`.
**Risk if left:** Low — frontend handles each endpoint independently.
**Dependencies:** Frontend api.ts types.

---

## Error Handling Patterns

### [TD-007] Bare except in engine.py merit calculation
**File(s):** `halatuju_api/apps/courses/engine.py` (line 191)
**What it is:** `check_merit_probability()` uses a bare `except:` clause that swallows all exceptions including KeyboardInterrupt and SystemExit.
**What consistent looks like:** `except (ValueError, TypeError):` — only catch expected conversion errors.
**Risk if left:** Medium — could mask real bugs in merit calculation silently returning "Unknown".
**Dependencies:** Golden master tests would not catch this since they don't test merit labels.

### [TD-008] ProfileView accepts arbitrary fields without validation ✅ RESOLVED (Security Sprint, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/views.py`, `halatuju_api/apps/courses/serializers.py`
**Resolution:** Created `ProfileUpdateSerializer` (ModelSerializer for StudentProfile, 19 fields, partial=True). Both `ProfileView.put()` and `ProfileSyncView.post()` now validate via serializer — malformed input returns 400 instead of 500.

### [TD-009] No rate limiting on Gemini API calls
**File(s):** `halatuju_api/apps/reports/views.py`, `halatuju_api/apps/reports/report_engine.py`
**What it is:** The report generation endpoint calls the Gemini API with no rate limiting. An authenticated user could trigger unlimited API calls, each costing money.
**What consistent looks like:** Rate limit report generation per user (e.g., max 3 per day).
**Risk if left:** Medium — cost risk if abused, though currently low traffic.
**Dependencies:** Would need Django cache or a counter model.

---

## Authentication and Permission Handling

### [TD-010] ~~9 pre-existing auth test failures~~ **RESOLVED (TD-010 Sprint, 2026-03-14)**
**File(s):** `halatuju_api/apps/courses/tests/test_auth.py`, `test_saved_courses.py`, `test_views.py`
**What it was:** 13 tests (not 9 — count was wrong in original audit) failed because they mocked `jwt.decode` but not `jwt.get_unverified_header`, which the middleware calls first. Fixed by adding the missing mock.
**Resolution:** Simple mock fix. Proper auth test infrastructure deferred to admin layer design — see `docs/decisions.md`.

### [TD-011] SupabaseIsAuthenticated returns 403 instead of 401 ✅ RESOLVED (API Consistency Sprint, 2026-03-14)
**File(s):** `halatuju_api/halatuju/middleware/supabase_auth.py`, `halatuju_api/halatuju/settings/base.py`
**Resolution:** Added `SupabaseAuthentication` DRF authentication class with `authenticate_header()` returning `'Bearer'`. Registered as `DEFAULT_AUTHENTICATION_CLASSES`. DRF now returns 401 with `WWW-Authenticate: Bearer` header for unauthenticated requests, per RFC 7235. All auth tests updated from 403→401.

### [TD-012] DEFAULT_PERMISSION_CLASSES is AllowAny ✅ RESOLVED (Security Sprint, 2026-03-14)
**File(s):** `halatuju_api/halatuju/settings/base.py`
**Resolution:** Default changed to `SupabaseIsAuthenticated`. 16 public views explicitly marked with `permission_classes = [AllowAny]`. All 382 tests pass.

---

## Frontend-Backend Implicit Contracts

### [TD-001] STPM SPM prerequisite fields not checked (HIGH RISK)
**File(s):** `halatuju_api/apps/courses/stpm_engine.py` (lines 106-113), `halatuju_api/apps/courses/models.py` (lines 575, 577)
**What it is:** `StpmRequirement` model has `spm_pass_bi` (line 575) and `spm_pass_math` (line 577) boolean fields. But `check_spm_prerequisites()` only checks: `spm_credit_bm`, `spm_pass_sejarah`, `spm_credit_bi`, `spm_credit_math`, `spm_credit_addmath`, `spm_credit_science`. The `spm_pass_bi` and `spm_pass_math` fields are loaded from CSV, stored in DB, but NEVER evaluated.
**What consistent looks like:** Add `('spm_pass_bi', 'eng', SPM_PASS_GRADES)` and `('spm_pass_math', 'math', SPM_PASS_GRADES)` to `SIMPLE_CHECKS`.
**Risk if left:** HIGH — students may be shown as eligible for programmes that actually require a pass in BI or Math at SPM level. This is a correctness bug, not just tech debt.
**Dependencies:** STPM golden master will change. Must update baseline after fix.

### [TD-002] Client-side eligibility logic duplicated (HIGH RISK) — RESOLVED
**Resolved:** TD-002 Sprint (2026-03-14). Frontend calculation files (`merit.ts`, `stpm.ts`, `pathways.ts` — 596 lines) deleted. Three new backend API endpoints added: `/calculate/merit/`, `/calculate/cgpa/`, `/calculate/pathways/`. Frontend now calls backend for all calculations. `getPathwayFitScore()` ported to `pathways.py`. Backend is the single source of truth.

### [TD-013] Subject key naming split
**File(s):**
- Frontend grades page: Uses MAT, AMT, CHE, PHY, BIO, BI, BM, SEJ, SN, PI, PM etc.
- Backend engine: Uses math, addmath, chem, phy, bio, eng, bm, hist, sci, islam, moral etc.
- Serializer mapping: `halatuju_api/apps/courses/serializers.py` (lines 157-173)
- STPM engine CSV mapping: `halatuju_api/apps/courses/stpm_engine.py` (lines 65-70)
**What it is:** Frontend and backend use completely different subject key conventions. The serializer maps between them, but the frontend pathways.ts and the backend pathways.py both hardcode their respective key sets. If a new subject is added, it must be added to: (1) subjects.ts, (2) serializer GRADE_KEY_MAP, (3) engine subject lists, (4) pathways.ts groups, (5) pathways.py groups.
**What consistent looks like:** One canonical key set (either frontend or backend), shared via a generated constants file.
**Risk if left:** Medium — any new subject requires changes in 5+ places.
**Dependencies:** All eligibility logic, all UI grade entry.

### [TD-014] localStorage sprawl with no centralised management
**File(s):** `halatuju-web/src/app/dashboard/page.tsx`, `halatuju-web/src/app/onboarding/grades/page.tsx`, `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`, `halatuju-web/src/lib/auth-context.tsx`, `halatuju-web/src/components/AuthGateModal.tsx`, many others
**What it is:** Over 20 different `halatuju_*` localStorage keys scattered across 15+ files with no centralised read/write layer. Keys include: `halatuju_grades`, `halatuju_profile`, `halatuju_stream`, `halatuju_merit`, `halatuju_quiz_signals`, `halatuju_signal_strength`, `halatuju_report_generated`, `halatuju_exam_type`, `halatuju_stpm_grades`, `halatuju_stpm_cgpa`, `halatuju_muet_band`, `halatuju_spm_prereq`, `halatuju_stpm_stream`, `halatuju_koko_score`, `halatuju_aliran`, `halatuju_elektif`, `halatuju_lang`, `halatuju_locale`, `halatuju_resume_action`. No TypeScript types enforce the shape of values stored/retrieved.
**What consistent looks like:** A single `useStudentStore()` hook (or Zustand/Jotai store) that wraps localStorage with typed getters/setters.
**Risk if left:** Medium — easy to introduce bugs by reading/writing wrong key or wrong shape. Hard to reason about data flow.
**Dependencies:** Every page that reads/writes student data.

### [TD-015] Frontend merit calculation sent to backend, backend may recalculate — RESOLVED
**Resolved:** TD-002 Sprint (2026-03-14). Frontend no longer calculates merit locally — it calls `/calculate/merit/` API. Backend is the single source of truth. `merit.ts` deleted.

### [TD-016] StpmProgrammeDetailView looks up institution by name
**File(s):** `halatuju_api/apps/courses/views.py` (lines 1409-1411)
**What it is:** `StpmProgrammeDetailView` looks up the institution by `institution_name=prog.university` using `Institution.objects.get()`. This is fragile — if the STPM course `university` field doesn't exactly match `Institution.institution_name`, the lookup silently fails (returns no institution data). There's no foreign key relationship.
**What consistent looks like:** Either add a FK from StpmCourse to Institution, or use `iexact` lookup with proper error handling.
**Risk if left:** Medium — any name mismatch means STPM programme detail page shows no institution card.
**Dependencies:** STPM programme detail page.

### [TD-017] Pre-U fit scoring exists only on frontend — RESOLVED
**Resolved:** TD-002 Sprint (2026-03-14). `getPathwayFitScore()` ported to `pathways.py` with 5 tests. `/calculate/pathways/` endpoint returns fit scores. Frontend `pathways.ts` deleted.

---

## Duplicated Logic

### [TD-018] Duplicate import of Count, Subquery, OuterRef
**File(s):** `halatuju_api/apps/courses/views.py` (line 25 and line 354)
**What it is:** `Count, Subquery, OuterRef` are imported at the top of the file (line 25) and then re-imported inside `EligibilityCheckView.post()` (line 354).
**What consistent looks like:** Remove the inline import at line 354.
**Risk if left:** Low — no functional impact.
**Dependencies:** None.

### [TD-019] Inline json import in views.py
**File(s):** `halatuju_api/apps/courses/views.py` (lines 487, 827)
**What it is:** `import json as _json` is done inline inside method bodies at lines 487 and 827, with an underscore prefix to avoid name collision. Also `defaultdict` is imported inline as `_dd` at line 488.
**What consistent looks like:** Import at the top of the file.
**Risk if left:** Low — just code smell.
**Dependencies:** None.

### [TD-020] Duplicate credit_stv key in serializer SPECIAL_FIELDS
**File(s):** `halatuju_api/apps/courses/serializers.py` (lines 75, 88)
**What it is:** `'credit_stv': 'Kredit Sains/Teknikal/Vokasional'` appears twice in the `SPECIAL_FIELDS` dict. In Python, the second silently overwrites the first, so the duplicate is dead code.
**What consistent looks like:** Remove the duplicate at line 88.
**Risk if left:** Low — no functional impact, but misleading.
**Dependencies:** None.

### [TD-021] PISMP deduplication logic in views.py is complex and inline
**File(s):** `halatuju_api/apps/courses/views.py` (lines 481-557)
**What it is:** ~75 lines of PISMP zone-variant deduplication logic is embedded directly inside `EligibilityCheckView.post()`. This includes hash computation, zone detection, language merging — all with inline imports and local function definitions. The method is already ~300 lines long.
**What consistent looks like:** Extract PISMP deduplication to a separate function in a utilities module.
**Risk if left:** Low — works but makes the eligibility endpoint very hard to read and maintain.
**Dependencies:** PISMP eligibility results.

### [TD-022] Eligibility sort logic duplicated between search and eligibility views
**File(s):** `halatuju_api/apps/courses/views.py` (lines 220-225, 565-598)
**What it is:** Both `CourseSearchView` and `EligibilityCheckView` have their own sort logic with different priority structures. Search sorts by `credential > source_type > merit > name`. Eligibility sorts by `merit_label > delta > credential > pathway > cutoff > name`. The `SOURCE_TYPE_ORDER` and `PATHWAY_PRIORITY` dicts are defined inline in each view.
**What consistent looks like:** Extract sort configuration to module-level constants or a shared function.
**Risk if left:** Low — intentionally different sorting, but the inline constants are hard to maintain.
**Dependencies:** None.

---

## Naming Conventions

### [TD-023] Model field name vs engine key inconsistencies
**File(s):** `halatuju_api/apps/courses/models.py`, `halatuju_api/apps/courses/engine.py`
**What it is:** The `CourseRequirement` model uses `three_m_only` (Python-valid identifier) but the engine expects `3m_only` (from CSV). The `apps.py` renames this column at startup (line 65). Similarly, `pass_history` in the model maps to checking `g.get('hist')` in the engine.
**What consistent looks like:** Model fields match engine expectations, or the mapping is documented in one place.
**Risk if left:** Low — the rename works, but it's a hidden coupling.
**Dependencies:** apps.py startup code, engine.py.

### [TD-024] Course name field is just 'course'
**File(s):** `halatuju_api/apps/courses/models.py` (line 23)
**What it is:** The Course model's name field is called `course` — so you get `course.course` to access the name. Every serializer, view, and template that references the course name reads `c.course` which looks like a self-reference.
**What consistent looks like:** Field should be `name` (yielding `course.name`).
**Risk if left:** Low — functionally fine, but confusing for new contributors.
**Dependencies:** Would require migration + updates to engine, views, serializers, templates, frontend types. Too risky to change now.

### [TD-025] StudentProfile table name uses 'api_' prefix
**File(s):** `halatuju_api/apps/courses/models.py` (line 424)
**What it is:** `db_table = 'api_student_profiles'` — the `api_` prefix was added to avoid collision with the legacy Streamlit `student_profiles` table. This is documented in the model docstring but is still a naming oddity.
**What consistent looks like:** Use `student_profiles` once Streamlit is fully decommissioned.
**Risk if left:** Low — works fine, just slightly confusing.
**Dependencies:** Supabase RLS policies, migration needed.

### [TD-026] Inconsistent response field names for course name
**File(s):** `halatuju_api/apps/courses/views.py`
**What it is:** Eligibility returns `course_name`, Course serializer returns `course` (the model field name), search returns `course_name`. Frontend types in api.ts have both `Course.course` and `EligibleCourse.course_name`.
**What consistent looks like:** Always use `course_name` in API responses.
**Risk if left:** Low — frontend handles it, but new developers will be confused.
**Dependencies:** Frontend api.ts types.

---

## Bolt-On Code from Pre-Django Migration

### [TD-027] Legacy key mapping still in engine.py
**File(s):** `halatuju_api/apps/courses/engine.py` (lines 92-97)
**What it is:** `LEGACY_KEY_MAP` maps old keys like `"tech" → "eng_civil"`, `"voc" → "voc_weld"`, `"islam" → "moral"`, `"b_arab" → "b_tamil"`. The `islam → moral` mapping is particularly surprising — it means if a student has `moral` grade data stored under `islam` key, it maps to `moral`.
**What consistent looks like:** If no user data still uses these keys, remove the map. If it's still needed, document why each mapping exists.
**Risk if left:** Low — defensive code, but the `islam → moral` mapping could be a logic error.
**Dependencies:** Would need to check if any StudentProfile.grades in Supabase still use these keys.

### [TD-028] CSV data files still in codebase
**File(s):** `halatuju_api/data/stpm/` (4 CSV files)
**What it is:** STPM CSV data files remain in the repo even though data has been migrated to Supabase. They're only used by the `load_stpm_data.py` management command (one-time migration).
**What consistent looks like:** Move to `_archive/` or delete if migration is confirmed complete.
**Risk if left:** Low — just clutter, but 4 files × ~500 lines each.
**Dependencies:** load_stpm_data.py command.

### [TD-029] Legacy Streamlit archive still in repo
**File(s):** `_archive/streamlit/` (246 files)
**What it is:** The complete Streamlit prototype is preserved. While documented, it inflates repo size and could confuse contributors.
**What consistent looks like:** If valuable for reference, keep. If not, move to a separate branch or archive repo.
**Risk if left:** Low — clearly marked as archive.
**Dependencies:** None.

### [TD-030] Model docstring row counts are stale
**File(s):** `halatuju_api/apps/courses/models.py` (lines 21, 57, 75, 206, 267, 311)
**What it is:** Docstrings reference original CSV row counts: "431 rows", "212 rows", "633 rows". The actual current counts are different (389 courses, 239 institutions, ~800 course_institutions).
**What consistent looks like:** Remove specific row counts from docstrings — they go stale immediately.
**Risk if left:** Low — misleading but no functional impact.
**Dependencies:** None.

---

## Management Commands and Data Integrity Scripts

### [TD-031] One-time scripts still in management commands
**File(s):**
- `halatuju_api/apps/courses/management/commands/enrich_stpm_metadata.py`
- `halatuju_api/apps/courses/management/commands/fix_stpm_names.py`
**What it is:** These were one-time data enrichment/fix scripts that called the Gemini API and fixed name casing. They're still importable as management commands and could be accidentally run again.
**What consistent looks like:** Move to `scripts/` directory (not management commands) or delete if work is confirmed done.
**Risk if left:** Low — running `enrich_stpm_metadata.py` again would make unnecessary Gemini API calls (costs money).
**Dependencies:** None.

### [TD-032] load_csv_data.py references original Streamlit data paths
**File(s):** `halatuju_api/apps/courses/management/commands/load_csv_data.py`
**What it is:** The CSV loader references data paths relative to the Streamlit app structure. It was used for the initial migration and shouldn't need to run again, but it's still a live management command.
**What consistent looks like:** Document as deprecated or move to scripts/.
**Risk if left:** Low — confusing but not dangerous.
**Dependencies:** None.

---

## Test Patterns and Coverage Gaps

### [TD-003] Zero frontend tests (LOW RISK)
**File(s):** `halatuju-web/` (entire frontend)
**What it is:** The Next.js frontend has zero test files. Remaining client-side logic is UI rendering and API calls — no business logic after TD-002 Sprint deleted `pathways.ts`, `merit.ts`, and `stpm.ts`.
**What consistent looks like:** Component tests for critical flows (onboarding, dashboard). Nice-to-have, not urgent.
**Risk if left:** LOW — all calculation logic now lives in the backend with 344 tests. Frontend is display-only.
**Dependencies:** Would need Jest/Vitest setup in halatuju-web.

### [TD-033] ~~Auth test failures not triaged~~ **RESOLVED (TD-010 Sprint, 2026-03-14)**
**File(s):** `halatuju_api/apps/courses/tests/test_auth.py`
**What it was:** Auth tests were failing due to incomplete mocking — triaged and fixed as part of TD-010.
**Resolution:** See TD-010 resolution.

### [TD-034] No integration test for full eligibility → ranking → report flow
**File(s):** `halatuju_api/apps/courses/tests/`
**What it is:** Tests cover individual components (engine, ranking, serializers) but there's no end-to-end test that sends a student profile through eligibility → ranking → report generation. This is the critical user path.
**What consistent looks like:** One integration test that exercises the full API flow with a realistic student profile.
**Risk if left:** Medium — individual units could pass while the integrated flow breaks.
**Dependencies:** None.

### [TD-035] Golden master count discrepancy ✅ RESOLVED (Test Health Sprint, 2026-03-14)
**File(s):** `halatuju_api/CLAUDE.md`, `.claude/ARCHITECTURE_MAP.md`
**What it was:** CLAUDE.md referenced golden master baselines as both "8280" and "8283" in different places. The architecture map said 8283.
**Resolution:** Old baseline (8283) was from stale CSV data. Golden master test was silently skipping for months because CSV files were deleted. Converted to DB fixtures, verified baseline is 5319 (matches production Supabase data). All references now say 5319.
**Dependencies:** None.

---

## Configuration and Environment Handling

### [TD-036] Hardcoded fallback SECRET_KEY in base.py ✅ RESOLVED (Security Sprint, 2026-03-14)
**File(s):** `halatuju_api/halatuju/settings/production.py`
**Resolution:** `production.py` now raises `ValueError` if `SECRET_KEY` equals the insecure dev default. Dev/test environments still use the fallback for convenience.

### [TD-037] db.sqlite3 in project folder
**File(s):** `halatuju_api/db.sqlite3`
**What it is:** Local development SQLite database is present in the project folder. It's in .gitignore but its presence in the working directory can confuse.
**What consistent looks like:** Store in a temp or data directory, not the project root.
**Risk if left:** Low — just clutter.
**Dependencies:** development.py database config.

### [TD-038] CORS_ALLOW_ALL_ORIGINS possible in production ✅ RESOLVED (Security Sprint, 2026-03-14)
**File(s):** `halatuju_api/halatuju/settings/production.py`
**Resolution:** `production.py` now raises `ValueError` if `CORS_ALLOWED_ORIGINS=*`. Must set explicit origin list.

### [TD-039] sentry-sdk pinned to <2.0
**File(s):** `halatuju_api/requirements.txt` (line 22)
**What it is:** `sentry-sdk>=1.39,<2.0` — Sentry SDK 2.x has been available since late 2024 with breaking changes. Staying on 1.x means missing performance improvements and eventual EOL.
**What consistent looks like:** Upgrade to sentry-sdk 2.x.
**Risk if left:** Low — 1.x still supported, but will eventually become unsupported.
**Dependencies:** Production monitoring.

### [TD-040] numpy pinned to <2.0
**File(s):** `halatuju_api/requirements.txt` (line 15)
**What it is:** `numpy>=1.24,<2.0` — NumPy 2.0 was released in June 2024. The <2.0 pin blocks security fixes and performance improvements. NumPy is imported by pandas but may not be directly used by HalaTuju code.
**What consistent looks like:** Test with numpy 2.x and update the pin.
**Risk if left:** Low — no immediate security issues, but aging dependency.
**Dependencies:** pandas compatibility.

---

## Missing Features / Stubs

### [TD-041] settings/page.tsx is a stub
**File(s):** `halatuju-web/src/app/settings/page.tsx`
**What it is:** The settings page only has a "Reset All Data" button that clears localStorage. No account management, no notification preferences, no data export.
**What consistent looks like:** Either flesh out with real settings or remove the nav link until ready.
**Risk if left:** Low — users see a nearly empty page.
**Dependencies:** None.

### [TD-042] No error.tsx, loading.tsx, or not-found.tsx pages
**File(s):** `halatuju-web/src/app/`
**What it is:** No custom error boundary, loading skeleton, or 404 page. Using Next.js defaults which show generic messages.
**What consistent looks like:** Custom error page with HalaTuju branding, helpful error messages in BM/EN/TA.
**Risk if left:** Low — functional but unprofessional UX.
**Dependencies:** i18n keys.

### [TD-043] Phone/OTP login blocked with "coming soon"
**File(s):** `halatuju-web/src/app/login/page.tsx`
**What it is:** Phone number login shows a "coming soon" message. Only Google OAuth works. This limits accessibility for students who don't have Google accounts.
**What consistent looks like:** WhatsApp OTP plan exists (`docs/plans/2026-03-09-whatsapp-otp-plan.md`) but not implemented.
**Risk if left:** Medium — blocks users without Google accounts.
**Dependencies:** Twilio/WhatsApp integration, ~RM12/month cost.

---

## Performance and Architecture

### [TD-044] EligibilityCheckView iterates entire DataFrame on every request
**File(s):** `halatuju_api/apps/courses/views.py` (lines 370-476)
**What it is:** Every eligibility check iterates ALL rows of the requirements DataFrame (389 courses), runs the full engine check for each, then sorts. For the PISMP deduplication, it iterates the DataFrame AGAIN (line 502).
**What consistent looks like:** Pre-filter DataFrame by obvious exclusions (nationality, gender) before full check. Cache deduplication hashes at startup.
**Risk if left:** Low — 389 rows is fast enough (~200ms), but doubles unnecessarily with the second iteration.
**Dependencies:** Golden master test must still pass.

### [TD-045] EligibilityCheckView.post() is 300+ lines
**File(s):** `halatuju_api/apps/courses/views.py` (lines 303-617)
**What it is:** The main eligibility endpoint method is over 300 lines long, handling: validation, merit calculation, engine loop, matric/STPM merit branching, PISMP deduplication, stats computation, sorting, pathway stats, and insights generation.
**What consistent looks like:** Extract sub-functions: `_compute_merit()`, `_build_eligible_list()`, `_deduplicate_pismp()`, `_sort_results()`.
**Risk if left:** Medium — hard to modify or debug any single aspect without reading the entire method.
**Dependencies:** None.

### [TD-046] CourseListView returns all 389 courses with no pagination
**File(s):** `halatuju_api/apps/courses/views.py` (lines 765-774)
**What it is:** `CourseListView.get()` returns ALL courses in a single response with no pagination. For 389 courses this is fine, but it's architecturally inconsistent with `CourseSearchView` which has pagination.
**What consistent looks like:** Add optional pagination or document that this endpoint is intentionally unpaginated.
**Risk if left:** Low — current dataset size is manageable.
**Dependencies:** Any frontend code using this endpoint.

### [TD-047] Startup data load is all-or-nothing
**File(s):** `halatuju_api/apps/courses/apps.py` (lines 30-50)
**What it is:** `CoursesConfig.ready()` loads all data at startup. If the database connection fails or tables don't exist, it logs a warning and the app starts with empty DataFrames. The first eligibility check then returns 503.
**What consistent looks like:** Health check endpoint that verifies data is loaded, with automatic retry.
**Risk if left:** Low — Cloud Run containers restart if they fail health checks.
**Dependencies:** None.

---

## Frontend-Specific Issues

### [TD-048] console.error calls in production code
**File(s):** `halatuju-web/src/app/course/[id]/page.tsx` (line 39), `halatuju-web/src/app/profile/page.tsx` (lines 88, 121, 135, 145), `halatuju-web/src/app/dashboard/page.tsx` (line 160), `halatuju-web/src/app/stpm/[id]/page.tsx` (line 35)
**What it is:** Error handling in catch blocks uses `console.error()` which shows in browser DevTools but provides no user feedback.
**What consistent looks like:** Show a toast/notification to the user AND log to an error tracking service.
**Risk if left:** Low — errors are swallowed from the user's perspective.
**Dependencies:** Would need a toast/notification component.

### [TD-049] `as any` type assertion in profile page
**File(s):** `halatuju-web/src/app/profile/page.tsx` (line 118)
**What it is:** `} as any, { token })` — a type assertion to `any` bypasses TypeScript safety.
**What consistent looks like:** Define the proper type for the API call parameter.
**Risk if left:** Low — single instance, but sets a bad precedent.
**Dependencies:** None.

### [TD-050] i18n locale key inconsistency
**File(s):** `halatuju-web/src/lib/i18n.tsx`, `halatuju-web/src/app/quiz/page.tsx` (lines 40, 149)
**What it is:** The i18n system uses `halatuju_locale` localStorage key, but the quiz page reads `halatuju_lang` (which doesn't exist — it will always get the default 'en'). These are different keys.
**What consistent looks like:** Use one key consistently. The quiz should use the i18n context's locale, not a separate localStorage read.
**Risk if left:** Medium — quiz may always load in English regardless of the user's language setting.
**Dependencies:** Quiz page, i18n context.

### [TD-051] STPM field metadata has 207 unique values
**File(s):** Database (stpm_courses.field column)
**What it is:** Gemini-generated field categories produced 207 unique values where ~30 were expected. This means field-based filtering and grouping on the search page returns overly specific categories.
**What consistent looks like:** Normalisation pass to map the 207 values to ~30 canonical categories.
**Risk if left:** Medium — search filters show too many field options, degrading UX.
**Dependencies:** Data migration needed.

### [TD-052] Hardcoded merit colour thresholds duplicated
**File(s):**
- Backend: `halatuju_api/apps/courses/views.py` (lines 411-416, 433-438)
- Backend: `halatuju_api/apps/courses/engine.py` (lines 196-201)
- Frontend: `halatuju-web/src/app/pathway/matric/page.tsx` (lines 99-101)
- Frontend: `halatuju-web/src/app/stpm/[id]/page.tsx` (lines 188)
**What it is:** Merit colour/label thresholds (High ≥ 94, Fair ≥ 89 for matric; High ≤ 12 for STPM) are hardcoded in both backend views and frontend pages. The merit probability thresholds (gap ≥ 0 = High, ≥ -5 = Fair) are in engine.py.
**What consistent looks like:** Define thresholds as named constants in one place per layer.
**Risk if left:** Low — easy to change one and forget the other.
**Dependencies:** Multiple files.

---

## Summary by Risk Level

### HIGH (8 items)
| ID | Title | Category | Status |
|----|-------|----------|--------|
| TD-001 | STPM SPM prerequisite fields not checked | Correctness bug | Resolved (Sprint 4) |
| TD-002 | Client-side eligibility logic duplicated | Duplication | Resolved (TD-002 Sprint) |
| TD-003 | Zero frontend tests | Test coverage | Downgraded to LOW (TD-002 Sprint removed all frontend business logic) |
| TD-007 | Bare except in engine.py | Error handling | Resolved (Sprint 4) |
| TD-010 | 9 pre-existing auth test failures | Test coverage | Resolved (TD-010 Sprint) |
| TD-012 | DEFAULT_PERMISSION_CLASSES is AllowAny | Security | Resolved (Security Sprint) |
| TD-045 | EligibilityCheckView.post() is 300+ lines | Maintainability | Resolved (Refactoring Sprint) |
| TD-050 | i18n locale key inconsistency (quiz language bug) | Correctness bug | Resolved (Sprint 4) |

### MEDIUM (22 items)
| ID | Title | Status |
|----|-------|--------|
| TD-008 | ProfileView accepts arbitrary fields without validation | Resolved (Security Sprint) |
| TD-009 | No rate limiting on Gemini API calls | Open |
| TD-011 | SupabaseIsAuthenticated returns 403 instead of 401 | Resolved (API Consistency Sprint) |
| TD-013 | Subject key naming split (5+ files to change) | Open |
| TD-014 | localStorage sprawl (20+ keys, no typing) | Open |
| TD-015 | Frontend/backend merit calculation may disagree | Resolved (TD-002 Sprint) |
| TD-016 | StpmProgrammeDetailView institution lookup by name | Open |
| TD-017 | Pre-U fit scoring exists only on frontend | Resolved (TD-002 Sprint) |
| TD-021 | PISMP deduplication logic inline and complex | Open |
| TD-033 | Auth test failures not triaged | Resolved (TD-010 Sprint) |
| TD-034 | No integration test for full flow | Open |
| TD-035 | Golden master count discrepancy in docs | Resolved (Test Health Sprint) |
| TD-038 | CORS_ALLOW_ALL_ORIGINS possible in production | Resolved (Security Sprint) |
| TD-043 | Phone/OTP login blocked | Open |
| TD-044 | EligibilityCheckView iterates DataFrame twice | Resolved (Refactoring Sprint) |
| TD-046 | CourseListView returns all courses unpaginated | Open |
| TD-048 | console.error in production with no user feedback | Open |
| TD-051 | STPM field metadata has 207 unique values | Open |
| TD-052 | Hardcoded merit thresholds duplicated across layers | Open |

### LOW (22 items)
| ID | Title | Status |
|----|-------|--------|
| TD-004 | Mixed HTTP status code style | Resolved (API Consistency Sprint) |
| TD-005 | No standard error response envelope | Open |
| TD-006 | Inconsistent success response keys (count vs total_count) | Open |
| TD-018 | Duplicate import of Count, Subquery, OuterRef | Resolved (Sprint 4) |
| TD-019 | Inline json import in views.py | Resolved (Sprint 4) |
| TD-020 | Duplicate credit_stv key in serializer | Resolved (Sprint 4) |
| TD-022 | Sort logic duplicated between search and eligibility | Open |
| TD-023 | Model field name vs engine key inconsistencies | Open |
| TD-024 | Course name field is just 'course' | Open |
| TD-025 | StudentProfile table name uses 'api_' prefix | Open |
| TD-026 | Inconsistent response field names for course name | Open |
| TD-027 | Legacy key mapping in engine.py | Open |
| TD-028 | CSV data files still in codebase | Open |
| TD-029 | Legacy Streamlit archive (246 files) | Open |
| TD-030 | Model docstring row counts are stale | Open |
| TD-031 | One-time scripts still in management commands | Open |
| TD-032 | load_csv_data.py references Streamlit paths | Open |
| TD-036 | Hardcoded fallback SECRET_KEY | Resolved (Security Sprint) |
| TD-037 | db.sqlite3 in project folder | Open |
| TD-039 | sentry-sdk pinned to <2.0 | Open |
| TD-040 | numpy pinned to <2.0 | Open |
| TD-041 | settings/page.tsx is a stub | Open |
| TD-042 | No custom error/loading/404 pages | Open |
| TD-047 | Startup data load is all-or-nothing | Open |
| TD-049 | `as any` type assertion | Open |

---

## Recommended Fix Order

**Sprint 1 — Critical correctness (1 session)**
- TD-001: Fix STPM SPM prerequisite check (add missing fields to SIMPLE_CHECKS)
- TD-050: Fix quiz language key (use i18n context instead of wrong localStorage key)
- TD-007: Fix bare except in engine.py
- TD-020: Remove duplicate credit_stv
- TD-018, TD-019: Clean up duplicate/inline imports

**Sprint 2 — Test foundation (1 session)**
- ~~TD-010, TD-033~~: Fixed — mock patch for `jwt.get_unverified_header`. See `docs/decisions.md`
- ~~TD-003~~: Downgraded to LOW — frontend has no business logic to test after TD-002
- TD-034: Add one integration test for full eligibility → ranking flow

**Sprint 3 — Security & error handling (1 session)**
- ~~TD-012, TD-008, TD-038, TD-036~~: RESOLVED — Security Hardening Sprint (2026-03-14)

**Sprint 4 — API consistency (1 session)**
- TD-004, TD-005, TD-006, TD-026: Standardise error/success response format
- TD-011: Fix 401 vs 403

**Sprint 5 — Frontend cleanup (1 session)**
- TD-014: Centralise localStorage into a typed store
- TD-048: Add user-facing error toasts
- TD-041, TD-042: Add custom error/404 pages, flesh out settings

**Sprint 6 — Architecture (1-2 sessions)**
- ~~TD-002, TD-015, TD-017~~: RESOLVED — backend is single source of truth, frontend files deleted
- TD-013: Subject key naming split (still open, lower risk)
- ~~TD-045~~: RESOLVED — EligibilityCheckView refactored, business logic extracted to eligibility_service.py
- TD-021: Refactor EligibilityCheckView into smaller functions (remaining cleanup if needed)

**Sprint 7-8 — Cleanup (1-2 sessions)**
- TD-028, TD-029, TD-031, TD-032: Archive/remove legacy files
- TD-030: Update stale docstrings
- TD-051: Normalise STPM field metadata
- TD-039, TD-040: Update dependency pins
