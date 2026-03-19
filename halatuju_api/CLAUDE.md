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
               │ POST /api/v1/admin/invite/
               │ GET /api/v1/admin/orgs/
               ▼
┌─────────────────────────────────┐
│  Django API (Cloud Run)         │
│  halatuju-api                   │
│                                 │
│  ┌─ Serializer ──────────────┐  │
│  │ Grade key mapping         │  │
│  │ BM→bm, BI→eng, MAT→math  │  │
│  │ Gender/nationality norm.  │  │
│  │ Bool passthrough           │  │
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

# Run ALL tests (892 collected, 892 pass, 0 failures, 0 skipped)
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
| test_serializers.py | 27 | Grade key passthrough, gender/nationality normalization, bool passthrough, validation |
| test_api.py | 73 | Eligibility endpoint (perfect/ghost/frontend/engine keys, colorblind, nationality, merit labels, PISMP integration, Matric/STPM integration, pathway_stats), course detail offerings (fees, hyperlink, allowances, badges, empty fields), career occupations (included, fields, empty), course/institution CRUD, search (text/level/field/field_key/source_type/state/pagination/combined/institution count/institution name/institution state/empty offering/field_keys filter), unified search (both qualifications, qualification filter, STPM field mapping, bumiputera exclusion, filters include qualifications, cross-qualification text search, field filter STPM, level/source_type filter skipping), calculate endpoints (merit, cgpa, pathways with signals) |
| test_auth.py | 15 | Auth enforcement — protected endpoints reject 401, accept with JWT 200, public endpoints open, profile sync (create/update/anon reject), profile name+school fields |
| test_saved_courses.py | 17 | SPM save/list/delete/idempotent/course_type, STPM save (auto-detect prefix + explicit type)/list/filter/delete/patch/404, both types list, qualification filter (SPM/STPM), check constraint (both-null/both-set rejected) |
| test_quiz.py | 24 | Quiz endpoints (questions 3 langs, submit single+multi, validation), engine (multi-select, weight splitting, Not Sure Yet, conditional Q2.5, field_interest, signal strength, lang parity) |
| test_ranking.py | 62 | Fit score calculation, category/institution/global caps, merit penalty, sort tie-breaking, credential priority, ranked list output, API endpoint validation, field interest matching via field_key (primary/no match/cap/heavy_industry/no field_key/double match), high_stamina, rote_tolerant, quality_priority, work preference cap, pre-U scoring (Matric/STPM prestige, academic bonus, field preference, signal adjustment, signal cap, routing) |
| test_data_loading.py | 10 | TVET metadata enrichment, PISMP metadata enrichment, institution modifiers storage, MASCO occupation model (PK, M2M, reverse relation, idempotent load, __str__) |
| test_insights.py | 8 | Insights engine: empty input, stream breakdown, labels, top fields, merit counts, level distribution, summary text |
| test_report_engine.py | 37 | Report engine: format helpers (SPM grades, STPM grades, human-readable signals BM/EN, courses sorted by fit score, insights), prompts (SPM BM/EN, STPM BM/EN, placeholder parity), exam_type routing (SPM/STPM), Gemini mock (success, cascade, missing key) |
| test_views.py (reports) | 8 | Report views: list (own only), detail, cross-user 404 regression, validation, student name passthrough, STPM exam_type passthrough |
| test_outcomes.py | 10 | Outcome CRUD (create, duplicate 409, with institution, missing course), list (own only), update status, cross-user 404, delete, auth enforcement (GET/POST 401) |
| test_pathways.py | 37 | Matric/STPM eligibility: grade helpers (is_credit, meets_min, find_best_elective), all 4 Matric tracks (sains, kejuruteraan, sains_komputer, perakaunan), both STPM bidangs (sains, sains_sosial), merit calculation, mata gred threshold, check_all_pathways integration, pathway fit score (base, academic bonus, signal cap) |
| test_profile_fields.py | 19 | Expanded profile fields (NRIC, address, phone, income, siblings defaults), SavedCourse interest_status (default, set, got_offer), profile API (GET new fields, PUT new fields), saved-courses API (GET includes status, PATCH updates status), STPM profile fields (exam_type default, STPM fields stored, defaults empty/null), profile sync STPM (create, update, GET returns fields) |
| test_stpm_models.py | 7 | StpmCourse creation + __str__, StpmRequirement creation + defaults, JSON field round-trip, metadata fields (explicit values + defaults), is_active (defaults true, can set false) |
| test_stpm_data_loading.py | 17 | Fixture integrity (courses loaded, 1:1 requirements, count ~1113, JSON parsing, booleans, merit scores, proper case) + proper_case_name utility (9 unit tests) |
| test_stpm_engine.py | 16 | CGPA calculator (5), grade comparison (4), eligibility integration (6: strong science, CGPA filter, MUET filter, subject req, result shape, colorblind), is_active filtering (1: inactive excluded from eligibility). Grade scale: A→F with D+(1.33), C-(1.67), E/G legacy aliases |
| test_stpm_golden_master.py | 1 | 5 students × all programmes = 2103 baseline |
| test_stpm_api.py | 16 | STPM eligibility endpoint (exists 200, returns programmes, missing fields 400, count consistency), STPM ranking API (returns 200, scored programmes, sorted desc, missing 400, empty list), W11 pre-quiz RIASEC (science boost I-type, arts boost A-type, post-quiz not overwritten, empty/PA no effect, framing) |
| test_stpm_search.py | 14 | STPM search API (200, programmes shape, text/university/stream filters, pagination, filter metadata), STPM detail API (200, programme data, 404, subjects list), is_active filtering (inactive excluded from STPM search, inactive excluded from unified search) |
| test_stpm_sync.py | 7 | Sync command: dry run reports removed, apply deactivates removed, reactivates returned, updates URLs, reports merit changes, reports new programmes, shows inactive count |
| test_stpm_ranking.py | 58 | CGPA margin (5: base, bonus, cap, negative, partial), field match (9: primary +8, automotif via mekanikal, secondary +4, no match, empty, cross-domain +2, cap, law), RIASEC alignment (8: primary +6, secondary +3, no match, cross +2, cap, empty, no signals, tied seeds), efficacy (6: confirmed/confident/open/redirect/mismatch/none), goal alignment (7: professional+medicine, nonreg, postgrad+research, entrepreneurial+business, employment, no goal, no field), resilience (7: redirect+high/-3, redirect+moderate/-1, supported+high/-1, redirect+low/0, high resilience/0, no difficulty, no signals), interview (2), full integration (4: max/min score, no quiz, v1 compat), result framing (5: 3 modes, default, subtitle), ranked results (5: sort, empty, output, merit survives, quiz affects order) |
| test_stpm_quiz_engine.py | 56 | RIASEC seed calculation (all combos, PA excluded, unknown subjects), primary seed (single/tie/empty), branch routing (science/arts/mixed/ICT/MathM/PA), cross-stream detection, question generation (branch Q2, Q3 variants, Q5 filtering, trilingual, lang fallback), Q3/Q4 resolution (all fields, weak/strong grade threshold, interpolation), signal accumulation (RIASEC seed, field interest, field_key, efficacy, context, strength levels, arts branch, error handling) |
| test_stpm_quiz_data.py | 22 | Structure validation (required fields, no dupes), trilingual completeness (prompts, options, Q5, display names), signal taxonomy consistency (categories, no cross-category dupes, question signals in taxonomy), field key map, subject classification, grade points monotonicity |
| test_stpm_quiz_api.py | 24 | Questions endpoint (200, branch/seed, Q3 variants, Q5/trunk, validation, grades JSON, lang), resolve endpoint (200, Q3/Q4, validation), submit endpoint (200, signals, strength, branch, validation, arts branch) |
| test_eligibility_service.py | 19 | Service module: compute_student_merit (precomputed/grades/hist rename/default coq), compute_course_merit (standard/no cutoff/tvet/matric/stpm), deduplicate_pismp (passthrough/identical collapse/language merge), sort_eligible_courses (merit order/pismp/iljtm), compute_stats (source_type/pathway_type) |
| test_preu_courses.py | 4 | Pre-U eligibility (stats include matric/stpm), search (level Pra-U, text Matrikulasi, source_type matric) |
| test_admin_auth.py | 14 | PartnerAdmin model (CRUD, super admin flag), PartnerAdminMixin (UID lookup, email fallback, UID backfill), invite endpoint (super admin only, validation), orgs endpoint, AdminRoleView (admin_name) |
| test_stpm_enrichment.py | 40 | RIASEC mapping (completeness, all 6 types, design doc keys R/I/A/S/E/C, umum excluded), difficulty mapping (valid levels, medicine=high, law=high, business=low), efficacy mapping (valid domains, eng=quantitative, med=scientific, law=verbal, design=practical), mapping consistency (same keys across all 3 maps), FieldTaxonomy riasec_primary (default, valid code, leaf enrichment), StpmCourse fields (default, set/read, all three together), enrich command (dry run, apply RIASEC/difficulty/efficacy, unmapped field_key, taxonomy update, idempotent, multi-course same field) |
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
# 1. Run all tests (932 collected, 932 must pass, SPM golden master = 5319, STPM golden master = 2026)
python -m pytest apps/courses/tests/ apps/reports/tests/ -v

