# Retrospective — Post-award lifecycle Sprint 3: `awarded` + signing → `active`; retire `sponsored` (2026-06-28)

Roadmap `docs/scholarship/post-award-lifecycle-plan.md`. Migration `0075` (status choices, state-only).
The money-adjacent award flow. Dark signing behind `BURSARY_AGREEMENT_ENABLED`.

## What Was Built
Wired the award state machine onto the new statuses and retired `sponsored` (TD-146):
- **`fund_student` → app `awarded`** (a funder committed; the offer is out + signing begins; leaves
  the discovery pool).
- **`awarded → active` by two paths (dual-path, as agreed):** flag-OFF — acceptance + the #14
  cool-off finalises to `active` (`_finalise_award`, renamed from `sponsored`); flag-ON — the student
  + guarantor sign on accept but the app STAYS `awarded`, and the **Foundation counter-signature**
  (`bursary.countersign_foundation` → `_maybe_activate`) executes it → `active`.
- **Revert-to-pool:** an offer declined / held / expired before it becomes active reverts the app
  `awarded → recommended` (`_revert_to_pool`, used by `respond_to_award(decline)`, `hold_pending_award`,
  `lapse_expired_offers`) so it re-enters discovery.
- **Retired `sponsored`** everywhere: STATUS_CHOICES, `pool.FUNDED_STATES`/`IN_PROGRAMME_OR_BEYOND`,
  `DECIDED_STATUSES`, `QUERYING_LOCKED`, `_TERMINAL`, the `complete_onboarding` + award-finalising
  gates, admin status maps + i18n, `officerCockpit`. 0 prod rows to migrate.
- `is_fundable` / `release_pending_awards` / the student award page's "finalising" gate retargeted off
  `sponsored` → the new states.

## What Went Well
- Letting the suite triage the change was efficient: 36 failures pinpointed exactly the award-flow
  semantics that moved; fixing them confirmed the state machine end-to-end.
- The S1/S2 groundwork (pool sets, masking) meant the retirement was a clean contraction.

## What Went Wrong
- **The witness's role was ambiguous in my first cut.** I initially required all FOUR signatures
  (incl. witness) for `awarded → active`, which broke `test_missing_witness_does_not_block`. *Root
  cause:* I didn't reconcile my "Foundation signs last" model with the bursary code's existing
  "witness is **non-blocking**" contract. *Fix:* `_maybe_activate` binds on the three parties
  (student + guarantor + Foundation); the witness is an attestation, not a gate. Lesson: when wiring
  a new transition onto existing code, honour the contracts that code already documents.
- **`makemigrations` re-proposed the foreign `ScholarshipCohort.name` drift a third time** — dropped
  again (S1 lesson stands; the durable fix is upstream).

## Design Decisions (logged in decisions.md)
- `fund_student` → `awarded`; `awarded → active` via the dual path (cool-off when flag-off, Foundation
  counter-sign when flag-on); an unaccepted/declined/held/expired offer reverts to `recommended`.
- The partner-org witness is NON-BLOCKING — execution needs student + guarantor + Foundation only.

## Numbers
- Backend `pytest apps/scholarship/tests/`: **1636 passed**. jest **373**. `next build` clean.
  i18n parity **2879 × 3**. Migration `0075` (state-only). TD-146 resolved.
