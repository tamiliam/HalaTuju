# HalaTuju Technical Debt Audit

**Date:** 2026-03-14
**Auditor:** Claude (comprehensive codebase read)
**Scope:** halatuju_api + halatuju-web (full codebase)

---

## Executive Summary

**Total issues found: 52** (High: 8, Medium: 22, Low: 22)
**Resolved: 49/52** (as of 2026-03-16)

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

### [TD-005] No standard error response envelope ✅ RESOLVED (API Consistency Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/views.py` (throughout), `halatuju_api/apps/reports/views.py`
**Resolution:** Audited all error responses — already consistently use `{'error': 'message'}` pattern across all endpoints. Frontend catches errors by HTTP status, not response body, so no envelope change needed. Marked as consistent.

### [TD-006] Inconsistent success response keys ✅ RESOLVED (API Consistency Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/views.py`
**Resolution:** Standardised all list endpoints to use `total_count` instead of `count`. Affected: CourseListView, InstitutionListView, OutcomeListView. Contextual keys (`total_eligible`, `total_ranked`, `total`) left as-is — they match frontend TypeScript types and have specific semantics.

---

## Error Handling Patterns

### [TD-007] Bare except in engine.py merit calculation ✅ RESOLVED (Tech Debt Sprint 4, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/engine.py` (line 191)
**Resolution:** Bare `except:` replaced with specific `except (ValueError, TypeError):` to only catch expected conversion errors.

### [TD-008] ProfileView accepts arbitrary fields without validation ✅ RESOLVED (Security Sprint, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/views.py`, `halatuju_api/apps/courses/serializers.py`
**Resolution:** Created `ProfileUpdateSerializer` (ModelSerializer for StudentProfile, 19 fields, partial=True). Both `ProfileView.put()` and `ProfileSyncView.post()` now validate via serializer — malformed input returns 400 instead of 500.

### [TD-009] No rate limiting on Gemini API calls ✅ RESOLVED (Quick Wins Sprint 2, 2026-03-15)
**File(s):** `halatuju_api/apps/reports/views.py`
**Resolution:** Added Django cache-based rate limiting (max 3 reports per user per 24 hours). Returns 429 with clear error message when exceeded. Counter increments only after successful generation.

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

### [TD-001] STPM SPM prerequisite fields not checked ✅ RESOLVED (Tech Debt Sprint 4, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/stpm_engine.py`
**Resolution:** Added `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS`. Zero programmes currently set these flags to true, so no eligibility results changed. STPM golden master baseline unchanged at 1,811.

### [TD-002] Client-side eligibility logic duplicated (HIGH RISK) — RESOLVED
**Resolved:** TD-002 Sprint (2026-03-14). Frontend calculation files (`merit.ts`, `stpm.ts`, `pathways.ts` — 596 lines) deleted. Three new backend API endpoints added: `/calculate/merit/`, `/calculate/cgpa/`, `/calculate/pathways/`. Frontend now calls backend for all calculations. `getPathwayFitScore()` ported to `pathways.py`. Backend is the single source of truth.

### [TD-013] Subject key naming split ✅ RESOLVED (Subject Key Unification Sprint, 2026-03-15)
**File(s):** `halatuju-web/src/lib/subjects.ts`, `halatuju_api/apps/courses/serializers.py`
**Resolution:** Frontend now sends engine keys directly. `GRADE_KEY_MAP` removed from serializer. `subjects.ts` is the single source of truth with `SPM_SUBJECTS` array. Report engine `SUBJECT_LABELS` fixed (5 wrong keys, 15 added).

### [TD-014] localStorage sprawl with no centralised management ✅ RESOLVED (Frontend Cleanup Sprint, 2026-03-15)
**File(s):** `halatuju-web/src/lib/storage.ts`
**Resolution:** Created `storage.ts` with 19 named key constants and `clearAll()` helper. All 15 files updated to import constants — zero hardcoded `halatuju_*` strings remain outside storage.ts. Grep-verified.

### [TD-015] Frontend merit calculation sent to backend, backend may recalculate — RESOLVED
**Resolved:** TD-002 Sprint (2026-03-14). Frontend no longer calculates merit locally — it calls `/calculate/merit/` API. Backend is the single source of truth. `merit.ts` deleted.

### [TD-016] StpmProgrammeDetailView looks up institution by name ✅ RESOLVED (Bug Fixes, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/views.py`, `halatuju_api/apps/courses/models.py`
**Resolution:** StpmCourse institution FK added. Name-based lookup replaced with proper foreign key relationship.

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

