# Changelog — HalaTuju

## localStorage & Bug Fixes Sprint (2026-03-19)

### Fixed
- **Dashboard "Failed to load recommendations" — complete fix**: Frontend was converting booleans to "Ya"/"Tidak" strings before API calls (6 sites). Removed all string conversions — frontend now sends booleans directly.
- **Stale localStorage causing errors on login**: `restoreProfileToLocalStorage()` now always overwrites from Supabase (source of truth) instead of only writing when localStorage is empty. Eliminates entire class of stale-cache bugs.

### Changed
- **localStorage is a cache, not a source of truth**: All `!localStorage.getItem()` guards removed from `restoreProfileToLocalStorage()`. Login always refreshes from Supabase API.
- **API types cleaned up**: `colorblind`/`disability` types changed from `boolean | 'Ya' | 'Tidak'` to `boolean` across `StudentProfile`, `SyncProfileData`, `StpmEligibilityRequest`

### Removed
- **`migrateProfile()` shim**: One-time localStorage migration for "Ya"/"Tidak" strings — replaced by always-overwrite-from-Supabase approach

### Stats
- Backend tests: 932 pass, 0 failures
- Frontend build: passes cleanly
- Golden masters: SPM 5319, STPM 2026 (unchanged)

---

## i18n Sprint 2 — Admin Pages (2026-03-19)

### Added
- **Admin i18n**: All 7 admin pages fully internationalised with `t()` calls (login, dashboard, students list, student detail, invite, profile, layout)
- **118 admin i18n keys** added to `en.json`, `ms.json`, `ta.json` under `admin` namespace — covering auth flow, dashboard stats, student table, 9 detail cards, invite form, profile form, danger zone
- **Interpolation support** for dynamic admin strings: `studentsCount`, `showingRange`, `orgInfo`

### Stats
- Admin pages with hardcoded strings: 0 (down from 7)
- Admin i18n keys: 118 (EN/MS/TA parity verified)
- Build: passes cleanly

---

## i18n & Bug Fixes Sprint (2026-03-19)

### Added
- **Error mapping layer**: `apiErrors` i18n keys + `ERROR_MAP` for translating API error codes to user-facing messages
- **i18n coverage**: Replaced hardcoded strings in auth callback, quiz, report, IC onboarding pages with `t()` calls
- **Trilingual email verification**: Email subject and body sent in user's language (EN/MS/TA). `SendVerificationView` accepts `lang` parameter.
- **Dynamic HTML lang attribute**: `<html lang>` now updates when user switches language
- **Translated aria-labels**: Clear, Remove, Dismiss buttons now use i18n system

### Fixed
- **Dashboard "Failed to load recommendations" bug**: Root cause — `StudentProfile.colorblind` and `disability` were `CharField` storing "Ya"/"Tidak" strings, but eligibility serializer expected `BooleanField`. Converted both fields to `BooleanField` end-to-end (model, engine, serializer, views, tests). Migration 0046 applied to Supabase.
- **Landing page stats**: Corrected from "1,500+" to "1,300+" courses and "838" to "800+" institutions
- **Login button overflow on mobile**: Replaced `btn-primary` base class (which forced `px-6 py-3`) with explicit compact styling + `whitespace-nowrap`
- **Profile incomplete count badge**: Fixed hardcoded `1` to use `{contactDetailsIncomplete}` variable

### Changed
- **Serializer no longer converts booleans to "Ya"/"Tidak"**: `EligibilityRequestSerializer.to_internal_value()` now passes booleans through directly
- **Engine checks use boolean logic**: `student.colorblind == 'Tidak'` → `not student.colorblind` in both SPM and STPM engines

### Stats
- Backend tests: 892 pass, 0 failures
- Frontend tests: 17 pass, 0 failures
- Golden masters: SPM 5319, STPM 2026 (unchanged)

---

## STPM Pipeline Completion Sprint (2026-03-18)

