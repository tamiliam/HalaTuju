# HalaTuju API — Architecture & Operations

This is the operating manual, kept SHORT on purpose: it loads into every session and helper agent, so
it is paid for on every call. It holds the rules that cause real damage if missed, the gate commands,
and the current Next Sprint. The full text of everything else is in the docs below, word for word:
**[`docs/deployment.md`](../docs/deployment.md)** (how a change reaches production, env vars),
**[`docs/testing.md`](../docs/testing.md)** (gates, fixtures, phone check),
**[`docs/code-standards.md`](../docs/code-standards.md)** (ledgers, budgets, guard rules),
**[`docs/domain-rules.md`](../docs/domain-rules.md)** (identity, income, course data, live rules),
**[`docs/architecture.md`](../docs/architecture.md)** (system map, engine, key files) and
**[`docs/sprint-history.md`](../docs/sprint-history.md)** (older sprint and state notes). Open debt:
`docs/technical-debt.md` (Open Items Index). Every ruling: `docs/decisions.md`. Release notes: `docs/releases/`.

## Read before you…

- Deploy, push to `main`, migrate, set an env var, run a Cloud Run job → `docs/deployment.md`
- Run or change tests, gates, fixtures, the phone check → `docs/testing.md`
- Touch code standards, a ledger, a budget, move a file, write a guard → `docs/code-standards.md`
- Touch identity (claim / apply gate), income, course data, money, i18n delivery, request hours → `docs/domain-rules.md`
- Need the system map, the engine's shape, or the key files → `docs/architecture.md`
- Want older sprint state or the Mobile-native arc's rules by milestone → `docs/sprint-history.md`

## Overview

HalaTuju (halatuju.xyz, **v3.0.0**, 2026-10-06) is two products in one codebase. The **course guide**
tells a Malaysian SPM or STPM leaver which courses they qualify for, ranks them and writes a report
(golden masters: SPM 5,319, STPM 2,025). The **scholarship platform** runs a funder's bursary end to end:
apply, results and documents read by OCR and AI, a deterministic verdict, interview, QC, award,
sponsors, payments through Vircle, and an organisation's own console (tenancy: organisation → gift →
intake year). Django REST API `halatuju_api/` + Next.js 14 `halatuju-web/`, both on Cloud Run
(asia-southeast1), Supabase PostgreSQL + Storage + Auth (Singapore).

## Build-for-Tenancy Conventions (MANDATORY for all new work)

HalaTuju is becoming a multi-tenant platform (course selector = shared base; scholarship programmes = org-owned tenants; plan of record in `docs/plans/2026-07-14-platform-roadmap-draft.md` at the repo root). Until that lands, **every sprint must follow `docs/build-for-tenancy-conventions.md` (repo root)** so ongoing BrightPath work stops deepening the coupling: new tunables on `ScholarshipCohort` (not module constants), no new "BrightPath"/persona/URL literals, new admin endpoints through the `_AdminBase` gates, referral fields (`PartnerAdmin.org`, `referred_by_org`) NEVER used for access control, billable calls only through the existing seams. The full rules + review checklist are in that doc.

## Architecture

System map, the course engine's shape (DB to Pandas at startup, golden masters), subject keys and the key
files: `docs/architecture.md`. One line: Next.js `halatuju-web` calls Django `halatuju-api` on Cloud Run,
backed by Supabase PostgreSQL; `engine.py` is a GOLDEN MASTER (SPM 5,319, STPM 2,025).

### The two identity rules (full text: `docs/domain-rules.md`)

- **NEVER RETURN THE HOLDER'S NAME.** `POST /api/v1/profile/claim-nric/` answers bare channel TYPES only; a claim is a LINK, never a move; the IC never goes in an application log.
- **One application in play, ONE rule, on the server** (`apply_gate.py`); the web keeps no copy. Do not relax it before M2 (TD-353).

## Deployment (full text: `docs/deployment.md`)

GCP project `gen-lang-client-0871147736`, account `tamiliam@gmail.com`; Cloud Run `halatuju-api` / `halatuju-web`
(asia-southeast1), Supabase Singapore. Read `docs/deployment.md` before any deploy or migration. The rules:

