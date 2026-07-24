# HalaTuju Architecture Map

Last updated: 2026-03-14 (system audit — all counts verified)

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
├── views.py                       # 22 API endpoint classes (see endpoint registry below)
├── serializers.py                 # Grade key mapping (BM→bm, BI→eng, etc.), request/response serializers
├── urls.py                        # 21 URL patterns → /api/v1/
│
├── engine.py                      # SACRED — SPM eligibility checker (743 lines, golden master: 8283)
├── stpm_engine.py                 # SACRED — STPM eligibility checker (255 lines, golden master: 1811)
├── ranking_engine.py              # Fit scores, category/institution caps, credential priority (809 lines)
├── stpm_ranking.py                # STPM fit scores: CGPA margin, field match, interview penalty (127 lines)
├── pathways.py                    # Matric track + STPM bidang eligibility + fit scores (315 lines)
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
├── migrations/                    # 20 migrations (0001–0020)
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
│   ├── 0018_insert_preu_institutions    # Pre-U institution records
│   ├── 0019_rename_stpm_program_to_course # STPM "programme" → "course" rename
│   └── 0020_remove_stpm_db_column_workaround # Clean up db_column overrides
│
└── tests/                         # 21 test files, 387 tests collected
    ├── test_golden_master.py      # 1 — 50 students × all courses = 8283 baseline
    ├── test_stpm_golden_master.py # 1 — 5 students × all STPM = 1811 baseline
    ├── test_api.py                # 71 — eligibility, ranking, course detail, search, STPM integration, calculate endpoints
    ├── test_ranking.py            # 62 — fit scores, caps, pre-U scoring, tie-breaking
    ├── test_pathways.py           # 37 — matric tracks, STPM bidangs, grade helpers, fit scores
    ├── test_serializers.py        # 27 — grade mapping, normalisation, validation
    ├── test_quiz.py               # 24 — quiz endpoints + engine, multi-select, weights
    ├── test_profile_fields.py     # 19 — expanded profile, saved course, STPM fields
    ├── test_stpm_data_loading.py  # 18 — STPM CSV loader, 1,113 courses
    ├── test_stpm_engine.py        # 16 — CGPA calculator, grade comparison, eligibility
    ├── test_auth.py               # 15 — JWT enforcement (pre-existing failures)
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
| `Course` | `courses` | Master course catalogue (390 SPM + 6 pre-U = 396 rows) | name, level, field, source_type, merit_type, headline, description |
| `CourseRequirement` | `course_requirements` | Eligibility rules per course | 70+ boolean fields mapping SPM subject requirements |
| `Institution` | `institutions` | Training providers (838 rows) | name, state, district, category, indian_population |
| `CourseInstitution` | `course_institutions` | Course ↔ Institution junction | fees, duration, intake_month, hyperlink |
| `CourseTag` | `course_tags` | Personality profile per course | work_modality, cognitive_type, people_interaction, learning_style, environment |
| `StudentProfile` | `student_profiles` | User eligibility data | SPM grades, gender, nationality, exam_type, muet_band, STPM fields, income, siblings |
| `SavedCourse` | `saved_courses` | User bookmarks | course, student, interest_status |
| `AdmissionOutcome` | `admission_outcomes` | Track application results | course, student, status (applied/offered/accepted/rejected/withdrawn) |
| `PartnerOrganisation` | `partner_organisations` | Dual role: partner-referral org AND (since platform Sprint 1, 2026-07-15) the tenant Organisation record | code, name, per-language branding/persona/sign-off, sender emails, frontend_url, module_* flags. NB: `PartnerAdmin.org` = *referring* org; `ScholarshipCohort.owning_organisation` = *owning* tenant (D-8) |
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
| `/api/v1/courses/search/` | GET | CourseSearchView | Search with filters (text, level, field, source_type, state, qualification) |
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
| `/api/v1/calculate/merit/` | POST | CalculateMeritView | Server-side UPU merit calculation |
| `/api/v1/calculate/cgpa/` | POST | CalculateCgpaView | Server-side STPM CGPA calculation |
| `/api/v1/calculate/pathways/` | POST | CalculatePathwaysView | Server-side pathway eligibility + fit scores |
| `/api/v1/stpm/eligibility/check/` | POST | StpmEligibilityCheckView | STPM eligibility check |
| `/api/v1/stpm/ranking/` | POST | StpmRankingView | STPM fit scores + ranking |
| `/api/v1/stpm/search/` | GET | StpmSearchView | STPM course search (university, stream, text) |
| `/api/v1/stpm/courses/<id>/` | GET | StpmCourseDetailView | STPM course detail |

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

### App: scholarship (B40 Assistance Programme — financing extension)

