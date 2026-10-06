# B40 Redesign — Sprint 7 Retrospective (2026-05-23)

Backend foundation for the decision-engine redesign + apply-form rebuild. Branch `feature/b40-redesign`,
not deployed (single deploy at S12). 6-sprint roadmap: `docs/scholarship/b40-decision-redesign-plan.md`.

## What Was Built
- **Soft-NRIC (Option A):** `StudentProfile.nric_verified`; uniqueness enforced only when verified
  (`unique_verified_nric` replaces `unique_nric_when_set`); NRIC read-only on `PUT /profile/` + `/profile/sync/`
  (changes only via the validated `/profile/claim-nric/`); claim blocks a change once verified (403 `nric_locked`).
- **`coq_score`** (co-curricular — now persisted, was transient) + **`preferred_call_language`** on the profile;
  profile GET returns both + `nric_verified`.
- **New `ScholarshipApplication` intake fields** (all optional): `field_of_study`, `pathways_considered`,
  `top_choices`, `upu_status` (incl. IPTS), `other_scholarships` (+text), `help_university`, `help_scholarship`,
  `anything_else`, `mentoring_candidate` — wired through the create serializer, `_APP_FIELDS`, the audit
  `intake_snapshot`, and the read serializer.
- Migrations courses `0048` + scholarship `0007`.

## What Went Well
- Baseline-first (1086 green) made the two contract-change failures obvious and expected, not surprises.
- Reasoning about the shared `ProfileUpdateSerializer` (PUT + sync) *before* coding meant making `nric` read-only
  closed **both** write gaps in one change, with no rework.
- All new fields optional ⇒ the existing submit path + tests were unaffected; only the two deliberately-changed
  tests moved.

## What Went Wrong
- **(Minor) Two tests failed on first run** — `test_put_profile_updates_new_fields` (PUT set NRIC) and
  `test_nric_unique_constraint` (any duplicate raises). *Root cause:* they encoded the old "IC immutable +
  unique-when-set" contract, which S7 deliberately reverses — not a defect, but a reminder that a contract change
  must update the earlier sprint's tests in the same sprint (lessons.md). *Fix:* updated both to the new contract,
  re-ran the full suite.
- **Finding (not fixed):** the NRIC-gate whitelist in `middleware/supabase_auth.py` (`NRIC_GATE_EXACT`) does not
  list `/api/v1/profile/sync/`, yet `docs/decisions.md` and `test_nric_gate` describe sync as whitelisted. Suite is
  green (sync tests pass via other paths), so no breakage — but the doc/code/test story should be reconciled.
  Logged as tech debt for a future sprint.

## Design Decisions
- Soft-NRIC supersedes the IC-Gate-Sprint "IC immutable" decision — see `docs/decisions.md` (2026-05-23 entry).

## Numbers
- Backend tests: **1086 → 1091** (+4 soft-NRIC, +1 intake round-trip), 0 failures. Golden masters intact
  (SPM 5319, STPM 2026).
- Files touched: ~12 (2 models, 2 migrations, 2 serializers, 1 view, 2 test files, CHANGELOG, decisions, roadmap).
