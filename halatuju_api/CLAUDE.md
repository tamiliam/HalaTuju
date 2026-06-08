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
| `apps/courses/management/commands/validate_stpm_urls.py` | Dead link checker | No |
| `apps/courses/management/commands/audit_data.py` | Data completeness report | No |
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

## Next Sprint (as of 2026-06-08)

**▶ IN PROGRESS — "About your family" section redesign (branch `feature/family-section-redesign`, NOT merged/deployed;
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
