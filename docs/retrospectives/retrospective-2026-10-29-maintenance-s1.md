# Retrospective — Student maintenance Sprint 1: one predicate, on hold stops money, the activity log (2026-10-29)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md`. Owner rulings: `docs/decisions.md`, 2026-10-29.
Shipped as `ad299d31` (moves only), `901c63d5` (feature), `ae939213` (lead review), `99ee813b` (adversarial
review); pushed as `99ee813b`. Migration `scholarship/0183_maintenance_activity_log` applied by hand on production
before the push (DDL, RLS, `service_role` policy, ledger row — all in its docstring).

## What Was Built

- **One predicate, `maintenance_scope.py`.** In maintenance = `awarded` with `vircle_activated_at`, or
  `active` / `maintenance`. `has_file` adds a closed student who was in it (read-only). The 65 live students
  (all `awarded`, all Vircle-activated) are now inside every in-programme gate. The status machine is unchanged.
- **On hold stops money, every door.** Run creation leaves her out; a hold placed after a run takes her item out
  of every editable run (a signed run reverts to draft); `set_item` will not put her back; `complete` refuses a run
  that still pays her (`on_hold_in_run`, with a count); `release_tranche` already refused. The MONEY hold
  (`maintenance.is_on_hold`) is the stored `on_hold` on a payable status, never the wallet stamp.
- **Who may hold.** `can_set_substate`: a payable status AND (in maintenance OR a `vircle_id` held); a stored
  hold can always be lifted. A move to or from `on_hold` needs `payments.may_prepare` (403 `hold_needs_payments`).
- **Activity log foundation.** `StudentActivity` (`student_activity`) + `activity.py`; wired: `substate_changed`
  (with the runs a hold touched and whether their signatures were cleared), `result_submitted`,
  `payment_released` (runs and tranches), `closed`. Written inside the caller's transaction.
- **Sub-state who/when** (`maintenance_substate_changed_at` / `_by`), a conditional write against the stored value,
  and a reset to on_track (stamped `system`, logged) when an award falls through.
- **Student page** reads served answers (`has_file`, `in_maintenance`, `can_record_results`, `support_paused`)
  from a serializer mixin; the raw sub-state is no longer served to her. Run items carry `on_hold` (a chip).
- **Moves only, first:** the Vircle ID rules left `payments.py` for `vircle_ids.py`, taking `payments.py` out of
  the oversize ledger (651 → 579, ends the sprint at 595); `test_maintenance.py` converted to the factory.

## What Went Well

- **Measured before changing**, as the brief asked: the scholarship baseline (8,203 passed) was taken before the
  first edit, and the two size budgets that were AT their limit (`payments.py`, `serializers.py`) were found
  before any code was written, so the split went in its own commit instead of a mid-sprint scramble.
- **Every refusal is pinned at the door that makes it** — service tests for each money door, plus one test
  through the real sign endpoint showing a refused approval leaves the run signed and unpaid.
- **Bite-checked (step 4b):** five injected faults, all turned red, every file restored to its original digest —
  (1) `is_on_hold` leaning on the file predicate → `TestTheHoldIsNotTheFilePredicate`; (2) `complete` not
  refusing → `TestCompletionRefusesAHeldStudent`; (3) the view's `may_prepare` gate removed →
  `TestHoldIsAMoneyAct`; (4) `can_record_results` widened to the predicate → `test_maintenance_scope`;
  (5) the hold not excluding open runs → `TestHoldAfterTheRunWasMade`. No silent bite.
- The `hold_needs_payments` gate and the narrowed results gate change no reviewer-facing Guide or FAQ text (neither
  mentions holds or result recording), so no Guide change was owed.

## What Went Wrong

