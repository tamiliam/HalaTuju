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
- `GEMINI_API_KEY` — Google Gemini API key for AI report generation (primary)
- `OPENAI_API_KEY` — OpenAI API key for report generation (fallback when all Gemini models fail)

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
| test_ranking.py | 73 | Fit score calculation, category/institution/global caps, merit penalty, sort tie-breaking, credential priority, ranked list output, API endpoint validation, field interest matching via field_key (primary/no match/cap/heavy_industry/no field_key/double match), W7 expanded mappings (nursing/dentistry→health, data science→digital, gen engineering→mechanical+heavy, comms→creative, physical science→agriculture, unmapped→no boost), high_stamina, rote_tolerant, quality_priority, work preference cap, pre-U scoring (Matric/STPM prestige, academic bonus, field preference, signal adjustment, signal cap, routing), W21 TRACK_FIELD_MAP science tracks (matric:sains→health, matric:sains→agriculture, stpm:sains→health) |
| test_data_loading.py | 10 | TVET metadata enrichment, PISMP metadata enrichment, institution modifiers storage, MASCO occupation model (PK, M2M, reverse relation, idempotent load, __str__) |
| test_institution_modifiers.py | 31 | W8 derive_institution_modifiers: urban classification (14: KL/Putrajaya/Penang always urban, city-in-address, city-in-name, case-insensitive, rural states), cultural safety net (13: 7 high states, 6 low states), command integration (3: dry run, apply, idempotent) |
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
| test_stpm_ranking.py | 63 | CGPA margin (5: base, bonus, cap, negative, partial), field match (9: primary +8, automotif via mekanikal, secondary +4, no match, empty, cross-domain +2, cap, law), RIASEC alignment (8: primary +6, secondary +3, no match, cross +2, cap, empty, no signals, tied seeds), efficacy (6: confirmed/confident/open/redirect/mismatch/none), goal alignment (7: professional+medicine, nonreg, postgrad+research, entrepreneurial+business, employment, no goal, no field), resilience (7: redirect+high/-3, redirect+moderate/-1, supported+high/-1, redirect+low/0, high resilience/0, no difficulty, no signals), interview (2), full integration (4: max/min score, no quiz, v1 compat), result framing (5: 3 modes, default, subtitle), ranked results (10: sort, empty, output, merit survives, quiz affects order, W14 uni tier tiebreak, competitiveness tiebreak, difficulty tiebreak, name tiebreak, score trumps tier) |
| test_stpm_quiz_engine.py | 56 | RIASEC seed calculation (all combos, PA excluded, unknown subjects), primary seed (single/tie/empty), branch routing (science/arts/mixed/ICT/MathM/PA), cross-stream detection, question generation (branch Q2, Q3 variants, Q5 filtering, trilingual, lang fallback), Q3/Q4 resolution (all fields, weak/strong grade threshold, interpolation), signal accumulation (RIASEC seed, field interest, field_key, efficacy, context, strength levels, arts branch, error handling) |
| test_stpm_quiz_data.py | 22 | Structure validation (required fields, no dupes), trilingual completeness (prompts, options, Q5, display names), signal taxonomy consistency (categories, no cross-category dupes, question signals in taxonomy), field key map, subject classification, grade points monotonicity |
| test_stpm_quiz_api.py | 24 | Questions endpoint (200, branch/seed, Q3 variants, Q5/trunk, validation, grades JSON, lang), resolve endpoint (200, Q3/Q4, validation), submit endpoint (200, signals, strength, branch, validation, arts branch) |
| test_eligibility_service.py | 19 | Service module: compute_student_merit (precomputed/grades/hist rename/default coq), compute_course_merit (standard/no cutoff/tvet/matric/stpm), deduplicate_pismp (passthrough/identical collapse/language merge), sort_eligible_courses (merit order/pismp/iljtm), compute_stats (source_type/pathway_type) |
| test_preu_courses.py | 4 | Pre-U eligibility (stats include matric/stpm), search (level Pra-U, text Matrikulasi, source_type matric) |
| test_nric_gate.py | 8 | NricGateMiddleware: anonymous pass-through, whitelisted endpoints (profile/claim-nric/sync/admin), blocks without NRIC, blocks without profile, allows with NRIC, public endpoints pass |
| test_nric_gate_integration.py | 10 | End-to-end NRIC gate: anonymous public access, anonymous blocked from saves, no-NRIC 403, with-NRIC pass-through, no-profile 403, whitelist (profile/claim-nric/sync), public endpoints open |
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

### UP_TVET Coverage Inventory (TVET gap analysis — no DB writes)

```bash
# 1. Scrape the public UP_TVET Perdana catalogue (~1000 programmes, ~50 pages)
python manage.py scrape_uptvet --output data/tvet/uptvet_latest.csv
#    (--max-pages N for a quick parser-validation spike)

# 2. Coverage report: total, Awam/Swasta split, by-institution, new-vs-already-held (ILJTM+ILKBS)
python manage.py audit_uptvet --csv data/tvet/uptvet_latest.csv
```

UP_TVET covers ~12 ministries / 685 institutions; we hold only ILJTM (ADTEC/JTM) + ILKBS (IKBN/IKTBN), ~83
courses. **No DB writes** — this is the decision-data step before a (golden-master-adjacent) TVET INGEST sprint.
Codes (`TVET/QP…`) don't match our synthetic `IJTM-*`/`IKBN-*` IDs, and the portal mixes Awam/Swasta — see
`docs/roadmap-course-data-pipeline.md` (UP_TVET track) + `docs/decisions.md`.
### Annual SPM Data Refresh (post-SPM `Course` catalogue — MOHE-coded subset only)

```bash
# 1. Scrape the SPM track (current year). Same scraper, --jenprog spm.
python manage.py scrape_mohe_stpm --jenprog spm --category A --output data/spm/mohe_2027.csv
#    (--max-pages N for a quick parser-validation spike; do NOT sync a --max-pages CSV)

# 2. Dry-run diff (report only — restricted to MOHE-coded UA/Asasi courses; synthetic-ID Poly/KK/TVET/PISMP excluded)
python manage.py sync_spm_mohe --csv data/spm/mohe_2027.csv

# 3. Apply (deactivate removed / reactivate returned / update merit; mass-deactivation guard; --force to override)
python manage.py sync_spm_mohe --csv data/spm/mohe_2027.csv --apply
```

**Scope:** `sync_spm_mohe` only touches courses whose `course_id` is a MOHE KOD PROGRAM (`^[A-Z]{2}[0-9]{7}$`, ~89
UA/Asasi). The ~300 synthetic-ID courses (`POLY-*`/`KKOM-*`/`TVET-*`/`50PD…`) are excluded (they need a name crosswalk —
roadmap Sprint 3b). New MOHE-coded courses are **reported, not auto-added** (requirements parsing = Sprint 3c). `is_active`
is set by the sync but **not yet read-filtered** anywhere. See `docs/roadmap-course-data-pipeline.md` + `docs/decisions.md`.

### Course Data dashboard (`/admin/course-data`, read-only reporting + health monitoring)

A read-only admin status surface: per-source **freshness** (e-Panduan STPM/SPM, UP_TVET, eMASCO), **coverage**
(have/available/gap, live from the DB), **link-health** + **audit** (last recorded run). Endpoint
`GET /api/v1/admin/course-data/` (`AdminCourseDataView`, any admin role). Freshness comes from `CourseDataStatus`
(`course_data_status` table) which the tools upsert on completion via `course_data_status.record_status(...)`:
`refresh_stpm`→`epanduan_stpm`, `validate_course_urls`→`link_health`, `audit_data`→`audit`. (The SPM `sync_spm_mohe` +
UP_TVET `scrape_uptvet`/`audit_uptvet` tools do NOT yet call `record_status` — until they do, the SPM/UP_TVET cards read
"never run"; wiring that is a one-line add per tool.)

**Health monitoring (READ-ONLY — no catalogue writes).** The dashboard's Link-health + Audit + freshness are kept
current by `course_data_check` = `audit_data` + `validate_course_urls --workers 40 --timeout 20 --retries 0`
(**no `--fix`/`--apply`/scrape**). It runs IN-REQUEST (cron + button), so it must fit the api's Cloud Run request
timeout — **raised 120s → 300s** for this (`gcloud run services update halatuju-api --timeout=300`). The bulk run uses
40 workers + `retries=0` so the slow MY-gov tail (20s/URL) stays well inside that budget; a per-URL retry would double
it. (The `--retries` default is 1 for manual/targeted runs.) Two ways to run it, both read-only:
- **Weekly cron** — `CronRunView` job `course-data-check` ← Cloud Scheduler `halatuju-course-data-check` (Mon 03:00 Asia/KL,
  `X-Cron-Secret`). POST needs a body (`-d '{}'`) or the LB returns 411.
- **Manual button** — `POST /api/v1/admin/course-data/check/` (`AdminCourseDataCheckView`, **super/admin only**) runs it
  synchronously and returns the refreshed payload; "Run health check now" on the page (~2 min).

`validate_course_urls` stores a `failures` list in its status (`{url, kind, institutions, refs}`) and splits results
into THREE severities so the dashboard doesn't cry wolf: **Broken** (`gone`/`dns`/`badurl` — actionable, the headline
count) · **Access-blocked** (`gated` = 401/403 — server up but refused this page: login wall OR wrong/old path like
Politeknik Port Dickson; eyeball) · **Couldn't verify** (`timeout`/`conn` — slow/blocked from Cloud Run, almost
certainly alive). SSL-cert-rejected-but-reachable sites are `insecure` (counted as alive). FIXING links (writes) is NOT
built into the check — owner inspects + corrects at source (done via audited MCP `UPDATE`s).

The browser catalogue scrapes (`refresh_stpm`, `scrape_uptvet`) stay manual/local (need Chromium) and only dry-run.
**UI-driven *updating* (apply-a-refresh) is deliberately NOT built** — owner wants reporting only.
Migration `0054_coursedatastatus` is the only schema for this surface (already on prod); the health-monitoring sprint
added NO migration.

### CRITICAL: Pre-Deploy Checklist

```bash
# 1. Run all tests (966 collected, 966 must pass, SPM golden master = 5319, STPM golden master = 2026)
python -m pytest apps/courses/tests/ apps/reports/tests/ -v

# 2. After any migration that creates/alters tables:
#    Run Supabase Security Advisor and fix all errors
#    (Dashboard → Advisors → Security Advisor → Rerun linter)
#    Or via MCP: get_advisors(project_id, type="security")

# 3. Every new table MUST have RLS enabled + policies
#    See docs/incident-001-rls-disabled.md for templates
```

966 tests must all pass (0 skipped, 0 failures). SPM golden master = 5319, STPM golden master = 2026. If golden master deviates, you broke eligibility logic.
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
| `apps/courses/management/commands/sync_spm_mohe.py` | SPM `Course` sync (MOHE-coded UA/Asasi subset; restriction + mass-deactivation guard) | No |
| `apps/courses/management/commands/validate_stpm_urls.py` | Dead link checker | No |
| `apps/courses/management/commands/scrape_uptvet.py` | UP_TVET catalogue scraper (mohon.tvet.gov.my → CSV; no DB writes) | No |
| `apps/courses/management/commands/audit_uptvet.py` | UP_TVET coverage inventory (Awam/Swasta split, new-vs-held; no DB writes) | No |
| `apps/courses/management/commands/audit_data.py` | Data completeness report (records dashboard `audit` status) | No |
| `apps/courses/management/commands/course_data_check.py` | READ-ONLY dashboard health check: audit + concurrent link reachability (no writes) | No |
| `apps/courses/course_data_status.py` | Course Data dashboard support: `record_status` + live `coverage_snapshot` | No |
| `apps/courses/management/commands/refresh_institution_urls.py` | Re-source institution URLs from authoritative index (matrikulasi/poly/kk); dry-run, --apply writes canonicalisations; run from a MY-capable network | No |
| `apps/courses/management/commands/generate_stpm_headlines.py` | Gemini-powered STPM headline generator | No |
| `apps/courses/management/commands/backfill_spm_field_key.py` | Deterministic SPM field_key classifier + backfill | No |
| `apps/courses/management/commands/classify_stpm_fields.py` | Deterministic STPM field_key classifier + backfill | No |
| `apps/courses/management/commands/enrich_stpm_riasec.py` | RIASEC type, difficulty, efficacy domain classifier for StpmCourse + FieldTaxonomy | No |
| `apps/courses/management/commands/derive_institution_modifiers.py` | Derive urban + cultural_safety_net modifiers from state/address | No |
| `apps/courses/insights_engine.py` | Deterministic insights from eligibility results | No |
| `apps/reports/report_engine.py` | Gemini-powered narrative report generator | No |
| `apps/reports/prompts.py` | SPM/STPM × BM/EN counselor report prompt templates | No |
| `apps/reports/views.py` | Report API endpoints (generate, detail, list) | No |

## Project Status

**v2.26.1 (2026-06-01) — Remove orphaned sponsor register-interest stack (TD-072b).** Full removal (Option B) of the
v2.16 sponsor lead-capture stack, orphaned since self-serve auth (E1c, v2.23.0; prod table had 0 rows): deleted the
`/sponsor/register-interest` page, `submitSponsorInterest` (api.ts), the `sponsorInterest.*` i18n block (en/ms/ta),
`SponsorInterestView` + `AdminSponsorInterestView` + their 2 routes, `SponsorInterestSerializer`, the `SponsorInterest`
model + `test_sponsor_interest.py`. **Kept** `emails.send_sponsor_interest_admin_email` — shared by the live
`SponsorRegisterView`. **Migration `0035_remove_sponsor_interest`** (DeleteModel) — destructive, applied **deploy-first**:
pushed code, then `DROP TABLE sponsor_interests` + recorded the migration row via Supabase MCP. 1446 pytest + 183 jest;
i18n parity 1662×3. Closes TD-072(b). See `docs/retrospective-v2.26.1-register-interest-removal.md`.