### Added
- **`is_active` field on StpmCourse**: BooleanField (default True) — deactivated courses hidden from search and eligibility
- **Course deactivation in `sync_stpm_mohe`**: `--apply` now deactivates removed courses and reactivates returned ones
- **STPM audit sections in `audit_data`**: 3 new sections — STPM courses (active/inactive, description, headline, MOHE URL, merit, institution, careers), requirements (coverage, subject groups), career mappings (M2M link count)
- **Stage 5 in STPM workflow**: Deactivation stage added to `stpm-requirements-update.md`

### Fixed
- **MOHE scraper selectors**: Rewrote `_parse_cards()` for redesigned ePanduan DOM — uses `.executive-data-label`/`.executive-data-value` instead of stale generic selectors. Changed page load strategy from `networkidle` (hung) to `domcontentloaded` + explicit selector wait. Added deduplication via `Set`. Verified: 1,002 Science programmes scraped successfully.
- **All STPM queries filtered by `is_active=True`**: 8 query sites updated (1 in `stpm_engine.py`, 7 in `views.py`). Detail view and saved courses intentionally NOT filtered.

### Stats
- Backend tests: 888 pass, 0 failures (was 829)
- Frontend tests: 17 pass, 0 failures
- Golden masters: SPM 5319, STPM 2026 (unchanged)
- New tests: 12 (model 2, engine 1, search 2, sync 7)

---

## SPM Prereq UI & Content Sprint (2026-03-18)

### Added
- **STPM SPM prereq stream-based UI**: Section 4 of STPM grades page redesigned with stream pills (Science/Arts/Technical), 4 stream subject slots, 0-2 elective slots
- **SPM_PREREQ_STREAM_POOLS**: New data structure in `subjects.ts` providing stream-specific subject pools for STPM SPM prerequisites
- **8 new subject display names**: teknologi_kej, prinsip_elektrik, etc. added to SUBJECT_NAMES in subjects.ts
- **SPM_PREREQ_OPTIONAL expanded**: 2 → 9 entries (added phy, chem, bio, poa, ekonomi, moral, geo)
- **7 i18n keys**: spmStream, spmStreamHint, spmAddElective, spmSains, spmSastera, spmTeknikal, spmVokasional across EN/MS/TA

### Fixed
- **NRIC/phone formatting**: Standardised display formatting in admin views
- **Admin mobile layout**: Improved responsive layout for admin portal on mobile devices
- **Site content**: Updated to cover both SPM and STPM students (was SPM-only)

### Stats
- Backend tests: 654 pass, 0 failures
- Frontend tests: 17 pass, 0 failures
- Golden masters: SPM 5319, STPM 2026

---

## Post-Launch Hardening Sprint (2026-03-17)

### Added
- **Rate limiting on email verification**: 3 requests/hour per profile to prevent Gmail 500/day abuse
- **SPM_CODE_MAP expansion**: 13 → 121 entries for complete STPM prerequisite coverage (all SPM subjects mapped)
- **Merit formula documentation**: "DO NOT CHANGE" blocks on all 4 formulas (SPM UPU, Matric, STPM mata gred, STPM CGPA) with full breakdowns
- **STPM MUET float support**: `min_muet_band` changed from IntegerField to FloatField (65 courses have fractional bands)
- **IC/verify-email i18n**: Trilingual support for IC claim page and verify-email landing page

### Fixed
- **SPM merit subject grouping**: `prepare_merit_inputs()` was grouping 5+3+1 subjects instead of correct UPU formula 4+2+2 (core/stream/elective)
- **NRIC validation**: Date portion validated (catch typos), age 15-23 enforced, state code validated against known codes
- **Mobile layout**: Header and dashboard card layout improved on mobile breakpoints
- **Dashboard TOP MATCHES**: Backend returned `top_5`/`rest` split globally — when filtered by pathway, some categories had fewer than 3 cards. Now returns single `ranked` list; frontend filters first, then splits into top 3 + rest

### Changed
- **Ranking API response**: `{top_5: [...], rest: [...]}` → `{ranked: [...]}`  (breaking change — frontend updated simultaneously)
- **STPM golden master**: Rebaselined 1994 → 2026 (MUET float fix + SPM_CODE_MAP expansion)

### Stats
- Backend tests: 654 pass, 0 failures (+9 net new)
- Frontend tests: 17 pass, 0 failures
- Golden masters: SPM 5319, STPM 2026

---