1. **The first cut tied the money hold to the wallet stamp.** `is_on_hold` was written as "in maintenance AND
   on hold", and "in maintenance" reads `vircle_activated_at` — a field MIRRORED from Vircle's relay sheet. If
   that stamp were ever cleared, the hold would silently stop holding and the next run would pay her. It also
   left the students a run pays on their wallet ID alone (not yet activated) impossible to hold. The lead found
   it in review, before the adversarial pass. **Root cause:** one predicate was asked to answer two questions —
   "who has a file?" (a display/eligibility question, fine to derive) and "is her money stopped?" (a money
   decision, which must survive any other system's write). Reusing it felt like the "one definition" the brief
   asked for. **System change:** the hold now reads only the stored decision plus the payable status; a test
   clears the stamp after a hold and proves the run still refuses; and a lesson (`docs/lessons.md`) says a money
   guard reads the stored decision, never a mirrored or derived field.
2. **A reviewer could undo a finance sign-off.** Placing a hold reverts a signed run to draft and clears its
   signatures, and the sub-state endpoint admitted anyone with app-write rights (a reviewer). The side effect
   on another module's object was designed in, but the permission was not re-asked. **Root cause:** the
   endpoint's gate was inherited from S5, when a hold touched only the student's own tranches; the sprint
   widened what the action DOES without re-reading who may do it. **System change:** a move to or from
   `on_hold` needs `payments.may_prepare`; the runs it touched are recorded on the activity row and in a
   WARNING AUDIT line; tested through the endpoint (reviewer 403, Prepare holder 200). Review prompt for the
   rest of the roadmap: when an action gains a side effect on another module's object, the gate must be the
   UNION of both modules' gates.
3. **Unreviewed, self-reported results would have reached sponsors.** Widening `record_semester_result` to the
   predicate let 65 more students type a CGPA that feeds the sponsor-visible progress band with no officer review.
   **Root cause:** the widening was checked against who may WRITE a result, not against every reader of it —
   the sponsor band, the portfolio badge, and the support status read results or sub-states by three different
   rules. **System change:** recording stays active/maintenance (`can_record_results`, served to the page) until
   Sprint 4, which carries results review and one sponsor-reader rule with a cross-reader test (roadmap row
   updated); lesson recorded.

## Design Decisions

- The FILE predicate and the MONEY hold are separate rules (see Went Wrong 1); `sponsor_support_status` follows
  the money hold, so a sponsor reads "paused" exactly when money is stopped — the same answer the portfolio badge
  gives.
- `has_file` for a closed record trusts `active_at`, or the wallet stamp only with a post-award-only closure reason:
  `revert_to_pool` keeps the stamp, and a later stalled pre-award close must not count (TD-352).
- The activity row is written inside the caller's transaction (the log is part of the record), which makes the
  migrate-first rule non-optional for every path that writes it.
- `payments.complete` refuses the WHOLE approval when one included student is on hold, rather than skipping her:
  the approver signed a list, and paying a different list than the one signed is the D2 rule this would break.
- Not changed, by design: `pool.FUNDED_STATES` / `derive_progress_state` (sponsor band — Sprint 4),
  `services/consent.py`'s onboarding gate, `views._FUNDED_STATES`, `spending_import`, `disbursement._require_funded`.
- Pre-existing and NOT fixed here: **TD-367** (`complete` never re-checks a CLOSED status) — the hold check sits
  beside the place that fix goes; it belongs to the TD-383 choke-point sprint.

## Numbers

- Full api suite: **9,869 pytest** (after the rebase onto `7a19c93d`); scholarship: **8,278**; baseline before
  the first edit: 8,203 passed / 3 skipped (scholarship).
- Web: **4,820 jest / 306 suites**; `tsc`, lint and i18n clean; `next build` OK; bundle budget OK.
- Migration ledger: 0183 is the last file and is recorded on production (applied by hand by the lead with RLS,
  policy and ledger row).
- Size budgets: `payments.py` left the oversize ledger (651 → 595); `serializers.py` held at 1,215 (its limit);
  `models/applications.py` 908 (limit 919); `test_maintenance.py` left the hand-built-fixture ledger.
- Four commits, two review rounds (lead + adversarial): 2 must-fix (M1, M2) and seven lesser (L1–L7): L1–L3 and
  L5 fixed, L4 a roadmap note, L6 the lead's deploy order, L7 raised as TD-420. TD-419 raised for the cockpit.
