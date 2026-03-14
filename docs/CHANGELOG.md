# Changelog — HalaTuju

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
