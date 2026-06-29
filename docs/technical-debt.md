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

### [TD-025] StudentProfile table name uses 'api_' prefix ✅ RESOLVED (2026-06-01)
**File(s):** `halatuju_api/apps/courses/models.py`
**What it was:** `db_table = 'api_student_profiles'` — the `api_` prefix was added to avoid collision with the legacy Streamlit `student_profiles` table. The two same-purpose-looking tables were an active footgun: in v2.21.0 a migrate-first `ALTER` silently hit the wrong (legacy 30-row) table instead of the live `api_student_profiles` — caught pre-deploy, but a miss would have 500'd prod.
**Resolution:** Dropped the dead legacy `public.student_profiles` table (30 Streamlit-era rows, 19 cols) via Supabase MCP — **not** a Django-managed table (the model owns `api_student_profiles`), so no migration/deploy. Pre-drop verified: zero incoming FKs, zero live code references (every runtime query uses `api_student_profiles`; bare `student_profiles` only appeared in docs/comments + the historical `courses/0001` migration that `0002` already renamed), zero view/trigger/RLS dependencies. The 30 rows were backed up first to `halatuju_api/docs/backups/student_profiles_legacy_backup_2026-06-01.json` (full schema + data). **The footgun is now gone:** a mistaken raw `ALTER student_profiles` would now error loudly ("relation does not exist") instead of silently succeeding against a real table. The `api_` prefix is retained as the canonical name (a rename was deemed not worth the churn — RLS policies, raw SQL, and migration history all reference `api_student_profiles`).

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

### [TD-003] Zero frontend tests (LOW RISK) — PARTIALLY RESOLVED
**File(s):** `halatuju-web/` (entire frontend)
**What it is:** The Next.js frontend had zero test files. After IC Gate Sprint (2026-03-15), 17 frontend tests exist. Remaining client-side logic is UI rendering and API calls — no business logic after TD-002 Sprint deleted `pathways.ts`, `merit.ts`, and `stpm.ts`.
**What consistent looks like:** Component tests for critical flows (onboarding, dashboard). Nice-to-have, not urgent.
**Risk if left:** LOW — all calculation logic now lives in the backend with 966 tests. Frontend is display-only. Auth flow refactored (2026-03-20) to eliminate localStorage as routing authority, further reducing frontend complexity.
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
**Resolution:** Extended `StudentProfile.colorblind`/`disability` to accept `'Ya' | 'Tidak'` union type (backend format). Typed gender/nationality state vars with literal types. Removed `as any`. **UPDATE (i18n & Bug Fixes Sprint, 2026-03-19):** Backend converted to BooleanField, frontend types updated to `boolean`. Union type removed — booleans flow end-to-end with zero conversion layers.

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

**B40 Redesign (found Sprint 7, 2026-05-23)**
- TD-053: Reconcile the NRIC-gate whitelist — `middleware/supabase_auth.py` `NRIC_GATE_EXACT` omits `/api/v1/profile/sync/`, but `docs/decisions.md` + `test_nric_gate` describe sync as whitelisted. Suite green (no breakage); align code/docs/tests.
- ~~TD-054~~: **RESOLVED — S11a (2026-05-24).** NRIC uniqueness is now enforced at the admin verify-&-accept point (`AdminVerifyAcceptView` returns `409 nric_conflict` if another profile already has that NRIC verified), per the soft-NRIC "clash surfaces at verification" design. The old claim transfer-path collision is no longer the uniqueness mechanism.

**B40 Redesign (found Sprint 9, 2026-05-24)**
- TD-055: Apply submit overwrites the whole `profile.guardians` list with the single `{name, phone}` entry from My Family. Fine today (guardians collected nowhere else), but if a future flow stores multiple/richer guardians, the apply form would clobber them. Merge-by-index or key on relationship when guardians become multi-entry.
- ~~TD-056~~: **RESOLVED — 2026-05-28.** All real partner-org codes in the /apply dropdown now have backing `PartnerOrganisation` rows seeded on prod via Supabase MCP: `smc`, `cumig`, `ewrf`, `hyo`, `mhm`, `sathya_sai`, `tara`, `hss`, `pptm` (9 total — 6 added with the new-orgs-pass in 8d6a07b, then the remaining 3 in a cleanup pass the same day). The `referred_by_org` FK now links cleanly for any of those selections. The remaining dropdown codes (`pushparani`, `govind`, `halatuju`, `social`, `other`) are intentionally **NOT** in `partner_organisations` — they're individual coordinators, self-referral, or generic catch-alls, not organisations. For those, `referral_source` carries the raw code and `referred_by_org` stays null by design. Original finding ↓ — TD-056: Seed `PartnerOrganisation` rows for the named referring-orgs (smc, cumig, pushparani, sathya_sai, halatuju, tara, govind). Until seeded, a selection persists as `referral_source` (raw code) but does **not** link the `referred_by_org` FK. Add a seed/data-migration (or admin entries) before launch so partner attribution works.
- TD-057: The apply→onboarding "return" marker (`halatuju_apply_return`, sessionStorage) can go stale if the student **abandons** the results-edit detour mid-flow and then starts a *normal* onboarding in the same tab — the final step would wrongly route to `/scholarship/apply` instead of `/dashboard`. Mitigated (orphan cleared on any normal apply-page visit; sessionStorage clears on tab close) but not eliminated for the abandon→dashboard→onboarding path. Clean fix: thread the return intent as a query param through the onboarding steps instead of a persistent flag, or clear the marker on a dashboard visit.

**B40 Plans redesign (found P5 ship, 2026-05-27)**
- TD-058: The **prod DB has no `django_content_type` / auth tables** (the contenttypes/admin apps' tables were never created on this Supabase instance). Harmless today — the app doesn't use contenttypes/admin/permissions at runtime, and additive `ADD COLUMN` migrations succeed — but `manage.py migrate` **exits non-zero** (the `post_migrate` create_contenttypes/create_permissions signal errors), and **any future migration that creates a new model (or code relying on contenttypes/permissions) would fail in prod**. Fix before such a migration: run `migrate contenttypes` + `migrate auth` against prod (or `migrate --run-syncdb`) to create the missing tables, after confirming no clash. Until then, treat a non-zero migrate exit as "verify the schema directly," not "it failed". (See lessons.md + retrospective-b40-plans-redesign.md.) **Status: MANAGED, not fixed.** The MCP migrate-first workaround is the standing practice and has fully absorbed this — we apply the migration's DDL + INSERT the `django_migrations` row via Supabase MCP `execute_sql` in one transaction (replicating what Django's executor would do), which never invokes `post_migrate`, so there's no non-zero exit and no contenttypes dependency. **This now covers NEW-MODEL migrations too, not just additive `ADD COLUMN`:** a new model is applied as a raw `CREATE TABLE` (+ RLS deny-by-default + the `django_migrations` row) — proven repeatedly, incl. `scholarship 0011` (additive, v2.3.0) and the new-model migrations **`0031` (E1a Sponsor), `0033` (E2a anon-pool cols), `0034` (E3a Donation/Sponsorship)** this Phase-E cycle. So the earlier caveat that "a new-model migration still needs the contenttypes/auth tables created first" is **superseded** — raw `CREATE TABLE` doesn't touch contenttypes, so we never created those tables and don't need to. **The only thing that still bites:** someone runs `manage.py migrate` for a new model **without** the workaround (e.g. a CI/local migrate against prod) — the `post_migrate` `create_contenttypes`/`create_permissions` signal would error. Real fix (if ever wanted): `migrate contenttypes` + `migrate auth` (or `--run-syncdb`) against prod once, after confirming no clash — but as long as every schema change goes through MCP migrate-first, this never fires. Treat a non-zero `migrate` exit as "verify the schema directly," not "it failed".
- ~~TD-060~~: **RESOLVED — S5c (v2.4.6, 2026-05-28).** `profile_engine._build_prompt` rebuilt to the current (profile-canonical) data model + "Your story" narrative + simplified funding (no dead `total`) + referees, and made language-aware (understands Malay/English/Tamil input; output in a target language, default applicant locale, admin EN/BM selector). New `test_profile_engine.py` includes the no-`AttributeError`-on-current-model regression. Original finding ↓ — TD-060: **The AI sponsor-profile generator (`apps/scholarship/profile_engine.py`) is stale and would error if invoked.** `_build_prompt` reads `application.qualification` / `spm_a_count` / `household_income` / `stpm_pngk` — all **removed** from the model by the profile-canonical refactor (now live on `StudentProfile`) — plus legacy/dead fields `intended_pathway` (→ `pathways_considered`/`chosen_programme`), `fears`, `justification`, and `fn.total` (TD-059). `_build_prompt` runs **before** the try/except in `generate_sponsor_profile`, so a real call (with `GEMINI_API_KEY` set) raises `AttributeError` → `AdminGenerateProfileView` 500s. **Masked today** because the programme is dormant and Phase-2 sponsor profiles aren't live (without a key it returns "not configured" before `_build_prompt`). Also English-only by design. **Fix = S5c:** rewrite `_build_prompt` to profile-canonical fields (`profile.exam_type`, `count_spm_a_grades`, `profile.stpm_cgpa`, `profile.household_income/size`, `receives_str/jkm`) + new story fields (`first_in_family`, `parents_occupation`, `family_context`, `daily_life`, `aspirations`, `plans`) + new funding (`categories`/`funding_note`/`programme_months`, not `total`) + referees; and make it **Tamil/BM-aware** (target-language param; handle Tamil/BM narrative input). Found during S5b scoping (2026-05-28).
- ~~TD-059~~: **RESOLVED — v2.4.7, 2026-05-28.** Dropped on prod via Supabase MCP under the expand-contract pattern (new code deployed first so the live `FundingNeedSerializer` no longer exposed the columns, then `ALTER TABLE funding_needs DROP COLUMN ×9` + `django_migrations` row for `0015_drop_funding_amount_fields`). 0 rows pre-drop confirmed. `funding_needs` now has exactly 7 columns: `id`, `created_at`, `updated_at`, `application_id`, `categories`, `funding_note`, `programme_months`. `FundingNeedSerializer.fields` shrunk to the 3 kept; `total` property + frontend `DetailsFormState` amount fields + `fundingTotal` helper + admin `RM${funding_need.total}` display all gone. Original finding ↓ — TD-059: **`FundingNeed` legacy amount columns are dead after the S3 funding reframe (v2.4.2).** `tuition_gap`, `laptop`, `hostel`, `transport`, `books`, `other`, `monthly_allowance`, `allowance_months` (+ the `total` property) are no longer written or rendered — the funding tab now uses `categories`/`funding_note`/`programme_months` only. Kept in place (additive migration `0013`, 0 prod rows) to avoid a non-backward-compatible drop mid-redesign. Cleanup: once the redesign ships fully (post-S5), drop the dead columns in one migration + remove them from `FundingNeedSerializer`/`DetailsFormState`/`fundingTotal`. Low risk (no data, no readers).

- TD-061: **/profile + /application schema consolidation — drop 4 dead columns** (`StudentProfile.family_income`, `StudentProfile.siblings`, `StudentProfile.phone`, **`ScholarshipApplication.siblings_studying`**). The first three were replaced 2026-05-29 (S14) by their canonical equivalents on the profile (`household_income`, `household_size`, `contact_phone`); the fourth was replaced 2026-05-29 (S15) by `ScholarshipApplication.siblings_studying_count` which captures the actual number rather than just a yes/no signal. Frontend stopped writing all four dead columns and the backfills have run: `household_income` populated from `family_income` range midpoints (41 rows), `household_size = siblings + 2` where missing (42 rows), `phone` promotion was a no-op (the 6 dead-phone rows all already have `contact_phone`); `siblings_studying_count` backfill was a no-op (0 applications had `siblings_studying = TRUE` at the time the new column landed). Old columns kept these sprints to keep the migrations backward-compatible during deploy. **Next session:** destructive migration + serializer cleanup, expand-contract pattern (deploy-first / DROP-after), zero data loss expected. Touches: `ProfileUpdateSerializer.Meta.fields` (3 cols), `ProfileView.get` response keys (3 cols), `ApplicationDetailsUpdateSerializer` (1 col), `_DEEPER_FIELDS` (1 col), `ApplicationReadSerializer` fields (1 col), `profile_engine._siblings_studying_display` (drop the boolean fallback), `api.ts` types (4 cols), the courses `StudentProfile` + scholarship `ScholarshipApplication` models, and two drop migrations (one per app).
  - ✅ **RESOLVED (v2.14.0, 2026-05-30).** Dropped all four columns under expand-contract (deploy-first / DROP-after; migrations `courses/0050` + `scholarship/0022` applied via Supabase MCP after the no-field revision went live). Repointed every reader/writer to the canonical fields (the "expand" step had never actually been finished — these columns were still wired into `/profile` GET + update serializer, both admin serializers, the CSV export, the AI prompt, and several FE consumers). **Fixed a latent bug found in the process:** `/profile` read/wrote `household_income`/`household_size` but the GET response + `ProfileUpdateSerializer` still listed the *legacy* `family_income`/`siblings`, so `/profile` edits to household income/size were silently dropped — only `/apply` could write them. Full backend 1249 pass; jest 155; build clean. See `docs/decisions.md`.

