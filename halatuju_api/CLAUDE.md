# HalaTuju API — Architecture & Operations

This is the operating manual: how the system is built, run, tested and deployed **today**, the rules
the gates enforce, and the current Next Sprint. It holds current state only. The sprint, batch and
incident notes that used to fill it are in **[`docs/sprint-history.md`](../docs/sprint-history.md)**,
word for word; the system map is **[`docs/architecture.md`](../docs/architecture.md)**; the deeper
domain rules (profile claim, apply gate, course data, document snapshot, income) are in
**[`docs/domain-rules.md`](../docs/domain-rules.md)**. Open debt: `docs/technical-debt.md` (Open Items
Index). Every ruling: `docs/decisions.md`. Release notes: `docs/releases/`.

## Overview

HalaTuju (halatuju.xyz, **v3.0.0**, 2026-10-06) is two products in one codebase. The **course guide**
tells a Malaysian SPM or STPM leaver which courses they qualify for, ranks them and writes a report
(golden masters: SPM 5,319, STPM 2,026). The **scholarship platform** runs a funder's bursary end to end:
apply, results and documents read by OCR and AI, a deterministic verdict, interview, QC, award,
sponsors, payments through Vircle, and an organisation's own console (tenancy: organisation → gift →
intake year). Django REST API `halatuju_api/` + Next.js 14 `halatuju-web/`, both on Cloud Run
(asia-southeast1), Supabase PostgreSQL + Storage + Auth (Singapore).

## Build-for-Tenancy Conventions (MANDATORY for all new work)

HalaTuju is becoming a multi-tenant platform (course selector = shared base; scholarship programmes = org-owned tenants; plan of record in `docs/plans/2026-07-14-platform-roadmap-draft.md` at the repo root). Until that lands, **every sprint must follow `docs/build-for-tenancy-conventions.md` (repo root)** so ongoing BrightPath work stops deepening the coupling: new tunables on `ScholarshipCohort` (not module constants), no new "BrightPath"/persona/URL literals, new admin endpoints through the `_AdminBase` gates, referral fields (`PartnerAdmin.org`, `referred_by_org`) NEVER used for access control, billable calls only through the existing seams. The full rules + review checklist are in that doc.

## Architecture

The whole-system map (services, apps, data, scheduled jobs, outside services) is
[`docs/architecture.md`](../docs/architecture.md). The course engine's own shape:

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

### Profile claim and the apply gate — the two identity rules (full text: `docs/domain-rules.md`)

