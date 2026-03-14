# HalaTuju Architecture Map

Last updated: 2026-03-14 (comprehensive audit prep)

## Root

```
HalaTuju/
├── halatuju_api/          # Django REST backend
├── halatuju-web/          # Next.js 14 frontend
├── docs/                  # Documentation, retrospectives, plans
├── _archive/streamlit/    # Legacy Streamlit app (preserved, not active)
├── .claude/               # Architecture map
├── CHANGELOG.md           # Full version history
├── README.md              # Project overview
├── .env                   # Root env vars (not committed)
└── .gitignore
```

---

## Backend — halatuju_api/

### Project Config

```
halatuju_api/halatuju/
├── settings/
│   ├── base.py                    # Shared: INSTALLED_APPS, middleware, DB, REST_FRAMEWORK
│   ├── development.py             # DEBUG=True, CORS allow all, SQLite or Supabase via DATABASE_URL
│   └── production.py              # Cloud Run: Supabase PostgreSQL, Sentry, security headers
├── middleware/
│   └── supabase_auth.py           # JWT auth (ES256 JWKS + HS256 legacy), sets request.user_id
├── urls.py                        # Root routing → /api/v1/ (courses) + /api/v1/reports/
└── wsgi.py                        # WSGI entry (gunicorn)
```

### App: courses (core eligibility engine)

```
apps/courses/
├── models.py                      # 11 models (see model registry below)
├── admin.py                       # Admin registration (Course, Institution, StudentProfile, etc.)
├── apps.py                        # Startup: loads Course + CourseRequirement → Pandas DataFrame cache
├── views.py                       # 19 API endpoint classes (see endpoint registry below)
├── serializers.py                 # Grade key mapping (BM→bm, BI→eng, etc.), request/response serializers
├── urls.py                        # 18 URL patterns → /api/v1/
│
├── engine.py                      # SACRED — SPM eligibility checker (743 lines, golden master: 8283)
├── stpm_engine.py                 # SACRED — STPM eligibility checker (255 lines, golden master: 1811)
├── ranking_engine.py              # Fit scores, category/institution caps, credential priority (809 lines)
├── stpm_ranking.py                # STPM fit scores: CGPA margin, field match, interview penalty (127 lines)
├── pathways.py                    # Matric track + STPM bidang eligibility formulas (315 lines)
├── quiz_engine.py                 # Stateless quiz signal accumulator, 6 questions (176 lines)
├── quiz_data.py                   # Quiz questions in 3 languages: BM/EN/TA (331 lines)
├── insights_engine.py             # Deterministic insights from eligibility results (121 lines)
│
├── management/commands/
│   ├── load_csv_data.py           # CSV → DB migration (11 loaders, one-time)
│   ├── load_stpm_data.py          # STPM CSV → DB (science 1,003 + arts 677 rows)
│   ├── enrich_stpm_metadata.py    # Gemini API → STPM field/category/description enrichment
│   ├── fix_stpm_names.py          # Proper-case normalisation in Supabase
│   ├── audit_data.py              # Data completeness report
│   └── backfill_masco.py          # MASCO occupation mappings → Course M2M
│
├── data/stpm/
│   ├── stpm_science_requirements_parsed.csv
│   ├── stpm_arts_requirements_parsed.csv
│   ├── stpm_science_merit.csv
│   └── stpm_arts_merit.csv
│
├── migrations/                    # 18 migrations (0001–0018)
│   ├── 0001_initial                     # Course, StudentProfile, CourseTag, Institution, CourseRequirement, CourseInstitution
│   ├── 0002–0007                        # SPM refinements (credit fields, PISMP, institution modifiers, MASCO, bilingual, headline)
│   ├── 0008_add_name_school             # StudentProfile.name_school
│   ├── 0009_add_admission_outcome       # AdmissionOutcome model
│   ├── 0010_expand_student_profile      # NRIC, address, phone, income, siblings
│   ├── 0011_add_interest_status         # SavedCourse.interest_status
│   ├── 0012_stpmcourse_stpmrequirement  # STPM models
│   ├── 0013_studentprofile_exam_type    # exam_type, muet_band, STPM profile fields
│   ├── 0014_stpmcourse_merit_score      # StpmCourse.merit_score
│   ├── 0015_stpm_metadata_columns       # STPM field/category/description enrichment
│   ├── 0016_merit_type_preu_sources     # Course.merit_type branching + matric/stpm source_types
│   ├── 0017_insert_preu_courses         # 6 pre-U courses as Course rows
│   └── 0018_insert_preu_institutions    # Pre-U institution records
│
└── tests/                         # 20 test files, ~336 tests (320 collected in last run)
    ├── test_golden_master.py      # 1 — 50 students × all courses = 8283 baseline
    ├── test_stpm_golden_master.py # 1 — 5 students × all STPM = 1811 baseline
    ├── test_api.py                # 64 — eligibility, ranking, course detail, search, STPM integration
    ├── test_ranking.py            # 62 — fit scores, caps, pre-U scoring, tie-breaking
    ├── test_pathways.py           # 32 — matric tracks, STPM bidangs, grade helpers
    ├── test_serializers.py        # 27 — grade mapping, normalisation, validation
    ├── test_quiz.py               # 24 — quiz endpoints + engine, multi-select, weights
    ├── test_profile_fields.py     # 19 — expanded profile, saved course, STPM fields
    ├── test_stpm_data_loading.py  # 18 — STPM CSV loader, 1,113 programmes
    ├── test_stpm_engine.py        # 16 — CGPA calculator, grade comparison, eligibility
    ├── test_auth.py               # 15 — JWT enforcement (9 pre-existing failures)
    ├── test_stpm_search.py        # 12 — STPM search filters, pagination, detail
    ├── test_data_loading.py       # 12 — CSV loaders, idempotency, JSON round-trip
    ├── test_report_engine.py      # 12 — report generation + Gemini mock
    ├── test_outcomes.py           # 10 — admission outcome CRUD, auth enforcement
    ├── test_stpm_ranking.py       # 10 — STPM fit scores, CGPA margins
    ├── test_stpm_api.py           # 9 — STPM eligibility + ranking endpoints
    ├── test_preu_courses.py       # 9 — pre-U (matric + STPM) eligibility
    ├── test_insights.py           # 8 — insights generation
    ├── test_stpm_models.py        # 7 — StpmCourse/StpmRequirement CRUD
    ├── test_saved_courses.py      # 3 — save/list/delete
    └── test_views.py              # 4 — report views
```

