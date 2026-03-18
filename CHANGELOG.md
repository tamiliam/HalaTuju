# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — STPM Quiz Engine Sprint 3: Ranking Integration (2026-03-18)

### Changed
- **STPM ranking formula rewritten** (`stpm_ranking.py`): 7-component scoring — BASE(50) + CGPA_MARGIN(+20) + FIELD_MATCH(+12) + RIASEC_ALIGNMENT(+8) + EFFICACY_MODIFIER(+4/-2) + GOAL_ALIGNMENT(+4) - INTERVIEW(-3) - RESILIENCE_DISCOUNT(0/-3). Max score 98.
- **Eligibility output enriched** (`stpm_engine.py`): Eligible course dicts now include `riasec_type`, `difficulty_level`, `efficacy_domain` for ranking engine consumption
- **Ranking API returns framing** (`views.py`): `POST /stpm/ranking/` now includes `framing` object with mode (confirmatory/guided/discovery), heading, and subtitle from Q1 crystallisation signal

### Added
- **Result framing logic**: 3 modes based on Q1 — confirmatory ("Your profile aligns with..."), guided ("Based on your interests..."), discovery ("Here are fields worth exploring")
- **STPM field_key → field_interest reverse mapping** (`_FK_TO_INTEREST`): Maps Q3 sub-field signals back to Q2 broad interest for secondary field matching

### Tests
- 58 ranking tests (was 11): CGPA margin (5), field match (9), RIASEC alignment (8), efficacy modifier (6), goal alignment (7), resilience discount (7), interview (2), full integration (4), framing (5), ranked results (5)
- 881 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Quiz Engine Sprint 2: Data Enrichment (2026-03-18)

### Added
- **3 new fields on StpmCourse**: `riasec_type` (R/I/A/S/E/C), `difficulty_level` (low/moderate/high), `efficacy_domain` (quantitative/scientific/verbal/practical) — for quiz-informed ranking in Sprint 3
- **`riasec_primary` field on FieldTaxonomy**: maps each field to its primary Holland RIASEC type
- **`enrich_stpm_riasec` management command**: deterministic classifier using field_key → RIASEC/difficulty/efficacy mappings from the design doc. Covers 37 field_keys (all except `umum` catch-all). Dry-run by default, `--apply` to save.
- **Migration 0044**: `add_riasec_difficulty_efficacy_fields`

### Tests
- 40 new enrichment tests (mapping completeness, correctness, consistency, DB fields, management command)
- 829 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Quiz Engine Sprint 1: Foundation (2026-03-18)

### Added
- **STPM quiz data** (`stpm_quiz_data.py`): ~35 questions × 3 languages (EN/BM/TA) with subject-seeded branching design grounded in Holland's RIASEC, SCCT, SDT, and Super's Career Development Theory
- **STPM quiz engine** (`stpm_quiz_engine.py`): RIASEC seed calculation from STPM subjects, branch routing (Science/Arts/Mixed), grade-adaptive Q4 resolution, cross-domain Q5 stream filtering, signal accumulation into 9-category taxonomy
- **3 new API endpoints**: `GET /stpm/quiz/questions/` (returns branch-specific questions), `POST /stpm/quiz/resolve/` (resolves Q3+Q4 after Q2 answer), `POST /stpm/quiz/submit/` (processes answers → signals)
- **STPM signal taxonomy**: 9 categories (riasec_seed, field_interest, field_key, cross_domain, efficacy, resilience, motivation, career_goal, context)
- **Cross-domain asymmetry enforcement**: Science students see 6 Q5 options; arts students see only achievable options (no science-prerequisite programmes)
- **Grade-adaptive confidence check**: Q4 uses actual STPM grades — weak grades (≤B-) trigger honest framing, strong grades trigger confirmatory framing

### Tests
- 102 new STPM quiz tests (56 engine + 22 data + 24 API)
- 775 backend tests, 0 failures
- Golden masters: SPM=5319, STPM=2026 (unchanged)

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 3: Validator + Workflow (2026-03-17)

### Added
- **Validator tool** (`Settings/_tools/stpm_requirements/validate_stpm_requirements.py`): 6 automated quality checks — completeness, subject key validity (validates against canonical key sets), grade validity, count sanity, cross-reference with source CSV, sample audit against raw HTML
- **Reusable workflow** (`Settings/_workflows/stpm-requirements-update.md`): Annual STPM requirements refresh SOP covering all 5 pipeline stages with checkpoints and failure modes

### Fixed
- Validator subject key check now catches invalid keys beyond `UNKNOWN:` prefix (validates against `VALID_STPM_KEYS`/`VALID_SPM_KEYS` sets)
- Validator handles `stpm_named_subjects` as list of dicts (real data format), not just list of strings
- Validator CSV cross-reference gracefully handles missing files instead of crashing
- Validator sample audit uses isolated PRNG (`random.Random(42)`) instead of global seed

### Tests
- 49 new validator tests (248 total pipeline tool tests)
- 590 backend tests, 17 frontend tests, 0 failures
- Golden masters: SPM=5319, STPM=2103

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 2: Backend Integration (2026-03-16)

### Added
- **Fixture converter** (`Settings/_tools/stpm_requirements/stpm_json_to_fixture.py`): Converts structured JSON → Django fixture format with null-safety for non-nullable model fields
- **4 new StpmRequirement boolean fields**: `req_male`, `req_female`, `single`, `no_disability` (migration 0031)
- **List-aware subject group engine**: `check_stpm_subject_group()` and `check_spm_prerequisites()` now handle both single dict (legacy) and list of dicts (new pipeline) formats with AND semantics
- **Exclusion list support**: SPM prerequisites engine checks `exclude` lists — student needs min_count subjects at min_grade from any subject NOT in the exclude list
- **Demographic eligibility checks**: `check_stpm_eligibility()` now enforces `req_male`, `req_female`, `no_disability`
- **API fields**: STPM course detail response includes `req_male`, `req_female`, `single`, `no_disability`
- **SpecialConditions component**: Renders gender, marital, disability conditions with colour-coded indicators
- **i18n keys**: `maleOnly`, `femaleOnly`, `unmarriedOnly`, `noDisability` in EN/MS/TA
- **Search page fix**: SPM grades merged from `KEY_GRADES` into profile for eligibility checks
- **Dashboard fix**: Report existence synced with DB on fresh devices

### Changed
- **STPM golden master**: 1811 → 2103 (richer requirement data = more eligible matches)
- **stpm_requirements.json fixture**: Regenerated from new pipeline (1,113 courses)

### Tests
- 32 new fixture converter tests (199 total pipeline tool tests)
- 590 backend tests, 17 frontend tests, 0 failures
- Golden masters: SPM=5319, STPM=2103

## [Unreleased] — STPM Requirements Pipeline Rebuild Sprint 1: Parser Rewrite (2026-03-16)

### Added
- **Subject key registry** (`Settings/_tools/stpm_requirements/subject_keys.py`): 135+ subject mappings (25 STPM + 110 SPM), slash-combo handling, `UNKNOWN:` fallback
- **HTML→JSON parser** (`Settings/_tools/stpm_requirements/parse_stpm_html.py`): Per-`<li>` block parsing via BeautifulSoup, 11 block types, multi-tier STPM groups, exclusion lists
- **Pipeline test suite**: 167 tests (subject keys + parser + integration)
- Parsed 1,680 courses (1,003 science + 677 arts): 1.4% warning rate, 0 unknown subjects

## [Unreleased] — MASCO Career Mappings Sprint B: AI Mapping Pipeline (2026-03-16)

### Added
- **FIELD_KEY_TO_MASCO mapping**: Deterministic mapping from 31 field_keys to MASCO 2-digit occupation groups for pre-filtering
- **filter_masco_by_field_key**: Filters 4,854 MASCO jobs to ~200-400 relevant jobs per field
- **map_course_careers command**: AI-assisted career mapping pipeline
  - Generate mode (`--output`): iterates unmapped courses, calls Gemini, outputs review CSV
  - Apply mode (`--apply`): reads reviewed CSV, writes M2M links to DB
  - Supports both SPM (`--source-type`) and STPM (`--stpm`) courses
  - Rate limiting (`--delay`), batch size (`--limit`), Gemini model cascade

### Tests
- 12 new tests (5 mapping, 3 filter, 2 generate, 2 apply)
- Total: 568 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged)

## [Unreleased] — MASCO Career Mappings Sprint A: Backend Foundation (2026-03-16)

### Added
- **Full MASCO 2020 dataset**: `load_masco_full` management command loads 4,854 occupations from CSV with auto-generated eMASCO URLs (`https://emasco.mohr.gov.my/masco/{code}`)
- **StpmCourse.career_occupations**: New M2M field mirrors SPM `Course` model — STPM degree courses can now link to MASCO job codes
- **STPM detail API**: Now returns `career_occupations` array (same shape as SPM detail)
- **CareerPathways component**: Extracted from SPM detail page into shared component used by both SPM and STPM course detail pages; jobs with `emasco_url` are clickable, without are plain tags; hidden when empty

### Tests
- 10 new tests (4 data loading, 3 model, 3 API)
- Total: 556 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged — no eligibility/ranking changes)

## [Unreleased] — Field Taxonomy Sprint 5: Cleanup & Legacy Removal (2026-03-16)

### Changed
- **`field_key` non-nullable** — both `Course` and `StpmCourse` now require `field_key` (was nullable); all 1,503 courses already populated
- **Frontend field fallbacks** — all `course.field` references replaced with `getFieldName(course.field_key)` from taxonomy hook (detail pages, saved page, CourseCard)
- **Search API** — removed `?field=` fallback from frontend; only `field_key` sent

### Removed
- `frontend_label` column from `Course` model (migration 0028)
- `category` column from `StpmCourse` model (migration 0029)
- `frontend_label` from `CourseSerializer` output and TypeScript `Course` type
- `field` from `SearchParams` TypeScript type

### Tests
- Total: 530 backend + 17 frontend, 0 failures
- Golden masters: SPM=5319, STPM=1811 (unchanged)

## [Unreleased] — Field Taxonomy Sprint 4: Frontend Integration (2026-03-16)

### Changed
- **CourseCard images** — replaced 150-line `getImageSlug()` keyword matcher with taxonomy-driven lookup via `field_key` → `image_slug`; images now resolve from `FieldTaxonomy.image_slug` instead of hardcoded keyword rules
- **Search field filter** — dropdown now uses `/api/v1/fields/` taxonomy API with trilingual labels (EN/MS/TA) and filters by `field_key` instead of raw `frontend_label`/`field` strings
- **Search API** — `?field_key=` parameter now preferred over `?field=` for filtering; `field_keys` list added to search filter response
- **Dashboard** — STPM course cards now pass `field_key` through to CourseCard for correct image resolution

### Added
- `useFieldTaxonomy` hook — fetches taxonomy once, caches module-level, provides `getImageUrl(fieldKey)` and `getFieldName(fieldKey)` for trilingual field labels
- `fetchFieldTaxonomy()` API client function for `/api/v1/fields/`
- `field_key` added to `EligibleCourse`, `SearchCourse`, `StpmEligibleCourse` TypeScript types
- 2 new backend tests: `field_key` filter, `field_keys` in search filters

### Tests
- Total: 546 backend + 17 frontend, 0 failures

## [Unreleased] — Field Taxonomy Sprint 3: Ranking Engine field_key Integration (2026-03-16)

### Changed
- **SPM ranking** — field interest matching now uses `field_key` (taxonomy key) instead of `frontend_label` strings; `FIELD_LABEL_MAP` replaced by `FIELD_KEY_MAP`
- **STPM ranking** — keyword-based `_match_field_interest()` replaced with `field_key` lookup against shared `FIELD_KEY_MAP` (DRY); removed 48-line `COURSE_FIELD_MAP`
- **`field_health` signal** — now correctly maps to health fields (`perubatan`, `farmasi`, `sains-hayat`) instead of agriculture (was a bug)
- **`field_key` in eligibility results** — added to both SPM and STPM eligibility response dicts so ranking engines can use it