## Identity Verification + UI Polish Sprint (2026-03-17)

### Added
- **NRIC identity system**: NRIC as unique identity anchor with claim/reclaim model — raw SQL PK transfer for existing profiles
- **Contact fields**: `contact_email` and `contact_phone` on StudentProfile (separate from auth credentials)
- **Email verification**: EmailVerification model, Gmail SMTP send/verify endpoints, verify-email landing page
- **Profile redesign**: 5-section layout (identity, contact with verification badges, academic, preferences, special needs)
- **Onboarding IC claim flow**: IC page now claims NRIC on backend, handles existing profile transfer
- **Referral link sharing**: Admin dashboard card with copy button, WhatsApp share, and QR code (`react-qr-code`)
- **Admin login back link**: "Kembali ke laman utama" link on `/admin/login`
- **Course compare feature**: Side-by-side comparison of 2-3 saved courses (desktop only, hidden on mobile)
- **Admin UI polish**: Student list — subtitle, download icon, pagination (5/page), blue left-border accent on names
- **Admin UI polish**: Student detail — icons on card headers, grade pill badges, rounded-xl cards, redesigned danger zone

### Changed
- **State sync**: Bidirectional sync between onboarding profile page and main profile page (localStorage + backend API)
- **Outcomes merged into Saved**: Deleted `/outcomes` page — application tracking now inline on `/saved` page via `interest_status`
- **Admin dashboard**: Returns `org_code` for referral URL generation
- **STPM golden master**: Rebaselined 1995 → 1994 (fixture corrections)

### Removed
- `/outcomes` page (`src/app/outcomes/page.tsx`) — redundant with saved page tracking

### Stats
- Backend tests: 645 pass, 0 failures (+30 new: profile fields, NRIC claim, email verification)
- Golden masters: SPM 5319, STPM 1994
- Migrations: 0039 (contact fields), 0040 (phone migration), 0041 (email verification)

---

## Admin Portal Student Pages Enhancement (2026-03-17)

### Added
- **Student list columns**: Sekolah, Telefon, Sumber (super admin only) added to admin student table
- **Student detail page**: Rewritten with 9 info cards showing all captured student data (personal, academic, contact, family, admin)
- **Dual grades display**: Both SPM and STPM grades shown simultaneously when student has both
- **Delete student endpoint**: `DELETE /api/v1/admin/students/<id>/` — super admin only, requires typing "delete" to confirm
- **Email in profile API**: ProfileView now returns email from Supabase Auth JWT
- **Profile completeness**: `angka_giliran` added to incompleteness badge count

### Changed
- Backend serializers expanded with `select_related` for N+1 query prevention
- Referral source column restricted to super admin only
- STPM golden master rebaselined: 2098 → 1995 (fixture corrections)

### Stats
- Backend tests: 615 pass, 0 failures
- Golden masters: SPM 5319, STPM 1995

---

## Admin Auth Sprint (2026-03-16)

### Added
- **PartnerAdmin model**: Separate admin identity table (`partner_admins`) with `supabase_user_id`, org FK, `is_super_admin`, name, email — replaces `admin_org_code` on StudentProfile
- **Admin invite endpoint**: `POST /api/v1/admin/invite/` — super admin only, calls Supabase `inviteUserByEmail`
- **Admin orgs endpoint**: `GET /api/v1/admin/orgs/` — returns all partner organisations
- **AdminRoleView**: Returns `admin_name` for display in admin UI
- **Isolated admin Supabase client**: Separate localStorage key (`halatuju_admin_session`) — admin and student sessions are completely independent
- **AdminAuthProvider + useAdminAuth() hook**: Wraps only `/admin/*` routes, checks PartnerAdmin role via backend
- **Admin login page** (`/admin/login`): Email/password + Google sign-in + forgot password
- **Admin OAuth callback** (`/admin/auth/callback`): Handles Google sign-in redirect
- **Admin invite page** (`/admin/invite`): Super admin only, supports existing or new org toggle
- **Admin layout**: Nav with Dashboard | Pelajar | Invite | Log Out, separate from student auth
- **Admin link**: Added to footer next to Contact Us
- `contact_person` and `phone` fields added to PartnerOrganisation
- `getOrgs()` and `inviteAdmin()` functions in `admin-api.ts`
- PartnerAdmin registered in Django admin
- 14 new admin auth tests (`test_admin_auth.py`)

