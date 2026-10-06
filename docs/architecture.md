# HalaTuju — architecture (current state, v3.0.0)

Written at the v3.0.0 release cut (2026-10-06) as the release workflow's architecture review. It
describes the system **as it is**; how it got here is in `CHANGELOG.md` and `docs/sprint-history.md`.
Operating detail (deploy steps, env vars, gates) is in `halatuju_api/CLAUDE.md`; the domain rules the
code depends on are in `docs/domain-rules.md`.

## What changed since the last release (v2.0-rc, 2026-03-20)

v2.0-rc was a course-recommendation site: a Django API, a Next.js front end and one Supabase
database. v3.0.0 is that **plus a multi-tenant bursary platform**. Structurally:

- a third Django app, `apps/scholarship` (169 migrations, ~215 new routes), now larger than the rest;
- tenancy: **organisation → gift (programme) → intake year (cohort)**, with an organisation fence on
  every admin endpoint and a gift gate inside it;
- outside services the course guide never needed: Cloud Vision, Gemini (and OpenAI as a fallback),
  Brevo SMTP, Twilio (WhatsApp, Verify), Google Workspace (Meet, Drive, Sheets — keyless), Vircle
  (the eWallet that pays students), Cloudflare Turnstile, Sentry;
- scheduled work: Cloud Scheduler → a secret-guarded cron endpoint on the running api, plus one Cloud
  Run Job (`release-decisions`);
- the deploy is gated: both Cloud Build triggers run the test suites before anything is pushed, and
  code-standard budgets are tests inside that gate.

## The pieces

```
 Browser ──► halatuju-web (Next.js 14, Cloud Run, Node 24)
   │            student pages · /admin console · /sponsor portal
   │  Supabase Auth (3 PKCE clients: student / admin / sponsor) — sign-in only
   ▼
 halatuju-api (Django REST, Cloud Run, asia-southeast1)
   ├─ apps/courses      course guide: eligibility (golden masters), ranking, quiz, search,
   │                    profiles, IC claim, organisations, staff (PartnerAdmin), themes
   ├─ apps/reports      the AI counsellor report
   └─ apps/scholarship  the bursary platform (below)
        │
        ├─► Supabase PostgreSQL (Singapore) — one database, RLS on every table
        ├─► Supabase Storage — private `b40-documents` bucket (+ weekly GCS backup)
        ├─► Cloud Vision · Gemini · OpenAI (fallback)      document reading, drafting
        ├─► Brevo SMTP · Twilio WhatsApp / Verify           student, staff, sponsor mail
        ├─► Google Workspace via keyless DWD                Meet links, Drive filing, the relay Sheet
        └─◄► Vircle (Airtable webhooks)                     who to onboard ↔ which wallet

 Cloud Scheduler ──POST /api/v1/internal/cron/<job>/ (X-Cron-Secret)──► halatuju-api
 Cloud Run Job `release-decisions` (api image, follows each deploy) ──► send_pending_decision_emails
```

## The course guide (apps/courses, apps/reports)

- **Eligibility** is a hybrid engine: `CourseRequirement` rows load into a pandas DataFrame at start-up
  (`CoursesConfig.ready()`); `engine.py` (SPM) and `stpm_engine.py` (STPM) are pinned by golden
  masters — SPM 5,319, STPM 2,026. Matric/STPM pre-U tracks are `pathways.py`.
- **Ranking** (`ranking_engine.py`, `stpm_ranking.py`) adds fit scores from the quiz signals
  (`quiz_engine.py`, `stpm_quiz_engine.py`, RIASEC for STPM).
- **Catalogue upkeep** is manual and annual (MOHE e-Panduan scrapes, UP_TVET inventory); the
  read-only Course Data dashboard and its weekly health check show freshness and broken links.