**v2.26.0 (2026-06-01) — Phase E Sprint E3a: sponsor wallet + match/consent (backend, NO real money).** On dummy
data, behind the pool flag; donations are **mocked** (no toyyibPay), disbursement + tranches are later gated slices,
money is a **ledger** not custody. **Wallet:** sponsor donates into myNADI (final, never a bank refund); balance =
donations − holding allocations (`sponsorship.py` `sponsor_balance`/`fund_student`/`respond_to_award`/`lapse_expired_offers`;
`Donation` + `Sponsorship` models). **Match (1:1 full-or-nothing, many-sponsor plumbing underneath):** admin sets
`ScholarshipApplication.award_amount` → sponsor funds in full → `offered` → student/**guardian** accepts → `active`,
app → new **`sponsored`** status, leaves the pool; decline/lapse → amount back to balance. DB partial-unique = one
holding sponsor per student. **Anonymity both ways, tested** (sponsor never sees student identity; student award view
has NO sponsor field; admin sees both). Endpoints: sponsor wallet/donate(mock)/fund/sponsorships/cancel; student
`scholarship/award/`; admin award-amount + `admin/sponsorships/`. **Migration `0034`** (additive `award_amount` + new
`sponsor_donations`+`sponsorships` tables + RLS, migrate-first via MCP, prod-verified). +17 tests; 1452 pytest + 183
jest. Deferred → TD-075 (toyyibPay + disbursement + tranches + lapse cron + partial funding). See
`docs/retrospective-v2.26-sponsorship-e3a.md`.

**v2.25.1 (2026-06-01) — Anon-profile pre-publish identifier scan (TD-074b).** Structural backstop on the generated
anonymous blurb: `pool.scan_anon_for_identifiers(text, profile)` scans for the student's own identifying tokens
(name/school distinctive tokens — generic SMK/Sekolah/… + bin/binti connectors stoplisted — city, NRIC, phone, email);
`AdminPublishAnonProfileView` **refuses to publish** on a leak (`400 anon_identifier_leak` + `fields`), admin must
regenerate. Three layers now guard the soft surface (prompt → admin review → publish-block); the allowlist card stays
the hard boundary. Closes one of the two pre-go-live pool gates (other = lawyer review). +7 tests; 1435 pytest + 183
jest. Backend only, no migration.

**v2.25.0 (2026-05-31) — Phase E Sprint E2b: anonymised pool FRONTEND (browse UI + admin anon controls).** Completes
E2 end-to-end, still behind `SPONSOR_POOL_ENABLED` (OFF → pool API 404s → `/sponsor` shows the "coming soon" shell; the
real UI appears only when flipped post-lawyer = **dark deploy**). Sponsor browse: `/sponsor` approved state → anonymised
cards grid (alias·state·field·academic·funding) or coming-soon on 404; new `/sponsor/pool/[id]` detail (summary + the
generated anon blurb via react-markdown + anonymity note). Admin `/admin/scholarship/[id]`: "Anonymous profile" card —
Generate (AI) → preview → Publish/Unpublish + badge (reviewer-gated). Client fns `getSponsorPool`/`getSponsorPoolDetail`
+ `generateAnonProfile`/`publishAnonProfile`. i18n parity 1675 (Tamil draft). No migration. 1428 pytest + 183 jest;
`next build` clean. See `docs/retrospective-v2.25-sponsor-pool-e2b.md`.

**v2.24.0 (2026-05-31) — Phase E Sprint E2a: anonymised sponsor discovery pool (backend, flag-gated).** The
PDPA-critical core, built behind `SPONSOR_POOL_ENABLED` (**default OFF** → browse endpoints 404) on **dummy data —
NOT live**. A sponsor never sees name/NRIC/address/phone/email/school. **Eligibility (consent = opt-in):** pooled iff
the **anonymous profile is published** AND an active `share_with_sponsors` consent exists (`pool.py`:
`is_pool_eligible`/`eligible_pool_queryset`/`pool_ref` alias/`academic_band`). **Generated (not scrubbed) anon profile:**
`profile_engine.generate_anonymous_profile` (separate prompt, non-identifying inputs only — no name/school/referees);
admin generate→review→publish (regenerate un-publishes). **Allowlist serializers = hard boundary:**
`SponsorPoolCardSerializer`/`SponsorPoolDetailSerializer` are plain `Serializer`s with explicit derived fields + zero
model passthrough; leak tests assert no identifier appears. Endpoints `GET /sponsor/pool/[/<id>/]` (flag + approved-
sponsor gated) + admin `…/anon-profile/generate/`+`/publish/` (reviewer-gated). **Migration `0033`** (additive `anon_*`
on `sponsor_profiles`, migrate-first, prod-verified). No frontend yet (E2b). 1428 pytest (+17) + 183 jest. See
`docs/retrospective-v2.24-sponsor-pool-e2a.md`.

**v2.23.2 (2026-05-31) — Logout isolation + student modal no longer overlays admin/sponsor.** Follow-up to v2.23.1:
the LOGOUT side is now isolated too. **(1)** `clearAll()` (student logout) was wiping **all** `halatuju_*` keys incl.
`halatuju_admin_session`/`halatuju_sponsor_session` → now preserves them; and all three `signOut()` switched to
**`scope: 'local'`** (default `global` revokes every session for the shared Google identity). So student/admin/sponsor
logouts no longer affect each other. **(2)** `AuthGateModal` (global in `Providers`) now route-guards via `usePathname`
and renders nothing on `/admin/*` + `/sponsor/*` (the visible half of TD-073). No migration/i18n. 1411 pytest + 183
jest; `next build` clean. See `docs/retrospective-v2.23.1-auth-isolation.md` (covers the auth-isolation arc).

**v2.23.1 (2026-05-31) — Auth session-isolation fix (PKCE) + sponsor/partner UX polish.** **Fixed a cross-scope
session leak:** Google login on the admin/sponsor console also created a Student session (implicit-flow `#access_token`
hash read by the globally-mounted student `AuthProvider`); admin logout didn't clear it. **All three Supabase clients
now use `flowType: 'pkce'`** (`getSupabase`/`getAdminSupabase`/`getSponsorSupabase`) so a non-initiating client can't
claim an OAuth session off the URL — closes the bleed (one Gmail = one Supabase identity, gated per-scope by role; the
risk was on shared computers). Polish: student modal → "Create Your Free **Student** Account"; phone fields →
"**Mobile number**" + `12-345 6789` placeholder + `formatMyMobile`/`isValidMyMobile` (node-tested) + inline email/mobile
validation (sponsor phone stored `+60 …`); red required `*`. `/admin/login` → "**Partner Login**" / "For partner
organisations and invited individuals" (badge "Partner"); footer "Admin" link removed. No migration. 1411 pytest + 183
jest; i18n parity 1652; `next build` clean. See `docs/retrospective-v2.23.1-auth-isolation.md`.

**v2.23.0 (2026-05-31) — Phase E Sprint E1c: sponsor self-serve auth (email/password + Google).** Live-feedback
follow-up to E1. **Dedicated `/sponsor/login`** (email/pw + Google + forgot, styled like `/admin/login`) + full
**`/sponsor/register`** (Full name as in NRIC/Passport, Email, Password w/ live rule checks, Re-enter, Phone +60,
Source, PDPA consent); Google sponsors hit a **"complete your details"** step (phone/source/consent). **Isolated
sponsor auth stack** — `sponsor-supabase.ts` (`storageKey 'halatuju_sponsor_session'`), `SponsorAuthProvider`,
`/sponsor/auth/callback` — mirrors the admin pattern and **supersedes E1's `KEY_SPONSOR_SIGNIN` student-client hack**
(reverted). **Backend:** `Sponsor` + `phone`/`source`/`consent_at`/`consent_version` (**migration `scholarship/0032`**,
additive, applied migrate-first via MCP); register requires name+phone+source+consent and completes incomplete rows;
`/sponsor/me` exposes `profile_complete`. Header: shared `components/AuthButtons.tsx` (Log in ▾ + Sign Up) used by
`AppHeader` **and the landing nav** (landing page otherwise unchanged); Sponsor menu → `/sponsor/login`, Sign-Up
chooser → `/sponsor/register`. Pure `lib/sponsorAuth.ts` node-tested. Deferred: Turnstile (TD-071), MY-only phone +
orphaned `/sponsor/register-interest` (TD-072). 1411 pytest + 178 jest; i18n parity 1650 (Tamil first-draft); `next
build` clean. **Not click-tested** (TD-070). See `docs/retrospective-v2.23-sponsor-auth.md`.

**v2.22.0 (2026-05-31) — Phase E Sprint E1: sponsor accounts + admin vetting (no student data).** First slice of
the safeguarded sponsor marketplace (`docs/scholarship/phase-e-sponsor-roadmap.md`). Self-register → admin vets →
approved sponsor lands in a portal shell. **Zero student data in this slice** (browsing arrives in E2, gated on
lawyer review). **Backend (E1a, `99c7937`):** `Sponsor` model (`supabase_user_id`-keyed, status
pending/approved/rejected/suspended; **migration `scholarship/0031`**, table `sponsors`, migrate-first + RLS
deny-by-default); `SponsorMixin` (mirrors `PartnerAdminMixin`); `POST /sponsor/register/` (idempotent, rejects anon,
emails admin) + `GET /sponsor/me/`; admin `GET /admin/sponsors/[?status]` + `POST /admin/sponsors/<id>/review/
{approve|reject|suspend}` (reviewer-gated); **allowlist `SponsorSerializer`**; NRIC-gate whitelists `/api/v1/sponsor/`.
**Frontend (E1b):** `/sponsor` portal (6 states off `getSponsorMe()`) + `/admin/sponsors` vetting table + nav link.
**Sponsor sign-in does a direct Google OAuth flagged by `KEY_SPONSOR_SIGNIN` (sessionStorage) → `/auth/callback`
routes to `/sponsor`, never touching the student NRIC modal.** No E1b migration. i18n `sponsorPortal.*` +
`admin.sponsors.*` (parity 1598; Tamil first-draft). 1408 pytest + 172 jest; `next build` clean. **Not yet
click-tested** (OAuth + admin flows — TD-070). See `docs/retrospective-v2.22-phase-e1-sponsor-portal.md`.

**v2.21.0 (2026-05-31) — SPM electives persist across logout/login + cap raised 2 → 7.** New
`StudentProfile.elective_subjects` JSONField (migration `0052`, on `api_student_profiles`) is the durable record of
which grade keys are electives (mirrors `stream_subjects`); synced in `/profile/sync/`, returned by the profile GET,
and re-hydrated on login (`auth-context` restores `KEY_ELEKTIF` + `KEY_ALIRAN`). Cap raised to 7 via `MAX_SPM_ELECTIVES`;
**merit engine unchanged** (Sec3 still scores best-2; golden master intact). Migrate-first hit + recovered the
`db_table='api_student_profiles'` trap (TD-025). No backfill (485/491 lack `stream_subjects`). STPM-flow electives
left for TD-069. 1396 pytest + 171 jest. See `docs/retrospective-v2.21-elective-persistence.md`.

**v2.20.0 (2026-05-31) — "Cikgu Gopal" document-help coach (student-facing, Documents tab).** A warm,
proactive helper appears beneath a document's amber/grey chip on /application explaining *why* the upload
mismatched and nudging a re-upload, in en/ms/ta. New `help_engine.py` (`generate_document_help` +
`verdict_for_document` + `_build_help_prompt`) reuses `profile_engine._call_gemini_text`; new
`DocumentHelpView` (`GET …/documents/<pk>/help/`, own-doc scoped, hourly per-application cache cap). **Coach,
never ghostwriter; structurally firewalled** — the engine receives only doc-type + already-decided verdict +
first name (no application/profile/score object; signature-asserted). Only *phrases* a verdict the
deterministic matchers/Vision already decided. Soft: AI off/throttled → FE shows pre-written i18n fallback
copy keyed by verdict (`scholarship.docs.help.fallback.*`). **No migration** (reads existing verdict columns).
FE: pure `lib/documentHelp.ts` (`shouldShowCoach`/`fallbackKeyFor`, node-env jest) + `DocumentHelpCoach.tsx`.
1391 pytest + 171 jest; i18n parity 1559 (Tamil first-draft). Stitch `daf30389` approved pre-build. See
`docs/retrospective-v2.20-cikgu-gopal-doc-help.md`. **On branch `feature/document-help-coach`; not yet
deployed (no migration; deploy = push, user-gated). Live click-through verify pending.**

**v2.19.0 (2026-05-31) — Four rejection buckets + differentiated decline emails.** Rejections are categorised
(`ScholarshipApplication.rejection_category`, migration `0029`): **merit**/**need**/**ineligible** set automatically
by the engine (it already recorded *why* — `evaluate()` now returns a `category`); **interview** (admin, reviewed-but-
not-selected, from shortlisted onward) and **contractual** (admin, post-award, accepted only) set via a reviewer-gated
`AdminRejectView` → `services.admin_reject()`. Each bucket sends its own suggestive trilingual decline email
(`emails.send_decline_email(category=…)`); generic covers ineligible+contractual. Admin UI: "Decline (after review)" +
"Decline (contractual)" buttons, a rejection-bucket badge, and the Review-&-actions panel hidden only for pre-shortlist
buckets. 1373 pytest + 163 jest. See `docs/retrospective-v2.19-rejection-buckets.md`.

**v2.18.0 (2026-05-31) — Phase D: Gemini v2 profile refine.** Second Gemini pass: an admin-on-demand "Refine with
interview findings (AI)" button takes the draft sponsor profile + the **submitted** `InterviewSession` (verdicts +
rationales + 1–5 rubric + overall note) → a refined **final profile (v2)** (`SponsorProfile.final_markdown`/
`final_model_used`/`finalised_at`, migration `0028`). Reviewer-gated (`AdminFinaliseProfileView`: 400 `no_draft`/
`no_interview`, 503 on engine error); **no Gemini in any GET**. The raw model call is now a shared `_call_gemini_text`
seam used by both the draft + refine functions. **Admin-facing only** — the sponsor consumer is gated on Phase E.
**This closes the post-shortlist "three buckets": profile-generation (draft+refine), document-reading (Vision+doc-assist),
interview-assist (deterministic+gap-spotter) are all functionally complete.** 1351 pytest + 163 jest. See
`docs/retrospective-v2.18-phase-d-profile-refine.md`.

**v2.17.0 (2026-05-31) — Gemini doc-assist + interview gap-spotter + consent-gating + supporting-doc OCR.**
Composite post-shortlist sprint that **completes the three-engine gap model** (deterministic + Vision + Gemini):
(1) consent is now a properly-gated final step (`consent_blockers` lists every unmet precondition; IC identity match);
(2) soft full-text Vision OCR name/address checks on supporting docs (migration `0025`); (3) **doc-assist** — Gemini
extracts supporting-doc fields on upload, deterministic matchers decide a soft verdict, the **student** self-corrects
at upload (migration `0026`); (4) **interview gap-spotter** (Phase B) — admin-on-demand Gemini reads the narrative →
3–6 `{code,question,why}` gaps beside the deterministic flags (migration `0027`). Plus: internal cron endpoint +
`ADMIN_NOTIFY_EMAIL` fix, Vision-outage alert, MyKad header-blocklist, guardianship-letter now optional, Step-4
live-refresh + un-confirm-on-incomplete. 1340 pytest + 163 jest. See `docs/retrospective-v2.17-gemini-doc-assist-gap-spotter.md`.

**v2.0 Released** (2026-03-20). Live at [halatuju.xyz](https://halatuju.xyz).
**B40 redesign (S7–S12a) DEPLOYED to prod 2026-05-25** (apply-form rebuild + deterministic decision engine + admin
verify-&-accept). **Decision-email scheduler NOW WIRED (2026-05-27)** — Cloud Run Job `release-decisions` + Cloud Scheduler `release-decisions-15m` (every 15 min) run `send_pending_decision_emails`; +2h/+48h reveal emails fire automatically (verified end-to-end). The old "wire before promoting" blocker is **cleared**; the programme is still not formally promoted but this gate is done.
**Apply-flow "Your Plans" redesign + post-launch polish DEPLOYED (v2.2.0–2.3.0, 2026-05-27):** context-aware Plans
step (P1–P5), then 8 post-launch fixes/additions from live new-user testing — `coq` round-trip, STPM eligibility
0-bug fix, STPM top-3 picker, Chrome autofill fix, NRIC prefill, rebuilt `/scholarship/application`, and a
truthfulness **declaration + typed-name signature** before submit (migration `scholarship 0011`). See
`docs/retrospective-post-launch-apply-polish.md`.

**S18 (v2.10.0, 2026-05-29) — SPM stream subject coverage** (core course-guide, off the B40 track): the apply-form
Arts stream dropdown went 9→38 subjects and Technical 8→16 to match the official SPM list (Islamic-stream subjects
excluded). `subjects.ts` subject model changed `category` (single) → `streams` (list) so a subject can sit in
multiple stream pools while staying electable; backend merit pools (`SCIENCE_POOL`/`ARTS_POOL`/`TECHNICAL_POOL` in
`engine.py`, now module-level) expanded to mirror it so the 30% stream weight recognises every selectable subject.
**No migration** (grades stored by key, not enum). Golden master unchanged (5319). FE/BE pool duplication is TD-063
(mitigated by linking comment + paired count tests). See `docs/retrospective-s18-stream-subject-coverage.md`.

**S19 (v2.11.0, 2026-05-29) — Minor consent flow hardening + UX iteration round** (composite, 6 commits): pre-S19
the minor branch trusted typed parent name + relationship unconditionally; this iteration closes the gap. Added
typed parent NRIC field (masked `XXXXXX-XX-XXXX`, stored in new `Consent.guardian_nric` column via migration
`scholarship/0021`); structured 7-option relationship dropdown (father/mother/legal_guardian/grandparent/brother/
sister/relative — older_sibling split + other_relative shortened); consent text body interpolates
`{student_name}` / `{student_nric}` / pronouns derived from the student's NRIC last digit (new `gender_from_nric`
helper); **hard-gate** name + NRIC match against `parent_ic` Vision OCR (was a soft anomaly flag in S17 — now blocks
consent POST with 400 `parent_ic_nric_mismatch` / `parent_ic_name_mismatch`); `CONSENT_VERSION` bump `2026-draft-2`
→ `2026-draft-3` (0 pre-existing consents on prod, forward-only). Plus four UX iterations driven by user feedback
through the session: layout cleanup (B40-language simpler text + student-directed blue info-box + amber warning
moved up); new `components/InfoBox.tsx` locking the 4-colour convention across /application (green=success,
blue=info, amber=warning, red=block); every step now opens with one instruction-led blue InfoBox where applicable;
**parent_ic now compulsory for EVERYONE** (not just minors) so admin can cross-check STR/EPF docs (typically
issued in a parent's name) against the parent's IC — `documents_done` extended to require all three, forward-only
(all 12 currently-submitted apps are pre-decision-reveal, no retroactive impact). DRAFT label removed from both
adult + minor consent branches (still a working model but the DRAFT banner no longer fits). Tests: **1236 backend
pytest** (+12) + **154 jest**. i18n parity 1369 (+12 net keys). Migration `0021` applied migrate-first via Supabase
MCP. 6 deploys (one per commit, all small). Tamil-pending queue now 10 batches / ~125+ strings — especially worth
a refine session before the lawyer meeting since the consent text IS the legal artefact being reviewed.
Retrospective `docs/retrospective-s19-minor-consent-v2-and-ux-iteration.md`. **3 design decisions logged**:
hard-gate vs soft-flag for parent_ic mismatch; InfoBox component as convention enforcement; parent_ic universal
compulsory.

**Post-shortlist sprint (v2.12.0–2.16.0, 2026-05-30) — Phase C + supporting work.** One session, 4 merges; see
`docs/retrospective-phase-c-sprint.md`. (1) **TD-063** (v2.13.0): merit engine trusts the student's explicit
stream/aliran pick — `prepare_merit_inputs(grades, stream_subjects=None)`; FE/BE stream pools become fallback-only
(S18 mis-score impossible for labelled data); new `StudentProfile.stream_subjects` (migration `courses/0049`).
(2) **TD-061 + TD-062** (v2.14.0): dropped 4 dead cols (`family_income`/`siblings`/`phone`/`siblings_studying`)
under expand-contract (`courses/0050` + `scholarship/0022`) — fixed a latent `/profile` household-income/size
silent-drop bug; `cleanup_orphan_blobs` mgmt command. (3) **Phase C** (v2.15.0, headline): post-shortlist funnel
`shortlisted → profile_complete → interviewing → interviewed → accepted`. Explicit "Confirm & submit"
(`confirm_profile`, stamps `profile_completed_at`, emails admin via `ADMIN_NOTIFY_EMAIL`); **hard accept-gate** on
incomplete profiles (no override) in `AdminVerifyAcceptView`; request-more-docs; `PartnerAdmin.role`
{super,reviewer,viewer} (kept alongside `is_super_admin`; `is_super` bridge + `has_role()`); `assigned_to` FK +
`?assigned=me|none|<id>`; new **`InterviewSession`** table (findings keyed to anomaly codes → `{verdict, rationale}`
+ 1–5 rubric) + capture UI extending the Pre-interview-flags card. **Completion is NOT a freeze** —
`POST_SHORTLIST_EDITABLE` keeps Step 4 + document upload open. Migrations `courses/0051` + `scholarship/0023`.
(4) **Branded entry + sponsor-interest** (v2.16.0): header "Log in" dropdown (Student/Sponsor/Partner) + "Sign Up" →
`/get-started` chooser; `/sponsor/register-interest` → public `SponsorInterest` lead capture
(`POST /api/v1/sponsor-interest/`, AllowAny, NRIC-gate-whitelisted) + admin email; admin list. **Browse-first
preserved** — NRIC gate behaviour unchanged. Migration `scholarship/0024`. **Out of scope (future): Phase D**
(Gemini v2 refines profile with interview findings), **Phase E** (real sponsor portal + auth), **Phase F** (mentor).

- 1452 backend tests, 183 frontend (jest) tests, 0 failures
- Golden masters: SPM=5319, STPM=2026
- CI/CD: Cloud Build continuous deployment from GitHub (push to `main` triggers deploy). **Triggers do NOT run
  `migrate`** — apply migrations to prod manually before pushing (see the DEPLOY/MIGRATIONS gotcha below).
- Custom domain: halatuju.xyz (Cloud Run domain mapping)

## Next Sprint (as of 2026-07-03)

**▶ NEXT — Code-health Sprint 5 (FINAL): infra & guardrails** (roadmap findings #21/#23 + P3
quick wins): a real CACHES backend so the upload/report rate limits actually limit (database
cache — free tier); validate_course_urls treats 5xx as retryable + mass-change guard; HSTS
header; QC queue "Awaiting QC" label; dead 'accepted' banner branch; resolution-items trailing
slash. Then the FINAL REPORT (incl. the reconciled quiz copy for owner review).

**✅ SHIPPED 2026-07-03 — Code-health Sprint 4 (income/STR consistency; branch
`feat/code-health-s4`; NO migration; retro `docs/retrospective-2026-07-03-code-health-s4.md`).**
Shared STR_RED_STATES/STR_COACH_STATES (coach now covers wrong_type/unreadable; blocker gains
wrong_type); I4 through income_headroom (gross ceiling honoured, boundary inclusive — a small
household under the gross ceiling no longer reads "over the line"); blank-tag docs attach to
the named earner only; profile uses effective_working_members; STR-route verdict picks the
member-tagged earner IC; a pending IC no longer blames the rel doc; fall-through counts all
evidenced members; declared-unproven forces amber over blue. 2,016 scholarship pytest.

**✅ SHIPPED 2026-07-03 — Code-health Sprint 3 (money & comms; branch `feat/code-health-s3`;
NO migration; retro `docs/retrospective-2026-07-03-code-health-s3.md`).** Contractual reject
auto-lapses the sponsorship (cancel reinstates, balance-guarded); award-offer email stamps only
on success; offer_emailed_at backfill VERIFIED on prod (18/18 stamped, no change);
sign-invitation command gated on BURSARY_AGREEMENT_ENABLED; bank-details save maps the
account-number field error + inline countDigits hint (en/ms/ta); **comprehension quiz
reconciled to AGREEMENT_CLAUSES** (dark; phantom-term guardrail test; ⚠ owner reviews the
copy — esp. Tamil — before the flag ever flips). 2,006 scholarship pytest + 412 jest.

**✅ SHIPPED 2026-07-03 — earlier the same day: OWNER CHECKPOINT passed after Code-health S1+S2** (roadmap
`docs/plans/2026-07-03-code-health-review.md`, findings #6-#11): sponsorship lapse on contractual
reject, award-email stamp only on success, `offer_emailed_at` backfill VERIFY (lessons.md says the
operational backfill was already done — check prod, don't re-blast), FE bank field-error mapping,
quiz↔agreement reconciliation (owner reviews copy before any flag flip), sign-invitation flag guard.
Owner pre-took the three S3 judgment calls on 2026-07-03 (see the roadmap's execution-authorisation
block). Then S4 income/STR consistency, S5 infra & guardrails.

**✅ SHIPPED 2026-07-03 — Code-health Sprint 2 (document-pipeline safety; branch
`feat/code-health-s2`; NO migration; retro `docs/retrospective-2026-07-03-code-health-s2.md`).**
Clobber guards on all three vision writers (a FAILED re-run can never wipe a stored good read —
the "local re-extract destroys vision_fields" incident mode is now impossible in code);
`reextract_documents` marks failures `'error'` + `--retry-errors` (never stamps them done);
cockpit Re-run passes the profile street (no more false address-mismatch flips); and
**one Vision call per upload instead of two** (`ocr_document_full` — text + word boxes + bytes from
a single read; digital PDFs keep the free text-layer path). 3,196 backend tests.

**✅ SHIPPED 2026-07-03 — Code-health Sprint 1 (decision & needs-gate integrity; branch
`feat/code-health-s1`; migration `0090` additive, applied migrate-first + verified; retro
`docs/retrospective-2026-07-03-code-health-s1.md`).** Three P1 findings from the 2026-07-03
full-codebase review: cancel-decline now truly reverses (own `decline_email_sent_at` stamp +
`pre_decline_status` snapshot restore — no more silent stay-rejected, no verdict-less cases into the
QC queue), YTD-alone payslips return None instead of YTD÷12 (up-to-12× income understatement → false
B40 green), and the 64-key subject-map drift vs `subjects.ts` is synced + pinned by
`test_subject_drift.py` (loud, never skips). 3,185 backend tests. **Same day: git history rewritten
(PII purge — `docs/backups` legacy dump removed via filter-repo; all pre-2026-07-03 commit SHAs after
2026-06-01 are dead — match old commits by subject line; `.gitignore` now blocks `**/docs/backups/` +
`*_backup_*.json`).**

**✅ DEPLOYED (was "awaiting deploy") — Sponsor visibility bound to the QC-Accept transition (2026-07-02; worktree
`.worktrees/mask-accepted`; NO migration; retro `docs/retrospective-2026-07-02-publish-at-qc.md`; decision in
`docs/decisions.md`).** The clean state-machine fix for "a student was shown to sponsors before QC cleared them."
- **Publish moved off the reviewer's verdict onto QC-Accept.** `AdminRecordVerdictView` finalise now only
  PREPARES the profile (`final_markdown`/`anon_markdown` + card blurb) and leaves it unpublished;
  `AdminQcDecisionView` accept calls the new **`pool.publish_profile_to_pool(app)`** (idempotent +
  PII-backstopped) — the SINGLE point a student becomes sponsor-visible (entering `recommended`).
- **Belt-and-suspenders read gate:** `pool.is_pool_eligible`, `pool.eligible_pool_queryset`, and
  `sponsorship.is_fundable` now hard-require `status == 'recommended'` — an awaiting-QC case can't leak or be
  funded even if a profile is (accidentally) published. Reopen/cancel-reopen unchanged.
- State machine: `Under review —[Reviewer Accept]→ Awaiting QC —[QC Accept ⇒ PUBLISH]→ Recommended —[Sponsor
  Support]→ Awarded`. No student-visible change (student view masks interviewed/recommended alike).
- 1960 scholarship pytest (net; +5 `TestPublishBoundToQc`, 1 reopen test updated); NO FE change (reviewer
  message stays accurate; pool is backend-gated); NO migration.
- **▶ DEPLOY (owner-gated): push `main` — code only, NO migrate-first, NO data backfill.** The 12 legacy
  awaiting-QC students still carry `anon_markdown`/`anon_blurb`/share-consent (verified), so when Suresh
  QC-Accepts each, `publish_profile_to_pool` re-publishes it automatically → back in the pool, one at a time
  (sponsors notified per acceptance, not a bulk blast). IDs: 20,21,33,35,51,53,62,72,75,76,95,104.

**▶ JUST SHIPPED — Senior `qc` role + BrightPath/HalaTuju nav split (2026-07-02, follow-up to the QC gate).**
`qc` is now a superset: assignable + reviews its assigned cases (like a view-all admin) AND QCs others — with
a **self-QC guard** (`_require_qc` → 403 `self_qc_forbidden`; cockpit hides the QC box when the qc is the
case's assigned reviewer). `services._can_review` + assignable list include `qc`. **Nav split:** `admin`+`qc`
are BrightPath roles → `Scholarship · Sponsors · Profile · Guide · FAQ` (dropped HalaTuju Dashboard/Students/
Course-Data, which only `super` keeps); BrightPath roles landing on `/admin` redirect to `/admin/scholarship`.
No migration. +5 pytest. **Owner follow-up:** flip Suresh to `role='qc'` when his review experience on #66 is
done (he's `admin` reviewing it now); one unified `partner` = HalaTuju org rep, a partner Scholarship view is
future **TD-155**.

**▶ JUST SHIPPED — QC gate (repurposed `interviewed` stage) (2026-07-02).** A quality-control step before
`recommended`, no new status. Findings-submit no longer advances status (stays `interviewing`); the
reviewer's verify-accept lands the case in `interviewed` = AWAITING QC. New **`qc` role** (or super) uses a
Quality Control box in the cockpit: **Accept** → `recommended`; **Reopen** → gaps note → back to reviewer
(`interviewing`, reopened banner) + reviewer emailed (`send_qc_returned_email`). `_require_qc` (super/qc,
read-all/QC-write-only); endpoint `POST …/qc-decision/`. Reuses `reopen_decision`/`DecisionReopen`; reopen
mapping now two-step invertible (`recommended↔interviewed`, `interviewed↔interviewing`). Choices-only
migrations (courses 0060, scholarship 0088 — **no DDL**). Retro `docs/retrospective-2026-07-02-qc-gate.md`.
- **Immediate follow-up (owner-gated):** grant the owner (or a dedicated account) the **`qc` role** —
  `UPDATE partner_admins SET role='qc' WHERE email='<qc person>'` (invite-UI button deferred). Then
  smoke-test: reviewer submits verdict → `interviewed` → QC Reopen (email + back to `interviewing`) →
  reviewer redoes → QC Accept → `recommended`.

**▶ JUST SHIPPED — Income model, Part 2 COMPLETE (2A + 2B + 2C, 2026-07-02; worktree `.worktrees/str-salary`;
commits `630c5528`/`c1aef662` 2A, `62816882` 2B, `3a45f850` 2C; migrations `0086_income_declared` +
`0087_income_nonearning`, both additive/migrate-first; retro
`docs/retrospective-2026-07-02-income-model-part2.md`).** The B40 income assessment now goes beyond parents'
payslips, all through the single seam `income_engine.earner_monthly_income → income_per_capita →
income_headroom`, and **never gates** (soft signals + Action-Centre requests; officer decides):
- **2A declared informal income** — a working member with no payslip may declare a wage; counts only with a
  valid STR (means-test) OR a supporting `income_support_doc` (flexible: employer/wage letter, bank statements,
  or a community/penghulu letter), else Unsure. Wizard field behind a "can't get a payslip?" opt-in.
- **2B unemployment detail** — for an `unemployed` roster member: why + since-when (`income_nonearning`) +
  soft EPF corroboration (employer all-zeros, or lapsed `last_contribution`). Roster sub-panel, Stitch-approved.
- **2C household completeness** — income-proof requests generalised to EVERY working roster member
  (`household_status_gaps`, not just parents); soft reviewer `household_size_confirm` when described people
  outnumber the stated household size (over-count direction only). D4 confirmed already-safe (guard test).
- 1943 scholarship pytest + 404 jest; i18n en/ms/ta. **▶ NEXT (owner): the salary/pension RE-RUN** (S2
  `gross_income_ytd` annualisation + pension-as-income only populate on re-extraction via the cockpit Re-run;
  the STR-currency + these income-model bands recompute live). Then the full salary-track redesign (per-member
  aggregation, GREEN via a corroborated family roster) — a larger separate spec.
- **QC-gate note:** `next build` type-check OOMs on the 8 GB dev box after a full pytest run (WorkerError
  after "Compiled successfully") — it's memory, not code; verify types with `npx tsc --noEmit --target
  es2018 --downlevelIteration` and trust Cloud Build.

**▶ JUST SHIPPED — Assignment-based review permission (2026-07-02).** View (role) and act (assignment)
are now decoupled: a `role='admin'` sees all read-only AND can WRITE only on applications assigned to
them; reviewer=assigned-only; super=any; partner=none. A view-all admin is now an assignable target.
One shared gate `_AdminBase._can_review_app`/`_require_app_write` (25 endpoints + 2 special). FE cockpit
`canWrite = super || assigned-to-me` (role endpoint returns `admin_id`). Partner nav lost Guide/FAQ.
No migration. Retro `docs/retrospective-2026-07-02-assignment-write-permission.md`.
- **Immediate follow-up (owner-gated):** enable **Suresh** as a selective reviewer — he stays `role='admin'`
  (no change); the super-admin just **assigns him the chosen students** and edit controls appear on those.
  Assign only students he does **not** fund (conflict-of-interest guard). Optional: give him a
  `reviewer_profile` if he'll conduct interviews (language matching / interviewer email).
- **TD-153** logged — partner-role least-privilege tidy-ups (UI delete button + API-readable oversight lists).

**▶ POST-AWARD CONTRACT-SIGNING FLOW — COMPLETE & MERGED to `feat/award-comprehension` 2026-07-01,
DARK behind `BURSARY_AGREEMENT_ENABLED` (5 sprints; commits `013effe3`→`f7cc7300`; migrations
`0083`/`0084`/`0085` ALL ADDITIVE — apply migrate-first at go-live; retro
`docs/retrospective-2026-07-01-post-award-signing.md`; go-live `docs/scholarship/bursary-go-live-playbook.md`).**
- The wiring from the "ready to sign" email → Action Centre → **comprehension quiz** ("Understand", 8
  checkpoints, `comprehension_passed_at`) → **signing**. The guarantor signature is gated on an **SMS PIN
  to the parent's pre-declared LOCKED phone** (`profile.guardians`; `guarantor_phone`/`_verified_at` +
  freshness TTL; Twilio Verify; `sign_agreement` raises `guarantor_phone_missing`/`_unverified`).
- **Notify-and-sign chain** (`bursary.notify_after_guarantor_signed` / `record_witness` /
  `countersign_foundation`): partner witness (if referring org w/ contact email) → else Foundation
  directly (graceful) → executed (`awarded`→`active`) → student "in effect" email. `foundation_notify_emails()`
  = `FOUNDATION_NOTIFY_EMAIL` → super admins → `ADMIN_NOTIFY_EMAIL`. Daily SLA cron
  `bursary-signing-reminders` (`BURSARY_SIGN_REMINDER_DAYS`). Owner-sent "ready to sign" =
  `send_sign_invitation_emails` (scope `SIGN_INVITE_APP_IDS`). Panel gated away from the portal until executed.
- **TD-144 RESOLVED** — `AdminApplicationDetailSerializer.bursary_agreement` surfaces the real agreement;
  cockpit ticks are accurate; buttons disabled until an agreement exists.
- **Local E2E driver** `python manage.py bursary_e2e` (`--no-org`/`--keep`) walks the whole chain with all
  seams mocked. In-house e-signature only (no third-party); donor never named. **Go-live owner-gated on
  Phase-0** (lawyer-vet template + Foundation entity); see the playbook + `bursary-signer-provisioning.md`.
- **▶ NEXT:** owner tests in prod (migrate-first `0083`/`0084`/`0085` → deploy → flip `BURSARY_AGREEMENT_ENABLED`
  + send `SIGN_INVITE_APP_IDS`). The local browser walkthrough was skipped (owner will test in prod).

**▶ STR-PROOF MODEL — Sprint 4 (Check-2 case summary) SHIPPED DARK 2026-07-01 (worktree `.worktrees/str-salary`;
`verdict_narrative.py` + `AdminVerdictSummaryView` (`GET …/verdict-summary/`) + FE lead paragraph; NO migration;
dark behind `VERDICT_CASE_SUMMARY_ENABLED`).**
- An **LLM briefing that "talks to the reviewer"** above the verdict checklist: for a non-Certain verdict it
  narrates the *already-decided* verdict as a 2–4 sentence case (verdict + decisive reason → threaded reasoning
  → why THIS band not the next up → action) in the firm fiscal-steward voice. The LLM only narrates the
  deterministic band + glossed items (`_CODE_GLOSS`); forbidden to invent/change the band. Bullets stay as the
  audit trail. Income framed **gross → per-capita** (never take-home); earner "confirmed as the student's parent".
- **Grounded + cached** per (application, verdict-signature) via Django LocMemCache (runs at verdict-time, not
  per-open); fetched **lazily** by the FE so the detail GET never blocks on Gemini. Band label is a Python port
  of `officerCockpit.factTileTone` (keep in step). Reuses `profile_engine._call_gemini_text` (flash cascade).
  +14 pytest (Gemini mocked). Also bundled: the "take-home"→gross/per-capita income copy fix (en/ms/ta).
- **▶ NEXT (owner):** flip `VERDICT_CASE_SUMMARY_ENABLED=1` in Cloud Run (`halatuju-api`) to live-validate the
  voice on #102/#83/#14/#13, then keep it on. Retro to follow after validation. Watch Gemini cost (cached, flash).

**▶ STR-PROOF MODEL — Sprint 3 (officer-review refinement) SHIPPED 2026-07-01 (worktree `.worktrees/str-salary`;
commits `9a349001` ICU-copy fix + `d82de368` Status chip/finding-first + `067dd008` payment guard/band
matrix/Current chip + `a1ca9ade` prescriptive firm-steward copy; NO migration; `MODEL_VERSION` 1.2 → 1.2.1;
spec `docs/scholarship/str-proof-spec.md` §2–§8; retro `docs/retrospective-2026-07-01-str-proof-model-s3.md`).**
- **Payment guard** (`income_engine._str_currency`, new `amount_raw` param): "Lulus" is PRIMARY approval; a
  positive PAID amount ("Jumlah Telah Dibayar") is an ADDITIVE rescue for a misread status (the #23 "STR"-label
  leak). Zero/absent never downgrades; Ditolak/non-STR still win. **`current_status` is computed on read → the
  whole #23 class self-corrects on deploy, NO re-run.**
- **STR band matrix** (`verdict_engine._verdict_income`): Lulus+dated→Certain, Lulus+no-date→Probable,
  stale/unreadable→**Unsure** (`recommend`, not a blue read off earner-IC greens), Ditolak/non-STR→salary route
  (over-B40→**Fail/gap/RED**, no-salary→Unsure). **Revises S2 "over-B40 → amber, don't auto-reject" → red
  income fact** (advisory; officer still decides; interview override stays).
- **Officer chips split** (`officerCockpit`): Status (approval: `strStatusFactStatus`) + Current (date-only:
  `strCurrencyFactStatus`, dateless/n-a → grey "we don't know"). Recipient·IC·**Status**·Current; verdict detail
  leads with the finding. Fixed the S1 raw-ICU copy (custom `t` has NO ICU engine → flat per-status keys +
  `verdictItemKey`; guardrail `no-icu-messageformat.test.ts`).
- **Prescriptive, firm-steward Check-2 copy** (en/ms/ta): every officer line = a lean + an action, never "can't
  tell"; "Unsure" = "proof required from the student" (auto-raised 5-day Action-Centre query;
  `CHECK2_STUDENT_QUERIES_ENABLED`/`CHECK2_AUTO_GENERATE` both ON in prod). **Two personas:** Cikgu Gopal
  (Check 1, `help_engine.py`) kind/tolerant for the student — UNTOUCHED; Check 2 firm donor-steward for the officer.
- 1864 pytest + 403 jest green; 4 deploys (3× web, 1× api); web `…00523`, api `…00601`+.
- **▶ NEXT:** owner's **salary/pension re-run** (the S2 `gross_income_ytd` annualisation + pension fields need
  re-extraction — STR-currency fixes incl. #23 do NOT). Then the full salary-track redesign (below).

**▶ STR-PROOF MODEL — Sprint 2 (salary spillover) SHIPPED 2026-07-01 (worktree `.worktrees/str-salary`;
commits `97b59918` income core + `7a7586e7` verdict/extraction/FE; NO migration; spec
`docs/scholarship/str-proof-spec.md` §6/§7; retro `docs/retrospective-2026-07-01-str-proof-model-s2.md`).**
- **Evidence-driven route fall-through:** `verdict_engine._verdict_income` — a `wrong_type`/`rejected` STR
  no longer freezes the income fact; it assesses the salary/benefit docs on file via the new
  **`income_engine.income_headroom`** band. unsure/over → `recommend` (amber — deliberately NOT a blue read
  off the verified earner-IC greens); probable → `review` + a green `income_salary_probable` (→ blue).
  **#13 (payslip-in-STR-slot) → Unsure; SARA/PERKESO → Probable.**
- **Headroom** = `max(gross_ceiling, per_capita_ceiling×size) − household income`; thin breach-room (< one
  per-capita head) or an unread earner → Unsure; large → Probable. Roster-independent; GREEN for the salary
  route stays reserved for a corroborated household (the family roster, later).
- **Annualised pay incl. O/T** (`gross_income_ytd ÷ 12`; #13 RM3,800 → ~RM7,064) + **pension/benefit as
  income** (PERKESO survivor's pension), via the salary_slip extraction + reader.
- 1836 pytest; jest 394 + build clean. **▶ Takes effect on RE-RUN:** the annualisation + pension reads only
  populate on re-extraction — the owner is doing **one combined re-run pass** (the 6 S1 label-leak docs +
  the salary/pension docs) post-S2 (`memory/halatuju.md`). The headroom band itself recomputes live on deploy.
- **▶ NEXT:** the full **salary-track redesign** (per-member aggregation, GREEN via a corroborated family
  roster) is a larger separate spec; the parked family-roster branch is its enabler.

**▶ STR-PROOF MODEL — Sprint 1 SHIPPED 2026-06-30 (worktree `.worktrees/str-model`; commits
`8b4686b1` backend + `0f1e09ba` web; `MODEL_VERSION` 1.1 → 1.2; NO migration; spec
`docs/scholarship/str-proof-spec.md`; retro `docs/retrospective-2026-06-30-str-proof-model-s1.md`).**
- **`income_engine._str_currency` → structured states** `wrong_type / rejected / unreadable / stale /
  unconfirmed / current` (was: everything collapsed to `unconfirmed`). **Format gate first:** a non-STR
  in the STR slot (`source_type='unknown'`: SALINAN / SARA / payslip) → `wrong_type` (RED), never
  softened. A **dateless approved STR → `unconfirmed` (BLUE)**, no longer `current` (GREEN) — a year-old
  screenshot also reads "Lulus", so undated can't confirm the cycle.
- **verdict_engine:** the `str_not_current` item carries the state; the **`document_not_genuine` caveat
  is suppressed for `wrong_type`** (`_str_wrong_type` — a genuine payslip is the wrong KIND, not a
  forgery). **FE:** officer verdict line is an **ICU `select`** (one decisive sentence per state, EN/BM/TA);
  STR doc-chip green/amber/red via `strCurrencyFactStatus`.
- **vision.py extraction:** read the status VALUE not the "Status Permohonan STR" label (#112); dates only
  from letter/Maklumat-Pembayaran (never the FAQ-nav "2026"); sharper dashboard-vs-semakan signatures.
- Profile honesty: claim STR only on a confirmed-**current** (dated) STR. 1827 pytest; jest 395 + build clean.
- **▶ ON DEPLOY:** the demotion re-bands existing dateless-approved STR income verdicts Certain→Probable
  (visible to reviewers — intended). **Then RE-RUN the ~25 existing STR docs on the LIVE service** (cockpit
  Re-run) so the extraction fixes (status-value, dates, classify) land — re-extraction must NOT run locally
  (no Storage → corrupts `vision_fields`; see `memory/halatuju_never_reextract_locally.md`).
- **▶ NEXT — Sprint 2 (the salary spillover):** evidence-driven **route fall-through** (a wrong_type/rejected
  STR → assess the salary docs on file, don't freeze); **pension/benefit counts as income**; **annualised
  income incl. O/T**; the **headroom-graded** household-corroboration rule (#13 → Unsure vs SARA → Probable).
  The full salary-track redesign is a larger separate spec.

**▶ SHIPPED & LIVE 2026-06-29 — Bursary data-quality sprint (worktree `.worktrees/data-quality`; 12
commits `b16b5ecd`→`965b1b23`; NO migration; retro `docs/retrospective-2026-06-29-bursary-data-quality.md`).**
- **Verdict-aware recommended amount:** `award.proposed_award_amount` → `None` (no amount) on a confident
  disqualifier (`offer_not_official` / `income_above_b40_line`); cockpit shows a "no amount + reason" state,
  super-overridable, self-correcting. **Continuing-STPM = RM1,000** (offer reporting year < cohort year →
  one year left); fresh STPM stays RM3,000.
- **Pre-U standardisation, AUTOMATIC in `autofill_pathway_from_offer` (idempotent):** track → canonical
  vocab (Matrikulasi 4 / STPM 2); course name → "Program Matrikulasi" / "Tingkatan Enam"; institution →
  matric catalogue college (STPM = casing-only). **Institution single-source-of-truth = the recommender
  catalogue** (`offer_pathway.catalogue_institution`, UNIQUE-match, never swaps a conflicting institution).
  `normalise_institution_names` (courses cmd) expanded matric (`KM`→`Kolej Matrikulasi`) + fixed mis-cased
  acronyms (21 catalogue rows).
- **Reporting-date persist fix** (was gated behind the locked early-return). New backfill commands:
  `backfill_pre_u_track`, `standardise_pre_u_course`, `align_institution_to_catalogue`,
  `standardise_stpm_institution`. ~100 prod rows standardised (all dry-run verified).
- **GOTCHA (lesson):** NEVER re-extract documents from a local checkout (no Storage access → reads
  "no text" → destroys `vision_fields`); use the cockpit "Re-run" / live service. See `docs/lessons.md`.
- **▶ NEXT:** TD-150 (course matcher assigns wrong public `course_id` — poly-IT synthetic majors; #95 on a
  placeholder Ungku Omar IT course pending real specialisation). STPM-school casing is intentionally
  casing-only (not catalogue-matched). #16 is a test account.

**▶ DOC-RECOGNITION LAYER 2 (cross-document matching) — L2-1 SHIPPED + LIVE 2026-06-29** (commits
`c1fa3066` extraction robustness + `63a56a61` chain/chips; `halatuju-api-00548` + `halatuju-web-00502`;
no migration). The **IC NUMBER is the cross-document join key**: `income_engine.chain_verified_earner`
confirms an earner when a Layer-1-genuine BC (child = student) carries a parent IC number matching the
income proof's NRIC (STR/salary/EPF) — exact, or one-digit OCR drift WITH name corroboration — so the
mother is verified EVEN when the wrong card sits in her slot or it's absent (#9). It only ever demotes a
red to a verified green (never asserts a mismatch); a positively-suspect BC can't anchor it; the one hard
block survives (proof name AND number both contradict, no corroboration). Wired in lockstep across the
four checks (`student_income_ic_check`/`_proof_check`/`_str_check`/`_bc_check`), `resolution.doc_match_verdict`,
and both `verdict_engine` income paths. Cockpit: EPF/salary chips show IC No; parent-IC chip shows a soft
amber "Wrong card" caveat. Verified on cached eval: #9 all-green, #5 stays red. Retro
`docs/retrospective-2026-06-29-l2-ic-number-chain.md`. **NEXT (L2-2, not yet planned):** the remaining
Layer-2 issues + reconcile the stale eval-corpus labels (move str_a9/a23 → fixtures, a5 → counter_examples)
+ re-capture the a10/a86 BC snapshots (Item-B extraction fix is live, so they clear on real re-upload).

**▶ POST-AWARD STUDENT LIFECYCLE — multi-sprint roadmap `docs/scholarship/post-award-lifecycle-plan.md`
(approved 2026-06-28). Target state machine: `recommended → awarded → active → maintenance → closed`
(+ `closure_reason`; maintenance sub-states on_track/probation/on_hold/ready-to-close; signing order
student→guarantor→witness→Foundation under `BURSARY_AGREEMENT_ENABLED`).**
- **S1 SHIPPED + LIVE 2026-06-28** (commits `76a7ae06` mask + `6a9ddc58` rename; migration `0073`
  STATE-ONLY, recorded on prod; 23 rows migrated `accepted`→`recommended`, verified 0/23). Renamed the
  application status `accepted` → `recommended` via **expand-contract**: `recommended` is canonical,
  legacy `accepted` is **still TOLERATED** in `models` STATUS_CHOICES, `serializers` mask, `services`
  (admin_reject gate + QUERYING_LOCKED), `family.DECIDED_STATUSES`, `send_review_nudges._TERMINAL`,
  `reopen`, and the web admin status maps/`officerCockpit.QUERYING_LOCKED_STATES`. Student-masking folded
  in (now masks `recommended`). Retro `docs/retrospective-2026-06-28-post-award-s1-rename.md`.
- **S2 SHIPPED 2026-06-28** (migration `0074`: additive `closure_reason` column **migrate-first** + status
  choices state-only). Added `awarded`/`active`/`maintenance`/`closed` + `closure_reason`; dropped the
  `accepted` alias; re-gated the pool (`pool.IN_PROGRAMME_OR_BEYOND` — a student leaves the discovery pool at
  funder-commit), the in-programme gate + progress band (`pool.FUNDED_STATES` = active/maintenance/sponsored).
  `sponsored` kept VALID until S3 (TD-146). Retro `docs/retrospective-2026-06-28-post-award-s2-statuses.md`.
- **S3 SHIPPED 2026-06-28** (migration `0075`, status choices state-only). `fund_student → awarded`;
  `awarded → active` via the dual path (flag-OFF: acceptance + #14 cool-off `_finalise_award`; flag-ON:
  Foundation counter-sign `bursary._maybe_activate`, witness NON-BLOCKING); declined/held/expired offer
  reverts `awarded → recommended` (`_revert_to_pool`). **`sponsored` retired** (TD-146) from choices + all
  status sets + onboarding/finalising gates + admin maps + i18n (0 prod rows). Retro
  `docs/retrospective-2026-06-28-post-award-s3-awarded-signing.md`.
- **S4 SHIPPED 2026-06-28** (migration `0076_disbursement`: CreateModel + RLS, **migrate-first**). New
  `Disbursement` model (table `disbursements`; `scheduled → due → released | withheld | returned`; FK
  application + nullable FK sponsorship). `disbursement.py` core: `schedule_tranche`/`release_tranche`/
  `withhold_tranche`/`return_tranche`/`mark_due`; **the first `released` tranche flips the app `active →
  maintenance`** (`_flip_to_maintenance`, idempotent). Reviewer-gated admin endpoints
  (`POST …/applications/<pk>/disbursements/` + `POST …/disbursements/<pk>/<action>/`); cockpit panel
  (funded-state gated) + `lib/disbursement.ts` + `admin.disbursement.*` i18n. Mock ledger (real toyyibPay
  = TD-075). Retro `docs/retrospective-2026-06-28-post-award-s4-disbursement.md`.
- **S5 SHIPPED 2026-06-28** (migration `0077_maintenance_substate`: additive column, **migrate-first**).
  `ScholarshipApplication.maintenance_substate` (on_track/probation/on_hold/ready_to_close, default
  on_track) — an admin operational overlay within `maintenance`, distinct from the sponsor-facing academic
  band (`pool.derive_progress_state`). `maintenance.py` core (`set_substate` + `is_on_hold` +
  `sponsor_support_status` + `ready_to_close_queryset`). **`on_hold` blocks `disbursement.release_tranche`**
  (`DisbursementError('on_hold')`; withhold/return still allowed). Reviewer-gated `POST …/applications/<pk>/
  maintenance/ {substate}`. Surfaces: cockpit (badge + transitions in the disbursement panel), student
  in-programme ("support paused" banner), sponsor card (coarse `support_status` paused/completing —
  probation hidden). i18n `admin.maintenance.*` + `scholarship.inProgramme.onHold.*` +
  `sponsorPortal.myStudents.support.*`. Retro `docs/retrospective-2026-06-28-post-award-s5-maintenance.md`.
- **S6 SHIPPED 2026-06-28 — FINAL sprint; the post-award lifecycle is COMPLETE** (migration
  `0078_closure_stamp`: additive `closed_at`/`closed_by`, **migrate-first**). Manual CLOSE via
  `closure.close_application` (gated active/maintenance) → `status='closed'` + `closure_reason` +
  audit stamp; terminal. `disbursement.release_tranche` now also requires a funded state (a closed
  file's leftover tranche is un-releasable). Thank-you relay re-gated: `in_programme.submit_graduation_message`
  uses `_require_can_thank` (active/maintenance/**closed**) so a graduated student can still write
  post-closure (results/promo stay funded-only). Surfaces: cockpit closure panel (reason + offboarding
  checklist + closed summary), student in-programme closed banner (graduated/completed/neutral) with the
  thank-you kept open. Reviewer-gated `POST …/applications/<pk>/close/`. i18n `admin.closure.*` +
  `scholarship.inProgramme.closed.*`. Retro `docs/retrospective-2026-06-28-post-award-s6-closure.md`.
- **▶ POST-AWARD LIFECYCLE COMPLETE (S1–S6, all LIVE + dark).** `recommended → awarded → active →
  maintenance → closed` end-to-end. **Go-live still gated** on bursary Phase-0 (TD-140) + real disbursement
  / toyyibPay (TD-075). **TD-147 DONE** (`f8094760` — migration `0079_alter_scholarshipcohort_name`
  retired the recurring `scholarshipcohort.name` drift; `makemigrations scholarship --check` is now clean).
  **NEXT engineering = doc-recognition Layer 2 (L2-2)** — see the top of this section.
- **▶ POST-AWARD S7 SHIPPED 2026-06-29 — bank-details capture (retro
  `docs/retrospective-2026-06-29-post-award-s7-bank-details.md`; migration `0081_bankaccount` applied
  migrate-first + RLS).** An `awarded`/`active` student gets a `bank_details_missing` task in the Action
  Centre: upload a bank statement → Gemini field-extracts (bank/account-no/holder) → the student
  confirms/corrects → save. **Holder MUST be the student** (hard gate, `vision.name_match`, server-side);
  mismatch/unclear → Cikgu Gopal coaches (`bank_holder_mismatch`/`bank_details_unclear`). New `BankAccount`
  model (`bank_accounts`, OneToOne, RLS) + `bank_statement` doc type; `GET/POST /scholarship/bank-account/`;
  `resolution.sync_bank_details_item`; upload-THEN-confirm (never auto-resolves). `_current_application`
  broadened to the funded states so the funded student reaches the upload/Action-Centre surface (safe —
  revert-on-incomplete only acts on `profile_complete`). **Stored only — no admin/officer view yet** (the
  payout view is later, with TD-075). FE `BankDetailsTask` in `ActionCentre.tsx`. **SHIPPED + LIVE** (table on
  prod via migrate-first; verified live on #16). Deferred: TD-148 (officer payout/verify view), TD-149
  (replacing a confirmed account post-save).

- **▶ POST-AWARD S7 follow-up SHIPPED + LIVE 2026-06-29 — award-panel embargo + funded Action-Centre copy +
  email sign-off bold (commit `6d968975`; NO migration; retro
  `docs/retrospective-2026-06-29-award-panel-embargo-funded-copy.md`).** Live-testing the awarded flow on #16:
  (1) the 🎉 "View my award / one more step" panel on `/scholarship/application` is now **embargoed behind
  `AWARD_ACCEPTANCE_ENABLED` (default OFF)** — it leads to the accept→onboarding flow which isn't tested
  end-to-end; exposed on the student award payload as `acceptance_enabled`, FE gates `awardPanel()` on it.
  **Re-enable with `AWARD_ACCEPTANCE_ENABLED=1` on `halatuju-api` — env var only, no deploy** (the owner will
  instead invite awarded students into onboarding by a later email). NB: flipping it un-hides the panel for ALL
  funded students at once — test onboarding end-to-end first. (2) The funded Action-Centre header was reworded
  to the warm bank-invitation tone (new `funded` prop on `ActionCentre` + `fundedTitle`/`fundedIntro`, en/ms/ta),
  replacing the review-phase "we're reviewing your application" copy. (3) The sign-off team name ("The BrightPath
  Bursary Team") is now bolded in the rendered HTML of the branded card emails — in both `_decline_html` (declines)
  and `_award_offer_html` (the award/bank email has its own builder as of `4e44962b`; the team-name bold there is
  additive to the owner's bank-phrase bold + Action-Centre button). Plain-text unchanged. 41 scholarship pytest +
  next build clean + i18n parity 3012×3.

**▶ LIVE FEATURE-FLAG STATE (prod `halatuju-api`, verified 2026-06-21 — env is the source of truth, not these notes).**
ON: `WHATSAPP_ENABLED`, `INTERVIEW_SCHEDULING_ENABLED`, `INTERVIEW_MEET_ENABLED`, `REVIEW_NUDGES_ENABLED`,
`CHECK2_STUDENT_QUERIES_ENABLED`, `CHECK2_AUTO_GENERATE`, **`CHECK2_ANSWER_RELEVANCE_ENABLED` (turned ON 2026-06-21)**,
**`STUDENT_ASSIGNMENT_EMAIL_ENABLED` (ON — students DO get the "interview is next, times to follow" email on assignment)**,
`DOC_GENUINENESS_CHECK_ENABLED`, `SPONSOR_POOL_ENABLED`, `IC_GEMINI_FALLBACK_ENABLED`,
**`PROFILE_COMPLETE_EMAIL_ENABLED` (ON 2026-06-22 — the "your application is in — what happens next" student email at
profile-complete; supersedes the basic submission-ack)**. **WhatsApp S2 proposed-slots nudge + S3 reminder-v2 are LIVE**
(the four `TWILIO_WHATSAPP_{PROPOSED,REMINDER}_CONTENT_SID_{EN,BM}` set on rev …00504, Meta-approved 2026-06-21; legacy
`TWILIO_WHATSAPP_REMINDER_CONTENT_SID` also set).
**S4 phone-verify is LIVE on SMS** (2026-06-22): `TWILIO_VERIFY_SERVICE_SID=VA3ca85b…` set, channel via
`PHONE_VERIFY_CHANNEL` (default `sms`; WhatsApp channel deferred — Twilio's BYO-sender onboarding is ~2-4wk, error 60223
until done — flip the env var to `whatsapp` once cleared, no code change). **S5 STOP→opt-out webhook is LIVE** (owner set
the Twilio inbound webhook URL 2026-06-22; unsigned POST→403, STOP maps a profile only when we've sent it an app-logged
WhatsApp).
**Decision cool-off LIVE — REWORKED 2026-06-27 to "immediate decision, embargoed email".** `DECLINE_COOLOFF_DAYS=7`.
A cool-off DECLINE now flips the application to `rejected` IMMEDIATELY (status + bucket + when/who — the cockpit and
records reflect it at once); only the student EMAIL is embargoed for the window and sent by the `send_pending_decision_emails`
cron. The student does NOT see the rejection during the embargo — `ApplicationReadSerializer.status` masks an
email-embargoed rejection (`status='rejected'` + `pending_rejection_category` set) as `interviewed`; the admin cockpit uses
its own serializer and sees the real `rejected`. `cancel_pending_decline` now REVERSES the rejection (restores
`interviewed` + cancels the email); `release_pending_declines` only lifts the email embargo (status already rejected).
`services.admin_reject` + `_record_reject`/`_send_decline_for`. Decline emails are now HTML (interview bucket thanks for
time + documents). `AWARD_COOLOFF_DAYS=2` (accept side) is UNCHANGED (still defers status until release). Set
`DECLINE_COOLOFF_DAYS=0` to email immediately. Migration `scholarship/0069` (4 additive fields).
DARK/unset: `SHOW_REFEREES=false`, **`AWARD_ACCEPTANCE_ENABLED=false`** (embargoes the "View my award" panel →
accept/onboarding flow on `/scholarship/application`; flip to `1` only after onboarding is tested end-to-end — it
un-hides for ALL funded students at once), **`BURSARY_AGREEMENT_ENABLED=false`** (the tri-partite conditional bursary agreement —
code shipped 2026-06-26 but OFF; the cockpit panel is now **gated on this flag** (2026-06-27) so it stays hidden while
OFF — `bursary_agreement_enabled` on `AdminApplicationDetailSerializer`). The **full signing FLOW is now wired**
(comprehension quiz + parent PIN + notify-and-sign chain + SLA reminders + cockpit ticks, 2026-07-01, DARK) —
**TD-144 RESOLVED**. Flip only AFTER the two Phase-0 gates: lawyer-vet the `bursary.py` template wording, and
finalise the Foundation entity via `FOUNDATION_SIGNATORY_NAME/_TITLE/_NRIC`; then migrate-first `0083`/`0084`/`0085`.
See `docs/scholarship/bursary-go-live-playbook.md`.
Meet SA key **rotated 2026-06-21** (old key `692d49f8…` deleted after a transcript exposure; new `7ef25e69…` in
`GOOGLE_MEET_SA_JSON` — still an env var, TD-125 to move it to Secret Manager).

**▶ SHIPPED 2026-06-27 — Decision-flow & verification hardening (worktree `.worktrees/wa-comms`; commits `2410f25`,
`791a582`, `badda56d`, `f2059d1c`, `435ba2ef`, `3d0b4f27`; NO migration; retro
`docs/retrospective-2026-06-27-decision-flow-hardening.md`).**
- **Decline = immediate rejection + embargoed email** (see the cool-off note above) — fixes #11/#12 showing "Accepted".
- **Reopen returns an accepted case to `interviewed`** (real status transition, not a side-flag) + clears any pending
  decline; cancel-reopen restores `accepted`. A decline after reopen is bucketed **`interview`** (not `contractual`);
  `contractual` is reserved for genuinely post-award (`sponsored`) — the direct decline button shows only for `sponsored`.
  Decline emails are now **HTML** (`send_decline_email` → `_send_html`; interview bucket thanks for time + documents).
- **BC/guardianship relationship rows: name-primary matching.** name-match + AI-misread IC → amber "check the IC number"
  / "differs by one digit" (`vision.nric_close`, `income_engine._combine_relationship`), never a hard red. Fixes #12.
- **Upload orphan-row guard** (`storage.object_exists`): reject a CONFIRMED-missing blob (`400 upload_incomplete`) before
  the stale-sweep. Found+deleted the 1 orphan across 603 docs (#80 EPF). Student msg `scholarship.docs.uploadIncomplete`.
- **Bursary-agreement cockpit panel gated** behind `BURSARY_AGREEMENT_ENABLED` (was leaking false "signed" ticks while
  dark) — TD-144 for the real-agreement ticks at flip-on.
- **Ops:** api memory **1 GiB → 2 GiB** (was OOM-killing interview "Propose times", #90). #11/#12 → `interview` bucket;
  #12 `rejected` (email embargoed to 7/4); #12/#62 mislabelled accepted→`interviewed`. B40 invite **batch 8** (27 new
  SPM merit+need) + **Group A reminder** (6). Supabase MCP connected to the CLI session.
- **▶ NEXT:** no queued sprint. Owner gates remain: bursary Phase-0 (lawyer + Foundation entity) before flipping
  `BURSARY_AGREEMENT_ENABLED`; #12 releases its decline email automatically on 4 July; #62 awaits the reviewer's re-decision.

**▶ SHIPPED 2026-06-26 — Conditional Bursary Award Agreement (Phase 1, DARK) + auth scope policy + sponsor card
(retro `docs/retrospective-2026-06-26-bursary-agreement-and-auth-scope.md`).**
- **Conditional Bursary Award Agreement** (`a085774` backend + `f596dd0` frontend, `BURSARY_AGREEMENT_ENABLED` OFF):
  award-accept becomes a tri-partite signed contract — student + parent surety ↔ Foundation, partner org witness, donor
  never a party. New `BursaryAgreement` model (migration `scholarship/0072`, table + RLS, migrate-first); `bursary.py`
  (EN+BM DRAFT template, `rendered_html`+sha256 snapshot, `xhtml2pdf` PDF to `b40-documents`, `guarantor_identity_check`
  reusing the `parent_ic` Vision gate); signing wired into `respond_to_award`; admin counter-sign + partner witness
  endpoints; `/scholarship/award` signing page. **Two Phase-0 gates before flip-on: lawyer-vet the template; finalise the
  Foundation entity.** Deferred: parent-phone link (Phase 2), real disbursement (Phase 3 / TD-075). TD-140..142.
- **Auth: one active privileged scope per Google identity, super-exempt** (`63fec7c` local-signout fix + `bf832ce`
  intentional policy): `lib/sessionPolicy.ts`; signing into partner *or* sponsor ends the other's local session, super
  admins keep both; kicked tab → its login with a "signed out elsewhere" note. Replaces the prior emergent Supabase kick.
- **Sponsor pool card redesign** (`511259f`): 4-region card (code·SPM·As·state / programme + target university / ≤20-word
  blurb / amount·Support); school dropped from sponsor view; `SponsorProfile.anon_blurb` (migration `scholarship/0071`).
- **Asasi TVET (`FB0500001`) un-hidden**: removed an unsatisfiable `"ANY"` or-group on its requirements (data-only,
  migrate-first + catalogue reload). No code change.

**▶ SHIPPED 2026-06-21 — WhatsApp comms go-live + cockpit fixes + interview reminder-notice gating (retro
`docs/retrospective-2026-06-21-whatsapp-golive-cockpit-reminders.md`; same day: request-owned doc slots, retro
`…-request-owned-doc-slots.md`).**
- **WhatsApp comms is LIVE** (`WHATSAPP_ENABLED=1`, api rev `…00490-h96`). Interview reminders (1-day + 1-hour) now send a
  real WhatsApp alongside the email, opt-in gated (`whatsapp_opt_in`, opt-out toggle in /profile). Migrate-first:
  scholarship `0068` (`whatsapp_messages`, RLS) + courses `0059` (`whatsapp_opt_in`). Sender `whatsapp:+19162597009`,
  approved template `copy_b40_interview_reminder` (`HX7b5eee…`). Smoke-test delivered. Twilio creds in Cloud Run env.
- **Reminders gate on booking notice** (`1c15ca6`): 24h reminder needs ≥24h notice, 1h needs ≥1h (no instant same-day
  "reminder"); `book_slot` stamps `interview_booked_at` on every (re)booking. All 3 channels.
- **Cockpit** (`9197467`): Save-draft accepts `verdict=''` (no data loss); gap-spotter told today's date (MYT).
- **▶ NEXT — roadmap `docs/plans/2026-06-21-whatsapp-and-scheduling-followups.md`** (awaiting approval): proposed-slots
  WhatsApp nudge (TD-138, highest value) · enhanced reminder template w/ Join button · reschedule lead-time relax
  (TD-137) · phone verification via Twilio Verify (TD-136) · STOP→opt-out webhook (TD-135).

**▶ SHIPPED 2026-06-19 — Reviewer comms consistency + reschedule + verdict SLA (3-sprint roadmap, commits
`a3c5d31`→`1d89393`; migration `scholarship/0064` additive migrate-first; retro
`docs/retrospective-2026-06-19-reviewer-comms-and-verdict-sla.md`). Worktree `.worktrees/sched`.**
- **Interview email set now fully HTML+bilingual:** the student **reminder** + **cancellation** emails joined their
  siblings (reused `_html_email_shell`/`_email_button`; `english_only` gate; From `interview@`). `REVIEW_SLA_DAYS` = 10.
- **Reviewer reschedule (move the time)** on the cockpit booked card: `propose_slots(..., release_booking=True)` releases
  the booking (slot + Meet event + fields) → student re-picks via the "pick a time" email with a moved-the-time preface.
  **No reviewer self-cancel** (a hand-off is an admin reassignment); propose endpoint takes a `reschedule` flag.
- **Verdict-completion SLA (TD-131) — NOW LIVE.** `send_review_nudges` cron (job `review-nudges`) — verdict due
  `assigned_at + REVIEW_SLA_DAYS` (10); nudge reviewer 2 days before + once overdue; escalate to all super-admins at
  **day 14** (grace 4). Idempotent stamps (migration `0064`) reset on (re)assignment; recorded `verdict_decided_at`
  cancels. Reviewer interview reminder also shows the verdict-due date. **Switched on 2026-06-19**:
  `REVIEW_NUDGES_ENABLED=1` on the api (rev `halatuju-api-00471`) + Cloud Scheduler `halatuju-review-nudges` daily
  9am MYT; end-to-end smoke test returned 200; first-run blast = 0 (no case due yet). Emails:
  `send_reviewer_verdict_due_email`, `send_super_verdict_escalation_email`.
- **Reviewer email tree is consistent** (Dear / one dashboard CTA / `{ref}` subject / "The B40 Assistance Team" / all
  from `interview@`). Accept/decline-in-email idea was evaluated and **dropped** (unsafe one-click + redundant).
- **▶ Status:** Interview scheduling is **fully LIVE** — `INTERVIEW_SCHEDULING_ENABLED=1`, `INTERVIEW_MEET_ENABLED=1`,
  `REVIEW_NUDGES_ENABLED=1` (all on); reviewers briefed 2026-06-19; Guide scheduling step + screenshots done (TD-126);
  SPF record added + verified 2026-06-19 (`v=spf1 include:_spf.google.com include:spf.brevo.com ~all`).
  **Remaining (owner):** Brevo List-Help on transactional (TD-130). **Optional eng:** extend the `mailto:` unsubscribe
  shim to decision/reminder emails; later tighten SPF `~all`→`-all` + DMARC `p=none`→`p=quarantine`.

**▶ SHIPPED 2026-06-19 — Interview-scheduling arc: Calendly picker + bilingual HTML emails + request-alternatives loop +
cancellation fix (12 commits `a68b442`→`7fcb82d`; migration `scholarship/0063` additive, migrate-first; retro
`docs/retrospective-2026-06-19-interview-scheduling.md`). Worktree `.worktrees/sched`.**
- **Reviewer propose UI = Calendly-style** month calendar + 12-hour time pills (`lib/interviewSlots.ts` mirrored in
  `scheduling.py`): **08:00–21:30 MYT, 30-min, 24h minimum lead, exactly 3** required; existing proposals pre-load;
  re-proposing the same set sends no email. **Reviewer conflict-blocking** across students (`reviewer_busy` admin-payload
  only; server guards `reviewer_conflict`/`too_soon`/`invalid_slot_time`); self-reschedule kept. Locked "Proposed times"
  view + **Propose alternative times**, dustbin icon, bigger arrows, state-aware subheader.
- **All interview emails → HTML+text, bilingual EN+BM** (`english_only` gate = app-English + no Malay/Tamil call pref +
  A/A+ SPM English), **From `interview@`**, anti-scam note. Booked email has **Add-to-calendar (.ics + Google URL)** +
  linked "application page". Helpers: `_send_html`/`_send_bilingual`/`_send_plain`, `_interview_ics`/`_gcal_url`,
  `emails.english_only_email`.
- **In-app "Ask for other times"** loop (closes the email-reply dead-end): migration `0063`
  (`interview_alternatives_requested_at`/`_note`), `scheduling.request_alternatives`,
  `StudentInterviewRequestAlternativesView`, reviewer email, cockpit banner; cleared on next propose.
- **Cancellation fix:** `cancel()` voids the menu + clears pointers; `propose_slots()` lifts a prior cancellation. Booked
  panel: **"Cancel interview" + confirm step**; guardian copy aligned to emails. **Scoped harmless `List-Unsubscribe`**
  (mailto:help@) on interview emails only.
- **▶ Carry (owner / next):** TD-130 = Brevo **List-Help on transactional** (account-wide unsubscribe fix; then drop the
  mailto shim); reminders + cancelled student emails not yet on the HTML/bilingual standard; the student booking side
  could reuse the slot-chip UI. Verify the live #16 flow end-to-end.

**▶ SHIPPED 2026-06-19 — PISMP Aliran → Bidang pathway picker (Sprint 2 of the PISMP work; commits `d86cf11` picker +
`c321f7d` live-review; NO migration; retro `docs/retrospective-2026-06-19-pismp-aliran-picker.md`). Worktree off
origin/main.**
- **Two-tap PISMP course selection.** A student on the PISMP pathway picks **school type** (Aliran: SK/SJKC/SJKT/SKPK,
  eligible-only chips via `AliranPicker`) then **subject** (Bidang) in the **same compact course combobox the UA pathway
  uses** (`ProgrammePicker`) — replacing the type-a-course-name box. Wired into BOTH `/profile` (shared `PathwayPicker`)
  and the inline `/apply` flow via the same components + helpers (`pismpAlirans`/`bidangForAliran`/`aliranForChosen` in
  `lib/scholarship.ts`).
- **Backend:** the eligible-courses payload (`EligibilityCheckView`) now carries `aliran` for PISMP courses (derived via
  `pismp_taxonomy.aliran_of`; **no migration** — serializer-only). Non-PISMP courses get an empty aliran.
- **Live-review fixes (same sprint):** dropped the redundant "(Aliran Bahasa Tamil/Cina)" descriptor that
  `deduplicate_pismp` appended on top of the name's own "(SJKT)" suffix (the name is now clean; `pismp_languages` facet
  kept); swapped the first-cut vertical bidang list for the compact combobox per owner feedback.
- **Eligibility is correct, verified vs the PDF:** the picker shows only the bidang a student qualifies for. A
  science-stream student missing some SJKT specialisms is correct — e.g. Matematik needs A− in **both** Mathematics
  *and* Additional Mathematics, Jasmani's science pool is Sains Sukan/Biologi/Sains/Sains Tambahan only (not Physics/
  Chem) — both confirmed against the official 2026 IPGM syarat (Perdana PDF pp. 7, 11).
- **Tests:** +1 backend (aliran on eligible PISMP) + a no-`(Aliran)` assertion; jest helper tests for the picker.
  `next build` clean. **Deployed (api `…00451`→, web `…00444`→); 2 deploys (initial + live-review).** Elektif (the
  minor) deferred.
- **▶ NEXT:** no PISMP sprint queued. Deferred PISMP follow-ups: STPM + SKPK → `StpmCourse` track (spec
  `memory/halatuju-pismp-refresh-spec.md` Sprint R3); polish cloned generic descriptions on the new Khas/Prasekolah/MBPK
  rows (TD-127); broaden the MBPK gate beyond "Physical disability" (TD-128). Minor: the SJKT C-group requirement
  includes BT (4 subjects) where the PDF lists 3 (BM/BI/Sejarah) — harmless over-spec for SJKT students, tidy at the
  next courses refresh.

**▶ SHIPPED 2026-06-18 — Sponsor-profile income honesty + cockpit final-label fix (2 commits `73b9586` backend +
`289853a` frontend; NO migration; retro `docs/retrospective-2026-06-18-profile-income-honesty.md`). Worktree
`.worktrees/sched`.**
- **Income honesty in the generated profile — `PROMPT_VERSION` 2026-06-16.2 → 2026-06-18.1.** One principle:
  *documented = certain; self-reported = a claim.* (a) STR/JKM asserted ONLY when a current welfare DOCUMENT is on file
  (`profile_engine._gated_str`/`_gated_jkm`, gated on `income_engine.student_str_check` currency; mirrors
  `_gated_first_in_family`) — fixes #21 (salary-route applicant's profile asserted STR "affirming B40 status" off the bare
  self-tick). (b) A DOCUMENTED salary (payslip/EPF) MUST be stated as documented, not buried behind the reported figure —
  fixes #10 (mother's RM3,049 payslip gross dropped for the reported ~RM1,700). Same clause added to `REFINE_PROMPT`. +9
  tests (1343 scholarship pytest).
- **Cockpit profile panel labels "final" once a final exists.** Header + hint were static, so an already-generated final
  (v2 with interview) read as a pending draft; now key off `profile.final_markdown` (`profileFinalTitle`/`profileFinalHint`,
  en/ms/ta).
- **▶ PENDING (billable, owner's call):** run the `backfill-assigned-profiles` cron to regenerate existing drafts onto
  `2026-06-18.1`. New generations after this deploy already use the new prompt. Verify both Cloud Builds went SUCCESS.

**▶ SHIPPED 2026-06-18 — PISMP catalogue reconciliation + Aliran facet + MBPK disability gate (Sprint 1 of the PISMP
pathway work; commits `4446c2e` bug+aliran, `4589a6a` req_disability; courses migration `0058`; retro
`docs/retrospective-2026-06-18-pismp-catalogue.md`). Worked in worktree off origin/main.**
- **Fixed "0 of 0" in Explore.** `CourseSearchView` skipped the SPM branch for level=`Ijazah Sarjana Muda` (treated it
  as STPM-only), hiding all PISMP. Now only skipped for `source_type='ua'`. PISMP degrees are visible again.
- **Aliran facet** (SK/SJKC/SJKT/SKPK) in Explore, derived read-time by `pismp_taxonomy.py` (no schema change); web
  shows an Aliran dropdown when source-type=PISMP, trilingual.
- **SPM Perdana catalogue now matches the official 2026 PDF** by code + name + requirements (SJKT 10 / SK 14 / SJKC 15).
  Fixed a systematic `A→A−` over-restriction across all 35 Perdana, the B/D/L→`…H` Pendidikan Khas/Prasekolah swap, and
  retired spurious rows (all backed up to `Downloads/*_retire_backup_2026-06-18.json`).
- **MBPK intake disability-gated.** New `req_disability` must-HAVE flag (courses migration `0058`) + engine gate; 10
  Laluan Khas track-A `50BK…` bidang ingested, recommended only to students who declared a disability. Verified live
  (rev …00447).
- **Gotchas:** PISMP is **PDF-sourced** (not web-scrapeable). Eligibility reads a pandas `requirements_df` cached at app
  boot (`apps.py:61`) — **DB requirement/catalogue edits don't reach live eligibility until the api restarts** (force a
  no-rebuild revision via `--update-env-vars=PISMP_DATA_RELOAD=<v>`). Search/Explore read the ORM live.
- **▶ NEXT (Sprint 2): the Aliran → Bidang pathway picker** in `/apply` + `/profile` — the UI that lets a student
  navigate Aliran → Bidang Pengkhususan to the right PISMP course (`PathwayPicker.tsx` / `lib/scholarship.ts`).
  Stitch-prototype first, trilingual en/ms/ta, tests. The catalogue is now correct enough to drive it. **Deferred:**
  STPM + SKPK → `StpmCourse` track (spec in `memory/halatuju-pismp-refresh-spec.md` Sprint R3); polish the cloned
  generic descriptions on the new Khas/Prasekolah/MBPK rows; broadening the MBPK gate beyond "Physical disability".

**▶ SHIPPED 2026-06-18 — Reverse a recorded decision ("Reopen") + cockpit Q&A presentation (migration
`scholarship/0062` migrate-first; retro `docs/retrospective-2026-06-18-decision-reopen.md`). Worktree `.worktrees/sched`.**
- **Reopen (super-only) reverses a finalised decision.** The Decision panel's cosmetic "Edit" (frontend-only) became
  **Reopen**: it **holds the student's profile from the sponsor pool** (`anon_published=False`), opens a `DecisionReopen`
  audit row (attributed to the assigned reviewer, with a required reason), stamps `decision_reopened_at`, unlocks the
  panel + reviewer dropdown, and banners "held from sponsors". **Cancel reopen** restores the prior published state;
  **re-saving** (Approve/Decline) regenerates + republishes per the new decision. `reopen.py` service +
  `reopen-decision/`/`cancel-reopen/` endpoints. NO flag (super-only cockpit action; ships LIVE).
- **Corrections metric (model B):** a reopen counts against the reviewer ONLY when it leads to a saved change (a
  cancelled reopen doesn't). Count = `COUNT(DecisionReopen.resulted_in_change=True)` per reviewer — internal only
  (assign panel), never on a sponsor/student surface.
- **Assign panel:** "Reviewer assigned" / "Reviewer: {name}"; dropdown **locks** once a decision is recorded, unlocks on
  Reopen. **Interview Stage submitted record** now reads like Check 2 (✓ tick · bold Question · "Reviewer's finding"
  header above the box); top "Submitted" pill removed; "Conclusion"/"Findings" labels are headers above their boxes.
- **Tests:** 2488 backend pytest (+10 `test_decision_reopen.py`) + 327 jest + i18n parity/orphan guardrail + next build
  clean. **Prod at scholarship migration `0062`.**

**▶ SHIPPED 2026-06-18 — Interview scheduling + Google Meet, email aliases, contact-form notify, cockpit live-review
(10 commits `d13b949`→`a51517a`; migration `scholarship/0061` migrate-first; retro
`docs/retrospective-2026-06-18-scheduling-meet-aliases-cockpit.md`). Worked in worktree `.worktrees/sched`.**
- **In-app interview scheduling + Google Meet** — reviewer proposes 2–3 times (`InterviewSlot`), student books one on
  `/scholarship/application`, system auto-creates a Meet link + calendar event (best-effort) + bilingual confirmation +
  1-day/1-hour reminders; self-reschedule/cancel to a 12h cutoff. `scheduling.py` + `meeting.py` (Workspace SA +
  domain-wide delegation), booking columns + `interview_slots` table (mig `0061`), `send_interview_reminders` cron,
  cockpit propose-card + student booking panel, Guide+FAQ. **`INTERVIEW_MEET_ENABLED=1` + `INTERVIEW_SCHEDULING_ENABLED=1`
  BOTH LIVE (scheduling flipped on 2026-06-18, api rev …00432); Meet proven end-to-end. The surface is exposed to
  reviewers + students.** (Re-dark with `--update-env-vars INTERVIEW_SCHEDULING_ENABLED=0` if needed.)
- **Google Workspace `halatuju.xyz` live; email mapped to aliases.** From=`info@`, support=`help@`, interview
  reply-to=`interview@`, sponsor=`sponsor@`, internal notify=`contact@`, Meet organiser=`admin@` (the PRIMARY account —
  DWD can't impersonate an alias). Brevo domain authenticated (any `@halatuju.xyz` sends). Fixed lost replies
  (`noreply@` wasn't a real mailbox); removed personal `tamiliam@gmail.com` from user-facing copy.
- **Contact form now alerts** — `notify-contact-submissions` cron emails each unread `contact_submissions` row to
  `contact@` (was stored-but-unseen). No admin inbox UI yet (TD-124).
- **Cockpit fixes** — Decision panel + Interview Stage **freeze read-only once committed** (superadmin reopen); Interview
  Stage **"Saved ✓"** + read-only blue-box record after submit (closed a duplicate-draft bug); audit lines show **full
  name** (`verified_by_name` etc.); assignee filter lists reviewers by name; sortable Name/Merit (server-side, `?sort`);
  status labels Sentence-cased + "Completed"; profile merit→grades returns to `/profile`; footer "B40 Aid" links.
- **OPS:** SA `halatuju-meet@` + DWD authorised (scope `calendar.events`); Cloud Scheduler `halatuju-interview-reminders`
  + `halatuju-notify-contact-submissions` (both */15). Env on `halatuju-api`: `INTERVIEW_MEET_ENABLED=1`,
  `MEET_ORGANISER_EMAIL`, `GOOGLE_MEET_SA_JSON` (secret), `DEFAULT_FROM_EMAIL=info@`, `ADMIN_NOTIFY_EMAIL`/
  `COURSE_REFRESH_REMINDER_EMAIL=contact@`. Prod at scholarship migration **`0061`**.