### Changed
- **PartnerAdminMixin** rewritten: Uses `partner_admins` table with UID lookup + email fallback + UID backfill (replaces `admin_org_code` lookup on StudentProfile)
- All admin pages rewired from `useAuth()` to `useAdminAuth()`

### Removed
- `admin_org_code` field from StudentProfile (migration 0037)

### Stats
- Backend tests: 615 pass, 0 failures (was 590)
- Migrations: 0036_partneradmin, 0037_remove_admin_org_code_add_org_fields

---

## IC Gate + Profile Redesign Sprint (2026-03-15)

### Added
- **IC Gate**: New compulsory IC number step in AuthGateModal after Gmail/phone auth — replaces school name input
- **IC utilities**: `ic-utils.ts` with auto-dash formatting (`XXXXXX-XX-XXXX`), validation (DOB age 15–23, valid state code), and masked display (`****-**-1234`)
- **IcInput component**: Reusable input with `inputMode="numeric"`, auto-formatting, blur validation, and error display
- **Profile completeness hook**: `useProfileCompleteness()` counts 8 key unfilled fields (name, NRIC, gender, state, phone, income, siblings, address)
- **Incompleteness badge**: Red badge on profile nav link and avatar showing count of unfilled fields
- **Returning user skip**: IC gate is skipped if user already has NRIC stored in backend
- **i18n keys**: 16 new keys × 3 languages (EN/MS/TA) for IC gate and profile view/edit
- **Jest config**: `jest.config.js` for TypeScript test support in frontend

### Changed
- **Profile page redesign**: View mode by default with per-section Edit/Save/Cancel. IC always masked and read-only. Only one section editable at a time. Global save button removed.
- **AuthGateModal**: `ModalStep` type now includes `'ic'` step. School input removed. NRIC synced to backend via `SyncProfileData`.
- **SyncProfileData**: Added `nric` field to API interface

### Stats
- Frontend tests: 17 pass (IC utils)
- Backend tests: 293 pass, 0 failures
- Files created: 4 (ic-utils.ts, ic-utils.test.ts, IcInput.tsx, useProfileCompleteness.ts)
- Files modified: 6 (AuthGateModal.tsx, api.ts, AppHeader.tsx, profile/page.tsx, en/ms/ta.json)

---

## API Consistency Sprint — TD-005, TD-006, TD-022, TD-026, TD-052 (2026-03-15)

### Changed
- Standardised list endpoint count keys: `count` → `total_count` in CourseListView, InstitutionListView, OutcomeListView (TD-006)
- Added `course_name` alias to `CourseSerializer` — all endpoints now include `course_name` alongside `course` for consistency (TD-026)
- Extracted `SOURCE_TYPE_ORDER` to module-level constant in `views.py` (TD-022)
- Extracted merit gap thresholds to named constants: `MERIT_GAP_HIGH`, `MERIT_GAP_FAIR`, `MERIT_COLORS` in `engine.py` (TD-052)
- `eligibility_service.py` merit tuples now derive colours from `engine.MERIT_COLORS` instead of duplicating hex values (TD-052)
- Audited error responses — already consistently use `{'error': 'message'}` pattern (TD-005)

### Stats
- Tests: 424 pass, 0 failures
- Golden masters: SPM 5319, STPM 1811
- Tech debt resolved: TD-005, TD-006, TD-022, TD-026, TD-052 (35/52 total resolved)

---

## Legacy Cleanup — TD-028, TD-029, TD-031, TD-032 (2026-03-15)

### Removed
- `_archive/streamlit/` — 246 files, 80MB legacy Streamlit app (TD-029)
- `data/stpm/` — 4 CSV source files, data now lives in Supabase + test fixtures (TD-028)
- 6 one-time management commands: `load_csv_data`, `load_stpm_data`, `enrich_stpm_metadata`, `populate_stpm_urls`, `fix_stpm_names`, `backfill_masco` (TD-031)
- Streamlit path references resolved by deleting `load_csv_data.py` (TD-032)