### Tests
- Updated 7 field interest tests (5 SPM, 2 STPM) from `frontend_label`/keyword to `field_key`
- Added 3 new tests: double-match bonus, no-field_key edge case (SPM + STPM)
- Total: 544 tests, 0 failures

---

## [Unreleased] — Field Taxonomy Sprint 2: STPM Classification + API Integration (2026-03-16)

### Added
- **STPM deterministic classifier** — `classify_stpm_course()` maps `category + field + course_name` to taxonomy key; handles ~170 category values across 29 taxonomy keys
- **`_classify_spm_matching()` helper** — sub-classifies 10 SPM-matching STPM categories using `course_name` (STPM field == category aggregate, not specific sub-discipline)
- **`FieldTaxonomySerializer`** — recursive serializer with `children` field for nested group→leaf structure
- **`GET /api/v1/fields/`** — returns 10 field groups with nested children (37 leaf fields)
- **`?field_key=` filter** — backwards-compatible query parameter on search endpoints (alongside existing `?field=`)
- **`field_key` in API responses** — added to SPM search, STPM search, and STPM course detail
- **`classify_stpm_fields` management command** — dry-run/save modes, distribution summary, safety checks
- **57 new STPM classifier tests** + 4 API endpoint tests (total 118 in test_field_taxonomy.py)
- **SQL reference script** — `scripts/stpm_backfill_field_key.sql` for documentation

### Database
- Backfilled all 1,113/1,113 STPM courses with `field_key_id` (0 unclassified)
- Distribution: 29 of 37 taxonomy keys used (top: pertanian=100, pendidikan=97, umum=77, sains-hayat=65, it-perisian=65)

---

## [Unreleased] — Field Taxonomy Sprint 1: Model + Migration + SPM Backfill (2026-03-16)

### Added
- **FieldTaxonomy model** — canonical table with 37 leaf fields + 10 parent groups, trilingual names (EN/MS/TA), image slugs, parent-child hierarchy
- **field_key FK** on `Course` and `StpmCourse` — nullable foreign key to FieldTaxonomy (will become non-nullable in Sprint 5)
- **Data migration** — populates all 47 taxonomy entries with trilingual names and sort orders
- **Deterministic classifier** — `classify_course()` maps `frontend_label + field + course_name` to taxonomy key; handles 16 production frontend_label variants
- **Backfill management command** — `backfill_spm_field_key` with `--save` flag (dry-run by default), safety check for PostgreSQL
- **Admin registration** — FieldTaxonomyAdmin with list/filter/search; CourseAdmin updated with field_key display/filter
- **55 new tests** — 7 model integrity tests + 48 classifier tests (including 24 production frontend_label tests)

### Database
- Created `field_taxonomy` table (47 entries) with RLS enabled (public read)
- Added `field_key_id` column to `courses` and `stpm_courses`
- Backfilled all 390 SPM courses (0 unmapped)
- Recorded Django migrations 0025 + 0026

---

## [Unreleased] — Special Conditions, Report Guard & Search Fix (2026-03-15)

### Added
- **Special Conditions expansion** — SpecialConditions component now shows gender restrictions (male/female only), unmarried requirement, and no-disability condition with colour-coded dots (blue/pink/purple/red)
- **i18n keys** — `maleOnly`, `femaleOnly`, `unmarriedOnly`, `noDisability` in EN/MS/TA
- **Contact form** — Supabase-backed contact form replaces raw email on contact page (name, email/phone, category, message)
- **Onboarding guard** — `useOnboardingGuard` hook protects dashboard/saved/profile/outcomes from users without grades
- **IC gate** — post-login IC + name collection page for users without NRIC
- **Smart auth routing** — Google OAuth and OTP login check NRIC → grades → route appropriately
- **Profile redesign** — two-column layout, amber incomplete indicators, email/phone/angka giliran fields, Yes/No toggles

### Fixed
- **Search "Eligible only" broken** — grades stored in `KEY_GRADES` but search page only read `KEY_PROFILE`; now merges both (root cause of 0 results)
- **"Generate Report" shown alongside "Read Report"** — syncs `reportGenerated` state from DB when localStorage flag missing (cross-device/cache clear)
- **Profile i18n bug** — `onboarding.name` key replaced with `profile.name` in all 3 languages
- **Mobile nav auth gate** — uses `link.authReason` instead of hardcoded `'profile'`

### Database
- Set `single = true` for 4 courses (IKBN-CET-005, UZ0520001, UZ0345001, UZ0721001) — recovered from deleted `details.csv`
- Created `contact_submissions` table with RLS (anon insert, service_role manage)

---

## [Unreleased] — Tech Debt Quick Wins 2 (2026-03-15)

### Added
- **Trilingual pre-U descriptions** — i18n keys (EN/MS/TA) for all 6 pre-U course headlines and descriptions in message files, replacing empty DB fields
- **Gemini API rate limiting** — max 3 reports per user per 24 hours via Django cache, returns 429 when exceeded (TD-009)
- **CourseListView pagination** — optional `?page=1&page_size=50` query params, backwards-compatible (TD-046)
- **Fallback description template** — `courses.descriptionFallback` i18n key replaces hardcoded fallback strings in course detail page

### Fixed
- **Engine field naming** — `three_m_only` used directly instead of runtime column rename hack in `apps.py` (TD-023)
- **Bug 4** — reclassified as "not a bug" (pre-U entry requirements are genuinely broad, not generic)
- **Bug 5** — pre-U description content added via i18n system (proper trilingual approach)

### Changed
- **Dependency pins relaxed** — `sentry-sdk>=1.39,<3.0` (was `<2.0`), `numpy>=1.24,<3.0` (was `<2.0`) (TD-039, TD-040)
- **Tech debt doc** — updated 10 items to reflect resolved status (5 from earlier sprints not marked, 5 new). Now 48/52 resolved.

---

## [Unreleased] — Bug Fixes & Auth Gating (2026-03-15)

### Added
- **Centralised localStorage keys** — `storage.ts` with 19 key constants + `clearAll()` helper, all 15 pages updated (TD-014 resolved)
- **Auth gating** — My Profile nav link, Load More buttons (dashboard SPM/STPM/ranked + search), and profile page now show sign-up modal for anon users
- **Saved courses UX** — institution name + course ID on saved cards, unified status toggle with correct state transitions (un-toggle "Got Offer" falls back to "Applied")
- **Error boundary pages** — `error.tsx`, `loading.tsx`, `not-found.tsx` for graceful error handling
- **Backend** — `institution_name` returned for both SPM and STPM saved courses
- **i18n** — `profileReason`, `loadmoreReason` auth gate messages in EN/MS/TA; error/loading/not-found page keys

### Changed
- About page tagline: removed "No sign-ups" (all 3 languages) since sign-up is now required for key features

---

## [Unreleased] — Saved Courses Sprint 2 (2026-03-15)

### Added
- **`useSavedCourses()` shared hook** — single source of truth for save state, auth gating, optimistic updates, toast feedback, and resume-after-login across all pages
- **Toast notification system** — `ToastProvider` + `useToast()` hook with success/error variants, auto-dismiss after 3s, slide-in animation
- **Search page save** — bookmark icon on search results now reflects actual saved state and toggles correctly
- **Detail page visual states** — save button shows green "Saved" when saved, red "Remove from Saved" on hover, blue "Save This Course" when not saved (both SPM and STPM detail pages)
- **Saved page SPM/STPM tabs** — tabbed interface with counts, correct detail page links per type (`/course/` for SPM, `/stpm/` for STPM)
- **Translation keys** — `courseDetail.saved`, `saved.noSpm`, `saved.noStpm` in EN/MS/TA

### Changed
- **Dashboard** — replaced ~50 lines of inline save logic with `useSavedCourses()` hook call
- **SPM detail page** — replaced broken `handleSave` (no auth, no token) with hook
- **STPM detail page** — same fix as SPM detail page

### Removed
- Inline `savedIds` state, `handleToggleSave`, `handleSaveOrGate` from dashboard (moved to hook)
- Direct `saveCourse`/`unsaveCourse` imports from detail pages (now via hook)

---

## [Unreleased] — Saved Courses Sprint 1 (2026-03-15)

### Added
- **STPM course saving** — SavedCourse model supports both SPM and STPM courses via dual nullable FKs with DB check constraint
- **Qualification filter** — `GET /saved-courses/?qualification=SPM|STPM` filters saved courses by type
- **Auto-detect STPM** — POST with `stpm-*` prefix or explicit `course_type` saves to correct FK
- **`course_type` in response** — GET /saved-courses/ returns `course_type: 'spm' | 'stpm'` per entry
- **Frontend types** — `SavedCourseWithStatus.course_type`, `saveCourse` accepts optional `courseType`, `getSavedCourses` accepts optional `qualification` filter

### Changed
- **SavedCourse model** — `course` FK now nullable, `stpm_course` FK added, `unique_together` replaced with partial unique indexes
- **SavedCourseDetailView** — DELETE/PATCH check both FKs when looking up saved course

### Database
- Supabase migration: `stpm_course_id` column, nullable `course_id`, check constraint, partial unique indexes

### Tests
- Saved courses tests expanded from 3 to 17 (SPM CRUD, STPM CRUD, qualification filter, idempotent save, check constraint enforcement)
- Full suite: 425 pass, 0 fail, 0 skip

---

## [Unreleased] — External Links & MOHE Sprint (2026-03-14)

### Added
- **MOHE ePanduan integration** — `mohe_url` field on StpmCourse, auto-generated URL pattern for 1,113 STPM courses, validated with Selenium-based page content checker
- **MOHE scraper + sync** — `scrape_mohe_courses` and `sync_stpm_mohe` management commands for auditing MOHE catalogue against DB
- **STPM URL validator** — Selenium-based validator (not HTTP status — MOHE always returns 200). Checks rendered page content for "daripada 0 carian" to detect dead links
- **Course-level "More Info" pill** — About section on course detail pages now shows a contextual "More Info" link: MOHE ePanduan for UA/poly/kkom, polycc for poly (TBD), MOE sites for matric/form 6/PISMP, institution hyperlink for TVET
- **Institution website links** — Institution cards now link to the institution's own website URL instead of the course-level hyperlink
- **STPM institution cards** — Rich institution card on STPM detail page with acronym, type, category, state, and website link (looked up from Institution table)
- **ILJTM/ILKBS filter split** — Search API resolves `tvet` source_type into `iljtm`/`ilkbs` using `course_pathway_map`; filter dropdown shows them separately
- **IPG campus URLs** — 27 IPG campuses populated with correct website URLs
- **Annual STPM data refresh procedure** — Documented in `docs/stpm-annual-refresh.md`

### Changed
- **Search limit** — Backend limit bumped from 100 to 10000 for full result sets
- **Merit colour logic** — STPM mata gred courses use inverted colours (low = green/good); arts stream ≤12 green, science ≤18 green
- **Pre-U course detail** — Department and WBL fields hidden for pre-U courses (not meaningful)
- **"More Info" pill style** — STPM detail page changed from "View on ePanduan (MOHE)" text link to compact pill button

### Fixed
- **1 dead MOHE URL** — UJ6521004 cleared after Selenium validation confirmed "daripada 0 carian"
- **Kolej Komuniti URL** — 1 missing institution URL fixed
- **Search pathway_type** — Search results now include `pathway_type` and `qualification` fields for correct badge rendering

---

## [Unreleased] — Security, API Consistency & Refactoring Sprints (2026-03-14)

### Changed
- **Default permissions flipped** — `DEFAULT_PERMISSION_CLASSES` changed from `AllowAny` to `SupabaseIsAuthenticated` (TD-012). 16 public views explicitly marked.
- **401 for unauthenticated** — Added `SupabaseAuthentication` DRF class; unauthenticated requests now return 401 with `WWW-Authenticate: Bearer` instead of 403 (TD-011)
- **DRF status constants** — All raw integer status codes replaced with DRF constants (TD-004)
- **EligibilityCheckView refactored** — Extracted 5 pure functions into `eligibility_service.py`, view reduced from 310 → 100 lines (TD-045)
- **Double DataFrame iteration eliminated** — `_apply_pismp_dedup()` no longer iterates twice (TD-044)

