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
3. **[TD-003] Zero frontend tests** — All client-side eligibility, merit calculation, CGPA calculation, and pathway logic is completely untested.

**Category with most inconsistency:** Frontend-backend implicit contracts (11 items)

**Estimated fix sprints:** 6-8 sprints if addressed systematically (grouped by risk, not by category)

---

## API Response Format Consistency

### [TD-004] Mixed HTTP status code style
**File(s):** `halatuju_api/apps/courses/views.py` (lines 943, 951, 953, 967, 968, 977, 985)
**What it is:** Some endpoints use DRF constants (`status.HTTP_400_BAD_REQUEST`), others use raw integers (`status=400`, `status=404`, `status=201`). The SavedCoursesView and SavedCourseDetailView use raw integers while OutcomeListView and OutcomeDetailView use DRF constants.
**What consistent looks like:** All endpoints use `status.HTTP_*` constants from `rest_framework.status`.
**Risk if left:** Low — functionally identical, but makes code review harder and introduces inconsistency risk on new endpoints.
**Dependencies:** None.

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

### [TD-008] ProfileView accepts arbitrary fields without validation
**File(s):** `halatuju_api/apps/courses/views.py` (lines 1029-1038)
**What it is:** `ProfileView.put()` and `ProfileSyncView.post()` iterate over allowed field names and call `setattr(profile, field, request.data[field])` with no type validation. A string sent for `siblings` (int field) or invalid JSON for `grades` (JSONField) would cause a 500.
**What consistent looks like:** Use a DRF serializer for profile updates with proper field-level validation.
**Risk if left:** Medium — any malformed request to `/profile/` could cause an unhandled 500 error.
**Dependencies:** None.

### [TD-009] No rate limiting on Gemini API calls
**File(s):** `halatuju_api/apps/reports/views.py`, `halatuju_api/apps/reports/report_engine.py`
**What it is:** The report generation endpoint calls the Gemini API with no rate limiting. An authenticated user could trigger unlimited API calls, each costing money.
**What consistent looks like:** Rate limit report generation per user (e.g., max 3 per day).
**Risk if left:** Medium — cost risk if abused, though currently low traffic.
**Dependencies:** Would need Django cache or a counter model.

---

## Authentication and Permission Handling

### [TD-010] 9 pre-existing auth test failures
**File(s):** `halatuju_api/apps/courses/tests/test_auth.py`
**What it is:** 9 tests fail because they use malformed JWT tokens that the middleware correctly rejects. The tests were written before JWKS support was added but never updated.
**What consistent looks like:** Tests generate properly signed JWTs for the test environment.
**Risk if left:** Medium — broken tests mask real auth regressions. If a genuine auth bug is introduced, it would be invisible among the 9 known failures.
**Dependencies:** Need a test JWT signing helper using HS256 with the dev secret.

### [TD-011] SupabaseIsAuthenticated returns 403 instead of 401
**File(s):** `halatuju_api/halatuju/middleware/supabase_auth.py` (line 132)
**What it is:** The permission class returns 403 Forbidden for unauthenticated requests. RFC 7235 says 401 should be used when authentication is required but not provided; 403 is for "authenticated but not authorised". The docstring even acknowledges this is DRF's default behaviour.
**What consistent looks like:** Return 401 with a `WWW-Authenticate` header.
**Risk if left:** Low — frontend handles both 401 and 403 the same way, but API semantics are wrong.
**Dependencies:** Frontend error handling, auth test expectations.

### [TD-012] DEFAULT_PERMISSION_CLASSES is AllowAny
**File(s):** `halatuju_api/halatuju/settings/base.py` (line 94-96)
**What it is:** REST_FRAMEWORK default permission is `AllowAny`. Each protected endpoint must explicitly set `permission_classes = [SupabaseIsAuthenticated]`. If a developer forgets, the endpoint is silently public.
**What consistent looks like:** Default to `IsAuthenticated` and explicitly mark public endpoints with `permission_classes = [AllowAny]`.
**Risk if left:** Medium — new endpoints default to public unless developer remembers to add auth.
**Dependencies:** Would need to audit all views and add explicit AllowAny to public endpoints.

---

## Frontend-Backend Implicit Contracts

