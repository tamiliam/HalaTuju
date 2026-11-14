# HalaTuju API — Architecture & Operations

> **DEPLOY RULE (owner, 14 Nov 2026).** Pushing to `main` only SAVES; it never deploys.
> To publish: `git push origin <tested-main-sha>:live` (fast-forward only, never force). The triggers fire on `live`.
> Each publish needs the owner's yes. Details: `docs/deployment.md`.
> Publishes happen only at 11:00, 16:00 and 21:00 Malaysia time (max 3 a day), one batch, run by one release lead; a hotfix may go any time with the owner's yes. Workflow: `Settings/_workflows/release-train.md`.
> End your final commit with trailers: `Phone-check: <plain line>`, `Migration: <name> (additive|non-additive)`, `Services: api|web|both`. Take a TD number only when pushing to `main`: `python Settings/_tools/release_queue.py next-td --project <this repo>`.

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

HalaTuju (halatuju.xyz, **v3.1.0**, 2026-11-05) is two products in one codebase. The **course guide**
tells a Malaysian SPM or STPM leaver which courses they qualify for, ranks them and writes a report
(golden masters: SPM 5,319, STPM 2,025). The **scholarship platform** runs a funder's bursary end to end:
apply, results and documents read by OCR and AI, a deterministic verdict, interview, QC, award,
sponsors, payments through Vircle, and an organisation's own console (tenancy: organisation → gift →
intake year). Django REST API `halatuju_api/` + Next.js 15 `halatuju-web/`, both on Cloud Run
(asia-southeast1), Supabase PostgreSQL + Storage + Auth (Singapore).

## Build-for-Tenancy Conventions (MANDATORY for all new work)

HalaTuju is becoming a multi-tenant platform (course selector = shared base; scholarship programmes = org-owned tenants; plan of record in `docs/plans/archive/2026-07-14-platform-roadmap-draft.md` at the repo root). Until that lands, **every sprint must follow `docs/build-for-tenancy-conventions.md` (repo root)** so ongoing BrightPath work stops deepening the coupling: new tunables on `ScholarshipCohort` (not module constants), no new "BrightPath"/persona/URL literals, new admin endpoints through the `_AdminBase` gates, referral fields (`PartnerAdmin.org`, `referred_by_org`) NEVER used for access control, billable calls only through the existing seams. The full rules + review checklist are in that doc.

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

- **A push to `main` only SAVES (since 2026-11-14). Publishing = moving `live`, and needs the owner's yes.** Fast-forward `live` to a tested `main` commit: `git push origin <sha>:live` (never force). Path filters still apply: root `docs/**` and `CHANGELOG.md` deploy nothing; a file under `halatuju_api/` or `halatuju-web/` does.
- **The tests are the gate** (api: `manage.py check`, `makemigrations --check`, `pytest -n auto`; web: `npm run gates` then `npm run bundle-budget -- --gate`). Run the gate's OWN command lines locally first. Never deploy more than twice per feature.
- **MIGRATE-FIRST, by hand.** Triggers never run `migrate`: apply to production BEFORE the push (postgresql DDL, plus the `django_migrations` ledger row in the SAME transaction). Old image must stay safe: additive and nullable first. Catalogue rows a new gate hides go in AFTER the deploy.
- ⚠ After an `UPDATE` touching a `DEFERRABLE INITIALLY DEFERRED` FK, run `SET CONSTRAINTS ALL IMMEDIATE;` before `CREATE INDEX` in the same transaction.
- ⚠ Adding, pausing or re-timing a Scheduler job means editing `cron_health.EXPECTED_CADENCE` in the same change.
- ⚠ A `node_modules` JUNCTION in a worktree is removed with `[IO.Directory]::Delete('<path>')` BEFORE `git worktree remove`.
- **Commit type is honest.** `fix:` only for a real defect that was live or would have been; a rename, a label, a review-round tweak or a follow-up to your own sprint is `refactor:`, `test:`, `chore:` or `docs:`. `fix:` counts feed `fix%` (TD-385) and the Consolidation Review reads them as failures. A sprint step carries the word "sprint" in its subject.
- With more than one agent in the checkout: declare files in `AGENT-TERRITORY.log`, stage explicit paths (never `git add -A`), build in a worktree, push with `git push origin HEAD:main`.
- A live re-read through a Cloud Run JOB must carry the service's read flags (`DOC_GENUINENESS_CHECK_ENABLED=1`, `BILLING_USAGE_ENABLED=true`); ⚠ the genuineness flag is on only for the exact value `1`.
- A one-off team command runs through the `release-decisions` job with an args override (recipe in the doc).
- Env vars: ⚠ the Gemini key must belong to the HalaTuju GCP project (prepaid; credit out = outage); ⚠ rotating the Brevo key also means Supabase Auth's SMTP setting; `SPONSOR_MOCK_DONATIONS_ENABLED` is **NEVER in production**; ⛔ `BURSARY_AGREEMENT_ENABLED` needs TD-347 fixed first; `UPDATE_EMAIL_GOLDEN` is local-only and ⛔ never set.
- **Which flags are ON in production:** the table in `docs/deployment.md` ("Live flag values"), read off the running service. Never read a flag from a settings default.
- The api image installs `requirements.lock` (refresh it deliberately); `.dockerignore` is the file that counts for the image.
- New documents go where the doc says: retrospectives `docs/retrospectives/`, release notes `docs/releases/`, history `docs/sprint-history.md`, domain rules `docs/domain-rules.md`.