### Fixed
- **ProfileUpdateSerializer** — PUT/PATCH profile now validates via serializer instead of accepting arbitrary fields (TD-008)
- **SECRET_KEY guard** — Production raises ValueError if SECRET_KEY equals insecure dev default (TD-036)
- **CORS wildcard guard** — Production raises ValueError if CORS_ALLOWED_ORIGINS=* (TD-038)

---

## [Unreleased] — Tech Debt Sprint 4 (2026-03-14)

### Fixed
- **TD-001: STPM SPM prerequisite check** — Added `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS` in `stpm_engine.py`. Zero programmes currently set these flags, so no eligibility results changed. STPM golden master baseline unchanged at 1,811.
- **TD-050: Quiz language bug** — Quiz page now reads locale from i18n context (`useT()`) instead of non-existent `halatuju_lang` localStorage key. Quiz loads in the user's selected language (EN/BM/TA).
- **TD-007: Bare except in engine.py** — `check_merit_probability()` now catches `(ValueError, TypeError)` instead of bare `except:`.
- **TD-020: Duplicate serializer key** — Removed duplicate `credit_stv` entry in `SPECIAL_FIELDS` dict.
- **TD-018: Duplicate import** — Removed redundant `from django.db.models import Count, Subquery, OuterRef` inside `EligibilityCheckView.post()`.
- **TD-019: Inline imports** — Moved `json` and `defaultdict` imports from inline method bodies to top of `views.py`.

---

## [Unreleased] — Hotfix Sprint (2026-03-14)

### Added
- **STPM programme institution enrichment** — Detail API now looks up university in `institutions` table, returning acronym, type, category, state, URL; frontend renders rich institution card matching SPM style
- **i18n: Max Grade Points** — New key `courseDetail.maxGradePoints` in EN ("Max Grade Points"), BM ("Mata Gred Maksimum"), TA ("அதிகபட்ச தர புள்ளிகள்")

- **STPM sidebar redesign** — Entry Requirements consolidated into unified card matching SPM route: General Requirements (checkmarks), STPM Requirements (key-value table), STPM Subjects (blue pills), SPM Prerequisites (green pills), Special Conditions (separate card with warning icon). STPM Subjects and SPM Prerequisites moved from left column to sidebar.

### Changed
- **Search: ILJTM/ILKBS resolution** — Search API now resolves `tvet` → `iljtm`/`ilkbs` using `course_pathway_map`; filter options show ILJTM and ILKBS separately instead of hidden `tvet`
- **Search: course limit removed** — Backend no longer caps at 100 courses; explore page shows all results
- **Course detail: merit label** — "Avg. Mata Gred" → "Max Grade Points" (i18n) for `stpm_mata_gred` merit type
- **Course detail: merit colour logic** — Arts stream: ≤12 green, 13-18 amber, >18 red; Science stream: ≤18 green, >18 amber

### Fixed
- **ILJTM/ILKBS badges on explore page** — CourseCard now receives `pathway_type` from search API, showing correct ILJTM/ILKBS badges instead of undefined
- **DB: Arts merit cutoff** — `stpm-sains-sosial` cutoff updated from 18 → 12 in Supabase

---

## [Unreleased] — UI Polish & Consistency Sprint

### Added
- **Rich institution cards for pre-U courses** — STPM course detail (`/course/stpm-*`) now shows schools with PPD, subjects (colour-coded badges), phone numbers from frontend JSON data; matric courses show colleges with tracks, phone, website
- **Subject Key legend** — STPM course detail pages include a sidebar legend explaining subject abbreviations (BT, L.ENG, etc.)
- **STPM programme detail redesign** — `/stpm/[id]` now matches SPM course detail format: header with level+stream badges, About section with AI description, Quick Facts sidebar (field, category, merit), institution card, save/actions buttons
- **STPM API enrichment** — Detail endpoint now returns `field`, `category`, `description`, `merit_score`

### Changed
- **Search filter labels standardised to Malay** — Universiti, IPGM, Politeknik, Kolej Komuniti, Kolej Matrikulasi, Tingkatan 6, ILJTM, ILKBS
- **TVET removed from search filter** — ILJTM and ILKBS appear separately; redundant "tvet" option hidden

### Fixed
- **Dashboard pathway pills** — matric/stpm pills now appear; university pill fixed (`'ua'` → `'university'` key)
- **Badge key case** — TYPE_LABELS/TYPE_COLORS changed from uppercase to lowercase keys to match API response
- **University ranking** — Added `'university'` key to PATHWAY_PRIORITY (was only `'ua'`)
- **Pathway priority** — Corrected order: asasi(8) > matric(7) > stpm(6) > university(5) > poly(4) > pismp(3) > kkom(2) > iljtm/ilkbs(1)
- **Institution name on SPM cards** — Dashboard course cards now show institution name, state, and count
- **DB state normalisation** — "Kuala Lumpur" → "WP Kuala Lumpur" (3 IPG campuses), "Labuan" → "WP Labuan" (1 matric college)
- **Level rename** — "Ijazah Sarjana Muda Pendidikan" → "Ijazah Sarjana Muda" (73 rows in Supabase)

## [Unreleased] — STPM Entrance (Sprints 1–5)

### Fixed (Sprint 5)
- **STPM grade scale** — Replaced E with D+(1.33), corrected C- from 2.00→1.67, kept E/G as legacy aliases in GRADE_ORDER for backward compatibility with parsed requirement data
- **Quiz signal localStorage key** — Dashboard STPM path read `halatuju_student_signals` (nonexistent) instead of `halatuju_quiz_signals`; quiz signals now reach STPM ranking correctly
- **STPM ranking field_interest format** — Fixed default value from `[]` to `{}` to match quiz engine's dict format

### Changed (Sprint 5)
- **STPM grade entry page redesign** — Stream selector (Science/Arts) as Section 1; 3 stream-filtered subject slots + 1 open elective; co-curriculum score input (0.00–4.00); overall CGPA = 90% academic + 10% co-curriculum; MUET as plain numbers; SPM prereqs split into 4 compulsory + 2 optional
- **Frontend CGPA points** — `lib/stpm.ts` updated to match backend (C-=1.67, D+=1.33, removed E)
- **SPM prereq constants** — Split `SPM_PREREQ_SUBJECTS` into `SPM_PREREQ_COMPULSORY` (4) + `SPM_PREREQ_OPTIONAL` (2)
- **i18n** — 9 new keys × 3 locales (stream, koko, formula labels)

### Added (Sprint 4)
- **STPM search API** — `GET /api/v1/stpm/search/` with text, university, stream filters + cursor pagination (20/page)
- **STPM programme detail API** — `GET /api/v1/stpm/programmes/<id>/` with human-readable subject labels, SPM prereqs, flags
- **STPM search page** — `/stpm/search` with debounced text input, dropdown filters, responsive card grid, load-more
- **STPM detail page** — `/stpm/[id]` with breadcrumb, stream badge, subject pills, quick facts sidebar, requirement flags
- **i18n** — 33 new `stpm.*` keys in EN/BM/TA for search and detail pages
- **Dashboard link** — "Browse All Programmes" button linking to STPM search

### Added (Sprint 3)
- **Supabase migration** — `stpm_courses` + `stpm_requirements` tables with RLS policies, 2,226 rows loaded
- **STPM ranking engine** — `stpm_ranking.py` (BASE=50, CGPA margin +20, field match +10, interview -3)
- **STPM ranking API** — `POST /api/v1/stpm/ranking/` endpoint
- **Frontend fit scores** — `rankStpmProgrammes()` API client, colour-coded badges (green ≥70, amber ≥55, grey <55)

### Added (Sprint 1)
- **StpmCourse & StpmRequirement models** — Django models for ~1,113 unique STPM degree programmes across ~20 public universities
- **STPM CSV data loader** — `load_stpm_data` management command loads science (1,003) + arts (677) CSVs with idempotent update_or_create
- **STPM eligibility engine** — `stpm_engine.py` with CGPA calculator, grade comparison, SPM prerequisite checks, STPM subject/group requirements, demographic filters
- **STPM eligibility API** — `POST /api/v1/stpm/eligibility/check/` endpoint accepting STPM grades, SPM grades, CGPA, MUET band
- **STPM golden master** — baseline 1811 across 5 test student profiles
- **Implementation plan** — `docs/plans/2026-03-12-stpm-entrance.md` (5 sprints, 22 tasks)

### Added (Sprint 2)
- **STPM subject definitions** — `lib/subjects.ts` constants (20 subjects, grade scale, MUET bands, SPM prereqs) aligned with backend engine keys
- **Frontend CGPA calculator** — `lib/stpm.ts` mirrors backend `stpm_engine.py` grade-point mapping
- **Exam type activation** — `/onboarding/exam-type` page now enables STPM selection (was "Coming Soon"), sets `halatuju_exam_type` in localStorage
- **STPM grade entry page** — `/onboarding/stpm-grades` single combined page with STPM subjects (PA compulsory + 4 optional), MUET band pills, auto-calculated CGPA, SPM prerequisites (6 subjects)
- **STPM API client** — `checkStpmEligibility()` in `lib/api.ts` with typed request/response interfaces
- **Dashboard STPM routing** — `dashboard/page.tsx` conditionally renders STPM programme cards or SPM course cards based on `exam_type`
- **Backend STPM profile fields** — `StudentProfile` gains `exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band`, `spm_prereq_grades` fields with profile sync + API support
- **i18n support** — 14 new translation keys across EN/MS/TA for STPM onboarding flow

### Stats
- Tests: 320 collected, 287 passing (1 new in Sprint 5, 12 in Sprint 4, 13 in Sprint 3, 6 in Sprint 2) | SPM golden master: 8283 | STPM golden master: 1811
- STPM programmes: 1,113 unique (from 1,680 CSV rows with 567 overlapping)

## [1.33.0] - 2026-03-12 — Unified Pre-U Backend & IPGM Integration

### Added
- **Backend Matric/STPM eligibility** — `pathways.py` port of all frontend eligibility logic (4 Matric tracks, 2 STPM bidangs, 32 tests)
- **Matric/STPM in API response** — eligible tracks returned in `eligible_courses` with merit labels, display fields, mata_gred
- **Unified pre-U ranking** — `calculate_matric_stpm_fit_score()` routes matric/stpm through prestige + academic + field preference + signal scoring (12 tests)
- **27 IPG campuses** — all Institut Pendidikan Guru campuses added as institutions, linked to 73 PISMP courses (1,971 offerings)
- **Pathway-based sort priority** — `PATHWAY_PRIORITY` dict replaces `SOURCE_TYPE_PRIORITY` for correct Asasi > Matric > STPM > UA > Poly > PISMP > KKOM ordering

### Fixed
- **PISMP ranking** — credential priority changed from 4 to 2.5; pathway priority from 5 to 3. Now sorts below Poly High, above KKOM High
- **ILJTM/ILKBS sort placement** — merit fallback 1.5 places them between Fair and Low tiers
- **Matric/STPM credential priority** — was returning 0 (fell through all checks); now returns 5 via source_type and name-based fallback
- **Course name capitalisation** — fixed BAHASA MELAYU → Bahasa Melayu, SAINS PENDIDIKAN → Sains Pendidikan, Ukm → UKM

### Removed
- **Frontend synthetic pre-U entries** — 201 lines removed from `dashboard/page.tsx` (pathwayResults, mergedRankingData, syntheticFlat useMemos)

### Stats
- Tests: 259 collected, 250 passing | Golden master: 8283
- Institutions: 239 (212 existing + 27 IPG)
- Course offerings: +1,971 PISMP-IPG links

## [1.32.2] - 2026-03-11 — Unified Pre-U Scoring & Pathway Fixes

### Added
- **Unified pre-U scoring system** — Asasi, Matric, and STPM all use consistent prestige + academic + field preference + signal adjustment scoring
  - Prestige order: Asasi (+12) > Matric (+8) > STPM (+5)
  - Academic bonus: Matric >=94:+8, >=89:+4; STPM <=4:+8, <=10:+4; Asasi >=90:+8, >=84:+4
  - Field preference bonus (+3) when quiz field interest matches pathway variant