```
apps/scholarship/                  # Phase 1: intake & profile engine (no money flow)
├── models.py                      # ScholarshipCohort, ScholarshipApplication
├── apps.py                        # ScholarshipConfig (no startup data load)
├── serializers.py                 # ApplicationCreate / ApplicationRead
├── services.py                    # Intake logic (count_spm_a_grades, resolve_open_cohort, create_application)
├── emails.py                      # Trilingual (EN/MS/TA) acknowledgement email
├── views.py                       # ApplicationListCreateView, ApplicationDetailView
├── urls.py                        # /api/v1/scholarship/applications/ (+ <id>/)
├── genuineness/                   # ONE home for all document-genuineness checks (2026-06-16)
│   ├── __init__.py                #   assess(doc_type, ...) — single entry point + re-exports
│   ├── bands.py                   #   shared probability → status bands (suspect/review/genuine)
│   ├── ic.py                      #   ic_genuineness (MyKad markers) — moved from vision.py
│   ├── supporting_doc.py          #   doc_genuineness (STR/BC/EPF) — moved from vision.py
│   ├── results_doc.py             #   probabilistic SIGNATURE scorer (SPM slip + certificate + BC/EPF/offer/STR)
│   ├── salary_doc.py              #   salary_genuineness — statutory-grammar cascade (2026-07-09, MODEL_VERSION 1.0.0)
│   ├── electricity_doc.py         #   electricity_genuineness — issuer identity + bill grammar (2026-07-10, MODEL_VERSION 1.0.0)
│   └── water_doc.py               #   water_genuineness — GRAMMAR-first, operator-as-bonus (2026-07-10, MODEL_VERSION 1.0.0)
├── doc_signatures.py              # back-compat shim → genuineness/results_doc + bands
├── sql/rls_policies.sql           # Deny-by-default RLS for the 2 new tables (apply before deploy)
├── migrations/0001_initial.py     # ScholarshipCohort + ScholarshipApplication
└── tests/                         # test_models.py (4), test_api.py (13)
```
**Genuineness (`genuineness/`):** every "is this document genuine?" check lives here behind `assess()`. IC + STR/BC/EPF
are multimodal "looks official?" reads; the results-slip/certificate check is a deterministic SIGNATURE-probability
scorer over the OCR text (+ a focused QR/crest visual read), soft-bands, calibrated on a labelled corpus. The result
(`vision_fields['authenticity']`) soft-caps the verdict (`verdict_engine`) and raises an officer flag (`anomaly_engine`);
it never blocks. `vision.py` keeps the shared OCR/Gemini plumbing and re-exports `ic_genuineness`/`doc_genuineness`.

**New tables (created in migration; applied to Supabase at deploy):** `scholarship_cohorts`,
`scholarship_applications`. PRD + roadmap live in `docs/scholarship/`. Phase 1 = 6 sprints;
Sprints 1-3 done. Sprint 3 added `shortlisting.py` (pure rules engine → A/B/FAIL),
`management/commands/send_pending_decision_emails.py` (delayed fail email), and 4 model fields
(`shortlisted_at`, `decision_email_sent_at`, `locale`, `notify_email`; migration 0002). (v2.19.0: the engine result
now also carries a rejection `category` — merit/need/ineligible — which `score_application` persists to
`rejection_category`; the admin buckets interview/contractual are set by `services.admin_reject`/`AdminRejectView`, and
each bucket maps to its own decline email via `emails.send_decline_email(category=…)`. 2026-07-21 adds a THIRD admin
bucket `incomplete` — `services.org_admin_reject`/`AdminOrgRejectView`, super/org_admin only, `shortlisted` only,
IMMEDIATE and irreversible (no cool-off), reason stored verbatim in `rejection_comments` but never emailed; it has
no template of its own so it falls through to the generic `FAIL_*` copy.) Sprint 4a
added the `FundingNeed` model (OneToOne → application, `funding_needs`, computed `total`), deeper-info
fields (`aspirations`/`plans`/`fears`/`justification`), a `PATCH` details endpoint, and a
`completeness` block on the read serializer (migration 0003). Sprint 5a added `ApplicantDocument`/
`Referee`/`Consent` models, `storage.py` (signed-URL private-bucket vault), and document/referee/
consent endpoints with a minor→guardian consent gate (migration 0004). Sprint 6a added the
`SponsorProfile` model, `profile_engine.py` (Gemini sponsor-profile drafting), and the MyNadi admin
API (`views_admin.py`/`serializers_admin.py`, reusing `PartnerAdminMixin`) under
`/api/v1/admin/scholarship/` (migration 0005). Sprint 6b added the admin console UI
(`src/app/admin/scholarship/page.tsx` + `[id]/page.tsx`, AI profile generate/edit/publish) and the
admin scholarship client functions in `lib/admin-api.ts`. **Phase 1 build complete (all 6 sprints).**

**Post-shortlist three-engine gap model (S13–v2.17.0):** `vision.py` (Google Cloud Vision OCR — IC NRIC/name/
address extraction + soft full-text name/address presence checks on supporting docs + the shared
`_call_gemini_json` seam + doc-assist field extraction, `vision_fields`), `anomaly_engine.py` (S16 — pure
deterministic `detect_anomalies` → `{code, params}` flags, no LLM), and `gap_engine.py` (v2.17.0 Phase B — Gemini
reads the typed narrative → 3–6 `{code, question, why}` interview gaps, `interview_gaps`). Profile draft + Phase-D
refine: `profile_engine.py` — `generate_sponsor_profile` (draft from the form) and `refine_sponsor_profile`
(v2: draft + submitted `InterviewSession` findings → `SponsorProfile.final_markdown`), both routed through the shared
`_call_gemini_text` seam. Phase C added `InterviewSession` (findings keyed to anomaly/gap codes) + `PartnerAdmin.role`.
All Gemini engines mock one seam in tests (`vision._call_gemini_json` for JSON, `profile_engine._call_gemini_text`
for prose) — no billable calls in CI. **Student-facing help (v2.20.0):** `help_engine.py` ("Cikgu Gopal") —
`generate_document_help(doc_type, verdict, *, first_name, target_language)` phrases an already-decided document
verdict into a warm 2-3 sentence coach note (reuses `_call_gemini_text`); `verdict_for_document` maps a doc's
soft signals to the verdict, mirroring the FE chip precedence. Served by `DocumentHelpView`
(`GET …/documents/<pk>/help/`, own-doc scoped). **Structurally firewalled** — the engine receives only primitives,
never an application/profile/score object (signature-asserted); it is the inverse wall to the admin-only gap-spotter.

