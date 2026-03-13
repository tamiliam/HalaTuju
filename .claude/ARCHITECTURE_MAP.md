# HalaTuju Architecture Map

Last updated: Pre-U Courses Sprint (2026-03-13)

## Root

```
HalaTuju/
├── halatuju_api/          # Django REST backend
├── halatuju-web/          # Next.js 14 frontend
├── docs/                  # Documentation, retrospectives, plans
├── _archive/streamlit/    # Legacy Streamlit app (preserved)
├── CHANGELOG.md           # Full version history
├── README.md              # Project overview
└── .gitignore
```

## Backend — halatuju_api/

```
halatuju_api/
├── halatuju/                          # Django project config
│   ├── settings/
│   │   ├── base.py                    # Shared settings (apps, middleware, DB)
│   │   ├── development.py             # Local dev overrides
│   │   └── production.py              # Cloud Run settings (Supabase, CORS)
│   ├── middleware/
│   │   └── supabase_auth.py           # JWT auth (ES256 JWKS + HS256 legacy)
│   ├── urls.py                        # Root URL routing
│   └── wsgi.py                        # WSGI entry point
│
├── apps/
│   ├── courses/                       # Core app — eligibility, ranking, quiz
│   │   ├── models.py                  # Course, CourseRequirement, Institution,
│   │   │                              #   StudentProfile, SavedCourse, AdmissionOutcome,
│   │   │                              #   MascoOccupation, CourseInstitution,
│   │   │                              #   StpmCourse, StpmRequirement
│   │   ├── engine.py                  # SACRED — SPM eligibility checker (golden master: 8283)
│   │   ├── stpm_engine.py             # SACRED — STPM eligibility checker (golden master: 1811)
│   │   ├── pathways.py                # Matric/STPM eligibility formulas (used by views.py for merit_type branching)
│   │   ├── ranking_engine.py          # Fit scores, credential priority, pre-U scoring
│   │   ├── stpm_ranking.py            # STPM fit scores (CGPA margin, field match, interview)
│   │   ├── insights_engine.py         # Deterministic insights from eligibility results
│   │   ├── quiz_engine.py             # Stateless quiz signal accumulator
│   │   ├── quiz_data.py               # 6 questions x 3 languages
│   │   ├── views.py                   # All API endpoints (eligibility, ranking, search,
│   │   │                              #   quiz, profile, saved courses, outcomes, STPM)
│   │   ├── serializers.py             # Grade key mapping (BM→bm, BI→eng, etc.)
│   │   ├── urls.py                    # /api/v1/ routes
│   │   ├── apps.py                    # Startup: DB → DataFrame cache
│   │   ├── management/commands/
│   │   │   ├── load_csv_data.py       # CSV → DB migration (11 loaders, one-time)
│   │   │   ├── load_stpm_data.py      # STPM CSV → DB migration (1,113 programmes)
│   │   │   ├── audit_data.py          # Data completeness report
│   │   │   └── backfill_masco.py      # MASCO occupation mappings
│   │   ├── data/stpm/                 # STPM parsed CSV data files
│   │   ├── migrations/                # 17 migrations (0001–0017)
│   │   └── tests/                     # 22 test files, 359 collected (320 pass)
│   │       ├── test_golden_master.py  # 1 test — 50 students x all courses = 8283
│   │       ├── test_stpm_golden_master.py # 1 — 5 students x STPM = 1811
│   │       ├── test_stpm_engine.py    # 15 — CGPA, grade comparison, eligibility
│   │       ├── test_stpm_models.py    # 3 — StpmCourse/StpmRequirement CRUD
│   │       ├── test_stpm_data_loading.py # 6 — CSV loader
│   │       ├── test_stpm_api.py       # 9 — STPM eligibility + ranking endpoints
│   │       ├── test_stpm_ranking.py   # 9 — STPM fit score + ranked results
│   │       ├── test_stpm_search.py    # 12 — STPM search + detail endpoints
│   │       ├── test_api.py            # 52 — eligibility, search, CRUD
│   │       ├── test_ranking.py        # 62 — fit scores, caps, pre-U scoring
│   │       ├── test_pathways.py       # 32 — Matric/STPM eligibility
│   │       ├── test_serializers.py    # 27 — grade mapping, normalization
│   │       ├── test_quiz.py           # 24 — quiz endpoints + engine
│   │       ├── test_auth.py           # 15 — JWT enforcement (9 pre-existing failures)
│   │       ├── test_profile_fields.py # 19 — expanded profile + saved course + STPM fields
│   │       ├── test_report_engine.py  # 12 — report generation + Gemini mock
│   │       ├── test_data_loading.py   # 10 — TVET/PISMP enrichment, MASCO
│   │       ├── test_outcomes.py       # 10 — admission outcome CRUD
│   │       ├── test_insights.py       # 8 — insights engine
│   │       ├── test_saved_courses.py  # 3 — save/list/delete
│   │       └── test_views.py          # 4 — report views
│   │
│   └── reports/                       # AI report generation
│       ├── models.py                  # Report model (student, content, language)
│       ├── report_engine.py           # Gemini-powered narrative generator
│       ├── prompts.py                 # BM/EN counselor prompt templates
│       ├── views.py                   # Generate, detail, list endpoints
│       └── tests/                     # test_report_engine.py, test_views.py
│
├── scripts/                           # One-time migration utilities
│   ├── generate_sql_inserts.py
│   ├── migrate_to_supabase.py
│   └── supabase_data_migration.sql
│
├── CLAUDE.md                          # Detailed architecture + deploy guide
├── DEPLOY.md                          # Cloud Run deployment steps
├── Dockerfile                         # Container definition
├── requirements.txt                   # Python dependencies
├── pytest.ini                         # Test configuration
└── .env.example                       # Environment variable template
```