### Added
- `apps/courses/utils.py` — extracted `proper_case_name` and `build_mohe_url` from deleted commands
- `apps/courses/fixtures/stpm_courses.json` + `stpm_requirements.json` — 1,113 STPM courses as Django fixtures

### Changed
- 6 STPM test files migrated from `call_command('load_stpm_data')` to `loaddata` fixtures
- 4 recurring commands preserved: `audit_data`, `scrape_mohe_stpm`, `sync_stpm_mohe`, `validate_stpm_urls`

### Stats
- Tests: 424 pass, 0 failures (was 425 — removed loader idempotency test)
- Tech debt resolved: TD-028, TD-029, TD-031, TD-032 (29/52 total resolved)

---

## Tech Debt Quick Wins — TD-027, TD-030, TD-037, TD-049 (2026-03-15)

### Fixed
- Removed dead `LEGACY_KEY_MAP` from `engine.py` — never used, contained questionable `islam → moral` mapping (TD-027)
- Removed stale CSV row counts from model docstrings, now reference Supabase tables (TD-030)
- Deleted `db.sqlite3` from working directory — already in `.gitignore` (TD-037)
- Removed `as any` type assertion in profile page — properly typed `colorblind`/`disability` as `boolean | 'Ya' | 'Tidak'` union, typed gender/nationality state vars (TD-049)

### Stats
- Tests: 425 pass, 0 failures | TypeScript: 0 errors
- Tech debt resolved: TD-027, TD-030, TD-037, TD-049 (25/52 total resolved)

---

## Subject Key Unification — TD-013 (2026-03-15)

### Changed
- SPM grades page (`grades/page.tsx`) now uses engine keys (`bm`, `eng`, `math`) instead of uppercase frontend keys (`BM`, `BI`, `MAT`)
- Subject arrays removed from grades page — imports `SPM_CORE_SUBJECTS`, `SPM_STREAM_POOLS`, `SPM_ALL_ELECTIVE_SUBJECTS` from `subjects.ts`
- Subject display names use `getSubjectName()` from `subjects.ts` instead of inline `name` fields or i18n keys
- `GRADE_KEY_MAP` and `validate_grades` removed from `EligibilityRequestSerializer` — keys pass through as-is
- Report engine `SUBJECT_LABELS` fixed to use correct engine keys (`sci` not `sc`, `phy` not `phys`, `addmath` not `add_math`, `poa` not `acc`, `ekonomi` not `econ`) and expanded with missing subjects
- Calculate endpoints (`/calculate/merit/`, `/calculate/pathways/`) no longer reference `GRADE_KEY_MAP`
- All test files updated to send lowercase engine keys

### Added
- `SpmSubject` interface and `SPM_SUBJECTS` array in `subjects.ts` — single source of truth with category metadata
- Derived exports: `SPM_CORE_SUBJECTS`, `SPM_STREAM_POOLS`, `SPM_ALL_ELECTIVE_SUBJECTS`
- Missing vocational subjects added to `SUBJECT_NAMES` dict (`voc_construct`, `voc_weld`, `voc_auto`, `voc_elec_serv`, `voc_catering`, `voc_tailoring`)

### Stats
- Tests: 411 collected, 411 pass, 0 failures, 0 skipped
- Tech debt resolved: TD-013

---

## Refactoring Sprint — TD-045, TD-044 (2026-03-14)

### Changed
- `EligibilityCheckView.post()` reduced from ~310 lines to ~100 lines — business logic extracted to `eligibility_service.py` (TD-045)
- PISMP req hash collection merged into the main eligibility loop, eliminating double DataFrame iteration (TD-044)
- Unused imports removed from `views.py` (`defaultdict`, `check_merit_probability`, `check_matric_track`, `check_stpm_bidang`)
- TVET `source_type != 'tvet'` guard removed from merit calculation — confirmed 0/84 TVET courses have merit data

### Added
- `eligibility_service.py` — 5 pure functions: `compute_student_merit`, `compute_course_merit`, `deduplicate_pismp`, `sort_eligible_courses`, `compute_stats`
- `test_eligibility_service.py` — 19 unit tests covering all service functions

