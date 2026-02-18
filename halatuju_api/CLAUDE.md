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
- `SUPABASE_JWT_SECRET`

**Frontend (halatuju-web)**:
- `NEXT_PUBLIC_API_URL` — Backend API URL

## Testing

```bash
cd halatuju_api

# Run ALL tests (124 tests)
python -m pytest apps/courses/tests/ -v

# Golden master only (8280 baseline)
python -m pytest apps/courses/tests/test_golden_master.py -v

# Serializer tests (27 tests — grade mapping, normalization)
python -m pytest apps/courses/tests/test_serializers.py -v

# API endpoint tests (29 tests — eligibility, PISMP, course detail offerings, courses, institutions, merit)
python -m pytest apps/courses/tests/test_api.py -v
```

### Test Coverage

| File | Tests | What's Covered |
|------|-------|----------------|
| test_golden_master.py | 1 (50 students × all courses) | Engine integrity — 8280 baseline |
| test_serializers.py | 27 | Grade key mapping, gender/nationality normalization, bool→Ya/Tidak, validation |
| test_api.py | 29 | Eligibility endpoint (perfect/ghost/frontend/engine keys, colorblind, nationality, merit labels, PISMP integration), course detail offerings (fees, hyperlink, allowances, badges, empty fields), course/institution CRUD |
| test_auth.py | 11 | Auth enforcement — protected endpoints reject 403, accept with JWT 200, public endpoints open |
| test_saved_courses.py | 3 | Saved course CRUD — save (201), list (appears), delete (removed) |
| test_quiz.py | 14 | Quiz endpoints (questions 3 langs, submit, validation), engine (accumulation, taxonomy, strength, lang parity) |
| test_ranking.py | 34 | Fit score calculation, category/institution/global caps, merit penalty, sort tie-breaking, credential priority, top_5/rest split, API endpoint validation |
| test_data_loading.py | 5 | TVET metadata enrichment, PISMP metadata enrichment, institution modifiers storage |

### CRITICAL: Pre-Deploy Checklist

```bash
# 1. Run all tests (124 must pass, golden master = 8280)
python -m pytest apps/courses/tests/ -v

# 2. After any migration that creates/alters tables:
#    Run Supabase Security Advisor and fix all errors
#    (Dashboard → Advisors → Security Advisor → Rerun linter)
#    Or via MCP: get_advisors(project_id, type="security")

# 3. Every new table MUST have RLS enabled + policies
#    See docs/incident-001-rls-disabled.md for templates
```

All 124 tests must pass. If golden master deviates from 8280, you broke eligibility logic.
Supabase Security Advisor must show 0 errors before deploy.

## Key Files

| File | Role | Sacred? |
|------|------|---------|
| `apps/courses/engine.py` | Eligibility logic | YES — Golden Master |
| `apps/courses/serializers.py` | Request normalization (grade keys, gender, booleans) | No |
| `apps/courses/views.py` | API endpoints | No |
| `apps/courses/apps.py` | Startup data loading (DB → DataFrame) | Careful |
| `apps/courses/models.py` | Django ORM models | No |
| `apps/courses/quiz_data.py` | Quiz questions (6 Qs × 3 languages) | No |
| `apps/courses/quiz_engine.py` | Stateless quiz signal accumulator | No |
| `apps/courses/ranking_engine.py` | Fit score calculation + course ranking | No |
| `apps/courses/management/commands/load_csv_data.py` | CSV → DB migration (9 loaders) | One-time |
| `apps/courses/management/commands/audit_data.py` | Data completeness report | No |

## Known Issues

- 73 PISMP courses without course tags (need tag data to be created)
- 87 offerings without tuition fee data (data not available in source CSVs)

## Next Sprint

**Sprint 10 — Deterministic Insights**
- Generate deterministic insights from eligibility results (top fields, merit analysis, level distribution)
- Current tests: 124 | Golden master: 8280
- All 383 courses now have complete metadata; institution modifiers in DB
- Current tests: 119 | Golden master: 8280
- `details.csv` is now loaded into CourseInstitution via `load_course_details` in `load_csv_data.py`
- Course detail page now shows fees, allowances, "Apply" button, free hostel/meals badges

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