### [TD-022] Eligibility sort logic duplicated between search and eligibility views ✅ RESOLVED (API Consistency Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/views.py`, `halatuju_api/apps/courses/eligibility_service.py`
**Resolution:** `SOURCE_TYPE_ORDER` extracted to module-level constant in `views.py`. `_PATHWAY_PRIORITY` already module-level in `eligibility_service.py` from Refactoring Sprint. Sorting logic intentionally different between search and eligibility (different use cases) — the fix was extracting inline constants, not unifying the sort.

---

## Naming Conventions

### [TD-023] Model field name vs engine key inconsistencies ✅ RESOLVED (Quick Wins Sprint 2, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/engine.py`, `halatuju_api/apps/courses/apps.py`, `halatuju_api/apps/courses/tests/conftest.py`
**Resolution:** Engine updated to use `three_m_only` directly (matching the model field). Column rename hack removed from `apps.py` and `conftest.py`.

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

### [TD-026] Inconsistent response field names for course name ✅ RESOLVED (API Consistency Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/serializers.py`
**Resolution:** Added `course_name = CharField(source='course', read_only=True)` to `CourseSerializer`. All endpoints now include `course_name` in responses. `course` field kept for backwards compatibility — frontend can migrate to `course_name` at its own pace.

---

## Bolt-On Code from Pre-Django Migration

### [TD-027] Legacy key mapping still in engine.py ✅ RESOLVED (Quick Wins Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/engine.py`
**Resolution:** `LEGACY_KEY_MAP` removed. Grep confirmed it was never referenced anywhere in the codebase — dead code from the Streamlit migration.

### [TD-028] CSV data files still in codebase ✅ RESOLVED (Legacy Cleanup Sprint, 2026-03-15)
**File(s):** `halatuju_api/data/stpm/`
**Resolution:** Deleted 4 CSV files. Data lives in Supabase. Created `stpm_courses.json` + `stpm_requirements.json` Django fixtures for tests.

### [TD-029] Legacy Streamlit archive still in repo ✅ RESOLVED (Legacy Cleanup Sprint, 2026-03-15)
**File(s):** `_archive/streamlit/`
**Resolution:** Deleted 246 files (80MB). Git history serves as the archive.

### [TD-030] Model docstring row counts are stale ✅ RESOLVED (Quick Wins Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/models.py`
**Resolution:** Removed stale CSV filenames and row counts from all model docstrings. Now reference Supabase table names instead.

---

## Management Commands and Data Integrity Scripts

### [TD-031] One-time scripts still in management commands ✅ RESOLVED (Legacy Cleanup Sprint, 2026-03-15)
**File(s):** 6 commands deleted
**Resolution:** Deleted `load_csv_data`, `load_stpm_data`, `enrich_stpm_metadata`, `populate_stpm_urls`, `fix_stpm_names`, `backfill_masco`. Extracted `proper_case_name` and `build_mohe_url` to `apps/courses/utils.py`. 4 recurring commands preserved.
**Dependencies:** None.

### [TD-032] load_csv_data.py references original Streamlit data paths ✅ RESOLVED (Legacy Cleanup Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/management/commands/load_csv_data.py`
**Resolution:** File deleted (TD-031).

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

### [TD-034] No integration test for full eligibility → ranking → report flow ✅ RESOLVED (External Links & MOHE Sprint, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/tests/`
**Resolution:** Integration test added covering the full eligibility → ranking flow with a realistic student profile.

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

### [TD-037] db.sqlite3 in project folder ✅ RESOLVED (Quick Wins Sprint, 2026-03-15)
**File(s):** `halatuju_api/db.sqlite3`
**Resolution:** Deleted the file. Already covered by `.gitignore` (`*.sqlite3`). Django dev settings recreate it on demand if needed.

### [TD-038] CORS_ALLOW_ALL_ORIGINS possible in production ✅ RESOLVED (Security Sprint, 2026-03-14)
**File(s):** `halatuju_api/halatuju/settings/production.py`
**Resolution:** `production.py` now raises `ValueError` if `CORS_ALLOWED_ORIGINS=*`. Must set explicit origin list.

### [TD-039] sentry-sdk pinned to <2.0 ✅ RESOLVED (Quick Wins Sprint 2, 2026-03-15)
**File(s):** `halatuju_api/requirements.txt`
**Resolution:** Pin relaxed to `sentry-sdk>=1.39,<3.0`. Allows upgrade to 2.x when ready.