#### Model Registry

| Model | Table | Purpose | Key Fields |
|-------|-------|---------|------------|
| `Course` | `courses` | Master course catalogue (389 rows: 383 SPM + 6 pre-U) | name, level, field, source_type, merit_type, headline, description |
| `CourseRequirement` | `course_requirements` | Eligibility rules per course | 70+ boolean fields mapping SPM subject requirements |
| `Institution` | `institutions` | Training providers (239 rows) | name, state, district, category, indian_population |
| `CourseInstitution` | `course_institutions` | Course ↔ Institution junction | fees, duration, intake_month, hyperlink |
| `CourseTag` | `course_tags` | Personality profile per course | work_modality, cognitive_type, people_interaction, learning_style, environment |
| `StudentProfile` | `student_profiles` | User eligibility data | SPM grades, gender, nationality, exam_type, muet_band, STPM fields, income, siblings |
| `SavedCourse` | `saved_courses` | User bookmarks | course, student, interest_status |
| `AdmissionOutcome` | `admission_outcomes` | Track application results | course, student, status (applied/offered/accepted/rejected/withdrawn) |
| `MascoOccupation` | `masco_occupations` | Career occupation codes (274 entries) | code, title_en, title_bm |
| `StpmCourse` | `stpm_courses` | STPM degree programmes (1,113 rows) | name, university, stream, merit_score, field, category |
| `StpmRequirement` | `stpm_requirements` | STPM eligibility rules | min_cgpa, min_muet_band, stpm_min_subjects, stpm_min_grade, subject requirements |

#### API Endpoint Registry

