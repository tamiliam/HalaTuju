# HalaTuju API — Architecture & Operations

## Overview

Django REST API for SPM course eligibility checking. Deployed on Cloud Run (asia-southeast1).

## Architecture

```
┌─────────────────────────────────┐
│  Next.js Frontend (Cloud Run)   │
│  halatuju-web                   │
└──────────────┬──────────────────┘
               │ POST /api/v1/eligibility/check/
               │ POST /api/v1/profile/sync/
               │ GET/POST/PUT/DELETE /api/v1/outcomes/
               ▼
┌─────────────────────────────────┐
│  Django API (Cloud Run)         │
│  halatuju-api                   │
│                                 │
│  ┌─ Serializer ──────────────┐  │
│  │ Grade key mapping         │  │
│  │ BM→bm, BI→eng, MAT→math  │  │
│  │ Gender/nationality norm.  │  │
│  │ Bool → Ya/Tidak           │  │
│  └───────────┬───────────────┘  │
│              ▼                  │
│  ┌─ Hybrid Engine ───────────┐  │
│  │ DB → Pandas at startup    │  │
│  │ engine.py (GOLDEN MASTER) │  │
│  │ 8280 baseline matches     │  │
│  └───────────────────────────┘  │
└──────────────┬──────────────────┘
               │ Django ORM (startup only)
               ▼
┌─────────────────────────────────┐
│  Supabase PostgreSQL            │
│  pbrrlyoyyiftckqvzvvo           │
│  (Singapore)                    │
└─────────────────────────────────┘
```

### Hybrid Engine Approach

- At startup, `CoursesConfig.ready()` loads all `CourseRequirement` rows from DB into a Pandas DataFrame
- The engine runs eligibility checks against this in-memory DataFrame
- **Why**: Avoids cold start CSV loading (5-10s). DB is source of truth, DataFrame is runtime cache.
- **Trade-off**: ~1GB RAM per container. Acceptable for correctness.

### Grade Key Mapping (Serializer)

Frontend sends UI subject IDs → serializer maps to engine internal keys:

| Frontend | Engine | Subject |
|----------|--------|---------|
| BM | bm | Bahasa Melayu |
| BI | eng | English |
| SEJ | hist | Sejarah |
| MAT | math | Matematik |
| PHY | phy | Fizik |
| CHE | chem | Kimia |
| BIO | bio | Biologi |
| AMT | addmath | Matematik Tambahan |
| PI | islam | Pendidikan Islam |
| PM | moral | Pendidikan Moral |
| SN | sci | Sains |
| ECO | ekonomi | Ekonomi |
| ACC | poa | Prinsip Perakaunan |
| BUS | business | Perniagaan |
| GEO | geo | Geografi |

Unmapped keys (e.g. `COMP_SCI`) fall back to `.lower()`.

## Deployment

| Component | Platform | Region | Service |
|-----------|----------|--------|---------|
| Backend | Cloud Run | asia-southeast1 | halatuju-api |
| Frontend | Cloud Run | asia-southeast1 | halatuju-web |
| Database | Supabase | Singapore | pbrrlyoyyiftckqvzvvo |

### GCP Project

`gen-lang-client-0871147736` (account: `tamiliam@gmail.com`)

### Deploy Commands

```bash
# Backend
cd halatuju_api
gcloud run deploy halatuju-api --source . --region asia-southeast1 --project gen-lang-client-0871147736 --allow-unauthenticated

# Frontend
cd halatuju-web
gcloud run deploy halatuju-web --source . --region asia-southeast1 --project gen-lang-client-0871147736 --allow-unauthenticated
```

### Environment Variables (Cloud Run)