- TD-062: **Orphaned Supabase Storage blobs from pre-fix doc deletions.** Before today's single-instance-doc fix, the `DELETE /api/v1/scholarship/documents/<id>/` endpoint dropped the DB row but did NOT sweep the corresponding object in the `b40-documents` private bucket. Elanjelian's test account left ~3-4 orphan IC blobs (storage_paths matching the deleted doc IDs 1, 3, 4); other applicants who clicked Remove similarly leaked. The going-forward path is now clean (both DELETE and the new single-instance replace path call `storage.delete_objects`), so this only covers historical leaks. Cheap: write a one-shot management command that lists every object in the bucket via the Supabase Storage REST API and deletes any whose path doesn't correspond to an existing `applicant_documents.storage_path` row. Storage is cheap so this is low priority — flagging so we don't forget when we look at storage costs.
  - ✅ **RESOLVED (v2.14.0, 2026-05-30).** Built `manage.py cleanup_orphan_blobs` (+ `storage.list_objects` helper): walks the bucket, diffs leaf paths against `ApplicantDocument.storage_path`, dry-run by default / `--apply` to delete. 3 tests (mocked Storage). Running `--apply` against prod to actually purge the historical orphans is a separate manual step — the tool is in place.
  - ✅ **PURGE RUN — fully closed (2026-06-01).** Swept the historical orphans against prod. To dodge the wrong-DB footgun entirely, the diff used the known-paths set pulled from the **prod DB via Supabase MCP** (not a local DB connection) and listed the bucket via the Storage REST API (service-role key read from the live `halatuju-api` Cloud Run env, never written to disk). Dry-run cross-checked clean: **49 KNOWN** (= the prod `applicant_documents` count exactly) · 55 bucket objects · 49 matched · **6 orphans, all under `3/` (Elanjelian test account)** — 5×`ic` + 1×`parent_ic`, ~198 KB JPEGs, no DB row. Deleted all 6 after explicit user sign-off; re-verify showed **49 bucket objects / 0 orphans**. No backup taken — already-orphaned IC images from a test account, and copying PII to local disk would be worse than deleting. The going-forward delete path was already clean, so no recurrence is expected. _Original footgun for the record: orphans = `bucket objects − ApplicantDocument rows in the CONNECTED DB`, so `cleanup_orphan_blobs --apply` with the storage key set but the DB pointed anywhere other than prod would flag every real document as an orphan — always dry-run and eyeball before `--apply`._

- TD-063: **SPM stream pools are duplicated across the FE/BE boundary** (`SPM_STREAM_POOLS` in `halatuju-web/src/lib/subjects.ts` and `SCIENCE_POOL`/`ARTS_POOL`/`TECHNICAL_POOL` in `halatuju_api/apps/courses/engine.py`). They must stay identical — a stream subject present in the dropdown but absent from the backend pool silently scores on the 10% elective weight (Sec3) instead of the 30% stream weight (Sec2). Mitigated S18 with a linking code comment on both definitions + paired count tests (jest `subjects.test.ts`: 38 arts/16 technical; pytest `test_merit_pools.py`: same). (Found S18, 2026-05-29)
  - ✅ **RESOLVED (v2.13.0, 2026-05-30).** The duplication existed only because the back-end re-derived the stream from a flat grades dict (no label), which forced it to keep its own copy of the pools to *guess* the stream by counting. Fixed by passing the student's explicit stream/aliran selection: `prepare_merit_inputs(grades, stream_subjects=None)` uses the designated subjects for Sec2 when present (pools NOT consulted → a missing-from-pool subject can no longer be mis-scored), and falls back to the count-heuristic only for old/unlabelled data. New `StudentProfile.stream_subjects` (migration `courses/0049`); FE sends `aliranSubjects` to every merit call + persists on sync. **The pools are now fallback-only**, so the drift risk no longer reaches a labelled student — the original S18 bug class is impossible for them. Linking comment + count tests kept for the fallback path. Verified: golden master unchanged (5319) + 6 differential unit tests in `test_merit_pools.py`. See `docs/decisions.md`.

- TD-064: **`PartnerAdmin.is_super_admin` kept alongside the new `role` field (expand-contract).** Phase C (v2.15.0) added `role ∈ {super, reviewer, viewer}` and backfilled it from `is_super_admin`, but kept the legacy boolean because several call sites still read it (`get_partner_students`, `AdminRoleView`, dashboards). An `is_super` bridge property + `has_role()` helper paper over the duality. **To resolve:** migrate every `is_super_admin` reader to `role`/`is_super`, then drop the boolean (additive→destructive migration, expand-contract). Low priority; the bridge is safe. (Introduced Phase C, 2026-05-30)
- TD-065: **Admin interview/Phase-C flow has no jest component tests.** The capture UI, accept-gate UI, assignment, and confirm button are covered only by `next build` type-checking + backend pytest — jest is render-only for these admin pages (longstanding repo gap, surfaced again by Phase C). The interactive behaviour (verdict binding, gate disabling, draft/submit) is unverified at the component level. **To resolve:** add component tests for the interview capture form + accept-gate. Low priority. (Surfaced Phase C, 2026-05-30) **Extended v2.17.0:** the new gap-spotter UI (suggest button → render → gap→findings capture merge) and the student doc-assist chip (`vision_fields.student_verdict`) are likewise jest-untested — only `next build` typing + backend pytest cover them. Same remediation. **Extended v2.18.0:** the Phase-D "Refine with interview findings (AI)" button + final-profile panel are also jest-untested (backend pytest + `next build` typing only). **Extended v2.19.0:** the reject-bucket UI (Decline-after-review / Decline-contractual buttons + confirm + rejection badge) is likewise jest-untested. **Extended v2.20.0:** the `DocumentHelpCoach` widget (loading shimmer / AI message / i18n fallback render + fetch effect) is jest-untested at the component level — though its *pure* decision logic (`lib/documentHelp.ts` `shouldShowCoach`/`fallbackKeyFor`) IS node-env unit-tested (8 tests), so only the render/effect wiring relies on `next build` typing. Same remediation. **Extended v2.22.0:** the sponsor portal (`/sponsor`, 6-state render off `getSponsorMe()` + the register form) and the admin vetting table (`/admin/sponsors` approve/reject/suspend) are jest-untested — `next build` typing + backend pytest only. (The `actionsFor(status)` helper in `/admin/sponsors` is pure and could be unit-tested if extracted.) Same remediation. **Extended v2.23.0:** the sponsor auth pages (`/sponsor/login`, `/sponsor/register`, the portal complete-details form) are component-untested — though the pure password-rule + source logic (`lib/sponsorAuth.ts` `checkPassword`/`SPONSOR_SOURCES`) IS node-env unit-tested (6 tests), so only the form render/effect + Supabase-auth wiring relies on `next build` typing. Same remediation. **Extended v2.25.0:** the pool frontend (`/sponsor` browse grid, `/sponsor/pool/[id]` detail, the admin "Anonymous profile" card) is render-only and jest-untested — `next build` typing + the backend `test_sponsor_pool.py` (incl. the allowlist leak tests = the load-bearing guarantee) cover it; the FE just renders the allowlist payload. Plus E2 (both tiers) is **not click-tested** — the grid only renders with the flag on + dummy data + sponsor/admin sessions (headless can't; do the local smoke before flipping the flag — TD-070).

- TD-066: **Temporary tech-support box on /application is marked `TEMP` and must be removed.** A testing-only support box ("Email tamiliam@gmail.com or call 012-337 5709…") sits in the /application left step menu (mobile fallback below the content). It was added during the live-test phase so a stuck student has a human to reach; it is **not** intended for the promoted programme. Every instance is tagged `TEMP` in code for grep-and-remove. **To resolve:** delete all `TEMP`-marked tech-support box markup + its i18n keys once live testing concludes. Low effort, just don't forget. (Introduced v2.17.0, 2026-05-31)

- TD-067: **The Phase-D final profile (`SponsorProfile.final_markdown`) has no edit/publish/reader path.** v2.18.0 added the refined "v2" profile, but: (a) it's display-only on the admin page — unlike the draft (editable textarea + Save + Publish), the final can only be regenerated, not hand-tweaked; (b) the existing `publish` endpoint publishes `current_markdown` (draft/edited), not `final_markdown`; (c) its intended reader — the sponsor — has no portal yet (Phase E). So today the final profile is an admin-visible artefact with no downstream consumer. **To resolve in Phase E:** decide whether the sponsor reads `final_markdown` directly or whether an admin reviews/edits/publishes it first (likely the latter — add a finalised-edit + publish-final path mirroring the draft's), then wire the sponsor view to the published final. Deliberately deferred — building the reader before Phase E would be a door into an empty room (see decisions.md, the sponsor-login decision). (Introduced v2.18.0, 2026-05-31) **Resolved-in-direction v2.24.0 (E2a):** the sponsor's reader is now a SEPARATE *generated anonymous* profile (`SponsorProfile.anon_markdown`, admin generate→publish), **not** `final_markdown` — so `final_markdown` stays purely admin-facing context, and the "who reads it" question is answered (nobody downstream; sponsors read the anon blurb). **Remaining nuance:** the anon profile is generated from the *application form data*, so it does NOT yet fold in the Phase-D *interview findings* that `final_markdown` captures. Future enhancement: generate the anon profile from the refined final (anonymised) so interview insight reaches sponsors. Low priority.

- TD-068: **Contractual rejection (bucket 4) has no admin-typed reason or post-award capture flow.** v2.19.0 shipped the `contractual` category + a "Decline (contractual)" button on accepted students, but: (a) it sends the **generic** decline email — the user's spec ("email will say the reason specified by admin") was explicitly deferred, so there is no reason text box and the student isn't told why; (b) there's no structured trigger for *when* a contractual rejection applies — no capture of the signed-document / bank-account state, no sign-by deadline or reminder, so an admin just decides manually. **To resolve:** add an admin reason field on `admin_reject`/`AdminRejectView` (reuse the `send_request_info_email(note=…)` pattern → a contractual email template that inserts the reason) and design the post-award contractual workflow (account-number capture, sign-by deadline, auto-reminders). Deferred per the user at build time. (Introduced v2.19.0, 2026-05-31)

- TD-069: **STPM flow's SPM-prerequisite electives aren't durably persisted and stay capped at 2.** v2.21.0 fixed the main SPM grades flow (new `elective_subjects` field + cap 7), but the STPM onboarding flow (`onboarding/stpm-grades`) uses a *separate* subsystem for the SPM prerequisites a STPM student enters: grades go to `spm_prereq_grades` (a distinct field) and the elective *selection* lives only in hardcoded localStorage (`halatuju_spm_elektif` / `halatuju_spm_aliran`) — never synced, never re-hydrated — so it has the same logout/login loss the main flow just fixed, and its elective slots are still capped at 2 (`spmElektifSlots.length < 2`). **To resolve:** mirror v2.21.0 for the STPM path — add a `spm_elective_subjects` field, sync + hydrate it, and raise the cap with `MAX_SPM_ELECTIVES`. Explicitly left out of v2.21.0 ("Don't touch STPM" — user). (Introduced v2.21.0, 2026-05-31)

- TD-070: **Phase E Sprint E1 (sponsor portal + admin vetting) is not click-tested interactively.** v2.22.0 is test-green (1408 pytest + 172 jest, `next build` clean) but the two genuinely stateful flows can't run headless: (a) the sponsor **Google-OAuth sign-in** on `/sponsor` (then the round-trip back via `KEY_SPONSOR_SIGNIN` → `/auth/callback` → `/sponsor`), and (b) the **admin approve/reject/suspend** on `/admin/sponsors` (needs a real admin session; the reviewer-vs-viewer 403 gate is backend-tested but the button wiring isn't). Per the logged lesson "test-green ≠ click-tested for a multi-screen stateful flow facing imminent users", this needs a live smoke **before E2 exposes anything to real sponsors**. **To resolve:** run the manual smoke in the "Next Sprint" step 0 (register → pending → approve → approved shell; confirm a viewer admin is blocked). No code; a verification gate. (Introduced v2.22.0, 2026-05-31) **Extended v2.23.0:** the surface grew — sponsor **email/password sign-up + sign-in** (`/sponsor/register` → `/sponsor/login`, incl. the email-confirmation gap → complete-details), the **Google → complete-details** path, **forgot-password**, and the landing-nav `Log in ▾ | Sign Up` cluster are all headless-untestable. The step-0 smoke now also covers these. Note: if the Supabase project has **email confirmation enabled**, a brand-new email/password sponsor won't get a session at sign-up (the "confirm your email" screen shows) and the row is created only after they confirm + complete details — verify the real project setting during the smoke.

- TD-071: **Cloudflare Turnstile (anti-bot) deferred on sponsor signup.** The user's mockup showed a Turnstile widget on the sponsor registration form; v2.23.0 ships without it (email confirmation + admin vetting gate fake sponsors for now). **To resolve when bot-signups become a concern:** create a Cloudflare Turnstile site (free) for halatuju.xyz, set the site key + secret, and enable Supabase Auth's built-in CAPTCHA (hCaptcha/Turnstile) — the form already has the consent/submit structure; the widget slots in above the submit button and the token is passed to `signUp({ options: { captchaToken } })`. (Deferred per user, v2.23.0, 2026-05-31)

- TD-072: **Sponsor phone is Malaysian-only + the old `/sponsor/register-interest` page is now orphaned.** (a) The sponsor register/complete-details phone input is a fixed `🇲🇾 +60` prefix with `formatPhone`/`isValidPhone` (Malaysian formats) — no country picker, so an international sponsor can't enter a non-MY number. If/when overseas sponsors are onboarded, add a country selector (or a phone-input lib) and relax `isValidPhone`. (b) ✅ **RESOLVED (v2.26.1, 2026-06-01).** The orphaned `app/sponsor/register-interest/page.tsx` (v2.16 public lead form → `SponsorInterest` model + admin list) and its entire stack have been **deleted** (Option B — full removal): the page, `submitSponsorInterest` API helper, the `sponsorInterest.*` i18n block (en/ms/ta), `SponsorInterestView` + `AdminSponsorInterestView` + their two routes, `SponsorInterestSerializer`, the `SponsorInterest` model, and `test_sponsor_interest.py`. Table `sponsor_interests` (0 rows) dropped via migration `0035_remove_sponsor_interest` (applied deploy-first). `emails.send_sponsor_interest_admin_email` kept — now shared by the live `SponsorRegisterView`. (Resolved v2.26.1, 2026-06-01) — _(a) MY-only sponsor phone remains open below._ (Introduced v2.23.0, 2026-05-31)