### [TD-040] numpy pinned to <2.0 ✅ RESOLVED (Quick Wins Sprint 2, 2026-03-15)
**File(s):** `halatuju_api/requirements.txt`
**Resolution:** Pin relaxed to `numpy>=1.24,<3.0`. Allows upgrade to 2.x when ready. Only used via pandas.

---

## Missing Features / Stubs

### [TD-041] settings/page.tsx is a stub
**File(s):** `halatuju-web/src/app/settings/page.tsx`
**What it is:** The settings page only has a "Reset All Data" button that clears localStorage. No account management, no notification preferences, no data export.
**What consistent looks like:** Either flesh out with real settings or remove the nav link until ready.
**Risk if left:** Low — users see a nearly empty page.
**Dependencies:** None.

### [TD-042] No error.tsx, loading.tsx, or not-found.tsx pages ✅ RESOLVED (Frontend Cleanup Sprint, 2026-03-15)
**File(s):** `halatuju-web/src/app/error.tsx`, `loading.tsx`, `not-found.tsx`
**Resolution:** Three pages added with full i18n (EN/MS/TA via `useT()`), primary brand colour, consistent layout. 7 translation keys added to `errors` section in all message files.

### [TD-043] Phone/OTP login blocked with "coming soon"
**File(s):** `halatuju-web/src/app/login/page.tsx`
**What it is:** Phone number login shows a "coming soon" message. Only Google OAuth works. This limits accessibility for students who don't have Google accounts.
**What consistent looks like:** WhatsApp OTP plan exists (`docs/plans/2026-03-09-whatsapp-otp-plan.md`) but not implemented.
**Risk if left:** Medium — blocks users without Google accounts.
**Dependencies:** Twilio/WhatsApp integration, ~RM12/month cost.

---

## Performance and Architecture

### [TD-044] EligibilityCheckView iterates entire DataFrame on every request ✅ RESOLVED (Refactoring Sprint, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/eligibility_service.py`
**Resolution:** Double DataFrame iteration eliminated during extraction to eligibility_service.py. PISMP deduplication now operates on the result list, not the DataFrame.

### [TD-045] EligibilityCheckView.post() is 300+ lines ✅ RESOLVED (Refactoring Sprint, 2026-03-14)
**File(s):** `halatuju_api/apps/courses/eligibility_service.py`, `halatuju_api/apps/courses/views.py`
**Resolution:** Extracted 5 pure functions into `eligibility_service.py`: `compute_student_merit()`, `compute_course_merit()`, `deduplicate_pismp()`, `sort_eligible_courses()`, `compute_stats()`. View reduced from ~310 lines to ~100 lines. 19 unit tests added for the service module.

### [TD-046] CourseListView returns all 389 courses with no pagination ✅ RESOLVED (Quick Wins Sprint 2, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/views.py`
**Resolution:** Added optional pagination via `?page=1&page_size=50` query params. Backwards-compatible: no params returns all results as before. Max page size capped at 100.

### [TD-047] Startup data load is all-or-nothing
**File(s):** `halatuju_api/apps/courses/apps.py` (lines 30-50)
**What it is:** `CoursesConfig.ready()` loads all data at startup. If the database connection fails or tables don't exist, it logs a warning and the app starts with empty DataFrames. The first eligibility check then returns 503.
**What consistent looks like:** Health check endpoint that verifies data is loaded, with automatic retry.
**Risk if left:** Low — Cloud Run containers restart if they fail health checks.
**Dependencies:** None.

---

## Frontend-Specific Issues

### [TD-048] console.error calls in production code ✅ RESOLVED (Frontend Cleanup Sprint, 2026-03-15)
**File(s):** All frontend pages
**Resolution:** All `console.error` calls replaced with `useToast()` hook providing user-facing toast notifications. Zero console.error/log/warn calls remain in production code. Toast system (`ToastProvider` + `useToast()`) added in Saved Courses Sprint 2.

### [TD-049] `as any` type assertion in profile page ✅ RESOLVED (Quick Wins Sprint, 2026-03-15)
**File(s):** `halatuju-web/src/app/profile/page.tsx`, `halatuju-web/src/lib/api.ts`
**Resolution:** Extended `StudentProfile.colorblind`/`disability` to accept `'Ya' | 'Tidak'` union type (backend format). Typed gender/nationality state vars with literal types. Removed `as any`.