- **▶ NEXT:** scheduling is now LIVE — **monitor the first real bookings** (a Meet link should generate + the
  confirmation/reminders fire). Owner follow-ups: add the Guide scheduling screenshot (TD-126); add a merged **SPF**
  TXT (`v=spf1 include:_spf.google.com include:spf.brevo.com ~all`); refine the assignment email copy to point students
  to "book your interview" (the assignment email `STUDENT_ASSIGNMENT_EMAIL_ENABLED` is now **ON** in prod — 2026-06-21).
  TD-124 (contact inbox UI), TD-125 (Meet key → Secret Manager). Other thread: genuineness branch (unmerged).

**▶ MERGED + LIVE 2026-06-27 (`4cb26111` → main; api rev …00533) — Layer-1 document-recognition model, `MODEL_VERSION=1.0`
(retro `docs/retrospective-2026-06-27-doc-recognition-layer1-golive.md` + earlier doc-eval retros).** The deterministic
SIGNATURE genuineness scorer (`genuineness/results_doc.py`) for ALL standard docs, behind the already-ON
`DOC_GENUINENESS_CHECK_ENABLED`.
- **`genuineness/` package** (`ic`, `supporting_doc`, `results_doc`, `bands`, `assess()`). Signature scorer over OCR text
  → **band suspect<0.35 / review 0.35–0.70 / genuine≥0.70**; canonical `genuine/suspect/not_<type>` enum.