**Per-org branding seam (Sprint 5, 2026-07-24):** `branding.py` is the single read seam for every rendered
brand literal — programme name, team sign-off, coach persona, sender identity, display domain — used by
`emails.py` and `help_engine.py`. A `PLATFORM` block holds today's BrightPath constants verbatim (byte-identical
output, enforced by 113 golden snapshots in `tests/test_email_branding.py`); a tenant resolves per the D3
fallback chain `org.col(lang) → PLATFORM.default(lang) → PLATFORM.default('en')` against the `PartnerOrganisation`
branding columns (line above). Topical aliases (`interview@`/`sponsor@`) stay platform-domain-only (D4). An
AST brand-guard (`tests/test_branding_guard.py`) scans `emails.py`/`help_engine.py` string constants for the
platform brand literals, allowing only `branding.py` to hold them. Decisions D3/D4/D6:
`docs/decisions.md` ("Per-org branding seam", 2026-07-24); retrospective:
`docs/retrospective-2026-07-23-sprint5-branding-email.md`. Backend only — no migration, `halatuju-web/` untouched.
**Sprint 6 (2026-07-24) extended the seam with 3 visual accessors** (`brand_colour`/`logo_url`/
`org_short_name`, each with a platform default) and a public read endpoint
`GET /api/v1/branding/<slug:code>/` (`views_branding.py`, AllowAny + throttle, exact key-set
snapshot-pinned, unknown codes → the platform payload) — the one way the frontend learns a
non-platform org's identity.

**Per-org branding seam, frontend half (Sprint 6, 2026-07-24):** `halatuju-web/src/lib/branding.ts` is the
FE's mirror of the backend seam — a `PLATFORM` block (today's literals verbatim, the FE's one sanctioned
literal home, guard-allowlisted), `resolveBranding(config|null)`, `interpolateMessage()` (extracted from
`i18n.tsx`, function-replacer closes a `$`-in-replacement hazard), `brandRamp(hex)` (computed 50–900 ramp
for a tenant colour), and `AUTO_TOKENS` (the 5 tokens auto-injected into every `t()` call, beneath any
explicit params). `branding-context.tsx`'s `BrandingProvider` (mounted in `providers.tsx`, outside
`I18nProvider`) fetches the Sprint-6-backend endpoint only when `NEXT_PUBLIC_ORG_CODE` names a non-platform
org — BrightPath/platform mode never fetches. Theme colours are ten `--brand-N` CSS variables in
**RGB-channel form** (not hex), because Tailwind's opacity modifiers (`bg-brand-500/10`) require it;
`<BrandLogo>` (new) replaces the 14 hardcoded `/logo-icon.png` sites. 18 message keys ×3 locales (en/ms/ta)
+ the ta-only `authGate.applyReason` interpolate to `{programmeName}`/`{orgShortName}`/`{personaName}`/
`{supportEmail}`/`{displayDomain}`; the legal pages (`terms/page.tsx`, `privacy/page.tsx`) swap only the
brand-mention JSX token. Guarded by `brand-guard.test.ts` (forbidden brand literals scanned across message
values + comment-stripped `src/**`, with documented allowlists and self-checking floors) and
`placeholder-parity.test.ts` (every locale's placeholders ⊆ en's ∪ `AUTO_TOKENS`). Byte-identity for
BrightPath is pinned by a pre-edit consent-snapshot test + a leaf-map diff (en 18 / ms 18 / ta 19 values
changed, 0 keys added/removed). Decisions: `docs/decisions.md` ("Per-org branding — frontend seam",
2026-07-24); retrospective: `docs/retrospective-2026-07-24-sprint6-branding-frontend.md`.

**Requests space — org-fenced work-request tracker (Platform Sprint 15, 2026-07-24, LIVE behind
`REQUESTS_ENABLED=1`).** `models.py` gains **`OrgRequest`** (table `org_requests`, migrations
`0111`+`0112`): org FK `PartnerOrganisation` PROTECT, `submitted_by` FK `PartnerAdmin` PROTECT, an
8-status flow (`submitted → triaged → quoted → approved → deferred → scheduled → done →
declined`), a `clarifications` JSON thread, owner-only `ai_draft_*`/`triage_note`, hours-only quote
fields (`quote_hours`/`quote_margin_pct`), and three optional Bugzilla-style scoping fields
(`component`/`urgency`/`steps_to_reproduce`, migration `0112`). **`org_requests.py`** is the service
layer — a `TRANSITIONS` table (single source of truth for the flow) + every transition action +
`run_ai_review` (through the sanctioned `contracts._gemini_generate` seam only, defensive JSON
parse, auto-run best-effort capped at 3; AI clarifying questions go straight to the requestee, the
hours estimate stays owner-gated). **Endpoints** under `admin/scholarship/requests/…` via
`_OrgRequestsBase` (16 endpoints, all classified in `test_org_fence.py`, `OrgRequest` in WATCHED);
**two allowlist serializers** with an exact-key-set snapshot test — the org-visible payload (19
keys) never carries `ai_*`/`triage_*`. **Frontend:** `src/lib/requestStatus.ts` (pure
statuses/tones/labels + `requestActionsFor`), `app/admin/requests/page.tsx` (rate-card panel +
submit form + list) and `app/admin/requests/[id]/page.tsx` (Q&A thread + owner triage/quote
controls), an Administration hub card + badge (hidden while the count probe 404s), i18n
`admin.requests.*` en/ms/ta. Decisions: `docs/decisions.md` ("Requests space", Sprint 15,
2026-07-24); retrospective: `docs/retrospective-2026-07-24-sprint15-requests-space.md`.