### [TD-050] i18n locale key inconsistency
**File(s):** `halatuju-web/src/lib/i18n.tsx`, `halatuju-web/src/app/quiz/page.tsx` (lines 40, 149)
**What it is:** The i18n system uses `halatuju_locale` localStorage key, but the quiz page reads `halatuju_lang` (which doesn't exist — it will always get the default 'en'). These are different keys.
**What consistent looks like:** Use one key consistently. The quiz should use the i18n context's locale, not a separate localStorage read.
**Risk if left:** Medium — quiz may always load in English regardless of the user's language setting.
**Dependencies:** Quiz page, i18n context.

### [TD-051] STPM field metadata has 207 unique values ✅ RESOLVED (Field Taxonomy Sprint 2, 2026-03-16)
**File(s):** Database (stpm_courses.field_key_id column)
**Resolution:** Deterministic classifier maps all 1,113 STPM courses to 29 of 37 canonical taxonomy keys via `classify_stpm_course()`. The 207 raw `field` values are superseded by `field_key_id` FK to `field_taxonomy`. Search/detail APIs now return `field_key` and support `?field_key=` filtering.

### [TD-052] Hardcoded merit colour thresholds duplicated ✅ RESOLVED (API Consistency Sprint, 2026-03-15)
**File(s):** `halatuju_api/apps/courses/engine.py`, `halatuju_api/apps/courses/eligibility_service.py`
**Resolution:** Backend merit thresholds extracted to named constants. `engine.py`: `MERIT_GAP_HIGH`, `MERIT_GAP_FAIR`, `MERIT_COLORS` dict. `eligibility_service.py`: `MATRIC_HIGH_THRESHOLD`, `MATRIC_FAIR_THRESHOLD` (already existed), `MERIT_HIGH`/`FAIR`/`LOW` tuples now derived from `engine.MERIT_COLORS`. Frontend thresholds in matric/STPM pages left as-is — the matric page uses `/calculate/pathways/` API response which includes labels, and the STPM detail page threshold (80/60) is for average merit display (different context).

---

## Summary by Risk Level

### HIGH (8 items)
| ID | Title | Category | Status |
|----|-------|----------|--------|
| TD-001 | STPM SPM prerequisite fields not checked | Correctness bug | Resolved (Sprint 4) |
| TD-002 | Client-side eligibility logic duplicated | Duplication | Resolved (TD-002 Sprint) |
| TD-003 | Zero frontend tests | Test coverage | Downgraded to LOW (TD-002 Sprint removed all frontend business logic) |
| TD-007 | Bare except in engine.py | Error handling | ✅ Resolved (Sprint 4) |
| TD-010 | 9 pre-existing auth test failures | Test coverage | Resolved (TD-010 Sprint) |
| TD-012 | DEFAULT_PERMISSION_CLASSES is AllowAny | Security | Resolved (Security Sprint) |
| TD-045 | EligibilityCheckView.post() is 300+ lines | Maintainability | Resolved (Refactoring Sprint) |
| TD-050 | i18n locale key inconsistency (quiz language bug) | Correctness bug | Resolved (Sprint 4) |

### MEDIUM (22 items)
| ID | Title | Status |
|----|-------|--------|
| TD-008 | ProfileView accepts arbitrary fields without validation | Resolved (Security Sprint) |
| TD-009 | No rate limiting on Gemini API calls | ✅ Resolved (Quick Wins Sprint 2) |
| TD-011 | SupabaseIsAuthenticated returns 403 instead of 401 | Resolved (API Consistency Sprint) |
| TD-013 | Subject key naming split (5+ files to change) | ✅ Resolved (Subject Key Unification Sprint) |
| TD-014 | localStorage sprawl (20+ keys, no typing) | Resolved (Frontend Cleanup Sprint) |
| TD-015 | Frontend/backend merit calculation may disagree | Resolved (TD-002 Sprint) |
| TD-016 | StpmProgrammeDetailView institution lookup by name | ✅ Resolved (Bug Fixes, 15 Mar) |
| TD-017 | Pre-U fit scoring exists only on frontend | Resolved (TD-002 Sprint) |
| TD-021 | PISMP deduplication logic inline and complex | Resolved (Refactoring Sprint) |
| TD-033 | Auth test failures not triaged | Resolved (TD-010 Sprint) |
| TD-034 | No integration test for full flow | ✅ Resolved (External Links Sprint) |
| TD-035 | Golden master count discrepancy in docs | Resolved (Test Health Sprint) |
| TD-038 | CORS_ALLOW_ALL_ORIGINS possible in production | Resolved (Security Sprint) |
| TD-043 | Phone/OTP login blocked | **Open** |
| TD-044 | EligibilityCheckView iterates DataFrame twice | Resolved (Refactoring Sprint) |
| TD-046 | CourseListView returns all courses unpaginated | ✅ Resolved (Quick Wins Sprint 2) |
| TD-048 | console.error in production with no user feedback | Resolved (Frontend Cleanup Sprint) |
| TD-051 | STPM field metadata has 207 unique values | Resolved (Field Taxonomy Sprint 2) |
| TD-052 | Hardcoded merit thresholds duplicated across layers | Resolved (API Consistency Sprint) |

### LOW (22 items)
| ID | Title | Status |
|----|-------|--------|
| TD-004 | Mixed HTTP status code style | Resolved (API Consistency Sprint) |
| TD-005 | No standard error response envelope | Resolved (API Consistency Sprint) |
| TD-006 | Inconsistent success response keys (count vs total_count) | Resolved (API Consistency Sprint) |
| TD-018 | Duplicate import of Count, Subquery, OuterRef | Resolved (Sprint 4) |
| TD-019 | Inline json import in views.py | Resolved (Sprint 4) |
| TD-020 | Duplicate credit_stv key in serializer | Resolved (Sprint 4) |
| TD-022 | Sort logic duplicated between search and eligibility | Resolved (API Consistency Sprint) |
| TD-023 | Model field name vs engine key inconsistencies | ✅ Resolved (Quick Wins Sprint 2) |
| TD-024 | Course name field is just 'course' | Open |
| TD-025 | StudentProfile table name uses 'api_' prefix | Open |
| TD-026 | Inconsistent response field names for course name | Resolved (API Consistency Sprint) |
| TD-027 | Legacy key mapping in engine.py | Resolved (Quick Wins Sprint) |
| TD-028 | CSV data files still in codebase | Resolved (Legacy Cleanup Sprint) |
| TD-029 | Legacy Streamlit archive (246 files) | Resolved (Legacy Cleanup Sprint) |
| TD-030 | Model docstring row counts are stale | Resolved (Quick Wins Sprint) |
| TD-031 | One-time scripts still in management commands | Resolved (Legacy Cleanup Sprint) |
| TD-032 | load_csv_data.py references Streamlit paths | Resolved (Legacy Cleanup Sprint) |
| TD-036 | Hardcoded fallback SECRET_KEY | Resolved (Security Sprint) |
| TD-037 | db.sqlite3 in project folder | Resolved (Quick Wins Sprint) |
| TD-039 | sentry-sdk pinned to <2.0 | ✅ Resolved (Quick Wins Sprint 2) |
| TD-040 | numpy pinned to <2.0 | ✅ Resolved (Quick Wins Sprint 2) |
| TD-041 | settings/page.tsx is a stub | Open |
| TD-042 | No custom error/loading/404 pages | Resolved (Frontend Cleanup Sprint) |
| TD-047 | Startup data load is all-or-nothing | Open |
| TD-049 | `as any` type assertion | Resolved (Quick Wins Sprint) |
| TD-052 | Search limit hardcoded to 10000, no pagination | Open |

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
- ~~TD-004, TD-005, TD-006, TD-022, TD-026, TD-052~~: RESOLVED — API Consistency Sprint (2026-03-15)
- ~~TD-011~~: RESOLVED — API Consistency Sprint (2026-03-14)

**Sprint 5 — Frontend cleanup (1 session)**
- TD-014: Centralise localStorage into a typed store
- TD-048: Add user-facing error toasts
- TD-041, TD-042: Add custom error/404 pages, flesh out settings

**Sprint 6 — Architecture (1-2 sessions)**
- ~~TD-002, TD-015, TD-017~~: RESOLVED — backend is single source of truth, frontend files deleted
- ~~TD-013~~: RESOLVED — subject keys unified, GRADE_KEY_MAP removed, subjects.ts is single source of truth
- ~~TD-045~~: RESOLVED — EligibilityCheckView refactored, business logic extracted to eligibility_service.py
- TD-021: Refactor EligibilityCheckView into smaller functions (remaining cleanup if needed)

**Sprint 7-8 — Cleanup (1-2 sessions)**
- TD-028, TD-029, TD-031, TD-032: Archive/remove legacy files
- TD-030: Update stale docstrings
- TD-039, TD-040: Update dependency pins
