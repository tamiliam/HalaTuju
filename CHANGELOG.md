# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