### [TD-001] STPM SPM prerequisite fields not checked (HIGH RISK)
**File(s):** `halatuju_api/apps/courses/stpm_engine.py` (lines 106-113), `halatuju_api/apps/courses/models.py` (lines 575, 577)
**What it is:** `StpmRequirement` model has `spm_pass_bi` (line 575) and `spm_pass_math` (line 577) boolean fields. But `check_spm_prerequisites()` only checks: `spm_credit_bm`, `spm_pass_sejarah`, `spm_credit_bi`, `spm_credit_math`, `spm_credit_addmath`, `spm_credit_science`. The `spm_pass_bi` and `spm_pass_math` fields are loaded from CSV, stored in DB, but NEVER evaluated.
**What consistent looks like:** Add `('spm_pass_bi', 'eng', SPM_PASS_GRADES)` and `('spm_pass_math', 'math', SPM_PASS_GRADES)` to `SIMPLE_CHECKS`.
**Risk if left:** HIGH — students may be shown as eligible for programmes that actually require a pass in BI or Math at SPM level. This is a correctness bug, not just tech debt.
**Dependencies:** STPM golden master will change. Must update baseline after fix.

### [TD-002] Client-side eligibility logic duplicated (HIGH RISK)
**File(s):**
- Frontend: `halatuju-web/src/lib/pathways.ts` (512 lines)
- Backend: `halatuju_api/apps/courses/pathways.py` (315 lines)
- Frontend: `halatuju-web/src/lib/merit.ts` (63 lines)
- Backend: `halatuju_api/apps/courses/engine.py` (lines 159-253)
- Frontend: `halatuju-web/src/lib/stpm.ts` (22 lines)
- Backend: `halatuju_api/apps/courses/stpm_engine.py` (lines 6-40)
**What it is:** Three separate pieces of eligibility/calculation logic are independently implemented in both frontend (TypeScript) and backend (Python). They use different subject key conventions (frontend: MAT, AMT, CHE; backend: math, addmath, chem). The frontend pathways.ts also includes pre-U fit scoring logic (lines 326-490) that has no backend equivalent.
**What consistent looks like:** Either (a) frontend calls backend for all calculations, or (b) a shared specification defines the formulas and both implementations are tested against the same test vectors.
**Risk if left:** HIGH — a formula change in one place but not the other causes silent divergence. The matric merit and STPM mata gred calculations run independently and could disagree.
**Dependencies:** Dashboard, pathway pages, onboarding pages all use frontend calculations.

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

### [TD-015] Frontend merit calculation sent to backend, backend may recalculate
**File(s):** `halatuju-web/src/app/onboarding/grades/page.tsx` (line 305), `halatuju_api/apps/courses/views.py` (lines 312-320), `halatuju-web/src/lib/api.ts` (line 44 `student_merit`)
**What it is:** The frontend calculates merit in `merit.ts` and stores it. The eligibility API accepts an optional `student_merit` field — if provided, the backend skips recalculation. But the backend's `prepare_merit_inputs()` splits grades differently (using science stream detection) than the frontend's fixed core/stream/elective split from the UI. They may disagree on which subjects go into which section.
**What consistent looks like:** Backend is the single source of truth for merit. Frontend should either always send grades and let backend compute, or the section split logic must be identical.
**Risk if left:** Medium — could produce different merit scores for the same student depending on whether the frontend pre-computed or the backend recalculated.
**Dependencies:** Onboarding flow, dashboard, eligibility endpoint.

### [TD-016] StpmProgrammeDetailView looks up institution by name
**File(s):** `halatuju_api/apps/courses/views.py` (lines 1409-1411)
**What it is:** `StpmProgrammeDetailView` looks up the institution by `institution_name=prog.university` using `Institution.objects.get()`. This is fragile — if the STPM course `university` field doesn't exactly match `Institution.institution_name`, the lookup silently fails (returns no institution data). There's no foreign key relationship.
**What consistent looks like:** Either add a FK from StpmCourse to Institution, or use `iexact` lookup with proper error handling.
**Risk if left:** Medium — any name mismatch means STPM programme detail page shows no institution card.
**Dependencies:** STPM programme detail page.

