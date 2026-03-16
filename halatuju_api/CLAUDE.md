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
│  │ 5319 baseline matches     │  │
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

### Subject Keys (Unified)

Frontend and backend both use the same lowercase engine keys (`bm`, `eng`, `math`, `phy`, etc.). The single source of truth is `halatuju-web/src/lib/subjects.ts` which exports `SPM_SUBJECTS`, `SPM_CORE_SUBJECTS`, `SPM_STREAM_POOLS`, and `SPM_ALL_ELECTIVE_SUBJECTS`. No serializer mapping is needed — keys pass through as-is.

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

# Run ALL tests (546 collected, 546 pass, 0 failures, 0 skipped)
python -m pytest apps/courses/tests/ apps/reports/tests/ -v

# Golden master only (5319 baseline)
python -m pytest apps/courses/tests/test_golden_master.py -v

# Serializer tests (27 tests — grade mapping, normalization)
python -m pytest apps/courses/tests/test_serializers.py -v

# API endpoint tests (52 tests — eligibility incl. Matric/STPM, PISMP, course detail, search)
python -m pytest apps/courses/tests/test_api.py -v
```

### Test Coverage

| File | Tests | What's Covered |
|------|-------|----------------|
| test_golden_master.py | 1 (50 students × all courses) | Engine integrity — 5319 baseline (DB fixtures) |
| test_serializers.py | 27 | Grade key passthrough, gender/nationality normalization, bool→Ya/Tidak, validation |
| test_api.py | 73 | Eligibility endpoint (perfect/ghost/frontend/engine keys, colorblind, nationality, merit labels, PISMP integration, Matric/STPM integration, pathway_stats), course detail offerings (fees, hyperlink, allowances, badges, empty fields), career occupations (included, fields, empty), course/institution CRUD, search (text/level/field/field_key/source_type/state/pagination/combined/institution count/institution name/institution state/empty offering/field_keys filter), unified search (both qualifications, qualification filter, STPM field mapping, bumiputera exclusion, filters include qualifications, cross-qualification text search, field filter STPM, level/source_type filter skipping), calculate endpoints (merit, cgpa, pathways with signals) |
| test_auth.py | 15 | Auth enforcement — protected endpoints reject 401, accept with JWT 200, public endpoints open, profile sync (create/update/anon reject), profile name+school fields |
| test_saved_courses.py | 17 | SPM save/list/delete/idempotent/course_type, STPM save (auto-detect prefix + explicit type)/list/filter/delete/patch/404, both types list, qualification filter (SPM/STPM), check constraint (both-null/both-set rejected) |
| test_quiz.py | 24 | Quiz endpoints (questions 3 langs, submit single+multi, validation), engine (multi-select, weight splitting, Not Sure Yet, conditional Q2.5, field_interest, signal strength, lang parity) |
| test_ranking.py | 63 | Fit score calculation, category/institution/global caps, merit penalty, sort tie-breaking, credential priority, top_5/rest split, API endpoint validation, field interest matching via field_key (primary/no match/cap/heavy_industry/no field_key/double match), high_stamina, rote_tolerant, quality_priority, work preference cap, pre-U scoring (Matric/STPM prestige, academic bonus, field preference, signal adjustment, signal cap, routing) |
| test_data_loading.py | 10 | TVET metadata enrichment, PISMP metadata enrichment, institution modifiers storage, MASCO occupation model (PK, M2M, reverse relation, idempotent load, __str__) |
| test_insights.py | 8 | Insights engine: empty input, stream breakdown, labels, top fields, merit counts, level distribution, summary text |
| test_report_engine.py | 12 | Report engine: format helpers (grades, signals, courses, insights), prompts (BM/EN), persona mapping, Gemini mock (success, cascade, missing key) |
| test_views.py (reports) | 4 | Report views: list (own only), detail, cross-user 404 regression, validation |
| test_outcomes.py | 10 | Outcome CRUD (create, duplicate 409, with institution, missing course), list (own only), update status, cross-user 404, delete, auth enforcement (GET/POST 401) |
| test_pathways.py | 37 | Matric/STPM eligibility: grade helpers (is_credit, meets_min, find_best_elective), all 4 Matric tracks (sains, kejuruteraan, sains_komputer, perakaunan), both STPM bidangs (sains, sains_sosial), merit calculation, mata gred threshold, check_all_pathways integration, pathway fit score (base, academic bonus, signal cap) |
| test_profile_fields.py | 19 | Expanded profile fields (NRIC, address, phone, income, siblings defaults), SavedCourse interest_status (default, set, got_offer), profile API (GET new fields, PUT new fields), saved-courses API (GET includes status, PATCH updates status), STPM profile fields (exam_type default, STPM fields stored, defaults empty/null), profile sync STPM (create, update, GET returns fields) |
| test_stpm_models.py | 5 | StpmCourse creation + __str__, StpmRequirement creation + defaults, JSON field round-trip, metadata fields (explicit values + defaults) |
| test_stpm_data_loading.py | 17 | Fixture integrity (courses loaded, 1:1 requirements, count ~1113, JSON parsing, booleans, merit scores, proper case) + proper_case_name utility (9 unit tests) |
| test_stpm_engine.py | 15 | CGPA calculator (5), grade comparison (4), eligibility integration (6: strong science, CGPA filter, MUET filter, subject req, result shape, colorblind). Grade scale: A→F with D+(1.33), C-(1.67), E/G legacy aliases |
| test_stpm_golden_master.py | 1 | 5 students × all programmes = 2103 baseline |
| test_stpm_api.py | 9 | STPM eligibility endpoint (exists 200, returns programmes, missing fields 400, count consistency), STPM ranking API (returns 200, scored programmes, sorted desc, missing 400, empty list) |
| test_stpm_search.py | 12 | STPM search API (200, programmes shape, text/university/stream filters, pagination, filter metadata), STPM detail API (200, programme data, 404, subjects list) |
| test_stpm_ranking.py | 10 | STPM fit score (base score, CGPA margin bonus, CGPA margin capped, field interest via field_key, field interest dict format, no field_key edge case, interview penalty), ranked results (sorted desc, empty list, output shape) |
| test_eligibility_service.py | 19 | Service module: compute_student_merit (precomputed/grades/hist rename/default coq), compute_course_merit (standard/no cutoff/tvet/matric/stpm), deduplicate_pismp (passthrough/identical collapse/language merge), sort_eligible_courses (merit order/pismp/iljtm), compute_stats (source_type/pathway_type) |
| test_preu_courses.py | 4 | Pre-U eligibility (stats include matric/stpm), search (level Pra-U, text Matrikulasi, source_type matric) |
| test_field_taxonomy.py | 140 | FieldTaxonomy model integrity (7), SPM classify_course (51: all frontend_label variants incl. 24 production labels, substring regression tests), STPM classify_stpm_course (57: 10 SPM-matching categories with course_name sub-classification, ~40 STPM-specific categories, edge cases), FieldListView API (4: groups structure, children count), UA course-name overrides (11) |

### Annual STPM Data Refresh (before UPU application season)

```bash
# 1. Scrape latest data from MOHE ePanduan
python manage.py scrape_mohe_stpm --output data/stpm/mohe_2027.csv