## Frontend — halatuju-web/

```
halatuju-web/
├── src/
│   ├── app/                           # Next.js App Router
│   │   ├── layout.tsx                 # Root layout
│   │   ├── page.tsx                   # Landing page
│   │   ├── login/page.tsx             # Login
│   │   ├── auth/callback/page.tsx     # OAuth callback
│   │   ├── onboarding/
│   │   │   ├── exam-type/page.tsx     # Select entrance exam
│   │   │   ├── grades/page.tsx        # Enter SPM grades + CoQ
│   │   │   ├── stpm-grades/page.tsx   # STPM grades (stream selector, 3+1 subjects, koko 90/10), MUET, SPM prereqs (4 compulsory + 2 optional)
│   │   │   └── profile/page.tsx       # Student demographics
│   │   ├── dashboard/page.tsx         # Main dashboard — course cards + merit lights
│   │   ├── quiz/page.tsx              # Career interest quiz
│   │   ├── course/[id]/page.tsx       # Course detail
│   │   ├── search/page.tsx            # Course search + filters
│   │   ├── saved/page.tsx             # Saved courses
│   │   ├── profile/page.tsx           # Student profile
│   │   ├── settings/page.tsx          # Account settings
│   │   ├── outcomes/page.tsx          # Admission outcomes
│   │   ├── report/[id]/page.tsx       # AI counselor report
│   │   ├── pathway/
│   │   │   ├── matric/page.tsx        # Matriculation detail
│   │   │   └── stpm/page.tsx          # STPM detail
│   │   ├── about/page.tsx
│   │   ├── contact/page.tsx
│   │   ├── privacy/page.tsx
│   │   ├── cookies/page.tsx
│   │   └── terms/page.tsx
│   │
│   ├── components/                    # Reusable UI
│   │   ├── AppHeader.tsx              # Navigation
│   │   ├── AppFooter.tsx              # Footer
│   │   ├── AuthGateModal.tsx          # Login prompt for unauth users
│   │   ├── CourseCard.tsx             # Course card with merit indicator
│   │   ├── FilterPill.tsx             # Filter tags
│   │   ├── LanguageSelector.tsx       # EN/BM/TA switcher
│   │   ├── PathwayCards.tsx           # Pathway option grid
│   │   ├── PathwayTrackCard.tsx       # Individual track display
│   │   ├── ProgressStepper.tsx        # Onboarding progress
│   │   └── RequirementsCard.tsx       # Course requirements
│   │
│   ├── lib/                           # Client-side logic
│   │   ├── api.ts                     # HTTP client for backend API
│   │   ├── supabase.ts                # Supabase client init
│   │   ├── auth-context.tsx           # Auth React Context
│   │   ├── i18n.tsx                   # i18n helper
│   │   ├── subjects.ts               # Subject mappings (SPM + STPM constants)
│   │   ├── stpm.ts                   # STPM CGPA calculator (mirrors backend)
│   │   ├── pathways.ts               # Pathway definitions (still used by detail pages)
│   │   └── merit.ts                   # Merit formula (UPU)
│   │
│   ├── data/                          # Static data
│   │   ├── matric-colleges.ts         # Matriculation college list
│   │   └── stpm-schools.json          # STPM schools (large)
│   │
│   └── messages/                      # i18n translations
│       ├── en.json                    # English (~500 keys)
│       ├── ms.json                    # Bahasa Melayu
│       └── ta.json                    # Tamil
│
├── public/                            # Static assets
│   └── logo-icon.png
├── scripts/
│   └── check-i18n.js                 # Translation completeness checker
├── Dockerfile
├── next.config.js
├── tailwind.config.ts
├── package.json
├── .env.example
└── .env.production                    # Public Supabase anon key + API URL
```