### Stats
- Tests: 406 collected, 406 pass, 0 failures, 0 skipped
- Tech debt resolved: TD-044, TD-045

---

## API Consistency Sprint (2026-03-14)

### Changed
- All HTTP status codes in `SavedCoursesView` and `SavedCourseDetailView` now use DRF constants (`status.HTTP_400_BAD_REQUEST`, etc.) instead of raw integers (TD-004)
- Unauthenticated requests now return 401 Unauthorized instead of 403 Forbidden (TD-011) — correct per RFC 7235

### Added
- `SupabaseAuthentication` DRF authentication class in `supabase_auth.py` — provides `WWW-Authenticate: Bearer` header so DRF returns 401 for unauthenticated requests
- `DEFAULT_AUTHENTICATION_CLASSES` in REST_FRAMEWORK settings

### Stats
- Tests: 387 collected, 387 pass, 0 failures, 0 skipped
- Tech debt resolved: TD-004, TD-011

---

## Security Hardening Sprint (2026-03-14)

### Changed
- Default REST Framework permission changed from `AllowAny` to `SupabaseIsAuthenticated` (TD-012) — new endpoints are now auth-required by default; 16 public endpoints explicitly marked with `AllowAny`
- `ProfileView.put()` and `ProfileSyncView.post()` now use `ProfileUpdateSerializer` with field-level validation instead of raw `setattr` loops (TD-008) — malformed input returns 400 instead of 500

### Added
- `ProfileUpdateSerializer` in `serializers.py` — ModelSerializer for `StudentProfile` with all 19 updatable fields, partial update support
- Production guard: `ValueError` raised if `SECRET_KEY` is the insecure default (TD-036)
- Production guard: `ValueError` raised if `CORS_ALLOWED_ORIGINS=*` (TD-038)

### Stats
- Tests: 382 collected, 382 pass, 0 failures, 0 skipped
- Tech debt resolved: TD-008, TD-012, TD-036, TD-038

---

## Test Health Sprint — Eliminate Skipped Tests & Auth Failures (2026-03-14)

### Fixed
- 13 auth/JWT test failures: added `jwt.get_unverified_header` mock alongside `jwt.decode` (TD-010, TD-033)
- 30 skipped tests: CSV data files no longer existed, tests silently skipped for months
- 2 stale assertions: `'Pre-University'` → `'Pra-U'` in matric/STPM eligibility tests
- Golden master count discrepancy in docs (TD-035): old CSV baseline 8283 was stale, correct DB baseline is 5319

### Changed
- Golden master test (`test_golden_master.py`): rewritten from CSV-loading unittest to pytest with DB fixtures, baseline 5319
- API endpoint tests (`test_api.py`): eligibility tests converted from CSV to DB fixtures via `conftest.load_requirements_df()`
- Pre-U tests (`test_preu_courses.py`): 5 redundant tests deleted (covered by test_pathways.py), 4 remain

### Added
- `apps/courses/fixtures/courses.json` — 389 Course records from production Supabase
- `apps/courses/fixtures/requirements.json` — 389 CourseRequirement records from production Supabase
- `apps/courses/tests/conftest.py` — shared helper to load DB data into DataFrame for tests

### Stats
- Tests: 382 collected, 382 pass, 0 failures, 0 skipped
- Tech debt resolved: TD-010, TD-033, TD-035
- SPM golden master: 5319 (DB fixtures) | STPM golden master: 1811

---

## TD-002 Sprint — Eliminate Frontend Calculation Duplication (2026-03-14)

### Added
- `/api/v1/calculate/merit/` — POST endpoint for UPU merit calculation
- `/api/v1/calculate/cgpa/` — POST endpoint for STPM CGPA calculation
- `/api/v1/calculate/pathways/` — POST endpoint for pre-U pathway eligibility + fit scores
- `get_pathway_fit_score()` in `pathways.py` — ported from frontend `pathways.ts`
- `calculateMerit()`, `calculateCgpa()`, `calculatePathways()` API client functions in `api.ts`
- 12 new backend tests (5 pathway fit score, 7 calculate endpoints)