- **Asasi-specific scoring in ranking engine** — replaces generic course-tag matching for pathway_type == 'asasi'
- **Matric/STPM cards for non-authenticated users** — synthetic pathway entries now appear in flat course list (without quiz)
- **Pre-U scoring design document** — `docs/plans/2026-03-11-pre-u-scoring-design.md`

### Changed
- **STPM progress bar scale** — uses full 3-27 mata gred range; shows raw values ("You: 4 | Need: 18") instead of converted 0-100
- **STPM Social Science 13-18 label** — changed from "Low" to "Fair" (appeal zone via Autonomi Pengetua)
- **Pathway card links** — now pass track/stream query params (was defaulting to Science)
- **MeritIndicator component** — accepts `displayStudent`/`displayCutoff` props for raw value display

### Removed
- **"Your Eligible Tracks" section** from Matric detail page (redundant with card grid)

## [1.32.1] - 2026-03-11 — Pathway Chance Indicator

### Added
- **Merit chance bar on Matric/STPM cards** — same High/Fair/Low indicator as regular courses
  - Matric: >= 94 High, 89-93 Fair, < 89 Low
  - STPM Science: always High (guaranteed place if eligible)
  - STPM Social Science: <= 12 High, 13-18 Low

### Changed
- **STPM Social Science eligibility expanded** — maxMataGred raised from 12 to 18; students with 13-18 now appear as Low chance instead of being excluded

## [1.32.0] - 2026-03-11 — Pathway Ranking, Quiz Flow, Data Persistence

### Added
- **Matric/STPM in ranked results** — pre-university pathways now compete in the ranked course list as synthetic entries with prestige + academic + quiz signal scoring (fit score range ~103-122)
- **Prestige scoring system** — `getPathwayFitScore()` in pathways.ts combines base score, prestige bonus (+8), academic bonus (merit/mata gred thresholds), and quiz signal adjustments
- **Supabase profile restore on login** — returning users get grades, demographics, and quiz signals restored from Supabase into localStorage automatically
- **localStorage cleanup on logout** — all `halatuju_*` keys wiped when signing out (multi-user device safety)

### Changed
- **Quiz signal adjustments for pathways** — 8 quiz questions now boost or penalise Matric/STPM scoring (e.g. concept-first learners +2, hands-on preference -1, pathway priority +3)
- **Report generation gated** — report can only be generated once per quiz run; retaking quiz resets the gate
- **Retake quiz navigation** — "Retake Quiz" button now navigates to `/quiz` instead of staying on dashboard

### Fixed
- **STPM subject data** — removed duplicate `pp` from 2 schools, fixed `PK`→`PAKN` mapping, removed redundant `MM/PP` from Kolej T6 Tun Fatimah
- **Missing STPM subjects** — added BT, BC, KMK, ICT, L.ENG to subject key legend with colours and full names

## [1.31.0] - 2026-03-11 — STPM UX Polish, WP Schools, MASCO Backfill

### Added
- **16 WP Kuala Lumpur Form 6 schools** — added to STPM school dataset from MOE SST6 portal
- **MASCO backfill management command** — `backfill_masco` command populates MASCO codes for 62 courses missing them, using Supabase lookup
- **Stream-filtered subjects** — STPM detail page filters school subjects by selected stream (Sains/Sastera)

### Changed
- **Average merit cutoff** — Quick Facts now shows average merit cutoff across all institutions offering the course, instead of student's own merit score
- **Pathway track cards on dashboard** — pills now show track cards inline when selected, with stream badge filtering
- **Card badge vs title** — pathway card badge shows short label (e.g. "Matric") while title keeps the full pathway name
- **STPM school data** — converted to title case at source for consistency
- **Mobile layout** — shorter labels, better spacing for pathway cards and course detail on small screens
- **Subject badges** — coloured by stream, phone number formatting improved, legend added to STPM detail page

### Fixed
- **WP and JPN preserved as uppercase** — title-case conversion no longer lowercases state abbreviations
- **School acronyms preserved** — e.g. "SMK" stays uppercase in school names

## [1.30.0] - 2026-03-10 — Matric/STPM Detail Pages, About Page, UX Fixes

### Added
- **Matriculation detail page** (`/pathway/matric`) — course-detail-style layout with header card, About This Track, Where to Study (15 KPM colleges), Quick Facts, Eligible Tracks sidebar, merit score with traffic light
- **STPM detail page** (`/pathway/stpm`) — same layout with 568 schools, state + PPD filters, stream badges, load-more pagination
- **Pathway track cards** — dashboard shows cards for each eligible matric track and STPM bidang when pills are active, with images, duration, fee, and institution count
- **Static data files** — `matric-colleges.ts` (15 colleges with track assignments from MOE Soalan Lazim Nov 2024) and `stpm-schools.json` (568 schools from MOE SST6 portal)
- **PathwayTrackCard component** — card component for matric tracks and STPM bidang with Supabase field images
- **About page content** — full mission statement: problem, what it does, who's behind it, how to help
- **About page i18n** — all content localised in EN, BM, and Tamil
- **Pathway detail i18n** — 30 keys across EN/BM/TA for matric/STPM detail pages
- **Student merit in Quick Facts** — course detail sidebar now shows student's merit score with colour coding

### Changed
- **Pathway pills** — matric and STPM pills now navigate to detail pages instead of filtering courses
- **Pathway pills as clickable filters** — all other pills toggle dashboard course filter; Clear button resets
- **Pathway pill order** — Asasi, Matric, Form 6 shown first; count shows eligible tracks (not scores)
- **Course detail header** — removed duplicate field name and duration (already in Quick Facts)
- **Institution link** — "Apply" button renamed to "More Info"
- **Phone login** — gracefully blocked with "coming soon" message directing users to Google sign-in

### Removed
- **Filter dropdowns** — removed institution type and course level dropdowns from dashboard (replaced by clickable pills)
- **"Ranked Courses" heading** — removed as redundant with Top Matches section

## [1.29.0] - 2026-03-10 — 9 Post-SPM Pathway Summary

### Added
- **Expanded pathways** — dashboard now shows 9 post-SPM options: Asasi, Matriculation, Form 6, PISMP, Polytechnic, University, Kolej Komuniti, ILJTM, ILKBS
- **Backend pathway_type** — eligibility API returns `pathway_type` field distinguishing Asasi from University (within UA), and ILJTM from ILKBS (within TVET) via institution category lookup
- **Course pathway map** — built at startup from CourseRequirement source_type, Course level, and Institution category
- **Compact badge layout** — PathwayCards redesigned as compact flex-wrap badges with unique SVG icons per pathway type
- **Pathway i18n** — 9 pathway type labels in EN/BM/TA plus "courses" count label

### Changed
- **PathwayCards component** — rewritten from individual track cards to compact summary badges showing eligible pathway types with course counts
- **Dashboard** — merges pathway engine results (Matric/STPM) with API eligibility counts by pathway_type

## [1.28.0] - 2026-03-10 — Matriculation & STPM Pathways

### Added
- **Matriculation eligibility** — 4 tracks (Sains, Kejuruteraan, Sains Komputer, Perakaunan) with subject requirements, minimum grade thresholds, and merit calculation (academic 90% + CoQ 10%)
- **STPM eligibility** — 2 bidang (Sains, Sains Sosial) with mata gred scoring. Best 3 credits from different subject groups, thresholds 18/12
- **Pathway engine** — pure TypeScript module (`lib/pathways.ts`) computing eligibility and scores entirely on the frontend
- **PathwayCards component** — dashboard cards showing eligibility status, merit scores (Matric) or mata gred (STPM), with reasons for ineligibility
- **4 stream subjects** — grades page expanded from 2 to 4 stream subject slots. Best 2 count as stream for UPU merit; weaker 2 compete with electives
- **Pathway i18n** — 14 translation keys across EN/BM/TA for pathway cards and eligibility reasons

### Changed
- **Grades page** — `aliranSubj1`/`aliranSubj2` state replaced with `aliranSubjects` array. Generic `handleAliranChange(index, id)` handler
- **UPU merit calculation** — sorts 4 stream grades, routes best 2 to stream section and weaker 2 to elective competition pool
- **Dashboard** — pathway cards rendered above course list, computed via `useMemo` from localStorage grades

## [1.27.0] - 2026-03-10 — Visual Quiz Redesign

### Added
- **Visual card quiz** — 8+1 questions with 2×2 icon card grids replacing old radio buttons. Each option has an emoji icon and short label
- **Multi-select** — Q1 ("What catches your eye?") and Q2 ("And this?") allow picking up to 2 options with weight splitting (3→2 each)
- **Conditional branching** — Q2.5 ("Which kind?") appears only when "Big Machines" is selected in Q2, splitting heavy industry into Electrical/Civil/Aero-Marine/Oil & Gas
- **"Not Sure Yet" option** — Q1, Q2, Q4 have a 5th option for undecided students. Q1/Q2 distribute +1 evenly across fields; Q4 generates zero signal
- **Field interest category** — new 6th signal category with 11 signals (`field_mechanical`, `field_digital`, `field_business`, `field_health`, `field_creative`, `field_hospitality`, `field_agriculture`, `field_electrical`, `field_civil`, `field_aero_marine`, `field_oil_gas`), capped at ±8
- **Field interest matching** — courses matched against `frontend_label` via `FIELD_LABEL_MAP`. Primary match +8, secondary +4
- **New signal wiring** — `rote_tolerant` (+3 for assessment-heavy courses), `high_stamina` (+2 for demanding courses), `quality_priority` (+1 for pathway-friendly/regulated courses)
- **Quiz i18n** — 12 new translation keys across EN/BM/TA for quiz UI (pickUpTo, notSureYet, becauseYouPicked, etc.)
- **Interpolation in i18n** — `t()` function now supports `{key}` parameter substitution

### Changed
- **Quiz data** — rewritten from 6 to 8+1 questions × 3 languages with `icon`, `select_mode`, `max_select`, `condition`, `not_sure` fields
- **Quiz engine** — handles both `option_index` (single) and `option_indices` (multi), weight splitting, "Not Sure Yet" exclusivity validation
- **Quiz submit API** — accepts either `option_index` or `option_indices` per answer
- **Ranking engine** — work preference cap lowered from ±6 to ±4; field interest cap ±8 (new)
- **Quiz page design** — gradient blue-purple header, progress bar, step dots, auto-advance on selection (no Next button), larger icons (text-5xl), mobile-first max-w-md layout

### Removed
- Dead signals: `organising`, `meaning_priority`, `exam_sensitive`, `time_pressure_sensitive`, `no_preference`
- Next button — auto-advance handles all navigation (300ms single-select, 400ms multi-select)

### Technical Notes
- 24 quiz tests + 16 ranking tests added. Total: 212 collected, 203 pass (9 pre-existing JWT failures). Golden master: 8245
- Stitch mockup: `projects/16660567457727755942` (10 screens)
- Design doc: `docs/quiz-redesign-final.md`
- Implementation plan: `docs/plans/2026-03-10-visual-quiz-redesign.md`
- Deployed as backend rev 41, frontend rev 47

## [1.26.0] - 2026-03-09 — My Profile & Course Interests

### Added
- **My Profile page** (`/profile`) — new page with 4 sections: Personal Details, Contact & Location, Family & Background, My Course Interests
- **Expanded student profile** — NRIC, address, phone number, family monthly income, number of siblings fields added to `StudentProfile` model (migrations 0010, 0011)
- **Course interest status** — saved courses now have a student-set status tag: Interested / Planning to apply / Applied / Got offer. Stored in `SavedCourse.interest_status` field
- **PATCH endpoint** — `PATCH /api/v1/saved-courses/<course_id>/` for updating interest status
- **Nav bar integration** — "My Profile" link added to top nav, dropdown menu, and mobile menu (all point to `/profile`)
- **i18n** — profile page translated in EN, BM, and TA (16 keys per language)
- **Exam-type page redesign** — gradient icon boxes, decorative corners, left-aligned layout, hover effects
- **Course detail page review** — documented 10 issues and prioritised fixes in `docs/Course Detail Page.pdf`