| Endpoint | Method | View Class | Purpose |
|----------|--------|------------|---------|
| `/api/v1/eligibility/check/` | POST | EligibilityCheckView | Run SPM eligibility engine |
| `/api/v1/ranking/` | POST | RankingView | Calculate fit scores + rank eligible courses |
| `/api/v1/courses/` | GET | CourseListView | List all courses (paginated) |
| `/api/v1/courses/<id>/` | GET | CourseDetailView | Single course with tags, occupations, offerings |
| `/api/v1/courses/search/` | GET | CourseSearchView | Search with filters (text, level, field, source_type, state) |
| `/api/v1/institutions/` | GET | InstitutionListView | List all institutions |
| `/api/v1/institutions/<id>/` | GET | InstitutionDetailView | Single institution detail |
| `/api/v1/quiz/questions/` | GET | QuizQuestionsView | 6 quiz questions (BM/EN/TA) |
| `/api/v1/quiz/submit/` | POST | QuizSubmitView | Process answers → student signals |
| `/api/v1/profile/` | GET/PUT | ProfileView | Student profile CRUD |
| `/api/v1/profile/sync/` | POST | ProfileSyncView | Sync profile from Supabase Auth |
| `/api/v1/saved-courses/` | GET/POST/DEL | SavedCoursesView | Bookmark management |
| `/api/v1/saved-courses/<id>/` | GET/PUT/DEL | SavedCourseDetailView | Update interest status |
| `/api/v1/outcomes/` | GET/POST | OutcomeListView | Admission outcome tracking |
| `/api/v1/outcomes/<id>/` | PUT/DEL | OutcomeDetailView | Update/delete outcome |
| `/api/v1/stpm/eligibility/check/` | POST | StpmEligibilityCheckView | STPM eligibility check |
| `/api/v1/stpm/ranking/` | POST | StpmRankingView | STPM fit scores + ranking |
| `/api/v1/stpm/search/` | GET | StpmSearchView | STPM programme search (university, stream, text) |
| `/api/v1/stpm/<id>/` | GET | StpmProgrammeDetailView | STPM programme detail |

### App: reports (AI narrative generation)

```
apps/reports/
├── models.py                      # GeneratedReport (student, content_en, content_ms, language, model metadata)
├── report_engine.py               # Gemini-powered narrative generator (150 lines)
├── prompts.py                     # BM/EN counselor prompt templates (system + user)
├── views.py                       # GenerateReportView, ReportDetailView, ReportListView
├── admin.py                       # GeneratedReportAdmin
├── urls.py                        # 3 routes (list, generate, detail)
├── migrations/
│   └── 0001_initial.py            # GeneratedReport model
└── tests/
    ├── test_report_engine.py      # 12 — format helpers, prompt selection, Gemini mock
    └── test_views.py              # 4 — report list/detail, cross-user 404, auth
```

### Backend Root Files

```
halatuju_api/
├── CLAUDE.md                      # Backend architecture + deploy guide
├── DEPLOY.md                      # Cloud Run deployment steps
├── Dockerfile                     # Python 3.11-slim, gunicorn, collectstatic
├── requirements.txt               # Django 5, DRF, psycopg2, pandas, numpy, PyJWT, google-genai, sentry-sdk
├── pytest.ini                     # DJANGO_SETTINGS_MODULE=halatuju.settings.development
├── .env.example                   # DATABASE_URL, SECRET_KEY, SUPABASE_JWT_SECRET, GEMINI_API_KEY
├── .gcloudignore                  # Cloud Build ignores
├── manage.py                      # Django CLI
├── db.sqlite3                     # Local dev database (not committed)
└── scripts/
    ├── generate_sql_inserts.py    # Legacy SQL generation helper
    ├── migrate_to_supabase.py     # Batched CSV → Supabase migration
    └── supabase_data_migration.sql
```

---

## Frontend — halatuju-web/

### Pages (Next.js App Router)