**Backend (halatuju-api)**:
- `DATABASE_URL` — Supabase Session Pooler URI
- `SECRET_KEY` — Django secret
- `DJANGO_SETTINGS_MODULE=halatuju.settings.production`
- `CORS_ALLOWED_ORIGINS`
- `SUPABASE_JWT_SECRET` — HS256 secret for legacy anon/service key JWTs
- `SUPABASE_URL` — e.g. `https://pbrrlyoyyiftckqvzvvo.supabase.co` (needed for ES256 JWKS verification)
- `GEMINI_API_KEY` — Google Gemini API key for AI report generation

**Frontend (halatuju-web)**:
- `NEXT_PUBLIC_API_URL` — Backend API URL

## Testing

```bash
cd halatuju_api

# Run ALL tests (359 collected, 320 pass, 9 pre-existing JWT failures)
python -m pytest apps/courses/tests/ -v

# Golden master only (8283 baseline)
python -m pytest apps/courses/tests/test_golden_master.py -v

# Serializer tests (27 tests — grade mapping, normalization)
python -m pytest apps/courses/tests/test_serializers.py -v

# API endpoint tests (52 tests — eligibility incl. Matric/STPM, PISMP, course detail, search)
python -m pytest apps/courses/tests/test_api.py -v
```

### Test Coverage

| File | Tests | What's Covered |
|------|-------|----------------|
| test_golden_master.py | 1 (50 students × all courses) | Engine integrity — 8283 baseline |
| test_serializers.py | 27 | Grade key mapping, gender/nationality normalization, bool→Ya/Tidak, validation |
| test_api.py | 64 | Eligibility endpoint (perfect/ghost/frontend/engine keys, colorblind, nationality, merit labels, PISMP integration, Matric/STPM integration, pathway_stats), course detail offerings (fees, hyperlink, allowances, badges, empty fields), career occupations (included, fields, empty), course/institution CRUD, search (text/level/field/source_type/state/pagination/combined/institution count/institution name/institution state/empty offering), unified search (both qualifications, qualification filter, STPM field mapping, bumiputera exclusion, filters include qualifications, cross-qualification text search, field filter STPM, level/source_type filter skipping) |
| test_auth.py | 15 | Auth enforcement — protected endpoints reject 403, accept with JWT 200, public endpoints open, profile sync (create/update/anon reject), profile name+school fields |
| test_saved_courses.py | 3 | Saved course CRUD — save (201), list (appears), delete (removed) |
| test_quiz.py | 24 | Quiz endpoints (questions 3 langs, submit single+multi, validation), engine (multi-select, weight splitting, Not Sure Yet, conditional Q2.5, field_interest, signal strength, lang parity) |
| test_ranking.py | 62 | Fit score calculation, category/institution/global caps, merit penalty, sort tie-breaking, credential priority, top_5/rest split, API endpoint validation, field interest matching (primary/secondary/no match/multi-field/cap), high_stamina, rote_tolerant, quality_priority, work preference cap, pre-U scoring (Matric/STPM prestige, academic bonus, field preference, signal adjustment, signal cap, routing) |
| test_data_loading.py | 10 | TVET metadata enrichment, PISMP metadata enrichment, institution modifiers storage, MASCO occupation model (PK, M2M, reverse relation, idempotent load, __str__) |
| test_insights.py | 8 | Insights engine: empty input, stream breakdown, labels, top fields, merit counts, level distribution, summary text |
| test_report_engine.py | 12 | Report engine: format helpers (grades, signals, courses, insights), prompts (BM/EN), persona mapping, Gemini mock (success, cascade, missing key) |
| test_views.py (reports) | 4 | Report views: list (own only), detail, cross-user 404 regression, validation |
| test_outcomes.py | 10 | Outcome CRUD (create, duplicate 409, with institution, missing course), list (own only), update status, cross-user 404, delete, auth enforcement (GET/POST 403) |
| test_pathways.py | 32 | Matric/STPM eligibility: grade helpers (is_credit, meets_min, find_best_elective), all 4 Matric tracks (sains, kejuruteraan, sains_komputer, perakaunan), both STPM bidangs (sains, sains_sosial), merit calculation, mata gred threshold, check_all_pathways integration |
| test_profile_fields.py | 19 | Expanded profile fields (NRIC, address, phone, income, siblings defaults), SavedCourse interest_status (default, set, got_offer), profile API (GET new fields, PUT new fields), saved-courses API (GET includes status, PATCH updates status), STPM profile fields (exam_type default, STPM fields stored, defaults empty/null), profile sync STPM (create, update, GET returns fields) |
| test_stpm_models.py | 5 | StpmCourse creation + __str__, StpmRequirement creation + defaults, JSON field round-trip, metadata fields (explicit values + defaults) |
| test_stpm_data_loading.py | 6 | CSV loader: creates courses, creates requirements, correct count (~1113), idempotent, JSON parsing, boolean fields |
| test_stpm_engine.py | 15 | CGPA calculator (5), grade comparison (4), eligibility integration (6: strong science, CGPA filter, MUET filter, subject req, result shape, colorblind). Grade scale: A→F with D+(1.33), C-(1.67), E/G legacy aliases |
| test_stpm_golden_master.py | 1 | 5 students × all programmes = 1811 baseline |
| test_stpm_api.py | 9 | STPM eligibility endpoint (exists 200, returns programmes, missing fields 400, count consistency), STPM ranking API (returns 200, scored programmes, sorted desc, missing 400, empty list) |
| test_stpm_search.py | 12 | STPM search API (200, programmes shape, text/university/stream filters, pagination, filter metadata), STPM detail API (200, programme data, 404, subjects list) |
| test_stpm_ranking.py | 9 | STPM fit score (base score, CGPA margin bonus, CGPA margin capped, field interest match dict format, interview penalty), ranked results (sorted desc, empty list, output shape) |
| test_preu_courses.py | 9 | Pre-U eligibility (matric sains eligible, merit values, STPM sains eligible, mata gred values, bad grades excluded, stats), search (level Pra-U, text Matrikulasi, source_type matric) |

