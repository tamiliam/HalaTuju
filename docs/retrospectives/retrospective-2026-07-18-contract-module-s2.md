# Retrospective — Contract Module Sprint 2 (engine cutover)

**Date:** 2026-07-18
**Plan:** `docs/plans/2026-07-18-contract-module-plan.md`
**Branch:** `feat/contract-module` (renamed from `feat/contract-module-s1`); NOT
pushed — the feature's single deploy is Sprint 5.
**Scope:** Backend only. `bursary.py`/`payments.py` read the versioned template;
the hard-coded constants STAY (removal is Sprint 5). Still behind
`BURSARY_AGREEMENT_ENABLED` (OFF). NO deploy.

## What Was Built

- **`bursary.py` cutover** — `particulars_for(app, template, locale)` (schedule
  text + progress standard + counterparty from the template, constants fallback);
  `render_agreement_html(..., template)` (title/preamble/clauses from the template,
  a Schedule 1 payment table with gap months, `parent_role` co-signer wording,
  English-authoritative notice, vetting footer, no DRAFT banner);
  `sign_agreement` with the `no_active_template` + `comprehension_stale` guards,
  storing `template` + version; `_regenerate_artefact` passing the pinned template;
  `foundation_notify_emails(application)` preferring the template's notify list.
- **`contracts.py`** — `schedule_calendar(row, cohort_year)` reader for Schedule 1.
- **Quiz API-served** — `StudentComprehensionQuizView` GET; the pass POST pins
  `comprehension_template` and 409s a stale `template_version`.
- **`payments.py` integration** — `_schedule_row` seam; `default_amount` /
  `_pathway_payment_start` from the row (legacy fallback byte-identical); `gap_month`
  / `schedule_complete` greyed reasons.
- **`bursary_e2e`** seeds + deploys a template and pins comprehension before the walk.
- **Tests** — `test_contract_cutover.py` (+14) + `test_bursary_agreement.py` updated.

## What Went Well

- **The parity guard is a real test, not a claim.** `TestPaymentRunParity` builds
  the eligible-app→amount map with NO template (legacy) and again after deploying
  the seeded template, and asserts they're equal for Jul–Nov — the concrete guard
  for the 30 live students. It also asserts every amount is exactly RM200 so an
  empty match can't pass silently.
- **The cutover guards are ordered so failures are cheap.** `no_active_template`
  and `comprehension_stale` raise BEFORE any render/PDF/storage, so those tests
  need no mocking — they exercise the real `sign_agreement` up to the guard.
- **The e2e is now a CI test**, not just a manual driver — a future cutover
  regression breaks the suite, not just a command someone forgot to run.

## What Went Wrong

1. **The working tree was on `main` (not my branch) at the start of the sprint, and
   `main` had advanced two commits since Sprint 1.** Symptom: `contracts.py` "did
   not exist" and my Sprint 1 commit wasn't in `git log`. Root cause: this is a
   shared repo — another agent pushed to `main` between sprints, and something left
   the checkout on `main`; my unpushed `feat/contract-module-s1` branch still held
   the work. Fix: `git checkout feat/contract-module-s1` then `git rebase main`
   (clean — the two new commits touched none of my files). **System change:** the
   pre-flight for a continuation sprint on a shared repo must start with `git branch
   --show-current` + `git log --oneline -3` to confirm I'm on my branch and rebase
   onto the latest `main` before editing — don't assume the tree is where the last
   sprint left it. (Added to lessons.md.)
2. **17 pre-cutover `test_bursary_agreement.py` tests broke** the moment
   `sign_agreement` required a template with the flag on (`no_active_template`).
   Root cause: those tests predate the cutover and signed against the constants.
   Two of them asserted `'Suresh'` in the rendered HTML. Fix: a shared
   `_ensure_active_template` helper that points the cohort at BrightPath and deploys
   a template whose counterparty is **'Suresh'** (matching the legacy
   `FOUNDATION_SIGNATORY_NAME`), wired into the one app factory `_fundable_app`
   (which now also pins `comprehension_template`) — so the fix was one helper, not
   17 edits, and the render assertions stayed valid. **Lesson:** when a signing path
   gains a hard prerequisite, fix it at the single shared test factory, and choose
   the new fixture's values to keep existing content assertions true.

## Design Decisions

- **`is_paid_month` distinction lives in payments, not contracts.** `contracts.is_paid_month`
  returns False for both a gap and a past-schedule month; payments needs to tell
  them apart (`gap_month` vs `schedule_complete`), so a small `_schedule_status`
  helper in `payments.py` computes the offset and classifies. Kept the money-facing
  branch logic next to the run builder rather than overloading the contracts reader.
- **`_credit_applied` threads the row rate too** (not just `default_amount`, which
  the plan named): a future non-RM200 template would otherwise offset credit against
  the wrong rate. Byte-identical for the seeded RM200 rows; correct for later ones.
- **Counterparty 'Suresh' in the bursary test template** — deliberately matches the
  legacy settings default so the existing render/anonymity assertions hold without
  edits; the real BrightPath fixture leaves it blank (owner fills it in the UI).

## Numbers

- +14 cutover tests; 17 pre-cutover tests updated. **4074 pytest** (2820
  scholarship + 1254 courses/reports) green; 0 migration drift (code-only sprint);
  `bursary_e2e` green both paths (manual + CI). 8 files changed.