```
src/app/
├── layout.tsx                     # Root layout (Lexend font, Providers wrapper)
├── providers.tsx                  # Client providers: QueryClient, I18n, Auth, AuthGateModal
├── page.tsx                       # Landing page (hero, features, stats, CTAs)
│
├── login/page.tsx                 # Phone OTP + Google sign-in
├── auth/callback/page.tsx         # Google OAuth callback handler
│
├── onboarding/
│   ├── exam-type/page.tsx         # Select SPM or STPM qualification
│   ├── grades/page.tsx            # Enter SPM grades + co-curricular score
│   ├── stpm-grades/page.tsx       # STPM: stream selector, PA + 4 subjects, MUET, SPM prereqs
│   └── profile/page.tsx           # Demographics (gender, nationality, state, etc.)
│
├── dashboard/page.tsx             # Main dashboard — course cards, merit lights, exam_type branching
├── quiz/page.tsx                  # 6-question career interest quiz
├── search/page.tsx                # Course search + filters (field, level, pathway, state)
├── course/[id]/page.tsx           # SPM course detail (requirements, institutions, save/apply)
│
├── stpm/
│   ├── [id]/page.tsx              # STPM programme detail (stream badge, subjects, requirements)
│   └── search/page.tsx            # Redirects to /search?qualification=STPM
│
├── pathway/
│   ├── matric/page.tsx            # Matriculation eligibility by track + college listings
│   └── stpm/page.tsx              # STPM (Form 6) pathway detail
│
├── saved/page.tsx                 # Saved courses list
├── profile/page.tsx               # Student profile view/edit
├── settings/page.tsx              # Account settings
├── outcomes/page.tsx              # Admission outcomes tracker
├── report/[id]/page.tsx           # AI counselor report (markdown rendering)
│
├── about/page.tsx                 # About HalaTuju
├── contact/page.tsx               # Contact/feedback form
├── privacy/page.tsx               # Privacy policy
├── terms/page.tsx                 # Terms of service
└── cookies/page.tsx               # Cookie policy
```

**27 page files total. No error.tsx, loading.tsx, or not-found.tsx (using Next.js defaults).**

### Components

```
src/components/
├── AppHeader.tsx                  # Top nav: logo, links, profile dropdown, language selector, sign out
├── AppFooter.tsx                  # Footer: logo, tagline, quick links, legal, social
├── AuthGateModal.tsx              # Modal on auth-required actions (quiz, save, report)
├── CourseCard.tsx                 # Course card: name, institution, merit indicator (green/amber/red), field image
├── FilterPill.tsx                 # Dropdown filter for search page
├── LanguageSelector.tsx           # EN/BM/TA language switcher dropdown
├── PathwayCards.tsx               # Pathway filter buttons (Asasi, PISMP, Polytechnic, etc.)
├── PathwayTrackCard.tsx           # Track card for matric/STPM (images, stats)
├── ProgressStepper.tsx            # Onboarding step indicator (Step X of Y)
└── RequirementsCard.tsx           # Course requirements display (general, special, OR groups)
```

**10 components.**

### Libraries

```
src/lib/
├── api.ts                         # HTTP client for Django backend (all endpoint wrappers)
├── supabase.ts                    # Supabase client init (auth, Google OAuth, OTP)
├── auth-context.tsx               # Auth React Context (session, token, profile hydration, localStorage)
├── i18n.tsx                       # Custom i18n context: t() function, locale switcher, localStorage
├── subjects.ts                    # Subject code → name mapping (60+ SPM + STPM codes)
├── stpm.ts                        # STPM CGPA calculator (4.0 scale, mirrors backend)
├── pathways.ts                    # Matric/STPM eligibility (frontend-only, no backend calls)
└── merit.ts                       # UPU merit formula: (core/72×40)+(stream/36×30)+(elective/36×10)×9/8+CoQ
```

**8 lib files. Note: pathways.ts and merit.ts run eligibility on the client side.**

### Static Data

```
src/data/
├── matric-colleges.ts             # 15 matriculation colleges (state, tracks, phone, website)
├── stpm-schools.json              # 6,639-line JSON: STPM schools with code, state, PPD, streams, subjects
└── stpm-schools.ts                # TypeScript interface wrapper for stpm-schools.json
```

### i18n Translations

```
src/messages/
├── en.json                        # English (459 keys)
├── ms.json                        # Bahasa Melayu (459 keys)
└── ta.json                        # Tamil (459 keys)
```

Validated by `scripts/check-i18n.js` (ensures identical key structure across all 3 files).

### Frontend Root Files