### CRITICAL: Pre-Deploy Checklist

```bash
# 1. Run all tests (359 collected, 320 must pass, SPM golden master = 8283, STPM golden master = 1811)
python -m pytest apps/courses/tests/ -v

# 2. After any migration that creates/alters tables:
#    Run Supabase Security Advisor and fix all errors
#    (Dashboard → Advisors → Security Advisor → Rerun linter)
#    Or via MCP: get_advisors(project_id, type="security")

# 3. Every new table MUST have RLS enabled + policies
#    See docs/incident-001-rls-disabled.md for templates
```

320 tests must pass out of 359 collected (9 JWT auth tests have pre-existing failures — malformed test tokens, not production issue). If golden master deviates from 8283, you broke eligibility logic.
Supabase Security Advisor must show 0 errors before deploy.

## Key Files

| File | Role | Sacred? |
|------|------|---------|
| `apps/courses/engine.py` | Eligibility logic | YES — Golden Master |
| `apps/courses/pathways.py` | Matric/STPM eligibility (virtual courses) | No |
| `apps/courses/serializers.py` | Request normalization (grade keys, gender, booleans) | No |
| `apps/courses/views.py` | API endpoints | No |
| `apps/courses/apps.py` | Startup data loading (DB → DataFrame) | Careful |
| `apps/courses/models.py` | Django ORM models | No |
| `apps/courses/quiz_data.py` | Quiz questions (6 Qs × 3 languages) | No |
| `apps/courses/quiz_engine.py` | Stateless quiz signal accumulator | No |
| `apps/courses/ranking_engine.py` | Fit score calculation + course ranking | No |
| `apps/courses/stpm_engine.py` | STPM eligibility logic | YES — STPM Golden Master |
| `apps/courses/stpm_ranking.py` | STPM fit score calculation + ranking | No |
| `apps/courses/management/commands/load_csv_data.py` | CSV → DB migration (11 loaders) | One-time |
| `apps/courses/management/commands/load_stpm_data.py` | STPM CSV → DB migration | One-time |
| `apps/courses/management/commands/enrich_stpm_metadata.py` | Gemini STPM field/category/description enrichment | One-time |
| `apps/courses/insights_engine.py` | Deterministic insights from eligibility results | No |
| `apps/courses/management/commands/audit_data.py` | Data completeness report | No |
| `apps/reports/report_engine.py` | Gemini-powered narrative report generator | No |
| `apps/reports/prompts.py` | BM/EN counselor report prompt templates | No |
| `apps/reports/views.py` | Report API endpoints (generate, detail, list) | No |

