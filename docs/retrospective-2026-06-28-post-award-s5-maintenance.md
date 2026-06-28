# Retrospective — Post-award S5: maintenance loop + operational sub-states

**Date:** 2026-06-28
**Branch:** `feat/post-award-s5-maintenance`
**Migration:** `0077_maintenance_substate` (additive column, migrate-first)

## What Was Built
The operational layer over `status='maintenance'` (the funded recurring loop). A funded
student now carries a `maintenance_substate` an admin manages, distinct from the
sponsor-facing ACADEMIC band (`pool.derive_progress_state`, derived from results):

- **`maintenance_substate`** on `ScholarshipApplication`: `on_track` (default) / `probation`
  / `on_hold` / `ready_to_close`. Additive column, migrate-first.
- **`maintenance.py`** core: `set_substate` (maintenance-only + valid-substate gate, free
  movement between the four), `is_on_hold`, `sponsor_support_status` (coarse signal),
  `ready_to_close_queryset` (the S6 close worklist).
- **`on_hold` pauses the money:** `disbursement.release_tranche` now refuses to release a
  tranche for an on-hold student (`DisbursementError('on_hold')`) — the hold is a real
  invariant, not just a label. Withhold/return still work while on hold.
- **Surfaces:** cockpit (full sub-state badge + transition buttons + on-hold hint, in the
  disbursement panel); the student in-programme page (a calm "support paused" banner when
  on_hold); the sponsor card (a coarse `support_status` = `paused` / `completing` only —
  **probation is never shown to a sponsor**). i18n `admin.maintenance.*` +
  `scholarship.inProgramme.onHold.*` + `sponsorPortal.myStudents.support.*` en/ms/ta.

The recurring loop (record SemesterResult → review → release/withhold next tranche) is now
fully usable end-to-end: the record/release/withhold pieces shipped in S4, and S5 adds the
sub-state overlay + the on-hold money-pause that the review step needs.

## What Went Well
- The S2/S4 groundwork meant the loop closed with **one additive column** and no changes to
  the pool/in-programme gates. `maintenance` was already a funded state.
- The privacy split fell out cleanly: academic band (results-derived, sponsor-facing) vs
  operational sub-state (admin-set), with a deliberate one-way coarsening for the sponsor
  (`sponsor_support_status` hides probation). Anonymity tests still green.
- Branching off `origin/main` (S4's lesson) — migration numbered `0077` first try, no collision.

## What Went Wrong
1. **`makemigrations` re-proposed the foreign `ScholarshipCohort.name` drift again (5th sprint).**
   *Symptom:* the generated migration carried the unrelated `AlterField`. *Root cause:* the
   long-standing model/migration-state mismatch persists. *Fix:* hand-wrote
   `0077_maintenance_substate.py` with only the `AddField` (now a reflex). **This has recurred
   every post-award sprint — it should be retired for real:** a one-line state-only migration
   that records the cohort.name `AlterField` once would stop `makemigrations` proposing it
   forever. Logged for the consolidation review / a quick standalone fix.

## Design Decisions
- **Sub-state is a stored admin field, NOT derived.** `on_hold`/`ready_to_close` are decisions
  that can't come from results; `probation` is an admin judgement (a poor CGPA only *suggests*
  it). One authoritative field beats mixing derived + manual signals.
- **Two parallel signals, deliberately:** the academic band (`derive_progress_state`) stays the
  sponsor's "how's it going"; the operational sub-state is the foundation's lifecycle control.
  The sponsor sees only a coarse `paused`/`completing` — never `probation`.
- **`on_hold` blocks `release_tranche` (not just a flag).** Putting the guard in the writer makes
  the pause an invariant the UI can't bypass. Withhold/return stay allowed (you can still record
  ledger movements on a paused student).

## Numbers
- Migration: `0077_maintenance_substate` (additive column, migrate-first).
- Tests: backend 1665 pytest (+16 `test_maintenance.py`), frontend 383 jest (unchanged — the
  new surfaces are component-level; logic is covered backend-side).
- i18n: parity 2920×3 (+17 keys).
- Files touched: ~14.