```
halatuju-web/
├── Dockerfile                     # Multi-stage Node 18 Alpine build (standalone output)
├── next.config.js                 # React strict mode, standalone output, NEXT_PUBLIC_API_URL
├── tailwind.config.ts             # Brand colours (primary: #137fec), Lexend font, 8px radius
├── tsconfig.json                  # Strict mode, path alias @/* → ./src/*
├── postcss.config.js              # Tailwind + Autoprefixer
├── package.json                   # Next.js 14.2, React 18.2, Supabase 2.39, React Query 5.17, react-markdown 10.1
├── .env.example                   # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
├── .env.local                     # Local dev env
├── .env.production                # Production public keys + API URL
├── .gcloudignore                  # Cloud Run deploy ignores
├── scripts/
│   └── check-i18n.js             # Translation completeness checker
└── public/
    └── logo-icon.png              # HalaTuju logo
```

**No frontend tests exist.**

---

## Documentation — docs/

```
docs/
├── README.md                      # Docs index with status badges, management rules
├── roadmap.md                     # Master roadmap (STPM ✓, WhatsApp OTP active, admin dashboard future)
├── decisions.md                   # Architectural decisions log
├── lessons.md                     # Cross-cutting engineering lessons
├── release-notes-v1.33.0.md      # Latest stable release notes
├── Course Detail Page.pdf         # UI design spec
├── incident-001-rls-disabled.md   # RLS incident report + remediation templates
│
├── retrospective-*.md             # 30+ retrospectives:
│   ├── retrospective-sprint{1-20}.md        # SPM flow sprints
│   ├── retrospective-stpm-sprint{1-8}.md    # STPM entrance sprints
│   ├── retrospective-v1.{25-33}.0.md        # Release retrospectives
│   ├── retrospective-post-s20-polish.md     # UI polish
│   ├── retrospective-preu-courses.md        # Pre-U integration
│   ├── retrospective-visual-quiz.md         # Quiz redesign
│   └── retrospective-ui-polish.md           # UI polish release
│
├── plans/                         # Active & completed plans
│   ├── 2026-03-09-whatsapp-otp-plan.md         # ACTIVE — Twilio WhatsApp OTP, ~RM12/month
│   └── 2026-03-12-stpm-entrance.md             # COMPLETED — 5 sprints, 22 tasks, all done
│
└── archive/                       # Historical documentation
    ├── 2026-02-completed/         # 9 files: consolidation, institution sync, merit integration, etc.
    ├── audits/                    # 10 files: data audits, subject analysis, integration plans
    ├── ranking_logic.md           # Live reference — v1.5 ranking algorithm
    ├── pismp_integration_plan.md  # Done
    ├── stpm_implementation_plan.md # Superseded by 2026-03-12 version
    ├── quiz-redesign-*.md         # 4 files: iteration history
    ├── sprint-roadmap-v1.x.md     # Old roadmap
    ├── ui_ux_improvement_plan.md  # Deferred
    └── DATA_FOLDER_POLICY.md      # Data management rules
```

---

## _archive/streamlit/ (Legacy)

Previous Streamlit prototype. **246 files, not actively developed.** Preserved for reference on data structures, original ranking logic, and historical decisions.

Key contents: `.streamlit/` config, `data/` (course descriptions, institutions JSON, subject mappings), `scripts/analysis/` (SPM analysis, overlap checks), `src/` (auth, dashboard, engine, quiz_manager, ranking_engine), `tests/`, `DATA_DICTIONARY.md`, `ROADMAP.md`.

---

## Database — Supabase

**Project**: `pbrrlyoyyiftckqvzvvo` (Singapore region)

| Table | Rows | Purpose |
|-------|------|---------|
| `courses` | 389 | Master catalogue (383 SPM + 6 pre-U) |
| `course_requirements` | 389 | Eligibility rules (70+ boolean fields per course) |
| `institutions` | 239 | Training providers (212 original + 27 IPG) |
| `course_institutions` | ~800 | Course ↔ Institution offerings (fees, duration, intake) |
| `course_tags` | ~389 | Personality profiles per course |
| `student_profiles` | dynamic | User eligibility data (grades, demographics, STPM fields) |
| `saved_courses` | dynamic | User bookmarks with interest_status |
| `admission_outcomes` | dynamic | Application result tracking |
| `masco_occupations` | 274 | Career occupation codes |
| `course_masco_link` | ~500 | Course ↔ Occupation M2M |
| `reports` | dynamic | AI-generated counselor reports |
| `stpm_courses` | 1,113 | STPM degree programmes (162 bumiputera-only excluded at runtime) |
| `stpm_requirements` | 1,113 | STPM eligibility rules |

