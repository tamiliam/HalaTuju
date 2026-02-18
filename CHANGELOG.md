# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
