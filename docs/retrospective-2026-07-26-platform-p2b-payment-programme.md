# Retrospective — Platform P2b: a payment run pays ONE gift

**Date:** 2026-07-26
**Sprint:** P2b of `docs/plans/2026-07-26-programme-layer-roadmap.md`
**Branch:** `feat/p2b-payment-programme` (worktree — the repo is shared with another agent)
**Result:** 4696 pytest passed, 0 failed (baseline 4678). Migrations `0126`+`0127` migrate-first.

## What was built

`PaymentRun.programme`, a backfill that derives it from each run's own students, and the narrowing
that makes it mean something: `create_run` requires a programme, `eligible_rows` filters by it, and
the run detail's skipped-list narrows with it. Plus a programme column on the funding summary.

## What went well

- **Sprint-start paid for itself before any code.** Four questions were carried into it; two
  dissolved on investigation — run references **already** disambiguate (`_next_reference` appends
  `-02`), and per-programme payment rates are **already** expressible via the contract template's
  `monthly_amount`. Both would have been invented work. The remaining two were genuine owner
  decisions and took one exchange.
- **The required parameter did its job as a worklist, not as a trap.** Making `programme`
  positional-and-required turned 17 call sites into a mechanical list of `TypeError`s rather than
  17 chances to silently pay across gifts. Fixed at the shared fixture (one `_make_cohort` change +
  one `_run` helper), per the standing lesson, not test-by-test.
- **The allowlist snapshot failed exactly as designed.** Adding `programme` to the funding summary
  broke `test_allowlist_key_set_is_exact` — which is how that addition got reviewed instead of
  slipped in. The updated snapshot carries a comment saying who decided it and why.
- **Enumerating channels caught the real gap.** The plan said "narrow `eligible_rows`". That would
  have left the run-detail's *skipped this run* list computing over the whole organisation, so a
  student of another gift — never a candidate — would have read as skipped. Found by listing what
  reads the choke-point, not by a failing test.

## What went wrong

- **The sprint brief under-scoped the change to one function, and I nearly built exactly that.**
  *Symptom:* the roadmap's scope line named `eligible_rows` and the funding summary; the skipped
  list and the two run payloads went unmentioned. *Root cause:* the brief was written from the
  model outward ("add a column, filter the query") rather than from the surfaces inward ("what
  displays a run?"). *Fix:* the channel sweep is now the habit that catches this — it has now
  found something in three consecutive sprints (P3 emails, P4b sponsor statement, P2b skipped
  list), which says the failure is not sprint-specific but structural: **a brief written from the
  data model will systematically miss the read paths.** Generalised into `docs/lessons.md`.
- **I planned this as "reporting hygiene" and it is not.** The roadmap called P2b lower-priority
  than the wallet work because nothing visible changes today. That is true and irrelevant: the
  reason nothing changes today is that only one programme exists, which is exactly the condition
  that ends when Sabah or Inspire arrives. The cost of the bug is not "a wrong report" — it is one
  benefactor's money paying another's students, on the live payout path. Sequencing it last was
  right for risk; describing it as hygiene was wrong.

## Design decisions

Recorded in `docs/decisions.md` (2026-07-26): the operator states the gift rather than the system
deriving it; the funding summary gains a column, not a grouping; the programme column stays
permanently nullable with the requirement living in `create_run`; and the reference scheme is left
alone.

## Numbers

4696 pytest (from 4678: +18 in the new `test_payment_programme.py`). Two migrations, one additive
and one data. No frontend files changed.

## Follow-ups

- **Apply `0126`+`0127` migrate-first, then deploy.** Post-check: every run with items has a
  programme; no run disagrees with its own students; `PR-2026-08-01` still holds 30 items.
- **The FE create-run screen needs a programme picker** before a second programme goes live. The
  API preselects when an org runs one, so today's UI keeps working untouched — this is owed at the
  same moment Sabah opens, not now.
- Routing PF-1 (date-parked ~May/June 2027), reviewer programme scoping, P4b-ii, Phase 2 S7–S9,
  Sprint E.