### Changed
- Profile API (`GET/PUT /api/v1/profile/`) returns and accepts new fields
- Profile sync (`POST /api/v1/profile/sync/`) accepts new fields
- Saved courses API (`GET /api/v1/saved-courses/`) returns `interest_status` per course
- "My Profile" links in header dropdown and mobile menu now point to `/profile` (was `/onboarding/grades`)

### Technical Notes
- 13 new backend tests (6 model + 3 SavedCourse + 4 API). Total: 188 collected, 179 pass (9 pre-existing JWT failures). Golden master: 8280
- Frontend build passes clean. `/profile` route: 4.3 kB (169 kB first load)
- Deployed as backend rev 40, frontend rev 44
- Design doc: `docs/plans/2026-03-09-my-profile-design.md`
- Stitch mockup: `projects/13238979537238863747`

## [1.25.1] - 2026-03-09 — Merit Score Fix

### Fixed
- **Merit score mismatch** — grades page showed 68.88 but course cards showed 56.38 for the same student. The backend was recalculating merit using a different subject grouping (5/3/1) instead of the correct UPU formula (4/2/2). Now the frontend sends its pre-computed merit score to the backend, eliminating the duplicate calculation entirely.

### Changed
- **Eligibility endpoint** — accepts optional `student_merit` field. When provided, skips backend recalculation. Falls back to old calculation for backwards compatibility.

### Technical Notes
- Frontend: grades page saves `finalMerit` to localStorage; dashboard includes it in API payload
- Backend: serializer accepts `student_merit`; view uses it directly when present
- 166 tests pass (9 pre-existing JWT failures unchanged). Golden master: 8280
- Deployed as backend rev 33, frontend rev 42

## [1.25.0] - 2026-02-26 — Eligible Toggle Auth Gate + Merit Progress Bar

### Added
- **Eligible toggle prompts login** — clicking the "Eligible Only" toggle on `/search` now opens the auth gate modal if the user is not logged in, encouraging account creation. Previously the toggle was permanently disabled because `halatuju_eligible_courses` was never written to localStorage.
- **`eligible` auth gate reason** — new `AuthGateReason` type, i18n strings (EN, BM, TA), resume action so toggle auto-activates after login
- **Merit progress bar indicator (Variation C)** — replaced simple traffic-light dot with a visual progress bar showing the student's score inside the bar, a dashed cutoff line, and "High/Fair/Low Chance" label with numeric scores (e.g. "You: 72 | Need: 65")
- **`eligibleMap` state** on search page — stores full `EligibleCourse` data (not just IDs), enabling merit scores to flow into CourseCard on the search page

### Changed
- **Eligible toggle** — changed from disabled `<label>` to always-clickable `<button>` element
- **MeritIndicator component** — now accepts `studentMerit` and `meritCutoff` props; falls back to simple dot+label when numeric scores are unavailable

### Technical Notes
- Frontend only — no backend changes, no migrations
- Build passes cleanly
- Deployed as frontend rev 40 (eligible toggle) and rev 41 (merit progress bar)
- Backend rev remains 32

## [1.23.4] - 2026-02-26 — Stitch Design Polish

### Changed
- **Pill labels shortened** — "All Institution Types" → "Institution Type", "All Levels" → "Course Level", etc. (EN, BM, TA)
- **Pill background** — white → gray-100 fill matching Stitch design
- **Search placeholder** — descriptive: "Search for courses, institutions, or fields (e.g. Computer Science, UM)..."
- **Clear Filters always visible** — greyed out when no filters active, blue when filters applied

## [1.23.3] - 2026-02-26 — Filter Pill Dropdown Redesign

### Changed
- **Filter dropdowns restyled as pill/chip buttons** — replaced 4 native HTML `<select>` elements with custom `FilterPill` component matching Stitch design (compact rounded pills, chevron icon, dropdown panels)
- **Active filter state** — selected pills highlight with primary blue border/background
- **Clear Filters button** — now has funnel icon and rounded-full styling to match pills
- **Outside-click dismiss** — dropdown panels close when clicking outside

### Technical Notes
- New component: `src/components/FilterPill.tsx` (~100 lines, uses `clsx`)
- No new dependencies, no backend changes, no i18n changes
- Build passes cleanly

## [1.23.2] - 2026-02-25 — Search Page Stitch Alignment

### Added
- **Institution info on search cards** — each course card now shows the primary institution name, state (pin icon), and "+N more" count when offered at multiple institutions
- **Book icon** on field text in course cards for visual consistency with Stitch design
- **Clear Filters button** — appears in the filter row when any filter is active, resets all filters in one click
- **Eligibility toggle redesign** — replaced plain checkbox with a styled pill toggle, moved into the filter row with descriptive subtitle text
- **Search API: institution fields** — backend now returns `institution_name` and `institution_state` per course via Django Subquery (alphabetically first offering)
- **3 new backend tests** for institution name, state, and empty-offering fallback
- **3 new i18n keys** (`clearFilters`, `eligibleToggleDesc`, `moreInstitutions`) in EN, BM, TA

### Technical Notes
- Backend tests: 173 collected, 164 passing (9 pre-existing JWT failures — not production)
- Golden master: 8280 (unchanged)
- Files changed: 8 (1 backend view, 1 test, 1 API type, 3 i18n, 1 component, 1 page)

## [1.23.1] - 2026-02-25 — Deploy Fix: Suspense Boundary

### Fixed
- **Next.js prerender crash** — `/search` page crashed during Cloud Run build because `useSearchParams()` requires a `<Suspense>` boundary for static generation. Wrapped `SearchPageInner` in `<Suspense>` with a loading spinner fallback.
- **Stale container image** — previous failed deploy pushed a stale image to gcr.io (old Container Registry). Redeployed from source to Artifact Registry (`asia-southeast1-docker.pkg.dev`), restoring correct build. Frontend now on rev 35.

### Technical Notes
- Backend tests: 173 passing (13 pre-existing JWT test failures — not a production issue)
- Golden master: 8280 (unchanged)

## [1.23.0] - 2026-02-25 — Course Search / Explorer

### Added
- **Course search page** (`/search`) — browse the full course catalogue with text search and 4 filters (Institution Type, Course Level, State, Field)
- **Search API** (`GET /api/v1/courses/search/`) — server-side filtering, pagination, dynamic filter options, institution count per course
- **Eligible-only toggle** — if student has eligibility data, toggle to show only courses they qualify for
- **"Explore" nav link** — added to header between Dashboard and Saved
- **i18n** — full search page translations in EN, BM, TA
- **10 backend tests** for the search endpoint (text, level, field, source_type, state, pagination, combined, institution count)

### Changed
- **Institution URLs** — corrected 7 broken/outdated institution website links in `data/institutions.csv`

## [1.22.4] - 2026-02-25 — Profile Page Polish

### Changed
- **Profile icons** — replaced emoji icons (🇲🇾, 🌍, 👨, 👩, 🎨, ♿) with inline SVG icons for nationality, gender, and health condition buttons; icons change colour when selected
- **"Non-Malaysian" label** — renamed to "Foreign" (EN), "Asing" (BM), "வெளிநாட்டவர்" (TA) for clarity

## [1.22.3] - 2026-02-23 — Merit Formula Fix + Supabase Security

### Fixed
- **UPU merit formula** — replaced incorrect engine.py port with correct UPU calculation: `weighted = (core/72×40) + (stream/36×30) + (elective/36×10)`, `academic = weighted × 9/8`, cap 90 + CoQ
- **Stale grades bug** — grades from previously-selected subjects lingered in localStorage, inflating merit score; now only grades for currently-selected subjects (core + aliran + electives) are loaded
- **Dynamic merit on subject switch** — clearing old subject grades when switching stream, aliran, or elective subjects so merit updates immediately
- **14 Supabase RLS initplan warnings** — rewrote all RLS policies using `(select auth.uid())` subselect for performance
- **Supabase `django_migrations` RLS** — enabled Row Level Security on Django migrations table (security advisory)

### Changed
- **Merit score display** — removed green/yellow colour coding; score displays in neutral grey (no judgement)
- **Merit calculation** — grades page now passes categorised grades (core/stream/elective) directly instead of flat map with heuristic splitting

## [1.22.2] - 2026-02-23 — UI Polish: Grades Page

### Changed
- **Subject renames** — "Bahasa Tamil" → "Bahasa Cina/Tamil", "Bahasa Cina" → "Kesusasteraan Cina/Tamil" (combined options to shorten dropdown)
- **Stream pills** — equal-width grid layout, less rounded (rounded-xl), two-tone SVG icons (flask/book/wrench)
- **Shadow/depth treatment** — subtle shadows on core subject cards, stream pills, compact subject rows, merit panel, grade buttons (modern soft style)

### Added
- **Lukisan** — new subject in Arts stream pool and elective list (distinct from PSV)
- **StreamIcon component** — two-tone SVG icons for science/arts/technical streams

## [1.22.1] - 2026-02-23 — Sprint 20: Merit Score & CoQ

### Added
- **Co-curricular (CoQ) score input** — decimal number input (0-10, e.g. 5.50, 7.85) on profile page
- **Live merit score panel** — grades page shows real-time academic merit (/ 90) + CoQ (/ 10) = total (/ 100) as grades are entered
- **Client-side merit calculator** — TypeScript port of `engine.py` formula in `lib/merit.ts` (`prepareMeritInputs` + `calculateMeritScore`)
- New translation keys in EN, BM, TA: coqScore, coqHint, meritScore, academicMerit, coqMerit, meritTotal

### Fixed
- **Stream subject pre-population** — first-time visitors now see default stream subjects (PHY/CHE for science) instead of empty dropdowns

### Changed
- **Backend CoQ passthrough** — `EligibilityRequestSerializer` now accepts `coq_score` (float, 0-10); `views.py` uses it instead of hardcoded 5.0
- Dashboard passes saved CoQ from profile localStorage to eligibility API
- `StudentProfile` interface updated with optional `coq_score` field

## [1.22.0] - 2026-02-23 — Sprint 20: Onboarding Redesign

### Added
- **SPM/STPM exam type selection** — new `/onboarding/exam-type` screen with SPM card (active) and STPM card (coming soon)
- **Progress stepper** — shared `ProgressStepper` component shows "Step 1 of 3" with visual progress bars across all onboarding screens
- **Negeri (state) dropdown** — 16 Malaysian states/territories added to profile page
- **Elective subject add button** — "Tambah Subjek Elektif" dashed button to dynamically add 0-2 elective subjects
- New translation keys in EN, BM, TA for all new UI elements

### Changed
- **Stream + grades merged** — stream selection (compact pill buttons) now lives on the grades page, removing one navigation step
- **Core subjects redesign** — button grid with green checkmark on completion, clear icon, responsive 5+5 mobile layout
- **Stream/elective subjects redesign** — compact dropdown + grade badge dropdown rows replacing full button grids
- **Profile page compact layout** — single card with Negeri, Jantina toggle, Nationality toggle, Keperluan Khas checkboxes with accessibility icons
- **Improved helper text** — contextual subtitles on each screen ("Enter your grades so we can find courses that match your results")
- All `/onboarding/stream` links updated to `/onboarding/exam-type` across landing, dashboard, footer, login pages

### Removed
- `/onboarding/stream` page — stream selection moved into grades page

### Technical Notes
- Next.js build: 20 routes, 0 errors
- Files: 10 modified/created, 1 deleted
- Backend tests: 176 (unchanged — frontend-only sprint)
- Golden master: 8280 (unchanged)

## [1.21.0] - 2026-02-23 — Course Image Classification (37 Categories)

### Added
- **37 AI-generated course images** — replaced 9 generic field images with 37 category-specific images generated via Gemini 2.5 Flash Image, covering all 383 courses
- **Keyword-based image matching** — `CourseCard.tsx` now uses a multi-level matcher (`getImageSlug`) that routes courses to images based on field name and course name keywords
- **Sub-routing for large fields** — Pendidikan (73 courses) splits into 5 teaching-subject images; Mekanikal & Pembuatan (24) into 4; Elektrik & Elektronik (13) into 3; Teknologi Maklumat into 2
- **"Umum" dissolution** — 17 miscategorised "Umum" courses now route to proper categories via course name matching (e.g. perikanan → pertanian, bank → perakaunan)
- **Future STPM images** — pre-created images for Undang-undang and Farmasi categories