- **Reports** (`apps/reports`) write a counsellor narrative with Gemini, OpenAI as the fallback.
- **Identity**: a student profile is keyed on the Supabase user; the IC claim is a LINK
  (`ProfileLoginAlias`) resolved in `SupabaseAuthMiddleware`, which sets `request.auth_sub` (who holds
  the token) and `request.user_id` (whose student data). `NricGateMiddleware` blocks data access
  without an IC.

## The bursary platform (apps/scholarship)

The student's road, and the module that owns each step:

| Step | What happens | Where it lives |
|---|---|---|
| Apply | The apply link names a gift (`?p=<code>`); the intake answer and ONE apply gate decide | `views.py` intake, `services/apply_gate.py`, `student_status.py` |
| Score | A silent deterministic shortlist at submit; the reveal email after an embargo | `shortlisting.py`, `send_pending_decision_emails` |
| Documents | Upload → stage → judge → promote; Vision OCR, deterministic parsers, Gemini fallback, genuineness signature models | `vision.py`, `doc_parse*.py`, `genuineness/`, `promotion.py`, `document_snapshot.py` |
| Income | Per-earner evidence, STR precedence, salary route, declared-wage ask | `income_engine/`, `income_shown.py`, `income_str_ownership.py`, `verdict_income_salary.py` |
| Verdict | Facts with confidence bands (Identity · Academic · Pathway · Income); versioned | `verdict_engine.py` (`VERDICT_ENGINE_VERSION`), `verdict_ladder.py`, `pathway_engine.py`, `offer_pathway.py` |
| Check 2 | AI clarify queries to the student, resolution items, the Action Centre | `check2_queries.py`, `resolution.py`, `help_engine.py` |
| Interview | Reviewer assignment, proposed times, booking, Meet link, reminders (email + WhatsApp) | `scheduling.py`, `meeting.py`, `whatsapp.py`, `review_sla.py` |
| Decide | Reviewer verdict → QC gate (accept / reopen / decline) → recommended | `services/`, `reopen.py`, `closure.py` |
| Sponsor | Anonymised pool, wallet credits with a maker/approver chain, funding, terms | `pool.py`, `sponsorship.py`, `sponsor_terms.py`, `views_sponsor.py` |
| Award | Offer email after a cool-off, Vircle onboarding, the bursary agreement (dark) | `award.py`, `vircle.py`, `vircle_airtable.py`, `contracts.py`, `bursary.py` |
| Pay | Payment runs per gift (maker → finance checker → approver), Drive filing, Vircle email | `payments.py`, `disbursement.py` |
| Spend | Vircle spending reports read from Drive, categorised, summarised for officers and sponsors | `spending_import.py`, `spend_category.py`, `spend_summary.py`, `spend_sponsor.py` |
| Bill | Usage meter, cost ledger, tenant invoices and receipts | `usage.py`, `platform_cost.py`, `invoicing.py` |

**The console** (`/admin`) is one route registry behind a scope sidebar, a breadcrumb with
organisation and gift switchers, and a command palette. Organisations configure their own
programme (requirements catalogue, document limits, interview grid, clocks, comms templates, apply
copy, theme with a contrast gate, Overview layout). Requests (`org_requests.py`) is the tenant's
channel to the engineer: forms, an AI triage, an engineer's analysis, owner-gated quotes.

**Emails** live in the `emails/` package; a golden master pins every rendered email in three
languages. Partner, sponsor and student comms each have a platform switch and a per-template switch.

## Tenancy and access

- **Organisation** (`partner_organisations`) owns gifts, staff, templates, themes and billing.
  Referral organisations are a different thing and never grant access.
- **Gift** (`scholarship_programmes`, code + aliases) owns intake years, the apply copy, the agreement
  template, payment runs and spending. **Intake year** (`scholarship_cohorts`) holds the academic
  thresholds and has four states, one final.
