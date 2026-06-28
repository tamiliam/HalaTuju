# Retrospective — Reviewer-query automation S1: full-household-income capture

**Date:** 2026-06-29
**Branch:** `feat/reviewer-query-s1-household-income`
**Migration:** none (logic only)
**Roadmap:** `docs/scholarship/reviewer-query-automation-roadmap.md` (S1)

## What Was Built
The single most-repeated manual reviewer query — chasing the *second* parent's income, or a
blank parent's status — is now auto-raised. The sponsor counts the FULL household income, but
apply only collects the ONE declared earner; reviewers filled the gap by hand (~14 of the 29
recommended/interviewing students). Now deterministic:

- **`income_engine.parent_income_status(application, member)`** → `satisfied` (non-earning
  status recorded, OR income evidence on file) / `need_proof` (earning occupation, no income
  doc) / `need_status` (blank slot). `parent_income_gaps()` returns the per-parent gaps.
- **`check2_queries` integration:** a `need_proof` gap raises an **uncapped doc-request**
  (`{father,mother}_income_proof_missing`, kind=`doc`) — per decision #1 docs sit outside
  `MAX_CLARIFY`; a `need_status` gap raises a **capped clarify** (`{father,mother}_status_unknown`),
  prioritised first in `_CLARIFY_ORDER`. Both auto-resolve when the gap clears (income evidence
  arrives / status recorded), via the same reconcile loop as the existing clarifies.
- **Frontend:** the 4 codes added to `actionCentre.ts` KNOWN_CODES (so they render as
  assistant items, not raw prompts) + student `actionCentre.item.*` copy + the admin cockpit
  Check-2 flat copy, all en/ms/ta.

The key modelling insight: **occupation already encodes non-earning status**
(`family.NON_EARNING` = homemaker/retired/unemployed/unable/deceased/no_contact). So "every
parent must be EITHER non-earning OR income-evidenced, else ask" cleanly covers both the
"upload the other parent's payslip" and the "why only one earner?" cases the owner described.

## What Went Well
- The corpus-first approach paid off: pulling the ~60 real manual queries made the rule
  obvious and the priority unarguable (the second-parent gap dominates).
- The rule fell straight out of existing structure (`NON_EARNING`, `household_member` doc tags,
  `chain_verified_earner`) — no schema change, no migration.

## What Went Wrong
1. **Changing `check2` shifted 5 existing tests that used blank-parent fixtures.** *Symptom:*
   `test_resolution` / `test_query_sla` asserted specific clarify sets / "no questions", but blank
   parents now legitimately raise the new status clarifies. *Root cause:* the shared fixtures
   never set a family roster, so my new rule fired in unrelated tests. *Fix:* made those fixtures
   income-complete (father earning + a payslip, mother homemaker). *Lesson (already on file):*
   when a sprint changes an earlier code path, run the FULL suite and update the older fixtures in
   the same sprint — caught + fixed here before close.

## Design Decisions (settled pre-sprint, applied)
- **Doc-requests uncapped, question-clarifies capped** (#1) — a payslip upload isn't a "question",
  so it never suppresses the clarify queue; both parents can be asked for proof.
- **Student-facing for document gaps** (#3) — uploading a parent's payslip is hard to game, so it
  belongs in student-facing Check 2; resilience/honesty probes are deferred to the interview (S4).
- Non-earning **status is data we already hold** (the occupation code), so a homemaker/deceased
  parent is never needlessly questioned.

## Numbers
- Tests: backend 1713 pytest (+10 `test_parent_income.py`; +5 existing fixtures updated),
  frontend 387 jest. i18n parity 2955×3 (+12 keys). No migration.
- Files touched: ~9.

## Next
S2 — stale income doc + sibling-in-tertiary funding + high-utility probe (same plumbing).