### Changed
- **Every course now has an image** — previous system had 97% of courses showing a grey placeholder (only 13/383 matched). Now 383/383 resolve to a relevant image
- **`getFieldImageUrl` signature** — now takes `(field, courseName)` instead of just `(field)`, enabling course-name-based sub-routing
- **Image generation script** — `tools/generate_field_images.py` rewritten with 37 categories, detailed Malaysian-context prompts, and `--skip-existing` flag

### Technical Notes
- 37 images uploaded to Supabase Storage `field-images` bucket (~1.5-2 MB each)
- 15-max rule: no image category covers more than 15 courses
- Next.js build: 20 routes compiled successfully
- Modified files: `CourseCard.tsx`, `generate_field_images.py`, `CHANGELOG.md`

## [1.20.0] - 2026-02-23 — Sprint 18: Header & Footer Redesign

### Added
- **AppHeader component** — shared responsive header with logo (120px), Dashboard/Saved nav links with active indicator, profile dropdown (name, email, My Profile, My Applications, Settings, Log Out), mobile hamburger menu with slide-out drawer
- **AppFooter component** — shared footer with brand column + tagline, Quick Links (Dashboard, Start Here, Saved), Legal links (About, Privacy, Terms, Cookies), copyright bar with Contact Us link
- **Profile dropdown** — shows user initials avatar, full name and email from Supabase session metadata, grouped account actions, red Log Out button with sign-out via Supabase
- **Cookies page** (`/cookies`) — explains essential cookies only, no tracking/analytics, links to Settings for data clearing
- **Contact page** (`/contact`) — Tamil Foundation (MCEF) contact info, email for enquiries and data deletion requests
- **Logout functionality** — first time users can sign out (calls `supabase.auth.signOut()`, redirects to landing)
- **i18n keys** — `header.*` (myProfile, myApplications, logout), `footer.*` (tagline, quickLinks, legal, startHere), `common.cookies`, `common.contact` in all 3 languages (EN, BM, TA)

### Changed
- **Logo optimised** — compressed from 6.2 MB to 27 KB (99.6% reduction), transparent background, 480px wide for retina
- **Logo size increased** — rendered at 120×40px across all pages (was 60×32px), improves brand visibility
- **All pages now use shared header/footer** — dashboard, saved, settings, outcomes, about, privacy, terms, course detail, report. Landing page uses shared footer with its own hero header. Quiz page keeps focused workflow header.
- **About/Privacy/Terms pages** — upgraded from back-arrow mini-headers to full AppHeader + AppFooter
- **Privacy page** — added contact email link

### Technical Notes
- Backend tests: 176 (unchanged) | Golden master: 8280 (unchanged)
- Next.js build: 20 routes compiled successfully
- New files: `AppHeader.tsx`, `AppFooter.tsx`, `/cookies/page.tsx`, `/contact/page.tsx`
- Modified: 15 frontend files, 0 backend files

## [1.19.1] - 2026-02-22 — Post-Sprint 17 Hotfixes

### Fixed
- **ES256 JWT authentication**: Supabase user access tokens use ES256 (JWKS), but middleware only accepted HS256 — all authenticated API calls (saved-courses, reports, outcomes) returned 403. Middleware now checks token `alg` header and routes to HS256 (JWT secret) or ES256 (JWKS public key via `PyJWKClient`).
- **Missing Cloud Run env vars**: Added `SUPABASE_JWT_SECRET`, `GEMINI_API_KEY`, and `SUPABASE_URL` to backend Cloud Run service.
- **Google name pre-fill**: AuthGateModal now pre-fills the user's name from their Google profile on OAuth sign-in.

### Added
- **"Read Report" button**: Dashboard shows "Read Report" (linking to existing report) instead of "Generate Report" when a report already exists. Reverts to "Generate Report" on quiz retake.
- **3 i18n keys**: `dashboard.readReport` in EN ("Read Report"), BM ("Baca Laporan"), TA ("அறிக்கையைப் படி")

### Technical Notes
- Backend tests: 176 (unchanged) | Golden master: 8280 (unchanged)
- Deployed: backend rev 26, frontend rev 20
- Cloud Run env vars added: `SUPABASE_JWT_SECRET`, `GEMINI_API_KEY`, `SUPABASE_URL`
- JWKS client uses `PyJWKClient` from `PyJWT` with automatic key caching

## [1.19.0] - 2026-02-22 — Sprint 17: Outcome Tracking

### Added
- **AdmissionOutcome model** — tracks student application outcomes (applied/offered/accepted/rejected/withdrawn) per course+institution, with intake year, session, notes, and date fields
- **CRUD endpoints** (`/api/v1/outcomes/` and `/api/v1/outcomes/<id>/`) — list, create, update status, delete. All auth-required, filtered to own outcomes.
- **"I Applied!" / "I Got an Offer!" buttons** on saved courses page — inline outcome creation with optimistic UI
- **Outcomes page** (`/outcomes`) — "My Applications" page listing all outcomes with colour-coded status badges, inline status editing, and delete
- **Track Applications CTA** on saved courses page — links to outcomes page
- **20 i18n keys** in `outcomes.*` section across all 3 locales (EN, BM, Tamil)
- 10 new backend tests: CRUD, duplicate (409), auth enforcement (403), cross-user isolation

### Technical Notes
- Backend tests: 176 (+10) | Golden master: 8280 (unchanged)
- Frontend build: passes clean
- Migration 0009 applied: `admission_outcomes` table with RLS + 5 policies
- Supabase security advisor: 0 errors (excluding known `django_migrations`)
- Sprint 16 deployed: backend rev 21, frontend rev 17

## [1.18.0] - 2026-02-22 — Sprint 16: Registration Gate

### Added
- **AuthGateModal** (`components/AuthGateModal.tsx`): Multi-step registration modal with inline Phone OTP + Google OAuth sign-in, reason-specific messaging (quiz/save/report), benefit bullets, and name+school profile completion form
- **AuthContext** (`lib/auth-context.tsx`): `AuthProvider` + `useAuth()` hook wrapping Supabase session state, providing `token`, `isAuthenticated`, `showAuthGate(reason)`, `hideAuthGate()`. Detects pending Google OAuth actions on mount.
- **ProfileSyncView** (`POST /api/v1/profile/sync/`): New backend endpoint that bulk-pushes localStorage data (grades, gender, quiz signals, name, school) to backend after first login — creates or updates profile in one call
- **`name` + `school` fields** on `StudentProfile` model (migration 0008) — for follow-up tracking
- **Profile sync API** (`syncProfile()` in `api.ts`) + `SyncProfileData` type
- **21 i18n keys** in `authGate.*` section across all 3 locales (EN, BM, Tamil)
- 4 new backend tests: sync creates profile, sync updates existing, sync rejects anon, profile PUT accepts name/school

### Changed
- **Dashboard**: Save button always visible (gates on auth if not logged in), Report CTA always visible (was hidden for guests), Quiz CTA triggers auth gate instead of direct navigation. Actions auto-resume after auth completion via localStorage resume action.
- **Quiz page**: Gated behind authentication — shows sign-in prompt with auth gate trigger for unauthenticated visitors
- **Dashboard imports**: Replaced ad-hoc `getSession()` with `useAuth()` hook for consistent auth state

### Technical Notes
- Backend tests: 166 (+4) | Golden master: 8280 (unchanged)
- Frontend build: passes clean
- Google OAuth edge case handled: pending action stored in localStorage before redirect, AuthProvider restores it on mount, modal opens at profile step
- New files: `components/AuthGateModal.tsx`, `lib/auth-context.tsx`
- Modified: `providers.tsx`, `dashboard/page.tsx`, `quiz/page.tsx`, `api.ts`, `views.py`, `models.py`, `urls.py`, `en.json`, `ms.json`, `ta.json`

## [1.17.0] - 2026-02-22 — Sprint 16: Bilingual Descriptions Pipeline

### Added
- `headline_en` and `description_en` fields on Course model (migration 0007)
- `load_course_descriptions()` method in data loader — reads `course_descriptions.json`, populates all 4 description fields
- `data/course_descriptions.json` — 383 bilingual course descriptions extracted from `src/description.py`
- Course detail page now shows locale-appropriate headline and description (BM for `ms`, EN for `en`/`ta`)
- `courseDetail.*` i18n keys added to all 3 locale files (EN, BM, Tamil)
- 6 new tests: bilingual API fields, empty defaults, description loading, TVET overwrite protection

### Fixed
- TVET metadata loader no longer overwrites rich descriptions with thin CSV text (conditional update)

### Technical Notes
- CourseSerializer now exposes `headline_en`, `description_en`
- Frontend `Course` interface updated with new fields
- Supabase migration applied: `ALTER TABLE courses ADD COLUMN headline_en/description_en`
- Backend tests: 162 (was 156) | Golden master: 8280 (unchanged)

## [1.16.1] - 2026-02-21 — Description Sprint: Quality Audit + English Translations

### Added
- English translations (`headline_en`, `synopsis_en`) for all 383 course descriptions in `src/description.py` — enables bilingual course cards
- `headline` field added to all entries (previously only `synopsis` existed)
- English fallback defaults in `get_course_details()` function

### Fixed
- 33 description quality issues across all 6 institution types:
  - 25 "mereka" (third-person) pronoun fixes → "anda" (second-person, direct address)
  - 2 typos: "DANN" → "DAN", "turu padang" → "turun padang"
  - 2 thin descriptions expanded (IJTM-CET-035, IJTM-CET-037)
  - 3 headline fixes ("Suara Untuk Mereka" → "Suara Untuk Semua")
  - 1 "kita" → "anda" fix

### Technical Notes
- `src/description.py`: ~2,400 → ~3,090 lines
- All 383 entries verified via AST parsing — 100% bilingual coverage
- British English spelling throughout translations
- Backend tests: 156 (unchanged) | Golden master: 8280 (unchanged)

## [1.16.0] - 2026-02-20 — Sprint 15: Career Pathways (MASCO Integration)

### Added
- **MascoOccupation model**: New Django model with `masco_code` (PK), `job_title`, `emasco_url` — stores 272 MASCO-classified occupations from Malaysia's official eMASCO portal
- **Course ↔ Occupation M2M**: `Course.career_occupations` ManyToManyField links courses to career outcomes (531 unique links across all TVET and Polytechnic courses)
- **Career Pathways on course detail**: New "Career Pathways" section on `/course/[id]` page shows clickable indigo pill badges linking to eMASCO portal pages for each linked occupation
- **API: career_occupations in course detail**: `GET /api/v1/courses/<id>/` now returns `career_occupations` list with `masco_code`, `job_title`, and `emasco_url`
- **MASCO data loaders**: Two new methods in `load_csv_data.py` — `load_masco_occupations` (from `masco_details.csv`) and `load_course_masco_links` (from `course_masco_link.csv` with deduplication)
- **8 new tests**: 3 API tests (career occupations in detail, field validation, empty list) + 5 model tests (PK, M2M, reverse relation, idempotent update_or_create, __str__)
- Migration `0005_add_masco_occupations`

### Technical Notes
- Backend tests: 156 (+8) | Golden master: 8280 (unchanged)
- Data loaded into Supabase with RLS enabled (public read) on both `masco_occupations` and `courses_course_career_occupations` tables
- MASCO data sourced from existing project files (`data/masco_details.csv`, `data/course_masco_link.csv`) — originally used by legacy Streamlit app
- eMASCO portal pages contain starting salary, annual increment, demand status, and job descriptions

## [1.15.0] - 2026-02-20 — Sprint 14: TVET Data Fix + UX Polish

### Fixed
- **TVET orphaned courses**: All 84 TVET courses had zero institution links because `load_course_details` used `.filter().update()` on non-existent `CourseInstitution` records. Changed to `update_or_create` so TVET rows in `details.csv` create links when none exist.
- **Institution taxonomy**: 55 ILKBS/ILJTM institutions were incorrectly typed as `IPTA`. Changed to `ILKA` in `data/institutions.csv` and Supabase DB (157 IPTA + 55 ILKA).