## Known Issues

- 73 PISMP courses without course tags (need tag data to be created)
- 87 offerings without tuition fee data (data not available in source CSVs)

## Next Sprint

**STPM Sprints 1-8 COMPLETE — merged to main, deployed**
- 1,113 STPM degree programmes: eligibility, ranking, search, detail, dashboard cards
- Unified `/search` page: SPM + STPM with qualification filter
- STPM dashboard uses same CourseCard as SPM (images, badges, merit bars)
- All names proper-cased in Supabase. `feature/stpm-entrance` branch deleted.

**Pre-U Courses Sprint COMPLETE — merged to main, Supabase migrated**
- 6 pre-university courses (4 matric + 2 STPM) as real Course rows with `merit_type` branching
- Badge consistency: TVET → ILJTM/ILKBS, University → ua, labels in Malay, Pra-U level badge

**UI Polish & Consistency Sprint COMPLETE — merged to main, deployed**
- Rich institution cards for pre-U course detail pages (STPM schools with PPD/subjects/phone, matric colleges with tracks/phone/website)
- STPM programme detail page redesigned to match SPM format (header, about, quick facts, institution card, save actions)
- Search filter labels standardised to Malay, TVET removed, Kolej Matrikulasi and Tingkatan 6 added
- DB state normalisation (WP Kuala Lumpur, WP Labuan)
- STPM detail API enriched with field, category, description, merit_score

**Pending work**
- Phone/OTP login implementation (currently blocked with "coming soon" message)
- Grade modulation layer (4 rules cross-referencing StudentProfile.grades with quiz signals)
- Course detail page: remaining fixes from `docs/Course Detail Page.pdf`
- Store `signal_strength` in Supabase (currently only `student_signals` synced)
- STPM field metadata refinement: 207 unique field values from Gemini (expected ~30) — consider normalisation pass
- Fix 13 pre-existing auth/JWT test failures (test_auth, test_saved_courses, test_views)

## Streamlit App (Legacy — migrating to Django API)

**Root directory:** `./HalaTuju` (Streamlit), `./HalaTuju/halatuju_api` (Django API)

### Critical Rules (Non-Negotiable)

| Rule | What It Means |
|------|---------------|
| **Golden Master** | `src/engine.py` is sacred. Run `python -m unittest tests/test_golden_master.py` before AND after any change touching ranking or eligibility logic. |
| **Data Integrity** | `requirements.csv` must align with `course_tags.json`. If unsure, run `python _tools/check_integrity.py`. |
| **Data Discipline** | Do not create new CSVs. Append only to `data/courses.csv`. |

### Common Commands (Streamlit)

| Action | Command |
|--------|---------|
| Run App | `cd HalaTuju && streamlit run main.py` |
| Run Golden Master Tests | `cd HalaTuju && python -m unittest tests/test_golden_master.py` |
| Lint Code | `flake8 src/` |
| Snapshot Data | `python _tools/snapshot_db.py` (run before mass edits) |

### Coding Standards

- **Type hints** on all new functions
- **Absolute imports** (`from src.engine import ...`)
- **Reasoning comments** for complex logic (ranking, penalties) — comment block-by-block
- Deterministic correctness beats cleverness

General rules (testing, deployment discipline, git, cleanup, British English) are in the workspace-level `CLAUDE.md`.
