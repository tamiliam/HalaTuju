# Retrospective — Platform P2a: the sponsor wallet is per-programme

**Date:** 2026-07-26
**Sprint:** P2a of `docs/plans/2026-07-26-programme-layer-roadmap.md`
**Commits:** `bd2e6799` (code), `b7628c4e` (P4 sign-off decision)
**Result:** shipped to prod schema; 4604 pytest passed, 0 failed. **Not deployed** (schema ahead of code — the safe direction).

## What was delivered

`Donation.programme`; `sponsor_balance(sponsor, programme)` with the programme **required and
defaulted to nothing**; `sponsor_programme_balances()` + `sponsor_available_total()` (display only);
all seven call sites re-pointed, with the four spend paths authorising against the programme of the
student being funded. Migrations `0120`/`0121` applied migrate-first and verified: **RM172,000.00
before and after**, 6 donations, 0 unattributed, all under `brightpath-flagship`.

## What went well

- **Making the programme argument mandatory did the work a comment never would.** The alternative —
  `sponsor_balance(sponsor, programme=None)` defaulting to a cross-programme total — would have
  compiled, passed every existing test, and silently pooled Sabah money with the flagship's. Instead
  13 call sites failed immediately with a `TypeError`. A required argument is a migration you cannot
  forget to run.
- **P1a paid off exactly where predicted.** Every spend path needed "which gift is this student in?",
  and `application.programme` was already there. The structural sprint's value showed up one sprint
  later, which is the argument for having split it out.
- **The source guard is the durable part.** Tests prove today's behaviour; the guard asserting no
  spend path calls `sponsor_available_total`, and that `sponsor_balance` has no default, prevents
  tomorrow's regression. Same shape as the org-fence static check. Behaviour tests would not have
  caught a future edit that reintroduced a pooled read while all the numbers still looked right.
- **A backfill of financial data carried its own invariant.** "Totals identical, only attribution
  changes" was asserted in the test suite *and* re-checked either side of the prod apply. Capturing
  the RM172,000.00 baseline in the pre-check made the post-check a comparison rather than a hope.

## What to do differently

- **I reported the full suite green before it had actually tested the final code.** Two edits (moving
  a `Programme` import to module level) landed after the background run started. The change was
  trivial and the re-run passed, but "trivial" is exactly the category that hides regressions, and
  the honest sequence is freeze → run → report. **Rule for next time: no source edits between
  launching a verification run and reporting its result** — if an edit is needed, re-run.
- **Splitting P2 mid-sprint was right but should have been visible earlier.** `PaymentRun.programme`
  was in the brief from the start; that payments is live with an open draft run was knowable at
  planning time, not discovery. Sprint briefs touching a live money module should carry an explicit
  "what is currently in flight in this module?" check before scoping.

## Lesson candidates

- **When a shared helper gains a scoping dimension that must never be defaulted, make the new
  parameter REQUIRED rather than optional-with-a-safe-looking-default.** A default silently preserves
  the old (now wrong) semantics at every call site and passes the existing suite; a required
  parameter converts the same mistake into an immediate `TypeError` at every site, which is a
  complete, mechanical worklist. Pair it with a source guard asserting the unscoped/aggregate variant
  is never consulted by an authorisation path. (P2a, 2026-07-26 — added to `docs/lessons.md`.)

## Verification performed

Full suite 4604 passed / 0 failed (reconciled against the summary; no `FAILED` lines), plus a
targeted 161-test re-run covering the two post-run edits. Prod pre-check captured the donation
baseline; post-check confirmed count, total, zero unattributed, correct programme and correct
organisation. No frontend files changed (the sponsor endpoint gained a `balances` array and kept
`balance`), so jest is unaffected. `wat_lint --project .`: 0 fails.

## Follow-ups

- **P2b** — `PaymentRun.programme`. Prod holds an open draft run; backfill it to the flagship
  explicitly and prove the item set is unchanged.
- **Deploy** — still not required. Schema is ahead of code on both P1a and P2a; the next functional
  push carries them together.
- **P4** — sign-off chain settled (reuse payments). One question open: credit-per-transfer vs a
  running top-up ledger.