## Documentation — docs/

```
docs/
├── roadmap.md                         # Active — STPM entrance + admin dashboard planned
├── release-notes-v1.33.0.md          # Latest release
├── lessons.md                         # Cross-cutting engineering lessons
├── Course Detail Page.pdf             # UI design spec
├── README.md                          # Docs index
├── incident-001-rls-disabled.md       # RLS incident + templates
├── retrospective-*.md                 # 30+ sprint/release retrospectives
├── plans/
│   ├── 2026-03-09-whatsapp-otp-plan.md  # Active — not yet built
│   ├── 2026-03-12-stpm-entrance.md      # STPM master plan (5 sprints, 22 tasks)
│   ├── 2026-03-12-stpm-sprint2-frontend.md # Sprint 2 plan (7 tasks, DONE)
│   ├── 2026-03-13-stpm-sprint3-ranking.md # Sprint 3 plan (5 tasks, DONE)
│   └── 2026-03-13-stpm-sprint4-search-detail.md # Sprint 4 plan (6 tasks, DONE)
└── archive/                           # Completed plans, old roadmaps, design docs
    ├── 2026-02-completed/             # February completion reports
    ├── audits/                        # Data audit reports
    ├── stpm_implementation_plan.md    # Old STPM plan (superseded by roadmap.md)
    ├── pismp_integration_plan.md      # Done
    └── ...                            # Quiz redesign iterations, old roadmaps
```

## Database — Supabase

**Project**: `pbrrlyoyyiftckqvzvvo` (Singapore)

Key tables: `courses`, `course_requirements`, `course_institutions`, `institutions`, `course_tags`, `student_profiles`, `saved_courses`, `admission_outcomes`, `masco_occupations`, `course_masco_link`, `reports`, `stpm_courses`, `stpm_requirements`

- 389 SPM courses (383 original + 6 pre-U), 239 institutions (212 original + 27 IPG)
- 1,113 STPM degree programmes (162 bumiputera-only excluded at runtime)
- RLS enabled on all tables, 0 security errors
- Course `#` suffix = "typically has interview" (data marker, not display)

## Data Flow

```
Student enters grades → Serializer maps keys → Engine checks DataFrame
    → merit_type branching (standard/matric/stpm_mata_gred) → PISMP deduplication
    → Sort by merit tier → credential → pathway → cutoff
    → Ranking engine adds fit scores from quiz signals
    → Response: eligible_courses[] + pathway_stats{}
```