### [TD-017] Pre-U fit scoring exists only on frontend
**File(s):** `halatuju-web/src/lib/pathways.ts` (lines 326-490)
**What it is:** The `getPathwayFitScore()` function and all its helpers (prestige bonus, academic bonus, field preference, signal adjustment) exist only in the frontend. The backend has no equivalent. This means pre-U course ranking on the dashboard is entirely client-side and cannot be verified by tests.
**What consistent looks like:** Either move fit scoring to backend (like SPM/STPM ranking), or accept this as a design decision and add frontend tests.
**Risk if left:** Medium — untested scoring logic that could silently break.
**Dependencies:** Dashboard pre-U course cards.

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

### [TD-003] Zero frontend tests (HIGH RISK)
**File(s):** `halatuju-web/` (entire frontend)
**What it is:** The Next.js frontend has zero test files. All client-side logic — pathways.ts (512 lines), merit.ts (63 lines), stpm.ts (22 lines), subjects.ts, i18n.tsx, auth-context.tsx — is untested.
**What consistent looks like:** At minimum, unit tests for pathways.ts, merit.ts, and stpm.ts (pure functions, easy to test). Ideally component tests for critical flows.
**Risk if left:** HIGH — the three duplicated calculation modules have no safety net. A refactor or bug fix could silently break eligibility calculations shown to students.
**Dependencies:** Would need Jest/Vitest setup in halatuju-web.

### [TD-033] Auth test failures not triaged
**File(s):** `halatuju_api/apps/courses/tests/test_auth.py`
**What it is:** 9 auth tests have been failing since JWKS support was added. They're documented as "pre-existing failures" and excluded from pass criteria. But nobody has investigated whether they test real security requirements.
**What consistent looks like:** Either fix the tests (generate valid test JWTs) or delete tests for requirements that don't exist.
**Risk if left:** Medium — normalises test failures, making real regressions harder to spot.
**Dependencies:** JWT test helper utility.

### [TD-034] No integration test for full eligibility → ranking → report flow
**File(s):** `halatuju_api/apps/courses/tests/`
**What it is:** Tests cover individual components (engine, ranking, serializers) but there's no end-to-end test that sends a student profile through eligibility → ranking → report generation. This is the critical user path.
**What consistent looks like:** One integration test that exercises the full API flow with a realistic student profile.
**Risk if left:** Medium — individual units could pass while the integrated flow breaks.
**Dependencies:** None.

### [TD-035] Golden master count discrepancy
**File(s):** `halatuju_api/CLAUDE.md`, `.claude/ARCHITECTURE_MAP.md`
**What it is:** CLAUDE.md references golden master baselines as both "8280" and "8283" in different places. The architecture map says 8283. The actual current count should be verified.
**What consistent looks like:** One canonical baseline number, documented in one place.
**Risk if left:** Low — confusing documentation, but the test file has the authoritative number.
**Dependencies:** None.

---

## Configuration and Environment Handling

### [TD-036] Hardcoded fallback SECRET_KEY in base.py
**File(s):** `halatuju_api/halatuju/settings/base.py` (line 13)
**What it is:** `SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')`. The fallback is a known insecure key. If production somehow starts without SECRET_KEY set, it would use this.
**What consistent looks like:** No fallback in production settings. `production.py` should raise if SECRET_KEY is not set (like it does for DATABASE_URL).
**Risk if left:** Low — production.py doesn't override this, but Cloud Run always sets env vars.
**Dependencies:** None.

### [TD-037] db.sqlite3 in project folder
**File(s):** `halatuju_api/db.sqlite3`
**What it is:** Local development SQLite database is present in the project folder. It's in .gitignore but its presence in the working directory can confuse.
**What consistent looks like:** Store in a temp or data directory, not the project root.
**Risk if left:** Low — just clutter.
**Dependencies:** development.py database config.

