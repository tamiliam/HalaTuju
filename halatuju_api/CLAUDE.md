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

# Run ALL tests (70 tests)
python -m pytest apps/courses/tests/ -v

# Golden master only (8280 baseline)
python -m pytest apps/courses/tests/test_golden_master.py -v

# Serializer tests (27 tests — grade mapping, normalization)
python -m pytest apps/courses/tests/test_serializers.py -v

# API endpoint tests (14 tests — eligibility, courses, institutions)
python -m pytest apps/courses/tests/test_api.py -v
```

### Test Coverage

| File | Tests | What's Covered |
|------|-------|----------------|
| test_golden_master.py | 1 (50 students × all courses) | Engine integrity — 8280 baseline |
| test_serializers.py | 27 | Grade key mapping, gender/nationality normalization, bool→Ya/Tidak, validation |
| test_api.py | 14 | Eligibility endpoint (perfect/ghost/frontend/engine keys, colorblind, nationality), course/institution CRUD |
| test_auth.py | 11 | Auth enforcement — protected endpoints reject 403, accept with JWT 200, public endpoints open |
| test_saved_courses.py | 3 | Saved course CRUD — save (201), list (appears), delete (removed) |
| test_quiz.py | 14 | Quiz endpoints (questions 3 langs, submit, validation), engine (accumulation, taxonomy, strength, lang parity) |

### CRITICAL: Pre-Deploy Checklist

```bash
# 1. Run all tests (70 must pass, golden master = 8280)
python -m pytest apps/courses/tests/ -v

# 2. After any migration that creates/alters tables:
#    Run Supabase Security Advisor and fix all errors
#    (Dashboard → Advisors → Security Advisor → Rerun linter)
#    Or via MCP: get_advisors(project_id, type="security")

# 3. Every new table MUST have RLS enabled + policies
#    See docs/incident-001-rls-disabled.md for templates
```

All 70 tests must pass. If golden master deviates from 8280, you broke eligibility logic.
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
| `apps/courses/management/commands/load_csv_data.py` | CSV → DB migration | One-time |

## Known Issues

- Ranking endpoint (`/api/v1/ranking/`) is a stub — needs port from `ranking_engine.py`
- Course names show as course_id when Course table doesn't have the entry (graceful fallback in views.py)

## Next Sprint

**Sprint 4 — Ranking Engine Backend**
- Port `src/ranking_engine.py` → `apps/courses/ranking_engine.py` (551 lines — most complex migration task)
- Load course tags from `CourseTag` model, institution modifiers from `Institution` model
- Implement `RankingView.post()` (currently a stub returning empty arrays)
- Add `RankingRequestSerializer` for input validation
- 10-15 tests (score calculation, cap enforcement, merit penalty, tie-breaking, sort stability)
- No deploy (backend only)
- Current tests: 70 | Golden master: 8280

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
