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

### Mobile-native arc (separate stream): COMPLETE (M0-M8; M8 live 2026-11-04, main bea7111d, halatuju-web-01079-tv4)

Roadmap `docs/plans/2026-10-31-mobile-native-roadmap.md`; rules `docs/mobile-standard.md` (rules 15-17: one box level; nothing spills out of its box; phone pills via `lib/phonePill.ts`); ledger `docs/mobile-ledger.md`. Every UI change: `npm run mobile-check` green (four numbers: overflow, small fields, small targets, spills) and `npm run mobile-ledger`; a new `page.tsx` is classified in `src/lib/mobileClass.ts`; every overlay is `src/components/Sheet.tsx`; a pinned bottom bar on a student or sponsor page carries `data-page-bar`; a desktop-only route needs `lib/desktopOnly.ts` AND `mobileClass.ts` plus a reason in en/ms/ta. Manifest stays `display: 'browser'`. Per-milestone rules: `docs/sprint-history.md`. **Open mobile work:** TD-489 (mentor screens' white cards), TD-490 (chart first paint on a phone).

### STATE AT 2026-11-04 — TEAM TABLES T5b LIVE (main f44f0a8b, api-01248-ggf, web-01076-gr4; migration 0202 choices only, no endpoint, no web change)

Roadmap T5; decisions.md "Team tables T5b". **`qc` IMPLIES `see_all`** (`staff_permissions.IMPLIES`, read by `clean`;
`DEPENDS_ON` is gone): a stored `['qc']` resolves to `see_all + qc`, so every `see_all` reader opens for it by
construction; `_b40_scope` names `qc` too; the editor saves `['qc']` as `see_all + qc` (`qc_needs_see_all` retired).
It is never an Admin hat (`staff_tables.admin_keys` drops that `see_all`). v2: `HAT_IMPLIES` (still not a gate).
**The QC separation guard is `apps/scholarship/qc_separation.refusal`** (asked by `_require_qc`): refuses the current
assignee, anyone EVER assigned (`AssignmentEvent`), any interviewer (a draft counts) or slot proposer, the verdict
recorder, the verify-accepter, and anyone whose activity list records review work on the case; super exempt. **A new
kind of review work belongs in that module** (+ `test_qc_self_sufficient.py`). Open: TD-481, TD-483, TD-484, TD-485. Review round 1: verb `interview_drafted` (migration 0202, choices only) is
written by `AdminInterviewView.post` when a draft's credit moves to the saver, and is a guard verb. Live access unchanged.

**TD-481 (2026-11-04):** `AdminRejectView` refuses `{category: 'interview'}` on an `interviewed` (AWAITING QC) case
for everyone, super included — 400 `awaiting_qc`; it is declined only at `qc-decision`. The rule sits at the door, NOT
in `admin_reject` / `INTERVIEW_REJECT_FROM` (the QC decision declines through them). Open from it: TD-486 (super's
cancel-reopen), TD-487 and TD-488 (owner's calls). Test: `test_td481_awaiting_qc_decline.py`.

**NEXT = T5c** (owner to rule on TD-487 / TD-488 when convenient).

### ⚠ STATE AT 2026-11-03 — TEAM TABLES T5a LIVE (main 55de0610, api-01245-mrb; no migration, no endpoint, no web change)

Roadmap T5; decisions.md 2026-11-03 "Team tables T5a". `apps/courses/staff_permissions_v2.py` = the v2 vocabulary
(`CATALOGUE_V2` page x tier in groups Organisation / Programme / Engagement / Money, `HATS` review + qc, `IMPLIES`,
`DEPENDS_ON_V2`, lead-only marks), `ALIASES` old -> v2, and `effective_v2(admin)` (a READ). **⚠ v2 IS NOT YET A GATE:**
nothing outside the tests imports it (`NotYetAGate` walks the tree), every page still opens through `resolve` /
`has_perm`, `staff_tables.may_*` and the role checks, and `asked_set` refuses a v2 key. **A NEW PAGE must still be gated
the old way AND get a v2 key** in `CATALOGUE_V2` plus a door in `test_permission_catalogue_v2._doors` (the coverage
test asks the real gate per live shape).

### ⚠ STATE AT 2026-11-03 — TEAM TABLES T4 LIVE (main 7871bb39; api-01244-2rq, web-01073-jxr; no migration)

Roadmap T4; decisions.md 2026-11-03 "Team tables T4". **Team -> Emails** = Admin (read-only list) · Reviewer
(`ReviewerEmailsCard`, moved whole) · Mentor (`InvitationEmailsCard only=['invite_mentor']`, the same template as
Invitations -> Emails), in `components/admin/TeamEmails.tsx` (also `TeamTerms`: three "Soon" sections; the Terms tab is
no longer disabled). The admin list is `apps/scholarship/admin_email_catalogue.py` (`CATALOGUE` of ten rows, each naming
its sender; `NOT_ADMIN_SENDERS` with reasons) served as keys by `GET admin/admin-emails/`
(`views_admin/org_emails.py` `AdminTeamAdminEmailsView`, the `_SponsorEmailsBase` gate; route in `urls_mentors.py`;
matrix cell `T4_ADDED`). **A new non-student `send_*` must be classified there** (`test_admin_email_catalogue`), and its
row needs en/ms/ta words under `admin.team.emails.kind/when/to` (`teamAdminEmailsDrift.test.ts`). HalaTuju's own inbox
(`ADMIN_NOTIFY_EMAIL`) is never listed as the organisation's (lead ruling). Deploy: API first, then web.

### ⚠ STATE AT 2026-11-03 — TEAM TABLES T3 LIVE 2026-11-03 (main 99d8ac1c; api-01243-dzq, web-01070-c44 — web went out in the Requests R1 build 2da37ff4; no migration)

Roadmap T3; decisions.md 2026-11-03 "Team tables T3". **Team -> Mentors** is the old Mentors page's table
(`components/mentors/MentorsAdmin.tsx`, default `TeamMentors` + `MentorDetail`, ONE lazy chunk loaded by the Team page
and by `/admin/organisation/reviewers/mentors/[id]`); `/admin/organisation/mentors` redirects (matched to the Team nav
row; the Mentors row went). Readers = `mentor_invite.may_read` (web `pageGuard.mayReadMentors`). Backend:
`apps/scholarship/mentor_detail.py` (`team_columns` one query; `scholars_of` fixed queries; per-scholar average gap;
open concern = unhandled on a file in maintenance); `views_admin/mentors.py` `mentor_rows(team=True)` and
`AdminMentorView.get` (`GET admin/mentors/<id>/`, matrix cell `T3_ADDED`). `staff_tables_admin`: leaving the last staff
table while mentoring -> role `mentor` (`may_become_mentor`: admin / reviewer / qc, mentors now, signed in, no open
case; plan `becomes_mentor`), else `mentors_only`. Owner scope addition: `GET admin/admins/<id>/permissions/` serves
`tables`; `PermissionEditor` has one section per table (no `table` prop any more; `?table=` only picks the back tab);
the Team tables lost the permission column (`KeyChips` unused there). Review fixes: scholar side only for
`_b40_scope == 'all'` (`_MentorsBase.sees_scholars`; `sees_scholars` served); `staff_mentor.stop` locks the login
row. Deploy: API first, then web.

### ⚠ STATE AT 2026-11-03 — TEAM TABLES T2 LIVE 2026-11-03 (main 54f997a8; api-01241-9hv, web-01069-4vh; no migration)

Roadmap T2; decisions.md 2026-11-03 "Team tables T2" (lead rulings Q1-Q4). **Team -> Admins / Reviewers -> Add and
Remove from** live in `apps/scholarship/staff_tables_admin.py` (`may_act`, `plan_table_change`, `change`,
`candidates`, `row_fields`); views `views_admin/staff.py` `AdminTeamTableView` (`POST admin/team/<table>/`
`{admin_id, action: add|remove, dry_run}`) and `AdminTeamCandidatesView` (`GET admin/team/<table>/candidates/`);
routes in `urls_mentors.py` (urls.py is at the 600-line standard). Add = keys only (+`see_all` / +`review` on the
materialised preset; role untouched); Remove = that table's keys, and the role moves only where the label would keep
them seated (`admin`/`finance` -> `reviewer`/`qc`; `reviewer`/`qc` -> `admin`, who OPENS the admin work pages; the confirm says so). The org
admin may hold `['review']` in `permissions` (`staff_permissions.lead_reviews`; `resolve` ignores every other key
on a lead row; only Add/Remove Reviewers writes it, by a super or the org admin on their OWN row);
`team_holding(..., with_lead=True)` puts them on the Reviewers list. Both Team lists serve `tables`, `lead`,
`admin_keys`, `reviewer_keys`, `remove`. Invites: an org admin invites `admin` / `reviewer` only; a new Admin row
stores `['see_all']` (`staff_tables.invite_permissions`); old finance / qc invitations still accept and stay
cancellable (`KIND_CANCELLABLE_ROLES`). Access matrix: no cell moved; the two new routes are `T2_ADDED`. Web:
`components/admin/TeamTables.tsx` (AlsoIn, KeyChips, RemoveControl, TeamAddSheet, TeamRemoveSheet), `StaffTable`
`team` prop, the person page's `?table=` (PermissionEditor `table`). Deploy: API first, then web (an old web
ignores the new fields; a new web on an old API shows no Add/Remove). Change role (`staff_lifecycle`) refuses a switch INTO finance / qc (409 `label_retired`); a switch out keeps the
resolved keys exactly. `change` re-runs `may_act` on the locked row. Open: TD-475 (credits read the finance role),
TD-476 (a reopened case can strand a removed reviewer; predates T2).

### ⚠ STATE AT 2026-11-03 — TEAM TABLES T1 LIVE 2026-11-03 (main 83cddf96; api-01239-5jr, web-01067-6fr; hats plumbing; no migration)

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md`; ruling decisions.md 2026-11-03 (option B). A person's
TABLES (Admins / Reviewers / Mentors) are DERIVED in `apps/courses/staff_tables.py` (a leaf; never stored):
`in_admins`, `in_reviewers`, `in_mentors` (= `mentors_now`), `tables()`; served by `admin/role/` as `tables`.
**Every admin page gate that is not lead-only goes through `staff_tables.admits` — today's role list OR the Admins
table by a key, never instead**: `may_read_org` (surface_gates `may_read_sponsors` / `may_read_team`, sponsor
pending-count, sponsorships, wallet-credit screens) and `may_do_admin_work` (Sources + witness, Mentors read,
`admin/admins/`, Announcements / Surveys / Development `may_post` / `may_make`, sponsor terms, sponsor / partner
emails; `ADMIN_WORK_KEYS = ()` — no key opens them yet). A new admin key opens a page by being added to its gate.
Web: rows carry `adminKeys`, `admitsRow` reads `tables`, page guards call `lib/pageGuard.ts` `mayOpen`; the landing
(`defaultRoute`) deliberately ignores `tables`. Golden tests: `scholarship/tests/test_team_tables_matrix.py`
(fixture `fixtures/team_tables_access_before.json`, from faacf681 — never regenerate it; a moved cell is a bug or a
line in `EXPECTED_CHANGES`) and `halatuju-web/src/lib/__tests__/teamTablesMatrix.test.ts`. Deploy: API first, then
web (an old web ignores `tables`). NEXT: T2 (the Team page).

### ⚠ STATE AT 2026-11-02 — STUDENT MAINTENANCE SPRINT 10 LIVE 2026-11-02 (main acf86f25; api-01238-972, web-01065-4xf; 0201 applied by hand first; Scheduler job halatuju-module-emails hourly, first run OK) — development modules

**Next free migration numbers: scholarship 0202, courses 0092.** **scholarship 0201_development_modules — MIGRATE
FIRST by hand** (five new tables `development_modules`, `module_lessons`, `module_progress`, `module_lesson_reads`,
`module_emails`, each RLS + one service_role policy; the `student_email_templates.kind` choice `module_published`
needs no SQL; DDL, pre-check, ledger row and rollback in its docstring), then the Security Advisor, then API, then
web, then **create the hourly Cloud Scheduler job `halatuju-module-emails`** (job `module-emails`;
`CronRunView.JOBS` -> `send_module_emails`; `cron_health.EXPECTED_CADENCE` HOURLY already expects it, so the health
light goes red after two missed hours without it). No new bucket: files live in `b40-documents` (lesson
`<org>/development/<module>/<uuid>`, her task `<org>/<app>/growth-<module>/<uuid>`; `cleanup_orphan_blobs` knows
both). Rules: `apps/scholarship/development.py` (`may_make`, `module_status`, `modules_for_file`,
`mark_lesson_read`, `submit_task`, create / update / archive / delete), `development_progress.py` (rows, Progress,
CSV, `review`, the scholar file's tab, `mentor_rows`), `development_files.py` (keys, `verify` = the bytes' type and
size, signed links), `development_emails.py` (`send_due_module_emails`, `remind_not_done`); staff fence
`views_admin/development.py` (`admin/scholarship/development/`, `<id>/` PATCH/DELETE, `<id>/progress/`,
`<id>/progress/<app>/file|review/`, `<id>/csv/`, `<id>/archive|remind/`, `<id>/lessons/<lid>/file/` (+ `sign/`),
`admin/scholarship/scholars/<id>/development/`); her `scholarship/bursary/growth/` (+ `<id>/`,
`<id>/lessons/<lid>/read|file/`, `<id>/task/` (+ `sign/`, `file/`)); summary keys `growth_tab`, `growth_to_do`; the
mentor's `admin/mentor/students/<id>/` gains `modules` (no links), and the mentor-only
`admin/mentor/students/<id>/modules/<module>/file/` signs an upload on the tap (`mentor_methods`; review fix). Routes in `urls_development.py`. `storage.download_object`
gained `max_bytes`. Web: `/admin/programme/development` (+ `[id]`, lazy, Mobile `can`), the scholar file's Growth
tab (lazy `ScholarGrowth`), the mentor page's Growth section, the bursary Growth tab (lazy, `bursaryTabs.growth`).
**MAINTENANCE ROADMAP COMPLETE (Sprints 1–10 live). NEXT (maintenance stream): the parked Team tables T1–T4
(`docs/plans/2026-11-01-team-tables-roadmap.md`) only on the owner's word.**

### Offer letters read exactly (separate stream) — S1–S5 LIVE (S5 2026-11-03, main ae443f45; api-01240-cg2); S6 BUILT on offer-read-s1, not pushed

Roadmap `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md`. AI reader `offer_reader.py` (`OFFER_READER_VERSION`
2.4.0) + IC guard `offer_ic.py` (a non-label or source-less IC is corroborate-only: exactly the profile IC, never a
`mismatch`). The fixed-format Exact read (STPM / matric / poly) is `offer_exact.exact_offer_read` — the ONE entry
point (`offer_parse.py` 2.0.0 shared block reader + `offer_parse_families.py`; the IC guard runs on it and a blanked IC
means NO lock; the parser's keys are written whole, the dates merge-preserve; the reporting date is the DATE ONLY in
the house shape, decisions.md 2026-11-03). Any reader change: `eval/offer_parse_check.py` (Exact read: 0 WRONG / 0
control locks) and `eval/offer_read_check.py` on dev, held-out ONCE at the end, then the production dry run
`eval/offer_s4_dry_run.py` (read-only, rolled back; `--suffix .s5_exact.json` after `offer_s5_caches.py --write` for
the Exact read; send the realign/link/ticks diff to the matcher session; it counts the money reach and any new
wrong-person red) and an adversarial review before the push. Paid Gemini runs only on the owner's yes. **S6 (built,
not pushed):** genuineness `MODEL_VERSION` 1.23.0 — the owner's rulings live in ONE place, `genuineness/offer_rulings.py`
(TVET offers genuine, confirmations by issuer, private suspect → fail, printouts never below suspect); a genuineness
change re-runs `eval/offer_genuineness_check.py` (dev, held-out once) and updates `offer_genuineness_expect.json`.
The submission gate blocks ONLY a not_offer_letter (`pathway_engine.offer_fails`); the offer chips follow the
owner's table (`halatuju-web/src/lib/offerFacts.ts`; Pathway never red) and the ladder counts only Name / IC
mismatch. `pathway_engine.py`'s matcher lives in `pathway_match.py` (TD-473 lands there). Before the push: the
lead runs `offer_s4_dry_run.py --s6` (GO / STOP), adversarial review. NEXT: S7 live re-read (now
safe for the 21 at-risk reads; list = the 6 reporting-date letters + every live letter whose Exact read changed);
S8 keep it exact; the money sprint is separate (TD-465); TD-473 (Cockpit: a pre-U letter ticks Pathway `match`
against a degree pick by a shared word; `pathway_engine.py` split first).

### ⚠ STATE AT 2026-11-02 — STUDENT MAINTENANCE SPRINT 9 LIVE 2026-11-02 (main ab806a87; api-01236-jkr, web-01062-wx2; 0200 applied by hand first; Scheduler job halatuju-survey-emails hourly, first run OK) — surveys

**Next free migration numbers: scholarship 0201, courses 0092.** **scholarship 0200_surveys — MIGRATE FIRST by hand**
(five new tables `surveys`, `survey_questions`, `survey_responses`, `survey_answers`, `survey_emails`, each RLS + one
service_role policy; the `student_email_templates.kind` choice `survey_open` needs no SQL; DDL, pre-check, ledger row
and rollback in its docstring), then the Security Advisor, then API, then web, then **create the hourly Cloud
Scheduler job `halatuju-survey-emails`** (job `survey-emails`; `CronRunView.JOBS` -> `send_survey_emails`;
`cron_health.EXPECTED_CADENCE` HOURLY already expects it, so the health light goes red after two missed hours
without it). Rules: `apps/scholarship/surveys.py` (`may_make`, `effective_status`, `surveys_for_file`, `submit`,
create / update / close_now / delete), `survey_results.py` (staff rows, results, CSV, `scholar_file_payload`),
`survey_emails.py` (`send_due_emails`, `remind_now`); staff fence `views_admin/surveys.py`
(`admin/scholarship/surveys/`, `<id>/` PATCH/DELETE, `<id>/results/`, `<id>/csv/`, `<id>/close/`, `<id>/remind/`,
`admin/scholarship/scholars/<id>/surveys/`); her `scholarship/bursary/surveys/` + `surveys/<id>/answers/`; summary
keys `surveys_tab`, `surveys_to_answer`. Routes in `urls_surveys.py` (`urls.py` is at 600). Student communications
gains the switchable `survey_open` kind under News (ONE wording for the opening email and the reminder). Web:
`/admin/programme/surveys` and `/admin/programme/surveys/[id]` (lazy, Mobile `can`), the scholar file's Surveys tab
(lazy `ScholarSurveys`), the bursary Surveys tab (lazy, `bursaryTabs.surveys`). ⚠ A lazy admin screen that only
reads the session imports `useAdminAuth` from the leaf `src/lib/adminAuthCore.ts` (the provider module drags
`admin-supabase` in, and enough such chunks regroup webpack's shared chunks onto every student route).
**NEXT (maintenance stream): Sprint 10 — development modules, design first; then the parked Team tables T1–T4
(`docs/plans/2026-11-01-team-tables-roadmap.md`) only on the owner's word.**

### ⚠ STATE AT 2026-11-01 — STUDENT MAINTENANCE SPRINT 8 LIVE 2026-11-02 (main adfeddc7; api-01232-zdb, web-01059-4vp; 0199 applied by hand first; Scheduler job halatuju-announcement-emails hourly, first run 200) — announcements

**Next free migration numbers: scholarship 0200, courses 0092.** **scholarship 0199_announcements — MIGRATE FIRST by
hand** (three new tables `announcements`, `announcement_reads`, `announcement_emails`, each RLS + one service_role
policy; the `student_email_templates.kind` choice `announcement` needs no SQL; DDL, pre-check, ledger row and
rollback in its docstring), then the Security Advisor, then API, then web, then **create the hourly Cloud Scheduler
job `announcement-emails`** (`CronRunView.JOBS` -> `send_announcement_emails`; `cron_health.EXPECTED_CADENCE` HOURLY
already expects it, so the health light goes red after two missed hours without it). Rules:
`apps/scholarship/announcements.py` (`may_post`, `live_q`, `for_file`, `send_due_emails`); staff fence
`views_admin/announcements.py` (`admin/scholarship/announcements/`, `<id>/` PATCH/DELETE, `<id>/withdraw/`; the org
from `?programme=` inside the caller's own, else theirs; an org-less super must name a gift); her
`scholarship/bursary/news/` + `news/read/`; summary keys `news_tab`, `news_unread`. Routes in `urls_announcements.py`
(`urls.py` is at 600). Student communications gains the switchable `announcement` kind under a News heading. Web:
`/admin/programme/announcements` (lazy, Mobile `can`), the bursary News tab (lazy, `bursaryTabs.news`).

### ⚠ STATE AT 2026-11-01 — STUDENT MAINTENANCE SPRINT 7d LIVE (main fe6f21de; api-01229-4x6, web-01056-pld; courses 0091 applied by hand first) — staff can also be mentors

**Next free migration numbers: courses 0092, scholarship 0199** (7d adds NO scholarship migration). **courses
0091_partneradmin_staff_mentor — MIGRATE FIRST by hand** (drop + add the relaxed CHECK
`partner_admin_mentor_iff_mentor`: role `mentor` ⇒ `mentor_id`; `mentor_id` ⇒ mentor / org_admin / admin / reviewer
/ qc / finance, never a super; DDL, pre-check, ledger row and rollback in its docstring), then API, then web. Rules:
`apps/scholarship/staff_mentor.py` (add, Stop mentoring, Mentor again, `leave` — called by People → Revoke and
Delete, a staff invitation's Cancel and Admin → Finance); "mentors now" is ONE predicate,
`PartnerAdmin.mentors_now` (desk `mentor_desk.mentor_of`, `staff_contact.works_with_students`, `admin/role/`
`mentoring`, the web's `navigation` `staffMentors` row and `profileCards.mentorsNow`). 7a's mentor doors refuse a
staff mentor (`mentor_invite.is_staff_login`, 400 `staff_mentor`); `_switch_off` is never reached for one. New
route `admin/mentors/staff/` (GET candidates, POST add; super / org_admin). Mentoring counts as staff WORK
(`staff_footprint` `scholars_mentored`): a staff member who has mentored is revoke-only.

### ⚠ STATE AT 2026-11-01 — STUDENT MAINTENANCE SPRINT 7c LIVE (main e5bf699c; api-01228-98t, web-01054-7mz; 0198 applied by hand first) — mentors see their students and log meetings

**Next free migration numbers: scholarship 0199, courses 0091** *(superseded by 7d above — courses 0092)*. 0198 = `0198_mentor_logs_meetings` (four
additive columns on `mentoring_sessions`, defaults kept in the database): **MIGRATE FIRST by hand** (DDL, pre-check,
ledger row and rollback in its docstring), then API, then web. A mentor's own door is `apps/scholarship/mentor_desk.py`
+ `views_admin/mentor_students.py` (`admin/mentor/students/`, `<id>/`, `<id>/sessions/` — the only 7c additions to
`mentor_methods`, pinned by `test_mentor_desk.TestTheMentorMethodsAreTheListedOnes`); the meeting rule is 7b's
`mentoring.clean_meeting` / `write_session`; staff clear a concern with `POST .../mentoring/handle-concern/`. Web:
`/admin/my-students` (+ `/[id]`, Mobile must), the `mentoring` nav scope (mentor only, their landing).

### ⚠ STATE AT 2026-11-01 — STUDENT MAINTENANCE SPRINT 7b LIVE (main 7dc9c15d; api-01224-s6w, web-01047-lvq; 0196 applied by hand, ledger row in)

Mentoring: `MentorAssignment` / `MentoringSession` (scholarship **0196_mentoring — MIGRATE FIRST by hand**, DDL +
RLS + service_role policies + ledger row + rollback in its docstring, then the Security Advisor), rules in
`apps/scholarship/mentoring.py`, staff tab `views_admin/mentoring.py` (`admin/scholarship/scholars/<id>/mentoring/`
+ `assign/`, `end/`, `sessions/`; super / org_admin / admin only), the student's `scholarship/bursary/mentoring/`,
"You have a mentor" (`student_comms` kind `mentor_assigned`, switchable, Mentoring heading). Deactivate / Revoke
and closing a file end open assignments. **Next free migration numbers: scholarship 0198, courses 0091**
(0197 = the S7b follow-up's `0197_invite_mentor_template`, choices only: the ledger row by hand before the push,
then `seed-partner-emails` after the deploy so the editable mentor letter has its row) — LIVE 2026-11-01 (main 23ec0494; api-01226-p5d, web-01052-v94; 0197 ledger row by hand, `invite_mentor` seeded):
mentors are invited on Invitations → Mentor; the Mentors page manages arrived mentors (Mentors · Emails · Terms).
NEXT: Sprint 8 (Announcements) or 7c, on the owner's choice. Later: 7c — mentors see their students and log meetings
*(superseded: 7c built — see the state block above; scholarship 0198 claimed, next free 0199)*.

### ⚠ HAND-OVER 2026-11-02 (Cockpit session, offer-letter + exam-year work) — read this first

Live on main 49e50778: offer realignment (Bumi-only + DATE rule), offer link, empty-pick fill (#202), one campus
test (`offer_course_match.CampusReader`), and route-aware exam-year colours (`apps/scholarship/exam_years.py`; owner
table: SPM-only → SPM C−1; STPM → STPM C−1 + SPM C−3; matric/asasi → C + SPM C−2; diploma → C−1 or C + SPM C−4;
display only). All live repairs applied (realign 13 + 27, link 9, fill #202).
**ONE OPEN JOB, owned here:** the profile session's offer-reader S4 (branch `offer-read-s1`,
`docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md`) will return `institution` = name only, `campus` = as
printed, hostel/venue in neither (`reporting_venue`), `issuer` unchanged; it also reads the UPM reference-line NRIC
(#175). Before S4 pushes, the matcher must read `campus` and join it with `institution` for per-campus families
(poly / KK / IPG / IKBN / IKM / KKTM) in `match_offer_course`, `letter_place`, `CampusReader` (fed from
`pathway_engine.student_offer_check`). S4 sends a realign/link/tick dry run first and waits for this change.
**DONE 2026-11-02, pushed to main (api only, no migration; confirm the build + revision):**
`offer_course_match.letter_institution` is the one join (SPACE-joined, the pre-S4 shape — a ", " join hid clashes,
review 2026-11-02); `student_offer_check`, `align_institution_to_catalogue` and `offer_reporting_bonus` read the campus
(`test_offer_campus_split.py`). Once the revision serves, S4 may send its realign/link/tick dry run.
⚠ `pathway_engine.py` is now AT its line allowance (633).
Owner rules to keep: Check 1 records facts, only gift rules restrict; a reviewer judges a stale intake (#202).
Open debt: TD-447–449, TD-451, TD-452.

### ⚠ STATE AT 2026-11-01 — OFFER REALIGNMENT + DATE RULE + OFFER LINK LIVE (main 9969c1f3; api-01225-fxd; no migration)

**Follow-up live 2026-11-01:** owner DATE rule — a pick on an application submitted before
`services/offer_sync.PICKER_COMPLETE_AT` (2026-10-31 13:10:21 MYT, the complete picker) whose profile was not saved
since is not a real selection; the student's own genuine offer replaces it (any course). `link_offer_courses` links
an offer-sourced labels-only pick to its catalogue course (`services/offer_link.py`, source kept). Campus naming is
ONE shared test, `offer_course_match.CampusReader` (own name / unique acronym / `_ALIASES`; else own words with a
non-place, non-`_TYPE_WORDS` word; a line naming another institution outright never names the campus); the level
check is exact (`letter_level` vs `course_level`). Both commands applied on live (27 realigned, 9 linked). Open:
TD-451, TD-452. Retro: `docs/retrospectives/retrospective-2026-11-01-offer-date-rule-and-link.md`.


The offer → course matcher is `apps/scholarship/offer_course_match.py` (`match_offer_course`, `letter_place`,
`is_bumiputera_only`); `offer_pathway.resolve_catalogue_course` is a thin caller with an optional `issuer`. It reads
BOTH catalogues (`StpmCourse` too), names institutions in tiers (exact name / unique acronym, then the issuer, then
words with the institution's words inside the line), and returns one course or none. Owner rule: a genuine, own
offer for a Bumi-only course replaces a student-made pick on an undecided case (`services/offer_sync.plan_bumi_realign`);
`realign_bumi_offers` (report default, `--apply`) was applied on live 2026-11-01. `is_bumiputera_only` is pinned to
one reader and one caller (`test_bumiputera_blind`); never read `StudentProfile.bumiputera`. Open: TD-447, TD-448,
TD-449. Retro: `docs/retrospectives/retrospective-2026-11-01-offer-realignment.md`.

### ⚠ STATE AT 2026-10-31 — STUDENT MAINTENANCE SPRINT 7a LIVE (main f0bcc0f0; api-01218-7sr, web-01041-xhh)

Migrations scholarship 0194 and courses 0090 APPLIED BY HAND 2026-10-31 and recorded — never re-apply that DDL.
Retro: `docs/retrospectives/retrospective-2026-10-31-maintenance-s7a.md`. Open from the review: TD-440 (staff
Resend, pre-existing). **NEXT = Sprint 7b** (assignments, meetings, the Mentoring tabs, "You have a mentor").

**What it is.** Mentors log in, on the source-partner pattern: role `mentor`, `scholarship.Mentor`
(`PartnerAdmin.mentor`, `Invitation.mentor`), deny by default (`mentor_methods`), the Mentors page
(`/admin/organisation/mentors`, `GET admin/mentors/`, actions `admin/mentors/<id>/<action>/`, invite through
`POST admin/invitations/` `audience='mentor'`), and the mentor's own profile (`admin/me/` `mentoring_area`;
`staff_contact.works_with_students`). Rules: `apps/scholarship/mentor_invite.py`. Next free migration
numbers: scholarship 0196, courses 0091 *(superseded by 7b above — 0197)* (0195 = common profile S3, live). Release order: apply scholarship 0194 THEN courses 0090 by hand
(DDL + ledger rows in each docstring; the new `mentors` table gets RLS + one service_role policy in the
same transaction; then the Security Advisor), then API, then web. Next: Sprint 7b (assignments, meetings,
the Mentoring tabs) — 7b's mock-ups are in the maintenance design project.

### ⚠ STATE AT 2026-10-31 — COMMON PROFILE ARC DONE: S1+S2 LIVE (main `3ad1f387`, migration 0193) and S3–S5 LIVE (main `d85eedbc`; api-01220-drw, web-01044-mjt; migration scholarship 0195 applied by hand + recorded; back-fill applied)

**What it is.** One `/admin/profile` page for EVERY role (source users included), built from the card registry
`halatuju-web/src/lib/profileCards.ts` (`PROFILE_CARDS`, `cardsFor`); cards in `src/components/adminProfile/`
(one lazy chunk). Reviewer cards follow the `review` PERMISSION; the first-sign-in hold stays Reviewer-ROLE only.
API: `GET/PATCH admin/me/`, `POST admin/me/password/` (current password checked by a Supabase grant, flag-owed
temp password cleared in the same write, other sessions signed out, atomic 5/15 min attempt slots),
`POST/DELETE admin/me/photo/` (Pillow re-encode, no metadata, `staff-photos/<id>/…` in the private bucket).
`StaffProfile` = alias of `ReviewerProfile` (table `reviewer_profiles`, +6 columns in 0193 incl. `other_language`).
Roadmap `docs/plans/2026-10-31-common-profile-roadmap.md`; retro `retrospective-2026-10-31-common-profile-s1-s2.md`.

**S3–S5 LIVE 2026-10-31 — My activity.** Table `staff_activity` (`models/staff_activity.py`), the ONE best-effort
writer `staff_activity.record()` (savepoint, never raises, closed verb + meta-key lists, no free text), every verb
in `staff_activity.WIRED` (drift test `tests/test_staff_activity.py`); courses-side actions through
`apps/courses/staff_activity_hook.py`. Reader `GET admin/me/activity/` (`staff_activity_read.py`: own rows only,
D7 removed, D8 names decided at read time by the screens' own gates in `surface_gates.py`; source users and
mentors are outsiders). Web: the My activity card (`components/adminProfile/ActivityCard.tsx`, words
`lib/profileActivity.ts`, drift test `profileActivityDrift.test.ts`). **A NEW VERB needs: the TextChoice, a
`record()` call listed in `WIRED`, a `KIND_OF_VERB` entry, and its en/ms/ta sentence** — the two drift tests
turn red otherwise. Back-fill `manage.py backfill_staff_activity --dry-run | --apply` was applied once
(961 rows, `backfilled=true`); it is idempotent and rebuilds only before the earliest live row — never needed
again unless the table is emptied. Doors left unwired on purpose: see CHANGELOG S3. Open: TD-442, TD-443, TD-444.

**Gotchas.** Never run `cleanup_orphan_blobs --apply` from a pre-S2 checkout (it would delete staff photos).
The live sign-in captcha against the service-role password grant is UNVERIFIED: if it blocks, the change answers
503 `supabase_unavailable` (never "wrong password") — read the auth logs after the first real password change.
TD-439 (resolved 2026-10-31): `phone` / `share_phone_with_students` are read-only on reviewer-profile.

### ⚠ STATE AT 2026-10-30 — SCHOLARSHIP "MY PLANS" REDESIGN LIVE (main `53706f21`; api-01212-lr2, web-01035-m7b)

**What it is.** The apply form's and /profile's Plans step asks "Have you received an offer…?" (labels only:
`pathway_certainty` stays `sure` / `uncertain`), names the institution FIRST then the course, and is NOT filtered by
results unless the student switches "Eligible only" on. Its catalogue is `GET /api/v1/courses/offerings/?pathway=`
(`apps/courses/views_offerings.py`: public, unfiltered, Bumi-only and inactive included). `chosen_programme` gains
`institution` (catalogue spelling) + `institution_id`; **every writer of `institution` goes through
`card_display.with_institution`** — never write that key directly. No migration. Decision: decisions.md 2026-10-30;
retro `docs/retrospectives/retrospective-2026-10-30-my-plans-redesign.md`.

**Follow-ups / what to know:**
- The student's OWN pick now shows on the sponsor card and contract until her offer settles it; a wrong-campus pick
  reads as a clash (red ladder chip + `pathway_confirm`) until she confirms the letter — owner accepted.
- **Never add a qualification filter to a scholarship-side picker** (memory: scholarship pickers unfiltered); the
  course guide stays filtered. `lib/planPicker.scope.test.ts` guards which files may call the eligibility endpoints.
- TD-434 (latent): the TVET pathway map's first-category-wins rule decides which picker lists a TVET course; 0 live
  cases today — re-check after any TVET ingest.
- Not driven live: the signed-in apply form (no test account). Bundle median 147.698 kB against 148 (TD-427).

### ⚠ STATE AT 2026-10-30 — SOURCE SIGN-IN LIVE (main `14537b10`; api-01211-psc, web-01034-n7j)

**What it is.** A referral source can now be invited and sign in (new role `source_partner`, `PartnerAdmin.source`).
Invitations → Source replaces "Add source"; the Sources page's Edit locks once the source has joined. A source user
is denied every existing view by default (`PartnerAdminMixin.get_admin`) and reaches only `api/v1/admin/source/…`:
a read-only console of its own students (stage = what the student sees), its Profile, and the bursary witness step
on the student's page (`?step=witness`). Roadmap `docs/plans/2026-10-30-source-sign-in-roadmap.md`, retro
`docs/retrospectives/retrospective-2026-10-30-source-sign-in.md`.

**DEPLOYED 2026-10-30.** `courses/0089`, `scholarship/0190`, `scholarship/0191` were applied MIGRATE-FIRST by hand
with their ledger rows (checked afterwards: 3 rows, 4 columns, 1 check constraint) — **never re-apply that DDL.**
Both builds green, api health 200, no 5xx after the deploy. No source has been invited yet.
`BURSARY_AGREEMENT_ENABLED` stays OFF, so no witness email is sent — the web route the emails link to is live.

⚠ **Bundle budget: the first-load median reads 147.751 kB against 148 (0.25 kB of room), and
`/scholarship/application` is 0.13 kB under its line.** The next web change that grows a route may tip the gate
(TD-427, TD-433). Measure before pushing; never raise the line.

**Owner items open:** (a) confirm the witness source may see the FULL contract, which includes NRICs and amounts
(owner ruled "full contract"); (b) the witness declaration wording. CLOSED 2026-10-30: inviting a source is
super / org_admin only — owner confirmed; the Admin role no longer adds sources. CLOSED 2026-10-31: the source's
student page keeps the missing checklist parts (names only) — owner confirmed.

### ⚠ STATE AT 2026-10-29 — READ THIS FIRST

**PAYMENTS FOLLOW A DEFAULT SCHEDULE THAT MIRRORS CONTRACT 10 (LIVE 2026-10-29, `e6a03fb3`, api-01191-f9p).**
No contract template is active, so `default_schedule.py` pays every student: RM200; Poly/University skip
November, STPM skips December and June, every pathway stops after its last month. Edit it together with the
seed fixture (a drift test ties them). ⚠ A draft run keeps the line-up it was made with: the November draft
made before this deploy is being cancelled and re-created by admin staff (owner). Retro
`docs/retrospectives/retrospective-2026-10-29-default-schedule-c10.md`.

**THE FIRST REAL INVOICES ARE ISSUED AND SENT.** INV-2026-0001 July RM0.00, INV-2026-0002 August
RM790.86, INV-2026-0003 September RM179.89 — all three emailed to surithiru@gmail.com. **Do NOT
void, re-issue or re-number anything under scholarship billing without asking the owner.** Live:
`halatuju-api-01175-xll`, `halatuju-web-01009-x22`. Migrations `scholarship/0181` and `0182` were
applied MIGRATE-FIRST and recorded — never re-apply that DDL.

**ALL OF THE BILLING WORK IS LIVE (2026-10-30, main `d602faaf`; `halatuju-api-01192-m29` on 100%,
api health 200).** Migrations `scholarship/0184`, `0185` and `0187` were applied MIGRATE-FIRST by
hand and recorded — **never re-apply that DDL**. Backend 10,302 pass / 3 skipped, web 4,981 / 319
suites.

⚠ **DEVELOPMENT BILLING NO LONGER READS `quote_hours`.** The owner audited all sixteen billed
requests on 2026-10-29 and found five wrong (10, 14, 28, 30, 31) because billing charged the PLAN
while the closing report had published a different number. **The authority is what was
communicated back to the requester.** `OrgRequestAnalysis.charged_hours` is what reaches an
invoice; a finished request with none REFUSES the month (`actual_hours_missing`, absolute, not
overridable). `charged_hours = 0.0` is a real answer and is not NULL. **Nothing parses the prose
— a person types the figures.**

1. **The busy-meter guard** (`metered_without_cost` in `invoicing.readiness`, `metered_usage.py`).
   An invoice REFUSES when the meter recorded this tenant's billable calls for the month but the
   metered bucket of the cost ledger reads RM0.00 — the October fault, written down as a guard.
   Overridable with a written reason (a free-tier month is real); **the monthly job overrides
   nothing.** ⚠ **The early diagnosis blaming prepaid Gemini credits was WRONG** — AI Studio and
   the GCP report both read RM34.95 for October, so the export already covers prepay AND postpay.
   Do not rebuild that theory; the cause was `sync_gcp_costs` not having been run. The split also
   found a real bug: `tenant_shares` / `reconcile` crashed on an unreadable month.

2. **The tenant payment declaration** (`0184`, `payment_declarations.py`,
   `AdminInvoiceDeclarationView`, `InvoicePaymentPanel.tsx`). `Unpaid → Payment declared → the
   owner checks the bank → Paid`, a reasoned rejection falling back to unpaid. **Date + bank
   reference only, no amount and no slip** — an amount posted by hand is ignored. ⚠ **A
   declaration does NOT mint a receipt**; confirming calls `invoicing.record_receipt`, still the
   one place a receipt is raised. A receipt outranks a claim, so money in plus a claim open reads
   `part_paid`. The owner is EMAILED on a declaration (`ADMIN_NOTIFY_EMAIL`), with no amount in it.

3. **The owner's four readings of the live page** (2026-10-29, after the above shipped):
   - **Nothing owed is never late.** A zero balance reads "Nothing to pay", not a red "Overdue"
     (July is discounted to zero). NOT "Paid" — no money arrived, and `Invoice.status` never
     claims it did.
   - **Dates are DD-MM-YYYY** on the tenant's declare box (`isoFromDayFirst`, which refuses a day
     that does not exist). The owner's own date boxes are still ISO; neither audience sees both.
   - **`(REQ-12)` links to `/admin/requests/12`** — just the number. Read back OUT of the frozen
     line text, so the three invoices already sent have the links too. The PDF is untouched.
   - **The receipt is EMAILED with its PDF** (`0185` adds `emailed_at` / `emailed_to`), on Record
     payment and on confirming alike; the screen says "Emailed 29 Oct" or, in amber, "Not emailed".
     ⚠ `invoicing.email_receipt` is a SEPARATE call run AFTER the money is committed, because
     `record_receipt` is itself called from inside `confirm_payment`'s transaction. A mail failure
     never undoes the money. Receipts live in `invoice_receipts.py` (moves-only split, 2026-10-29).
   - **Answered, not changed:** the invoice PDF is already attached when a super presses Send.
     Issuing stays silent by the owner's standing rule.

4. **The published hours, and corrections of an earlier month** (2026-10-30, `0187`;
   `request_hours.record_hours`, `charge_adjustments.py`, `OrgBillingCorrection`).
   - **The hours panel sits ONCE, under the QUOTE** (`RequestHoursForm`, super-only), writing to
     the analysis the invoice reads (`requestStatus.hoursAnalysisId`, pinned to the server's
     `closing_report` by `hoursAnalysisDrift.test.ts`). ⚠ It was first rendered on every approved
     analysis card, and request #3 has two — the second kept claiming the invoice would refuse
     after the figures were already recorded. One claim about the request, one place on the screen.
   - **A wrong month is corrected in a LATER one, never by editing a sent invoice.**
     `OrgBillingCorrection`: signed amount, a REQUIRED reason that is PRINTED on the tenant's
     invoice, optionally the invoice it puts right. `period_month` is the month that CARRIES it.
     ⚠ **The order is load-bearing: subtotal → discount → corrections → total.** A discount is a
     percentage of this month's work; a correction is a fixed sum putting an earlier bill right,
     so discounting one would shrink a refund we owe and July's 100% discount would erase it.
     Frozen onto the invoice at issue (`corrections_myr`, `corrections_snapshot`).
     A credit bigger than the month REFUSES (`correction_exceeds_month`) — split it by hand.
   - **Both audiences see the FINAL label** (`OrgRequestOrgSerializer.kind` → `_effective_kind`),
     so a charge links to a request labelled the way it was billed. Nine were mislabelled.

**ALL 16 BILLED REQUESTS NOW CARRY THEIR PUBLISHED FIGURES (2026-10-30).** Zero missing. ⚠ The
owner's own audit figure was SHORT: August's over-charge is **8.5 h = RM195.50**, not the 5.5 h
first computed, because **request 12 was billed at its 6.0 quote after its report said "three is
what you are charged"**. August billed 27.0 h against 18.5 h published (10: 15.0→11.5, 12:
6.0→3.0, 14: 2.0→0.0). `OrgBillingCorrection` id 1 carries −RM195.50 on 2026-10, linked to
INV-2026-0002. ⚠ #38 published NO actual ("added work; we are charging the 82 hours quoted") — the
owner supplied 82. #28's October hours row was corrected 2.5 → 5.0 before invoicing (an
under-charge; no correction row needed, the month is not issued).

**Owner still to do:** the October **Supabase, Twilio and Workspace** bills — the ONLY thing now
blocking October, which will bill 140.5 h less the RM195.50 credit. Also: convert the held
Anthropic rows for October and November once each month ends. **Blocked on permissions:** deleting the orphan `.worktrees/budget-base` (already
git-pruned, no junctions, three harmless files).

---

**Student maintenance Sprints 1–6b are ALL LIVE (S1 `99ee813b` + migration `scholarship/0183`, S2 `1debc6cc`,
S3 `c007883e`, S4a `10072c71` + `scholarship/0186`, S4b `47d00f11` + `scholarship/0188`, S5a `cebc9850`, S5b
`2b62a6f8`, S6a `a1c9f85b` + review `002c6ad7` + `scholarship/0189` (api-01209-74s, 2026-10-30 ~08:20 UTC; 0189
applied by hand first, recorded — never re-apply that DDL); retros `docs/retrospectives/retrospective-2026-10-29-maintenance-s1.md` …
`-s4a.md`, `retrospective-2026-10-30-maintenance-s4b.md`, `-s5a.md`, `-s5b.md`, `-s6a.md`; roadmap
`docs/plans/2026-10-29-student-maintenance-roadmap.md`). S6b letters LIVE 2026-10-31: `0e506798` + review
`98b0f964` + `scholarship/0192_letters` (applied by hand first, recorded — never re-apply that DDL; api-01213-crq,
web-01036-mkf; retro `retrospective-2026-10-31-maintenance-s6b.md`). NEXT = Sprint 7, mentors (records) — design
first. Next free scholarship migration: 0193 (superseded: see the S7a state above — 0195).**
- Letters (S6b): `letters.py` is the rule (who issues which kind, the typed name, closed-file kinds, withdraw,
  acknowledge, the one `state`), `views_admin/letters.py` the fence, `urls_letters.py` the routes (urls.py is at 600).
  Documents only: never a status or money write. The notice email `letter_issued` is locked and NOT behind
  `MAINTENANCE_REMINDERS_ENABLED`; `emailed_at` only when it went. PDFs en/ms only, `<org>/<app>/letters/<id>.pdf`. Design of record: https://claude.ai/artifact/LFHNYc4ynsyKLn6ZZtzReC.
- **6b rulings already made (owner, 2026-10-30, decisions.md):** termination/suspension letters are DOCUMENTS ONLY
  (staff use Hold and Close; after a termination letter the file prompts "close the file?"); letter PDFs in English
  or Malay (the PDF stack cannot shape Tamil), the notice email and screen in her language. A funded student's close
  sends NO email today; the `file_closed` notice belongs with 6b's close-out letter.
- Student comms (S6a): `student_email_catalogue.py` lists all 29 (drift test over every `send_*` in `emails/`);
  `may_send(application, key)` is THE gate at every send site of the 9 switchable emails (award confirmed is LOCKED,
  owner 2026-10-30) — best-effort (a failed read SENDS); no row means on, a locked
  key always sends, the env flags outrank the row. `StudentEmailSwitch` (no seed) + `StudentEmailLog` (the worded
  family's last sent; code-owned last sent reads `usage_events`). ⚠ **MIGRATE FIRST** — the submit's acknowledgement
  reads `student_email_switches`. The usage_context fixes are FORWARD-ONLY: never backfill `usage_events`.
- `MAINTENANCE_REMINDERS_ENABLED` is **ON in production** (api env, since 2026-10-30): the results emails are live.
  ⚠ **OWNER PENDING (S4b):** the Cloud Scheduler jobs `results-overdue-flag` (08:00 MYT) and `results-due-reminders`
  (08:30 MYT) — the System health light expects both.
- ONE predicate, `maintenance_scope.py`; the MONEY hold is separate (`maintenance.is_on_hold`), needs
  `payments.may_prepare` to place or lift (403 `hold_needs_payments`).
- Admin: `/admin/scholars` (+ `/<id>`) by the Applications rule; the sub-state + post-award Close live in the file
  header (`ScholarControls`); the cockpit keeps the pre-award Close and, for a payable student with NO file, her
  status control (`maintenance_controls`).
- Student: `/scholarship/bursary` (`/scholarship/in-programme` redirects) from `scholarship/bursary/summary/` —
  `support_paused` only, never a sub-state; the header link is a `localStorage` hint, not a gate.
- ⚠ **MIGRATE FIRST for anything that writes `student_activity`**; deploy the api before the web.
- Results (S4a): recorded on the predicate WITH a portal-uploaded slip (owner ruling: emailed docs not accepted;
  no staff attach path); ONLY an accepted result counts — standing (`standing.py`, org `maintenance` settings) and
  every sponsor reader go through `results_review.accepted` (per-function doors fence in `test_results_review.py`).
  A slip is evidence: never deletable, replaceable, listed with her documents or re-read by a sweep.
- Due dates (S4b): `results_expectations.py` — terms CHAIN from the stored rows (first term from the funding date,
  no back-dated debt); ONE late rule (`late`) for standing, list, file, hub and both jobs; student emails
  (`student_comms.py`, defaults in code, org rows only when edited) are all dark behind `MAINTENANCE_REMINDERS_ENABLED`
  and never go to a student on hold.
- Money and Contract (S5a): `scholar_money.py` — money ONLY through `payments.paid_to_date` / `_remaining`
  (five readers held equal by one test); spending only with `has_perm('spending')`, by category CODE, unfolded;
  contract = `platform_signed` (binds + organisation countersigned + PDF; the witness is optional), PDF link 300 s,
  minted on request, only for this application's own `<org>/<app>/…` path.
- Her Funds + Contract (S5b): `views_bursary` (`_own_file`, 404 `no_file`), `scholar_money.student_funds` /
  `student_contract` — totals plus categories only (owner ruling (a)); a CLOSED file sends `closed` + `remaining:
  null` (never a promise); her words live in their own message slice (`bursaryTabs`, `lib/messagesBursary.ts`,
  imported by the bursary PAGE only); `SpendingCard` takes its words from the caller (`copy`, required).

---

**Bumi + Islamic coverage: Sprints A to F2 are LIVE; the arc is COMPLETE (Sprint E dropped). F1 2026-10-30,
`a60662cc`; retro `docs/retrospectives/retrospective-2026-10-30-bumi-sprint-f1.md`; F1b held flag fix
`579e27ca`, retro `retrospective-2026-10-30-bumi-sprint-f1b.md`; F2 MARA `2127fda6`, retro
`retrospective-2026-10-30-bumi-sprint-f2.md`). F1 added 35 public non-MARA UP_TVET courses
(`TVET-<id_kursus>`; 2 Bumi-only KEMAS), 33 campus links to held courses, institutions IKBN-022 / ILKA-001..003,
and pathways `mara` + `tvet_other`. F1b set the 63 held courses' flags from their pages (rollback: `fix_held_tvet_flags --reverse --apply`). F2
added 181 public MARA courses (177 Bumi-only; 4 GIATMARA pages silent on Bumi stay open), 606 offerings and
institutions MARA-001..233 (rollback: `ingest_tvet_courses --file data/tvet/tvet_new_courses_F2.json
--rollback-sql`, read-only checks first).** Follow-ups: the 59 flagged F2 rows (54 no SPM route); the 20 held TVET courses with no October page (still no `req_malaysian`); the 92 out-of-scope held
differences in `held_flag_fix_F1b.json` (`three_m_only`, subject rules); the 90 flagged rows; fixture drift — UL0481001, FB0500001 (prod
only) and IKBN-DIP-002 (fixture only); college lists for the 2 Bumi matric tracks; F2: a grouped TVET course's DISPLAY text (the age remark, level, duration) comes from its FIRST
campus only — TVET-30715 shows age 15-55 though 7 of its 8 campuses say 15-70; TVET-30733, 30754, 34179 and
48236 have mixed duration or level across campuses (not fixed in F2; eligibility is unaffected). The Bumi answer stays
course-guide only. Adversarial review before push; the lead's read-only prod SQL checks the review file's
own ids and pairs before the push.

**Back-issuing invoices is READY TO PUSH (2026-10-28; retro
`docs/retrospectives/retrospective-2026-10-28-back-issue-invoices.md`).** A super may now set an invoice's
printed issue date, so July can say 15 August — bounded by `invoicing.issue_date_for`: never after today,
never on or before the last day of the billed month, never in a closed calendar year (the printed year opens
that year's run of numbers). `_refuse_out_of_order` keeps the series and the calendar agreeing: **issue the
OLDEST month first.** The "To issue" tab gained a month picker (the endpoint always took `?month=`; the screen
never sent it) and an issue-date box, in `halatuju-web/src/components/admin/InvoiceToIssue.tsx`.
- **`[REQ-n]` is stripped from a printed development line** (`invoicing.printable_module`) and STAYS in
  `OrgBuildHours.module`, which is what makes a request countable as billed. Only lines frozen from now on.
- **A back-dated invoice carries TODAY's issuer, bill-to and payment terms** — none of the three is versioned.
  The money is the billed month's (rates and discounts are month-keyed); the identity and terms are not.
- **`record_platform_cost --month <month> --convert-held`** gives a held foreign row its ringgit figure at the ECB
  closing rate for the month's last day. Nothing could do this before: `import_invoices` fetches the rate at
  import time and never returns, so a bill imported before month-end stayed unconverted forever.
- **Supabase's INVOICE parses as well as its RECEIPT** ("Amount due" / "Amount paid"), and a window that has
  not started is refused rather than filed under a month that has not closed.
- **Development lines are GROUPED (owner, 2026-10-29).** A *"Feature requests, <month>"* line carries the
  group's hours, the billed rate and the whole group's amount; one sub-item per request sits under it
  (`InvoiceLine.parent`, migration `scholarship/0181`) showing its own hours and its number in ROUND brackets
  — `show year SPM was taken (REQ-12)`. ⚠ **A sub-item carries NO money** (`amount_myr` 0.00, no rate), so a
  reader adding the Amount column still reaches the subtotal; `build_lines` checks that invariant and refuses.
  The payload sends `is_sub_item` (a boolean, never the parent id) and the screen indents on it.
- **Bug work is charged at ZERO and shows on the paper.** A *"Bug reports, <month>"* line carries the hours at
  a rate of RM0.00 and is deliberately NOT itemised. ⚠ This is not a new rule — the owner's own note on the 15%
  development margin says *"The margin should help cover bug fixing which is not billed separately"*, so
  charging a bug as a feature collected for the same work twice. `platform_cost.billable_kind` decides per
  hours row and **ONLY `OrgRequest.triaged_kind` may move money** — never the submitter's `kind`, never
  Gemini's `ai_draft_kind`. An untagged hours row, an untriaged request and a dangling tag all read as
  FEATURE (billable): a human typing the row already made that call, and reading it as free would discard work
  nobody waived. `development_charge.subtotal_myr` still counts the free hours, because it is what answers
  "is the rate enough?".
- **A FEATURE CANNOT BE BILLED WITHOUT A QUOTE AND AN ACCEPTANCE** (owner, 2026-10-29: *"Make sure
  every feature has a quote and acceptance from BrightPath (including me signed in as BrightPath org
  admin)."*). `request_hours.consent_gaps` checks each billed feature in the month;
  `readiness` raises `feature_not_accepted` and it is **ABSOLUTE — the override does not work on
  it**, because the remedy is to quote it and have it accepted. ⚠ Two deliberate exemptions: a BUG
  (free, so nothing to consent to) and an hours row with NO `[REQ-n]` tag (a super typed it and
  meant it). An acceptance from the org's own org_admin counts.
- **AN ACCEPTANCE RECORDS WHO MADE IT** (TD-418, raised and closed 2026-10-29).
  `OrgRequest.approved_by` + `approved_by_role`, migration **`scholarship/0182`**; `approve()` stores
  both from the arguments it was already handed. The request page prints "Accepted on … · accepted
  by …", and `acceptedBySuper` reads differently when a super accepted on the organisation's behalf
  — the owner holds a BrightPath org_admin account as well as a super one, so the two are not the
  same fact. ⚠ **Rows accepted before 2026-10-29 are UNNAMED and must stay that way** — a guessed
  name on a consent record is worse than a blank. `consent_gaps` reads `approved_at`, NEVER the
  name, so no older month is gated on it. Request 38's acceptance is attributed to BrightPath by
  the owner, in TD-418's prose.
- ⚠ **THE REQUEST PILL SHOWS THE KIND THAT PRICES, NOT THE ONE THAT WAS FILED.** Both screens used
  to print `kind`, so request 5 read "Bug report" while being billed as a feature from
  `triaged_kind`, with nothing saying so. `requestStatus.effectiveKind` is now the single rule
  (`triaged_kind || kind`), `filedKindDiffers` drives an amber "filed as …" chip, and
  `halatuju-web/src/lib/__tests__/effective-kind-drift.test.ts` reads
  `org_requests._effective_kind` AND `request_hours.billable_kind` so the three cannot drift.
  Bite-checked from both sides.
- **The hourly rate is RM20 from 1 July 2026** (RM20 + 15% = **RM23.00** billed). Reduced from RM50 on the
  owner's instruction 2026-10-29, before any invoice had been issued, so nothing was re-priced. ⚠ The 1 August
  RM50 row was AMENDED rather than superseded, which the append-only doctrine on `BillingRate` otherwise
  forbids — safe only because `rate_in_force` takes the latest row on or before the month start, so a July row
  alone would have left RM50 winning for August onward, and because no document depended on RM50.
- **Who bills UPFRONT:** Anthropic (window 3rd→3rd) and Supabase (8th→7th); Workspace and Twilio bill the
  calendar month in arrears. An upfront bill is filed under the month its window STARTS, with a `period_note`
  saying so. Anthropic is excluded from a tenant's charge (a development cost recovered by the hourly rate),
  so a missing Anthropic bill barely moves an invoice; a missing Supabase bill moves it by ~RM117.
- ⚠ **OWNER ACTIONS before the first real issue:** add a `metered` `margin_pct` row effective **2026-07-01**
  (without it July prints one line, not two), import the September bills (and the October Anthropic +
  Supabase ones), and record August's 27.0 hours and September's 0.5.
- **The kind question is SETTLED (owner, 2026-10-29): the TRIAGE decision prices, not what was filed.** Of
  the seven requests filed as bugs, six were read as features by Gemini or by the engineer's own analysis
  and the owner accepted that reading — so they are priced, and that is not a defect. Only **request 14**
  disagreed with its own evidence (filed bug, engineer said bug, triaged feature) and it was re-ruled to a
  bug on 2026-10-29. Do NOT reopen the other six without the owner saying so.
- ⚠ **Known gap, pre-existing:** tax is pooled across all suppliers and apportioned pro-rata over
  platform / metered / development. Anthropic's SST therefore puts ~RM9 of tax on a tenant's infrastructure
  charge even though Anthropic's own cost is excluded. Owner decision pending; a fix would bucket each tax row
  against its own source.
- ⚠ **Bundle budget: 0.118 kB under the 180 kB median on MAIN** — measured on both main and this branch,
  identical. The deploy gate prints and passes at this margin, but main is one non-admin string from red.

**Earlier — Health light, TD-408 and TD-411 are LIVE (2026-10-28; TD-408 + TD-411 `cc47ef04` api-01168-5v7; health light +
TD-411 hotfix `305b0434` api-01169-s5k / web-01003-xsf; migration scholarship 0180 applied by hand; retro
`docs/retrospectives/retrospective-2026-10-28-health-td408-411.md`).** Super admins see a System health light in
the admin top bar (Gemini reads, Vision OCR, email sending, scheduled jobs, AI credit; `cron_health.EXPECTED_CADENCE`
must change with any Cloud Scheduler change). A reversed patronymic (father/son) no longer matches; bare
ANAK/AK/BT/BTE give a father name, which can only turn 'unknown' into 'match'. A PDF text layer that is only a
scanner stamp is no layer (`pdf_pages.usable_text_layer`); the KWSP app screen reads suspect `epf_app`.
Genuineness `MODEL_VERSION` 1.17.1; `VERDICT_ENGINE_VERSION` 2026-10-28.2 (the other session's C4 takes .3).
- **TD-399 PARKED** (owner, 2026-10-28: "No, not now" — no second company reads student documents). Next: pick from the Open Items Index (Now tier first).
- A rule that turns away text or documents is dry-run on the LIVE stored data before deploy, not only on the
  eval corpus (lesson 2026-10-28: the corpus missed a Canva-style statement the live run caught).
- ⚠ Bundle budget: median 179.49 kB of 180 — about 0.5 kB headroom.

**Earlier — Income declarations (#374) are LIVE with the hotfix (2026-10-28; `afaf23cd` … `8a11d41e`, hotfix `c58b7237` +
`00f1f7eb`, api-01164-sfb; follow-ups in the close commit; retro
`docs/retrospectives/retrospective-2026-10-28-income-declarations.md`).** Every informal income document (support
letter, informal payslip, declaration form) counts only when approved — a stamp with a named / titled approver,
a header with a signed named approver, or a header with a stamp — read off the IMAGE in one extra Gemini call;
bank statements naming a known bank and government payslips / pension statements are exempt; a declared
amount is never Certain. Genuineness `MODEL_VERSION` 1.16.0; `VERDICT_ENGINE_VERSION` 2026-10-27.8.
- **Next: the health status light** (owner chose option A: an admin-console status light) — **Stitch first**.
- **Then TD-408** (word order: order-aware patronymics; the father-name splitter learns ANAK).
- **Then TD-411** (EPF `not_epf` p=0.00 on recognised statements). ⚠ The other session's finding: production
  reads PDF text layers with **pypdf 5.9** while local checkouts had **6.19** (cached) — the two lay text out
  differently, so any local probe of the EPF text layer must pin pypdf 5.9 (`capture_ocr` now warns on drift).
- **Then TD-399** (OpenAI fallback for document reads, after the owner's privacy ruling).
- A new document rule that can refuse a document is dry-run on real approved documents' stored fields before
  it ships (lesson, 2026-10-28).

**Earlier — TD-409 is pushed (2026-10-27; `ddd46dda` + `ddb26b60`; retro `docs/retrospectives/retrospective-2026-10-27-td409.md`).**
An STR no household card matched never closes an STR request (owner ruling A): `doc_match_verdict` gives it
`pending` (red only for a proven stranger's); an upload holds the STR requests it answers for the officer, both
syncs hold rather than close them (unless a member's income is shown on its own), a re-opened Check-2 request
drops the hold, and an unmatched STR never displaces a matched one that still counts. Check 2 asks for a
near-miss STR's IC-number page (`str_needs_recipient_ic`). No band moves. Register: **134 open** (TD-410 raised).
- **Next: the health status light** (owner chose option A: an admin-console status light) — **Stitch first**.
- **Then TD-408** (word order: order-aware patronymics; the father-name splitter learns ANAK) and **TD-399**
  (OpenAI fallback for document reads, after the owner's privacy ruling).
- ⚠ **Bundle budget:** the median first-load JS has only **0.4 kB** headroom under 180 kB — the next web change
  that adds to a shared chunk will FAIL it; budget for a trim.
- TD-410 (Next tier): does a suspect payslip show income? An owner question before any tightening.
- Proposed: a code-health split of the genuineness wiring out of `vision.py` (at its allowance twice running).

**Earlier — TD-407 and TD-404 are LIVE (2026-10-27; TD-407 `9bdb163f` + `e65a9cd3`, api-01151-gmw; TD-404 `b1fe889c` +
`71e38f89` + `0e03a678`; retro `docs/retrospectives/retrospective-2026-10-27-td407-td404.md`).** A re-read never
replaces a stored genuineness score with nothing (`genuineness.bands.keep_stored_authenticity`); the hand-run
re-read commands refuse without the flag, the hourly self-heal warns. Every name match treats ANAK/AK and
BT/BTE as connectors; a household STR one romanised syllable from a card is "cannot judge" and, with no IC
number on it, asks for the IC-number page (`str_needs_recipient_ic`). `VERDICT_ENGINE_VERSION` 2026-10-27.3.
Register: **134 open**.

**Earlier — the corpus-gaps arc is DONE (2026-10-26): C3 + C4 LIVE (C3 `0ae5f431`, api-01147-9gw; C4 the lead's live
re-run of 43 documents; retro `docs/retrospectives/retrospective-2026-10-26-corpus-c3-c4.md`).** STPM results
are scored as STPM (`genuineness/stpm_doc.py`, MODEL_VERSION 1.9.0) in the results and semester-result
slots; the online checker page is not a result document (ruling 1A), a certified copy is (2A). C4: 11 UiTM
offers → genuine, 17 STPM documents → genuine, IKBN d3465 → not checked. ⚠ A re-read through a Cloud Run
JOB must carry the service flags — without `DOC_GENUINENESS_CHECK_ENABLED` it wipes stored scores
("How a change reaches production" item 11; TD-407, Now tier). Only the data-gated TVET families remain.
Register: **134 open** (TD-407 raised).

**Earlier — corpus gaps C1 + C2 are LIVE (2026-10-26; C1 `1a2b4962` + `95131a65`, api-01144-sfg / web-00988-nhg;
C2 `1accaab9` + `a781b49a`; retro `docs/retrospectives/retrospective-2026-10-26-corpus-c1-c2.md`).** C1: a
suspect-band offer with offer wording from a known public TVET issuer named on its letterhead is stored
`unchecked` (`genuineness/offer_issuers.py`) and read as no signal everywhere (no block, no official-offer
request, Probable; the officer is told "not checked"); KPTM / UniKL stay private (owner rulings A, B, C,
`decisions.md` 2026-10-26). C2: UiTM scores as a public university, photo OCR and PDF text layer alike; an
officer's own offer request is held for the officer, never closed by a "not checked" upload.
MODEL_VERSION 1.8.2, VERDICT_ENGINE_VERSION 2026-10-26.1. Register: **134 open** (TD-406 raised).
- **TD-403 is LIVE (2026-10-26; `32a847f1`, `cafcfc43`, `85921925`, `b67dd4f5` + `ed342354`; retro
  `docs/retrospectives/retrospective-2026-10-26-td403-str-this-year.md`).** An STR counts as income proof
  only if it is from THIS year — `str_route.str_this_year(application)`, the one seam: today in Malaysia
  before submission, the year of `profile_completed_at` once submitted (strict, no Jan–Mar grace). An
  earlier year = `stale` (`str_stale:<year>`), a later one = neutral `future` (`str_not_this_year`).
  `VERDICT_ENGINE_VERSION` 2026-10-26.2. **TD-404 soon** (Sabah/Sarawak `AK`/`ANAK` names — every name match, adversarial review).

**Earlier — TD-401 + TD-402 and the owner's STR ruling are LIVE (2026-10-25, `014cae5b`, `4f582222`, `76a07ee7`;
retro `docs/retrospectives/retrospective-2026-10-25-td401-td402-str-ruling.md`).** Identity rests on the
card's NRIC (a student IC with a name but no NRIC is `ic_unreadable`). An STR is income proof at the
submission gate only when a card MATCHED its recipient, on BOTH routes (`decisions.md` 2026-10-24 item 3c,
superseding F1 for the gate; the verdict keeps F1's lenient reading): unmatched, the gate asks for the IC of
the roster member who could settle it (`services.blockers._unmatched_str_asks` — the card TD-309 already
offers), else `str_not_household`, a clearer document, or "try later" when the read is ours.
`VERDICT_ENGINE_VERSION` 2026-10-25.2. Fixtures needing a household's own STR use
`factories.matched_str_pair`. Register: **133 open**.
- **Still queued: the health status light** (owner chose option A: an admin-console status light) — **Stitch first**.
- **Then TD-403** — LIVE 2026-10-26 (see above), and
  **TD-399** (OpenAI fallback for document reads, gated on the owner's privacy ruling + an eval run).

**Earlier — TD-390 is LIVE (2026-10-25, `46b1c0bd`; retro
`docs/retrospectives/retrospective-2026-10-25-td390-ic-second-opinion.md`).** A MyKad read that NEEDED the
Gemini second opinion, skipped by our outage, is marked on the row (`read_errors.IC_SECOND_OPINION_ERROR`,
72-hour window, renewed by a new outage): the gate answers `ic_service_down` (still blocks; a half read
passes only on a verified NRIC), every reader scoped to THAT card says pending, the sweep re-runs it, the
alert counts it, and past the window the old read applies in full. Owner ruling (scenario B): an STR we
cannot judge only because the earner's own card is half-read blocks as "try later". `VERDICT_ENGINE_VERSION`
2026-10-25.1.

**Earlier — the AI-outage sprint is LIVE (2026-10-25, `9d3ff53a`, api-01135-djr; retro
`docs/retrospectives/retrospective-2026-10-24-ai-outage.md`).** OUR read failing (Gemini or Vision down,
unconfigured, throttled, a revoked key) is stored `review_manually` + `service_error`, never the student's
`unreadable` — one classifier, `apps/scholarship/read_errors.py`; a document is blamed only when every model
refused its CONTENT or none parsed an answer. Deferred reads raise no student request, no consent blocker,
no attempt, and hold Check-2 requests (`check2_deferred.py`); the hourly sweep re-reads them
(`services/read_retry.py`); the outage alert covers Gemini and supporting-document OCR.
- ⚠ A Check-2 request held for a deferred read stays frozen if the sweep's 72 h pass (TD-397); TD-394
  (a deferred EPF/letter holds the income gate) is KEPT by owner ruling.

**Earlier (still current):** per-gift referral sources (Sprints 1 + 2) are LIVE (2026-10-09, `ffa0983a`,
api-01117-4m6 / web-00968-28w; retro `docs/retrospectives/retrospective-2026-10-09-per-gift-sources.md`). Each gift
chooses its referral sources on Programme → Configuration ("Who referred you?" toggles; table
`programme_referral_sources`, rules in `apps/scholarship/gift_sources.py`); the public intake serves that
gift's `{code, name}` list; the apply form adds Halatuju.xyz / Facebook-WhatsApp / Other (since request
#44 a gift may switch off the first two — `Programme.offers_halatuju` / `offers_social`, served as
`fixed_sources`, one rule `gift_sources.offered_fixed_codes`; Other is never switchable); the
submit refuses any other code (400 `referral_source_not_offered`). Org-timing Sprint 1 (2026-10-07) and
request #31 + TD-371..377 (2026-10-08) are live too. Ledgers (applied migrate-first, contiguous):
scholarship ends at 0174, courses at 0083 on main; **#39 S4 (`perm-s4`) adds scholarship 0175_staff_permission_changes, applied by hand BEFORE its deploy** — and request #42 added scholarship 0176 (the AI-outage sprint added none) — request #44 adds scholarship 0177_programme_fixed_source_switches (plain ADD COLUMN, migrate-first) — third route S3a added 0178_higher_results and D16 adds 0179_programme_asks_higher_results (`Programme.asks_higher_results`, plain ADD COLUMN + the flagship set false, migrate-first; since D16c the column is UNREAD — `results_route.gift_asks_higher` follows the intake's `min_stpm_pngk` — and a later migration drops it) — **next free: scholarship 0180 / courses 0084.**
- **Org-timing Sprint 2 is next (≈2026-10-14 — one week live with no timing incident):** drop the UNREAD
  intake-round columns `success_delay_hours`, `decline_delay_hours`, `query_response_sla_days` and the dead
  `fail_email_delay_days` (roadmap `docs/plans/2026-10-07-org-timing-settings-roadmap.md`). Timings live in
  `org_config` only (registry `apps/courses/org_config_registry.py`, rules `org_config_rules.RULES`, read
  seam `org_config.value(org, key)`), checked on the MERGED settings; a guard test holds every default in
  range and passing every rule. Reminder days, the answer time and the award-email delay are re-read on
  every sweep (a change reaches students already waiting); the auto-close never comes sooner than reminder
  4 PROMISED (`reminders.promised_close_days`).
- **Sources — what must not break:** a source switched on in Sources joins NO gift, and a new gift starts
  with none (someone switches it on per gift). The fixed three are held on both sides
  (`gift_sources.FIXED_CODES` / web `FIXED_REFERRAL_CODES`, drift-tested); they and the house
  organisation's code are reserved (Sources POST 400 `code_reserved`). `PartnerOrganisation.programme`
  left the model in sources Sprint B; **TD-379's drop is `courses/0080`, IMAGE-FIRST** (after that image
  serves). TD-380's witness half and TD-381's part (4) wait for Sprint C
  (`docs/plans/2026-10-09-sources-and-referrals-roadmap.md`).
- **Referral columns (Sprint A LIVE 2026-10-18; Sprint D BUILT 2026-10-19):** the bursary submit writes
  NOTHING on the profile (its answer is the application's); `referred_by_org` and the chip
  `referral_source` are written ONLY by a `?ref=` link, first touch — `referred_by_org` only to an
  `is_referral_partner` row (`apps/courses/referral_links.py`). Never let a bursary answer reach the
  `partner` logins' list or its Source column. A super marks / unmarks a referral partner through
  `PATCH /api/v1/admin/referral-partners/<id>/` (no screen yet, TD-387).
- **Sources become their own table (Sprint B, BUILT, NOT LIVE):** `scholarship.ReferralSource`
  (`referral_sources`), OWNED by an organisation, same ids as the `partner_organisations` rows it was
  copied from; every source surface is fenced to the owning organisation; referral partners stay on
  `partner_organisations`. ⚠ **`scholarship/0173` + `courses/0079` are MIGRATE-FIRST and pending, and
  `courses/0080` (TD-379, the column drop) is IMAGE-FIRST — only after the new revision serves**:
  `docs/scholarship/sources-b-cutover-sql.md` (freeze Sources and gift Configuration between the
  cutover and the deploy). Next free after it: scholarship 0174 / courses 0081.
- **Sources Sprint D — the arc's clean-up (BUILT 2026-10-19, NOT LIVE):** ⚠ `courses/0082` is
  MIGRATE-FIRST (gives `partner_organisations.show_in_apply` `DEFAULT false`; switches the sources' old
  rows off) and `courses/0083` is IMAGE-FIRST and OWNER-RUN in the SQL Editor (drops
  `api_student_profiles.source_id` and `partner_organisations.show_in_apply`, after backups) —
  `docs/scholarship/sources-d-cutover-sql.md`. The cockpit's `referred_by_org` key is gone (web and api
  in either order). Next free after it: scholarship 0175 / courses 0084 (request #39 S1 holds courses 0081).
- **Each application keeps its own "Who referred you?" (sources Sprint C, LIVE 2026-10-19):**
  `ScholarshipApplication.referral_code` + `.source` (written once at submit from the snapshot,
  resolved inside the application's own organisation) feed partner emails, Sources counts, the
  Applications filter and the witness; the witness is never the referral partner and only a super
  records it; `?ref=` never pre-fills the bursary form. (`scholarship/0174` applied 2026-10-19.)
- **TD-347 when the owner says go** (ruled B: when the parent call is recorded, re-arm a FRESH full
  accept window; the email names the new deadline). ⛔ It must ship before anyone sets
  `BURSARY_AGREEMENT_ENABLED`; before that flip, prompt every awarded student to check the parent phone on
  /profile. **On hold by owner ruling:** TD-366 (releasing an awarded student who stops answering — until
  signing is finalised), TD-353 (two organisations at once). **Now tier:** TD-367 (a payment run can pay a
  CLOSED student), TD-356, TD-348, TD-252.
- **Bundle room (TD-360 Sprint 1, 2026-10-21):** median 178.829/180, `/scholarship/apply` 191.962/193,
  `/scholarship/application` 221.861/223, `/profile` 218.548/220 — 1.04 to 1.45 kB each. `admin.*` strings
  no longer move these; a non-admin string still does. Run `npm run bundle-budget` before any push that adds one.
  Malay/Tamil first drafts go to Sol (tagged there), never to the owner as a reminder.
- **Owner actions open:** record parent calls for #116, #62, #125, #25 (not #20); the 24 Owner-decision
  questions in the register.
## Known Issues & Future Work

The open debt register is `docs/technical-debt.md` (Open Items Index, in working order); the release
notes list it by importance and size (`docs/releases/release-notes-v3.0.0.md`, Known Issues). Plans:
`docs/roadmap.md` and `docs/plans/`. General rules (testing, deployment discipline, git, cleanup,
British English) are in the workspace-level `CLAUDE.md`.