### Added
- **181 TVET course-institution links** now loaded correctly — IKBN/IKTBN/IKSN courses linked to ILKBS institutions, ILP/ADTEC/JMTI courses linked to ILJTM institutions, with fees, allowances, and application hyperlinks.
- **Settings page redesign** (`settings/page.tsx`): Language selector, clear profile data button, about section — fully localised (EN/BM/TA).
- **Saved page i18n**: Localised with `useT()` hook across all 3 locales.
- **Settings and saved i18n keys**: Added `settings.*` and `saved.*` translation keys to all 3 locale files.

### Changed
- **Gemini SDK migration**: `google-generativeai` (deprecated) replaced with `google-genai` v1.x Client API pattern in `report_engine.py`. Updated mocks in `test_report_engine.py`.
- **`requirements.txt`**: `google-generativeai>=0.3,<1.0` → `google-genai>=1.0,<2.0`

### Technical Notes
- Backend tests: 148 (unchanged) | Golden master: 8280 (unchanged)
- Both `halatuju-api` and `halatuju-web` deployed to Cloud Run
- Data fix applied directly to Supabase DB (55 institution type updates + 181 link inserts)

## [1.14.0] - 2026-02-18 — Sprint 13: Localisation (EN/BM/TA)

### Added
- **i18n infrastructure** (`lib/i18n.tsx`): React context with `useT()` hook, localStorage-persisted locale preference, static JSON imports for zero-latency switching
- **Language selector** (`components/LanguageSelector.tsx`): Dropdown in landing page nav and dashboard header — switches between English, Bahasa Melayu, and Tamil
- **142 translation keys** per locale across 6 sections: common, landing, onboarding, dashboard, login, subjects
- **i18n validation script** (`scripts/check-i18n.js`): Checks JSON parsing, key completeness across all 3 locales, and no empty values

### Changed
- **6 core pages localised**: Landing, stream selection, grades input, profile input, dashboard, and login — all hardcoded strings replaced with `t('key')` calls
- **Landing page** converted from server component to client component to support `useT()` hook
- **Grades page**: Core subject labels now use translated `t('subjects.XX')` keys; stream/elective subjects retain official Malay names
- **Dashboard sub-components** (`InsightsPanel`, `FilterDropdown`, `RankedResults`, `LoadingScreen`) each call `useT()` for their own translated strings
- **Tamil translations** quality-reviewed per style guide: brand name kept as "HalaTuju", compound words joined, sandhi rules applied

### Technical Notes
- Backend tests: 148 (unchanged) | Golden master: 8280 (unchanged)
- Frontend-only sprint — no backend changes, no migrations
- New files: `lib/i18n.tsx`, `components/LanguageSelector.tsx`, `scripts/check-i18n.js`
- Modified: 3 JSON translation files + 6 page files + `providers.tsx`

## [1.13.0] - 2026-02-18 — Sprint 12: Report Frontend + PDF

### Added
- **Report display page** (`/report/[id]`): Renders AI counsellor report as formatted markdown with `react-markdown` and Tailwind Typography prose styling
- **PDF download**: "Download PDF" button using `window.print()` with `@media print` stylesheet (A4, clean layout, hidden nav)
- **Generate Report CTA** on dashboard: Auth-protected button calls `POST /api/v1/reports/generate/`, redirects to report page on success
- **Report API client functions** in `api.ts`: `generateReport()`, `getReport()`, `getReports()` with TypeScript types
- 4 new view tests: report list (own reports only), report detail, cross-user 404 regression, validation

### Fixed
- **FK bug in report views**: `ReportDetailView` and `ReportListView` filtered by `student_id=request.user_id` (comparing integer PK with UUID string — would never match). Fixed to `student__supabase_user_id=request.user_id`

### Dependencies
- Added `react-markdown@10.1.0` for markdown rendering
- Added `@tailwindcss/typography` for prose styling

## [1.12.0] - 2026-02-18 — Sprint 11: AI Report Backend

### Added
- **Report engine** (`apps/reports/report_engine.py`): Gemini-powered narrative counselor report generator with model cascade fallback (gemini-2.5-flash → gemini-2.5-flash-lite → gemini-2.0-flash)
- **Report prompts** (`apps/reports/prompts.py`): BM and EN counselor report templates ported from legacy Streamlit, with counselor personas (Cikgu Venu, Cikgu Gopal, Cikgu Guna)
- **Report API endpoints**: `POST /api/v1/reports/generate/` (generate report), `GET /api/v1/reports/` (list), `GET /api/v1/reports/<id>/` (detail) — all auth-protected
- 12 new tests: format helpers (grades, signals, courses, insights), prompt templates (BM/EN), persona mapping, Gemini mock (success, cascade fallback, missing API key)

### Changed
- Report views wired up (previously stubs returning "coming soon")
- Reports URL config updated with list endpoint

## [1.11.0] - 2026-02-18 — Sprint 10: Deterministic Insights

### Added
- **Insights engine** (`insights_engine.py`): Pure function that generates structured summaries from eligibility results — stream breakdown, top fields, level distribution, merit summary, and Malay summary text
- **Insights in eligibility response**: `POST /api/v1/eligibility/check/` now returns an `insights` key alongside `eligible_courses` and `stats`
- **InsightsPanel component** on dashboard: Three-column layout showing top fields (Bidang Teratas), level distribution (Tahap Pengajian), and merit bar chart (Peluang Kemasukan)
- 8 new tests: empty input, stream breakdown, labels, top fields ranking, merit counts, level distribution, summary text
- **KKOM separation**: Kolej Komuniti requirements split into dedicated `kkom_requirements.csv` with `source_type: 'kkom'`

### Changed
- Eligibility API response now includes `insights` object for frontend consumption
- Dashboard displays insights panel between stats cards and quiz CTA
- API types updated with `Insights`, `InsightsStreamItem`, `InsightsFieldItem`, `InsightsLevelItem` interfaces

## [1.10.0] - 2026-02-18 — Sprint 9: Data Gap Filling

### Added
- **TVET course metadata**: 84 TVET courses enriched with names, levels, departments, descriptions, semesters, and WBL flags from `tvet_courses.csv`
- **PISMP course metadata**: 73 PISMP courses enriched with level (Ijazah Sarjana Muda Pendidikan), department, field, semesters (8), and auto-generated Malay descriptions
- **Institution modifiers in DB**: Added `modifiers` JSONField to Institution model — ranking modifiers (urban, cultural_safety_net, etc.) now stored in PostgreSQL instead of loaded from filesystem JSON
- **`audit_data` management command**: Reports data completeness across courses, requirements, institutions, offerings, and tags
- 5 new tests: TVET enrichment, PISMP enrichment, institution modifiers storage

### Fixed
- **Institution modifiers not working on Cloud Run**: Modifiers were read from `data/institutions.json` at startup, but this file isn't in the Docker image. Now loaded from DB via `load_csv_data`.

### Technical Notes
- Migration 0004: adds `modifiers` JSONField (default={}) to Institution
- All 383 courses now have complete metadata (description, level, department, field, frontend_label, semesters)
- `load_csv_data` now runs 9 loaders in sequence: courses → requirements → tvet_metadata → pismp_metadata → institutions → modifiers → links → details → tags

## [1.9.0] - 2026-02-18 — Sprint 8: Course Detail Enhancement

### Added
- **Course offering details** in `/course/[id]` API response — tuition fees, hostel fees, registration fee, monthly/practical allowances, free hostel/meals flags, application hyperlink
- **"Apply" button** on institution cards linking to official application portals (407 courses with hyperlinks)
- **Fee display** on institution cards — tuition, hostel, and registration fees in a clean grid layout
- **Benefit badges** — "Free Hostel", "Free Meals", and "RM{amount}/month" allowance badges on institution cards
- **`load_course_details`** management command method — loads `details.csv` to enrich CourseInstitution rows (TVET: per-institution, Poly/Univ: per-course)
- 5 new backend tests: offering fees, hyperlink, allowances, free badges, empty field handling

### Technical Notes
- No schema migration needed — CourseInstitution model already had fee fields from initial setup
- `details.csv` (407 rows): TVET rows have institution_id (per-institution fees), Poly/Univ rows don't (shared fees across all institutions)
- Golden master unchanged at 8280 (no engine changes)

## [1.8.0] - 2026-02-18 — Sprint 7: PISMP Integration

### Added
- **73 PISMP (teacher training) courses** integrated into eligibility engine — new `source_type: 'pismp'`
- **PISMP data file** (`data/pismp_requirements.csv`) — cleaned and formatted from draft
- **"Teacher Training" filter** in dashboard dropdown and stat card
- **Amber badge styling** for PISMP courses (`bg-amber-100 text-amber-700`)
- 8 new backend tests: eligibility, exclusion, borderline, subject-specific, Malaysian-only, stats, merit labels, subject requirements
- Django migration `0003_add_pismp_source_type`

### Fixed
- **Empty subjects bug** in `check_subject_group_logic`: rules with `subjects: []` (meaning "any N subjects at grade X") were silently skipped. Now counts from all student grades. Critical for PISMP's "5 Cemerlang from any subjects" requirement.
- **NaN guard** in `check_subject_group_logic` and `check_complex_requirements`: non-string input (NaN from DataFrame concat) no longer crashes the engine

### Technical Notes
- Golden master unchanged at 8280 (PISMP data is additive, no existing courses affected)
- PISMP courses have no `merit_cutoff` — merit labels are `null` (same as TVET)
- `age_limit` field in PISMP data not implemented (not in student profile) — documented as future enhancement

## [1.7.0] - 2026-02-17 — Sprint 6: Dashboard Redesign (Card Grid)

### Added
- **Merit traffic lights** on course cards: Green (High Chance), amber (Fair Chance), red (Low Chance) indicators based on student merit vs course cutoff
- **Student merit calculation** in eligibility endpoint: Computes merit score from SPM grades using UPU-style formula, returns `merit_label`, `merit_color`, `student_merit` per course
- **CourseCard component** (`components/CourseCard.tsx`): Extracted reusable vertical card with field image header, merit indicator, rank badge, and fit reason tags
- 2 new backend tests for merit labels in eligibility response

### Changed
- **Dashboard layout**: Responsive card grid (3 col desktop, 2 tablet, 1 mobile) replaces single-column list
- **Card design**: Vertical layout with field image on top instead of horizontal flex
- Low merit courses (`merit_label === 'Low'`) rendered with reduced opacity
- TVET courses show no merit indicator (no cutoff data)
- Dashboard reduced from ~764 to ~370 lines by extracting CourseCard and FilterDropdown

### Fixed
- **Ranking merit penalty** now works correctly: `student_merit` included in eligibility response flows through to ranking API (previously defaulted to 0)
- Grade key mismatch: `prepare_merit_inputs` expects `'history'`, serializer produces `'hist'` — adapted in eligibility view

### Technical Notes
- Backend tests: 106 (+2) | Golden master: 8280 (unchanged)
- New files: `src/components/CourseCard.tsx` | Modified: `views.py`, `test_api.py`, `api.ts`, `dashboard/page.tsx`
- CoQ (co-curricular quality) score defaults to 5.0 — future enhancement to ask user

## [1.6.0] - 2026-02-17 — Sprint 5: Quiz Frontend

### Added
- **Quiz page** (`/quiz`): Interactive 6-question quiz with step-by-step navigation, progress bar, and auto-advance on selection
- **Quiz API integration** (`lib/api.ts`): `getQuizQuestions()`, `submitQuiz()`, `getRankedResults()` functions with TypeScript types
- **Take Quiz CTA** on dashboard: Prominent gradient banner inviting users to personalise their rankings
- **Ranked results view** on dashboard: Top 5 matches with rank badges and fit reason tags, plus "Other Eligible Courses" section
- **Quiz state management**: Signals stored in localStorage; retake quiz option clears and resets
- **Quiz completed banner**: Green confirmation with retake link when quiz has been completed