### [TD-038] CORS_ALLOW_ALL_ORIGINS possible in production
**File(s):** `halatuju_api/halatuju/settings/production.py` (lines 20-24)
**What it is:** Production settings check if `CORS_ALLOWED_ORIGINS` env var is `*`, and if so, sets `CORS_ALLOW_ALL_ORIGINS = True`. This means production CAN be configured to accept requests from any origin.
**What consistent looks like:** Never allow `*` in production. Raise or log a warning if `CORS_ALLOWED_ORIGINS=*` is set.
**Risk if left:** Medium — depends on the actual env var value in Cloud Run. If it's set correctly, no issue.
**Dependencies:** Cloud Run environment variables.

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
| TD-001 | STPM SPM prerequisite fields not checked | Correctness bug | Open |
| TD-002 | Client-side eligibility logic duplicated | Duplication | Open |
| TD-003 | Zero frontend tests | Test coverage | Open |
| TD-007 | Bare except in engine.py | Error handling | Open |
| TD-010 | 9 pre-existing auth test failures | Test coverage | Open |
| TD-012 | DEFAULT_PERMISSION_CLASSES is AllowAny | Security | Open |
| TD-045 | EligibilityCheckView.post() is 300+ lines | Maintainability | Open |
| TD-050 | i18n locale key inconsistency (quiz language bug) | Correctness bug | Open |

### MEDIUM (22 items)
| ID | Title | Status |
|----|-------|--------|
| TD-008 | ProfileView accepts arbitrary fields without validation | Open |
| TD-009 | No rate limiting on Gemini API calls | Open |
| TD-011 | SupabaseIsAuthenticated returns 403 instead of 401 | Open |
| TD-013 | Subject key naming split (5+ files to change) | Open |
| TD-014 | localStorage sprawl (20+ keys, no typing) | Open |
| TD-015 | Frontend/backend merit calculation may disagree | Open |
| TD-016 | StpmProgrammeDetailView institution lookup by name | Open |
| TD-017 | Pre-U fit scoring exists only on frontend | Open |
| TD-021 | PISMP deduplication logic inline and complex | Open |
| TD-033 | Auth test failures not triaged | Open |
| TD-034 | No integration test for full flow | Open |
| TD-035 | Golden master count discrepancy in docs | Open |
| TD-038 | CORS_ALLOW_ALL_ORIGINS possible in production | Open |
| TD-043 | Phone/OTP login blocked | Open |
| TD-044 | EligibilityCheckView iterates DataFrame twice | Open |
| TD-046 | CourseListView returns all courses unpaginated | Open |
| TD-048 | console.error in production with no user feedback | Open |
| TD-051 | STPM field metadata has 207 unique values | Open |
| TD-052 | Hardcoded merit thresholds duplicated across layers | Open |

### LOW (22 items)
| ID | Title | Status |
|----|-------|--------|
| TD-004 | Mixed HTTP status code style | Open |
| TD-005 | No standard error response envelope | Open |
| TD-006 | Inconsistent success response keys (count vs total_count) | Open |
| TD-018 | Duplicate import of Count, Subquery, OuterRef | Open |
| TD-019 | Inline json import in views.py | Open |
| TD-020 | Duplicate credit_stv key in serializer | Open |
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
| TD-036 | Hardcoded fallback SECRET_KEY | Open |
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
- TD-010, TD-033: Fix or remove the 9 auth test failures
- TD-003: Set up frontend test framework + test pathways.ts, merit.ts, stpm.ts
- TD-034: Add one integration test for full eligibility → ranking flow

**Sprint 3 — Security & error handling (1 session)**
- TD-012: Change DEFAULT_PERMISSION_CLASSES to IsAuthenticated
- TD-008: Add profile update serializer with validation
- TD-038: Reject CORS_ALLOW_ALL_ORIGINS in production
- TD-036: Raise on missing SECRET_KEY in production

**Sprint 4 — API consistency (1 session)**
- TD-004, TD-005, TD-006, TD-026: Standardise error/success response format
- TD-011: Fix 401 vs 403

**Sprint 5 — Frontend cleanup (1 session)**
- TD-014: Centralise localStorage into a typed store
- TD-048: Add user-facing error toasts
- TD-041, TD-042: Add custom error/404 pages, flesh out settings

**Sprint 6 — Architecture (1-2 sessions)**
- TD-002, TD-013, TD-015: Address frontend-backend duplication (decide: backend-only or shared spec)
- TD-045, TD-021: Refactor EligibilityCheckView into smaller functions
- TD-017: Decide on pre-U scoring architecture

**Sprint 7-8 — Cleanup (1-2 sessions)**
- TD-028, TD-029, TD-031, TD-032: Archive/remove legacy files
- TD-030: Update stale docstrings
- TD-051: Normalise STPM field metadata
- TD-039, TD-040: Update dependency pins