- **⚠ NEVER RETURN THE HOLDER'S NAME.** `POST /api/v1/profile/claim-nric/` answers `{status: 'exists',
  channels: [...]}` — bare channel TYPES, never a name, a masked address or digits. A claim is a LINK
  (`ProfileLoginAlias`), never a move; `SupabaseAuthMiddleware` sets `request.auth_sub` (who holds the
  token — **staff and sponsor identity resolve on this**) and `request.user_id` (whose student data).
  Every step is audited in `ProfileClaimEvent`; the IC goes in that table and **never in an application
  log**. Revoke: `profile_claim.revoke_alias(alias_uid, by=…)`. Widen only in `claim_channels()`.
- **One application in play, ONE rule, on the server** (`apps/scholarship/services/apply_gate.py`,
  judged on the student-facing status). The web keeps no copy: `useApplyGate.ts` asks
  `GET /api/v1/scholarship/apply-gate/` and obeys. Deliberately stricter than the owner's
  per-organisation ruling on TD-337 until M2 (TD-353 — relax it WITH M2, never before). Embargoed
  declines are read through `student_status` (TD-349). Open edges: TD-348 (no database lock),
  TD-338, TD-339, TD-343, TD-351, TD-354.

## Deployment

| Component | Platform | Region | Service |
|-----------|----------|--------|---------|
| Backend | Cloud Run | asia-southeast1 | halatuju-api |
| Frontend | Cloud Run | asia-southeast1 | halatuju-web |
| Database | Supabase | Singapore | pbrrlyoyyiftckqvzvvo |

### What the api image installs and carries (H1, 2026-09-18)

- The Dockerfile installs **`requirements.lock`** — exact `==` pins, a freeze of what pip actually
  installed in the production image build of 2026-09-18. Two builds of one commit now install the
  same code. Refresh it deliberately, never as a side effect: the recipe is in the file's header.
- **`requirements.txt` stays** as the statement of intent — the allowed ranges and the reason each
  package is here. A new package goes in `requirements.txt` first, then into the lock.
- **`.dockerignore`** keeps the tests, the eval corpus, prose and local state out of the image.
  The Cloud Build trigger runs `docker build`, so `.dockerignore` is the file that counts —
  `.gcloudignore` does nothing here.

### GCP Project

`gen-lang-client-0871147736` (account: `tamiliam@gmail.com`)

### How a change reaches production

1. **A push to `main` IS a deploy request, and for HalaTuju it needs the owner's yes** (`push = deploy`).
   Two Cloud Build triggers run committed configs — `halatuju_api/cloudbuild.yaml` (files
   `halatuju_api/**`, ignoring `docs/**` and this file) and `halatuju-web/cloudbuild.yaml`
   (`halatuju-web/**`, ignoring `docs/**`). Root `docs/**` and `CHANGELOG.md` deploy nothing.
2. **The tests are the gate.** Each build runs its suite in parallel with `docker build`; Push and
   Deploy wait for both, so a red suite ships nothing. api: `manage.py check`,
   `makemigrations --check`, `pytest -n auto`; web: `npm run gates` then `npm run bundle-budget -- --gate`.
   Run the gate's OWN command lines locally first (see Testing). Never deploy more than twice for one feature.
3. **MIGRATE-FIRST. Triggers never run `migrate`.** Apply the migration to production BY HAND before
   the push (Supabase MCP or psql): render the Postgres DDL with the postgresql schema editor (local
   `sqlmigrate` renders SQLite) — the DDL and the ledger row are in each migration's docstring — then
   `INSERT INTO django_migrations (app, name, applied) …` in the SAME transaction. A choices-only
   migration needs only the ledger row. ⚠ After an `UPDATE` that touches a `DEFERRABLE INITIALLY
   DEFERRED` foreign key, run **`SET CONSTRAINTS ALL IMMEDIATE;` before `CREATE INDEX`** in the same
   transaction, or Postgres refuses the index (0163, 2026-10-03). The old image must stay safe
   between migrate and deploy: additive and nullable first, `NOT NULL` in a later migration (0163 → 0164).
4. **Reconcile the ledger before the push.** Compare every migration file with production's
   `SELECT app, name FROM django_migrations ORDER BY name` (read-only): a gap in the middle is the
   signal (0135 sat applied-but-unrecorded for a day in July). Release list: `docs/releases/v3.0.0-migrations.md`.
   Two sessions racing for one number: the second renumbers on rebase, and the ledger row is handed
   to the owner only once the number is settled.
5. **Eligibility, money and identity work gets an adversarial review BEFORE the push**, by an agent
   that did not build it (owner rule 2026-09-21; three user-reachable defects slipped past green gates).
6. **A push is a REQUEST.** Match your SHA in `gcloud builds list`, read the status, then check
   `status.latestReadyRevisionName` (never `status.traffic[0]` — this service carries a tagged revision
   at index zero). Only then say "live".
7. **Hotfix bypass:** run the trigger by hand with `_SKIP_TESTS=1` (command in each `cloudbuild.yaml`
   header); write the skip into the retro. **Rollback:** shift Cloud Run traffic to the previous
   revision (no build), or re-import the pre-H2 trigger exports in `docs/infra/`.
8. **Every gcloud command carries `--account tamiliam@gmail.com --project gen-lang-client-0871147736`**,
   and env changes use **`--update-env-vars`, never `--set-env-vars`** (it wipes the rest). Read a live
   value from `gcloud run services describe halatuju-api`, never from a settings default (the `VIRCLE_*`
   folder defaults are stale on purpose). The `release-decisions` Cloud Run Job follows the api image on
   every deploy (`SyncReleaseJob`) but NOT its env: mirror an env change onto the job by hand.
9. Scheduled work runs as **Cloud Scheduler → `POST /api/v1/internal/cron/<job>/`** with
   `X-Cron-Secret` (`CronRunView.JOBS`); a POST needs a body (`-d '{}'`) or the load balancer answers 411.
10. **When more than one agent is in the checkout:** declare the files you own in
   `AGENT-TERRITORY.log` (gitignored); stage explicit paths, never `git add -A`; build in a
   `git worktree` and push from it with `git push origin HEAD:main` — never check out `main` there.
   ⚠ A `node_modules` JUNCTION in a worktree must be removed with `[IO.Directory]::Delete('<path>')`
   BEFORE `git worktree remove`: a recursive delete walks into the real `node_modules` (happened 2026-10-05).

**Where documents go:** a new retrospective in `docs/retrospectives/`, release notes in
`docs/releases/`, sprint and incident history in `docs/sprint-history.md`, a domain rule in
`docs/domain-rules.md` — this file keeps current state only.

### Environment variables (Cloud Run `halatuju-api`)

Defaults live in `halatuju/settings/base.py` and `production.py`; each has a comment saying why.
**Secrets are named here, never written down.** Flags are OFF unless set to `1`/`true`.

| Variable | What it means |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `halatuju.settings.production` |
| `SECRET_KEY` | Django secret (production refuses the dev fallback) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | The database (production uses these, not `DATABASE_URL`; either one marks "real database") |
| `DATABASE_URL` | Alternative to the `DB_*` set (Supabase Session Pooler URI) |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | Comma lists; `CORS_ALLOWED_ORIGINS='*'` is refused |
| `SUPABASE_URL` | Supabase project URL — the ES256 JWKS check needs it |
| `SUPABASE_JWT_SECRET` | HS256 secret for legacy anon/service JWTs |
| `SUPABASE_SERVICE_ROLE_KEY` | Creates staff Supabase accounts (invite/resend); without it onboarding 500s |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | AI: Gemini primary, OpenAI the report fallback |
| `GOOGLE_CLOUD_VISION_API_KEY` | Cloud Vision OCR (also usable by the eval tools) |
| `CONTRACT_QUIZ_MODEL`, `APPLY_COPY_DRAFT_MODEL`, `REQUESTS_TRIAGE_MODEL` | The one model each job uses (no silent downgrade) |
| `GOOGLE_DWD_SERVICE_ACCOUNT` | The Workspace delegation account's EMAIL (`halatuju-meet@…`), **keyless** (TD-125): the runtime SA signs as it through the IAM Credentials API. Not a secret. Empty → Meet/Drive/Sheets do nothing |
| `MEET_ORGANISER_EMAIL` | The Workspace mailbox Meet, Drive and Sheets act as |
| `GOOGLE_MEET_SA_JSON` | **GONE** (TD-329, 2026-10-04): removed from Cloud Run, the key deleted in GCP, the code path deleted; setting it does nothing |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL` | Brevo SMTP. ⚠ Rotating the Brevo key also means Supabase Auth's own SMTP setting |
| `FRONTEND_URL` | Links in emails (`https://halatuju.xyz`) |
| `ADMIN_NOTIFY_EMAIL`, `FOUNDATION_NOTIFY_EMAIL`, `COURSE_REFRESH_REMINDER_EMAIL` | Who internal notices go to |
| `CRON_SECRET` | Guards `/api/v1/internal/cron/` |
| `SENTRY_DSN` | Error tracking (no PII sent) |
| `DOCUMENT_BACKUP_BUCKET` | GCS bucket `backup_documents` mirrors the private document bucket into |
| `SGD_TO_MYR_RATE` | S$ → RM for Singapore payslips (in-review cases only) |
| `MAX_DOC_SIZE_BYTES`, `MAX_DOCS_PER_APPLICATION`, `MAX_OTHER_DOCS`, `DOC_STAGE_MAX_ATTEMPTS` | Upload limits and the re-upload circuit-breaker |
| `DOC_ASSIST_RATE_LIMIT_PER_HOUR`, `DOC_ASSIST_ONLY_WHEN_UNCERTAIN`, `IC_GEMINI_FALLBACK_ENABLED` (default ON), `DOC_GENUINENESS_CHECK_ENABLED` | Paid AI reads on upload |
| `CHECK2_STUDENT_QUERIES_ENABLED`, `CHECK2_AUTO_GENERATE`, `CHECK2_ANSWER_RELEVANCE_ENABLED`, `VERDICT_CASE_SUMMARY_ENABLED` | Check-2 switches (the last three are paid) |
| `SPONSOR_POOL_ENABLED` | The anonymised sponsor pool (live) |
| `SPONSOR_MOCK_DONATIONS_ENABLED` | **NEVER in production** (TD-258) — mints money; refuses to arm against a real database |
| `SPONSOR_COMMS_ENABLED`, `SPONSOR_TERMS_ENABLED`, `PARTNER_COMMS_ENABLED`, `PARTNER_NOTIFY_MAX_PER_RUN` | Platform halves of two-gate comms (each template has its own switch) |
| `SPONSOR_SEEN_THROTTLE_HOURS`, `ADMIN_SEEN_THROTTLE_HOURS`, `POOL_FUNDED_GRACE_HOURS` | Last-seen stamps; how long a funded card lingers |
| `DECLINE_COOLOFF_DAYS`, `DECLINE_QC_COOLOFF_HOURS`, `AWARD_COOLOFF_DAYS`, `AWARD_OFFER_EMAIL_COOLOFF_HOURS` | Embargo windows before a decision's email |
| `AWARD_ACCEPTANCE_ENABLED`, `BANK_DETAILS_CAPTURE_ENABLED` (deprecated) | Post-award student screens |
| `BURSARY_AGREEMENT_ENABLED` | In-app signing. ⛔ **TD-347 must be fixed first** |
| `GUARANTOR_PHONE_VERIFY_TTL_SECONDS`, `SIGN_ACCEPT_DEADLINE_DAYS`, `BURSARY_SIGN_REMINDER_DAYS`, `CONTRACTS_DRIVE_FOLDER` | Signing chain |
| `VIRCLE_SETUP_ENABLED`, `VIRCLE_ID_PREFIX`, `VIRCLE_ID_BAND_MIN` / `_MAX` | The eWallet task and the typed-id guard |
| `VIRCLE_AIRTABLE_PUSH_URL` / `VIRCLE_AIRTABLE_SECRET` | Vircle webhooks (secrets; blank = dark) |
| `VIRCLE_PAYMENTS_EMAIL`, `VIRCLE_PAYMENTS_FOLDER`, `VIRCLE_DRIVE_FOLDER`, `VIRCLE_SHEET_NAME`, `VIRCLE_SHEET_ID`, `VIRCLE_GUIDE_FOLDER`, `VIRCLE_GUIDE_FILENAME`, `VIRCLE_GUIDE_CACHE_SECONDS`, `VIRCLE_SPENDING_FOLDER`, `VIRCLE_SPENDING_SUMMARY_FOLDER`, `SPENDING_REPORT_QUIET_DAYS` | Payments, the relay sheet, the guide, spending reports (read live values, not defaults) |
| `INTERVIEW_SCHEDULING_ENABLED`, `INTERVIEW_MEET_ENABLED`, `INTERVIEW_DURATION_MIN`, `INTERVIEW_RESCHEDULE_CUTOFF_HOURS` | Interviews |
| `REVIEW_SLA_DAYS`, `REVIEW_NUDGES_ENABLED`, `REVIEW_NUDGE_SOON_DAYS`, `REVIEW_ESCALATE_GRACE_DAYS` | Reviewer deadlines and nudges |
| `STUDENT_ASSIGNMENT_EMAIL_ENABLED`, `PROFILE_COMPLETE_EMAIL_ENABLED` | Student notices |
| `WHATSAPP_ENABLED`, `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` (secret), `TWILIO_WHATSAPP_FROM`, `TWILIO_WHATSAPP_*_CONTENT_SID[_EN/_BM]` | WhatsApp reminders |
| `TWILIO_VERIFY_SERVICE_SID`, `PHONE_VERIFY_ENABLED` (paused), `PHONE_VERIFY_CHANNEL` | Student phone verification |
| `PARTNER_TEMP_PASSWORD_TTL_DAYS` | Staff temporary passwords |
| `REQUESTS_ENABLED`, `REQUESTS_QUOTE_MARGIN_PCT`, `BILLING_USAGE_ENABLED` | Requests space; the usage screen (the meter always runs) |
| `PARTNER_EMAIL_RESET_KINDS` | Set, run the seed job, UNSET. Several kinds need `--update-env-vars "^@^PARTNER_EMAIL_RESET_KINDS=a,b"` |
| `PROFILE_REFRESH_APP_IDS`, `AWARD_EMAIL_APP_IDS`, `VIRCLE_EMAIL_APP_IDS`, `SIGN_INVITE_APP_IDS`, `SEED_SPONSOR_ID` / `SEED_AWARD_APP_IDS`, `PATHWAY_REPAIR_APP_IDS`, `INCOME_DOC_TAG_APPLY`, `REQUIREMENTS_SNAPSHOT_APPLY`, `BACKFILL_VERDICT_VERSION_APPLY`, `BACKFILL_CONFIRMED_PROFILES_APPLY`, `REEXTRACT_DOC_TYPE`, `REEXTRACT_PASS` | One-shot scopes for argless cron jobs — set, run, unset |

Local-only (never on Cloud Run): `UPDATE_EMAIL_GOLDEN` (⛔ never set — see Live rules),
`HALATUJU_API_URL` / `HALATUJU_ADMIN_TOKEN` (`record_request_analysis`).
**Web (`halatuju-web`, build-time):** `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY` (public), `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (public),
`NEXT_PUBLIC_APP_VERSION` (from `COMMIT_SHA`, TD-076), `NEXT_PUBLIC_ORG_CODE` (unset in production),
`NEXT_PUBLIC_SANDBOX`, `NEXT_PUBLIC_THEME_SWITCH`.

## Security and access (full review: `docs/security-posture.md`)

- **Roles** (`PartnerAdmin.role`): `super` (platform, cross-org), `org_admin`, `admin` (view-only),
  `reviewer` (assigned applicants only), `qc`, `finance` (payment-run checker, no B40 data), `partner`
  (referral org's own students). `is_super_admin` is kept beside `role` (TD-064). Sponsors are a
  separate `Sponsor` identity. The role matrix is `docs/scholarship/role-matrix.md`.
- **The organisation fence** is `_AdminBase` (`_org_scoped` / `_org_allows`); every new admin endpoint
  goes through it, and the H3 guard fails a wired route no test drives or that skips the fence.
  Referral fields (`PartnerAdmin.org`, `referred_by_org`) are NEVER access control.
- **The gift gate:** `?programme=<code>` NARROWS inside the fence and never widens it; unknown or
  cross-tenant → 404, never "show everything". An **organisation-less super must name a gift** on
  money surfaces (`400 programme_required`, TD-334; the Overview still pools — TD-336).
- **RLS:** every `public` table has RLS on (event trigger `rls_auto_enable`, since 2026-09-16 — it adds
  no policy: add the `service_role` policy yourself). Scholarship tables are deny-all to the public key.
  **The four advisory tables are READ-only to students through the public key since 2026-10-05** (eight
  write policies dropped; undo `docs/security/2026-10-05-restore-student-write-policies.sql`); every write
  goes through Django. Run the Supabase Security Advisor after any migration; 0 errors before deploy.
  New-table policy templates (written after an earlier RLS incident): `halatuju_api/docs/incident-001-rls-disabled.md`.
  Check the trigger: `select evtenabled from pg_event_trigger where evtname = 'rls_auto_enable';` — `'O'` = on.
- **Google Workspace is keyless** (TD-125/TD-329): no service-account key exists. If the path breaks,
  alert policy "Google Workspace keyless path failed (Sheets / Drive / Meet)"
  (`alertPolicies/10163327245873580870`) emails tamiliam@gmail.com; recovery = the IAM grant
  (`roles/iam.serviceAccountTokenCreator` for the runtime SA on `halatuju-meet`) and
  `iamcredentials.googleapis.com` enabled. A key fallback would be a code restore plus a deploy.
- **Audit lines:** `AUDIT <event>` log lines (applicant reads feed the `applicant_record_reads` metric
  and its > 30-in-10-minutes alert); logs are JSON with a real `severity` (TD-290, `halatuju/logging_json.py`)
  — an alert matching `severity>=WARNING` only works because of it. Loggers are named in full
  (`apps.scholarship.emails`), never `__name__` inside a package (`AuditLoggerNameTest`).
- **Sessions:** three PKCE Supabase clients (student / admin / sponsor) with separate storage keys;
  the web never imports a value from `@supabase/supabase-js` outside `supabaseAuthClient.ts`.

## Data handling

- **PII:** NRIC, income and family documents. Never in a log line, a commit, a test fixture copied from
  production, or a scratch file left behind. `docs/scholarship/*.pdf|xlsx|txt` are gitignored real data.
  A reviewer's profile serves their phone and never their home address (`docs/scholarship/role-matrix.md`).
  The sponsor serializer is an ALLOWLIST: a new field is invisible to sponsors until deliberately added.
- **⛔ Never re-extract documents from a local checkout** — no Storage access, so it reads "no text"
  and destroys `vision_fields`. Re-read one document with the cockpit's **Re-run** on the live service.
  `reextract_documents` has no dry run and no single-document scope.
- **Production reads are read-only probes, counts only:** `BEGIN READ ONLY` per transaction; ⛔ never
  `set_session(readonly=True)` through the Supabase pooler (it leaks onto the shared backend). A
  probe's script lives in the scratchpad, never in the repo.
- **Paid jobs run only on the owner's word:** `refresh_sponsor_profiles`, `sort_spending --reask-version`
  (and ⚠ its REPORT mode also calls the model and pays), `reextract_documents`, `eval_doc_recognition`,
  a cohort-wide EPF re-read. `rescore_pending_decisions` re-scores EVERY unreleased submitted application
  in every cohort and the release job then emails the new verdict — count first.
- **Never edit production data to make a case look right** — fix the engine, then re-run it.

## Testing

### Reviewing the console locally (TD-194, 2026-10-05) — no production data, ever

```bash
cd halatuju_api                      # NO DATABASE_URL / DB_HOST in the environment → SQLite
python manage.py migrate
python manage.py seed_local_console --email you@example.com   # made-up org, gift, applications
SUPABASE_URL=https://pbrrlyoyyiftckqvzvvo.supabase.co python manage.py runserver
cd ../halatuju-web && npm run dev    # .env.local already points at http://localhost:8000
```

Sign in at http://localhost:3000/admin with that address. Supabase does the sign-in only; the
local API verifies the token through the public JWKS (`SUPABASE_URL`) and links your account to
the seeded super admin on the first VERIFIED sign-in. Development settings allow every origin, so
nothing changes on the live API. The command refuses any database that is not SQLite. It cannot
show documents (no Storage) — never re-run extraction locally.

### ⚠ The API gate — run the deploy gate's OWN line, not a serial run

```bash
cd halatuju_api
python -m pytest -q -n auto -p no:cacheprovider   # ⬅ what cloudbuild.yaml runs (xdist). A serial
                                                  # run passes things the gate refuses: subTest /
                                                  # parametrize values travel to the controller and
                                                  # execnet cannot serialise a datetime (TD-352's
                                                  # push, 2026-10-06: 1 failed in the gate, 0 here).
```

### ⚠ The FRONTEND gate list — all four, before any push that deploys web

```bash
cd halatuju-web
npm run gates                # ⬅ ONE WORD, runs all four below in order — `typecheck`, `lint`,
                             # `i18n`, `test` — and stops at the first failure. Each is also a
                             # script of its own in package.json, for iterating on one gate. The
                             # warnings below still apply; this only saves you typing them.

# ── or the same four by hand ──
npx jest --maxWorkers=2      # --maxWorkers=2 was required on the old 8 GB box (a full run OOMed and
                             # reported worker contention as FAILURES, exit 253). The dev box has
                             # 32 GB since 2026-08-02, so that note is stale; the flag is harmless.
npx tsc --noEmit --incremental false
                             # types. ⚠ 0 ERRORS REQUIRED since 2026-09-18 (TD-221 closed: the 24
                             # old test-file errors are gone, so ANY error is yours). Keep
                             # `--incremental false`: with the cache on, tsc REPLAYS errors from
                             # tsconfig.tsbuildinfo after the cause is fixed.
npx next lint                # ⚠ 0 ERRORS REQUIRED (warnings are fine — passing builds carry
                             # several). NEITHER jest NOR tsc runs ESLint, and `next build` LINTS
                             # BEFORE IT EMITS: on 2026-07-30 two eslint-disable comments naming a
                             # rule this config never loads failed the WEB build while the api
                             # deployed, so production ran new server code behind an unchanged UI
node scripts/check-i18n.js   # parity across en/ms/ta
```

**⚠ AND FOR INTERACTIVE BEHAVIOUR, A RENDERED TEST — a source-shape guard is not evidence.**
This repo has 17 `@testing-library/react` + jsdom tests; `components/admin/CommandPalette.test.tsx`
is the model and its docblock states the reason. Source-shape guards are right for **structural**
claims (no bare `disabled`, no hard-coded hex, no surface forgotten). They are blind to anything
depending on **focus, event propagation, keyboard, drag, mount/unmount or async flush** — a paste
handler on an unfocused `<div>` satisfied `/onPaste=/` for a day while the feature could not fire at
all. See `components/OrgRequestAttachments.paste.test.tsx` for the shape: dispatch the event from
somewhere ELSE on the page, because dispatching at the panel passes under both implementations and
proves nothing.


### Backend

```bash
cd halatuju_api
pip install -r requirements.lock -r requirements-dev.txt     # a fresh clone needs nothing else
python -m pytest -q -n auto -p no:cacheprovider              # the gate's line (above)
python -m pytest apps/courses/tests/test_golden_master.py apps/courses/tests/test_stpm_golden_master.py -q
python manage.py check
python manage.py makemigrations --check --dry-run            # "No changes detected"
```

Golden masters: **SPM 5,319**, **STPM 2,026** — if either moves, you broke eligibility. At v3.0.0:
8,084 pytest / 3 skipped · 4,146 jest / 252 suites (measured at the cut). Measure your own
baseline before you start; never quote an inherited number.

### Pre-deploy checklist

1. Both suites green with the gates' own command lines; `bundle-budget` green on the dev box.
2. A migration? Production applied by hand, ledger row recorded, ledger diffed (no gap).
3. A new table? RLS on (automatic), one `service_role` policy added, Security Advisor 0 errors.
4. Eligibility, money or identity? Adversarial review done, findings fixed or answered.
5. A version bump owed? `VERDICT_ENGINE_VERSION` if a band can move; the genuineness `MODEL_VERSION`
   on any doc-recognition signature change; a `PROMPT_VERSION` when a prompt changes.
6. New strings in en/ms/ta (Malay and Tamil are first drafts until the owner reads them); a changed
   reviewer surface updates the reviewer Guide + FAQ in the same change.
7. The owner's yes to push.

### Test fixtures

`apps/scholarship/tests/factories.py` builds the supporting rows (`make_org`, `make_programme`,
`make_cohort`, `make_admin`, `make_student`, `make_shortlistable_student`, `auth_token`,
`authed_client`) and, above all, **`make_application(stage=…, outcome=…)`** — an application at a
named stage, carrying every field the product would have stamped by then and none it would not.
`**overrides` sets anything explicitly; an unknown stage, or an `outcome` at a stage that has none,
raises a clear `ValueError`.

| Stage | `status` | What the product has set by then | What it deliberately has NOT |
|---|---|---|---|
| `submitted` | `submitted` | locale, notify_email, declaration + `declared_at`, consent-to-contact | verdict, any decision stamp |
| `scored` | `submitted` | `verdict`, `bucket`, `shortlist_reason`, `decision_due_at` | `decision_released_at`, `shortlisted_at` |
| `shortlisted` | `shortlisted` | `decision_released_at`, `shortlisted_at`, `reminder_anchor_at` | `profile_completed_at` |
| `profile_complete` | `profile_complete` | `profile_completed_at`, frozen `requirements_snapshot` | reviewer, verdict |
| `assigned` | `profile_complete` | `assigned_to`, `assigned_at` — **the status does not move** | verdict |
| `interviewing` | `interviewing` | `reporting_date` (the officer settles it here) | verdict |
| `verdict_recorded` (needs an outcome) | `interviewing` | `officer_verdict`, `verdict_decided_at/_by`, engine version; `award_amount` applied on accept / cleared on decline — **the status does not move** | every verify stamp |
| `awaiting_qc`, `outcome='recommend'` | `interviewed` | the verdict stamps **plus** `verified_at`, `verified_by`, `verify_checklist`, `profile.nric_verified` | QC/award stamps |
| `awaiting_qc`, `outcome='decline'` | `interviewed` | the verdict stamps only | **`verified_at`, `verified_by`, `verify_checklist`, the NRIC lock, `award_amount`** |
| `recommended` | `recommended` | `recommended_at/_by`, published anon `SponsorProfile`, active share consent, `award_amount` → in the sponsor pool | `awarded_at` |
| `awarded` / `active` / `maintenance` | same | `awarded_at` / `active_at` / `maintenance_at` + `maintenance_substate` | later stamps |
| `closed` | `closed` | `closure_reason`, `closed_at/_by` (the factory builds a FUNDED close; a stalled pre-award close is `make_application(<stage>)` + `closure.close_application`, TD-352) | — |
| `rejected` (branches off the decline road) | `rejected` | `rejection_category`, `rejected_at/_by`, `pre_decline_status`, `pending_rejection_category`, `decline_due_at`, `pending_decline_by` | `decline_email_sent_at`, any QC/award stamp |
| `expired` (branches off `shortlisted`) | `expired` | `expired_at`, `reminder_stage` 4, `last_reminder_at` | any verdict or reviewer |

⚠ **Two roads reach QC and they leave different marks.** A reviewer who RECOMMENDS goes through
`verify-accept`, which stamps `verified_at` / `verified_by` / `verify_checklist` and locks the
NRIC; a reviewer who DECLINES goes through `submit-decline`, which stamps **none** of those,
because a decline has no identity or completeness gate. Asking for `verified_at` on the decline
road is asking for a mark production never writes — that was BrightPath request #24.

`test_factories.py` walks a fresh application to **every** stage through the real services and the
real endpoints and asserts the factory agrees, so the factory cannot become the next stale fixture.
**New test files must use it** — enforced by `test_code_standards.py`; the ~134 files that still
hand-build one convert as they are next touched (`small-change-lane.md`), and their ledger entries
may only fall.

### Rendered tests for the cockpit

**Where the harness lives** (code health H6, front end): `halatuju-web/src/test/`.

| File | What it is |
|---|---|
| `adminApplicationDetail.ts` | `buildApplicationDetail(stage, overrides?)` — a complete, type-correct `AdminScholarshipDetail` at a NAMED STAGE. It mirrors the stage table above, including the two roads to QC, and `adminApplicationDetail.test.ts` reads `factories.py` and fails if the two stage lists drift apart. |
| `renderCockpit.tsx` | Mounts the real `src/app/admin/scholarship/[id]/view.tsx` for a given ROLE, with i18n, the admin-auth context, the router and `@/lib/admin-api` mocked, every on-mount call primed, and **any `console.error` failing the test**. |
| `view.decision` / `view.closed` / `view.roles` / `view.actions` `.test.tsx` | 59 rendered tests, beside the page. |

**The rule.** A change to `view.tsx`, or to any cockpit panel split out of it, runs `view*.test.tsx`.
**A new panel gets a rendered test, not a source guard** — the screen is the subject, so mount it.
Two text guards were retired into this harness (`approveLockoutGuard`, the component half of
`docFileLayout`) and two more converted to mounts (`ActionCentre.vircle`, the per-surface half of
`screenshotInput`).

**The text guards that remain, ON PURPOSE.** Each one's subject really is the shape of the source,
and there is nothing to render:

| Guard | Why it stays text |
|---|---|
| `brand-guard.test.ts` | One home for a brand literal. The claim is "this string appears nowhere else", which only a scan of everywhere can make. |
| `sandbox-safety.test.ts` | The sandbox must reach no real service. A mount proves one path is safe; the scan proves no path exists. |
| `icPadlockGuard.test.ts` | A verified NRIC stays locked. Structural: one expression either consults the rule or it does not. |
| `no-icu-messageformat.test.ts` | The SHAPE of a message value. `t` has no ICU engine, so an ICU construct renders its template verbatim — that is a property of the catalogue, not of a screen. |
| `navigation.test.ts` | Walks the routes on DISK against the registry, so a page that exists with no row (or the reverse) is found. Only the filesystem can answer that. |
| `soft-evidence-drift.test.ts` | A backend list copied into the front end. The guard is that the copy still matches its source. |
| `codeStandards.test.ts` | The standards themselves. Deliberately ONE file, so the project gains one source-reading test and not a habit of them. |
| `theme.test.ts`, `pageWidth.test.ts` | Convention checks that belong in ESLint. Noted, not moved (H6 scope). |
| `applicationStatus` / `requestStatus` / `screenshotInput` (the disk-walk half) | Each asks "is there a case/surface nobody thought about?" — a question only a walk of the tree can answer. The BEHAVIOUR each one used to assert now lives in a mount. |

## Code standards (enforced by tests — since code health H4, 2026-09-19)

These are not advice. Each one is an assertion in the normal test suite, and since H2 both suites
run inside the Cloud Build deploy gate — so **a change that breaks a standard cannot deploy**,
whoever or whatever wrote it. If you are reading this because a build went red, the failure
message itself tells you what to do; this table is the why.

| Standard | Enforced by | Why it exists |
|---|---|---|
| **No new giant file** — a source file may not pass 600 lines; the 36 api / 20 web files already over are listed with their size and may not grow more than 20 lines | `test_code_standards.py` · `codeStandards.test.ts` | `views_admin.py` was 8,547 lines and had been fixed 34 times in 90 days. Nobody holds a file that size in one head, and nobody reviews it properly. (H11 split it: the entry is now `views_admin/__init__.py` at 5,093, and **a split RENAMES a ledger key** — since TD-272 that is a DECLARED move, not a hand edit of the frozen baseline: see **Moving a file that is in a ledger** below before splitting anything else on this list) |
| **No new giant function** — no Python function of 150+ lines outside the ledger of 16; a listed one may not grow more than 10 lines | `test_code_standards.py` | A 300-line function has no seams, so a branch in the middle of it can only be reached by running the whole thing |
| **One rule, one home** — no module-level function name defined in 3+ files of one app, beyond the ten listed | `test_code_standards.py` | `_money` is seven functions with one name. A money-format fix made in one copy is not made in the other six |
| **Tests can fail** — zero `skip` / `skipif` / `xfail` / `unittest.skip`; zero `.skip` / `.todo` / `xit` / `xdescribe`; the four files using a runtime `self.skipTest` are ledgered and may only shrink | both | Both golden masters used to skip themselves on the run straight after a regenerate: the least supervised moment in the process passed green |
| **No blind spots** — `# noqa` and `# type: ignore` counts may not rise; no `@ts-ignore`; the `any` and `@ts-expect-error` counts may not rise | both | Every one is a gate told to look away, and `tsc` is a deploy gate here |
| **Every `eslint-disable` carries a written reason** — ` -- why` on the same line, or a sentence in the comment above; the 37 without one are ledgered and may only shrink, and the total may not rise | `codeStandards.test.ts` | A rule switched off without a reason cannot be told from one switched off by accident, and nobody can ever judge whether it is still needed |
| **No unguarded mirror** — a `src/lib` comment saying a rule is *mirrored* or *kept in sync* must carry `drift-test: <repo-relative path>` naming the test that proves it; the ledger of those without one is **3** (58 at H4, 17 discharged by H9, 38 by H10) and only shrinks. ⛔ The three that remain are `incomeWizard.ts` and they stay **by decision** until TD-262 is settled — the reason is at the top of that file | `codeStandards.test.ts` | The `SOFT_EVIDENCE` denylist rotted because nothing enforced its mirror, and a fact backed only by soft signals leaked to blue. A comment asking two files to stay in step is a request; only a test is a rule. **Serve a rule that VARIES between callers; guard a rule that is a constant** (decisions.md 2026-09-19) — a served constant can only fail at runtime, a drift test fails in the deploy gate. The shared reader is `halatuju-web/src/test/apiSource.ts` |
| **No dead weight** — every package in `dependencies` is imported somewhere | `codeStandards.test.ts` | Downloaded on every build, audited on every scan, and read by the next person as something this app uses |
| **The app boundary** — `courses → scholarship` imports may not rise above 25, and the module-level ones may not rise above 1 | `test_code_standards.py` | Two apps that import each other are one app with a line drawn through it, and the import-time half is what takes the service down at start-up |
| **New tests use the factory** — a test file not already in the ledger of 134 may not call `ScholarshipApplication.objects.create(`; a listed file's count may only fall | `test_code_standards.py` | A hand-built fixture can describe a state the product cannot reach, and then the test passes for ever while testing nothing (BrightPath #24). See **Test fixtures** below |
| **A route may not get heavier** — no route's first-load JS may reach **300 kB** unless it is in the `first_load_js` ledger with its own number, no ledgered route may pass that number, and the **median across all routes** may not rise above **229 kB** (256 until TD-300, 2026-09-28) | `scripts/bundle-budget.js` **in the deploy gate** (+ `codeStandards.test.ts` for the ledger and the wiring) | A visitor downloaded 1.53 MB of message catalogues to read one language, and nothing counted it for a year. See **The two budgets H18 added** below — this one is NOT measured by jest and that matters |
| **Opening one applicant may not cost more queries** — the officer's applicant-detail GET is pinned at **38**, with or without documents, with ZERO slack | `test_query_budgets.py` (the reading) + `test_code_standards.py` (the ratchet) | It was **315** and **385** — an N+1 nobody had counted since June. TD-282 fixed it with the document snapshot (below); the two numbers are now EQUAL because a document costs nothing extra to open. The budget's job now is to notice if that comes undone |

**Post-freeze query budgets — `_admitted` (TD-286, 2026-10-04).** A query budget set after H18 is a
dated record in the `_admitted` array of `halatuju_api/code-standards.json` — `{on, by, why, ledger,
key, value}`, `ledger` = `query_budgets` only — and its `value` IS the live budget
`test_query_budgets.py` reads (that file holds no numbers). ADD a record for a new reading; LOWER a
value when the tightness test says so; NEVER raise one (`code_health.py`'s `std` reading compares
the array with the last close and FAILs a rise). Never put a new budget in the frozen `baseline`.

**The debt register is not the api gate's (TD-256, 2026-10-04).** The api trigger ignores `docs/**`,
so `test_technical_debt_register.py` does not run on a docs edit. `code_health.py`, run at every
close, performs the same duplicate-id check and FAILs on a new collision; the declared collisions
are the `<!-- td-known-collisions: … -->` comment in the register.

**The two budget files.** `halatuju_api/code-standards.json` and `halatuju-web/code-standards.json`.
Each sits inside its own service folder, so it is inside the path filter of the Cloud Build trigger
that runs the tests reading it. Each holds a frozen `baseline` (every number and every ledger as H4
found them) and a live `budget` (starts identical, only ever tightens). Open either file; the
`_how_this_works` note at the top says the same thing in five sentences.

**The ratchet, in three sentences.** A test asserts `actual <= budget`, so the code may not get
worse. It asserts `budget <= baseline` and that no ledger has gained a member, so a limit can never
be raised back to where H4 found it and an exemption list can only shrink. And it asserts
`budget <= actual + slack`, so when you improve something the build goes red until you lower the
budget to match — that is the ratchet catching up with you, not a complaint. (The `baseline` block
is pinned by a SHA-256 held in the test file, so rewriting history takes a second deliberate edit
that a reviewer sees.)

### The two budgets H18 added (2026-09-20) — and HOW TO RUN EACH LOCALLY

Both are ordinary ratchets: a frozen `baseline`, a live `budget` that only tightens, and a failure
message that tells you which number to lower. What is different is **where each one is measured**,
and that is the part to read before trusting either.

**1. First-load JS per route — `halatuju-web/`, and jest does NOT measure it.**

```
cd halatuju-web && npm run bundle-budget        # builds, then checks. One command.
```

The number exists in exactly one place: the route table `next build` prints. jest has no build
output; `code_health.py` does not build either. So the reader is `halatuju-web/scripts/bundle-budget.js`
and it runs **inside the Cloud Build deploy gate** (`halatuju-web/cloudbuild.yaml`, the `test` step,
after `npm run gates`), which is the only place a build already happens. A regression therefore
turns the gate red before the image is pushed.

- It refuses three things: a route at or above the **300 kB ceiling** that is not in the ledger; a
  ledgered route past its own number; the **median** above 229 kB (TD-300 took it from 256).
- **Every run prints a TIGHTNESS NOTE** (TD-300): how far the median sits under its budget, how
  many routes are within 1 kB of it, and how many routes may each cross the budget before the
  median does. **Watch that last count** — at 0 the next byte on a median route turns the gate red
  for a reason unrelated to the change that added it (that was TD-300).
- **A dev-box run is STRICTER than the gate** (Consolidation Review 2026-10-06): it FAILS when any
  budgeted route, or the median, has less than `NEAR_LINE_KB` (0.15 kB) of room under its line,
  because the gate's build reads ~0.06 kB heavier and the next en.json string moves every route.
  The gate runs `npm run bundle-budget -- --gate` and only prints that finding. Take weight off;
  never raise a line, and never pass `--gate` locally. The margin is a ratchet (0.25 when TD-344
  frees `/scholarship/apply` and `/scholarship/application`).
- ⛔ **No value import from `@supabase/supabase-js` in `src/`** — the three clients are AUTH-ONLY
  (`src/lib/supabaseAuthClient.ts`); one `createClient` puts 29 kB back on 73 routes.
  `import type` is fine. Enforced by `src/lib/__tests__/supabaseAuthClient.test.ts`.
- ⚠ **Next's printed first-load for an app route counts the PAGE entry only** — a chunk only a
  LAYOUT loads is downloaded on first paint and is not in the number (`/login` prints 87.6 kB; the
  browser fetches ~231). Moving weight from a page into a layout "passes" without making anything
  lighter. TD-304.
- **Since TD-304 (2026-10-04) the reader budgets EXACT bytes** — each route's page entry from
  `.next/app-build-manifest.json`, gzipped at level 9 as Next does — after checking every exact
  figure against the printed one (a mismatch FAILS: the manifest is another build's). So the 0.5 kB
  rounding trap is gone, and a "LOWER it to" note names a whole kB at or above the exact figure.
  It also PRINTS a **first-paint JS** line (page + every layout above it) that has NO budget: first
  reading median 257.8 kB, worst 324.6 kB (`/profile`). A budget on it is a new standard — owner's
  call, with TD-286 — so do not add one in passing. ⚠ `--from-log` now needs the SAME build's
  `.next/` beside the log.
- ⚠ **87.2 kB is the FLOOR** under every route (React + the Next runtime + the shared chunk). No
  target below that is reachable by any change — subtract it before setting one.
- ⚠ **What it cannot see:** it does not run in `npm test`; it reads what Next PRINTS (gzipped
  first-paint JS — no CSS, no fonts, no lazily-imported chunks, so moving weight behind an
  `import()` lowers the number without shrinking the app); and it is blind between the floor and
  the ceiling, which is what the median covers. The full list is at the top of the script.
- `codeStandards.test.ts` owns the ledger's arithmetic **and asserts `cloudbuild.yaml` still runs
  the reader.** Do not remove that line from the gate; the numbers become decoration the moment
  you do, silently.

**2. Database queries to open one applicant — `halatuju_api/`.**

```
cd halatuju_api && python -m pytest apps/scholarship/tests/test_query_budgets.py -q
```

Two readings through the REAL endpoint, built with the H5 factory: **38** queries with no
documents and **38** with three named documents. The pair separates a fixed cost from a
per-document one — if the three-document budget fails while the bare one holds, the new work is
inside a per-document N+1 and every real applicant pays for it several times over. Zero slack,
because the reading is deterministic.

⚠ **THE TWO NUMBERS BEING EQUAL IS THE POINT.** They were **315** and **385** when H18 recorded
them on 2026-09-20 — roughly twenty queries for every document a family uploaded, so a case with a
dozen was past six hundred. TD-282 (2026-09-21) removed the slope entirely with the **document
snapshot** described in the next section. If these two ever diverge again, the per-document N+1 is
back.

⚠ Its keys are **route patterns**, not file paths (`api/v1/…/<int:pk>/::GET::<fixture>`), so
`query_budgets` is a full member of `_moved` but not of `PATH_KEYED_LEDGERS` — see the next
section, and the reading test asks the equivalent question ("does this pattern still resolve?")
where Django's resolver exists.


**The document snapshot** (TD-282, `apps/scholarship/document_snapshot.py`) is why opening one
applicant costs 38 queries with or without documents. ⚠ **No write path may open or read one**; it is
opened in ONE place (`AdminApplicationDetailView.get`). Widen it only by the four steps in
`docs/domain-rules.md`, and only with the surface added to the ON==OFF matrix first.

### Moving a file that is in a ledger — HOW TO DECLARE A MOVE (TD-272, 2026-09-20)

Every ledger is keyed on a FILE PATH. **So before you plan a cut, grep both `code-standards.json`
files for the file you are about to split** — the question is not "may this file's key move?" but
"does anything INSIDE this file have a key of its own?" A file's size entry, a long function, a
runtime skip, a hand-built fixture, an `eslint-disable` and a mirror claim are all keyed on the
path, and the last two live *inside* the body you are about to lift.

When the answer is yes, **you do not add the new key and you do not touch the frozen `baseline`.**
You declare the move. Add a record to the `_moved` array at the top of that service's
`code-standards.json`:

```json
{
  "on": "2026-09-20",
  "why": "IncomeWizard left ScholarshipDocuments.tsx for its own module; the two reasonless
          exhaustive-deps disables are inside the moved body, so they travelled with it.",
  "ledger": "eslint_disable_without_reason",
  "from": "src/components/ScholarshipDocuments.tsx::react-hooks/exhaustive-deps::1",
  "to":   "src/components/ScholarshipDocuments/IncomeWizard.tsx::react-hooks/exhaustive-deps::1"
}
```

…then edit `budget` to spell the entry at its new key, exactly as you would have edited it anyway.
One record per key: a body carrying two disables is two records. The tests read the frozen
`baseline` THROUGH `_moved`, so every rule above then applies to the relabelled record, unchanged.

**A move may not buy anything, and the test will say so if you try.** It is refused when the `to`
key is one the ledger already holds (a merge would give the survivor the room of both), when the
`from` key is not in the frozen ledger (there is no recorded debt to relabel — fix the code
instead), when `to` names a file that is not in the tree, when the record is incomplete, or when
`why` is a shrug rather than a sentence. And because a relabel swaps one key for one key, **a
ledger's length and total are the same either side** and the moved entry inherits exactly the room
the old one had — not a line more.

**You do NOT re-pin `BASELINE_SHA256` for a move.** `_moved` is a sibling of `baseline`, never a
part of it, so the frozen record stays byte-for-byte what H4 measured. H11 re-pinned by hand and
said in its own retro that a fifth acceptance of a wrong guard is how a guard stops being read;
this is what replaced that. Rewriting the `baseline` block itself is still refused, exactly as
before.

**Prune the record when the debt is paid.** Once the budget line it follows is gone — the file fell
under 600, the disable gained a reason — the record describes nothing and the test asks you to
delete it. The story of the move lives in the CHANGELOG and in `_history`, not in a live lens over
the frozen record.

⚠ **A guard that READS a moved file by path must follow it in the same change.** `theme.test.ts`
walks a directory and so needs nothing; `incomeEvidenceHomes.test.ts` names a file and had to be
re-pointed when `IncomeWizard` moved. A source-read guard left on the old path goes GREEN while
watching a file the rule has left, which is the most dangerous way for a test to pass. **Run BOTH
suites whatever you touched** — a web guard reads api source and vice versa.

**Never raise a budget.** If you must grow a file that is already on the list, **split it first, in
its own commit, with no behaviour change** — then add your work to the smaller module. If you must
add a rule the front end already knows, serve it rather than mirror it. If a suppression is
genuinely unavoidable, write the reason on the line. No failure message here will ever tell you to
raise a number, because there is no case in which that is the right answer.

**Not yet covered** (later sprints, each with its own test): first-load-JS and database-query
budgets arrive with H18. Style and formatting are deliberately out of scope for ever — a formatter
pass rewrites every file and proves nothing about bugs.

### A TREE-WALKING GUARD NEEDS A FLOOR (TD-276, 2026-09-20)

**If a test walks the tree, it must assert that the walk found something — and how much.** This is
not a style note. This arc met the same failure four times and every time it was SILENT: a guard
walks the tree, finds N things, asserts something about each, and then the code moves and the walk
finds ZERO. Every assertion is now vacuous and the guard goes on passing. It never appears in a
failure list, because **a scan that finds less asserts less**. `officerGateDrift.test.ts` read
`views_admin.py` by path and died at import for two sprints (13 tests); `test_verdict_item_i18n.py`
used `glob` where a package needed `rglob`; `AuditLoggerNameTest` was pinned to one package and its
bite came back GREEN; `test_wallet_credit.py` allowlisted by bare filename.

**A guard that can pass while seeing nothing is not a guard.**

Use the shared helper. `halatuju_api/apps/scholarship/tests/source_walk.py` (api) and
`halatuju-web/src/test/sourceGuard.ts` (web); `src/test/apiSource.ts` is the same idea pointed at
the backend's tree and already carries `readApiTree(dir, minFiles)`.

| You are about to… | Use | It fails with |
|---|---|---|
| read one file by path | `read_source(path, why)` · `readWeb` / `readRepo(rel, why)` | the path, and `why` this guard reads it |
| read an api file from a web test | `readApi('apps/…')` — the repo-relative LITERAL | the path; and the api gate sees it (below) |
| walk a directory | `walk_sources(root, '*.py', floor, why)` · `walkFloor(dir, floor, why, {exts})` | the shortfall, the tree, and `why` |
| count what a scan found | `floor_count(found, floor, what, why)` · `floorCount` | the shortfall and `why` |

Four rules for the number itself:

1. **A floor is a MINIMUM, not an equality.** It is the count the walk found the day it was
   written, rounded down for churn. Adding a legitimate file must leave the guard GREEN — a floor
   that cries wolf teaches the next engineer to edit the number without reading it, and a floor
   nobody believes is worse than none. A guard that genuinely needs a CLOSED set asserts that
   equality itself, beside the reason it is closed.
2. **It names its number AND its reason.** "expected 12, got 0" tells a future engineer nothing.
   `why` is a sentence saying what rule this holds and where to look for the code that moved.
3. **Floor the FILES and the THINGS.** A walk can read every file and still find none of what it
   came for, because the marker it greps was renamed. `test_ai_registry.py` floors both, and they
   fail differently on purpose.
4. **Never lower a floor to make red go away, and never convert one to a skip.** A skipped drift
   test is how the 64-subject drift shipped.

⚠ **Allowlist a PATH, never a NAME (TD-277).** A guard that exempts or selects a file by its bare
name (`path.name == 'funding.py'`, `basename(f) === 'source_walk.py'`) silently widens to every
future file of that name anywhere in the tree. Key it on the path relative to the app or the repo.
Swept 2026-10-04: the last two (`test_verdict_item_i18n.py`, `crossTreePaths.test.ts`) now key on
paths; directory-name skips (`migrations`, `__tests__`) are a convention, not an allowlist.

⚠ **Watch for a corpus fed to `parametrize` or `.each`.** An empty list there generates ZERO tests:
the file collects clean, reports nothing, and is green for ever. `test_slip_fixtures.py` was
exactly this.

⚠ **The two trees watch each other.** `test_web_guards_read_live_paths.py` (api side) extracts
every api path the web tree names and fails if one is gone — so a backend refactor goes red in its
OWN gate instead of killing a web suite that nobody will run for two sprints.
`crossTreePaths.test.ts` does the reverse. Both also carry a MANIFEST of the guard files on the
other side, which is the only thing in either tree that notices a whole test FILE leaving the run.
**When you add a guard that reads across the trees, add it to that manifest the same day.**

### THE RULES THE ARC HARVESTED (code health H19, 2026-09-20)

Nineteen sprints put about 150 entries into `docs/lessons.md`. Most are about one incident. These
nine groups are the shapes that came back three, four and five times, reduced to the rule and its
reason. **`lessons.md` keeps the evidence; this keeps the instruction** — read this, and read the
story only when you want to know why. The two classes that earned a section of their own are above:
**moving a file that is in a ledger**, and **a tree-walking guard needs a floor**.

**1. A guard is only as strong as its cheapest passing state.**
- Before writing a source-level guard, ask what the laziest passing state looks like. If the answer
  is *"the right word appears somewhere in the file"*, the guard is decorative — count occurrences,
  or assert the property. `/TableFrame/.test(src)` was satisfied by an import line.
- **A negative assertion goes GREEN when its subject leaves the file it reads.** `not.toMatch` and
  `assertNotIn` reward the code leaving; a positive assertion at least fails loudly. Pair every
  negative with a positive, or point the guard at a walk with a floor.
- A negative assertion over a whole payload needs a sentinel no timestamp, id or amount can
  contain, and a positive line proving the sentinel is in the data at all.
- Match the instrument to the claim. A source-shape test is right for a STRUCTURAL claim (no bare
  `disabled`, no raw hex, no surface forgotten) and is **not evidence** for anything depending on
  focus, event propagation, keyboard, drag, mount/unmount or async — that class needs a mount. A
  rendered test is in turn only evidence of what jsdom actually implements; where it does not,
  assert the structural pair that decides the real behaviour and say in the test why.

**2. Bite it, or you do not know.**
- A guard, a golden master, a drift test and a budget are all hypotheses until an injected fault
  turns them red. **"It still passes after the move" is not a measurement; "it still fails when it
  should" is.**
- **A silent bite is the finding, not a curiosity to note.** Write the test that should have
  spoken, or delete the line that can never matter — in this sprint.
- A silent bite may mean the FIXTURE is too kind rather than the guard unnecessary. Read the
  function from the top and name the branch your fixture returns on; the missing row is the one
  that reaches your code.
- **Verify the injection LANDED.** A zero-match needle is unproven, not passing, and reads exactly
  like "the code has moved". Prove the needle is unique, and derive the newline from the file's own
  bytes — line endings are per FILE here.
- The fault must leave the file parseable. If every test goes red you broke the module, not the
  behaviour; the signal is *the right tests went red and no others*.
- **Restore by writing the original BYTES back in a `finally`, and verify the restore against the
  ORIGINAL digest** — not against "no exception was raised". A harness that edits one file twice
  backs up the intermediate state. **Never `git checkout --`**: it restores to the last commit, not
  to the state you were in. This arc lost real work to it twice.

**3. A number you did not measure is a number you do not have.**
- **Measure every baseline yourself before touching anything, even when the brief states it.**
  H13's brief said 2,913 jest and the tree stood at 2,900 with a whole suite dead at import for two
  sprints. An inherited number is the one most likely to predate the thing that broke it.
- **Do the arithmetic on any target you are asked to accept, on day one.** H14, H16 and H17 each
  inherited an acceptance from a differently-shaped predecessor, and each found on the last day
  that it had never been reachable. Find the FLOOR first — 87.2 kB sits under every route.
- Say what you ran. "3,584 passed" measured in one directory, quoted as a project total, is a trap
  for whoever reads it next.
- **When a reading's DEFINITION changes, say so at the row and do not compare across it** (`xapp`
  steps 133 → 46 on 2026-09-20 because the definition changed, not the code).

**4. When a reading punishes the right behaviour, fix the reading — never the number.**
- `xapp` counted import STATEMENTS, so a faithful split could only inflate it. `guard%` counts
  source-reading tests, which are the cure for unguarded mirrors and not the disease. `hot#1` does
  not follow a rename, so a split reads as a hotspot vanishing rather than shrinking.
- **A number held by hiding the thing it measures is worse than a number that went up honestly.**
  Write the arithmetic out, raise the tool shortcoming as a TD entry, accept the rise in the review.
- A metric's match list is reviewed whenever a sprint invents a new idiom for the thing it counts,
  and a widened definition is dated in the source, so the step reads as the definition catching up.

**5. A standard is the thing that RUNS.**
- A budget needs a READER before it needs a number, and the reader needs a home that already runs.
  **A ledger full of figures nothing reads is worse than an empty column: it reads as enforced.**
- **When a standard is enforced somewhere other than the test suite, a test in the suite asserts
  the wiring.** `codeStandards.test.ts` asserts `cloudbuild.yaml` still runs `npm run
  bundle-budget`; without it, one tidy-up of the gate turns every kilobyte in the ledger into a
  comment, silently.
- Name where it runs and what it cannot see, in the file itself.
- If the number cannot be measured yet, ship the SOURCE rule that causes it and make the measured
  half a named finding with its reader as the first task. H17 refused a number it could not measure
  and that refusal was worth more than the number.

**6. "Nothing uses this" is a claim about your SEARCH.**
- A symbol search answers *who imports this*. Lazy imports are deliberate here, so that is not *who
  calls this*. **Grep for what the thing PRODUCES** — the served field name, the status value, the
  error code — not only for its own name. `interview_agenda_full` was written into a roadmap, a
  brief and this file as dead, and serves every cockpit load.
- Two greps for a patch target, always: `patch('pkg.name')` **and** `patch.object(pkg, 'name')`. On
  a re-export shell the first SUCCEEDS, rebinds something nothing calls, and the real function runs
  — use `tests/package_patch.py`'s `patch_engine`.
- Never conclude an absence from a truncated search (`| head`), from one field of a model, or from
  the repository at all: authored content — clauses, templates, copy — lives in the database.

**7. Measure before you reach for the obvious fix.**
- **A performance fix is not done until the MEASUREMENT moved.** Take the reading, apply the fix,
  take it again; if the two are equal you have not fixed it, whatever the mechanism suggests. A
  `.filter(...)` on a related manager ignores a prefetch cache, so the reflex fix for the cockpit's
  315 queries is a no-op that passes every test (TD-282).
- Budgeting a bad number is a legitimate outcome: it stops the number growing while the real fix is
  scoped, and it makes the fix visible when it lands, because the tightness rule then fails with
  *"LOWER it to N"*.

**8. Characterise before you change, and never edit an expectation.**
- A de-duplication or unification sprint starts with a characterisation table over ALL the copies
  against ONE input list, written against the unchanged tree. Surprises are pinned and reported,
  never folded into the move. H7 found five defects that way; H8 found eleven homes where the
  register said four.
- **A test that starts failing when you convert a fixture is a FINDING, not a fixture to bend
  back.** A test that breaks is a claim about which behaviour was intended: read its purpose before
  touching its assertion, and when you must amend one, write into the test what superseded it.
- **Any sprint on eligibility, money, consent or identity states its STOP condition in the brief
  and names the smaller deliverable that ships if it stops.** H8 stopped, shipped a verified map
  and no production code, and that was the right outcome — the literal goal would have un-submitted
  real students with a green suite.

**9. Prose rots; write it so it cannot.**
- **A docstring describing THE CURRENT SPRINT has a shelf life.** Write status as a dated sequence
  — *"Sprint 2 landed this inert; 3a moved the gates onto it"* — which can never be falsified,
  instead of a present tense that the next sprint silently makes false.
- **Advocacy text expires the day the gap closes**, and the sprint that closes it owns rewriting
  the case that was made for it.
- **A comment asking two files to stay in step is a defect report, not a safeguard.** Extract it,
  serve it, or write the drift test.
- An exemption carries its reason at the SITE somebody would open to remove it, and names the
  condition that releases it. Left silent, a decision is indistinguishable from an oversight and
  the next sweep "finishes the job".
- A promise to a named future sprint belongs in that sprint's ROADMAP section. A code comment is a
  note to whoever next opens that file, which is a different person (TD-271).


## Income — the rules that move money (full text: `docs/domain-rules.md`)

Before you touch any income home, read the income section of `docs/domain-rules.md`. The rules in one
breath: `income_shown(application, member)` is the ONE per-earner answer and has **no STR arm, by
ruling**; an STR is household evidence, settles the verdict by precedence, and only the FAMILY'S OWN
STR opens the submission gate (`str_not_breached` stays recipient-agnostic on purpose); the cash /
declared door is **never** added to the STR route (owner 2026-09-20); `_stronger_income_fact` can only
RAISE a band and asks `salary_evidence_stands_without_the_str` first — that fall-through gate stays;
`has_valid_str` asks whose STR it is (TD-285) — a mismatch refuses only when COMPLETE on a field the
STR offers; ⛔ **never "tidy" `application_completeness`** (its legacy arm is more permissive on
purpose; replacing it un-submits students); `income_engine/` is eligibility and `incomeWizard.ts` is its
parked mirror until TD-262 is settled. Any change answers to `tests/test_income_evidence_homes.py`,
`tests/test_income_shown.py` and `src/lib/__tests__/incomeEvidenceHomes.test.ts`.

## Course data operations (full text: `docs/domain-rules.md`)

Annual STPM and SPM catalogue refreshes (`scrape_mohe_stpm`, `sync_stpm_mohe`, `sync_spm_mohe`,
`validate_stpm_urls`, `refresh_stpm`), the UP_TVET inventory (`scrape_uptvet`, `audit_uptvet`, no DB writes) and the
read-only Course Data dashboard (`course_data_check`, weekly cron `course-data-check`, the api request
timeout raised to 300 s for it) — the commands, their order and what each may write are in
`docs/domain-rules.md`. Browser scrapes stay manual and local; nothing applies a refresh from the UI.

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


## Live rules carried from the sprint history

Each was learned the hard way; the story is in `docs/sprint-history.md` and `docs/lessons.md`.

- **Never raise a budget, a floor or a ledger** — split the file first, in its own commit, moves only.
  ⚠ The tight ones: `pathway_engine.py` (0 lines of room) and `models/applications.py` (1); `serializers.py`
  and `serializers_admin.py` are close. Grep both `code-standards.json` files before planning.
- **The standing rule (owner, 2026-09-19):** a feature sprint does not grow a file waiting to be split —
  it runs that file's split first. The split table is "Which Phase-4 sprint owns which file" in
  `docs/plans/2026-09-18-code-health-roadmap.md`; the ratchet binds regardless.
- ⛔ **Never set `UPDATE_EMAIL_GOLDEN`.** `tests/test_email_branding.py` pins every email's bytes in three
  languages; a failure means you changed what a student receives — that needs the owner.
- **Patching a re-export package:** `patch('pkg.name')` can SUCCEED and patch nothing. Grep for both
  `patch('…')` and `patch.object(…)`; use `tests/package_patch.py`'s `patch_engine`. Grep a module for
  `__file__` as well as `__name__` before splitting it.
- `apps/scholarship/constants.py` is a LEAF — adding one import to it undoes its purpose.
- **i18n delivery:** `src/lib/messages.ts` is the ONE place a catalogue is imported; ⛔ never add a line to
  `oneLocalePerVisitor.test.ts`'s exemption list — lazy-load, split, or serve the value from the api.
  Every new English string moves every route's first-load weight (TD-360).
- **Serve, never assemble or derive in the browser:** `apply_url`, a gift's `state`, a request's status;
  a draft (theme or copy) must never reach a visitor; "draft from English" drafts and never saves.
- **Status is derived, never stored** (invitations); `last_send_ok` is tri-state (null = not recorded).
- **Never re-run `build_verdict` over old snapshots** — a snapshot is the historical record.
- **Version bumps are not optional:** `VERDICT_ENGINE_VERSION` when a band can move;
  the genuineness `MODEL_VERSION` (`results_doc.py`) on any doc-recognition signature change.
- **Money:** read Vircle's `Principal Wallet ID`, never `Supp Wallet ID`; the inbound webhook never
  overwrites a stored `vircle_id`; "sent to a person" comes from `duitnow_type`, never the merchant
  name; a student's name in a spending report is never stored; a new FILE triggers the spending job,
  never the calendar.
- **The padlock keys on `nric_locked`, never `identity_verified`**; soft-NRIC: unique only when verified.
- **An organisation's Overview layout narrows and orders a role's sections; it never widens them.**
- **A Django `AlterField` that only changes a default does not rewrite existing rows** — sync config rows by hand.
- **Node 24 is named in four places** (Dockerfile, the `cloudbuild.yaml` test step, `.nvmrc`, `engines`)
  held by `nodeVersion.test.ts`; change all four together.
- **A STPM/Form-6 offer reading `ua_offer` + `suspect` is often CORRECT** (an online announcement, not the letter).
- **The debt register:** close a TD only with evidence; put the resolution marker ON the defining line in
  the same change; never write a new entry inside the Open Items Index.
- **Never conclude an absence from a grep** — authored content (clauses, templates, copy) lives in the database.

## Next Sprint

**State at the v3.0.0 cut (2026-10-06).** Everything below is on `origin/main` and live: TD-352 (an
officer closes a stalled application; migration 0168) and request #30 (the C-or-better SPM rung;
migration 0169, applied migrate-first, ledger 0167–0169 contiguous). **Next migration number: 0170**
(scholarship) / 0077 (courses). Register: **116 open** (`docs/technical-debt.md`, Open Items Index).

- **TD-347 is the next sprint when the owner says go** (ruled B: when the parent call is recorded,
  re-arm a FRESH full accept window; the email names the new deadline). ⛔ It must ship before anyone
  sets `BURSARY_AGREEMENT_ENABLED`. Before that flip, also prompt every awarded student to check the
  parent phone on /profile (request #26 retro §4).
- **Now tier** (money, identity, eligibility): TD-367 (a payment run can pay a CLOSED student), TD-356,
  TD-348, TD-252 (the lapse job is written, the Scheduler job and console withdrawal remain).
- **On hold by owner ruling:** TD-366 (who may release an awarded student who stops answering — until
  signing is finalised), TD-353 (two organisations at once — until a second organisation joins).
- **Owner actions open:** record parent calls for #116, #62, #125, #25 (not #20); read the Malay/Tamil
  first drafts (one sitting: TD-091, 094, 097, 105, 108, 132, 170, 180, 183, 215); the 25 Owner-decision
  questions in the register.
- **Weight:** `/scholarship/apply` and `/scholarship/application` are the thin first-load lines (TD-344);
  the cure is TD-360 (split the English catalogue by audience). Run `npm run bundle-budget` before any
  push that adds a string.

## Known Issues & Future Work

The open debt register is `docs/technical-debt.md` (Open Items Index, in working order); the release
notes list it by importance and size (`docs/releases/release-notes-v3.0.0.md`, Known Issues). Plans:
`docs/roadmap.md` and `docs/plans/`. General rules (testing, deployment discipline, git, cleanup,
British English) are in the workspace-level `CLAUDE.md`.