### Changed
- Grades page calls `/calculate/merit/` API with 400ms debounce instead of local `calculateMeritScore()`
- STPM grades page calls `/calculate/cgpa/` API with 400ms debounce instead of local `calculateStpmCgpa()`
- Matric/STPM pathway pages call `/calculate/pathways/` API instead of local `checkAllPathways()`
- Dashboard inlines CGPA-to-percent formula (one-liner) instead of importing from `stpm.ts`

### Removed
- `halatuju-web/src/lib/merit.ts` (63 lines) — deleted
- `halatuju-web/src/lib/stpm.ts` (22 lines) — deleted
- `halatuju-web/src/lib/pathways.ts` (511 lines) — deleted
- Total: 596 lines of duplicated frontend calculation logic removed

### Stats
- Tests: 344 passing (+12 new), 13 pre-existing auth failures, 30 skipped
- Tech debt resolved: TD-002, TD-015, TD-017
- Backend is now single source of truth for all eligibility formulas

---

## Data Integrity Sprint (2026-03-14)

### Changed
- STPM "programmes" renamed to "courses" across entire codebase (23 files: models, views, serializers, tests, URLs, i18n)
- i18n strings updated (EN/BM/TA) — "programmes" → "courses" / "kursus" / "படிப்புகள்"
- Supabase `stpm_courses` columns renamed: `program_id` → `course_id`, `program_name` → `course_name`
- Django `db_column` workaround removed from `StpmCourse` model (real column rename eliminates technical debt)
- 2 course names fixed in Supabase: "Rekabentuk Industri" → "Reka Bentuk Industri", "Food & Beverage" → "Food and Beverage"

### Added
- 2 new courses from MOHE ePanduan audit:
  - FB0500001 Asasi Teknologi Kejuruteraan (Asasi TVET) — 10 polytechnics, merit 75.14%
  - UL0481001 Asasi Teknologi Maklumat Huffaz — UMK, merit 70.70%
- Full requirements and institution links for both new courses

### Stats
- MOHE audit: 363 CSV courses → 208 eligible (after UiTM/bumi/Islamic filters) → 196 matched, 2 added, 2 name-fixed
- Tests: 332 passing, 13 pre-existing auth failures, 30 skipped
- Database: 390 SPM courses, 1,113 STPM courses, 838 institutions

## Pre-U Courses Sprint (2026-03-13)

### Added
- 6 pre-university courses as real database entries: 4 matric tracks (Sains, Kejuruteraan, Sains Komputer, Perakaunan) + 2 STPM bidangs (Sains, Sains Sosial)
- `merit_type` field on `CourseRequirement` — drives matric grade-point and STPM mata gred formulas
- Merit calculation branching in eligibility endpoint: matric uses `pathways.py` grade-point formula, STPM uses mata gred formula
- `merit_display_student`/`merit_display_cutoff` fields in API response for STPM raw mata gred display
- 9 new tests for pre-U eligibility and search (`test_preu_courses.py`)

### Changed
- Badge consistency: TVET renamed to ILJTM/ILKBS (distinct colours), STPM → Tingkatan 6, University → ua, all labels in Malay
- Matric/STPM level badges → Pra-U (orange)
- `SOURCE_TYPE_ORDER` updated: matric/stpm ranked at priority 4

### Removed
- Synthetic matric/STPM pathway entries from eligibility endpoint (now real DB courses)

### Stats
- Tests: 320 passing, 9 pre-existing auth failures, 30 skipped | Supabase: 0 security errors
- Supabase migration applied: `merit_type` column + 6 courses + 6 requirements

## STPM Sprint 8 — Polish & Dashboard Upgrade (2026-03-13)

### Added
- STPM dashboard upgraded to use shared `CourseCard` component — field images, source type/level badges, merit progress bars, bookmark icons, institution names
- Merit-based ranking on STPM dashboard: High Chance (highest merit desc) → Fair (smallest gap first, no-rating in middle) → Low (smallest gap first)
- "Take Quiz" button on STPM dashboard header
- `field` added to STPM eligibility API response for frontend image matching