## Security and access (full review: `docs/security-posture.md`)

- **Roles** (`PartnerAdmin.role`): `super` (platform, cross-org), `org_admin`, `admin` (view-only),
  `reviewer` (assigned applicants only), `qc`, `finance` (payment-run checker, no B40 data), `partner`
  (referral org's own students). `role` is the only super marker; the old `is_super_admin` column is retired from the model (TD-064, migration 0093; column dropped by hand, then migration 0094). Sponsors are a
  separate `Sponsor` identity. The role matrix is `docs/scholarship/role-matrix.md`.
- **The organisation fence** is `_AdminBase` (`_org_scoped` / `_org_allows`); every new admin endpoint
  goes through it, and the H3 guard fails a wired route no test drives or that skips the fence.
  Referral fields (`PartnerAdmin.org`, `referred_by_org`) are NEVER access control.
- **The gift gate:** `?programme=<code>` NARROWS inside the fence and never widens it; unknown or
  cross-tenant → 404, never "show everything". An **organisation-less super must name a gift** on
  money surfaces (`400 programme_required`, TD-334; the Overview still pools — TD-336).
- **RLS:** every `public` table has RLS on (event trigger `rls_auto_enable`; it adds no policy: add the `service_role` policy yourself). Run the Supabase Security Advisor after any migration; 0 errors before deploy. The student write-policy history, new-table templates, the keyless Google Workspace recovery (alert policy, IAM grant), `AUDIT` log-line rules and the three-client session rules: `docs/security-posture.md`, section "Moved from halatuju_api/CLAUDE.md, 2026-11-05".

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

Full suites run ONCE locally, right before the push. Run the API gate with `-n auto`. All four frontend gates before any web deploy; any UI change runs `npm run mobile-check`. Golden masters SPM 5,319 / STPM 2,025: if either moves you broke eligibility. Never run `cleanup_orphan_blobs --apply` from a checkout older than S2 (it deletes staff photos). Never re-run extraction locally. The rest of the rules (pre-deploy checklist, the two roads to QC, rendered tests): `docs/testing.md`, section "Moved from halatuju_api/CLAUDE.md, 2026-11-05".

## Code standards (full text: `docs/code-standards.md`)

Enforced by tests inside the deploy gate: no file over 600 lines (ledgered ones may not grow), no function of 150+ lines, one rule one home, no skipped tests, no new `# noqa` / `@ts-ignore` / `any`, every `eslint-disable` carries a reason, no unguarded mirror, no unused dependency, the `courses -> scholarship` import ceiling, new tests use the factory, a route may not get heavier (250 kB, median ratchet), applicant-detail GET pinned at 38 queries, the Mobile Standard. The two budget files are `halatuju_api/code-standards.json` and `halatuju-web/code-standards.json` (frozen `baseline` + live `budget` that only tightens). The one-liners that cause damage if missed:

- **NEVER raise a budget, a floor or a ledger**; split the file first, in its own commit, moves only. No value import from `@supabase/supabase-js` in `src/` (auth clients only in `supabaseAuthClient.ts`). The remaining guard rules (bundle, query budgets, moved ledger files, tree-walking guards, the nine harvested groups): `docs/code-standards.md`, section "Moved from halatuju_api/CLAUDE.md, 2026-11-05".
- **Dates (owner, TD-424, 2026-11-12):** a date box shows and takes **DD-MM-YYYY** (the Malaysian format) and sends **ISO** to the API (`isoFromDayFirst`, `lib/invoices.ts`). Nothing stored changes. ISO is only for file names and sorting.

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
- More live rules (re-export patching and the `constants.py` leaf, i18n delivery, serve-never-derive in the browser, status derived / never re-run `build_verdict` / version bumps, the money rules for Vircle wallets and spending names, the padlock and Overview layout): `docs/domain-rules.md`, section "Moved from halatuju_api/CLAUDE.md, 2026-11-05".
- A Django `AlterField` that only changes a default does not rewrite existing rows. Node 24 is named in four places (change all four). A STPM `ua_offer` + `suspect` is often CORRECT.
- The debt register: close a TD only with evidence, marker on the defining line, never write inside the Open Items Index.
- **Never conclude an absence from a grep**: authored content lives in the database.

## Next Sprint

Older state blocks and the Mobile-native arc's milestone-by-milestone rules: `docs/sprint-history.md` ("Moved from halatuju_api/CLAUDE.md Next Sprint, 2026-11-03").

### STATE AT 2026-11-05 — T5c P5b + P5c LIVE (main 3c39489b, api-01255-zsm, web-01084-l6b; no migration)

- One "Overview" row and page: per-person pending cards (`GET admin/scholarship/my-pending/`, `apps/scholarship/my_pending.py`) above the programme cards. Unassigned means ready to assign (`queries_sla.ready_to_assign`); cards open the filtered applications list (`?ready=1`, `?band=`, `?status`, `?assigned=me`) or `?tab=action`. Owner phone check OK 2026-11-05. Open lows: TD-502 to TD-505.
- **NEXT, in order:** (1) push v3.1.0 (`Settings/_workflows/release.md`; notes `docs/releases/release-notes-v3.1.0.md`; the local tag sits on the security-patch commit; push needs the owner's yes); (2) the Next 15 upgrade as audit fix sprint 1 (TD-506; a security fix, so the freeze allows it); (3) TD-501 (reviewer invite must choose one gift or every gift; staff invites take no gift otherwise; Opus build, adversarial review, owner phone check); (4) the full project audit (`Settings/_workflows/project-audit.md`) on the new tag, after TD-501. **FREEZE in force: no T5d, no offer S7** until the audit's fix sprints are done.

### Older state blocks and the other streams (full text in `docs/sprint-history.md`, section "Moved from halatuju_api/CLAUDE.md, 2026-11-05")

- Team tables T5a, T5b and T5c P1 (the `staff_tables.opens` door gate, `qc` implies `see_all`, `qc_separation.refusal`, the v2 permission catalogue), Requests list R1 (`org_requests_queue.needs_action_q` is the ONE Needs-action rule) and T5c Part 5 (Programmes landing; open TD-500, TD-501): rules and gotchas are in that section. A new page is gated the old way AND gets a v2 key, except the merged Overview.
- **Offer letters read exactly:** S1-S6 live. **NEXT = S7 (paid; owner yes)**, then S8. Roadmap `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md`. New evasions go to TD for S7 unless they block a real public letter.
- **Mobile-native arc:** COMPLETE (M0-M8). Rules `docs/mobile-standard.md`, ledger `docs/mobile-ledger.md`; every UI change runs `npm run mobile-check`.
- **FREEZE:** no T5d, no offer S7 until the audit fix sprints are done (roadmap `docs/plans/2026-11-05-audit-fix-roadmap.md`).

## Known Issues & Future Work

The open debt register is `docs/technical-debt.md` (Open Items Index, in working order); the release
notes list it by importance and size (`docs/releases/release-notes-v3.0.0.md`, Known Issues). Plans:
`docs/roadmap.md` and `docs/plans/`. General rules (testing, deployment discipline, git, cleanup,
British English) are in the workspace-level `CLAUDE.md`.
