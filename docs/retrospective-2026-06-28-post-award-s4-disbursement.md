# Retrospective — Post-award S4: Disbursement/tranche ledger + `active → maintenance`

**Date:** 2026-06-28
**Branch:** `feat/post-award-s4-disbursement`
**Migration:** `0076_disbursement` (CreateModel — additive DDL, migrate-first + RLS)

## What Was Built
The money-OUT ledger for a funded award. A tranche (`Disbursement`) is scheduled against a
funded application and marked disbursed by an admin. It is a LEDGER, not custody — real
toyyibPay is deferred (TD-075), so a release records a 'released' row with a mock reference.

- **Model `Disbursement`** (`disbursements`): `scheduled → due → released | withheld | returned`;
  FK application (CASCADE) + nullable FK sponsorship (SET_NULL, future Foundation-direct + history
  survival); `sequence`, `label`, `scheduled_for`, `released_at`, `actioned_by`, `reference`, `note`.
- **`disbursement.py`** core: `schedule_tranche` (funded-gate, amount validation, auto-sequence,
  funder auto-link), `release_tranche`, `withhold_tranche`, `return_tranche`, `mark_due`,
  `_flip_to_maintenance`. **The first release flips the application `active → maintenance`**
  (idempotent — a second release does not re-flip).
- **Admin endpoints** (reviewer-gated, access-scoped): `POST …/applications/<pk>/disbursements/`
  (schedule) + `POST …/disbursements/<pk>/<action>/` (release|withhold|return|mark_due).
- **Cockpit panel** (`[id]/page.tsx`, gated to funded states): tranche list + per-row actions +
  schedule form; `lib/disbursement.ts` pure helpers (node-jest tested); `admin.disbursement.*` i18n
  en/ms/ta (Tamil first-draft).

## What Went Well
- The state machine slotted cleanly into the existing pool/in-programme gates — `maintenance` was
  already in `pool.FUNDED_STATES` (built in S2), so `derive_progress_state` + `_require_in_programme`
  needed **zero** changes. The S2 groundwork paid off.
- Full suite green first try after the backend: 1649 pytest, 383 jest (+10), `next build` clean, i18n
  parity 2903×3. No drift in earlier code paths (the lesson "run the FULL suite" held — nothing broke).

## What Went Wrong
1. **Branched off a stale local `main` — the new migration mis-numbered as `0073` and the S1–S3
   files "vanished".** *Symptom:* `git checkout -b … main` put the worktree 62 commits behind; the
   S1–S3 migrations (0073–0075) disappeared and `makemigrations` produced a colliding `0073`.
   *Root cause:* the worktree's local `main` ref was never fast-forwarded after S1–S3 were pushed to
   `origin/main`; a sibling branch (`feat/post-award-s3-awarded`) happened to equal `origin/main`, which
   masked the staleness. I trusted local `main`. *Fix:* always branch off `origin/main` (or fetch +
   verify `main == origin/main`) — added to `docs/lessons.md`. Recovered cleanly (reset branch to
   origin/main, re-applied the model edit, re-ran makemigrations → correct `0076`).
2. **`makemigrations` re-proposed the foreign `ScholarshipCohort.name` help_text drift (4th sprint
   running).** *Symptom:* the generated migration carried an unrelated `AlterField` on cohort.name.
   *Root cause:* a long-standing model/migration-state mismatch on a field this sprint didn't touch.
   *Fix (as before):* hand-wrote `0076_disbursement.py` with only the `CreateModel`. This is now a
   known, documented recurring step — candidate for a one-off state-only migration to retire it
   permanently (logged for the consolidation review).

## Design Decisions
- **Tranche linked to BOTH application and sponsorship (sponsorship nullable).** The application is
  the lifecycle owner; the sponsorship is the funder. Nullable sponsorship keeps a future
  Foundation-direct award (no Sponsorship row) working and preserves history on a Sponsorship delete.
- **`active → maintenance` flip lives in `release_tranche`, gated `if status == 'active'`.** Idempotent
  by construction; no separate "first release" bookkeeping needed.
- **Withhold/return built now, but the maintenance LOOP (result→review→release/withhold next) is S5.**
  S4 ships the ledger + the one transition; S5 wires the recurring decision loop + sub-states.

## Numbers
- Migration: `0076_disbursement` (1 new table + RLS, migrate-first).
- Tests: backend 1649 pytest (+13 `test_disbursement.py`), frontend 383 jest (+10 `disbursement.test.ts`).
- i18n: parity 2903×3 (en/ms/ta); `admin.disbursement.*` added.
- Files touched: ~16.