- TD-073: **The student `AuthProvider` (and its Supabase client) is mounted globally — incl. under `/admin/*` and `/sponsor/*`.** `app/providers.tsx` wraps the whole app, so the student client initialises on the admin/sponsor login + callback pages and **auto-anonymous-signs-in** there (a throwaway anon `auth.users` row, swept by the `purge-anon-users` cron) and, on `/admin/auth/callback` / `/sponsor/auth/callback`, **attempts** to read the `?code` it didn't initiate (a harmless local "code verifier not found" — no session claimed, no server call, thanks to PKCE). The **leak itself is fixed** (v2.23.1, PKCE) — this is only residual noise. **Partly addressed v2.23.2:** the most visible symptom (the student `AuthGateModal` "Create Your Free Student Account" overlaying `/admin` + `/sponsor`) is now closed — the modal route-guards via `usePathname` and renders nothing on those paths. **Still residual:** the student `AuthProvider` + client themselves still mount under `/admin` + `/sponsor` (anon-session creation + a harmless failed-exchange log). **Belt-and-suspenders if it ever matters:** scope the student `AuthProvider` so it doesn't mount under `/admin` + `/sponsor` (e.g. route-group layouts), and/or set `detectSessionInUrl: false` on the student client with an explicit `exchangeCodeForSession` on `/auth/callback`. Low priority — PKCE already closes the security hole and the modal overlay is fixed. (Introduced/observed v2.23.1; modal overlay fixed v2.23.2, 2026-05-31)

- TD-074: **Sponsor-pool follow-ups (E2a, low priority, all behind the OFF flag).** (a) **Detail keyed by raw application id** — `GET /api/v1/sponsor/pool/<id>/` uses the DB row id (the card exposes `id` for the fetch). It's non-identifying and the endpoint returns 404 unless the student is currently pool-eligible, but it leaks row count/order to a vetted sponsor. If that matters, switch the API key to the opaque `pool_ref` (needs a ref→id resolver). (b) ✅ **RESOLVED (v2.25.1, 2026-06-01).** The anon-profile generator is fed the student's free-text narrative, which *could* echo a name/school/place. Now there is a **structural** backstop on top of the prompt instruction + admin review + allowlist card: `pool.scan_anon_for_identifiers(text, profile)` scans the generated blurb for the student's own identifying tokens (name/school distinctive tokens, city, NRIC, phone, email), and `AdminPublishAnonProfileView` **refuses to publish** (`400 anon_identifier_leak` + the offending `fields`) when it finds any — the admin must regenerate first. Generic school-type words (SMK/Sekolah/Menengah/…) and name connectors (bin/binti/a-l/…) are stoplisted to avoid false positives; the scan errs toward blocking. (7 tests in `test_sponsor_pool.py`.) (c) **No filters yet** on the browse list (state/field) — fine for a small dummy pool; add when the pool grows. (Introduced v2.24.0, 2026-05-31)

- TD-075: **Phase E3 — the money + the rest of the sponsorship flow (deferred; built dark on mocked money in E3a).** v2.26.0 shipped the wallet/match/consent *state machine* on dummy data, but deliberately not the regulated/operational money parts:
  - **(a) Real toyyibPay donation-in.** `SponsorDonateView` is a **MOCK** (`POST /sponsor/wallet/donate/` just creates a `Donation` row, `reference='mock'`). Wire toyyibPay (FPX) properly: create-bill → redirect → callback verifies → `Donation` credited; the donation terms (**final, non-refundable to bank — sponsor can only redirect the balance within the platform**) must be in the donation flow + the lawyer's brief, and a one-receipt-at-donation-time (LHDN) approach if myNADI has the status.
  - **(b) Disbursement-out + tranches.** The award is currently funded as one block. Build the **tranche schedule** (e.g. RM1,000 ×3: one on acceptance, the rest progress-gated) with admin **release / withhold**; a withheld tranche **voids the contract** and **returns that amount to the sponsor's balance** (the `Sponsorship.amount` stops fully holding — model a per-tranche state). Real payout to the institution is the gated outbound step.
  - **(c) The lapse cron.** `sponsorship.lapse_expired_offers()` exists + is unit-tested but **isn't scheduled**. Wire a Cloud Scheduler → Cloud Run Job (mirror `release-decisions-15m`) so offered awards past `accept_deadline` actually lapse in prod.
  - **(d) Partial / multi-sponsor funding.** 1:1 full-or-nothing now (DB `uniq_holding_sponsorship_per_app`). The many-sponsor-to-a-target plumbing is in the shape (per-sponsor allocation amounts); opening it up means partial pledges + a target-vs-sum + a funding deadline + "what if some-but-not-enough" (the user deferred this to avoid the time-boxed wait).
  - **(e) Award / decline letters.** The "award letter" + "decline letter" are state transitions only right now — no emails yet. Add `send_award_email` / `send_award_lapsed_email` (reuse `emails.py`, best-effort) when the flow goes live.
  - **(f) Future:** the 2-year allocation window (then myNADI reallocates); and the E3 tables were created via raw MCP CREATE TABLE (migrate-first), so their FK **constraint names** differ from Django's — harmless, but a future migration that alters/drops one by Django's expected name would need the real name (same caveat as E1a/E2a). (Introduced v2.26.0, 2026-06-01; lawyer + gateway gate the real-money parts.)

