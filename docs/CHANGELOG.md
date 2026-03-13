# Changelog — HalaTuju

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