### Changed
- Dashboard dynamically switches between flat eligibility list (no quiz) and ranked results (after quiz)
- Dashboard subtitle updates based on whether quiz has been taken

### Technical Notes
- Frontend-only sprint — no backend changes, no migrations
- Backend tests: 104 (unchanged) | Golden master: 8280 (unchanged)
- New files: `src/app/quiz/page.tsx` | Modified: `src/lib/api.ts`, `src/app/dashboard/page.tsx`
- Quiz signals persisted in `halatuju_quiz_signals` localStorage key
- Ranking query uses React Query with eligibility + signals as combined query key

## [1.5.0] - 2026-02-17 — Sprint 4: Ranking Engine Backend

### Added
- **Ranking engine** (`apps/courses/ranking_engine.py`): Ported 551-line Streamlit ranking engine to Django — pure functions, no globals, no file I/O
- **Ranking endpoint** (`POST /api/v1/ranking/`): Accepts eligible courses + student signals, returns top 5 + rest with fit scores and natural language reasons
- **RankingRequestSerializer**: Validates eligible_courses (each must have course_id) and student_signals
- **Institution data loading**: AppConfig now loads course tags map, institution subcategories, and institution modifiers (from JSON) at startup
- **Ranking tests** (`test_ranking.py`): 34 new tests covering score calculation, category/institution/global cap enforcement, merit penalty (High/Fair/Low), sort tie-breaking (5 levels), credential priority, top_5/rest split, API endpoint validation

### Technical Notes
- Test count: 70 → 104 (+34 ranking tests)
- Golden master: 8280 (unchanged)
- No migrations, no deploy (backend only)
- Ranking engine uses dependency injection — course tags and institution data passed as parameters, not loaded from files
- Institution modifiers (urban, cultural_safety_net) loaded from `data/institutions.json` at startup; future sprint will migrate to model fields

## [1.4.0] - 2026-02-16 — Sprint 3: Quiz API Backend

### Added
- **Quiz data module** (`apps/courses/quiz_data.py`): 6 psychometric questions in 3 languages (EN, BM, TA), ported from `src/quiz_data.py`
- **Quiz engine** (`apps/courses/quiz_engine.py`): Stateless signal accumulator — takes answers in, returns categorised signals in 5-bucket taxonomy
- **Quiz questions endpoint** (`GET /api/v1/quiz/questions/?lang=en`): Returns quiz questions in requested language, public (no auth)
- **Quiz submit endpoint** (`POST /api/v1/quiz/submit/`): Accepts 6 answers, returns `student_signals` + `signal_strength`, public (no auth)
- **Quiz tests** (`test_quiz.py`): 14 new tests covering endpoint behaviour, signal accumulation, taxonomy mapping, validation, and language parity

### Technical Notes
- Test count: 56 → 70 (+14 quiz tests)
- Golden master: 8280 (unchanged)
- No migrations, no deploy (backend only)
- `ProfileView.put()` already accepts `student_signals` — no change needed
- Quiz engine is fully stateless: no session, no DB writes. Frontend sends all 6 answers in one POST.

## [1.3.0] - 2026-02-16 — Sprint 2: Saved Courses Fix + Page Shells

### Added
- **Saved courses page** (`/saved`): Lists saved courses from API, remove button, login prompt for guests
- **Settings page** (`/settings`): Links to edit grades, saved courses, about, privacy, terms
- **About page** (`/about`): Project description and mission
- **Privacy policy page** (`/privacy`): Data collection, usage, and storage disclosure
- **Terms of service page** (`/terms`): Disclaimer and liability
- **Auth callback page** (`/auth/callback`): Handles OAuth redirect from Supabase, redirects to dashboard
- **Saved course CRUD tests**: 3 new tests covering save (201), list (appears), and delete (removed) (`test_saved_courses.py`)
- **Bookmark button on dashboard**: Logged-in users see a save/unsave bookmark icon on each course card with optimistic updates

### Fixed
- **`unsaveCourse` API call**: Changed from body-based DELETE (`/api/v1/saved-courses/` + body) to URL-based DELETE (`/api/v1/saved-courses/<course_id>/`) matching the backend route
- **`getSavedCourses` return type**: Updated from `string[]` to `Course[]` to match actual backend response

### Changed
- **Dashboard CourseCard**: Refactored from single `<Link>` wrapper to `<div>` with separate link area and save button, so save/click targets are independent
- **Dashboard saved state**: Now fetches from Supabase API when session exists (was not wired at all)

### Technical Notes
- Test count: 53 → 56 (+3 saved course CRUD tests)
- Golden master: 8280 (unchanged)
- TypeScript: 0 errors
- Frontend deployed: revision `halatuju-web-00007-wd8`

## [1.2.0] - 2026-02-16 — Sprint 1: Git Housekeeping + Auth Enforcement

### Added
- **Sprint roadmap**: 15-sprint migration plan across 4 phases (`docs/roadmap/sprint-roadmap-v1.x.md`)
- **DRF permission class**: `SupabaseIsAuthenticated` for class-based views (`halatuju/middleware/supabase_auth.py`)
- **Auth enforcement**: `SavedCoursesView`, `SavedCourseDetailView`, `ProfileView` now require valid Supabase JWT
- **Auth tests**: 11 new tests covering protected endpoint rejection (403), authenticated access (200), and public endpoint openness (`test_auth.py`)
- **Git tracking**: All project code (`halatuju_api/`, `halatuju-web/`, `tools/`) now under version control
- **`.gitignore`**: Covers Node.js (`node_modules/`, `.next/`), Django (`*.sqlite3`, `staticfiles/`), and temp files (`.tmp/`)

### Changed
- **Protected views**: Replaced manual `if not request.user_id` checks with `permission_classes = [SupabaseIsAuthenticated]`
- **Migration 0002**: Renames `student_profiles` table to `api_student_profiles` (matching model's `db_table`), adds missing fields (`credit_math_or_addmath`, `credit_sci`, `credit_science_group`, `pass_sci`)

### Fixed
- **Table mismatch**: `StudentProfile.Meta.db_table = 'api_student_profiles'` didn't match migration 0001's `student_profiles` — generated migration 0002 to correct this

### Technical Notes
- DRF returns 403 (not 401) for unauthenticated requests when no `WWW-Authenticate` header is configured — this is expected behaviour
- Test count: 42 → 53 (+11 auth tests)
- Golden master: 8280 (unchanged)

## [1.1.0] - 2026-02-04

### 🎓 Major Feature: University Course Integration

Added comprehensive support for 87 Malaysian public university (IPTA) Asasi and Foundation programs across 20 institutions.

### ✨ New Features

#### Data Layer
-   **New Data Files**:
    -   `data/university_requirements.csv` - 87 university course eligibility rules
    -   `data/university_courses.csv` - Course metadata (department, field, frontend_label)
    -   `data/university_institutions.csv` - 20 IPTA universities with constituency data
-   **Course Catalog Expansion**: 727 → 814 courses (+12% growth)

#### Eligibility Engine (`src/engine.py`)
-   **Grade B Requirements**: New tier stricter than Credit C (Grade B or better)
    -   `credit_bm_b`, `credit_eng_b`, `credit_math_b`, `credit_addmath_b`
-   **Distinction Requirements**: Grade A- or better
    -   `distinction_bm`, `distinction_eng`, `distinction_math`, `distinction_addmath`
    -   `distinction_bio`, `distinction_phy`, `distinction_chem`, `distinction_sci`
-   **Complex OR-Group Logic**: JSON-based multi-subject requirements
    -   Example: "Need 2 subjects with Grade B from [Physics, Chemistry, Biology]"
    -   Supports AND logic between groups, OR logic within groups
-   **Pendidikan Islam/Moral Support**: `pass_islam`, `credit_islam`, `pass_moral`, `credit_moral`
-   **Additional Science Requirements**: `pass_sci`, `credit_sci`, `credit_addmath`

#### UI Updates (`main.py`, `src/dashboard.py`, `src/translations.py`)
-   **Institution Filter**: Added "Public University" (Universiti Awam) option
-   **Dashboard Metrics**: Expanded from 4 to 5 columns to include UA course count
-   **Translations**: Added `inst_ua` key in English/Bahasa Melayu/Tamil
-   **Grade Input**: Added "Pendidikan Islam" and "Pendidikan Moral" to Other Subjects dropdown

#### Data Manager (`src/data_manager.py`)
-   **University Data Merging**:
    -   Extracts course name and institution from `notes` column
    -   Merges with institution metadata for state/URL
    -   Maps to consistent type naming: "Universiti Awam"
-   **Type Standardization**: All institution types now use Bahasa Melayu for filter compatibility

### 🧪 Testing

-   **Golden Master Test Expansion** (`tests/test_golden_master.py`):
    -   Added 8 new student profiles (43-50) for UA requirement testing
    -   Grade B testing, Distinction testing, Complex OR-group testing
    -   Updated baseline: 5,318 → 8,280 eligible matches (+2,962)
    -   Test coverage: 50 students × 407 courses = 20,350 checks
-   **University Integration Tests** (`test_university_integration.py`):
    -   Data loading verification
    -   Eligibility engine testing with strong/weak students
    -   Complex requirements JSON parsing

### 🐛 Bug Fixes

-   **NaN Handling**: Fixed AttributeError in `check_complex_requirements()` when pandas passes NaN as float type
-   **Type Consistency**: Changed UA type from 'UA' to 'Universiti Awam' for UI compatibility
-   **Windows Console**: Removed Unicode emojis from test output for cp1252 encoding compatibility

### 📝 Documentation

-   **README.md**: Updated course catalog numbers and feature descriptions
-   **DATA_DICTIONARY.md**: Documented all 20+ new UA requirement columns and complex_requirements JSON format
-   **docs/university_integration_complete.md**: Comprehensive implementation summary

### ⚙️ Technical

-   **Engine Functions**:
    -   `is_credit_b(grade)` - Checks if grade is B or better
    -   `is_distinction(grade)` - Checks if grade is A- or better
    -   `check_complex_requirements(grades, json_str)` - Evaluates OR-group logic
    -   `map_subject_code(code)` - Maps 60+ SPM subjects to internal keys
-   **Performance**: No noticeable impact despite 12% course increase (~140KB additional data)

### 🔄 Backward Compatibility

-   All changes fully backward compatible with existing Poly/KK/TVET courses
-   New requirement columns default to 0 (not required)
-   Existing eligibility logic unchanged

## [1.0.0] - 2026-01-24

### 🚀 Initial Release
First official stable release of **HalaTuju**, the SPM Leaver Course Recommender.

### ✨ Key Features
-   **Eligibility Engine**: 
    -   Exact matching against General and Specific requirements for Polytechnics, Community Colleges, ILKBS, and ILJTM.
    -   Support for gender-specific, physically demanding, and interview-based course rules.
-   **Ranking System**: 
    -   Weighted scoring based on Student Interest (RIASEC), Work Preferences (Hands-on vs Theory), and Learning Styles.
    -   Tie-breaking logic using Credential Priority (Diploma > Certificate) and Institution Tier functionality.
-   **Dashboard**:
    -   Interactive filtering and "Tiered" display (Top 5 Matches vs Rest).
    -   Visual indicators for specific requirements (Medical checks, Interviews).
-   **Reports**:
    -   AI-generated personalized career pathway reports (Gemini Pro + OpenAI Fallback).
    -   PDF export functionality.
-   **Localization**: Full English, Malay, and Tamil language support.

### 🐛 Key Fixes & Stability
-   **Gender Logic**: Fixed regression where engine hardcoded Malay gender terms, causing rejection of eligible students using English/Tamil UI.
-   **Data Integerity**: Implemented a "Golden Master" regression test suite (`tests/test_golden_master.py`) achieving 100% integrity on 13,000+ test cases.
-   **Cleanup**: Removed unused dependency `match_jobs_rag` and unused `InsightGenerator`, consolidated imports, and verified no hardcoded secrets exist.

### ⚙️ Technical
-   **Stack**: Streamlit, Pandas, Supabase (Auth/DB), Google Gemini.
-   **Testing**: Automated Golden Master testing for the engine.
