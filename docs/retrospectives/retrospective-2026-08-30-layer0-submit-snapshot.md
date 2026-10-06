# Retrospective — Layer 0: what the programme asked for is frozen at Submit (2026-08-30)

## What shipped

The first of the two items Sprint 3a deferred, brought forward the same day Sprint 4 went live
because Sprint 4 made it urgent: with questions now switchable, an organisation turning one ON
would have made already-submitted forms "incomplete", and `revert_if_profile_incomplete` would
have un-submitted those students as if they had edited something themselves.

- **`ScholarshipApplication.requirements_snapshot`** (migration `0147`, additive, nullable jsonb).
  `{'captured_at', 'documents': {code: state}, 'questions': {code: state}}`.
- **`requirements.freeze`** — called by `confirm_profile` in the same save as the status flip,
  so the two are never observable apart. Idempotent: never overwrites a first freeze.
- **`requirements.resolve` reads the frozen copy FIRST.** That is the whole design: the gate,
  the payload, the verdict facts and the ticket queue all consume `resolve`, so all of them
  honour the freeze with no edits of their own.
- **A revert thaws.** Back in the wizard (only reachable through the student's own edit — the
  completeness check reads the frozen set, so a configuration change cannot cause it), the
  student follows the current form and is re-frozen at the next Submit.
- **`backfill_requirements_snapshots`** (report / `--apply`; cron job, write gated by
  `REQUIREMENTS_SNAPSHOT_APPLY=1`) freezes the ~92 rows submitted before the column existed.
  With zero overrides in production every one freezes to the seeded defaults.

**Owner's ruling (2026-08-30): freeze at Submit, not at start.** A student halfway through gets
the newest form; only Submit fixes their version.

## Verification

- +9 tests (`test_layer0_snapshot.py`): the exact regate scenario, the still-editing control,
  the payload reading the frozen copy, idempotent freeze, thaw-and-refreeze, and the backfill's
  report / apply / idempotence / non-candidate.
- **Bite-check:** with the frozen read in `resolve` disabled, the scenario test and the payload
  test fail. Committed before mutating.
- Full backend suite green; `makemigrations --check` clean; no frontend change.

## What went wrong

- The first fixture was not a complete application (no income route), so five submit tests
  raised `IncompleteProfileError` at once. Root cause: I wrote a fresh "complete app" recipe
  instead of reading the house one (`test_details._make_complete`). Lesson already on file
  (2026-06-05): grep for every complete-app helper before touching the gate. Fixed in one edit.

## Lessons

- **Put a freeze at the seam every consumer already reads, not at each consumer.** See
  `docs/lessons.md` 2026-08-30.