- **Roles** (`PartnerAdmin.role`): super, org_admin, admin, reviewer, qc, finance, partner. Sponsors
  are a separate identity. Fences: `_AdminBase` (`_org_scoped` / `_org_allows`), the gift narrowing
  (`?programme=`), assignment for reviewers. Full matrix: `docs/scholarship/role-matrix.md`; review:
  `docs/security-posture.md`.

## Data

- One Supabase PostgreSQL database for both products. RLS is on for every table (an event trigger
  switches it on at creation); the scholarship tables are deny-all to the public key and reached only
  through Django with the service role; the four advisory tables are read-only to students.
- Documents: private bucket `b40-documents`, mirrored weekly to the GCS bucket named by
  `DOCUMENT_BACKUP_BUCKET`. Daily database backups (Supabase Pro); no point-in-time recovery, by choice.
- Migrations are applied to production BY HAND before the code that needs them (the triggers never
  run `migrate`); `docs/releases/v3.0.0-migrations.md` lists every file.
- Rate limits use the database cache table `django_cache` (shared across instances).

## Scheduled work

All jobs are `CronRunView.JOBS` entries reached by Cloud Scheduler; each runs a management command
inside the live api. The ones that move students or money: decision emails, application and query
reminders, award offer emails (after the cool-off), sign-invitation emails, Vircle install emails and
the relay sheet (daily), bursary signing reminders, sponsor real-time and digest mail, monthly tenant
invoices, the lapse of expired offers, review nudges, interview reminders, the stuck-read sweep
(`reprocess-ic-vision`), the weekly document backup and the weekly course-data health check. Some
entries are one-shot doors (backfills, repairs) scoped by an env var and run by hand.

## Delivery

- **Gates:** api — `manage.py check`, `makemigrations --check`, `pytest -n auto`; web — `npm run gates`
  (typecheck, lint, i18n parity, jest) and `npm run bundle-budget -- --gate`. Both run in Cloud Build
  in parallel with the image build; red stops the push.
- **Code standards** are ratchets in two `code-standards.json` files: file and function size,
  duplication, skips, suppressions, unguarded mirrors, dependencies, the app boundary, the test
  factory, first-load JS per route, and the applicant-detail query budget (38).
- **Images:** the api installs `requirements.lock` (exact pins); the web builds on `node:24-alpine`
  and stamps `NEXT_PUBLIC_APP_VERSION` from the commit.

## Key files

| File | Role | Sacred? |
|---|---|---|
| `apps/courses/engine.py` | SPM eligibility | YES — golden master |
| `apps/courses/stpm_engine.py` | STPM eligibility | YES — golden master |
| `apps/courses/apps.py` | Start-up data load (DB → DataFrame) | Careful |
| `halatuju/middleware/supabase_auth.py` | Auth, the login alias, the IC gate | Careful — identity |
| `apps/scholarship/verdict_engine.py` | The verdict | Eligibility — owner rulings |
| `apps/scholarship/income_engine/` | Income evidence | Eligibility — owner rulings |
| `apps/scholarship/services/completeness.py` | `application_completeness` | ⛔ do not tidy |
| `apps/scholarship/payments.py`, `sponsorship.py`, `contracts.py` | Money and the agreement | Money — adversarial review |
| `apps/scholarship/views_admin/` | The console's endpoints (package, fenced) | No |
| `apps/scholarship/emails/` | Every email (golden master) | Careful |
| `halatuju-web/src/lib/messages.ts` | The one place catalogues load | Careful — weight |
| `halatuju-web/scripts/bundle-budget.js` | First-load JS budget | Gate |
| `halatuju_api/code-standards.json`, `halatuju-web/code-standards.json` | The ratchets | Never raise |

## Known structural debt

Seventeen files are still over 1,000 lines (TD-361: split `scholarship/views.py` and
`officerCockpit.ts` first); one English message file rides on almost every route (TD-360); production
lacks Django's bookkeeping tables and is managed by hand (TD-058); two applications to two
organisations at once wait for M2 (TD-353). The full list is the register's Open Items Index.