- TD-076: **The Settings page (`/settings`) is a minimal stub.** `halatuju-web/src/app/settings/page.tsx` (73 lines) does only three things: a language selector, a "clear local data" button (`clearAll()` localStorage wipe), and an About block. **No account settings** — no profile/contact edit, no password change, no notification preferences, no logout, no delete-account. For a logged-in student the page offers nothing tied to their account. Also the **version string is hardcoded** (`const VERSION` — manually bumped at release; set to `2.26.1` on 2026-06-01 after it had gone stale at `2.0.0`) with no central runtime version source. **To resolve (when account self-service matters):** decide the real scope (likely: edit contact details, change password via Supabase, notification opt-outs, logout) and prototype in Stitch first per the UI discipline; and either wire `VERSION` to a build-injected `NEXT_PUBLIC_APP_VERSION` or accept the manual bump as a release-checklist line. Low priority — nothing depends on it. (Logged 2026-06-01)
- TD-077: **Course `#` interview marker renders as raw text, not a badge.** A trailing/embedded `#` in a course name means "this course typically has an interview", but it's shown verbatim (e.g. `Diploma in Nursing #`) wherever course names render — looks like a typo to users. **To resolve:** strip the `#` from the display string and render a small "Interview" badge/indicator next to courses that carry it (needs a shared helper so every render site — eligibility results, course pickers, saved courses, admin — is consistent; new i18n label; prototype the badge in Stitch first). Was roadmap "Known Issues #5" with no TD number; promoted here so it's tracked. Low priority, cosmetic. (Logged 2026-06-01)
- TD-078: **Subject-name map duplicated across the FE/BE boundary (`subjects.ts` ↔ `academic_engine._SUBJECT_BM`).** The verification-verdict academic check (S2) compares the OCR'd results-slip subject names against the typed grades by *normalised Bahasa-Melayu name*, which needs a Python `key → BM name` map; it mirrors `halatuju-web/src/lib/subjects.ts` `SUBJECT_NAMES`. Two hand-maintained copies in different languages → drift risk (a new SPM subject added to `subjects.ts` won't be matched by the backend until `_SUBJECT_BM` is updated too). Mitigated by a code comment linking the two. **To resolve:** either (a) generate `_SUBJECT_BM` from `subjects.ts` at build time, (b) move the canonical subject table to a shared JSON both sides load, or (c) add a paired test asserting equal key membership (the cheapest guard — but the test would have to read the TS file). Low priority; the map is stable and additive. (Logged 2026-06-02, Verification-verdict S2)
- TD-079: **Resolution sync writes on GET + a deleted compulsory doc doesn't resurface its resolved ticket.** `resolution.sync_resolution_items` (S3) persists/auto-resolves `ResolutionItem` rows, and it's called from the **read** paths — `AdminApplicationDetailSerializer.get_resolution_items` and the student `ResolutionItemListView.get`. So an admin/student *GET* mutates rows (idempotent + `IntegrityError`-guarded, but a REST-purity smell). Separately, the **no-re-nag** rule means once a system ticket is resolved it is never re-created, so if a student deletes a now-compulsory document the gap returns on the officer's verdict but the *student's* queue does not re-surface the ticket. **To resolve (if it matters):** move `sync` to explicit state-change points only (upload + delete signals + a dedicated POST refresh) and drop it from the serializers; and/or allow re-opening by keying dedup on open-status + adding a re-open path. Both are deliberate S3 simplifications, not bugs — the officer always sees the true gap via the verdict. Low priority. (Logged 2026-06-02, Verification-verdict S3)
- TD-080: **⚠️ LIVE BUG — IC uploaded as PDF/video fails OCR and is mislabelled as a service outage, stranding real applicants at consent.** Google Vision `document_text_detection` with inline `content=` bytes (`vision.extract_mykad`) only decodes raster images (JPEG/PNG/GIF/BMP/WEBP/TIFF/…); a **PDF or video** returns `"Bad image data."`. Two compounding defects turn that into a dead end: **(1) No upload format restriction.** The FE file input (`halatuju-web/src/components/ScholarshipDocuments.tsx:81`) has no `accept` attribute, and the API (`DocumentListCreateView.post`, `halatuju_api/apps/scholarship/views.py:236`) validates **size + doc-count only**, never MIME/extension — so PDFs (CamScanner / "scan to PDF") and even phone videos are accepted and stored. **(2) Misclassification.** `_ic_identity_blockers` (`services.py:482-485`) buckets **any** `vision_error != 'empty image'` into `ic_service_down`, so `"Bad image data."` surfaces to the student as *"Our document-check service is temporarily unavailable. Please try again later."* (`en.json` `ic_service_down`). "Try again later" never clears it — the stored file is a PDF/video — so the student is permanently blocked at the final consent step and reasonably concludes the system is down. **Evidence (prod, 30 May–01 Jun):** of 17 `ic`/`parent_ic` uploads, **all 9 PDFs/MP4s → "Bad image data", all 8 JPG/PNG/JPEG → success**, interleaved in time (∴ NOT a Vision outage; `detect_vision_outage` correctly does not trip). **5 students blocked** because their *own* `ic` is a PDF/video: THEEPICAA (#4, PDF), JANANI (#5, PDF), Harish (#6, PDF), YESWINDRAN (#8, CamScanner PDF), Taanusiya (#10, **.mp4 video**). **Immediate ops remediation (no code):** message these 5 to re-upload their IC as a **clear JPG/PNG photo** (camera, not scan/video) — OCR re-runs on upload and unblocks them. **Scope note:** this is **IC-only.** Supporting docs (`results_slip`, `str`, `salary_slip`, `epf`, `offer_letter`, bills) get a *soft, non-blocking* name/address presence check (`views.py:271-273` "Soft, never blocks"); consent only checks their **presence**, so a **PDF supporting doc submits fine** and shows no error — those must keep accepting PDF. Only the student's own `ic` hard-gates on a successful OCR read. **To resolve (code, post-sprint, needs approval), in priority order:** (1) **Fix the message** (smallest, do first) — re-map decode-type Vision errors (`"Bad image data."`, `"could not fetch image"`, read-nothing) to `ic_unreadable` ("please re-upload a clearer photo of your IC"), reserving `ic_service_down` for genuine service failures (`detect_vision_outage` already distinguishes); this alone ends the false "system down" dead-end. (2) **Handle PDF for the IC rather than ban it** — scanning a MyKad to PDF (CamScanner) is normal (3 of the 5 stuck students did this); rasterise the PDF's first page to an image server-side before Vision (e.g. pdf2image/Pillow) **or** use Vision's async PDF OCR, so scanned-IC PDFs just work. (3) Reject only truly unreadable types (video, etc.) with a clear "a photo or scan of your IC" message, and add `accept="image/*,.pdf"` on the IC input as a hint. **NB: do NOT add a blanket image-only restriction — it would break the legitimate PDF supporting docs.** **Higher priority than typical debt — affecting live applicants now.** (Logged 2026-06-02; investigation only, no code changed)
  - **✅ RESOLVED (deployed 2026-06-02, 2 deploys):** (1) PDF intake — content-type-aware OCR reads digital PDFs via the text layer and rasterises scanned PDFs (page 1) for Vision; (2) upload format allowlist (images + PDF; video/junk rejected) + FE `accept`; (3) decode-error re-map (`"Bad image data."` → `ic_unreadable`, not `ic_service_down`); plus follow-ups: parent-IC re-run enabled, MyKad name extraction anchored on the parentage marker, and a name mismatch no longer hard-blocks consent when the NRIC matches. See CHANGELOG [Unreleased]. Residual OCR-quality items tracked in TD-081.
- TD-081: **OCR signal-capturing improvements.** The TD-080 fixes made documents *readable*; this tracks making the *reads* better.
  - **✅ RESOLVED for the Identity/IC document (Check-1 sprint, deployed 2026-06-02, `3d110a4`).** (a) marker-less names + (b) blurry-scan NRIC digit misreads are both covered by the **cost-gated Gemini IC second opinion** (`run_vision_for_document` → `_should_gemini_ic` → `_gemini_ic_second_opinion` reads the card **image** → `_merge_ic_reads`, behind `IC_GEMINI_FALLBACK_ENABLED`); the deterministic name-truncation + address card-label strip handle the cheap cases for free. (c) clearer NRIC/name-mismatch guidance is delivered by the S4 Action Centre **and** Cikgu Gopal's now-bidirectional name-mismatch coaching (offer re-upload OR fix the typed profile name, with a `/profile` link). Plan + retro: `docs/scholarship/check1-ic-hardening-plan.md`, `docs/retrospective-check1-identity.md`.
  - **✅ Live smoke PASSED (2026-06-02, user-run, prod):** two real low-confidence MyKads both cleared — **Theresa** (truncated `…A/P` surname, the name case) and **Yeswindran** (unclear/misread NRIC digit, the blurry-number case). The cost-gated Gemini IC second opinion recovered both. The Identity fact is fully validated end-to-end.
  - **✅ RESOLVED for the Academic/results-slip document (deployed 2026-06-02/03, `62339e9`+`177aed2`; + live-review fixes `4391f54`+`b370503`).** Fixed the "Entered 0 of 9" band-word bug (`academic_engine._split_band`), the clinical 3-check (`student_slip_check` → `ResultsSlipChecklist` Name/Subjects/Results + exam year), 3 specific Gopal verdicts; live-confirmed. **Live-review follow-up (2026-06-03):** image-based Gemini slip read fixes the A↔A+ row transposition; a letter↔band disagreement OR a ±-only (same base letter) difference degrades to `uncertain` ("Please check", amber) — never a confident wrong mismatch. **Academic OCR quirk fully closed** (OCR can't guarantee the '+'; the officer verifies by eye). Retros `docs/retrospective-check1-academic.md`, `docs/retrospective-check1-livefixes.md`.
  - **✅ RESOLVED for the Pathway/offer-letter document (deployed 2026-06-03, `3abe9a9`+`a0d997f`; + reconciliation rework `6a54699`).** Differentiated facts (Name+IC checks + Programme/Institution/Issuer/Date/Address data points; expanded Gemini schema covering all post-SPM offer types; `pathway_engine.student_offer_check` + `OfferLetterChecklist`), PLUS the **AI-raised final-pathway confirmation** (migration `0038`). Live-confirmed across all 5 sample types. **Live-review rework (2026-06-03):** the always-ask confirm became a **lenient offer-vs-declared matcher** (`offer_pathway_match`) — match/nothing-to-compare → verified (no nag), genuine clash → reframed confirm + soft Gopal nudge (`offer_pathway_mismatch`) + red checklist rows; the student's Yes realigns the record. Editable self-edit in Funding deferred to Phase 2. Retros `docs/retrospective-check1-pathway.md`, `docs/retrospective-check1-livefixes.md`.
  - **✅ Slip-read robustness improved (deployed 2026-06-04, `c416c2e`).** The deterministic SPM-slip parser now reads
    sideways/keystoned phone photos via gated de-rotation in `academic_engine._group_rows` (it previously fell back to
    Gemini on non-upright slips, which transposed grades). Four real slips frozen as fixtures. Retro
    `docs/retrospective-check1-livetesting-fixes.md`.
  - **✅ INCOME Check-1 (item 3: earner identity + relationship) — SHIPPED 2026-06-04 (`9fa5ffe`+`d151bf6`+`a8bcd75`,
    migration `0039` migrate-first).** Guided document wizard (Documents → Household income) → dynamic checklist;
    earner-relationship proof (father=patronymic / mother=Birth Certificate [new doc type] / guardian=letter); rewired
    `_verdict_income` (verified/recommend/review/gap; never-block informal→interview flag); 11 reason codes (4-link
    chain). `income_engine.py` + `lib/incomeWizard.ts` (mirrored). Retro `retrospective-check1-income.md`. **Residual:
    I4 = income AMOUNT (per-capita B40 test) + utility hardship signal (hooks left); Gopal income doc-coach copy; live
    click-through (TD-070).** _Original plan below:_
  - **✅ INCOME Check-1 COMPLETE — multi-earner salary route + per-document verification + per-capita amount gate
    (SHIPPED + DEPLOYED 2026-06-05, `e197209`→`668676b`, migration `0040` migrate-first).** The salary route became a
    multi-select ("tick everyone who works"); every income IC/salary-slip/EPF/STR is read and cross-checked against the
    earner's own IC (relationship semantics, never the student); a cluster-aware Cikgu Gopal speaks once per member; the
    **per-capita amount gate** (I4 — sum earners' pay from docs ÷ household size vs `per_capita_ceiling`) closes the last
    residual; EPF monthly-contribution + utility-bill address/hardship soft signals; birth-certificate + guardianship
    checklists surfaced. Retro `retrospective-check1-income-multiearner.md`. **The I4 amount-reading + utility-hardship
    residuals above are now RESOLVED.** Remaining residual: the document-first verdict gap (TD-085) + the income-cockpit
    redesign, and the live click-through (TD-070).
  - **▶ INCOME (now SHIPPED — see above) — last + hardest; plan LOCKED, I1 built (in progress).** Plan + schema:
    `docs/scholarship/check1-income-plan.md` (guided document wizard in /application Documents → Household income;
    earner identity + relationship: father=student-IC patronymic, mother=Birth Certificate [NEW doc type], guardian=
    guardianship letter; never-block informal-income families → officer/interview judgement; household-burden signals).
    **I1 backend BUILT this session but NOT yet deployed** (income_engine + requirement matrix + Birth-Certificate
    reader + migration `0039`, all green, uncommitted — migration not on prod). Remaining: I2 (verdict rewire + reason
    codes + officer tile) → I3 (student wizard UI). Amount-reading (per-capita B40 test) + utility hardship signal are
    a deferred 4th slice (hooks left). Policy resolved: keep hard-required where evidence exists, "provide if available"
    + interview judgement for informal earners. (Logged 2026-06-02; Identity+Academic+Pathway resolved 2026-06-03;
    slip-orientation 2026-06-04.)
- TD-082: **Student Action Centre `confirm` tickets for academic route to the Documents tab, not a grades-edit surface.** `/application` has no dedicated grades/results tab (grades come from the profile/onboarding; the results slip is uploaded under Documents), so a `confirm` ticket with `fact==='academic'` (e.g. `academic_missing_subjects` — "add Moral + Tamil Literature") sends the student to **Documents** rather than to the place they actually add subjects (the onboarding grades flow). Acceptable for now — the ticket copy states what to do and the ticket auto-clears once the subjects are entered — but the "Review" button under-delivers for academic. **To resolve:** add an in-`/application` grades-edit affordance (or deep-link the onboarding grades step) and map academic `confirm` to it (`actionCentre.confirmTargetFor` + `ScholarshipNextSteps.handleConfirmNav`). Low priority. (Logged 2026-06-02, Verification-verdict S4)
  - **✅ RESOLVED 2026-06-07:** `confirmTargetFor` now routes academic facts to a new `'grades'` target (the results
    *slip* stays on Documents); `handleConfirmNav` deep-links `'grades'` to `/onboarding/grades` with a return marker
    (`setOnboardingReturn('/scholarship/application')` → `popOnboardingReturn` honoured by the onboarding final step).
    Grades rehydrate from the profile via auth-context, so the editor isn't blank for a returning student.
- TD-083: **Verdict override-rate metric + `officer_verdict.overall` are built on the backend but not surfaced in the cockpit UI.** S5 ships `GET /api/v1/admin/scholarship/verdict-metrics/` (pure `audit.override_metrics` → `{applications, fact_decisions, overrides, override_rate, per_fact}`) and the `getVerdictMetrics()`/`VerdictMetrics` FE type, but the cockpit does **not** render the "how good is the AI" override rate anywhere — it's queryable, not visible. Separately, the officer records a per-fact pass/fail in the Record-verdict panel, but the `officer_verdict.overall` ('accept'|'decline'|'hold') field has **no explicit UI toggle** (it's sent as `''`; the backend accepts that and the overall stance can be inferred from the four facts). **To resolve (when a coordinator dashboard is wanted):** add a small "AI override rate" line/card to the admin console (cohort-filterable via `?cohort=`), and either add an explicit overall accept/decline control to the panel or wire it to the existing verify-&-accept / decline actions so `overall` is set deliberately. Low priority — the audit data is captured regardless; this is surfacing + an optional explicit control. (Logged 2026-06-02, Verification-verdict S5)
  **Resolved (surfacing) — verification-assurance Sprint 3, 2026-06-12.** The override rate is now visible: an **AI reliability card** at the top of the B40 applications list shows agreement (= 1 − override rate) per fact + overall, via the tested `verdictReliability()` helper over the existing `getVerdictMetrics()`. The `?cohort=` filter remains available on the endpoint but the card shows the all-cohort figure. The **second half — an explicit `officer_verdict.overall` accept/decline/hold UI toggle — was deliberately NOT built**: the card derives reliability from the four per-fact Pass/Fail decisions the reviewer already makes, so `overall` stays inferred (sent as `''`). If a future coordinator dashboard wants an explicit overall stance, re-open a thin follow-up for just that toggle.
- TD-084: **Orphaned single-earner income fields after the salary route went multi-earner.** The salary income route now uses `ScholarshipApplication.income_working_members` (multi-select); `earner_work_status` (old Q3) and `household_other_earners` (old Q4) are no longer read on that route (the STR route never used them) — kept in place to avoid a destructive migration. Likewise the wizard i18n keys `scholarship.docs.income.wizard.{q2,q3,q4,work}` are now unreferenced (kept for parity across en/ms/ta). **To resolve:** drop the two columns under expand-contract (grep for readers first — already write-only) and delete the four i18n key groups in all three locales. Low priority, cosmetic. (Logged 2026-06-04, Income Check-1 multi-earner)
- TD-085: **▶ RE-SCOPED 2026-06-05 to TWO sprints (consent gate v2 + officer Documents-panel redesign). The original
  "document-first verdict" + "re-extraction backfill" framing below was DROPPED:** the route stays AUTHORITATIVE (the
  strict route-aware gate + the manual slotting of all 16 pipeline students prevent the route/doc mismatch document-first
  was meant to fix), and the user re-runs legacy docs by hand in the cockpit. Spec: `docs/scholarship/consent-gate-v2-plan.md`.
  - **✅ S1 (consent gate v2) SHIPPED 2026-06-05 (no migration; retro `retrospective-consent-gate-v2-s1.md`):** the
    consent/submission gate is route-aware + strict (offer letter compulsory for all; per-route income docs; EPF no
    longer substitutes a salary slip), sourced from `income_engine.income_requirements` via `services.income_doc_blockers`;
    "never-block" moved to the interview verdict only; the 6 already-submitted apps grandfathered (keyed on
    `profile_completed_at`). 697 scholarship + 1037 courses pytest + 250 jest + i18n 1985.
  - **✅ S2 (officer Documents-panel redesign) SHIPPED 2026-06-05 (no migration; retro `retrospective-td085-cockpit-s2.md`) — ▶▶ TD-085 RESOLVED.**
    Coloured per-doc fact-labels (`officerCockpit.documentFacts`); movable relationship (father/sibling IC patronymic /
    mother→BC / guardian→letter); route+selection-aware Required→Optional ordering + red "Missing" placeholders
    (`officerCockpit.incomeDocLayout`); the row badge rolls up the fact colours, fixing the `documentPill` earner-IC
    "Unread" bug. `AdminApplicationDetailSerializer` now surfaces the income wizard answers (3 fields, no migration).
    258 jest + next build clean + i18n 2013. **TD-085 is complete** (consent gate v2 + cockpit redesign; the
    document-first verdict + re-extraction backfill were intentionally dropped — the route stays authoritative).
    Residual (own backlog items, not TD-085): the PARKED post-consent summary page + lock-at-Continue,
    ~~Gopal income copy~~ **(✅ done 2026-06-06 — one cluster Gopal per earner + lean diagnose→advise tone, `4fb5255`/
    `6d40af2`; retro `retrospective-gopal-cockpit-polish.md`)**, and re-running legacy docs by hand (the user's manual
    cockpit "Re-run").
  - _Original (dropped) framing for the record:_ Income verdict is wizard-route-driven, not document-driven — it ignores income proof the route didn't expect, and pre-wizard submissions can't assemble. Two linked gaps surfaced live (app #21, KISHANTAN): (a) the **STR-route branch of `verdict_engine._verdict_income` only accepts an `str` document as income proof** — a student flagged `receives_str=true` (so the wizard defaulted `income_route='str'`) who uploads the father's salary slip instead of an STR screenshot gets a red *"no proof of income"* even though the payslip + father's IC are present and the earner relationship is confirmed. The salary slip sitting in the drawer is never considered. (b) **Pre-wizard submissions have no route/earner/tags** — a pipeline audit found **15 apps with `income_route=''`** (the wizard didn't exist when they submitted), of which **only 6 are actually submitted (`profile_complete`)** and **9 are merely `shortlisted`** (not yet submitted — they self-heal when they walk the wizard to complete). So the real legacy remediation is **~7 submitted apps** (the 6 blank-route + app #21), not 15. Their income docs are in the **correct doc_types** (slotting is fine) but `household_member=''` (untagged), so the new salary-route cluster keying can't group them. **To resolve:** (1) make the income verdict **document-first** — look at what income proof actually exists (STR / salary slip / EPF, tagged or not) and verify it against the available parent IC(s), using the wizard answers (route/earner/members) as *hints not hard gates*; an STR-route student with a salary slip should still get per-capita credit; (2) a one-time **backfill** of `income_route`/`income_earner` for the 6 blank-route submitted apps so their clusters assemble; (3) **reconfigure the income cockpit** so the tile reflects what is actually in the drawer (surface the salary slip + per-capita + cluster) and never claims *"no proof of income"* when a verified income doc is present. The 9 shortlisted apps need nothing. (Logged 2026-06-05, Income Check-1 multi-earner close — the user's explicit next sprint.)
- TD-086: **Reminder support email is a personal Gmail (`tamiliam@gmail.com`).** The completion-reminder + closure emails
  point students to `emails.SUPPORT_EMAIL = 'tamiliam@gmail.com'` as the human fallback — intentional "for now" (user's
  call) so the system could go live. **To resolve:** swap to a branded address (e.g. `help@halatuju.xyz`, or a Gmail
  alias/forward) — a one-line change to `SUPPORT_EMAIL` in `apps/scholarship/emails.py`. Low priority, cosmetic/privacy.
  (Logged 2026-06-06, application-reminders.)
- TD-087: **Completion reminders land ~1 day after their nominal day-count.** The cadence uses
  `floor((now - reminder_anchor_at).days)` against thresholds (2/9/23/53), but the daily scheduler ticks at a FIXED 09:00
  Asia/KL while `reminder_anchor_at` carries the clock-time it was set — when the tick falls a few minutes before the
  anchor's time-of-day, the day threshold is first met one tick later (e.g. a 4-Jun anchor's R2 fires 14 Jun, not 13).
  Harmless for a reminder (consistent 1-day slip). **To resolve (if day-exact timing ever matters):** anchor to a DATE
  (midnight) or compare on date boundaries rather than a floor-of-timedelta. Low priority. (Logged 2026-06-06.)
  - **✅ RESOLVED 2026-06-07** (`services._elapsed_days_local`): the cadence now compares calendar dates in Asia/KL
    instead of flooring the timedelta, so each reminder fires on its nominal day regardless of the anchor's time-of-day.
    +2 regression tests in `test_reminders.py`. Auto-close gate left as-is (it compares two 09:00-job stamps → no slip).
- TD-088: **Two local `formatNric` duplicates in the admin students pages.** `app/admin/students/page.tsx` and
  `app/admin/students/[id]/page.tsx` each define their own `formatNric(nric: string | null)` (null-safe, returns the raw
  string when not 12 digits) instead of importing the shared `lib/scholarship.ts` one. Left unconsolidated in the
  income-card sprint deliberately: the shared helper takes `string` (not `string | null`) and returns `''` (not `'—'`)
  for invalid input, so a blind swap would crash on a null `nric`. **To resolve:** make the shared `formatNric` null-safe
  (or add a `formatNricDisplay` wrapper) and replace both locals. Cosmetic; both already render the canonical format.
  Low priority. (Logged 2026-06-06.)
  - **✅ RESOLVED** (this [Unreleased] cycle; see CHANGELOG "Changed"): added a null‑safe `formatNricDisplay()` in
    `lib/scholarship.ts` (em‑dash for a missing IC); both admin pages and the new `ScholarshipReview` use it.
- TD-089: **The guardianship-letter relationship path is unwired (guardian income route).** Unlike the birth
  certificate (fixed 2026-06-06), `guardianship_letter` is NOT in `views.SUPPORTING_NAME_CHECK_TYPES`, so an uploaded
  letter is never OCR'd or field-extracted. Worse, `income_engine._relationship_inputs` reads the letter's name from
  `doc.vision_name` — a field only the IC path (`run_vision_for_document`) sets; neither `run_vision_match_for_document`
  nor `run_field_extraction_for_document` writes it. So even after routing the letter into the pipeline, the guardian
  relationship would stay `pending`. **To resolve:** add `guardianship_letter` to `SUPPORTING_NAME_CHECK_TYPES` +
  `RELATIONSHIP_DOC_TYPES`, give it a name field in its extraction schema, and change `_relationship_inputs` to read the
  guardian's name from `vision_fields['fields']` (not `vision_name`). Deliberately NOT done in the BC fix to avoid making
  valid guardian letters show a false "unreadable". Guardian income route is rare; low priority. (Logged 2026-06-06.)
- TD-090: **`handleConfirm` does a full `window.location.reload()` after submit** (`ScholarshipNextSteps.tsx`) to
  re-render the page as the post-submit "received" screen, instead of updating React state in place. Pragmatic and
  reliable (the received screen lives in the parent `application/page.tsx`, keyed off `app.status`, so a reload is the
  simplest way to flip to it), but it's a heavier transition than necessary and loses client state. **To resolve:** lift
  the submitted application up via the existing `onChange`/refresh path so the parent re-renders without a full reload.
  Cosmetic; low priority. (Logged 2026-06-07, Review & submit flow.)
  - **✅ RESOLVED 2026-06-07** (same day): `ScholarshipNextSteps` gained an `onSubmitted` prop; `handleConfirm` hands the
    updated application to the parent (`onSubmitted={setApp}`), which re-renders into the post-submit "received" screen —
    no `window.location.reload()`.
- TD-091: **Sponsor-landing Tamil copy is a best-effort first pass, not the owner's voice.** The `sponsorLanding.*`
  Tamil strings (en/ms/ta parity, 40 keys) were written to ship trilingual but need the owner's refinement per the
  Tamil style guide (joins the existing Tamil-refine queue). Low risk — the page is dark behind `SPONSOR_POOL_ENABLED`
  until go-live. **To resolve:** owner refine pass on `messages/ta.json` `sponsorLanding` before Sprint 12 go-live.
  (Logged 2026-06-08, B40 Phase E/F Sprint 1.)
- TD-092: **Sponsor landing not yet click-through-verified in a live browser.** Sprint 1 verified F1 via `next build`
  typecheck + jest + the approved Stitch design, but did not run a Playwright/dev-server click-through (the page is dark
  on prod, and a live smoke needs `SPONSOR_POOL_ENABLED=on` locally with both servers). **To resolve:** before the
  Sprint 12 go-live deploy, run the app locally with the flag on and click through `/sponsor` in all three locales +
  confirm the counter renders the real eligible count. (Logged 2026-06-08, B40 Phase E/F Sprint 1.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-093: **The new `onboarding_responses` table (migration `0049`) needs RLS enabled on Supabase at deploy.** New
  Django-created tables land without row-level security; per the existing new-model pattern (TD-058 era), enable RLS +
  the appropriate policy when applying `0049` migrate-first via the Supabase MCP, and re-run `get_advisors` to confirm
  no "RLS disabled" finding. Low risk while dark (the api connects with a privileged role), but must be closed before
  go-live. **To resolve:** at the Phase E/F batch deploy, after `0049`, enable RLS on `onboarding_responses`. (Logged
  2026-06-08, B40 Phase E/F Sprint 2.)
- TD-094: **The F8b award/onboarding Tamil copy is a first-draft.** `scholarship.award.*` /
  `scholarship.onboarding.*` / `scholarship.application.awardPanel.*` Tamil strings were written to ship trilingual but
  need the owner's refinement (joins the Tamil-refine queue with TD-091). English + Malay are final. Low risk — the
  pages are dark until go-live. **To resolve:** owner Tamil refine before Sprint 12 go-live. (Logged 2026-06-09, B40
  Phase E/F Sprint 3.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-095: **Create the two F3 Cloud Scheduler jobs at deploy.** `send_sponsor_realtime` (HOURLY) and
  `send_sponsor_digests` (WEEKLY) are registered in `CronRunView.JOBS` (`sponsor-realtime`, `sponsor-digests`) but have
  no scheduler entries yet. **To resolve:** at the Phase E/F batch deploy, create two Cloud Scheduler jobs hitting the
  cron endpoint with `X-Cron-Secret` (mirror `halatuju-application-reminders`): hourly for `sponsor-realtime`, weekly
  for `sponsor-digests` (Asia/KL). Harmless while dark — no sponsor is `realtime`/`weekly`-eligible until the pool flag
  is on and sponsors exist. (Logged 2026-06-09, B40 Phase E/F Sprint 4.)
- TD-096: **Sponsor notification emails default to English.** `Sponsor` has no locale field, so F3 emails send in
  English (the `send_sponsor_*` templates are trilingual and ready). **To resolve:** add a `locale` to `Sponsor`
  (captured at registration) and pass it through `sponsor_notifications`. Low priority. (Logged 2026-06-09, B40 Phase
  E/F Sprint 4.)
- TD-097: **The F6 reviewer-credentials Tamil copy is a first-draft.** `admin.reviewer.*` Tamil strings were written
  to ship trilingual but need the owner's refinement (joins the Tamil-refine queue with TD-091/094). English + Malay
  are final. Low risk — the page is staff-only and held local until the batch deploy. **To resolve:** owner Tamil
  refine before Sprint 12 go-live. (Logged 2026-06-09, B40 Phase E/F Sprint 5.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-098: **Migration `0051_reviewerprofile` (new model) needs the contenttypes workaround + RLS at deploy.** The
  `reviewer_profiles` table is created by a new-model migration; per the TD-058 pattern, prod has no
  contenttypes/auth tables, so a plain `manage.py migrate` exits non-zero on the `post_migrate` signal even when the
  DDL commits. **To resolve:** at the Phase E/F batch deploy, apply `0051` via the Supabase MCP (CREATE TABLE +
  record the `django_migrations` row), then **enable RLS on `reviewer_profiles`** (deny-by-default, service-role-only
  — it holds sensitive staff PII: phone/address) and re-run `get_advisors`. Must be closed before go-live. (Logged
  2026-06-09, B40 Phase E/F Sprint 5.)
- TD-101: **The F2 "My students" view is read-only — donate/withdraw not wired.** The account header shows the giving
  balance but no functional "Donate more"; an offered (pending) card shows "Awaiting acceptance" but no "Withdraw
  offer" action, though `SponsorDonateView` (mock) and `SponsorCancelOfferView` both exist. These are E3 wallet actions
  (the real money is TD-075); F2 deliberately ships the *profile + list* read-surface only. **To resolve:** wire
  `donate`/`cancel` into the My-students view when the E3 wallet UI is built (or sooner if a dark click-through needs
  them). Low priority while dark. (Logged 2026-06-09, B40 Phase E/F Sprint 8.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-100: **Migration `0052` (new `AssignmentEvent` model) needs the contenttypes workaround + RLS at deploy.** Like
  `0051`, the new `assignment_events` table is a new-model migration; prod has no contenttypes/auth tables, so a plain
  `manage.py migrate` exits non-zero on `post_migrate` even when the DDL commits. **To resolve:** at the Phase E/F batch
  deploy, apply `0052` via the Supabase MCP (ADD COLUMN `assigned_at` + CREATE TABLE `assignment_events` + record the
  `django_migrations` row), then **enable RLS on `assignment_events`** (deny-by-default, service-role-only) and re-run
  `get_advisors`. Must be closed before go-live. (Logged 2026-06-09, B40 Phase E/F Sprint 7.)
- TD-099: **No first-sign-in nudge for a reviewer to complete their profile.** F5 (Sprint 6) lets a super admin invite
  a reviewer with the right role, but the roadmap's secondary "prompt Reviewer profile (F6) completion on first
  sign-in" was deferred to keep the sprint small — a newly-invited reviewer can reach `/admin` with a blank
  `ReviewerProfile`. **To resolve:** on the admin dashboard (or `/admin/profile`), show a dismissable banner for a
  reviewer/super whose `ReviewerProfile` is still blank, linking to `/admin/profile`. Low priority, non-blocking.
  (Logged 2026-06-09, B40 Phase E/F Sprint 6.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-102: **Migration `0053` (new `SemesterResult` + `GraduationMessage` models) needs the contenttypes workaround +
  RLS at deploy.** Like `0051`/`0052`, `0053` creates two new tables (`semester_results`, `graduation_messages`); prod
  has no contenttypes/auth tables, so a plain `manage.py migrate` exits non-zero on `post_migrate` even when the DDL
  commits. **To resolve:** at the Phase E/F batch deploy, apply `0053` via the Supabase MCP (CREATE both TABLEs + record
  the `django_migrations` row), then **enable RLS on both** (deny-by-default, service-role-only — `graduation_messages`
  holds free-text that, pre-approval, may contain identifiers in `raw_text`/`scan_result`) and re-run `get_advisors`.
  Must be closed before go-live. (Logged 2026-06-09, B40 Phase E/F Sprint 9.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-106: **Migration `0054` (new `SponsorReferral` model) needs the contenttypes workaround + RLS at deploy.** Like
  `0051`–`0053`, the new `sponsor_referrals` table is a new-model migration; prod has no contenttypes/auth tables, so a
  plain `manage.py migrate` exits non-zero on `post_migrate` even when the DDL commits. **To resolve:** at the Phase E/F
  batch deploy, apply `0054` via the Supabase MCP (CREATE TABLE + record the `django_migrations` row), then **enable RLS
  on `sponsor_referrals`** (deny-by-default, service-role-only — it holds prospective-sponsor emails, PII until purged)
  and re-run `get_advisors`. Must be closed before go-live. (Logged 2026-06-09, B40 Phase E/F Sprint 11.)
- ✅ RESOLVED (go-live 2026-06-09) — TD-107: **Create the F4 `purge-referrals` Cloud Scheduler job at deploy.** The 60-day PDPA purge
  (`purge_sponsor_referrals`) is whitelisted in `CronRunView.JOBS` but needs a **daily** Cloud Scheduler HTTP job
  (mirroring the F3 `sponsor-realtime`/`sponsor-digests` jobs: region, `X-Cron-Secret` from `CRON_SECRET`,
  `Asia/Kuala_Lumpur`). Without it, unconverted invitee emails are never scrubbed. **To resolve:** at deploy,
  `gcloud scheduler jobs create http halatuju-purge-referrals … POST …/internal/cron/purge-referrals/`. (Logged
  2026-06-09, B40 Phase E/F Sprint 11.)
- TD-108: **F4 Tamil copy is a first-draft.** The `sponsorPortal.referrals.*` UI strings (17 keys) + the
  `REFERRAL_INVITE_*` Tamil email templates were written to keep parity but need the owner's review per
  `tamil-style-guide.md` (the invite email is sent to a real prospective sponsor). Fold into the pre-go-live Tamil refine
  batch (TD-091/094/096/097/105). (Logged 2026-06-09, B40 Phase E/F Sprint 11.)
- TD-104: **F9b's results form has no slip-upload control (CGPA-only).** The approved Stitch design showed an optional
  "Upload results slip (staff-only)" row, but the document upload pipeline (sign-upload → PUT → create doc) is heavy and
  the CGPA/`graduated` values are what drive the sponsor-facing progress band; the `results_slip` FK on the backend is
  left unset from this surface. **To resolve (optional):** wire the existing document-upload flow into the Add-result
  form (or let the student attach via a future in-programme Documents tab) and pass `results_slip` to
  `addSemesterResult`. Low priority — the band works without it. (Logged 2026-06-09, B40 Phase E/F Sprint 10.)
- TD-105: **F9b Tamil copy is a first-draft.** The `scholarship.inProgramme.*` + `sponsorPortal.graduationMessages.*`
  Tamil strings (48 keys) were written to keep en/ms/ta parity but need the owner's review per `tamil-style-guide.md` —
  especially the graduation-relay wording (it's shown to a real sponsor). Fold into the pre-go-live Tamil refine batch
  alongside TD-091/094/096/097. (Logged 2026-06-09, B40 Phase E/F Sprint 10.)
- TD-103: **Semester-result CGPA is student-entered, not OCR-derived.** F9a's `record_semester_result` accepts an
  optional `results_slip` (a myNADI-only `ApplicantDocument`) but does NOT auto-extract the CGPA from it — the student
  types the CGPA + semester. The roadmap envisaged "reuse the OCR path"; deferred because the in-programme university
  slip differs from the SPM `results_slip` the academic engine parses, and a manual CGPA is enough to drive the coarse
  progress band. **To resolve (optional):** when an in-programme slip OCR schema exists, pre-fill the CGPA from the slip
  and let the student confirm (don't auto-trust). Low priority; the band only needs a coarse value. (Logged 2026-06-09,
  B40 Phase E/F Sprint 9.)
- TD-109: **`source='system'` resolution items are created but no longer shown to students.** The Action Centre now
  excludes `source='system'` from the student queue (`ResolutionItemListView`), and the officer cockpit reads the
  verdict directly (not `resolution_items`) — so `sync_resolution_items`' system rows are effectively dead (created +
  auto-resolved, read by nothing student-facing). Harmless but wasteful (a write on every GET — see TD-079). **To
  resolve (optional):** either stop generating `source='system'` items, or keep them only if a future feature reads
  them; revisit together with TD-079 (resolution sync writes on GET). Low priority. (Logged 2026-06-10, Action Centre.)
- TD-110: **`resolution.doc_match_verdict` duplicates the per-doc red/unreadable logic in
  `services.document_red_blockers` / `document_unreadable_blockers`.** Both classify each doc_type's `*_check` into
  mismatch/unreadable using the same status sets, so they must be kept in lockstep (the Action Centre and the consent
  gate must agree on a document). **To resolve:** extract one shared per-doc helper (e.g. `income_engine`/a new
  `doc_verdicts` module) that both call, when either is next touched. Low priority (a paired comment + the cross-check
  is the current mitigation). (Logged 2026-06-10, Action Centre.) **Update 2026-06-12:** `doc_match_verdict` now also
  returns a `'pending'` (not-yet-scanned → hold the task) state that the consent-gate blockers don't have — by design
  (the pre-submit gate's wizard is still open), but a future shared helper must keep the `'pending'` branch on the
  Action-Centre side only.
- TD-111: **Check-2 student-query coverage — the anomaly engine detects more than the clarify generator can ask, so
  student-answerable issues are silently dropped.** Check-2's student clarify questions come from a FIXED 4-item list
  (`check2_queries.CLARIFY_SPECS`: course/sibling/device/transport) tied to STEP-1 completeness gaps; the
  `anomaly_engine` detects more (`funding_other_without_note`, `device_in_funding`, …) but those stay OFFICER-only
  pre-interview flags and are never bridged into the student clarify stream — and there's NO detector for "utility
  account-holder ≠ student/parent". Surfaced on Theepicaa (app #4): Check-2 raised the BC (verdict ticket) + sibling
  level (clarify) but MISSED the funding-"other"-with-no-note and the water-bill-in-a-third-name questions. **To
  resolve:** (1) route EVERY detected issue (STEP-1 gaps + anomaly flags) through one triage tagging each ask-student /
  officer-only / auto-answered, so anomaly flags that are one-line + non-sensitive become clarify queries; (2) add the
  utility-account-holder-mismatch detector; (3) add a **coverage critic** that asserts every detected issue is routed
  somewhere and logs any "detected-but-routed-nowhere" (the durable safety net vs hand-adding specs); keep MAX_CLARIFY=3
  + prioritise (BC before funding note). Exclude the empty-`justification` field (owner: not a good question). FE/BE, no
  migration; student stream still flag-gated (CHECK2_STUDENT_QUERIES_ENABLED) so it surfaces to the officer until on.
  (Logged 2026-06-10, Action Centre follow-up.)
- TD-112: **Income route-switch not yet click-tested in a browser.** The post-submit self-serve income route switch
  (endpoint `.../income-route/` + `IncomeRouteSwitch` mini-wizard) is integration-tested via Django's test client (11
  tests: both directions, recompute, no-re-block) and the FE type-checks, but the live in-browser flow on a real
  `profile_complete` student isn't click-tested. Verify on prod after deploy: open the Action Centre on an STR-route
  student with an income task → "Change how you prove your income" → switch to salary → confirm → the STR task clears,
  the earner-IC task appears, status stays `profile_complete`. (Logged 2026-06-12, income route switch. TD-070 pattern.)
- TD-113: **Switching to the salary route does not ticket the salary slip (soft signal only).** The salary verdict
  (`verdict_engine._verdict_income_salary`) raises ticketable gaps for the earner IC + relationship docs, but a missing
  salary slip keeps income at `recommend`/`income_unverified_needs_interview` (an officer/interview flag, never a student
  task) — by design (the salary route never hard-blocks post-submit). So a student who switches STR→salary is prompted
  for the IC but not, via an Action-Centre task, for the salary slip; the route-switch wizard's "we'll show you which
  documents to upload" + the income_requirements checklist set the expectation. **To resolve (if wanted):** add a
  `salary_slip_missing` ticketable verdict code on the salary route + entry in `CODE_TO_TICKET`. **Needs sign-off** — it
  reopens the "never hard-block post-submit income" decision (consent-gate-v2). (Logged 2026-06-12, income route switch.)
- TD-114: **A fact can read CERTAIN off documents whose genuineness was never checked — a folder of typed sheets
  passed as Pathway + Income CERTAIN (test #16).** CERTAIN is asserted on field-match alone (typed text matches the
  application); it does not require the *document* to be genuine. Two holes: (A) genuineness runs at upload only and
  is never backfilled, so pre-feature uploads sit unscored and the verdict treats unscored as fine; (B) structural —
  `offer_letter`/`salary_slip` are un-fingerprinted (so Pathway can never be capped), and the engine never gates
  CERTAIN on a passed genuineness check. Demo (2026-06-13): re-running genuineness on #16's income docs dropped Income
  CERTAIN→Probable, but Pathway stayed CERTAIN (offer letter uncovered). **Approved design + full scope: `docs/scholarship/
  verification-genuineness-gating-plan.md`** (gate CERTAIN on genuineness; confirmed fake → Unsure; cover the offer
  letter; backfill command). **DEFERRED — edge case for our population; lower priority than current fixes.** Owner
  go-ahead required before building. (Logged 2026-06-13, test #16 finding.)
- TD-115: **No fixed document-slot model — uploads share slots and the income engine stores docs by a
  route-dependent convention, causing the "one IC under all earners" + "duplicate Mother's IC" bugs.** Target: 27 fixed
  `(doc_type × person)` slots; every upload (wizard or Action Centre) tagged by person; re-upload overwrites the slot;
  route controls which slots are required vs optional (not storage). Blocker: `income_engine._cluster_docs` reads STR-route
  docs as blank-member and salary-route docs as tagged — so data can't be re-tagged ahead of the code (one coordinated
  code + migration). Prod assessed safe: deterministic for ~all docs; only 1 true route correction (#12 salary→STR);
  duplicates hand-cleaned (#16, #12). **Full spec + confirmed model: `docs/scholarship/document-slot-model-plan.md`.**
  **Sprint 1 SHIPPED 2026-06-13** (`main` `7b460d4` + MCP backfill; retro `docs/retrospective-slot-model-s1.md`): tolerant
  readers (by-person, blank-as-earner fallback on STR) + authoritative upload tagging (STR income docs ← `income_earner`,
  tolerant sweep) + wizard per-earner; 53 docs backfilled (0 blanks, 0 dup slots); #12 corrected → STR/mother. Verdict-invariant.
  **(b) RESOLVED 2026-06-14** — salary-route Action-Centre member-tagging: an officer per-person doc request stashes the
  member in the ticket's `params`; the student's Action-Centre upload tags `household_member` from there (Check-2/Check-3 S2b,
  `main`). **(c) RESOLVED 2026-06-14** — Check-2/Check-3 process flow & display shipped as the cockpit redesign (4 sprints +
  3 review rounds; `f5243a7` → `762b358`; roadmap `docs/scholarship/check2-check3-roadmap.md`).
  **Still open (deferred):** (a) DB `UniqueConstraint(application,doc_type,household_member)` — the permanent guarantee; needs
  test-fixture rework (tests pre-create same-slot docs) + migrate-first; app layer already prevents dups. (Logged 2026-06-13; b+c closed 2026-06-14.)
- TD-116: **EPF mining benefits NEW uploads only — existing EPF statements need a re-parse to populate the new fields.**
  The 2026-06-14 EPF work (`97a7793`) extracts `avg_monthly_contribution`/`months_counted`/`contribution_status`/
  `statement_date`/`address`, but these need the CARUMAN rows + statement body, which aren't in the already-stored
  extracted fields — only a re-OCR/Gemini re-run repopulates them (billable). Shipped with a graceful fallback (the
  income estimate uses the latest-month figure for old records, so no regression). **To resolve (when wanted):** a
  targeted per-doc "Re-run vision" on the EPFs that matter, or a small `--apply` command that re-extracts EPFs (billable
  — owner's call). Low priority; outcomes already correct via the fallback. (Logged 2026-06-14.)
- TD-117: **#37-class mis-slot (an STR screenshot uploaded as EPF) isn't flagged on OLD docs because the wrong-type
  genuineness check never ran on them.** #37's EPF doc (id 411) predates the genuineness + capture layers
  (`authenticity: null`, `capture: null`); Gemini pulled a name+NRIC but no EPF financials, and `vision.doc_genuineness`
  → `wrong_type` (the designed detector) never ran, so no officer flag. A per-doc Re-run flags it. **Optional backstop
  (offered, not built):** a deterministic "EPF extracted a name but NO balance/contribution/year/employer → doesn't look
  like an EPF" soft officer signal (no billable call), to catch mis-slots even when genuineness hasn't run. (Logged
  2026-06-14.)
- **TD-118 (low) ✅ RESOLVED (small-change lane, 2026-06-16):** removed the six dead api-client functions
  (`generateSponsorProfile`, `finaliseSponsorProfile`, `saveSponsorProfile`, `publishSponsorProfile`,
  `generateAnonProfile`, `publishAnonProfile`) from `admin-api.ts` (the `AdminSponsorProfile` type is retained — still
  used by `sponsor_profile` + the cockpit), and the 29 orphaned i18n leaves under `admin.scholarship`
  (`generate`/`generating`/`regenerate`/`save`/`saving`/`publish`/`publishing`/`genError`/`saveError`/`publishError`
  + the whole `finalProfile.*` and `anonProfile.*` objects) across en/ms/ta — parity held at 2653×3. Each was grep-verified
  to have zero references (no dynamic key-building). `tsc` introduced no new error. Kept the still-rendered profile keys
  (`profileTitle`/`profileDraftHint`/`profilePending`/`genLang`/`model`). See TD-120 for a wider orphan set found in passing.
- **TD-118 (original): tidy dead profile UI plumbing after the narrative redesign.** The 2026-06-15 profile redesign
  removed the manual Generate/Save/Publish/Refine controls + the anonymous-profile card from the cockpit, but left
  behind: (a) unused api client functions in `halatuju-web/src/lib/admin-api.ts` (`generateSponsorProfile`,
  `finaliseSponsorProfile`, `saveSponsorProfile`, `publishSponsorProfile`, `generateAnonProfile`, `publishAnonProfile`)
  and (b) now-orphaned i18n keys under `admin.scholarship` (`generate`/`regenerate`/`save`/`publish` + `anonProfile.*` +
  some `finalProfile.*`). All harmless (build green, i18n parity intact), so deferred from the redesign sprint. Remove
  them in a future web-only change, grepping each key/fn for references first and keeping en/ms/ta parity. (Logged
  2026-06-15.)
- TD-119: **13 corpus false-positive flags still undiagnosed** — the eval run flagged 5 `parent_ic`, 5
  `birth_certificate`, 1 `epf`, 1 `str`, 1 `offer_letter` (mismatch), 1 `offer_letter` (unreadable) as genuine-docs-
  wrongly-flagged. The owner reviewed `ic`/`parent_ic` as all-genuine, so these are likely matcher false positives of
  the same class as the results-slip ones. **To resolve:** run the diagnose → fix → test loop per type (the
  results-slip pass closed 11 of the original 24). (Logged 2026-06-16, Genuineness signatures.)
- **TD-120 (low) ✅ RESOLVED (small-change lane, 2026-06-16):** removed **77** orphaned `admin.scholarship` i18n leaves
  across en/ms/ta (parity 2654→2577×3), pruned four now-empty objects (`extractFields`, `interview.rubric`,
  `recordVerdict.tools`, `upu`). Used a **dynamic-aware scan** (full-path literals + concatenation/template prefixes) so
  the dynamically-addressed subtrees (`anomaly.*`, `verdict.item.*`, `docsDrawer.*`, `statuses.*`, etc.) were correctly
  kept; cross-verified every candidate by grep, and confirmed the translator has no scoped/prefixed variant (every key is
  a full path). Chief removals: the retired **Verify & accept** card, the old **Vision OCR** card labels, and assorted
  dead field labels (`coq`, `referralSource`, `guardianName`, `pathway`, `upu.*`, `caveats.*` leftovers, …). Added a
  **guardrail** — `halatuju-web/src/messages/__tests__/admin-scholarship-i18n.test.ts` (jest) — that fails on any future
  orphan or en/ms/ta drift in this namespace, so the set can't silently regrow. jest 322 green; tsc clean; web-only, no
  migration. **Original entry (for context):**
- **TD-120 (original): a wider set of orphaned `admin.scholarship` i18n keys, beyond the profile redesign.** While doing
  TD-118 I scanned every leaf under `admin.scholarship` and found ~80 more keys with no code reference — chiefly the
  retired **Verify & accept** card (`verifyTitle`, `verifyHint`, `verifyAccept`, `nricLocked`, `acceptNeedsVerdict`,
  `check_nric`/`check_name`/`check_results`/`check_document`), and assorted field labels (`coq`, `referralSource`,
  `guardianName`, `intendsTertiary`, `declarationName`, `anythingElse`, several `interview.*`/`caveats.*`/`upu.*`/
  `docsDrawer.capture.*` leaves, etc.). These accumulated across earlier cockpit redesigns (the verify step folded into
  "Save verdict IS the decision"), NOT this round, so they were out of TD-118's scope and deliberately left to avoid
  scope-creeping a small change. **To resolve:** a dedicated web-only pass that re-runs the leaf scan, hand-verifies each
  candidate against dynamic key-building (many siblings ARE built dynamically — `statuses.*`, `anomaly.*`, `verdict.item.*`,
  `docsDrawer.*` — so a naive bulk delete would break the UI), removes only the confirmed-dead, and keeps en/ms/ta parity.
  Worth pairing with a guardrail (an i18n orphan-key check) so the set stops regrowing. (Logged 2026-06-16. NB: the
  unmerged `feature/doc-eval-harness` branch reserves TD-119 for its own corpus-flag debt — hence this is TD-120.)
- TD-121: **The eval harness scorecard doesn't run counter-examples through the genuineness cap.**
  `eval_doc_recognition --auto-ok` scores via `resolution.doc_match_verdict` (content match), which never reads
  `vision_fields['authenticity']` — that cap lives in `verdict_engine.build_verdict`. So the known typed fake (a16)
  shows as a content false-negative even though the new signature scorer + cap would flag it `suspect` in production.
  **To resolve:** capture the signature genuineness into the cached snapshots and score counter-examples through the
  band (or through `build_verdict`), so the two-directional scorecard reflects the genuineness layer. Verified inline
  during the sprint (a16 → suspect; 43 genuine → genuine; 4 cropped → review; zero misclassifications), just not wired
  into the command. (Logged 2026-06-16, Genuineness signatures.)
- TD-122 **✅ RESOLVED (2026-06-20):** BC + EPF genuineness now come from the probabilistic SIGNATURE
  scorer in the live upload path (`vision.run_field_extraction_for_document` routes `birth_certificate`
  + `epf` through `signature_genuineness`; STR stays holistic). Text-dominant (visual markers are bonus,
  the text clears the band); the EPF scorer doubles as the wrong-type backstop (tax/withdrawal/STR →
  not_epf, TD-117). Flag-gated, no migration; +wiring tests. (Logged 2026-06-16; done 2026-06-20.)
- TD-123 **✅ RESOLVED (2026-06-20):** Issue-2 extraction updated for BC + EPF. BC: dropped `bc_number`
  (schema + Gemini hint; `bc_child_nric` already optional/barcode-bound). EPF: extract the **employer-
  and employee-share contribution TOTALS separately** + `months_counted` + `employer_number`; the income
  engine derives `monthly_salary = max(ΣMajikan/(n·0.13), ΣAhli/(n·0.11))` (`income_engine._epf_monthly_salary`;
  `employer_number == 000000000 ⇒ unemployed → 0`), with a **legacy fallback** (combined contribution ÷ 0.24)
  so already-extracted prod EPFs don't regress. Retired `avg_monthly_contribution` from extraction. +tests.
  *(Minor follow-up: the deterministic `doc_parse` EPF parser doesn't yet emit the split totals → those
  records use the legacy-fallback estimate; image-Gemini EPFs use the precise max() formula.)* (Logged 2026-06-16; done 2026-06-20.)
- TD-124: **Contact-form messages are email-only — no in-app inbox.** `/contact` → `contact_submissions`; the
  `notify-contact-submissions` cron (2026-06-18) emails each unread row to `contact@halatuju.xyz` and marks it read.
  There is no `/admin/messages` UI to browse/triage them. **To resolve:** a small admin inbox reading
  `contact_submissions` with the `read` toggle. Low priority (email covers the need at current volume). (Logged 2026-06-18.)
- TD-125: **The Meet service-account JSON key lives in a Cloud Run env var (`GOOGLE_MEET_SA_JSON`), not Secret
  Manager.** Matches the project's existing env-var secret pattern (CRON_SECRET, GEMINI_API_KEY) but a long-lived SA
  key is higher-value. **To resolve:** move to Secret Manager (mounted) or switch `meeting.py` to keyless DWD via the
  Cloud Run runtime SA (workload identity), removing the key entirely. (Logged 2026-06-18.)
- TD-126: **Interview-scheduling Guide step has no screenshot.** The Guide "Scheduling the interview" step renders
  text-only (images were made optional). **To resolve:** once `INTERVIEW_SCHEDULING_ENABLED` is on, capture the
  cockpit "Propose interview times" card + student booking panel and add them like the other steps. (Logged 2026-06-18.)
- TD-127: **New PISMP rows (Pendidikan Khas `…H`, Prasekolah `…H7P`, MBPK `50BK…`) carry cloned generic descriptions.**
  During the 2026-06-18 catalogue reconciliation, the B/D/L→H swap and the MBPK ingest created rows whose `description`
  was cloned from a Perdana sibling rather than written for the specific bidang. They're correct on code/name/
  requirements but the prose is generic. **To resolve:** write proper bidang-specific descriptions (the retired B/D/L
  rows' bespoke Braille/BIM/autism copy is in `Downloads/sk_sjkc_retire_backup_2026-06-18.json` and can seed them).
  Low priority — cosmetic, doesn't affect eligibility or selection. (Logged 2026-06-18.)
- TD-128: **MBPK eligibility gate under-captures non-physical special-needs.** MBPK courses are gated on the existing
  onboarding "Physical disability" checkbox (`req_disability`), but MBPK also covers learning / hearing / visual needs
  (the old B/D/L categories) which that single signal doesn't capture — a deliberate partial proxy chosen for
  simplicity (see decisions.md). **To resolve, if matching proves too narrow:** broaden the Special-Needs onboarding
  field into typed categories and gate MBPK on the union. (Logged 2026-06-18.)
- TD-129: **SJKT PISMP bidang carry an over-specified language requirement (BT in the C-group).** The official 2026 IPGM
  Perdana syarat lists C in **3** subjects (Bahasa Melayu, Bahasa Inggeris, Sejarah), but several SJKT bidang
  requirements store a 4-subject C-group `[BM, BT, HISTORY, BI]` (Bahasa Tamil added). Harmless in practice — an SJKT
  applicant trivially has BT ≥ C — so it never changes an outcome, but it's a minor deviation from the PDF surfaced
  while investigating the picker. **To resolve:** drop BT from the C-group (or confirm it's intentional) at the next
  PISMP courses refresh, alongside TD-127. (Logged 2026-06-19.)
- TD-130: **Unsubscribe risk on transactional emails (definitive fix is Brevo-side).** Brevo auto-injects a
  `List-Unsubscribe` header on ALL mail it relays, including transactional — so Gmail shows an "Unsubscribe" button, and a
  mistaken click may add the contact to Brevo's suppression list and silently stop future service mail. We shipped a
  code-side shim on **interview** emails (our own harmless `mailto:help@` `List-Unsubscribe`, no one-click POST), but the
  **decision + application-completion reminder emails still carry Brevo's default unsubscribe**, and Brevo may still inject
  its own header alongside ours. **To resolve:** ask Brevo support to enable **List-Help instead of List-Unsubscribe on
  transactional** (account-wide, certain fix); then drop the mailto shim. Owner action (free-tier support latency unknown).
  Interim option: extend the same `mailto:` shim to the decision/reminder send paths. (Logged 2026-06-19.)
- TD-131 **✅ RESOLVED (2026-06-19):** built the verdict-completion SLA enforcement — `send_review_nudges` cron
  (dark behind `REVIEW_NUDGES_ENABLED`) nudges the assigned reviewer 2 days before + once overdue, escalates to all
  super-admins 4 days after the due date (`assigned_at + REVIEW_SLA_DAYS`), idempotent via stamps reset on
  (re)assignment, cancelled by a recorded `verdict_decided_at`; the verdict-due date is also surfaced in the reviewer
  interview reminder. Migration `0064` (migrate-first). The original debt:
- TD-131 (original): **No verdict-completion clock or overdue-verdict nudge for reviewers.** The reviewer-assigned email now shows a
  soft "Please review by {date}" (`REVIEW_SLA_DAYS`, default 7), but it is **display-only** — nothing tracks whether a
  reviewer actually records a verdict, and there is no reminder or escalation if they don't. (`decision_due_at` is the
  *student-facing* delayed-reveal timer, not a reviewer deadline.) The missing email in the reviewer lifecycle is the one
  that prevents a stuck case: *"you interviewed {ref} N days ago but haven't recorded a verdict."* **To resolve (own
  change):** add a verdict-due field/SLA, a detection job (interviewed/assigned + no verdict past the SLA), and an
  overdue-verdict nudge email; only then surface the due date in the **interview reminder** too (the deferred external-review
  point — a date with teeth, not a soft target that can already be in the past by interview time). (Logged 2026-06-19.)
- TD-132: **R1 sponsor-portal Tamil strings are first-drafts.** The new `sponsorPortal.nav` / `students` / `account`
  keys (+ `myStudents.none`) were added EN/MS/TA in lockstep, but the Tamil is a first-draft for owner refinement per
  `tamil-style-guide.md`. **To resolve (owner):** refine the Tamil copy on the three new sponsor-portal blocks.
  (Logged 2026-06-19, Sponsor redesign R1.) Related: **TD-101** (the Students "Support" button is a stub — funding not
  wired pending the owner's fund-UX sign-off).
  **Extended R7 (2026-06-20):** now covers the **whole redesign (R1–R7)** sponsor copy, not just R1. R7 also revealed
  that ~47 keys (`sponsorPortal.{impact,journey,activity,community,statement,students,account}.*`) were referenced by
  R1–R4 pages but **never authored in any language** — they were added EN/MS/TA in R7, so the **English is freshly
  authored (not just the Tamil)** and the **Tamil is a second-draft per the style guide**. A `sponsor-i18n.test.ts`
  guardrail now prevents missing keys recurring. **To resolve (owner):** a copy pass — **English AND Tamil** — over the
  full sponsor portal (My Giving / Students / Account / Trust / AutoSponsor) on the live site. (Mechanically the strings
  render correctly; this is a quality/voice pass.)
- TD-133: **R5 Trust & Transparency hub ships with honest PLACEHOLDERS — real content is owner-gated.** The hub's
  *Who we are* (legal entity), *Governance* (trustee board), *Sources & uses* (annual figures) and *Independent
  assurance* (auditor + FY report) render "to be published" / illustrative placeholders because the organisation is not
  yet formalised. The My Giving assurance strip likewise shows illustrative figures ("112 verified · RM 284,000 · FY2025
  · auditor to be appointed"), flagged illustrative. **To resolve (owner long-lead):** appoint the **independent
  auditor + trustee board**, define the attestation scope, and register the legal entity; then the real content drops in
  by editing the `trust_content` DB row — **no deploy** (language-neutral data in the DB, trilingual chrome in i18n). A
  per-student `enrolment_verified` flag (the "Enrolment independently verified" badge) likewise stays False until that
  institution-confirmation process exists. (Logged 2026-06-20, Sponsor redesign R5/R7.)
- TD-134: **[RESOLVED 2026-06-21]** Gap in the TD-115 slot model — the slot key `(doc_type, household_member)` could not
  represent multiple reviewer-requested docs of the same type, so each Action-Centre "Other" upload overwrote the previous
  one (live data loss — Theepicaa app 4: 5 requested, 1 stored) and a cross-person income request (father's IC on a
  mother-STR route) overwrote the route doc. **Resolved** by `feat/request-owned-doc-slots` (commit `d9278f3`, migration
  `scholarship/0067`): added `ApplicantDocument.request_code` so the slot key is `(doc_type, household_member,
  request_code)`; the STR force-tag is skipped for request-keyed uploads; `resolve_doc_items_for_upload` resolves by code;
  `MAX_OTHER_DOCS=10` cap. +6 tests. See `docs/decisions.md` + `docs/retrospective-2026-06-21-request-owned-doc-slots.md`.
  ⚠️ Migration `0067` clashes with the unmerged `feat/whatsapp-comms` branch — renumber the later merge to `0068`.
  (Logged + resolved 2026-06-21.) **UPDATE:** whatsapp-comms shipped its model as `scholarship/0068`; clash resolved.
- TD-135: **[RESOLVED 2026-06-21]** WhatsApp inbound STOP/opt-out → flag sync. **Resolved (roadmap S5):** Twilio inbound
  webhook `POST /api/v1/scholarship/whatsapp/inbound/` (`WhatsAppInboundView`) flips `whatsapp_opt_in` on STOP/START,
  Twilio-signature authed (`whatsapp.verify_twilio_signature`), number→profile via sent `to_number`. +5 tests. **Remaining
  to activate:** owner sets the inbound webhook URL in the Twilio console (code is signature-gated/inert until then).
  (Logged + resolved 2026-06-21.)
- TD-136: **Phone verification is a field, not a feature.** `contact_phone_verified` exists (resets on phone change) and is
  displayed, but nothing ever sets it True — there is no OTP send/verify flow. **To resolve (if wanted):** a "verify my
  number" flow via the **Twilio Verify API** (WhatsApp or SMS channel) → mark verified. Now feasible (Twilio wired).
  (Logged 2026-06-21.)
- TD-137: **[RESOLVED 2026-06-21]** The 24h slot min-lead was frontend-only and applied to reschedule too. **Resolved:**
  reschedule mode now uses `RESCHEDULE_MIN_LEAD_HOURS = 2h` (the picker offers nearer slots + jumps to the nearer earliest
  day); first-propose keeps 24h; backend already accepted any future slot. FE-only (`interviewSlots.ts` +
  `InterviewScheduleCard`), +2 jest. (Logged + resolved 2026-06-21; roadmap Sprint 1.)
- TD-138: **[CODE BUILT, sandbox-ready, dark in prod — 2026-06-21]** No WhatsApp when interview slots are PROPOSED.
  **Built (roadmap S2):** `_send_wa_proposed` in `propose_slots` (opt-in gated, links to the application page), dual-path
  (free-text in sandbox / template in prod). **Remaining to go live:** owner sandbox-tests the wording, then submit the
  Meta template + set `TWILIO_WHATSAPP_PROPOSED_CONTENT_SID` (dark on a real sender until then). (Logged + built 2026-06-21.)
- TD-139 **✅ RESOLVED (2026-06-20):** dropped `results_slip` from `genuineness.supporting_doc._GENUINENESS_DOCS`
  (it was scored by the SIGNATURE scorer — its upload branch wins first — so the holistic membership was dead);
  the slip branch is independent and the holistic set is now just STR. Test updated. (Originally logged as TD-133 on
  `feature/doc-eval-harness`; **renumbered to TD-139 at the 2026-06-23 merge** because main's TD-133 = the R5 Trust hub.
  This entry's number had churned 120→124→127→130→132→133→139 across parallel main merges — the exact collision the
  doc-eval lessons flag; resolved outright so the number no longer matters for tracking.)
- TD-140: **Bursary agreement go-live is blocked on two Phase-0 gates (DARK until both clear).** The Conditional Bursary
  Award Agreement shipped 2026-06-26 behind `BURSARY_AGREEMENT_ENABLED` (default OFF). It is a real legal instrument and
  must **not** be exposed to live students until: (1) **a lawyer vets the template wording** in
  `apps/scholarship/bursary.py` (it currently carries a "DRAFT — pending legal review" banner, EN+BM; Tamil not yet
  drafted) and confirms typed e-signature sufficiency for this contract type (Malaysia ECA 2006 — a bursary is not an
  excluded instrument, but confirm); and (2) **the Foundation entity + signatory are finalised** (interim
  `FOUNDATION_SIGNATORY_NAME/_TITLE/_NRIC` = "Suresh"; old agreements stand as signed when the entity changes). **To
  resolve:** owner/legal action (not code) → then set `BURSARY_AGREEMENT_ENABLED=1`. (Logged 2026-06-26.)
- TD-141: **Bursary parent surety signs IN-SESSION only — no separate parent-phone signing link (Phase 2).** v1 has the
  student and parent/guarantor sign on the same device in one sitting (`guarantor_method='in_session'`); the model already
  carries `guarantor_method='link'` for the future path. **To resolve (Phase 2):** a tokenised public signing page
  (`secrets.token_urlsafe`, mirrors the referral-link pattern) sent to the parent's phone via WhatsApp/SMS, gated by a
  Twilio Verify OTP, with reminders + expiry — so a parent who isn't physically present can co-sign. (Logged 2026-06-26.)
- TD-142: **Bursary agreement states a payment schedule it cannot yet honour — disbursement + suspension are still mocked
  (Phase 3; folds into TD-075).** The signed agreement *names* the RM500 + 10×RM250 schedule and the Foundation's right to
  suspend/withhold, but no money moves and `agreement.status` gates nothing operationally (the `is_executed` /
  all-four-signed state is recorded but inert). **To resolve (Phase 3, with TD-075):** wire real disbursement +
  suspension/withholding to `agreement.status == executed` + academic-progress signals so the stated schedule becomes
  operative. Until then the contract is a binding *instrument* on a mocked-money flow. (Logged 2026-06-26.)
- TD-143: **A birth certificate cropped ABOVE its header scores `not_birth_certificate`, not `suspect`.** The BC
  signature anchors live in the header block (`Sijil Kelahiran` / `Pendaftaran Kelahiran dan Kematian` / `Kerajaan
  Malaysia`); a screenshot cropped to the lower half (particulars only, e.g. corpus a27) loses them and the text score
  falls below 0.35 → `not_birth_certificate` (a harder "wrong type" verdict than the soft `suspect` a genuine-but-cropped
  doc deserves). All 13 unseen held-out BCs pass — this is a narrow header-crop edge. **To resolve (owner's call):** leave
  as-is (acceptable — half a BC isn't clearly a BC), OR floor a header-cropped-but-BC-ish doc at `suspect` rather than
  `not_type`. (Logged 2026-06-27, Layer-1 doc-recognition go-live.)

### [TD-144] Bursary-agreement panel: derive ticks from the real agreement when the feature goes live
**Status:** Open (deferred to the agent finishing the Conditional Bursary Agreement).
**Context:** The cockpit panel is now gated on `bursary_agreement_enabled` (2026-06-27), so it stays dark while OFF. But the Student/Guarantor ticks still default to ✓ (`bursary ? !!… : true`) on the assumption "signed-by-now once accepted", and the admin detail GET does not load the agreement.
**Fix when enabling:** include the `BursaryAgreement` (signed timestamps) in `AdminApplicationDetailSerializer`, initialise the panel's `bursary` state from it, and default all four ticks to **unsigned** (—) — so an accepted-but-not-yet-signed case isn't over-stated. Reuses the existing `BursaryAgreementSerializer`.

### [TD-145] Wrong-PUBLIC-university offer is not caught when the declared institution field is blank
**Status:** Open (deferred fast-follow from the offer-validity gate sprint, 2026-06-27).
**Context:** `_declared_pathway` reads the declared institution from `chosen_programme['institution']` (often blank) / `pre_u_institution`. For a degree applicant who picked a course via the eligibility tree, only `course_id` is stored — never resolved to an institution. So a student who declares **UMK** but uploads a genuine **UM** offer shows no institution clash (`offer_pathway_match` compares against an empty declared institution → 'unknown', not 'clash'). #31 is caught only because its offer is *also* a non-genuine pemakluman; a genuine wrong-public-uni offer would slip through. This is a SOFT confirm, NOT a hard gate (UPU routinely places a student at a different public uni, and our course tree can be wrong).
**Fix:** in `_declared_pathway`, when `chosen_programme['course_id']` is set, resolve `course_id → course_institutions → institutions.institution_name` and use it as the declared institution so `offer_pathway_match` can raise a real clash → `pathway_confirm`. Mind the KM/KMK/SMK/KTE convention — the place token already bridges abbreviation↔expansion, so canonicalise on the place name, not the prefix. (Logged 2026-06-27, offer-validity gate go-live.)

### [TD-146] Retire the legacy `sponsored` status once the award-accept flow is rewired
**Status:** RESOLVED in post-award lifecycle S3 (2026-06-28). `respond_to_award`/`fund_student` rewired
(`fund_student → awarded`, acceptance → `active` via cool-off or Foundation counter-sign); `sponsored`
removed from STATUS_CHOICES, all status sets, the onboarding/finalising gates, admin maps + i18n; 0 prod
rows to migrate. Migration `0075`. See `docs/retrospective-2026-06-28-post-award-s3-awarded-signing.md`.
**Context:** The post-award lifecycle replaces `sponsored` (award accepted, in-programme) with `active` (executed) → `maintenance` (funded). S2 added the new statuses but **kept `sponsored` valid** because `sponsorship.respond_to_award` still flips the app to `sponsored` on award acceptance, and the in-programme/pool/progress gates still accept it (`pool.FUNDED_STATES`/`IN_PROGRAMME_OR_BEYOND` include it). Prod has 0 `sponsored` rows.
**Fix (S3):** rewire `respond_to_award` to set `active` (then `maintenance` on first disbursement, S4); migrate any `sponsored` rows → `maintenance`; remove `sponsored` from STATUS_CHOICES + the `FUNDED_STATES`/`IN_PROGRAMME_OR_BEYOND`/DECIDED_STATUSES/QUERYING_LOCKED/_TERMINAL sets + the admin status maps + i18n. (Logged 2026-06-28, post-award S2.)

### [TD-147] Retire the recurring `ScholarshipCohort.name` migration drift for good
**Status:** RESOLVED 2026-06-28 (small-change lane, branch `chore/retire-cohort-name-drift`). Added the
standalone state-only migration `0079_alter_scholarshipcohort_name` (a help_text-only `AlterField` —
`sqlmigrate` confirms `-- (no-op)`, no DDL). `makemigrations scholarship --check` now reports "No
changes detected"; future sprints no longer have to hand-drop the stray op. Deployed state-only (the
`django_migrations` row recorded on prod via Supabase MCP; no schema change).
**Original (logged 2026-06-28, post-award S5). Low risk, recurring friction.**
**Context:** Every post-award sprint (S1–S5), `makemigrations scholarship` re-proposes an
`AlterField` on `scholarshipcohort.name` (a `help_text` drift between the model and migration
state that no sprint authored). Each sprint hand-writes its migration to omit the stray op — a
reliable but repeated chore (now a documented reflex). **Fix:** add ONE state-only migration that
records the `scholarshipcohort.name` `AlterField` (no DDL — `help_text` is not a column change), so
`makemigrations --check` is clean thereafter and future sprints stop having to drop the op. Do it as
a standalone small-change / in the next consolidation review, NOT folded into a feature sprint (keep
it isolated so it's obviously a no-op DDL). Verify with `makemigrations scholarship --check` returning
"No changes" afterwards.

### [TD-148] Officer view of a student's bank details (the payout surface)
**Status:** Open (logged 2026-06-29, post-award S7). **Context:** the bank-details capture (S7) stores the
student's confirmed `BankAccount` (bank/account-no/holder) but surfaces it on **no admin/officer view** —
the owner's explicit scope ("stored in the DB but not displayed anywhere"). To actually *pay* a student,
an officer will need to see (and likely re-verify) the account. **Fix:** an officer-only Bank-details panel
on the cockpit (read the `BankAccount` + the linked `source_doc` bank statement; show `holder_verdict`),
gated like the other reviewer surfaces. **Folds into real disbursement (TD-075)** — build it alongside the
payout rails, not before (there's nothing to do with the number until money can move). Anonymity note: this
is a back-office surface only; the account never crosses to a sponsor view.

### [TD-149] No path to change a bank account after it's confirmed
**Status:** Open (logged 2026-06-29, post-award S7). **Context:** once the student saves their `BankAccount`,
the `bank_details_missing` task resolves and leaves the Action Centre, so there is **no student-facing path
to correct/replace the account** (wrong account saved, account later closed). The backend confirm endpoint
already does `update_or_create` (a re-POST would update in place) — only the FE entry point is missing.
**Fix:** a small "Update my bank details" surface (e.g. re-open the task, or a thin panel on the
award/in-programme page) that re-uses `POST /scholarship/bank-account/` (same hard holder gate). Low risk;
do when the payout surface (TD-148) lands, since that's when a wrong account starts to matter.

### [TD-150] Course matcher assigns a wrong public `course_id` (poly-IT synthetic majors; private programmes)
**Status:** Open (logged 2026-06-29, bursary↔recommender alignment). **Context:** the catalogue course
matcher (apply-form pick / `offer_pathway.resolve_catalogue_course`) sometimes binds a student's
`chosen_programme.course_id` to the WRONG catalogue course, surfaced by the institution-alignment work
(institution derived from `course_id` conflicts with the institution on the actual offer):
- **Poly IT (#95 Gokulleshan):** the recommender models several **synthetic "majors"** for a single
  Politeknik IT diploma (e.g. Data Management, Software & App Dev) and each major row is attached to a
  *specific* campus, so a student's IT offer can match a major hosted at a *different* polytechnic
  (`POLY-DIP-077` → Politeknik Seberang Perai vs his actual Politeknik Ungku Omar). The split majors don't
  reflect the real single-course/campus reality. **Fix:** reconcile the poly-IT synthetic majors with the
  real catalogue (one course, campus from the offer), or make the matcher campus-aware.
- **Private programmes (#31 Dhurvaashrii):** a private offer (no public-catalogue equivalent) was force-
  matched to an unrelated public `course_id` (`UL0010002` → UMK). A private/IPTS programme should stay
  **label-only (no `course_id`)** rather than be bound to the nearest public course. (#31's spurious id was
  cleared by hand 2026-06-29; the matcher should not create them.) **Fix:** the matcher must return no id
  when confidence is low / the issuer is private, rather than forcing the nearest match.

The institution-alignment guard (`offer_pathway.catalogue_institution`) already *refuses to act* on these
conflicts (it never swaps one institution for a different one) and surfaces them instead — so live data is
safe; this TD is about stopping the wrong `course_id` being assigned at the source. Low urgency (display +
funding both key off `chosen_pathway`, not `course_id`, for these pre-U/poly rows).