- RLS enabled on all tables, 0 security errors
- Course `#` suffix = "typically has interview" (data marker, not display)

---

## Deployment Architecture

```
┌──────────────────────────────────┐
│  halatuju-web (Cloud Run)        │
│  Next.js 14 — standalone Docker  │
│  Region: asia-southeast1         │
└──────────────┬───────────────────┘
               │ /api/v1/* (all API calls)
               ▼
┌──────────────────────────────────┐
│  halatuju-api (Cloud Run)        │
│  Django 5 — gunicorn Docker      │
│  Region: asia-southeast1         │
│                                  │
│  Startup: Course+Req → DataFrame │
│  Gemini API → report generation  │
└──────────────┬───────────────────┘
               │ ORM / psycopg2
               ▼
┌──────────────────────────────────┐
│  Supabase PostgreSQL             │
│  pbrrlyoyyiftckqvzvvo (Singapore)│
│  13 tables + RLS policies        │
└──────────────────────────────────┘
```

**GCP Project**: `gen-lang-client-0871147736` (account: `tamiliam@gmail.com`)

---

## Data Flow

### SPM Flow
```
Student enters SPM grades
  → Serializer maps keys (BM→bm, BI→eng, etc.)
  → engine.py checks DataFrame (grade classification, merit calc, subject matching)
  → merit_type branching (standard / matric / stpm_mata_gred)
  → PISMP deduplication
  → Sort by merit tier → credential → pathway → cutoff
  → ranking_engine.py adds fit scores from quiz signals
  → insights_engine.py generates summary
  → Response: eligible_courses[] + pathway_stats{} + insights{}
```

### STPM Flow
```
Student enters STPM grades (PA + 4 subjects + MUET + SPM prereqs)
  → stpm.ts calculates CGPA on frontend
  → stpm_engine.py checks eligibility (CGPA threshold, subjects, MUET band, mata gred)
  → stpm_ranking.py adds fit scores (base + CGPA margin + field interest - interview penalty)
  → Response: eligible_programmes[] + ranked[]
```

### Quiz Flow
```
6 questions (BM/EN/TA) → quiz_engine.py accumulates signals
  → Multi-select weight splitting, conditional Q2.5
  → student_signals JSON stored in StudentProfile
  → Used by ranking_engine.py for fit score calculation
```

---

## Test Summary

| Category | Files | Tests | Notes |
|----------|-------|-------|-------|
| Golden Masters | 2 | 2 | SPM: 8,283 cases, STPM: 1,811 cases — run before any engine change |
| API Endpoints | 3 | 73 | Eligibility, ranking, search, STPM integration |
| Engine Logic | 3 | 88 | Ranking, STPM engine, STPM ranking |
| Pathways | 1 | 32 | Matric tracks, STPM bidangs |
| Data Loading | 3 | 39 | CSV loaders, STPM data, pre-U courses |
| Quiz | 1 | 24 | Endpoints, engine, multi-select |
| Serializers | 1 | 27 | Grade mapping, normalisation |
| User Features | 4 | 47 | Auth (9 failures), profile, saved courses, outcomes |
| Reports | 2 | 16 | Engine + views |
| Insights | 1 | 8 | Insights generation |
| **Total** | **20** | **~336** | **9 known auth test failures** |

**Frontend: 0 tests.**

---

## Key Technical Debt Indicators (for audit)

This section flags areas to investigate — not fixes, just pointers:

- **9 pre-existing auth test failures** in test_auth.py
- **Frontend has zero tests** — all logic in pathways.ts, merit.ts, stpm.ts is untested
- **Client-side eligibility duplication** — pathways.ts mirrors backend pathways.py
- **STPM CGPA calculator duplicated** — stpm.ts (frontend) mirrors stpm_engine.py (backend)
- **No error/loading/not-found pages** — using Next.js defaults
- **settings/page.tsx** — appears to be a stub (TBD)
- **Legacy archive** — 246 files in _archive/streamlit/, status unclear
- **Management commands** — enrich_stpm_metadata.py and fix_stpm_names.py are one-time scripts still in codebase
- **db.sqlite3** — local dev database present in project folder