### Fixed
- STPM detail page crash (React error #438) — replaced `use(params)` with `useParams()` to avoid Suspense requirement
- 1,080 STPM programme names proper-cased in Supabase (was ALL CAPS) — Malay/English connector words correctly lowercased

### Removed
- "Browse All Programmes" link from STPM dashboard
- Inline custom STPM card rendering (replaced by CourseCard)

### Stats
- Tests: 218 collected, 205 passing (13 pre-existing auth/JWT failures) | SPM golden master: 8283 | STPM golden master: 1811
- Deploys: 4 (2 API, 2 web)

## STPM Sprint 7 — Unified Explore Page (2026-03-13)

### Added
- Unified `/search` page serving both SPM and STPM courses in a single browse experience
- `qualification` filter (SPM / STPM / All) — toggle buttons with blue/purple colour coding
- STPM courses mapped to `CourseCard` shape: program_id→course_id, program_name→course_name, university→institution_name, merit_score→merit_cutoff
- Bumiputera-only programmes (UiTM) excluded at runtime from STPM search results
- Eligible toggle dual-check: calls both `checkEligibility` (SPM) and `checkStpmEligibility` (STPM) from localStorage data, merging ID sets
- `field`, `category`, `description` columns on `StpmCourse` model — AI-generated metadata via Gemini 2.0 Flash
- `enrich_stpm_metadata` management command for one-time Gemini batch classification (1,113 courses classified)
- `University` source type in CourseCard with purple styling
- `Ijazah Sarjana Muda` level badge with purple styling
- i18n keys for qualification filter in EN/BM/TA
- 12 new tests for unified search endpoint (`TestUnifiedSearchEndpoint`)

### Changed
- `/stpm/search` now redirects to `/search?qualification=STPM` (5-line redirect replaces 177-line page)
- `CourseSearchView` rewritten to query both `Course` (SPM) and `StpmCourse` (STPM) tables
- Smart filter skipping: level/source_type/state filters only apply to relevant qualification
- `SOURCE_TYPE_ORDER` updated with University priority (5)
- Filters response merges SPM+STPM values and includes `qualifications` array

### Fixed
- Gemini API key lookup: uses `settings.GEMINI_API_KEY` instead of bare `os.environ.get()` (Django settings loads from .env)

## STPM Sprint 6 — Merit Scoring + UX Polish (2026-03-13)

### Added
- `merit_score` field on `StpmCourse` model — stores UPU average merit percentage (0–100)
- Merit data loader (`_load_merit_data`) in `load_stpm_data.py` — reads slim CSVs, handles "Tiada" as null
- Slim merit CSV files: `stpm_science_merit.csv` (1,003 rows), `stpm_arts_merit.csv` (677 rows)
- `merit_score` exposed in STPM eligibility API response and ranking pipeline
- `cgpaToMeritPercent()` utility in `stpm.ts` for consistent CGPA→merit conversion
- Merit traffic lights on STPM dashboard — High (green), Fair (amber), Low (red) badges per course card
- Merit summary counts in dashboard header (e.g. "302 High, 75 Fair, 77 Low")
- Empty state UI for STPM dashboard when zero courses qualify
- Elective add-button UX pattern (replaces permanent dropdown) on STPM grade entry
- 1,080 merit scores loaded into Supabase `stpm_courses` table (33 are "Tiada" = null)

### Changed
- Koko score scale corrected: `max="4"` → `max="10"`, formula `× 0.1` → `× 0.04`
- CGPA formula now: `(academicCgpa × 0.9) + (kokoScore × 0.04)` where koko is 0–10

### Fixed
- STPM dashboard crash when API returns zero eligible courses (missing `setStpmResults([])` in catch block)
- ICT stream classification: `'both'` → `'arts'` in `subjects.ts`
- Hardcoded English "degree programmes" replaced with i18n key `dashboard.qualifyCourses`
- Inline CGPA→merit calculation replaced with shared `cgpaToMeritPercent()` function

## STPM Sprint 5 — Grade Scale Fix + UX Redesign (2026-03-13)

See `retrospective-stpm-sprint5.md`

## STPM Sprint 4 — Search + Detail Pages (2026-03-13)

See `retrospective-stpm-sprint4.md`

## v1.33.0 — Unified Pre-U Backend & IPGM Integration (2026-03-12)

See `release-notes-v1.33.0.md`