**Requests v1.1 — role-correct components, B40 sub-components, attachments (Sprint 15.1,
2026-07-24, LIVE, additive to Sprint 15 above; resolves TD-172).** `component` choices now derive
from a single tree, **`models.REQUEST_COMPONENT_TREE`** — `org_requests.VALID_COMPONENTS` and the
model's own choices are both built off it, and a consistency test ties the FE mirror
(`requestStatus.REQUEST_COMPONENT_TREE`) and the en/ms/ta i18n keys to the same tree (no
hand-enumeration anywhere). Super-only surfaces `students`/`course_data` were removed from the
choice set (role-verified against the submitter's own nav + backend 403s). `applications` gains an
optional **second-level sub-component** — 8 `applications_*` values (`_student_details`,
`_documents`, `_ai_prediction`, `_queries`, `_interview`, `_decision`, `_agreement`,
`_student_profile`) stored in the SAME `component` varchar(30) column with an **underscore**
separator (a dot breaks the nested i18n lookup); migration `0113` is choices-only, no DDL. New
model **`OrgRequestAttachment`** (migration `0114`, table `org_request_attachments`, RLS enabled)
lets a submitter attach up to 5 images (≤8MB each) to a request. Reuses the Requests space's
signed-URL pattern under a **NEW namespace** rather than the scholarship applicant-document vault
— storage key `requests/<org_id>/<request_id>/<uuid>` (`storage.build_request_attachment_key`;
`resolve_org_for_path` extended to resolve the org off this scheme for the download fence). Bytes
go browser→Supabase directly (never through Django, Rule 5); three endpoints on
`_OrgRequestsBase` (sign-upload/record/delete, org-fenced, classified in `test_org_fence.py`) with
every invariant test-proven (foreign-path rejection, count cap at sign AND record, images-only —
no pdf, cross-org signed URL → None, cross-org delete 404, flag-off 404). Org-payload allowlist
snapshot widened 19 → 20 keys (`attachments`); `ai_*`/`triage_*` leak tests still green. FE:
dependent-select sub-component picker (PathwayPicker pattern) + staged attachment upload on the
submit form and add/remove on the detail page while non-terminal. Decisions: `docs/decisions.md`
("Requests v1.1", Sprint 15.1, 2026-07-24); retrospective:
`docs/retrospective-2026-07-24-sprint15-1-requests-v11.md`.

**Verification verdict (the synthesis layer, branch `feature/verification-verdict`, S1–S2):** `verdict_engine.py`
(`build_verdict` → four facts Identity/Academic/Income/Pathway, each `{status, evidence[], unresolved[]}`; pure +
deterministic, **no LLM** — composes `_ic_identity_blockers`, `application_completeness`, the Vision matchers, doc-assist
verdicts and `detect_anomalies`) and `academic_engine.py` (S2 — `_SUBJECT_BM` mirrors `subjects.ts`; `read_slip` +
`compare_academics` = completeness + accuracy by normalised subject name). Surfaced via
`AdminApplicationDetailSerializer.verdict` as the "Verification verdict" scorecard above the Pre-interview flags.
S2 extended the results-slip doc-assist schema to `results: [{subject, grade}]` (grade read per subject).
**S3 — resolution tickets (the IBKR Action Centre backend):** `resolution.py` (`CODE_TO_TICKET` mapping +
idempotent, race-safe `sync_resolution_items` with auto-resolve + no-re-nag, `resolve_item`, `add_officer_item`) +
the `ResolutionItem` model (**migration `0036`**, table `resolution_items`, RLS deny-by-default; partial unique
`uniq_system_resolution_per_code`). Each unresolved verdict item → a discrete ticket closable by doc/explanation/
confirm; three codes deliberately excluded (`ic_service_down`/`grades_unverified`/`str_present_unverified`). Student
endpoints `scholarship/resolution-items[/<id>/resolve/]`; officer `…/<pk>/resolution-items/` +
`…/resolution-items/<id>/<action>/`; sync wired into doc upload/delete; `AdminApplicationDetailSerializer.resolution_items`
exposes the live open queue. S1–S2 reuse existing `vision_fields` (no migration); **S3 is the roadmap's first
migration**. **S4 — Student Action Centre (frontend):** `halatuju-web/src/components/ActionCentre.tsx` (the IBKR
queue at the top of `/application`, wired via `ScholarshipNextSteps`) + pure `src/lib/actionCentre.ts` (node-tested);
`getResolutionItems`/`resolveResolutionItem` + the `ResolutionItem` type in `lib/api.ts`; per-code student i18n
`scholarship.actionCentre.*`. doc=inline upload, explanation=reply, confirm=jump-to-tab; Cikgu-Gopal coach; all-done
state; additive/non-blocking. **S5 — Officer Review Cockpit (the roadmap's LAST sprint):** the admin
`/admin/scholarship/[id]` page becomes the two-stage hinge — verdict **tiles**, a **Caveats** panel (open
`resolution_items` + officer Ask/Resolve), a redesigned **Documents drawer** (grouped by fact; replaces the messy
flat list), and a sticky **Record-verdict** panel. Backend (additive, **migration `0037`**): 5 audit fields on
`ScholarshipApplication` (`ai_verdict_snapshot`, `officer_verdict`, `verdict_reason`, `verdict_decided_by`,
`verdict_decided_at`) + `AdminRecordVerdictView` (`…/<pk>/record-verdict/`; snapshots the AI verdict beside the
officer's, and optionally fires Phase-D `refine_sponsor_profile` for the final profile in one action) +
`AdminVerdictMetricsView` (`…/verdict-metrics/`) + pure `apps/scholarship/audit.py` (`compute_overrides`/
`override_metrics` = the AI override rate). FE pure `halatuju-web/src/lib/officerCockpit.ts`
(`factTileTone`/`groupDocumentsByFact`/`aiSuggestionFor`/`documentPill`, node-tested) +
`recordVerdict`/`getVerdictMetrics`/`raiseResolutionItem`/`actionResolutionItem` + audit/`AdminResolutionItem`
types in `lib/admin-api.ts`; admin i18n `admin.scholarship.{recordVerdict,caveats,docsDrawer}.*`. **Roadmap S1–S5
COMPLETE; the whole branch deploys next** (migrate-first `0036` new-model + `0037` additive; TD-058 + RLS). Plan:
`docs/scholarship/verification-verdict-plan.md`.

**Phase E — sponsor marketplace (E1, v2.22.0):** **Note the naming split** — `Sponsor` (the *account*: a
self-registering, admin-vetted real user; model in `apps/scholarship/models.py`, table `sponsors`, migration
`scholarship/0031`) is **distinct** from `SponsorProfile` (the AI-drafted *student* write-up sponsors will eventually
read). Sponsor endpoints: `views_sponsor.py` (`SponsorMixin`, `/api/v1/sponsor/register/` + `/me/`, allowlist
`SponsorSerializer`) and admin vetting in `views_admin.py` (`/api/v1/admin/sponsors/` list + `<id>/review/`).
NRIC-gate middleware whitelists `/api/v1/sponsor/`. `Sponsor` also carries `phone`/`source`/`consent_at`/
`consent_version` (migration `0032`) captured at registration. **Frontend (E1c, v2.23.0) — isolated sponsor auth
stack, mirroring admin:** `lib/sponsor-supabase.ts` (own `storageKey 'halatuju_sponsor_session'`; email/password +
Google + reset), `lib/sponsor-auth-context.tsx` (`SponsorAuthProvider`/`useSponsorAuth`, fetches `/sponsor/me`),
`app/sponsor/layout.tsx` (wraps the provider), `app/sponsor/login` + `app/sponsor/register` (full fields, pure
helpers in `lib/sponsorAuth.ts`) + `app/sponsor/auth/callback`. The `/sponsor` portal (`app/sponsor/page.tsx`) shows
sign-in → complete-details (Google/email-confirm gap) → pending/approved/inactive. The shared logged-out cluster is
`components/AuthButtons.tsx` (Log in ▾ + Sign Up), used by `AppHeader` + the landing nav. **The E1 `KEY_SPONSOR_SIGNIN`
student-client sign-in was removed** — sponsors never touch the student `AuthGateReason`/NRIC flow. E1 holds **zero
student data**; anonymised browsing (E2) is lawyer-gated.

**Phase E2a — anonymised discovery pool (v2.24.0, backend, flag-gated).** `apps/scholarship/pool.py` =
eligibility/alias/academic-band (a student is poolable iff `SponsorProfile.anon_published` AND an active
`share_with_sponsors` `Consent`). The sponsor-facing **anonymous** profile is a *generated* (not scrubbed) blurb:
`profile_engine.generate_anonymous_profile` + `_build_anon_prompt` (a SEPARATE prompt from the named `_build_prompt` —
no name/school/referees), stored in new `SponsorProfile.anon_*` columns (migration `0033`); admin generate→publish
gates it. **The hard safety boundary is the allowlist serializers** `SponsorPoolCardSerializer` /
`SponsorPoolDetailSerializer` (`serializers.py`) — plain `Serializer`s with explicit derived fields and **zero model
passthrough**, so a new model field cannot leak; `test_sponsor_pool.py` asserts no name/NRIC/address/phone/email/school
appears in any sponsor payload. Browse: `SponsorPoolListView`/`SponsorPoolDetailView` (`views_sponsor.py`,
`/api/v1/sponsor/pool/[/<id>/]`) gated by **`settings.SPONSOR_POOL_ENABLED` (default OFF → 404)** AND
`require_approved_sponsor`. Admin: `AdminGenerateAnonProfileView`/`AdminPublishAnonProfileView` (reviewer-gated). **TD-074b:**
`AdminPublishAnonProfileView` runs `pool.scan_anon_for_identifiers(text, profile)` and **blocks publish** (`400
anon_identifier_leak`) if the generated blurb contains the student's own name/school/city/NRIC/phone/email tokens — a
structural backstop on the one soft (generated-text) surface.
The whole pool is dark until the lawyer signs off (flip the env flag).

**Phase E2b — pool frontend (v2.25.0, dark deploy).** Sponsor browse: `app/sponsor/page.tsx` approved state fetches
`getSponsorPool()` → an anonymised cards grid, or (on the flag-off 404 / any error) degrades to the "coming soon"
shell — so the same dark deploy is safe on the frontend too. `app/sponsor/pool/[id]/page.tsx` = detail (summary +
the generated anon blurb via `react-markdown`). Admin: a teal "Anonymous profile" card on
`app/admin/scholarship/[id]/page.tsx` (Generate AI → preview → Publish/Unpublish + badge), wired to
`generateAnonProfile`/`publishAnonProfile` (`lib/admin-api.ts`); `getSponsorPool`/`getSponsorPoolDetail` in
`lib/api.ts`. i18n `sponsorPool.*` + `admin.scholarship.anonProfile.*`.

**Phase E3a — sponsor wallet + match/consent (v2.26.0, backend, mocked money, flag-gated).** Money is a **ledger, not
custody**: `Donation` (sponsor donates into myNADI — final, no bank refund) + `Sponsorship` (allocation: offered →
active/lapsed/cancelled). `apps/scholarship/sponsorship.py` is the service layer — `sponsor_balance` = donations −
holding allocations; `is_fundable`/`fund_student` (1:1 full-or-nothing, DB partial-unique `uniq_holding_sponsorship_per_app`);
`respond_to_award` (accept/decline; minor → guardian gate, reuses `services.record_consent` with
`consent_type='consent_to_sponsorship'`); `lapse_expired_offers`. `ScholarshipApplication.award_amount` (admin-set,
gates fundability, on the pool card) + new `sponsored` status (excluded from the pool). **Anonymity both ways:**
`SponsorSponsorshipSerializer` shows the anon student card (no identity); `StudentAwardSerializer` has **no sponsor
field**; admin `_sponsorship_dict` (back office) sees both. Endpoints: sponsor wallet/donate(MOCK)/fund/sponsorships/
cancel (`views_sponsor.py`, flag+approved gated); student `scholarship/award/` (`views.py` `StudentAwardView`); admin
award-amount + `admin/sponsorships/` (`views_admin.py`). Migration `0034` (new `sponsor_donations`+`sponsorships`
tables + RLS, migrate-first). **Real toyyibPay + disbursement + tranches = TD-075 (later, lawyer+gateway-gated).**

**Conditional Bursary Award Agreement (Phase 1, 2026-06-26, backend, flag-gated DARK `BURSARY_AGREEMENT_ENABLED`).** The
award-acceptance becomes a binding tri-partite contract. `apps/scholarship/bursary.py` = the agreement layer — the EN+BM
clause template (DRAFT banner), `render_agreement_html`, `agreement_sha256`, `generate_pdf` (pure-python `xhtml2pdf` →
`b40-documents` bucket), `guarantor_identity_check` (reuses the `parent_ic` Vision-OCR gate), `sign_agreement` /
`countersign_foundation` / `record_witness`. New `BursaryAgreement` model (`bursary_agreements`, OneToOne→application):
snapshots `rendered_html`, frozen particulars + four-party signatures, `binds`/`is_executed`/`status` props. **Parties:
student + parent/guarantor (surety) ↔ the Foundation (signatory from `FOUNDATION_SIGNATORY_*`); partner org = non-blocking
witness; the donor is NEVER a party or named** (anonymity preserved in the rendered doc + PDF). Signing wired into
`sponsorship.respond_to_award` inside the cool-off transaction (flag OFF = byte-for-byte unchanged). Endpoints:
`BursaryAgreementView` (student GET + signed PDF), `AdminBursaryCountersignView` (super-only), `AdminBursaryWitnessView`
(referring-org admin). Migration `0072` (new table + RLS, migrate-first). **Go-live blocked on two Phase-0 gates
(TD-140); parent-phone link = TD-141; real disbursement = TD-142 / TD-075.**

**Post-award bank-details capture (S7, 2026-06-29).** An `awarded`/`active` student's payout account, captured in the
**Action Centre** via upload-THEN-confirm. New `BankAccount` model (`bank_accounts`, OneToOne→application, RLS — financial
PII in its own table) + the `bank_statement` doc type, which rides the existing **document-assist** pipeline: Gemini
field-extracts {bank_name, account_number, account_holder} (`vision._FIELD_SCHEMAS['bank_statement']`), and
`vision._bank_verdict` decides deterministically — `ok` only if all three are present AND the **holder is the student**
(matched against `names[0]` only, never a guardian). `resolution.sync_bank_details_item` raises/clears a
`bank_details_missing` task (always student-visible, independent of the Check-2 flag); the upload never auto-resolves it
(`resolve_doc_items_for_upload` skips `bank_statement`) — it resolves when the student saves. `BankAccountView`
(`GET/POST /scholarship/bank-account/`) re-checks the **hard holder gate** server-side on the *confirmed* value (refuses
`bank_holder_mismatch`); `help_engine` Gopal coaches `bank_holder_mismatch` / `bank_details_unclear`. `_current_application`
spans the funded states so the funded student reaches the upload/Action-Centre surface. Migration `0081` (new table + RLS,
migrate-first). **Stored only — no admin/officer surface yet** (payout view = TD-148, with TD-075). FE: `BankDetailsTask`
in `ActionCentre.tsx`.

**Three isolated Supabase clients + the PKCE invariant (v2.23.1):** student `getSupabase` (default storage key, mounted
globally via `app/providers.tsx`), `getAdminSupabase` (`halatuju_admin_session`, mounted under `/admin/*`), and
`getSponsorSupabase` (`halatuju_sponsor_session`, mounted under `/sponsor/*`). **All three set `flowType: 'pkce'` — this
is load-bearing for session isolation.** With the supabase-js default (`implicit`), OAuth returns the session in the URL
hash and the globally-mounted student client reads admin/sponsor Google logins off `/admin/auth/callback` +
`/sponsor/auth/callback` into the student storage key (a real cross-scope bleed, fixed 2026-05-31). PKCE means the
session comes back as `?code=` exchangeable only with the verifier under the *initiating* client's key, so a
non-initiating client can't claim it. **Any new auth client must also use PKCE.** (One Google account = one Supabase
identity; "roles" are app-level rows — `StudentProfile`/`PartnerAdmin`/`Sponsor` — keyed by `supabase_user_id`.)

**Frontend (Sprint 2):** `halatuju-web/src/app/scholarship/apply/page.tsx` (single front-door
application form), `src/lib/scholarship.ts` (pure form helpers, node-tested in
`src/lib/__tests__/scholarship.test.ts`), `submit/getMyScholarshipApplications` in `lib/api.ts`,
and a new `'apply'` `AuthGateReason` in `lib/auth-context.tsx` + `components/AuthGateModal.tsx`.
Sprint 4b added `components/ScholarshipNextSteps.tsx` (post-shortlist 3-step checklist + funding/
deeper-info form), funding/details helpers in `lib/scholarship.ts`, and `updateScholarshipDetails`
in `lib/api.ts`. Sprint 5b added `components/Scholarship{Documents,Referee,Consent}.tsx` (signed-URL
upload + referee + consent flow with guardian fields for minors) as next-steps steps 4–6, plus the
document/referee/consent client functions in `lib/api.ts`.

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

### Design Principle: Thin Client

All calculation logic (merit, CGPA, pathway eligibility) lives on the backend. The frontend calls `/calculate/*` endpoints and renders results. No eligibility or scoring formulas exist in the frontend.

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
│   ├── grades/page.tsx            # Enter SPM grades + co-curricular score (calls /calculate/merit/)
│   ├── stpm-grades/page.tsx       # STPM: stream, PA + 4 subjects, MUET, SPM prereqs (calls /calculate/cgpa/)
│   └── profile/page.tsx           # Demographics (gender, nationality, state, etc.)
│
├── dashboard/page.tsx             # Main dashboard — course cards, merit lights, exam_type branching
├── quiz/page.tsx                  # 6-question career interest quiz
├── search/page.tsx                # Unified course search + filters (field, level, pathway, state, qualification)
├── course/[id]/page.tsx           # SPM course detail (requirements, institutions, save/apply)
│
├── stpm/
│   ├── [id]/page.tsx              # STPM course detail (stream badge, subjects, requirements)
│   └── search/page.tsx            # Redirects to /search?qualification=STPM
│
├── pathway/
│   ├── matric/page.tsx            # Matriculation eligibility by track + college listings (calls /calculate/pathways/)
│   └── stpm/page.tsx              # STPM (Form 6) pathway detail (calls /calculate/pathways/)
│
├── saved/page.tsx                 # Saved courses list
├── profile/page.tsx               # Student profile view/edit
├── settings/page.tsx              # Account settings (stub)
├── outcomes/page.tsx              # Admission outcomes tracker
├── report/[id]/page.tsx           # AI counselor report (markdown rendering)
│
├── about/page.tsx                 # About HalaTuju
├── contact/page.tsx               # Contact/feedback form
├── privacy/page.tsx               # Privacy policy
├── terms/page.tsx                 # Terms of service
└── cookies/page.tsx               # Cookie policy
```

**25 page files total. No error.tsx, loading.tsx, or not-found.tsx (using Next.js defaults).**

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
├── api.ts                         # HTTP client for Django backend (all endpoint wrappers incl. calculateMerit/Cgpa/Pathways)
├── supabase.ts                    # Supabase client init (auth, Google OAuth, OTP)
├── auth-context.tsx               # Auth React Context (session, token, profile hydration, localStorage)
├── i18n.tsx                       # Custom i18n context: t() function, locale switcher, localStorage
└── subjects.ts                    # Subject code → name mapping (60+ SPM + STPM codes)
```

**5 lib files. All calculation logic is server-side — no merit.ts, stpm.ts, or pathways.ts.**

### Static Data

```
src/data/
├── matric-colleges.ts             # 15 matriculation colleges (state, tracks, phone, website)
├── stpm-schools.json              # 6,639-line JSON: STPM schools with code, state, PPD, streams, subjects
└── stpm-schools.ts                # TypeScript interface wrapper for stpm-schools.json
```

### Content Modules (role-aware admin manual)

```
src/content/manual/                 # The /admin/guide (manual) + /admin/faq content, as typed
│                                     modules (one ManualChapter per file, stable deep-link anchors).
├── types.ts, index.ts             # Types + registry + PURE helpers (visibleChapters / defaultChapterSlug /
│                                     resolveTarget / manualRole) — role→content visibility, unit-tested
├── basics-*.tsx (×4)              # Shared Basics chapters (all roles)
├── role-*.tsx (×4)                # reviewer / qc / org-admin / general-admin (visibility per role;
│                                     org_admin + super see all role chapters)
├── help.tsx                       # Help group
└── faq.tsx                        # Audience-grouped Q&As + faq filter helpers
```

**Every capability claim traces to `docs/scholarship/role-matrix.md` (currency rule: a role-power
change updates its chapter + FAQ in the same commit). English only; shaped for ms/ta siblings.**

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
├── technical-debt.md              # Living doc: 52 items catalogued, 9 resolved (TD-001/002/007/015/017/018/019/020/050)
├── release-notes-v1.33.0.md      # Latest stable release notes
├── Course Detail Page.pdf         # UI design spec
│
├── retrospective-*.md             # 45 retrospectives:
│   ├── retrospective-sprint{1-20}.md          # SPM flow sprints (18 files)
│   ├── retrospective-stpm-sprint{1-8}.md      # STPM entrance sprints
│   ├── retrospective-v1.{25-33}.0.md          # Release retrospectives
│   ├── retrospective-post-s20-*.md            # Post-Sprint 20 polish
│   ├── retrospective-preu-courses.md          # Pre-U integration
│   ├── retrospective-visual-quiz.md           # Quiz redesign
│   ├── retrospective-ui-polish.md             # UI polish release
│   ├── retrospective-data-integrity.md        # Data integrity sprint
│   ├── retrospective-tech-debt-sprint4.md     # Tech debt sprint 4
│   └── retrospective-description-sprint.md    # Description sprint
│
├── plans/                         # Active & completed plans
│   ├── 2026-03-09-whatsapp-otp-plan.md                            # ACTIVE — Twilio WhatsApp OTP
│   ├── 2026-03-12-stpm-entrance.md                                # COMPLETED — 5 sprints
│   ├── 2026-03-14-td002-eliminate-frontend-duplication-design.md  # COMPLETED — design doc
│   └── 2026-03-14-td002-implementation-plan.md                    # COMPLETED — 12 tasks
│
└── archive/                       # Historical documentation
    ├── 2026-02-completed/         # 9 files: consolidation, institution sync, merit integration, etc.
    ├── audits/                    # 8 files: data audits, subject analysis, integration plans
    ├── ranking_logic.md           # Live reference — v1.5 ranking algorithm
    └── (+ quiz redesign iterations, old roadmaps, deferred plans)
```

---

## _archive/streamlit/ (Legacy)

Previous Streamlit prototype. **246 files, not actively developed.** Preserved for reference on data structures, original ranking logic, and historical decisions.

---

## Database — Supabase

**Project**: `pbrrlyoyyiftckqvzvvo` (Singapore region)

| Table | Rows | Purpose |
|-------|------|---------|
| `courses` | 396 | Master catalogue (390 SPM + 6 pre-U) |
| `course_requirements` | 396 | Eligibility rules (70+ boolean fields per course) |
| `institutions` | 838 | Training providers (212 original + 27 IPG + 15 matric + 584 STPM schools) |
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
│  Thin client — no calculations   │
└──────────────┬───────────────────┘
               │ /api/v1/* (all API calls)
               ▼
┌──────────────────────────────────┐
│  halatuju-api (Cloud Run)        │
│  Django 5 — gunicorn Docker      │
│  Region: asia-southeast1         │
│                                  │
│  Startup: Course+Req → DataFrame │
│  /calculate/* → merit/CGPA/paths │
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
  → Frontend calls /calculate/merit/ → backend returns student_merit
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
  → Frontend calls /calculate/cgpa/ → backend returns CGPA
  → stpm_engine.py checks eligibility (CGPA threshold, subjects, MUET band, mata gred)
  → stpm_ranking.py adds fit scores (base + CGPA margin + field interest - interview penalty)
  → Response: eligible_courses[] + ranked[]
```

### Pathway Flow
```
Student clicks pathway (Matric/STPM)
  → Frontend calls /calculate/pathways/ with grades + quiz signals
  → Backend calculates track eligibility + fit scores
  → Response: tracks[] with eligible flag + fit_score per track
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
| API Endpoints | 3 | 80 | Eligibility, ranking, search, calculate, STPM integration |
| Engine Logic | 3 | 88 | Ranking, STPM engine, STPM ranking |
| Pathways | 1 | 37 | Matric tracks, STPM bidangs, fit scores |
| Data Loading | 3 | 39 | CSV loaders, STPM data, pre-U courses |
| Quiz | 1 | 24 | Endpoints, engine, multi-select |
| Serializers | 1 | 27 | Grade mapping, normalisation |
| User Features | 4 | 47 | Auth (pre-existing failures), profile, saved courses, outcomes |
| Reports | 2 | 16 | Engine + views |
| Insights | 1 | 8 | Insights generation |
| **Total** | **21** | **387** | **Pre-existing auth test failures in test_auth.py** |

**Frontend: 0 tests.**

---

## Technical Debt

Tracked in `docs/technical-debt.md` — a living document with 52 items catalogued.

**Resolved (9):** TD-001 (STPM prereqs), TD-002 (frontend duplication), TD-007 (quiz lang bug), TD-015 (merit.ts), TD-017 (pathways.ts), TD-018 (bare except), TD-019 (duplicate imports), TD-020 (duplicate i18n keys), TD-050 (hardcoded debug)

**Remaining (43):** See `docs/technical-debt.md` for full list with priorities and dependencies.

**Top 3 remaining risks:**
1. TD-003: Zero frontend tests
2. TD-005: No standard API error response envelope
3. Auth test failures (15 tests, pre-existing JWT issues)