- **A push to `main` IS a deploy request and needs the owner's yes** (`push = deploy`). Root `docs/**` and `CHANGELOG.md` deploy nothing; a file under `halatuju_api/` or `halatuju-web/` does.
- **The tests are the gate** (api: `manage.py check`, `makemigrations --check`, `pytest -n auto`; web: `npm run gates` then `npm run bundle-budget -- --gate`). Run the gate's OWN command lines locally first. Never deploy more than twice per feature.
- **MIGRATE-FIRST, by hand.** Triggers never run `migrate`: apply to production BEFORE the push (postgresql DDL, plus the `django_migrations` ledger row in the SAME transaction). Old image must stay safe: additive and nullable first. Catalogue rows a new gate hides go in AFTER the deploy.
- ⚠ After an `UPDATE` touching a `DEFERRABLE INITIALLY DEFERRED` FK, run `SET CONSTRAINTS ALL IMMEDIATE;` before `CREATE INDEX` in the same transaction.
- ⚠ Adding, pausing or re-timing a Scheduler job means editing `cron_health.EXPECTED_CADENCE` in the same change.
- ⚠ A `node_modules` JUNCTION in a worktree is removed with `[IO.Directory]::Delete('<path>')` BEFORE `git worktree remove`.
- With more than one agent in the checkout: declare files in `AGENT-TERRITORY.log`, stage explicit paths (never `git add -A`), build in a worktree, push with `git push origin HEAD:main`.
- A live re-read through a Cloud Run JOB must carry the service's read flags (`DOC_GENUINENESS_CHECK_ENABLED=1`, `BILLING_USAGE_ENABLED=true`); ⚠ the genuineness flag is on only for the exact value `1`.
- A one-off team command runs through the `release-decisions` job with an args override (recipe in the doc).
- Env vars: ⚠ the Gemini key must belong to the HalaTuju GCP project (prepaid; credit out = outage); ⚠ rotating the Brevo key also means Supabase Auth's SMTP setting; `SPONSOR_MOCK_DONATIONS_ENABLED` is **NEVER in production**; ⛔ `BURSARY_AGREEMENT_ENABLED` needs TD-347 fixed first; `UPDATE_EMAIL_GOLDEN` is local-only and ⛔ never set.
- The api image installs `requirements.lock` (refresh it deliberately); `.dockerignore` is the file that counts for the image.
- New documents go where the doc says: retrospectives `docs/retrospectives/`, release notes `docs/releases/`, history `docs/sprint-history.md`, domain rules `docs/domain-rules.md`.

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
- **DB connections persist (`CONN_MAX_AGE` 600) WITH `CONN_HEALTH_CHECKS` on, on both branches of
  `settings/production.py`** (request #32): a network reset once left a dead connection that 500'd the
  next requests. Never drop the flag; `test_db_health_checks.py` pins it.
- **Paid jobs run only on the owner's word:** `refresh_sponsor_profiles`, `sort_spending --reask-version`
  (and ⚠ its REPORT mode also calls the model and pays), `reextract_documents`, `eval_doc_recognition`,
  a cohort-wide EPF re-read. `rescore_pending_decisions` re-scores EVERY unreleased submitted application
  in every cohort and the release job then emails the new verdict — count first.
- **Never edit production data to make a case look right** — fix the engine, then re-run it.

## Testing (full text: `docs/testing.md`)

The deploy gates' own command lines (a serial run passes things the gate refuses). The heavy ones go
through the machine-wide queue, so parallel sessions take turns instead of slowing each other down
(`credit-discipline.md` → Speed). While building, run only the targeted test files, without the queue.

```bash
cd halatuju_api && python C:/Users/tamil/Python/Settings/_tools/test_queue.py -- python -m pytest -q -n auto -p no:cacheprovider
python manage.py check && python manage.py makemigrations --check --dry-run
cd halatuju-web && python C:/Users/tamil/Python/Settings/_tools/test_queue.py -- npm run gates      # typecheck, lint, i18n, jest, in order
cd halatuju-web && npm run bundle-budget -- --gate
cd halatuju-web && python C:/Users/tamil/Python/Settings/_tools/test_queue.py -- npm run mobile-check    # ANY UI change, before a push (local only)
```

- **Full suites run ONCE locally, right before the push, after the last rebase.** Not after each review
  round or fix — re-run only the affected test files then. Cloud Build runs the full suite again and
  ships nothing red.

- ⚠ Run the API gate with `-n auto`, not serially. ⚠ Frontend: all four gates before any push that deploys web; tsc and `next lint` need 0 ERRORS (`next build` lints before it emits).
- ⚠ For any UI change run `npm run mobile-check` (and `npm run mobile-ledger`); ⚠ interactive behaviour needs a RENDERED test, a source-shape guard is not evidence.
- Golden masters SPM 5,319 / STPM 2,025: if either moves you broke eligibility. Measure your own baseline; never quote an inherited number.
- Reviewing the console locally: SQLite + `seed_local_console`, no production data, ever; never re-run extraction locally.
- Pre-deploy checklist: both suites green; migration applied by hand + ledger row; new table has RLS + `service_role` policy + Advisor 0 errors; eligibility/money/identity adversarial review; version bumps (`VERDICT_ENGINE_VERSION`, genuineness `MODEL_VERSION`, `PROMPT_VERSION`); strings in en/ms/ta; the owner's yes to push.
- ⛔ Never run `cleanup_orphan_blobs --apply` from a checkout or image older than S2 (it deletes staff photos). Dry-run first.
- ⚠ Two roads reach QC (recommend via `verify-accept`, decline via `submit-decline`) and leave different marks; fixtures and the cockpit's rendered tests are in the doc.

## Code standards (full text: `docs/code-standards.md`)

Enforced by tests inside the deploy gate: no file over 600 lines (ledgered ones may not grow), no function of 150+ lines, one rule one home, no skipped tests, no new `# noqa` / `@ts-ignore` / `any`, every `eslint-disable` carries a reason, no unguarded mirror, no unused dependency, the `courses -> scholarship` import ceiling, new tests use the factory, a route may not get heavier (250 kB, median ratchet), applicant-detail GET pinned at 38 queries, the Mobile Standard. The two budget files are `halatuju_api/code-standards.json` and `halatuju-web/code-standards.json` (frozen `baseline` + live `budget` that only tightens). The one-liners that cause damage if missed:

- **NEVER raise a budget, a floor or a ledger**; split the file first, in its own commit, moves only. A new post-H18 query budget is a dated `_admitted` record, never in the frozen `baseline`.
- ⛔ No value import from `@supabase/supabase-js` in `src/` (auth clients only in `supabaseAuthClient.ts`; `import type` is fine).
- ⚠ Next's printed first-load counts the PAGE entry only; moving weight from a page into a layout lightens nothing. ⚠ 87.2 kB is the floor under every route. ⚠ The bundle budget cannot see CSS, fonts or lazy chunks, and does not run in `npm test`; `--from-log` needs the SAME build's `.next/`.
- ⚠ The two query numbers (applicant detail with and without documents) being EQUAL is the point; ⚠ no write path may open or read the document snapshot. ⚠ `query_budgets` keys are route patterns, not file paths.
- Moving a file that is in a ledger: declare the move (`_moved`); ⚠ a guard that READS a moved file by path must follow it in the same change; run BOTH suites.
- ⚠ A tree-walking guard needs a floor; ⚠ allowlist a PATH, never a NAME (TD-277); ⚠ an empty `parametrize` / `.each` corpus generates ZERO tests; ⚠ the two trees watch each other (`test_web_guards_read_live_paths.py`, `crossTreePaths.test.ts`).
- The debt register is not the api gate's (docs edits skip it): `code_health.py` at every close does the duplicate-id check.
- The nine groups the code-health arc harvested (H19) are in the doc.

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

The key-files list moved to `docs/architecture.md` (section "Moved from halatuju_api/CLAUDE.md, 2026-11-03", and the "Key files" section above it).

## Live rules carried from the sprint history (full text: `docs/domain-rules.md`)

Each was learned the hard way; the story is in `docs/sprint-history.md` and `docs/lessons.md`. One line each; the reasons are in the doc.

- **ALL WORK IS PLANNED IN HOURS**: every analysis carries `estimated_hours`, and every completion report compares plan against ACTUAL. ⚠ A bug is not exempt (its charge is `0.0`, a real answer). The point is continuous improvement, not billing.
- ⛔ **FINISHING A REQUEST INCLUDES ITS FIGURES; the owner is not your reminder.** Post the completion report (PLANNED, ACTUAL, CHARGED, and why) then record `actual_hours` / `charged_hours` on that analysis via `POST …/requests/<rid>/analysis/<aid>/hours/`. ⚠ `org_requests.done` refuses without it. ⚠ RECORD LAST, CLOSE NEXT: the gate tests the NEWEST approved analysis.
- **Never raise a budget, a floor or a ledger**; split first. ⚠ `pathway_engine.py` (0 lines of room) and `models/applications.py` (1) are tight. A feature sprint runs the file's split first (owner 2026-09-19).
- ⛔ **Never set `UPDATE_EMAIL_GOLDEN`**: a failing `test_email_branding.py` means you changed what a student receives, and that needs the owner.
- Patching a re-export package can succeed and patch nothing (grep `patch(` and `patch.object(`; use `patch_engine`). `apps/scholarship/constants.py` is a LEAF: add no import.
- **i18n delivery:** only `messages.ts` and `messagesAdmin.ts` are static catalogue imports; ⛔ never add to `oneLocalePerVisitor.test.ts`'s exemption list; ⛔ never use an `admin.*` key outside the console.
- **Serve, never assemble or derive in the browser** (`apply_url`, a gift's `state`, a request's status); one server definition per answer a screen shows; name the server function before building a control, tick or count.
- Status is derived, never stored (invitations). **Never re-run `build_verdict` over old snapshots.** Version bumps are not optional (`VERDICT_ENGINE_VERSION`, genuineness `MODEL_VERSION`).
- **Money:** read Vircle's `Principal Wallet ID`, never `Supp Wallet ID`; the webhook never overwrites a stored `vircle_id`; "sent to a person" comes from `duitnow_type`; a student's name in a spending report is never stored.
- The padlock keys on `nric_locked`, never `identity_verified`. An organisation's Overview layout narrows, never widens.
- A Django `AlterField` that only changes a default does not rewrite existing rows. Node 24 is named in four places (change all four). A STPM `ua_offer` + `suspect` is often CORRECT.
- The debt register: close a TD only with evidence, marker on the defining line, never write inside the Open Items Index.
- **Never conclude an absence from a grep**: authored content lives in the database.

## Next Sprint

Older state blocks and the Mobile-native arc's milestone-by-milestone rules: `docs/sprint-history.md` ("Moved from halatuju_api/CLAUDE.md Next Sprint, 2026-11-03").

### STATE AT 2026-11-03 — REQUESTS LIST R1 LIVE (api-01242-ntg, web-01070-c44; no migration)

- `/admin/requests` is a PAGED, server-filtered list: tabs Needs action · In progress · Closed · All (they PARTITION
  the list; All is the sum), a Bug reports / Features filter on the effective kind, a title / `#id` search, 25 a
  page; tab / kind / q / page in the URL. Lands on Needs action. Web: `components/admin/RequestsList.tsx`.
- `org_requests_queue.needs_action_q` is the ONE Needs-action rule: the nav badge (`AdminOrgRequestCountView`) and
  the Needs-action tab both call it. Change the rule there only, never in a view.
- List rows are LIGHT (`OrgRequestOrgRowSerializer` / `OrgRequestOwnerRowSerializer`; tags served by `row_tags`):
  no thread, attachments or analyses — the detail page reads them via `getOrgRequest(id)`. Do not put them back
  on the row. Tab counts (`summary`) are of the whole fenced list, never the kind / search filter.
- Server default `group=all`, so an old caller reads what it always did; an unknown group / kind is a 400
  `bad_filter`. The old `?status=` was never read and is gone.
- Detail Previous / Next walks the list PAGE you came from (`lib/listNav.ts`, sessionStorage). TD-477: the
  Applications cockpit adopts the same hook after Mobile M6b.

### Mobile-native arc (separate stream): M0-M7b DONE (M7b live 2026-11-03, main fa8dd439, halatuju-web-01075-4d2), NEXT = M8

Roadmap `docs/plans/2026-10-31-mobile-native-roadmap.md`; rules `docs/mobile-standard.md`; ledger `docs/mobile-ledger.md`. Every UI change: `npm run mobile-check` green and `npm run mobile-ledger`; a new `page.tsx` must be classified in `src/lib/mobileClass.ts`; every overlay is `src/components/Sheet.tsx`; every pinned bottom bar on a student or sponsor page carries `data-page-bar`. The per-milestone rules (M1-M7a) are in `docs/sprint-history.md`. **M7b:** `AppShell` draws `components/DesktopOnly.tsx` for the `desktop` routes (`lib/desktopOnly.ts`, held equal to `mobileClass.ts`; a new desktop-only route needs both lists and a reason in en/ms/ta) and hides the page below md BY CSS; the Team / Invitations / Mentors tables are rows on a phone (staff-access actions NOT hidden, Maintenance call).

### ⚠ STATE — TEAM TABLES T5b (NOT LIVE YET; branch maint-s7; no migration, no endpoint, no web change)

Roadmap T5; decisions.md "Team tables T5b". **`qc` IMPLIES `see_all`** (`staff_permissions.IMPLIES`, read by `clean`;
`DEPENDS_ON` is gone): a stored `['qc']` resolves to `see_all + qc`, so every `see_all` reader opens for it by
construction; `_b40_scope` names `qc` too; the editor saves `['qc']` as `see_all + qc` (`qc_needs_see_all` retired).
It is never an Admin hat (`staff_tables.admin_keys` drops that `see_all`). v2: `HAT_IMPLIES` (still not a gate).
**The QC separation guard is `apps/scholarship/qc_separation.refusal`** (asked by `_require_qc`): refuses the current
assignee, anyone EVER assigned (`AssignmentEvent`), any interviewer (a draft counts) or slot proposer, the verdict
recorder, the verify-accepter, and anyone whose activity list records review work on the case; super exempt. **A new
kind of review work belongs in that module** (+ `test_qc_self_sufficient.py`). Open: TD-481 (Decline door at
AWAITING QC), TD-483, TD-484, TD-485. Review round 1: verb `interview_drafted` (migration 0202, choices only) is
written by `AdminInterviewView.post` when a draft's credit moves to the saver, and is a guard verb.

### ⚠ STATE AT 2026-11-03 — TEAM TABLES T5a LIVE (main 55de0610, api-01245-mrb; no migration, no endpoint, no web change)

Roadmap T5; decisions.md 2026-11-03 "Team tables T5a". `apps/courses/staff_permissions_v2.py` = the v2 vocabulary
(`CATALOGUE_V2` page x tier in groups Organisation / Programme / Engagement / Money, `HATS` review + qc, `IMPLIES`,
`DEPENDS_ON_V2`, lead-only marks), `ALIASES` old -> v2, and `effective_v2(admin)` (a READ). **⚠ v2 IS NOT YET A GATE:**
nothing outside the tests imports it (`NotYetAGate` walks the tree), every page still opens through `resolve` /
`has_perm`, `staff_tables.may_*` and the role checks, and `asked_set` refuses a v2 key. **A NEW PAGE must still be gated
the old way AND get a v2 key** in `CATALOGUE_V2` plus a door in `test_permission_catalogue_v2._doors` (the coverage
test asks the real gate per live shape). Next: T5b (QC self-sufficient).

## Known Issues & Future Work

The open debt register is `docs/technical-debt.md` (Open Items Index, in working order); the release
notes list it by importance and size (`docs/releases/release-notes-v3.0.0.md`, Known Issues). Plans:
`docs/roadmap.md` and `docs/plans/`. General rules (testing, deployment discipline, git, cleanup,
British English) are in the workspace-level `CLAUDE.md`.