# 2. Review diff report (dry run — no changes applied)
python manage.py sync_stpm_mohe --csv data/stpm/mohe_2027.csv

# 3. Apply URL updates
python manage.py sync_stpm_mohe --csv data/stpm/mohe_2027.csv --apply

# 4. Validate URLs (uses Selenium — checks rendered page, not HTTP status)
python manage.py validate_stpm_urls
# --fix flag clears dead URLs; --limit N checks first N only

# 5. For new programmes: parse requirements manually, add to DB
# 6. For removed programmes: consider marking inactive
# 7. Run golden master
python -m pytest apps/courses/tests/test_stpm_golden_master.py -v
```

Requires: `pip install selenium` (URL validation) + `pip install playwright && playwright install chromium` (scraper). Local admin tools, not deployed.

### CRITICAL: Pre-Deploy Checklist

```bash
# 1. Run all tests (590 collected, 590 must pass, SPM golden master = 5319, STPM golden master = 2103)
python -m pytest apps/courses/tests/ apps/reports/tests/ -v

# 2. After any migration that creates/alters tables:
#    Run Supabase Security Advisor and fix all errors
#    (Dashboard → Advisors → Security Advisor → Rerun linter)
#    Or via MCP: get_advisors(project_id, type="security")

# 3. Every new table MUST have RLS enabled + policies
#    See docs/incident-001-rls-disabled.md for templates
```

590 tests must all pass (0 skipped, 0 failures). SPM golden master = 5319, STPM golden master = 2103. If golden master deviates, you broke eligibility logic.
Supabase Security Advisor must show 0 errors before deploy.

## Key Files

| File | Role | Sacred? |
|------|------|---------|
| `apps/courses/eligibility_service.py` | Extracted business logic (merit, PISMP dedup, sort, stats) | No |
| `apps/courses/engine.py` | Eligibility logic | YES — Golden Master |
| `apps/courses/pathways.py` | Matric/STPM eligibility + fit scoring (virtual courses) | No |
| `apps/courses/serializers.py` | Request normalization (grade keys, gender, booleans) | No |
| `apps/courses/views.py` | API endpoints | No |
| `apps/courses/apps.py` | Startup data loading (DB → DataFrame) | Careful |
| `apps/courses/models.py` | Django ORM models | No |
| `apps/courses/quiz_data.py` | Quiz questions (6 Qs × 3 languages) | No |
| `apps/courses/quiz_engine.py` | Stateless quiz signal accumulator | No |
| `apps/courses/ranking_engine.py` | Fit score calculation + course ranking | No |
| `apps/courses/stpm_engine.py` | STPM eligibility logic | YES — STPM Golden Master |
| `apps/courses/stpm_ranking.py` | STPM fit score calculation + ranking | No |
| `apps/courses/utils.py` | Shared utilities (proper_case_name, build_mohe_url) | No |
| `apps/courses/management/commands/scrape_mohe_stpm.py` | MOHE ePanduan scraper (annual) | No |
| `apps/courses/management/commands/sync_stpm_mohe.py` | STPM data sync with diff report | No |
| `apps/courses/management/commands/validate_stpm_urls.py` | Dead link checker | No |
| `apps/courses/management/commands/audit_data.py` | Data completeness report | No |
| `apps/courses/management/commands/generate_stpm_headlines.py` | Gemini-powered STPM headline generator | No |
| `apps/courses/management/commands/backfill_spm_field_key.py` | Deterministic SPM field_key classifier + backfill | No |
| `apps/courses/management/commands/classify_stpm_fields.py` | Deterministic STPM field_key classifier + backfill | No |
| `apps/courses/insights_engine.py` | Deterministic insights from eligibility results | No |
| `apps/reports/report_engine.py` | Gemini-powered narrative report generator | No |
| `apps/reports/prompts.py` | BM/EN counselor report prompt templates | No |
| `apps/reports/views.py` | Report API endpoints (generate, detail, list) | No |

## Known Issues

- 73 PISMP courses without course tags (need tag data to be created)
- 87 offerings without tuition fee data (data not available in source CSVs)

## Next Sprint

**STPM Requirements Pipeline Rebuild Sprint 2 COMPLETE (2026-03-16)**
- Fixture converter (`stpm_json_to_fixture.py`): JSON → Django fixture with null-safety
- 4 new boolean fields on StpmRequirement (`req_male`, `req_female`, `single`, `no_disability`)
- List-aware engine: `check_stpm_subject_group()` + `check_spm_prerequisites()` handle multi-tier groups
- Exclusion list + demographic eligibility checks in engine
- 1,113 courses loaded via new pipeline, STPM golden master 1811 → 2103
- Pipeline tool tests: 199 passing (in `Settings/_tools/stpm_requirements/tests/`)

**Current state:** 590 backend tests, 17 frontend tests, 0 failures. Golden masters: SPM=5319, STPM=2103.

**STPM Requirements Pipeline — Next Sprint (Sprint 3)**
- Build Stage 3 validator tool (`validate_stpm_requirements.py`)
- Write reusable workflow doc (`Settings/_workflows/stpm-requirements-update.md`)

**MASCO Career Mappings Sprint C COMPLETE (2026-03-16)**
- 6 missing field_key→MASCO mappings added (bahasa, kejururawatan, komunikasi, pergigian, sains-data, sains-fizikal)
- Gemini AI pipeline: 89 UA + 73 PISMP + 951 STPM = 1,113 courses mapped
- 3,338 new M2M rows applied to Supabase (courses_career_occupations: 529→1014, stpm_courses_career_occupations: 0→2853)
- Standalone script: `scripts/gemini_map_careers.py`

**Pending work**
- Phone/OTP login (blocked — Twilio ~RM12/mo)
- Grade modulation layer
- Course detail page fixes from `docs/Course Detail Page.pdf`
- Audit course content for BM consistency

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