# 2. After any migration that creates/alters tables:
#    Run Supabase Security Advisor and fix all errors
#    (Dashboard → Advisors → Security Advisor → Rerun linter)
#    Or via MCP: get_advisors(project_id, type="security")

# 3. Every new table MUST have RLS enabled + policies
#    See docs/incident-001-rls-disabled.md for templates
```

932 tests must all pass (0 skipped, 0 failures). SPM golden master = 5319, STPM golden master = 2026. If golden master deviates, you broke eligibility logic.
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
| `apps/courses/stpm_quiz_data.py` | STPM quiz questions (~35 Qs × 3 languages, branching) | No |
| `apps/courses/stpm_quiz_engine.py` | RIASEC seed, branch routing, signal accumulation | No |
| `apps/courses/utils.py` | Shared utilities (proper_case_name, build_mohe_url) | No |
| `apps/courses/management/commands/scrape_mohe_stpm.py` | MOHE ePanduan scraper (annual) | No |
| `apps/courses/management/commands/sync_stpm_mohe.py` | STPM data sync with diff report | No |
| `apps/courses/management/commands/validate_stpm_urls.py` | Dead link checker | No |
| `apps/courses/management/commands/audit_data.py` | Data completeness report | No |
| `apps/courses/management/commands/generate_stpm_headlines.py` | Gemini-powered STPM headline generator | No |
| `apps/courses/management/commands/backfill_spm_field_key.py` | Deterministic SPM field_key classifier + backfill | No |
| `apps/courses/management/commands/classify_stpm_fields.py` | Deterministic STPM field_key classifier + backfill | No |
| `apps/courses/management/commands/enrich_stpm_riasec.py` | RIASEC type, difficulty, efficacy domain classifier for StpmCourse + FieldTaxonomy | No |
| `apps/courses/insights_engine.py` | Deterministic insights from eligibility results | No |
| `apps/reports/report_engine.py` | Gemini-powered narrative report generator | No |
| `apps/reports/prompts.py` | SPM/STPM × BM/EN counselor report prompt templates | No |
| `apps/reports/views.py` | Report API endpoints (generate, detail, list) | No |

## Known Issues

- 87 offerings without tuition fee data (data not available in source CSVs)

## Next Sprint

**localStorage & Bug Fixes Sprint COMPLETE (2026-03-19)**
- localStorage always refreshed from Supabase on login (source of truth, not cache)
- Frontend boolean cleanup: 6 sites stopped converting bool→"Ya"/"Tidak", API types cleaned
- Ranking: W4 (PISMP tags) and W11 (STPM stream pre-quiz signal) done
- W16 resolved: 100% STPM enrichment coverage in production

**Current state:** 932 backend tests, 17 frontend tests, 0 failures. Golden masters: SPM=5319, STPM=2026. Deployed.

**Next: Polish & User Testing Sprint**
- User testing with real STPM students (Science + Arts branches)
- Adjust signal weights based on feedback
- Mobile testing across quiz branches
- Trilingual content review (verify all quiz question text renders correctly in BM/TA)
- 8 unmapped field_keys for RIASEC (bahasa, kejururawatan, komunikasi, pergigian, sains-data, sains-fizikal, sains-sosial, umum)

**Pending work (parked)**
- **Ranking improvements** (full audit: `docs/2026-03-18-ranking-audit.md`)
  - ~~W4: PISMP course tags~~ — **DONE** (2026-03-19). 73 PISMP courses backfilled via `backfill_pismp_tags` command + SQL. 12 specialisations mapped (Sains→lab, Jasmani→field, Muzik/Seni→workshop, Reka Bentuk→workshop+design, etc.). 33 tests added. Applied to production Supabase.
  - W7: Expand SPM FIELD_KEY_MAP — only 12 quiz signals map to field_keys but taxonomy has ~45 keys. Courses in unmapped fields (pelancongan, tekstil, alam-sekitar) get no field interest boost. Fix: map existing signals more broadly (e.g., field_hospitality → also pelancongan).
  - W8: Institution modifiers + real proximity scoring — **separate sprint, 3 parts**: (1) Populate modifiers: zero institutions have modifiers today, but Institution model has lat/long, state, demographics — need a command to derive `urban` and `cultural_safety_net`. (2) Capture student location: add home state or lat/long to StudentProfile. (3) Real proximity scoring: `proximity_priority` quiz signal currently doesn't check actual distance — STPM pathway gives hardcoded +1, generic courses check `cultural_safety_net` (empty). Should calculate real distance from student to institution. Affects all SPM courses (±5 institution points completely inert) + makes proximity_priority meaningful.
  - ~~W11: STPM stream as free pre-quiz signal~~ — **DONE** (2026-03-19). Backend `StpmRankingView` derives RIASEC seed from `stpm_subjects` via `calculate_riasec_seed()` when no quiz signals present. Frontend sends `stpm_subjects` (subject keys from grade input). Science students now see I-type programmes ranked higher; arts students see A-type higher. Post-quiz signals take precedence (not overwritten). 7 tests added.
  - W14: Richer STPM sort tie-breaking — currently only score desc + name asc. Add university type/subcategory, min_cgpa competitiveness. SPM has 7-level hierarchy; STPM has 2. ~30 min fix.
  - W16: Audit STPM enrichment completeness — **RESOLVED**: production has 1,112/1,112 courses enriched (100%). Test fixtures don't have the data but production is fine. `efficacy_domain` is stored but not consumed by ranking formula — potential future enhancement.
  - W21: Add matric:sains and stpm:sains to TRACK_FIELD_MAP — science tracks missing from field preference mapping, so students interested in health/agriculture get no +3 bonus for the science pre-U track. Quick fix: add field_health, field_agriculture to both.
- Report: MASCO career data in prompt, institution/location context (low priority)
- Report: EN language selector in frontend
- STPM Pipeline: test scrapers against live MOHE
- Phone/OTP login (blocked — Twilio ~RM12/mo)
- Grade modulation layer
- Course detail page fixes from `docs/Course Detail Page.pdf`

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