- **LIVE for every standard doc:** results_slip/cert, **BC** (text-only — visual signatures dropped, fix-a), **EPF**
  (+ wrong-type backstop, TD-117), **offer_letter** families (stpm/matric/poly/pismp/**ua_offer**=20 fixed public unis,
  identity-anchor gated), **STR** (MOF letter/dashboard/Semakan, identity gated; SALINAN+SARA → unrecognised → holistic).
- **`MODEL_VERSION` stamped on every result + persisted in `vision_fields.authenticity`** — **BUMP on ANY signature/
  weight/gate change** (History comment in results_doc.py + feedback memory + a guard test enforce it).
- Rode along: IC-anchored offer NRIC, EPF salary reverse-engineer (`max(ΣMajikan/(n·0.13), ΣAhli/(n·0.11))`), SPM slip
  2-column bounce-to-Gemini, hand-written salary ringgit\|sen decimal read, Asasi-at-Politeknik pathway.
- **Validated** on local corpus + held-out 90 unseen prod docs across 5 models = **0 false rejections**. 1610 scholarship
  pytest. Eval tooling: `eval/capture_ocr.py` + `eval/heldout_eval.py` + `eval/calibrate_signatures.py` (PII gitignored).
- **Decisions:** UPU/MOHE semakan stays `suspect` (official offer letters only); see `docs/decisions.md`.
- **▶ NEXT (deferred):** Layer-2 cross-doc matching (parent-IC **TD-119**, via `courses.pismp_taxonomy.aliran_of`),
  **TD-121** (harness genuineness cap), **TD-143** (header-cropped BC → not_type, owner's call).

**▶ JUST SHIPPED & LIVE 2026-06-27 — Offer-validity SUBMISSION GATE + cockpit genuineness consistency
(commits `c935dad`→`c48ffbd`; no migration; retro `docs/retrospective-2026-06-27-offer-validity-gate.md`).**
- **Only a genuine OFFICIAL public offer qualifies** (`MODEL_VERSION 1.1`). Conditional / private-IPTS / non-official
  (pemakluman / UPU-semakan) → `offer_not_official` blocker at submission (en/ms/ta); **GRANDFATHERED** for already-
  submitted (the check is in `consent_blockers`, NOT `application_completeness` → status never reverts, only the pathway
  BADGE recomputes). Pathway verdict gates on `pathway_engine.offer_official_status`; the offer holistic fallback is
  dropped so a private/IPTS letter stays not-genuine (gate-able), not image-rescued.
- **Cockpit Documents drawer now reflects offer genuineness** — `get_authenticity` was dropping `offer_letter`, so a
  non-genuine offer showed a green "Verified"/"Pathway"; now Pathway→red + an "Official"→red fact → chip amber, never
  green (matches the verdict tile). **#30 false-clash fixed** — ministry/issuer boilerplate (`kementerian/pendidikan/…`)
  added to the non-distinguishing token set. **SPM exam year** now shown on the results-slip chip.
- **▶ NEXT (deferred fast-follow, TD-145):** wrong-PUBLIC-university soft-confirm — resolve `course_id →
  course_institutions → institution` so a declared-UMK vs UM-offer clash raises `pathway_confirm` (today invisible when
  the declared institution field is blank). **Existing offers need a re-run for badges to reflect the new scorer.**

**▶ JUST SHIPPED & LIVE 2026-06-16 — Live-review round (10 commits `c6bc963`→`611e6b1`; migration `scholarship/0058`
migrate-first via MCP; retro `docs/retrospective-2026-06-16-livereview-round.md`).**
- **AI profile — completeness & safety.** Now distils ALL student inputs (justification, fears, anything-else, top
  choices, other scholarships, help-wanted, deliberation); uses the **interest quiz** (accretive profile colour + an
  exploratory interview question on quiz-vs-pathway divergence); feeds the OCR'd **Statement of Intent** letter.
  **Grades summarised by GROUP** (no per-subject list) and **ethnicity-safe** — vernacular subjects fold into generic
  groups AND ethnic/cultural specifics in the narrative are generalised ("her mother tongue", not "Tamil").
- **Prompt versioning (`PROMPT_VERSION`, currently `2026-06-16.2`)** stamped on every `SponsorProfile.prompt_version`
  (migration `0058`); the `backfill-assigned-profiles` cron is **version-aware** (skips current, refreshes stale). To
  apply a future prompt change to existing drafts: bump `PROMPT_VERSION`, deploy, then run the cron job. All 8 current
  drafts regenerated onto `.2`.
- **Reviewer access:** new **`/admin/set-password`** page (invite + reset links → choose a password) unblocks non-Google
  invitees; assignee filter hidden for reviewers (their list is self-scoped). **Kalai** fixed in prod (reviewer record
  repointed from a never-activated yahoo email to her working gmail; dead yahoo auth user deleted; assignment preserved).
- **i18n:** TD-118 + TD-120 resolved (106 orphaned `admin.scholarship` keys removed) + a **dynamic-aware orphan/parity
  guardrail test** so the class can't regrow.
- **Carry / open:** the set-password **invite-link** path needs one **live test invite** to confirm (recovery path is
  solid); Dhurvaashrii-class consent gate too strict (tolerant parent-IC name match — PROPOSED, not built); Tamil refine
  of first-draft strings; funding figures for kkom/iljtm/ilkbs; candidate — schedule the version-aware backfill so drafts
  self-heal on a prompt bump.

**▶ SHIPPED & LIVE 2026-06-16 — Reviewer access fix (`4a74b9b`, NO migration; retro
`docs/retrospective-2026-06-16-reviewer-access.md`).** Two faults the newly-invited reviewers hit:
- **Invite link → `/admin/login`** (was bouncing to the homepage): `AdminInviteView` now sets
  `redirect_to: {FRONTEND_URL}/admin/login` on the Supabase invite POST. Supabase Redirect-URL allow-list already
  covers `halatuju.xyz/**` (confirmed live), so no dashboard change.
- **Reviewers/viewers now land on `/admin/scholarship`** (B40 Applications), not `/admin` (the partner-org dashboard,
  which 403s them → "not a partner organisation admin"). Role-branch added to both `admin/login` and
  `admin/auth/callback`; org `admin`/`super` keep `/admin`. **Lesson:** adding an auth role means re-auditing every
  "default landing / who's an admin" assumption — see `docs/lessons.md`.
- **Carry (unchanged):** TD-118 (dead profile api-client fns + orphaned i18n keys, web-only); Dhurvaashrii-class
  consent gate is too strict (exact parent-IC name match rejects shortened/Tamil-romanised names) — tolerant-match fix
  PROPOSED, not built, awaiting owner; Tamil refine of first-draft strings; funding figures for kkom/iljtm/ilkbs.

**▶ SHIPPED & LIVE 2026-06-15 — AI profile narrative redesign + 2-step lifecycle (5 commits `dc89c39`→`68fd1ac`,
NO migration; plan `docs/scholarship/profile-narrative-redesign-plan.md`, retro
`docs/retrospective-2026-06-15-profile-narrative-redesign.md`).**
- **ONE profile, common to reviewer + sponsor**, generated twice by the system: DRAFT at the Check 2 → reviewer handoff
  (Flash), FINAL at "Save verdict & generate final profile" (Pro) which REPLACES the draft and IS the sponsor/pool
  version. No more named-draft-vs-anon split, no manual Generate/Save/Publish/Refine, no anon-profile card.
- **Narrative prose** (no headers, he/she never "they", sparing em-dashes, no clichés). **PII-redaction:** alias not
  name; block ONLY name/NRIC/photo/phone/email/street (student+guardian) — school/town/institution/occupations allowed.
  Scanner split: strict `scan_anon_for_identifiers` (graduation relay) vs relaxed `scan_profile_pii` (profile).
- Feeds merit, subject grades, confirmed programme, and the **student's Check-2/reviewer Q&A**; final adds findings +
  verdict + conclusion + recommended amount. **Income honesty:** STR/JKM = B40/welfare status, NOT a figure; payslip/EPF
  used authoritatively else "reported", never a guessed earner. Cockpit = plain read-only text. Final published on Approve.
- **`CHECK2_AUTO_GENERATE` was referenced but never defined in settings** (so it was permanently off and the handoff
  auto-draft never fired) → wired in `base.py`, env var **on** (durable; the build trigger doesn't reset env). Future
  reviewer assignments now auto-draft. Backfilled the 7 already-assigned via the `backfill-assigned-profiles` cron job
  (runs on the service — the sandbox can't reach the prod DB). Validated live on #72.
- **Carry:** TD-118 (tidy dead profile api-client fns + orphaned i18n keys — harmless, web-only).

**▶ JUST SHIPPED & LIVE 2026-06-15 — Reviewer-invite + funding-estimate live-review round (7 commits `0eecd1d`→`4c2053f`,
NO migration; retro `docs/retrospective-2026-06-15-reviewer-invite-funding-estimate.md`).**
- **Reviewer-assignment email** (`emails.send_reviewer_assigned_email` → `services.assign_reviewer`): names the applicant,
  links to `/admin/login`, fires once per (re)assignment, best-effort. **Invite name** passed as Supabase `data:{name}` →
  `{{ .Data.name }}`. **Ops:** Brevo is now Supabase Auth's custom SMTP (verified `noreply@halatuju.xyz` sender) — invite
  + password-reset rate limit cleared; invite template rebranded.
- **Funding estimate rebuilt** to the owner's per-pathway model (`funding_estimate.py` + basis doc): single shortfall =
  costs − govt allowance − PTPTN, × fixed per-pathway months, rounded RM100 (STPM ~9k, Matrik ~2k, Asasi ~7k, Poly ~4.3k,
  uni-diploma ~6.6k, PISMP ~10.8k). **No device**, **no degree** (post-SPM can't, bar PISMP), **poly vs university-diploma
  split**, kkom/iljtm/ilkbs un-estimated. Classifies from `chosen_programme` when pathway-type blank (#62); duration is
  the table, NOT student `programme_months` (fixed STPM 24→18). Cockpit card: total + `~RM/mth × months` + variable +
  practical-term notes.
- **Gopal offer-vs-pathway clash**: names the difference, offers "fix in /profile" OR "confirm later via Check-2".
- **Corrected stale flag note:** `CHECK2_STUDENT_QUERIES_ENABLED` is **ON** in prod (student-facing Check-2 is live).
- **Gotchas reaffirmed:** another agent shares this repo (primary checkout on `feature/doc-eval-harness`) — read code from
  `main` (a worktree) + verify flags via `gcloud run …describe`, never CLAUDE.md or the primary checkout. The
  funding estimate is computed **live** per cockpit load — no backfill needed.

**▶ JUST SHIPPED & LIVE 2026-06-14 — Cockpit live-review + verification-accuracy round (4 commits `245facd`→`97a7793`,
NO migration; retro `docs/retrospective-cockpit-livereview-2026-06-14.md`).** A live-testing pass over the officer
cockpit + the income/document engine, driven by reviewing real applicants (#72/#54/#37):
- **Cockpit r8** (`245facd`): final sponsor profile on **Gemini 2.5 Pro** (drafts stay Flash); refine prompt folds in
  the 4-fact verdict + conclusion + recommended assistance; **Approve** gated on an assistance amount; **interview
  questions 3-at-a-time + "Generate more"**, fed the academic record + verdict + flags + answered Check-2 items;
  academic Check-2 queries name the missing subjects + the grades page. **Brand restyle** (`8b307c8`, web-only).
- **Weighted address matcher** (`51c17d3`): `vision.address_match` (found/unconfirmed/mismatch) — house# anchor + street
  + (postcode OR city), abbreviations normalised. Killed a whole class of false "address miss" (Port↔Pelabuhan Klang,
  abbreviations, postcode-absent bills); 15 prod bills recomputed to green via MCP (no billable calls). FE: only a true
  `mismatch` is red; `unconfirmed`/legacy `not_found` are amber.
- **Route-aware income genuineness cap** (`51c17d3`): only the route's REQUIRED proof can cap INCOME (STR→STR, +BC when
  earner=mother). An optional EPF/salary slip no longer downgrades the verdict; it still raises the officer flag.
- **EPF mining** (`97a7793`): avg monthly contribution (income estimate uses the average), zero-vs-unreadable
  contribution status, statement date, member address. NEW uploads only — existing EPFs use a latest-month fallback
  (TD-116; re-run to repopulate).
- **Gotchas reaffirmed:** another agent shares this repo — VERIFY the branch + work in your own worktree before any
  merge/push (this round a push accidentally advanced the other agent's branch; recovered via refspec). `address_match`
  verdicts + EPF avg are CACHED (recompute via MCP / per-doc Re-run, not auto). #37-class EPF mis-slots need genuineness
  to run (TD-117).

**▶ NEXT — no roadmap sprint queued.** Standing follow-ups: TD-116 (EPF re-parse, billable, owner's call), TD-117 (#37
deterministic EPF wrong-type backstop, offered), Tamil refine of first-draft strings, lawyer consent text.

**▶ COMPLETE & LIVE 2026-06-14 — Check-2 / Interview-Stage cockpit redesign (4 sprints + 3 review rounds; roadmap
`docs/scholarship/check2-check3-roadmap.md`, retro `docs/retrospective-check2-check3-s4.md`).** The cockpit reads
Verification verdict → Student profile (own box + collapsed own-words) → **Check 2 — Outstanding** (the single querying
channel: raise a query / request a document with per-person doc slots; shows the ACTUAL question + the student's answer;
answered = auto-accepted, unanswered = Delete) → **Interview Stage** (agenda + carried-over unanswered queries to ask
verbally + findings + Submit). Querying **locks** once the interview is concluded (`querying_locked`, status ≥ interviewed
or a submitted session); **Submit → final polished profile**, and the Check-2→Reviewer **handoff auto-drafts** the profile —
both gated behind the **OFF `CHECK2_AUTO_GENERATE`** flag (flip to `1` on the api to enable; billable Gemini). Shipped
`f5243a7` → `762b358`.
**▶ Deferred (TD-115):** the DB `UniqueConstraint(application, doc_type, household_member)` belt-and-suspenders (app layer
already prevents dups). The salary-route Action-Centre tagging gap is now CLOSED (S2b). The AI answer-relevance "off-topic"
hint stays unbuilt (depends on the OFF `CHECK2_ANSWER_RELEVANCE_ENABLED` + would touch the live resolve endpoint).

**▶ NEXT: nothing queued for the scholarship cockpit — awaiting the owner's next priority.**

---

**▶ Document slot model (TD-115) — Spec `docs/scholarship/document-slot-model-plan.md`. 27 fixed
`(doc_type × person)` slots; every upload lands in one slot; re-upload overwrites; the income route controls which slots
are required vs optional (display), NOT where a doc is stored.**

**▶ Sprint 1 SHIPPED & LIVE 2026-06-13 — tolerant readers + per-person upload tagging (on `main` `7b460d4` + MCP backfill;
data migration, no schema change; retro `docs/retrospective-slot-model-s1.md`).** Tolerant-then-tighten rollout:
`income_engine._cluster_docs` + cockpit `incomeDocLayout` read income docs BY PERSON with a blank-as-earner fallback on the
STR route; the upload endpoint (`views.DocumentListCreateView`) is AUTHORITATIVE for income-doc tagging (STR route tags
`income_earner` regardless of client input — also slots Action-Centre/Check-2 uploads — + tolerant sweep replaces the legacy
blank); wizard tags/displays per-earner. Backfill: 53 STR-route blank income docs → earner (0 blanks, 0 dup slots).
Verdict-invariant (verdict engine reads STR by doc-type, salary by member tag). #12 corrected → STR/mother (audited switch).
**▶ NEXT (deferred): (a) DB `UniqueConstraint(application,doc_type,household_member)` — needs test-fixture rework + migrate-first
(app layer already prevents dups); (b) salary-route Action-Centre member-tagging (STR path already fixed); (c) the Check-2/Check-3
process flow & display — **now IN PROGRESS as the 4-sprint redesign at the top (`docs/scholarship/check2-check3-roadmap.md`);
S1 done on branch `check2-check3-s1`**.**

**▶ COMPLETE — Verification-assurance programme (document genuineness + measured reliability). All 3 sprints SHIPPED & LIVE
2026-06-12. Roadmap `docs/scholarship/verification-assurance-roadmap.md` (layers 1–3 done). Governing principle: not
certainty — a "highly probable" genuineness confidence from a few independent fingerprints, shown with evidence, scored
against human review; SOFT throughout (reviewer is the authority); threat model = casual/wrong-document fakes, not forgers.
Owner-deferred (not built): the full audit-trail VIEW; verify-before-disbursement (money-gate); an explicit
`officer_verdict.overall` accept/decline toggle.**

**▶ Sprint 1 SHIPPED & LIVE (flag ON) 2026-06-12 — IC genuineness fingerprint (on `main` `29d5e7e`; NO migration; retro
`docs/retrospective-ic-genuineness.md`).** `vision.ic_genuineness()` — one multimodal read of the MyKad fingerprints
(header words + face + chip + physical-card look) → `{status, markers, reason}` in `vision_fields['authenticity']`
(no migration); NO signal on an AI outage. Three soft surfaces: Identity prediction caps at `review`/Unsure on a suspect
card (never auto-fails), officer flags `ic_low_confidence`/`parent_ic_low_confidence`, honest amber note on the student IC
card (matched name/IC stay green). **Flag `DOC_GENUINENESS_CHECK_ENABLED` flipped ON in prod (api rev `…00363-slj`);**
validated live on #16's typed fake (→ low_confidence + Identity Unsure + officer flag). Validated empirically first on our
real ICs. 12 tests; 1179 scholarship pytest, 303 jest, parity 2565×3. **Re-dark with one `--update-env-vars
DOC_GENUINENESS_CHECK_ENABLED=0`.**

**▶ Sprint 2 SHIPPED & LIVE 2026-06-12 — genuineness for the standardised supporting docs + wrong-type (on `main`
`4922003`; NO migration; retro `docs/retrospective-doc-genuineness-s2.md`).** `vision.doc_genuineness()` — a per-type
multimodal read (STR allows a genuine MySTR app screenshot; results-slip/BC/EPF expect a real scan/photo) →
`vision_fields['authenticity']` ({status, doc_seen, reason}; status adds `wrong_type`). Validated on real files first
(genuine pass; typed/screenshot → suspect; a typed BC + a KWSP withdrawal form mis-filed as a statement → wrong_type).
Soft surfaces: **verdict caps** (`verdict_engine._apply_genuineness_caps` in `build_verdict` — suspect/wrong-type
results-slip → Academic Unsure; str/epf/birth_certificate → Income; downgrade-only, never gap, never upgrade); officer
flag `document_not_genuine`; student amber note (shared `GenuinenessNote`). Fixed a Sprint-1 i18n gap (`ic_low_confidence`
verdict-item copy). NOTE: NOT "zero extra cost" — genuineness needs a multimodal IMAGE read (one extra Gemini call per
doc), since the supporting-doc extraction reads OCR text. Flag already ON. ~15 tests; 1190 scholarship pytest, 303 jest,
parity 2570×3. Salary slip + offer letter deliberately un-fingerprinted (too varied).

**▶ Sprint 3 SHIPPED & LIVE 2026-06-12 — the SCOREKEEPER (NO migration, NO backend change; retro
`docs/retrospective-verdict-scorekeeper.md`).** The reviewer's authority is now MEASURED. The (AI, human) verdict pairs +
the agreement maths were already built (`ai_verdict_snapshot`/`officer_verdict` at verdict-save; `audit.override_metrics`;
`AdminVerdictMetricsView`; `getVerdictMetrics()`) — TD-083 surfacing. Added the surface only: tested `verdictReliability()`
(`officerCockpit.ts`, agreement = 1 − override rate per fact + overall) + self-contained `AiReliabilityCard.tsx` at the
**top of the B40 applications list**, with an honest empty-state (hides until reviewers record verdicts; no prod verdicts
yet) and `catch → null` so a metrics hiccup never breaks the list. No flag (read-only aggregate). en/ms/ta
`admin.scholarship.reliability.*`. +2 jest; **305 jest, parity 2574×3, next build clean.** The explicit
`officer_verdict.overall` toggle (TD-083's other half) deliberately NOT built — the card derives reliability from the four
per-fact decisions.

**▶ NEXT — no active feature sprint queued. Standing follow-up: Tamil refine of the first-draft strings shipped across the
programme (`reliability.*`, `icCheck.notGenuine`, `genuineness.note`, `anomaly.document_not_genuine`/`ic_low_confidence`,
`verdict.item.*`, and the income route-switch strings). A separately-planned thread exists in
`.claude/plans/dapper-leaping-cloud.md` (school capture + cockpit refinements + verification soft-signals, 9 tasks) —
NOT started; revisit when the owner picks it up.**

**▶ JUST SHIPPED 2026-06-12 — upload-race fix + exact income-doc request (NO migration; on `main` `a38f484`; retro
`docs/retrospective-upload-race-and-income-request.md`).** (1) `resolution.doc_match_verdict` now returns a distinct
`'pending'` (hold the task) for a NOT-YET-SCANNED doc instead of `'ok'` — closes the race where an unread re-upload
(deferred/`review_manually` under the hourly doc-assist cap, hit in heavy testing) auto-closed its task before the scan
finished; covers results-slip name/subjects + unreadable subject-table (not just the name) + `ic`/`parent_ic` with no
`vision_run_at`. The interactive upload force-reads the just-submitted file past the cap (`views._maybe_extract_fields
force=True`); `resolve_doc_items_for_upload` only closes on `'ok'`. FE shows a calm "still checking" note on `'pending'`.
(2) `income_proof_missing` (STR-route-ONLY, `verdict_engine._verdict_income`) copy now names the STR (Sumbangan Tunai
Rahmah) specifically in en/ms/ta — student Action Centre + officer cockpit + consent blocker — instead of the generic
"salary slip, EPF, or STR" that invited a wrong upload (str-typed Upload button files any pick as `doc_type='str'`).
1156 scholarship pytest + 303 jest + parity 2543×3 + next build clean. Verified on prod #16 (STR route, earner mother).

**▶ JUST SHIPPED 2026-06-12 — student self-serve income ROUTE-SWITCH (on `main` `e1aff91`; NO migration; retro
`docs/retrospective-income-route-switch.md`).** A submitted student on the wrong income route can change it from the
Action Centre. New audited endpoint `POST .../applications/<id>/income-route/` + `services.switch_income_route` flips
`income_route` both ways, recomputes the resolution queue (old gap clears, new doc tasks appear), and **never reverts
the submission** — deliberately NOT via the details PATCH (which `revert_if_profile_incomplete` would un-submit them).
Audit = structured log (audit-only, no officer flag). FE `IncomeRouteSwitch` mini-wizard mounted once on an open income
task post-submit: "We receive STR (Sumbangan Tunai Rahmah)" → whose name, or "We don't receive STR" → who works. 11
backend tests (1167 scholarship) + 303 jest + parity 2560×3 + next build clean. **Carried:** TD-112 (live browser
click-through — verify on prod), TD-113 (salary slip stays a soft signal, not a hard task — needs sign-off to change),
Tamil refine of the new `incomeRouteSwitch.*` block.

**▶ NEXT — no roadmap sprint; do when inputs arrive:** lawyer consent text + `CONSENT_VERSION` bump; real money
(toyyibPay donate-in/disbursement/tranche, TD-075); reviewer-assignment activation when a real reviewer is invited;
Tamil refine batch (the income-request strings + `actionCentre.stillChecking` + `incomeRouteSwitch.*`); the carried
cockpit-school-ux backlog #1–#9 (still merged-not-pushed on another branch — reconcile with the parked family-redesign).

**▶ MERGED TO `main` 2026-06-12 — NOT YET PUSHED/DEPLOYED (owner gates the deploy). Live-review backlog #1–#9, two
sprints, NO migration. Retros `docs/retrospective-cockpit-school-ux.md` + `docs/retrospective-verification-soft-signals.md`.**
**Sprint A (#1–#7, FE+i18n):** guided optional school in onboarding (#1) + editable in profile above Angka Giliran (#3),
both via existing `StudentProfile.school`; cockpit real status pill (#2, `admin.scholarship.statuses.*`), "Applied"
milestone (#4), dynamic Parent/Guardian label from the consent relationship (#5), legacy `siblings_studying_count` row
hidden w/ captioned fallback for the 10/76 unsplit-legacy rows (#6), prev/next applicant nav following the list filter (#7).
**Sprint B (#8–#9, backend soft-signals, never gate):** `income_engine.utility_holder_unknown`/`utility_address_mismatch`
(hard mismatch only) → officer pre-interview flags (active) + student Check-2 clarify queries (**dark** behind
`CHECK2_STUDENT_QUERIES_ENABLED`); `income_engine.slip_epf_divergence` (payslip gross vs EPF-implied, 0.6–1.67 band) →
officer flag (#9). Gates: web `next build` clean + 297→ jest + (Sprint B) **1104 scholarship pytest** + parity 2531×3
(combined). **Deploy = push only (no migrate-first).** Tamil first-draft on all new keys (refine queue). Carried: #6/cockpit
overlaps the parked `feature/family-section-redesign` (reconcile at that branch's merge).

**▶ ALL SHIPPED & LIVE.** The B40 Phase E/F sponsor programme (13 sprints + go-live, `SPONSOR_POOL_ENABLED=true`),
the **Admin Roles realignment** (`super/admin/partner/reviewer` + full students/B40 scoping; nav/invite/profile
redesign), the post-deploy **invite-existing-user** + **phone/email search** fixes, and the **B40 income-gate policy**
(gross household income ≤ `income_ceiling` RM5,860 is the PRIMARY test; per-capita RM1,584 is a safety net above it)
are all on `main` and deployed. Prod migrations through `courses 0053` / `scholarship 0056`. Prod admins: 1 super
(owner) + 2 CUMIG partners.

**▶ JUST SHIPPED 2026-06-10 — Action Centre (post-submit student surface), no migration; retro
`docs/retrospective-action-centre.md`, plan `docs/scholarship/action-centre-gopal-plan.md`.** A submitted student
(`profile_complete`/`interviewing`/`interviewed`) now lands on the **form-locked Action Centre** (not the dead-end
"received" card). **Phase 1:** uploading a requested doc runs its specific scan (`resolution.doc_match_verdict`, mirrors
the consent-gate per-doc red/unreadable classification; `resolve_doc_items_for_upload` wired into `recordDocument`) →
match ticks **Done**, mismatch/unreadable keeps it open + contextual `DocumentHelpCoach`; **fixed the officer-doc-never-
resolves bug**. Student queue shows **only officer + AI-clarify items, never `source='system'` verdict gaps**
(`ResolutionItemListView` excludes system). Resolved tasks stay as green **Done** cards. **Phase 2:**
`help_engine.judge_answer_relevance` (Gemini JSON, firewalled, defaults to accept) nudges a typed answer **only when
TOTALLY off-topic**, behind **`CHECK2_ANSWER_RELEVANCE_ENABLED` (default OFF, billable)**. **The email +
AI-clarify-query switch `CHECK2_STUDENT_QUERIES_ENABLED` stays OFF** (owner's call — both flags are one env var from on).
Tests: 989 scholarship backend pytest + 276 jest; i18n parity 2474.
**▶ UPDATE 2026-06-15: `CHECK2_STUDENT_QUERIES_ENABLED` is now ON in prod — the student-facing Check-2 layer
(auto clarify queries, doc requests, the "few questions" emails, AND the `pathway_confirm` "Is this where you're going?"
step) is LIVE; students are responding. (`CHECK2_ANSWER_RELEVANCE_ENABLED` was also turned ON 2026-06-21.) Verify the live env var with
`gcloud run services describe halatuju-api` before asserting flag state — do not trust older log entries.**

**▶ JUST SHIPPED 2026-06-11 (b) — SARA≠STR fix + cockpit doc UX + in-cockpit viewer + HEIC (NO migration; retro
`docs/retrospective-cockpit-doc-ux-and-sara.md`; branch `fix/sara-not-str`).** **#5b SARA≠STR:** the Gemini
`source_type` now GATES `_str_currency` — a SARA-only Perdana Menteri letter (app #63) classified `unknown` →
`unconfirmed` whatever AI status was read; SARA "Layak" removed from STR approval words; blank/legacy source_type falls
through (existing approvals safe). **Cockpit:** per-doc-type tinted icons + standard labels ("STR proof"/"Mother's IC")
+ filename muted in brackets; the label IS the view-link (corner "View" dropped). **In-cockpit viewer**
(`components/DocViewer.tsx`): click a doc → embedded modal (img/iframe) — standardises "view, never download".
**HEIC→JPEG** server-side on upload (`apps.scholarship.imaging`; `pillow-heif`; `convert_heic_documents` command for the
existing files). Gates: 1015 scholarship + 1063 courses/reports pytest, 290 jest, parity 2486×3, next build clean.
**Post-deploy:** re-classify #63's STR (source_type='unknown'); `convert_heic_documents --apply`; watch the pillow-heif
install on the first build.

**▶ SHIPPED 2026-06-11 — deterministic label-anchored capture layer (Sprint 1: P0–P5 + #55 + UI; NO migration; branch
`sprint/deterministic-capture`; retro `docs/retrospective-deterministic-capture.md`).** `apps/scholarship/doc_parse.py`
`parse_by_labels(doc_type, text)` runs BEFORE Gemini in `run_field_extraction_for_document` (None → Gemini), tags
`vision_fields['capture']='deterministic'|'ai'`. CONSERVATIVE (None → Gemini unless it clearly recognises the doc — so
zero blast radius). Parsers, each VALIDATED ON REAL FILES (L86): **STR** (4 MySTR surfaces; `source_type` now
deterministic → retires the SARA→STR mis-pass #63 + closes the SALINAN-as-proof gap via `_str_currency`); **TNB elec**
(Caj Semasa/Baki Terdahulu/ALAMAT POS); **KWSP EPF** (JUMLAH SIMPANAN/CARUMAN; mis-slotted Borang EC → None); **JPN BC**
(child + both parents via the No.Kad-Pengenalan anchors; mononym-tolerant); **govt offer** (JPPKK/Matrik/Form6/IPG only —
deterministic identity name+12-digit-IC + clean programme; universities → Gemini). **#55** (`father_via_bc`+`father_link`):
a mononym student's father link via the BC, wired through `member_relationship_status` + both verdict routes. **UI**:
income-wizard card titles name the earner ("Father's salary slip"/"EPF statement"). Gates: 1059 scholarship + 1063
courses/reports pytest, 297 jest, parity 2496×3, next build clean. Deterministic capture IMPROVED on Gemini for several
digital PDFs it left blank + detects mis-slotted uploads.

**▶ SHIPPED 2026-06-11 — capture-layer follow-ons (Sprint 2; NO migration; retro
`docs/retrospective-capture-followons.md`).** Three items: **(1) IC leading-name-break fix** — `vision._extract_name`
gains `_LEADING_PARENTAGE`+`_preceding_givenname`+`_with_broken_name_parts`: when the chosen name line STARTS with a
parentage marker, the given name spilled onto the PREVIOUS line is prepended ("SARAWANAN"\n"A/L SUPRAMANIAM" →
"SARAWANAN A/L SUPRAMANIAM"). Shared across `ic`+`parent_ic`; both break directions regression-tested; **validated on the
2 real prod ICs** (#61/#31, rendered + Vision-OCR'd). **(2) P6 water-bill parser** — shared Malay labels (Bil Semasa /
Baki Terdahulu / Tunggakan); Air Selangor PDFs parse, other companies + photos defer to Gemini (SOFT signal). **(3)
Cockpit capture-confidence badge** — "Exact read" (deterministic) vs "AI read" (Gemini) on each doc row from
`vision_fields.capture`. Gates: 1067 scholarship + 1063 courses/reports pytest, ~297 jest, parity 2500×3, next build
clean.

**▶ NEXT — no roadmap sprint; do when inputs arrive:** optional backfill re-run of existing income docs (populate the
`capture` tag + deterministic `source_type` — outcomes already correct, robustness only); Tamil refine on the new
`salaryTitle`/`epfTitle` + `docsDrawer.capture.*` keys; **lawyer consent text** (+ `CONSENT_VERSION` bump); **real money**
(toyyibPay donate-in/disbursement/tranche, TD-075); reviewer assignment activation when a real reviewer is invited.

**▶ JUST SHIPPED 2026-06-11 — Verification-accuracy pass (5 live-testing fixes; NO migration; retro
`docs/retrospective-verification-accuracy-fixes.md`).** Upstream gaps from real-applicant review:
**(#4)** an optional wrong-person income doc (father's payslip on a mother-STR cluster; EPF) no longer hard-blocks
submission — only a compulsory salary-route slip gates (`services.document_red_blockers`); Gopal's
`income_proof_person_mismatch` copy is earner-aware (names the STR recipient, "optional on STR — none needed", advises
removal). **(#2)** `vision.relationship_name_match` folds Tamil/Indian romanisation (w↔v, doubles, trailing-h, 1-char
slip) — fixes *Saravanan/Sarawanan*; aliased into `income_engine` for all SAME-person cross-doc matches; **identity
keeps exact `name_match`** (strictly more lenient → never weakens identity; 0 false merges across 16 prod earners).
**(#3)** `vision.address_present` falls back to a strong street-token overlap (+`_address_tokens`) when a bill omits the
postcode (Swetha). **(#1)** the income wizard's roster→`income_working_members` default is now reactive (a `useEffect`
re-seeds until the student customises). **(#5)** `_str_currency` accepts an approved STR **without a year** as current
(MySTR pages print no year — "Semasa" = current; fixed 5/14 false `unconfirmed`); STR extraction gains a closed-set
`source_type` (letter/semakan_status/dashboard) + Tarikh-Kredit year reading. Gates: 1007 scholarship + 1063
courses/reports pytest, 282 jest, next build clean, i18n parity 2474×3; golden masters intact. **Deferred:** per-screen
type-aware Gopal "where to look" help (copy is generic across both screens for now); STR copy Tamil refine (TD-refine
queue).

**▶ NEXT — follow-ups only (no roadmap sprint; do when inputs arrive):** (1) **lawyer consent text** + `CONSENT_VERSION`
bump (re-attests everyone) — see decisions.md "Go live on draft consent text"; (2) **Tamil refine** (TD-105/108 etc.);
(3) **real money** — toyyibPay donate-in + disbursement-out + tranche (TD-075), a separate gated track; (4) when a
real **reviewer** is invited, assigned-only scoping activates — assign their applicants via the super-only assign
control. After any future threshold change: bump the cohort value + trigger the `rescore-pending` cron job.

---
_Historical sprint log below (archive — current state is the block above):_
- **✅ Sprint 1 DONE (F1, 2026-06-08, no migration):** public `/sponsor` marketing landing + public
  `GET /api/v1/sponsor/pool/count/` → `{count, enabled}` (count-only, flag-gated). `components/SponsorLanding.tsx`.
  TD-091 (Tamil refine), TD-092 (live click-through at go-live).
- **✅ Sprint 2 DONE (F8a, backend, 2026-06-08, migration `0049`):** student post-match onboarding. Accept
  (`respond_to_award`) now fires `send_award_confirmed_email` (NO sponsor identity, B4). New
  `complete_onboarding(...)` + `POST /api/v1/scholarship/applications/<id>/onboarding-complete/` → records a
  `student_onboarding_ack` consent (`CONSENT_VERSION` bumped → `2026-draft-4`), stores answers on the new
  `OnboardingResponse` model, stamps `onboarded_at` (refuses unless status `sponsored`). **Migration `0049`**
  (additive: `onboarded_at` col + `onboarding_responses` table) — apply migrate-first at deploy; **TD-093 = enable RLS
  on the new table at deploy.** Retro `docs/retrospective-sprint2-onboarding-backend.md`.
- **✅ Sprint 3 DONE (F8b, frontend, 2026-06-09, no migration):** `/scholarship/award` (accept/decline; guardian modal
  for minors) + `/scholarship/onboarding` (welcome → questions → finish wizard) + `getStudentAward`/`respondToAward`/
  `submitOnboarding` clients + an "accept your award" panel on `/scholarship/application`. Sponsor identity never shown.
  Naturally dark (no offer exists until a sponsor funds, needs the flag on). Stitch-approved (4 screens); built by a
  delegated subagent, orchestrator-reviewed + re-built (next build clean, 276 jest). Retro
  `docs/retrospective-sprint3-onboarding-frontend.md`. TD-094 (Tamil refine).
- **✅ Sprint 4 DONE (F3, sponsor notifications, ⭐ LAST must-have, 2026-06-09, migration `0050`):** `Sponsor.notify_frequency`
  (`realtime|weekly|off`, default weekly) + `last_digest_sent_at` + `SponsorProfile.realtime_notified_at`. New
  `sponsor_notifications` service + `send_sponsor_realtime` (hourly batch) / `send_sponsor_digests` (weekly) commands in
  `CronRunView.JOBS`; publish hook resets `realtime_notified_at`; emails built from `SponsorPoolDetailSerializer` only
  (allowlist-safe). `PATCH /api/v1/sponsor/notifications/` + a `/sponsor` toggle. **TD-095 = create 2 Cloud Scheduler
  jobs at deploy.** Retro `docs/retrospective-sprint4-sponsor-notifications.md`. **All four ⭐ must-haves now done.**
- **✅ Sprint 5 DONE (F6, reviewer profile, BE + FE, 2026-06-09, migration `0051`):** a reviewer's own credentials +
  contact profile as new cards on the existing `/admin/profile` page (reviewer/super only; viewer never sees them). New
  `ReviewerProfile` model in `apps/scholarship` — OneToOne to `courses.PartnerAdmin` (cross-app FK) with
  `highest_qualification, university, graduation_year, field_of_study, phone, address` (sensitive PII); NO password
  field. Self-scoped `GET/PATCH /api/v1/admin/reviewer-profile/` (own row only) + narrow `ReviewerProfileSerializer`;
  PII isolated in `reviewer_profiles` (own RLS at deploy), reachable by no outward serializer. `getReviewerProfile`/
  `updateReviewerProfile` + role-gated two-card section saved by the page's one Save button. Stitch-approved
  (`My profile — Reviewer Settings`). **Migration `0051`** (new model → apply via MCP + enable RLS at deploy, TD-098);
  TD-097 (Tamil refine). Retro `docs/retrospective-sprint5-reviewer-profile.md`.
- **✅ Sprint 6 DONE (F5, reviewer invite role selector, BE + FE, 2026-06-09, no migration):** `AdminInviteView` accepts
  `role` (super|reviewer|viewer; default reviewer, invalid→reviewer) + keeps `is_super_admin` in lockstep for super;
  `AdminListView` returns each admin's effective role. `/admin/invite` gains a role select + hint; admin list gains a
  role badge column. Trilingual `admin.role.*`/`admin.roleHint.*`. No migration (role field pre-existed). TD-099 =
  deferred first-sign-in profile-completion nudge. Retro `docs/retrospective-sprint6-reviewer-invite-role.md`.
- **✅ Sprint 7 DONE (F7, reviewer assignment/reassignment, BE + FE, 2026-06-09, migration `0052`):** super-only audited
  `POST .../applications/<id>/assign/` (body `{reviewer_id}`; null=unassign) via `services.assign_reviewer` — validates
  target is a reviewer (`not_reviewer`), gates first-assign on `is_ready_for_assignment` (`not_ready`), reassign/unassign
  any time, writes an `AssignmentEvent` per change + stamps `assigned_at`. Loose reviewer-gated `PATCH assigned_to` branch
  REMOVED (one audited path). Cockpit assign card super-only, reviewers-only dropdown, disabled-until-ready + reason.
  `admin.scholarship.assign.*`. **Migration `0052`** (new model → MCP + RLS at deploy, TD-100). Retro
  `docs/retrospective-sprint7-reviewer-assignment.md`.
- **✅ Sprint 8 DONE (F2, sponsor profile + "My students", BE + FE, 2026-06-09, no migration, ships dark):** derived
  `progress_state` on the allowlist card (`pool.derive_progress_state` stub: null until `sponsored`, then `on_track`;
  real band F9a) — flows through the existing wallet endpoint. FE "My students" on approved `/sponsor`: account+balance
  header + grid of anon student cards with colour-coded progress badge + an "awaiting acceptance" offered card.
  `getSponsorWallet` + `SponsorWallet`/`SponsorSponsorship` types; `sponsorPortal.myStudents.*`. Stitch-approved. Leak
  test green. TD-101 = donate/withdraw not wired (read-only). Retro `docs/retrospective-sprint8-sponsor-my-students.md`.
- **✅ Sprint 9 DONE (F9a, student in-programme results + progress + graduation relay, BE, 2026-06-09, migration `0053`,
  ships dark):** new module `apps/scholarship/in_programme.py` (one-way import `in_programme → pool → models`). **(1)** New
  `SemesterResult` model (semester, cgpa 0–4, graduated, myNADI-only `results_slip` link); `record_semester_result` gates
  `status='sponsored'`/CGPA. **`pool.derive_progress_state` now REAL** (graduated > CGPA≤2.0 needs_attention > CGPA
  semester_completed > on_track) — derived, single source of truth, slip stays myNADI-only. **(2)** New `promotional_use`
  consent (`grant_promotional_consent`, hard 18+ gate `minor_not_allowed`, NO guardian path); `CONSENT_VERSION` →
  `2026-draft-5`. **(3)** New `GraduationMessage` relay: `submit_graduation_message` → `scan_anon_for_identifiers` blocks
  leaks (`blocked` + fields) else `pending` → staff approve (re-scans scrubbed → `scrubbed_leak`)/reject → sponsor sees
  approved via plain allowlist `GraduationRelaySerializer` {ref, text, approved_at} linked to `pool.pool_ref` only.
  Endpoints: student `semester-results/`·`promotional-consent/`·`graduation-message/`; admin `graduation-messages/` +
  `.../<id>/review/`; sponsor `graduation-messages/`. +26 scholarship pytest (S8 `TestProgressState` extended). **Migration
  `0053`** (2 new models → MCP + contenttypes workaround + RLS at deploy, TD-102); TD-103 (results OCR deferred — CGPA
  student-entered). Retro `docs/retrospective-sprint9-in-programme.md`.
- **✅ Sprint 10 DONE (F9b, student in-programme + graduation relay — FRONTEND, 2026-06-09, no migration, ships dark):**
  the UI for F9a. **New page `/scholarship/in-programme`** ("My progress", Stitch-approved, shown when `status='sponsored'`):
  three cards — semester results (live progress pill + Add-result form, CGPA 0–4 / `bad_cgpa`), 18+ `promotional_use`
  toggle (greyed for a minor via server `is_minor`), graduation compose (a `blocked` submit shows an amber banner naming
  the scan-caught identifier fields → edit + resend; status chip pending→approved). **Sponsor `/sponsor`** gains a
  "Messages from students you supported" section (approved notes, anonymous, against `ref` only; 404-dark). New api
  clients `getSemesterResults`/`addSemesterResult`, `get/setPromotionalConsent`, `get/submitGraduationMessage`,
  `getSponsorGraduationMessages`. i18n `scholarship.inProgramme.*` + `sponsorPortal.graduationMessages.*` (parity 2399,
  +48; Tamil first-draft TD-105). `next build` clean (route 2.9 kB); 283 jest (render-only). TD-104 (slip-upload control
  deferred). Retro `docs/retrospective-sprint10-in-programme-frontend.md`.
- **✅ Sprint 11 DONE (F4, sponsor referral / invitation, BE + FE, 2026-06-09, migration `0054`):** an approved sponsor
  invites a prospective sponsor to the F1 landing. Owner decision: **FULL `SponsorReferral` guest-book + 60-day purge**.
  New `apps/scholarship/referrals.py` — `create_referral` (validates email `bad_email`, opaque code, best-effort invite
  email; duplicate pending invite idempotent), `attribute_referral` (a `/sponsor?ref=<code>` register flips the row to
  `joined`; self/unknown = no-op), `purge_expired_referrals` (scrub email/name + `expired` after 60 days). Trilingual
  `send_sponsor_referral_invite`. `GET/POST /api/v1/sponsor/referrals/` (approved only); `SponsorRegisterView` attributes
  `ref`; daily `purge-referrals` in `CronRunView.JOBS` + command (TD-107 = Cloud Scheduler job @deploy). FE `/sponsor`:
  invite form + "your invitations" list (Joined/Invited/Expired); `?ref` captured to `sessionStorage` (`KEY_SPONSOR_REF`)
  → threaded through register. `sponsorPortal.referrals.*` (parity 2416, +17; Tamil first-draft TD-108). +12 scholarship
  pytest; `next build` clean (`/sponsor` 7.21 kB); 283 jest. **Migration `0054`** (new model → MCP + contenttypes
  workaround + RLS @deploy, TD-106). Retro `docs/retrospective-sprint11-sponsor-referral.md`.
- **✅ Sprint 12 GO-LIVE DONE (2026-06-09) — the B40 Phase E/F sponsor programme is LIVE on prod.** Owner-authorised to
  ship with the CURRENT draft consent wording (lawyer-vetted text + `CONSENT_VERSION` bump to follow). The 25 held
  commits (Sprints 1–11) deployed in one batch: (1) migrations `0049`–`0054` applied **migrate-first** to prod via
  Supabase MCP (additive cols + 6 new tables) with **RLS enabled in the same transaction** on every new table, verified;
  (2) `git push` → both Cloud Build deploys SUCCESS (api rev `…00325`); (3) **`SPONSOR_POOL_ENABLED=true`** flipped via
  `--update-env-vars` (api rev `…00326`; count endpoint `enabled:true`); (4) **3 Cloud Scheduler jobs** ENABLED —
  `halatuju-sponsor-realtime` (hourly), `halatuju-sponsor-digests` (weekly Mon 09:00), `halatuju-purge-referrals` (daily
  03:00); (5) live smoke — new endpoints 401-not-500, web `/sponsor` 200. Resolved TD-093/095/098/100/102/106/107. Retro
  `docs/retrospective-sprint12-go-live.md`.
- **▶ NEXT — post-go-live follow-ups (no roadmap sprint; do when inputs arrive):** (1) **lawyer consent text** — when the
  vetted wording lands, sync it + bump `CONSENT_VERSION` (re-attests everyone), and apply any flow tweaks the lawyer
  prescribes; (2) **Tamil refine batch** (TD-091/094/096/097/105/108) — owner's eye on the trilingual sponsor/in-programme
  copy + the referral invite email; (3) **real money** (separate TD-075 track) — toyyibPay donation-in / disbursement-out
  / tranche schedule; (4) minor polish TD-101 (sponsor donate/withdraw wiring) + TD-104 (results-slip upload control).
- **Gotchas:** the sponsor programme is now **LIVE** (`SPONSOR_POOL_ENABLED=true` on `halatuju-api`; re-dark with one
  `--update-env-vars … SPONSOR_POOL_ENABLED=false`). **Prod is now at scholarship migration `0054`** (courses `0052`).
  i18n en/ms/ta parity; ≤2 deploys/feature; **`halatuju_api/CLAUDE.md` edits trigger an api rebuild on push** (root
  `docs/**` + `CHANGELOG.md` don't). Migrate-first still holds for any new migration (MCP CREATE TABLE + contenttypes
  workaround + RLS for new models). A family-redesign branch remains parked.

---

**▶ PARKED (other agent, unmerged) — "About your family" section redesign (branch `feature/family-section-redesign`, NOT merged/deployed;
plan `docs/scholarship/family-section-redesign-plan.md`, retro `docs/retrospective-family-section-redesign.md`).**
S1 backend + S2a foundation DONE & committed (`dbf19ba`/`2aa2bc4`/`55faf10`): structured family roster replacing the
four overlapping family fields with Father/Mother (name + coded profession) + a brother/sister/guardian pool + 2
sibling steppers + a *derived* first-in-family. `apps/scholarship/family.py` (40-option B40/lower-M40 profession
taxonomy, validated ~95% against real prod entries) + 7 additive model fields + migration **`0048`** (additive, NOT
applied — prod at `0047`); roster is the INPUT, `first_in_family`/`parents_occupation` are derived OUTPUTS so all
consumers work unchanged. **▶ S2 REMAINING (do next):** rebuild the Story "About your family" card per the approved
Stitch mockup (compulsory father/mother [name unless deceased/no-contact] + the pool + 2 compulsory blank-`—` steppers
+ derived note); i18n 40 professions ×3 (Tamil needs the owner's eye); a new `family_done` completeness part
(`services.application_completeness`) + required-field validation; income wizard (`ScholarshipDocuments.tsx`) — REMOVE
the sibling steppers (they move to Story) + PREFILL who-works/STR-earner from `family.earning_members`; cockpit Family
card → show the structured roster. Migrate-first `0048` via MCP at deploy. Phase 2 (later): roster feeds income earners
so the wizard drops its own "who works" step.

---

**✅ SHIPPED 2026-06-07 — Officer cockpit + verdict confidence-scale alignment (9 commits `c748284`→`dd40865` on `main`;
NO migration; retro `docs/retrospective-verdict-confidence-alignment.md`).** A live-testing pass over the officer cockpit
and the four-fact verification verdict:
- **Cockpit layout:** **About the student** now sits **above** Review & actions; the **Documents** drawer is fixed-height
  + scrollable; **Pre-interview flags** moved under **Caveats**; **Referees** hidden behind `SHOW_REFEREES=false`
  (handlers kept for a one-line re-enable; the consent status stays visible).
- **Verdict tiles = a Kent confidence scale (4 bands):** 🟢 Certain (`verified`) · 🔵 Probable (`review` **with ≥1
  verified value**) · 🟡 Unsure (`recommend`, or a review with no verified value) · 🔴 Can't verify (`gap`). Tiles show the
  estimative word + a legend (`TONE_BAND_KEY`, `verdict.band.*`). Blue/amber **swapped** so colour temperature tracks
  certainty; **"blue needs a green"** is enforced (`factTileTone(fact)` + `SOFT_EVIDENCE`: declarations / utility signals
  don't qualify a tile for blue).
- **Per-fact alignment (policy: don't pass weak evidence to manual review — bounce for re-upload):** **Identity** — the IC
  registered-address state is no longer a false-yellow caveat (it's a pre-interview flag); identity never auto-fails (the
  gate already blocks a NRIC mismatch / unreadable IC). **Academic** — a **slip-name mismatch is a hard stop** (red +
  fails `documents_done` → re-upload; only a positive mismatch blocks). **Pathway** — **no offer letter → red** (the offer
  was already a `consent_blockers` submission blocker; new `offer_letter_missing` verdict item + re-upload ticket).
  **Income** — **no income info → red** for consistency; the genuine "assess at interview" cases (informal/no-EPF,
  unprovable relationship, salary above the B40 line) correctly stay 🟡.
- **TDs resolved:** TD-082 (academic ticket → onboarding grades editor), TD-087 (reminders fire on the named calendar
  day, Asia/KL), TD-088 (`formatNric` de-dup), TD-090 (submit state-lift, no page reload). New reference doc
  `docs/scholarship/verdict-confidence-bands.md` (canonical category × colour map).
- Gates: **778 scholarship + 1037 courses/reports pytest + 274 jest** + next build clean; NO migration (scholarship still
  through `0042` on prod). **DB:** test account app 16 (ELANJELIAN) reset to shortlisted for re-testing earlier in the
  session. **▶ NEXT (queued):** Check 2 (5-day SLA); Check 3 (reviewer role); old/new cockpit consolidation; Tamil
  refine; income-arc live click-through (TD-070); TD-083/084/086/089; the open "Review & submit" auto-jump-vs-button UX
  choice.

**✅ SHIPPED 2026-06-07 — Input length-guard hardening (Story · Funding · Apply) (3 commits `b3f81d8`/`e343b96`/`048138a`
on `main`; migration `0042`; retro `docs/retrospective-input-length-guards.md`).** Prod incident (app #30,
POVIENTHIRAN): the "Your story" save failed with a generic *"Could not save your details"*. Root cause = the
**`parents_occupation`** field was a `varchar(255)` column with **no length guard on the form OR the API** (the Story
PATCH uses a plain `serializers.Serializer` + `save_application_details` writes via `setattr`, so neither inherits a
`max_length`); a real one-sentence answer overflowed 255 → Postgres `value too long` → the whole atomic save rolled
back. Fixed + audited the same trap everywhere a student types:
- **`parents_occupation` → `TextField`** (migration `0042`, backward-compatible widening, migrate-first via MCP). All
  free-text Story/Funding fields get an anti-spam cap **`STORY_TEXT_MAX = 5000`** on the form (`maxLength`) AND the
  serializer (clean 400). Closed the identical latent traps on **city** (`varchar(100)`) and, on **/apply**, **name** +
  **school** (free-text combobox → `varchar(255)` profile columns written by `sync_profile_fields`/`setattr`):
  `ApplicationCreateSerializer`'s write-only profile fields now carry `max_length` matching their columns.
- **Actionable error** replaces the blanket message: *"Your answer to "{question}" is too long. Please shorten it."*
  (en/ms/ta). The API client preserves DRF field-level 400s (`err.fieldErrors`); pure `firstTooLongField()` +
  `STORY_FIELD_LABEL_KEYS`/`APPLY_FIELD_LABEL_KEYS` resolve field → question label. (`contact_phone` was already safe —
  `formatPhone` caps to 11 digits; dropdowns can't overflow.)
- Gates: **1814 pytest** (777 scholarship + 1037 courses/reports) + **274 jest** + next build clean + i18n parity
  **2090**; scholarship migrations through **`0042`** on prod. **Carried note:** the same `name`/`school` are also
  editable via the onboarding "a few more details" path (different serializer) — NOT audited this sprint; audit if a
  similar report appears there. **▶ NEXT (queued, unchanged):** remove orphan `str_claimed_no_doc`; TD‑084 cleanup;
  Check 2 (5‑day SLA); Check 3 (reviewer role); old/new cockpit consolidation; Tamil refine; income‑arc live
  click‑through (TD‑070); the open "Review & submit" auto‑jump-vs-button UX choice.

**✅ SHIPPED 2026-06-07 — Review & submit flow live‑testing refinements (5 commits `1cc5f65`→`a533637` on `main`; NO
migration; retro `docs/retrospective-review-submit-flow.md`).** Built out the previously‑PARKED **post‑consent summary +
lock‑at‑Continue** and polished it from live testing:
- **Review is a post‑consent page, not a 6th tab.** `NEXT_STEP_ORDER` is back to the 5 wizard steps
  (quiz·story·funding·documents·consent); `ScholarshipReview` renders via a `reviewing` state reached only by the
  **"Review & submit"** CTA after consent. Back returns to the steps; Submit there is the **only** commit, then
  `handleConfirm` reloads into the post‑submit "received" screen.
- **Consent step is read‑only once given** — no dead‑end Edit link; it shows the **full consent text read‑only** + who
  gave it and when (new `consent.givenHeading`/`givenMetaSelf`/`givenMetaGuardian`).
- **"What happens next" moved to the post‑submit screen** and now reads review → **email query** (Check 2 / reviewer may
  ask for more docs/clarification *by email*, please reply) → **may‑call** → decision; the doubled email note de‑duped
  (`nav({email})`).
- **Submit‑flow copy unified on "submit"** across the "all set" banner, the review subtitle (with a scroll cue), and the
  button; banner no longer says "submit for review" (it opens the student's own read‑back); lock note reworded so it
  doesn't imply editing reopens after contact. Dynamic step counter; de‑duped doubled "Your application" title.
- FE‑only, no backend/migration. Gates: **758 scholarship + 1037 courses/reports pytest + 267 jest + next build clean +
  i18n parity 2084**; scholarship still through `0041` on prod. **▶ NEXT (queued):** remove orphan `str_claimed_no_doc`;
  TD‑084 cleanup; Check 2 (5‑day SLA); Check 3 (reviewer role); old/new cockpit consolidation; Tamil refine;
  income‑arc live click‑through (TD‑070). (Whether the "Review & submit" CTA should auto‑jump once all 5 steps complete,
  vs the current explicit button, is an open UX choice left to the user.)

**✅ SHIPPED 2026-06-06 — Income IC↔proof match + Gopal BC nudge + IC display format (2 commits `b0d851d`+`dbc8ac8`
on `main`; NO migration; retro `docs/retrospective-income-card-and-ic-format.md`).** Live-testing follow-up on the
income earner-IC card:
- **Earner IC now shows whether it MATCHES the income proof** — the point of uploading it. On a cluster (e.g. an STR in
  the mother's name) the IC No + Name read **"Matches the STR document" (green)** when they agree, red on a clash —
  `income_engine.student_income_ic_check` gains `proof_kind`/`proof_name_status`/`proof_nric_status` (cross-checks the
  earner IC against the cluster's STR / salary slip / EPF via `_cluster_proof_identity` + `vision.nric_match`).
- **Relationship moves OFF the IC card → it's the birth certificate's job.** New cluster verdict **`income_rel_doc_needed`**:
  once the IC is in and matches, Gopal nudges for the **birth certificate** (mother) / **guardianship letter** (guardian)
  as the last required step, then goes silent. Father needs none (patronymic).
- **Coach copy fixed (was wrong + contradicted gate v2).** `generate_document_help` was a hardcoded "father's payslip /
  not blocked" example regardless of the actual earner. The cluster coach now passes **non-sensitive member + document
  specifics** (`_specifics_block`; `IncomeClusterHelpView` builds `{member, income_doc, rel_doc}` labels) so it names the
  real earner + doc ("your **mother's** MyKad alongside her **STR document**"), and is honest these compulsory income docs
  **are required** (no more false "nothing's blocked"). Earner-IC labels: "from **your** IC" → "from **their** IC".
- **IC display standardised to `XXXXXX-XX-XXXX` everywhere shown** (`dbc8ac8`): student checklists (identity / income IC /
  income proof / STR) + officer cockpit (header NRIC, NRIC verify-row, Vision-extracted lines on identity + parent IC
  drawers) now wrap the raw OCR/stored value in the **existing shared `formatNric()`** (display-only, idempotent). Profile
  `maskIc` privacy masking + consent NRIC-match validation untouched; admin students list/detail already formatted.
- Gates: **1037 courses/reports + 758 scholarship pytest + 262 jest + next build clean + i18n parity 2024**; no migration
  (scholarship still through `0041` on prod). The firewall test now allows the `context` param (flat non-sensitive dict,
  never a model object — see decisions.md). **▶ NEXT (queued, unchanged):** ~~post-consent summary + lock-at-Continue~~
  (✅ shipped 2026-06-07); remove orphan `str_claimed_no_doc`; TD-084 cleanup; Check 2 (5-day SLA); Check 3 (reviewer
  role); old/new cockpit consolidation; Tamil refine; income-arc live click-through (TD-070).

**✅ SHIPPED + LIVE ON PROD 2026-06-06 — Application completion reminders + auto-close (2 commits `9b53810`+`f7f280d`;
migration `0041` applied migrate-first via MCP; retro `docs/retrospective-application-reminders.md`).** Escalating
reminder sequence for shortlisted-but-incomplete students + an auto-close at the end. Cadence from `reminder_anchor_at`:
**R1 +2d · R2 +9d · R3 +23d · R4/final +53d** ("5 days or we close"), then a 5-day grace → auto-close to a new
`expired` status. (The 55-min/48-h initial reveal was already live in cohort config.) `reminder_anchor_at` is a separate
clock knob (= shortlist invitation for new ones; the launch backfill set the in-flight cohort to *today−2d*).
`services.send_application_reminders` (idempotent, one stage/run; close gated on the final reminder having gone out
≥5d earlier, never raw days). The per-(cohort,profile) **unique constraint is now PARTIAL** (excludes `expired`) so a
closed student may restart. 5 trilingual emails (R1–R4 + closure) link to `/scholarship/application` + name **Cikgu
Gopal** + a human fallback `tamiliam@gmail.com` (temporary). `send_application_reminders` + `backfill_reminder_anchors`
commands; cron whitelist `application-reminders`. **OPS (live):** api rev `halatuju-api-00298-xhp`; daily Cloud Scheduler
**`halatuju-application-reminders`** (`0 9 * * *` Asia/KL) → the HTTP cron endpoint (mirrors `halatuju-vision-outage`,
`X-Cron-Secret` auth); backfill done (9 shortlisted-incomplete apps anchored, **R1 sent live**, all at `reminder_stage=1`).
Backend+email only (no FE). **1037 courses/reports + 753 scholarship pytest**; scholarship migrations through **`0041`**.
**▶ Known minor (TD): reminders land ~1 day after the nominal day-count** (anchor clock-time vs the fixed 09:00 tick →
floor rounding; harmless). **Support email is a personal Gmail for now** — swap to a branded address later (one line in
`emails.py`). **▶ Next auto-events (no action): R2 ~14 Jun · R3 ~28 Jun · R4 ~28 Jul · close ~2 Aug** (per cohort; any
student who completes drops off automatically).

**✅ SHIPPED 2026-06-06 — Gopal + Cockpit polish sprint (5 commits `d7e34eb`→`4fb5255` on `main`; NO migration; retro
`docs/retrospective-gopal-cockpit-polish.md`).** Live-testing follow-up after TD-085, all officer-cockpit + student
Gopal:
- **Utility-bill facts** (`d7e34eb`): the cockpit water/electricity row gains **Current** (billing period ≤3 months of
  the review date), **Reasonable** (combined water+electricity per-capita vs RM25/RM40 — one bill greys out with a
  "water/electricity only" note, high consumption stays amber not red), **Outstanding** (green only when arrears > the
  current charge), + an **orange note** when the account holder is neither the student nor any uploaded parent IC. All
  soft. `income_engine.utility_check` (+ `utility_reasonable` + billing-period parser); `officerCockpit.documentFacts`.
- **Verdict panel green-collapse** (`093a4ae`): a verified fact renders `● FACT ✓` with NO description + the evidence
  block hidden; amber/red keep the lead line + the full ✓-evidence/•-gap detail (where it's the story).
- **Gopal `ic_nric_misread`** (`72377d1`): on the student's OWN IC, name-match + IC-number-mismatch is its own verdict
  ("name matched, the number's likely a glare misread → re-upload cleanly"); both-fail keeps generic `nric_mismatch`.
- **Gopal lean tone** (`6d40af2`): the prompt now mandates diagnose→action→stop and BANS cheerleading openers/sign-offs
  (`HELP_PROMPT` + all 19 fallback strings en/ms/ta rewritten).
- **One Gopal per income earner** (`4fb5255`): income is the one CLUSTER fact, so the coach speaks once per earner at
  the foot of the cluster (father→after IC, mother→after BC, guardian→after letter; per ticked member on salary route),
  aware of the whole cluster + firing before the IC arrives. STR-currency + "add the IC" nudges folded in (precedence
  relationship→unreadable→STR stale→person-mismatch→missing-IC). `income_cluster_advice` rewrite + new
  `IncomeClusterHelpView` (`GET scholarship/income/<member>/help/`); FE shared `CoachCard` + `IncomeClusterCoach` +
  `clusterDocsFor`; per-file coaches suppressed for cluster docs. **Income-too-high deliberately NOT in the student coach**
  (officer/interview only — see decisions.md).
- Gates: **1037 courses/reports + 738 scholarship pytest + 262 jest + next build clean + i18n parity 2020**; no migration
  (scholarship still through `0040` on prod).

**✅ SHIPPED + DEPLOYED 2026-06-05 — Income Check-1 multi-earner arc COMPLETE (11 commits `e197209`→`668676b` on
`main`; migration `0040` migrate-first; retro `docs/retrospective-check1-income-multiearner.md`).** The income fact is
now a full clinical check, both routes:
- **Salary route → multi-select** ("tick everyone who works": father/mother/guardian/elder brother/elder sister), each
  with their own IC + salary slip + EPF. `household_member` tags income docs (single-instance per `(doc_type, member)`);
  new `income_working_members` JSON. Siblings verify via the SAME student-IC patronymic (`father_relationship` reused —
  closed the borrowed-payslip hole, no extra doc); mother→birth cert, guardian→letter. Forced non-earner EPF dropped.
- **Per-document verification** (the Identity standard, with relationship semantics): every income IC / salary slip /
  EPF / STR is read for name + **NRIC** + amount + period and cross-checked against the **earner's own IC** (never the
  student). One **cluster-aware Cikgu Gopal** per member, anchored on their IC.
- **I4 per-capita amount gate (DONE, not deferred):** salary route goes `verified` only when the summed earner pay (from
  payslip gross, or ≈24% of the EPF monthly contribution) ÷ household size clears `per_capita_ceiling` (RM1,584);
  at/above → `recommend` + interview, never auto-reject. EPF monthly-contribution + utility-bill address/hardship soft
  signals (officer-facing, never gates). Birth-certificate + guardianship checklists surfaced.
- **STR route:** STR doc read for recipient + currency; a stale/rejected STR no longer auto-greens; green = the whole
  cluster adds up.
- Gates: **687 scholarship pytest + 250 jest** + `next build` clean + i18n parity **1930**; scholarship migrations
  through **`0040`** on prod. Deprecated (kept, drop later, TD-084): `earner_work_status`, `household_other_earners` +
  `q2/q3/q4/work` i18n keys.

**▶ TD-085 income gate + cockpit — RE-SCOPED to 2 sprints (2026-06-05). DROPPED: the document-first verdict (the route
stays AUTHORITATIVE — the strict gate below + the manual slotting obviate it) and the re-extraction backfill (the user
re-runs legacy docs by hand via the cockpit "Re-run" button). Full spec: `docs/scholarship/consent-gate-v2-plan.md`.**

**✅ S1 — Consent gate v2 SHIPPED + DEPLOYED 2026-06-05 (no migration; retro `retrospective-consent-gate-v2-s1.md`).**
The consent/submission gate is now route-aware + STRICT: **offer letter compulsory for all**; STR route → STR doc +
earner IC + (mother→birth cert / guardian→letter; father via patronymic, none); salary route → for EACH selected member,
their IC + **salary slip** (EPF no longer substitutes) + rel doc. Sourced from `income_engine.income_requirements` (ONE
source of truth → `services.income_doc_blockers`; the consent blockers and the wizard checklist can't drift). Per-member
salary slip promoted optional→compulsory (backend + `incomeWizard.ts` mirror). **"Never-block" now lives ONLY at the
officer/interview verdict — submission hard-blocks** (a family that can't produce a route doc can't submit, but is never
auto-rejected later). **Grandfathered**: the strict bar applies only to not-yet-submitted apps (keyed on
`profile_completed_at`); the 6 already-submitted keep the OLD looser bar (`revert_if_profile_incomplete` never reverts
them on the new rules), resolved at Check 2 / interview. New blocker codes (`offer_letter_missing`/`str_missing`/
`salary_slip_missing`/`birth_certificate_missing`/`guardianship_letter_missing`/`income_incomplete`) en/ms/ta. Gates
**697 scholarship + 1037 courses/reports pytest + 250 jest + next build clean + i18n 1985**. (All 16 pipeline students
were hand-slotted onto income routes during triage — recorded in the plan doc; gate change guides the 9 shortlisted to
their route's docs, leaves the 6 grandfathered untouched.)

_S1 also got live-testing fixes (all deployed): offer-letter red `*` + dropped the redundant OPTIONAL pills; STR-route
income blocker order (STR doc before earner IC); and member-qualified consent blockers (`parent_ic_missing:<member>` /
`salary_slip_missing:<member>` → "Upload Father's IC", "Upload Mother's salary slip", per selection)._

**✅ S2 — Officer Documents-panel redesign SHIPPED + DEPLOYED 2026-06-05 (no migration; retro `retrospective-td085-cockpit-s2.md`). ▶▶ TD-085 COMPLETE.**
The cockpit Documents drawer now shows per-document **coloured fact-labels** (🟢/🟡/🔴 — only the facts THAT doc provides)
via new `officerCockpit.documentFacts`; the **relationship is movable** (father/sibling IC patronymic → on the IC; mother
→ BC; guardian → letter); the income section is **route+selection-aware Required→Optional** with red "Missing" placeholder
rows via `officerCockpit.incomeDocLayout`; the row badge **rolls up the fact colours**, fixing the "earner IC always
Unread" bug. `AdminApplicationDetailSerializer` now surfaces `income_route`/`income_earner`/`income_working_members` (3
fields, no migration); `admin-api.ts` declares the `*_check` + `household_member` + income fields. Gates **697 scholarship
+ 1037 courses/reports pytest + 258 jest + next build clean + i18n 2013**.

**▶ NEXT (queued — see `docs/scholarship/application-processing-pipeline-plan.md` MASTER + `consent-gate-v2-plan.md`):**
the post-consent **summary page + "lock at Continue"** (PARKED feature; full spec in the plan doc — note the consent lock
ALREADY exists, this just inserts a review step + moves the commit to Continue); **Gopal income doc-coach copy**; remove
orphaned `str_claimed_no_doc`; **TD-084 cleanup** (drop deprecated `earner_work_status`/`household_other_earners` cols +
`q2/q3/q4/work` i18n under expand-contract); **Check 2** (submission gap-queries + email + 5-day SLA); **Check 3**
(reviewer role + assignment gate); live click-through of the income arc (TD-070). Carried gotcha (S2 lesson): the data the
cockpit needs must be in `AdminApplicationDetailSerializer`, not just the student `ApplicantDocumentSerializer`.

---


**SHIPPED TO PROD 2026-06-04 — Check-1 live-testing fixes (5 commits, all deployed; retro `retrospective-check1-livetesting-fixes.md`):**
- **Orientation-robust SPM slip parse** (`c416c2e`) — gated de-rotation in `academic_engine._group_rows` (de-rotate by
  median word angle only when |θ|≥25°; upright untouched). Reads sideways/keystoned photos that used to fall to Gemini +
  transpose grades. 4 real slips frozen as fixtures (`tests/fixtures/slips/`).
- **Pointed Gopal slip advice** (`39510ac`) — `slip_grade_uncertain` (double-check) + `slip_skewed_unclear` (retake flat);
  anti-nag rule (skew advice only when skew coincides with a doubtful read).
- **Officer Academic false "could not be read"** (`d9e683b`) — use the slip's own `_slip_name_status`, not the
  supporting-doc `vision_name_match` column.
- **Two pathway false flags** (`e80b60c`) — Form-6 offer false-clash (enrolment-type words added to `_GENERIC_TOKENS`) +
  `offer_no_identity` for a readable notice with no name/IC.
- **Reason-code chain** (`e3d93c9`) — `offer_no_identity` added to `actionCentre.KNOWN_CODES` (the 4th wiring point).
- Totals: **~609 scholarship pytest + 231 jest** (deployed), i18n **1853**; scholarship migrations through **`0038`** on prod.

**SHIPPED TO PROD 2026-06-04 — INCOME fact Check-1 (the FOURTH + final fact), I1–I3 in one migrate-first deploy
(`9fa5ffe`+`d151bf6`+`a8bcd75`; retro `retrospective-check1-income.md`; plan `docs/scholarship/check1-income-plan.md`):**
- Guided **document wizard** in /application Documents → Household income (`IncomeWizard` in ScholarshipDocuments.tsx +
  pure `lib/incomeWizard.ts` mirroring the backend): Q1 STR-doc?→route · Q2 earner · Q3 work-status · Q4 other-earner ·
  burden steppers → **dynamic compulsory/optional checklist**. Earner-relationship proof: father=student-IC patronymic ·
  mother=**Birth Certificate** (new doc type, Gemini-read) · guardian=letter.
- `income_engine.py` (pure: `income_requirements` + `father_name_from_ic` + relationship checks) + rewired
  `verdict_engine._verdict_income` (verified/recommend/review/gap; **never-block** informal→`recommend` +
  `income_unverified_needs_interview` interview flag). **11 new reason codes** via the full 4-link chain.
- Migration **`0039`** (6 additive ScholarshipApplication fields + `birth_certificate` doc type) — **applied
  migrate-first via Supabase MCP** (Postgres `ALTER TABLE ADD COLUMN` ×6 + recorded `django_migrations` row; verified).
- **1680 pytest** (1037 courses/reports + 643 scholarship), jest 40, i18n parity **1900**; scholarship migrations
  through **`0039`** on prod.
- **▶ LIVE-VERIFY (TD-070, pending): click through the income wizard on /application** — walk Q1–Q4 + burden, confirm
  the dynamic checklist + a save round-trip + the officer Income tile recomputes. Not yet click-tested.

_(I1–I3 above were extended to the full multi-earner arc + I4 amount gate — SHIPPED 2026-06-05; see the top of this
section. The income-route document-first verdict + legacy backfill + cockpit redesign is the immediate ▶ NEXT, TD-085.)_
**Other queued:** PARKED post-consent summary page + lock-at-Continue (spec in `docs/scholarship/consent-gate-v2-plan.md`);
remove orphaned `str_claimed_no_doc`; TD-084 cleanup (drop `earner_work_status`/`household_other_earners` + `q2/q3/q4/work`
i18n); `/application` state machine + Check 2 (5-day SLA); reviewer-role sprint (Check 3); old/new cockpit consolidation;
Tamil i18n refine; STPM positional slip parser (parked); live click-through of the income arc + the new cluster Gopal
(TD-070). _(Gopal income doc-coach copy + lean tone = DONE this sprint.)_

**Carried gotchas:** TD-078 (subject map FE/BE dup), TD-079 (resolution sync writes on GET), TD-082 (academic confirm →
Documents), TD-083 (verdict-metrics + `overall` built, not surfaced in UI). Migrate-first via Supabase MCP (deploy does
NOT run `migrate`); new-model migrations need the TD-058 contenttypes workaround + RLS; confirm `Meta.db_table` before
any raw ALTER; Gemini JSON engines share `vision._call_gemini_json` (now image-capable), prose ones share
`profile_engine._call_gemini_text` — mock the seam, never a live call in CI.

---

**OTHER TRACK — Phase E (sponsor marketplace), paused at E3a.** Lawyer-gated; resume per the ordered list below.

Current state: v2.26.0 shipped (2026-06-01) — Phase E **Sprint E3a: sponsor wallet + match/consent BACKEND** (no real
money). The whole donate→fund-in-full→award→accept/lapse state machine on dummy data, behind `SPONSOR_POOL_ENABLED`
(OFF → dark). `Donation`+`Sponsorship` (migration `0034`, migrate-first); balance = donations − holding allocations;
1:1 full-or-nothing now, many-sponsor plumbing underneath; anonymity both ways (tested). E2 (the pool, backend+frontend)
also done + dark. 1452 pytest + 183 jest; golden masters intact; courses migrations through `0052`, scholarship through
**`0034`**.

Pick one (recommended order):
0. **Lawyer review** of the anonymised-card content + the consent text + **the donation/award terms** (the donation is
   final/non-refundable-to-bank; the award conditions). This is the gate to flipping `SPONSOR_POOL_ENABLED` on AND to
   wiring real money (TD-075). Until then, E2/E3 ship dark on mocked money.
1. **Phase E Sprint E3b/E3c (TD-075) — the money + the rest of the flow.** Real **toyyibPay** donation-in + **disbursement**
   out + the **tranche schedule** (RM ×N, progress-gated release/withhold → withheld returns to balance) + the **lapse
   cron** (a scheduled `lapse_expired_offers`, mirror `release-decisions`) + the **E3 frontend** (sponsor wallet/donate/
   fund/my-students; student award-accept; admin award-amount/oversight/tranche). Gated on the lawyer + gateway account.
2. **Local smoke of E2/E3** (flag on + dummy data): seed an approved sponsor (mock-donate), set an award amount, fund a
   student, accept as the student (+ minor/guardian path) → confirm anonymity both ways + the balance maths. (Headless
   can't — TD-070.)
3. **Tamil refine** (~16 batches incl. `sponsorPool.*`/`anonProfile.*`); **TD-068** (contractual reject) / **TD-066**
   (remove TEMP box) / **TD-069** (STPM electives); live-verify E1/E1c + auth isolation (TD-070).

Gotchas: migrate-first via Supabase MCP (deploy does NOT run `migrate`); **a new-model migration (like `0031`) needs
the contenttypes/auth tables — applied via the TD-058 MCP workaround**; **check the model's `Meta.db_table` before
any raw/MCP `ALTER` — `StudentProfile` is `api_student_profiles`, NOT the Django default `student_profiles` (the
collision-causing legacy Streamlit `student_profiles` table was DROPPED 2026-06-01, TD-025 resolved — a mistaken bare
`ALTER student_profiles` now errors loudly instead of silently hitting a real table, but the `db_table` override
remains, so still confirm it)**; new tables need RLS (service-role-only pattern, deny-by-default); **the sponsor serializer
is an allowlist — never a denylist — so a new model field is invisible to sponsors until deliberately added**;
`ADMIN_NOTIFY_EMAIL` on `halatuju-api` powers the confirm + sponsor-interest + sponsor-register emails; Gemini JSON
engines share `vision._call_gemini_json`, prose ones share `profile_engine._call_gemini_text` — mock the seam, never
a live call in CI.
Deferred: **Phase E E2/E3** (anonymised pool → match→consent→sponsorship, lawyer-gated), **Phase F** (mentor),
non-Google student login. Full history below under "Sprint History".

## Vision (post-shortlist interview-driven profile)

Direction-setting note captured 2026-05-29: **`docs/scholarship/post-shortlist-vision.md`**. Four user types (student done; admin done + needs role categories; sponsor + mentor to do), funnel through interview + sponsor + in-programme, three-engine gap model (deterministic rules + Vision OCR + Gemini), two-stage profile (draft → interview findings → final), and the standardisation-over-exhaustiveness principle for the interview UX. Phased build A→F with **Phase A (deterministic anomaly engine) recommended as the first slice**. Read before scoping any post-shortlist work.

## Sprint History — B40 Programme (decision engine + apply-form rebuild → post-shortlist)

Phase 1 (apply → shortlist → decision emails → docs/referee/consent → AI sponsor profile + MyNadi admin)
is **live on `main`** (deployed 2026-05-23, migrations 0001–0006 + courses 0047 applied to prod). The
**redesign** reworks the decision flow + apply form. 6-sprint roadmap: `docs/scholarship/b40-decision-redesign-plan.md`.
On branch **`feature/b40-redesign`** (off `main`); **single deploy at S12**.

- **✅ S7 done (2026-05-23):** backend foundation — **soft-NRIC** (editable until admin-verified; unique only
  when verified; read-only on PUT/sync, claim-only; claim blocked once verified, 403 `nric_locked`), `coq_score`
  + `preferred_call_language` persisted, all new `ScholarshipApplication` intake fields. Migrations courses `0048`
  + scholarship `0007`. Backend **1091** tests green. See `retrospective-b40-sprint7.md` + `docs/decisions.md`.
- **✅ S8 done (2026-05-24):** deterministic decision engine — gates → academic floor (SPM 4A-+1B+ / STPM PNGK 2.9)
  → income (STR passes, else per-capita < RM1,584); **silent score at submit**, **delayed reveal +2h shortlist
  (invitation) / +48h decline (warm email)** via the scheduler. Migration scholarship `0008`. Backend 1093 tests.
  See `retrospective-b40-sprint8.md` + `docs/decisions.md`. (6 policy calls all settled; public criteria stay at
  the advertised bar, engine intentionally more lenient to accommodate near-misses.)
- **✅ S9 done (2026-05-24):** apply form ① — **About Me + My Family** now inline-editable, pre-filled, with
  required `*`+`i` tooltips and **commit-on-submit** (About-Me/Family fields sync to the profile via
  `sync_profile_fields`; NRIC commits via the validated claim path, never the payload). New: referring-org fixed
  dropdown (→ `referral_source` → `referred_by_org` FK), home state, phone, parent name/phone (→ `guardians`),
  preferred call language. Validation jumps to the offending tab; error banner moved out of the Support tab.
  **No new migration** (reused existing profile fields). Backend 1095 tests, frontend 44 jest, `next build` clean,
  i18n 1051-key parity. **Approved mobile build via local screenshot** (desktop deferred to S12 — user's call).
  See `retrospective-b40-sprint9.md`. Results/Plans/Support tabs untouched this sprint.
- **✅ S9b done (2026-05-24):** My Results "edit/add results" now routes through the **full onboarding**
  (`/onboarding/exam-type` → … → "a few more details") instead of `/profile`/`/quiz`; the **final onboarding step**
  is context-aware — entered from apply, its button is **"Save & return to application"** and routes back to
  `/scholarship/apply` (else → dashboard). In-progress About-Me/My-Family edits are **stashed/restored** across the
  detour via sessionStorage (`stashApplyForm`/`popApplyStash`/`hasApplyReturn`/`clearApplyReturn`, storage-injectable,
  SSR-safe; orphan marker cleared on normal apply visit). Frontend only; **44→49 jest**, build clean, i18n 1052-key
  parity; backend unchanged (1095). See `retrospective-b40-sprint9b.md` + TD-057.
- **✅ S10 done (2026-05-24):** apply form ② — **My Plans** (intends-tertiary gate checkbox; pathways multi-select
  chips; UPU radio + inline IPTS-out-of-scope note; field-of-study dropdown from the taxonomy; **top-3 from the
  student's saved courses** ranked by tap order; other-scholarships chips + free text) + **Support** (help radios
  Yes/No/Not sure, optional "anything else", required consent). Single `intended_pathway` → `pathways_considered`
  multi; `notes` → `anything_else`; `intends_tertiary_2026` kept (engine gate). Apply page fetches saved courses
  (exam-type aware) + field taxonomy on mount. **Frontend only** (all fields accepted by `ApplicationCreateSerializer`
  since S7). Post-submit "Application received" screen already works (S8 silent-score → status `submitted` → neutral
  received card, no auto-advance). 49 jest, build clean, i18n 1087-key parity; backend unchanged (1095). Mobile build
  approved via screenshot. See `retrospective-b40-sprint10.md`.
- **✅ S11a done (2026-05-24):** admin verify-&-accept + NRIC lock + mentoring. `AdminVerifyAcceptView`
  (`POST …/<id>/verify-accept/`): checklist NRIC/name/results/doc → sets `profile.nric_verified` (**locks** NRIC),
  stamps `verified_at`/`verified_by`/`verify_checklist`, advances **shortlisted → `accepted`** (new status); only a
  shortlisted app can be accepted. Mentoring toggle via PATCH on the admin detail. **TD-054 RESOLVED** — uniqueness
  enforced at this single point (409 `nric_conflict` if another profile has that NRIC verified). Admin
  `/admin/scholarship/[id]` has a Verify-&-accept checklist card + mentoring toggle. Migration `0009`. Backend
  **1100** tests, build clean, i18n 1101-key parity. See `retrospective-b40-sprint11a.md`.
- **✅ S11b done (2026-05-24):** applicant application states + login banner. `/scholarship/application` gains the
  **`accepted`** = confirmed card (distinct from the neutral received card; shortlisted still → follow-up). New
  self-contained **`ScholarshipBanner`** (`components/ScholarshipBanner.tsx`, self-fetches the caller's application;
  renders on the dashboard only when shortlisted/accepted, links to `/scholarship/application`; margin on the banner
  so no empty gap). Frontend only; build clean, i18n 1107-key parity; backend unchanged (1100), jest 49.
- **S12 split (2026-05-24): Vision OCR deferred to a post-launch fast-follow** (it's a soft assist; admin verify-&-accept
  is the real gate — user's call). Launch path: desktop responsiveness → gated deploy.
- **✅ S12a done (2026-05-24):** apply-form desktop responsiveness. On `lg`, `/scholarship/apply` is a two-column
  layout — left vertical step-nav rail (active highlighted, completed ticked) + the active section card; container
  widens `max-w-2xl`→`lg:max-w-4xl`; the mobile bottom tab bar is `lg:hidden`. Mobile unchanged. Contained to the
  page's layout shell. Application cards already fine centred (left as-is); `ScholarshipNextSteps` not touched
  (desktop pass later if needed). `next build` clean; jest 49; backend unchanged (1100); no migration/i18n.
  Desktop + mobile approved via screenshot. See `retrospective-b40-sprint12a.md`.
- **✅ S12b DONE — DEPLOYED TO PROD (2026-05-25).** `feature/b40-redesign` merged to `main` (release `55c2c36`);
  both Cloud Run services rebuilt + deployed (SUCCESS); health checks 200; live course-guide unaffected. Migrations
  courses `0048` + scholarship `0007/0008/0009` applied to prod **before** the push (zero-downtime, additive). Cohort
  `b40-2026` live; its thresholds corrected to the settled S8 values (legacy Phase-1 row had 5/3.0 → set to 4/2.9).
  Idempotent `seed_b40_2026_cohort` command added (1103 backend tests). See `retrospective-b40-sprint12b.md`.
  **Pipeline is functional but dormant — the site is not promoted.**
- **✅ DONE (2026-05-27) — decision-email scheduler wired.** Cloud Run Job `release-decisions` (api image →
  `python manage.py send_pending_decision_emails`, 2Gi/2cpu, env copied from `halatuju-api`) + Cloud Scheduler
  `release-decisions-15m` (`*/15 * * * *`, Asia/KL, OAuth via App Engine SA, ENABLED), mirroring the existing
  `sjktconnect-daily-check` job pattern in this same GCP project. Verified end-to-end (released a 2h-overdue shortlist
  invitation + a scheduler-triggered run succeeded). Run manually: `gcloud run jobs execute release-decisions
  --region asia-southeast1`. Submitted apps now reveal at +2h (shortlist) / +48h (decline) automatically. **Note:**
  the acknowledgement email already sends synchronously at submit — only the *delayed reveal* needed the scheduler.
- **✅ DONE (2026-05-27) — job auto-syncs on deploy (image).** The `halatuju-api` build trigger gained a 4th,
  **non-fatal** step `SyncReleaseJob` (after Build/Push/Deploy) that runs `gcloud run jobs update release-decisions
  --image <the just-built image>`. So every api deploy re-points the job to the current code automatically — no more
  stale-image bug (which bit the 2.3.1 email-link fix). It's `|| echo`-guarded, so a sync failure never blocks the
  service deploy. The step lives in the trigger's **inline build config** (no committed `cloudbuild.yaml`; edit via
  `gcloud beta builds triggers export/import`). **ENV is NOT auto-synced** (rare): after changing a service env var
  that the job also needs (e.g. `FRONTEND_URL`, DB password, email creds), mirror it onto the job manually:
  `gcloud run jobs update release-decisions --region asia-southeast1 --update-env-vars KEY=VALUE`. (Future option to
  kill staleness entirely: replace the job with a secret-guarded HTTP endpoint on the always-current service and
  point the scheduler at that instead.)
- Keep one existing prod app (`YOGASHINI KRISHNAN`, rejected, Phase-1 test era) — real person, kept on user's
  instruction (contact separately, not via the pipeline).
- **▶ IN PROGRESS: `/scholarship/application` (Step 4) REDESIGN** — 5-sprint, plan
  `docs/scholarship/application-redesign-plan.md`. **S1 ✅ (v2.4.0):** 5-tab shell (Quiz · Your story · Funding ·
  Documents · Consent; referee removed from student flow → coordinator verify-&-accept). **S2 ✅ (v2.4.1):** "Your
  story" guided Family+You section — 5 additive narrative fields (migration `0012`), story-complete = aspirations+plans.
  **S3 ✅ (v2.4.2):** funding reframed → "how you'd use the support" — `FundingNeed` + `categories`/`funding_note`/
  `programme_months` (migration `0013`, migrate-first), tick-only (NO total), "up to RM3,000", funding-complete = ≥1
  category; legacy amount columns now dead (TD-059). **S4 ✅ (v2.4.3, DEPLOYED 2026-05-28; web `…00216-6pt`,
  api `…00171-cjf`):** Documents tab reworked — **Required** (IC + results slip, each with explainer) vs **Optional**
  (combined income-proof card = any one of STR/salary_slip/EPF, multi-file; water bill; electricity bill; statement of
  intent; offer letter; photo). 4 new `ApplicantDocument` doc types via **choices-only migration `0014`** (no DDL —
  `django_migrations` row recorded on prod via MCP before push). `application_completeness` gains **`documents_done`**
  (IC + results slip both present); **`complete` deliberately unchanged** (still quiz+story+funding — the docs/consent
  gate lands in S5). `reference_letter` dropped from the student UI (kept in model choices for back-compat). i18n parity
  1227; **Tamil copy is a first draft pending the user's refine.** **S5 was SPLIT → S5a (applicant) ✅ + S5b (admin/AI)
  queued.** **S5a ✅ (v2.4.4, DEPLOYED 2026-05-28; web `…00217-7t7`, api `…00173-4nm`; NO migration):** completeness
  loop closed — `application_completeness` gains **`consent_done`** (an active `Consent` exists) and **`complete` now =
  quiz+story+funding+compulsory-docs+consent** (full 5-part rollup; supersedes S4's interim). Read serializer exposes
  **`notify_email`** (read-only). `ScholarshipNextSteps` now wires the real **Documents + Consent step ticks** (were
  hardcoded false since S4) and, when complete, shows a green **"You're all set!"** banner + a **"What happens next"**
  panel (3-step timeline: review → we may call you in your preferred language → decision by email + the exact comms
  email). i18n 1235 (Tamil first-draft). Progress "X of 5" + per-step ticks + desktop rail were already in S1.
  **S5b ✅ (v2.4.5, DEPLOYED 2026-05-28; web `…00218-xgw`, api `…00175-cdj`; NO migration):** admin records the referee
  at verify-&-accept — new PartnerAdmin endpoints `GET/POST …/applications/<pk>/referees/` + `DELETE …/referees/<ref_id>/`
  (reuse `RefereeSerializer`); the `/admin/scholarship/[id]` Referee card is now interactive (list + remove + add form);
  `addReferee`/`deleteReferee` admin-api helpers; i18n 1245. (The `Referee` model + student-self endpoint already existed;
  the redesign had removed referee from the student UI, leaving no admin path until now.) **Scoping finding → TD-060:** the
  AI sponsor-profile generator (`profile_engine.py`) references fields the profile-canonical refactor removed
  (`qualification`/`spm_a_count`/`household_income`/`stpm_pngk`) + legacy/dead ones — it would **error if invoked** (masked
  only because the programme is dormant). **S5c ✅ (v2.4.6, DEPLOYED 2026-05-28; web `…00219-8ck`, api `…00177-vm2`;
  NO migration; resolves TD-060):** `profile_engine._build_prompt` rebuilt to the current data model (profile-canonical
  academic/financial + "Your story" narrative + `categories`/`funding_note`/`programme_months` — no dead `total` — +
  referees) and made **language-aware** — prompt understands Malay/English/Tamil student input; `generate_sponsor_profile
  (application, language=None)` writes the profile in a target language (defaults to applicant locale en→English/ms→Malay;
  admin EN/BM selector on `/admin/scholarship/[id]`; **Tamil output deferred to Phase 2** — one prompt-param away). New
  `test_profile_engine.py` (8, pure builder + TD-060 regression); Gemini mocked, **no paid calls**. i18n 1246. **The
  applicant + admin Step-4 redesign (S1–S5c) is COMPLETE.** **TD-059 ✅ RESOLVED (v2.4.7, DEPLOYED 2026-05-28;
  api `…00179-v26`, web `…00220-7v9`; destructive migration `0015` applied via Supabase MCP under expand-contract
  ordering — deploy-first / DROP-after; 0 prod rows pre-drop, 9 dead columns gone, `funding_needs` now 7 cols).
  **Ship-day cost:** 3 deploys instead of 2 — two web type-check failures were waved through locally because `npm run
  build` was piped to `grep` and the pipeline's exit code was grep's, masking npm's non-zero (lessons captured). **No
  engineering work queued.** Pending: user to refine S4-docs + S5a-panel **Tamil copy** (fold into a deploy); optional
  admin-triggered **live (billable) Gemini** generation check; S13 Vision OCR (queued separately below). Trims locked:
  photo optional, funding capped/no-total, most docs optional.
- **S13 ✅ DONE (v2.5.0, DEPLOYED 2026-05-28; web `…00221-qzp`, api `…00182-q84`; additive migration `0016` migrate-first via Supabase MCP; Cloud Vision API enabled on `gen-lang-client-0871147736`; runtime SA `90344691621-compute` has `roles/editor` which covers `serviceUsageConsumer`).** `apps/scholarship/vision.py` — Cloud Vision `document_text_detection` on the IC upload; pure matchers (`nric_match` exact, `name_match` token-set after stripping `bin`/`binti`/`a/l`/`a/p` → `match`/`partial`/`mismatch`); auto-triggered on `doc_type='ic'` in `DocumentListCreateView`; admin re-run via `POST .../documents/<id>/re-run-vision/`. Server-computed `vision_nric_verdict` / `vision_name_verdict` on the serializer so the FE just renders (S5c lesson reapplied). `ScholarshipDocuments` shows a 4-variant chip below the IC row; admin verify card has a "Vision OCR (soft signal)" row with two pills, raw extracted values, declaration-name comparison, Re-run link. Consent text bumped to disclose automated OCR honestly. **Vision is a SOFT signal — never a hard block; admin verify-&-accept (S11a) remains the real identity gate.** Tested end-to-end with a real MyKad: read NRIC `710829-02-5709` correctly from BOTH front and back; soft-flagged the mismatch against the test profile's synthetic NRIC. **3 billable Vision calls all-sprint** (1 project smoke + 2 IC uploads), well inside free 1000/month tier. Tiny known polish (deferred): `_extract_name` heuristic can pick up MyKad header phrases (`PENDAFTARAN NEGARA` etc.) on a back-only upload — verdict still resolves correctly, only the raw displayed name is misattributed. Retrospective `docs/retrospective-s13-vision-ocr.md`.
- **S14 ✅ DONE (v2.6.0, DEPLOYED 2026-05-29; commit `4aca9ae`, web `…00228-…`, api `…00187-…`; no migration; backfills via Supabase MCP).** /profile schema consolidation + required address on /application — closes four /profile gaps the user surfaced after live-testing. **/profile family card:** `family_income` range dropdown → open RM input on `household_income` (same column /apply writes); `siblings` count → `household_size` (also shared with /apply). **/profile phone:** dead `phone` input dropped (the canonical `contact_phone` in Contact Details is the one synced with /apply). **/profile contact_email:** `ProfileView.get` falls back to the auth-user email when `profile.contact_email` is blank and reports it as verified (Google/Supabase already verified that mailbox); read-time fallback, DB row stays untouched; explicit user-set value still wins with its real verified flag. **/application Story tab:** new "Where you live" sub-card under Family with street + postcode + city; state stays read-only ("from your application"); one Save button — `save_application_details` writes the address to `application.profile.*` alongside the narrative. **Completeness rule now 6-part:** `application_completeness` gains `address_done` (street + postcode + city all non-blank); `complete = quiz + story + funding + docs + consent + address`; Story tab tick requires both narrative AND address. Existing shortlisted applicants (app #3 Elanjelian) must add their address to reach "complete". **Backfills on prod via Supabase MCP** (before push): `household_income` from `family_income` range midpoints (41 rows), `household_size = siblings + 2` (42 rows), phone-promotion no-op (all 6 dead-phone rows already have `contact_phone`), contact_email auto-default is read-time so no DB write needed. **TD-061 logged** (drop the three replaced columns next session under expand-contract; old columns kept this sprint for backward-compat during deploy). i18n parity **1276** keys × en/ms/ta (was 1263 → +13; Tamil first-drafts for the new keys queued for refine batch). Tests: 151/151 scholarship pytest + 106/106 jest (+3 backend, +4 frontend). 1 web + 1 api deploy (under budget). Retrospective `docs/retrospective-s14-profile-consolidation.md`.
- **S17 ✅ DONE (v2.9.0, DEPLOYED 2026-05-29; commit `84462c2`; migration `scholarship/0020` applied via Supabase MCP — choices-only, no DDL; no backfill).** **Minor consent flow hardening — working model for lawyer review.** Pre-S17 minor branch was a half-measure (student-voice consent body + free-text relationship + typed guardian name with no identity verification). S17 delivers a defensible end-to-end flow. **(1) Re-voiced consent text** for minors — new `scholarship.consent.textMinor` i18n block in full parent voice ("I am the parent or legal guardian of the named applicant… I confirm that I have legal authority to give this consent for the applicant."). **(2) Structured `guardian_relationship` dropdown** with 6 codes (father, mother, legal_guardian (court-appointed), grandparent, older_sibling, other_relative). **"Other" intentionally excluded** per user direction — if no fit, the right path is legal_guardian + letter. `ConsentCreateSerializer` rejects any value not in the structured list (400). **(3) `parent_ic` doc compulsory for minors** — new doc type on `ApplicantDocument.DOC_TYPES`; auto-Vision-OCR'd on upload (reuses S13 pipeline); backend blocks consent POST with 400 `parent_ic_required` if missing. **(4) `guardianship_letter` doc compulsory for non-parent guardians** — pragmatic acceptance per user: court-issued guardianship order OR parent's written authorisation letter (both count; lawyer will tighten if needed). Backend blocks consent POST with 400 `guardianship_letter_required` when `needs_guardianship_letter(relationship)` is true and the doc isn't uploaded. **Completeness now 7-part** — `application_completeness` gains `guardian_docs_done` (adult trivially true; minor requires parent_ic, and if non-parent relationship also guardianship_letter). **2 new anomaly rules** extend S16's engine: `parent_ic_name_mismatch` (Vision-OCR name on parent_ic vs typed guardian name) + `parent_ic_underage` (Vision-OCR NRIC on parent_ic indicates age < 18 — the "guardian" is themselves a minor). **`CONSENT_VERSION` bumped** `2026-draft-1` → `2026-draft-2`. **Prod check: 0 existing consents** (programme still dormant) → bump is purely forward-looking; no real users need re-attestation. **Admin verify-&-accept card** gains a "Parent/guardian IC (Vision OCR)" row when present (extracted NRIC + name + address + Re-run link). **Defence-in-depth**: backend enforces doc prereqs at consent POST; FE pre-checks and shows amber warnings before submit. **Soft spot acknowledged in retro**: relationship dropdown is on Consent step (5), upload widget on Documents step (4); student picking "grandparent" at consent and discovering the letter requirement does one back-and-forth round trip. Acceptable for lawyer demo; revisit if real-use feedback shows friction. **Migration `0020`** = choices-only, no DDL; applied as direct `INSERT INTO django_migrations` via MCP per the TD-058 workaround. i18n parity **1356** × en/ms/ta (+20 keys). **Tamil-pending queue is now 9 batches / ~110+ strings** — especially worth a refine session before lawyer review since the consent text IS the artefact being legally evaluated. Tests: **1224 backend** pytest (+13) + **112 jest** (+2). **1 deploy** (under budget). Retrospective `docs/retrospective-s17-minor-consent-flow.md`. **3 design decisions logged**: pragmatic letter (court order OR parent letter), view-time enforcement with FE pre-check (defence-in-depth), no "Other" in relationship dropdown.
- **S16 Phase A ✅ DONE (v2.8.0, DEPLOYED 2026-05-29; commit `886968e`; no migration; no backfill).** First slice of the post-shortlist vision (`docs/scholarship/post-shortlist-vision.md`). New `apps/scholarship/anomaly_engine.py` — pure module with 10 `_detect_*` rules registered in a `_DETECTORS` tuple + a `detect_anomalies(application)` aggregator returning JSON-ready `{code, params}` dicts. No LLM calls, no model writes. The 10 rules (user-calibrated): `vision_nric_mismatch`, `vision_name_mismatch` (off S13 OCR); `address_state_mismatch` (Vision-OCR'd state vs `profile.preferred_state` with W.P. prefix normalisation); `jkm_high_income` (receives_jkm + income > RM3000, question reframed for disability/caregiving); `household_size_one`; `first_in_family_with_siblings_studying` (question preempts school-vs-university); `funding_other_without_note`; `declaration_name_mismatch` (token-set via `vision.name_match`); `str_claimed_no_doc` (new); `device_in_funding` (new, RM 3,000 won't cover a laptop alone). **Three rules deferred to Phase B** (need Gemini multimodal): utility-bill amount vs household size, SOI content-derived questions, "wrong" supporting doc detection. **Admin UI** (`admin/scholarship/[id]/page.tsx`): new "Pre-interview flags" card above verify-&-accept; amber list, fact + asked question per entry, count chip header, empty state *"No automated flags. Use your judgement during the interview."* **Backend wiring**: `AdminApplicationDetailSerializer` adds `anomalies = SerializerMethodField`. Read-only, computed per GET. **Frontend type**: `AdminAnomaly { code, params }` + array on `AdminScholarshipDetail`. **Anomaly serialisation pattern**: backend returns `{code, params}` only — FE resolves `scholarship.admin.anomaly.{code}.{fact,question}` from i18n with param interpolation (locale-agnostic server; copy edits land via web-only deploy). i18n parity **1336** × en/ms/ta (+26 keys: 5 UI scaffolding + 10 facts + 10 questions + 1 askLabel). Tests: **1211 backend** pytest (+23: per-rule + integration shape) + 110 jest (unchanged — admin UI is render-only, covered by `next build` typing not jest). **1 deploy** (under budget). Live preview for app #3 (Elanjelian, shortlisted): expected 2 flags — `address_state_mismatch` (IC: KEDAH vs profile: Putrajaya) + `str_claimed_no_doc`. Retrospective `docs/retrospective-s16-anomaly-engine.md`. Decision logged. **Tamil-pending queue now 8 batches / ~85+ strings** — worth a single refine session before the next sprint. **▶ NEXT recommended:** Phase C (admin role categories + `InterviewSession` model + capture UI) — the unlock for Phase D Gemini v2 refine. Phase B (Gemini gap-spotting + 3 deferred deterministic rules) lower priority — validate deterministic engine with real interviews first.
- **S15 ✅ DONE (v2.7.0, DEPLOYED 2026-05-29; commits `69cb1d0` Vision-address surface + `0fb08a3` state-pickup + `4baae5f` taman-line + `2ee7d5d` single-instance-docs + `87404e1` post-shortlist-vision doc + `53afbad` Story-tab polish; migrations `scholarship/0018` + `scholarship/0019` applied migrate-first via Supabase MCP).** Composite sprint: four discrete pieces. **(1) Vision OCR — MyKad address surface.** Building on S13's NRIC+name OCR; new `_extract_address` helper uses postcode-anchor heuristic with state allow-list (13 states + 3 WPs) + parentage-marker filter (BIN/BINTI/A/L/A/P/S/O/D/O/@) to identify the name vs address lines. `ApplicantDocument.vision_address` (CharField 500), surfaced on the admin verify-&-accept card next to `profile.address` for eyeball cross-check. **No automated matcher** for address — interviewer flags mismatches manually (matches post-shortlist vision: surface evidence, don't automate judgement). End-to-end verified on real MyKad (Elanjelian): final output `C65B JALAN SEJATI, TAMAN SEMANGAT, 08000 SUNGAI PETANI, KEDAH`. **Took 3 deploys** to converge — pass 1 missed the state (sits BELOW postcode, walk stopped at postcode line); pass 2 captured state but dropped `TAMAN SEMANGAT` ("looks like name" filter too aggressive); pass 3 swapped filter to parentage-markers + extended up-walk. Lesson captured: OCR heuristics need real-document validation, not just synthetic unit-test fixtures. **(2) Single-instance docs replace on re-upload.** `DocumentListCreateView.MULTI_INSTANCE_DOC_TYPES = {str, salary_slip, epf}`; everything else (IC, results_slip, statement_of_intent, offer_letter, water_bill, electricity_bill, photo) sweeps existing rows + Supabase Storage blobs before creating the new doc. Explicit DELETE also sweeps Storage (was leaking blobs on every Remove). New `storage.delete_objects()` helper. UI label flips "Add more" → "Replace" for single-instance types. **TD-062 logged** for historical orphan Storage blobs from pre-fix Remove clicks (low priority). **(3) Post-shortlist vision doc.** `docs/scholarship/post-shortlist-vision.md` — four user types (student done; admin needs role categories; sponsor + mentor to do), funnel through interview→sponsorship→in-programme, three-engine gap model (deterministic + Vision + Gemini), two-stage profile (draft → interview findings → final), standardisation north star, phased build A→F. Recommended Phase A = deterministic anomaly engine. No code; durable artefact. **(4) Story tab polish on /application** (the headline S15 commit). Four UX items: checkboxes → slide Toggles (firstInFamily + Consent agreement) matching /apply; `siblings_studying: boolean` → `siblings_studying_count: PositiveSmallIntegerField` (migration `0019`; profile_engine prefers count, falls back to boolean); placeholder ghost text + collapsible `<details>` "Need ideas?" tips on all 6 open textareas (tone deliberately first-person + slightly imperfect so student thinks "I can write better"); `*` on required fields via shared `FieldLabel` extracted from /apply to `src/components/FieldLabel.tsx`; dropped "(Optional)" suffix everywhere. **TD-061 grows by one column** (`siblings_studying` joins the next-session contract batch). i18n parity **1310** × en/ms/ta (+34 keys; Tamil first-drafts queued — **Tamil-pending queue is now 7 batches / ~60+ strings**, worth surfacing as a single refine session before the next big sprint). Tests: **1188 backend** pytest (+19) + **110 jest** (+4). **5 deploys this sprint** (3 Vision-address tuning + 1 single-instance docs + 1 S15 polish) — 3-deploy heuristic-tuning loop was over the 2-deploy guideline but each pass was forced by real-data feedback the synthetic fixtures couldn't reproduce. Retrospective `docs/retrospective-s15-story-polish-vision-address.md`.
- **Gotcha (DEPLOY/MIGRATIONS):** the Cloud Run deploy triggers run **build → push → deploy only — they do NOT run
  `migrate`.** Apply migrations to prod **manually first** (additive migrations are backward-compatible, so the live
  old code keeps working), **then** push `main`. The migrate is run from a local checkout against prod (DB creds via
  `gcloud run services describe halatuju-api`; the service uses individual `DB_*` env vars, not `DATABASE_URL`).
- **Gotcha:** Django `AlterField` that only changes a column **default** does NOT rewrite existing rows — a
  pre-existing config row keeps its old value (this bit the cohort thresholds: 5/3.0 lingered after S8 changed the
  defaults to 4/2.9). After a default change, explicitly sync existing config rows.
- **Gotcha:** soft-NRIC **supersedes** the old "IC immutable" decision — uniqueness is verified-only now.
- **Gotcha:** pushing `main` triggers a CI/CD deploy (path filters `halatuju_api/**`, `halatuju-web/**`; root `docs/**`
  + `CHANGELOG.md` do NOT trigger, but `halatuju_api/CLAUDE.md` does).
- **Gotcha:** PII source docs in `docs/scholarship/` (`*.pdf|xlsx|txt`) are gitignored — real NRICs/names/financials. Never commit them.

## Known Issues & Future Work

See `docs/roadmap.md` for the full list of known issues and planned future work.

General rules (testing, deployment discipline, git, cleanup, British English) are in the workspace-level `CLAUDE.md`.
