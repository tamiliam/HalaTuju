# Retrospective — Code-health Sprint 1: decision & needs-gate integrity (2026-07-03)

## What Was Built

Sprint 1 of the code-health roadmap (`docs/plans/2026-07-03-code-health-review.md`, findings #2/#3/#4):

1. **Cancel-decline integrity (#2).** The decline email got its own stamp
   (`decline_email_sent_at`) instead of reusing `decision_email_sent_at` (already stamped by the
   shortlist PASS email, so the restore branch never ran for real students), and
   `cancel_pending_decline` now restores the **snapshotted** pre-decline status
   (`pre_decline_status`, taken in `_record_reject`) instead of hardcoded `'interviewed'` — which,
   since the QC-gate repurposing, would have put a verdict-less case into the QC queue. Migration
   `0090` (2 additive columns, migrate-first on prod, verified). 4 new regression tests, including
   an end-to-end one through `release_decision`.
2. **YTD-alone guard (#3).** `income_engine._salary_monthly_amount` no longer returns YTD÷12 when
   the monthly cell is unreadable (up-to-12× income understatement → false B40 green). YTD counts
   only alongside a readable monthly figure; alone → None → 'verify at interview'.
3. **Subject-map sync (#4).** 64 keys the grades form offers were missing from
   `academic_engine._SUBJECT_BM`; synced from `subjects.ts` and pinned with
   `test_subject_drift.py`, which parses subjects.ts directly and fails loudly (never skips) in
   both drift directions.

Also ridden along earlier the same day (pre-sprint, on `main`): the PII history purge (Task A) and
the docs carry-over + `.gitignore` guard.

## What Went Well

- All three fixes were small and surgical because the review had already produced concrete failure
  scenarios with file:line — no investigation phase was needed.
- The migrate-first discipline (hand-written Postgres DDL via Supabase MCP, sentinel-column check
  before ALTER, verify after) worked exactly as the lessons prescribe.
- 3,185 backend tests green on the first full run after all three changes.

## What Went Wrong

- **The subject drift was 2.5× worse than the review estimated (64 keys, not ~25), and had been
  accumulating invisibly since S18 (2026-05-29) added the subjects to the web side only.**
  Root cause: the mirror was enforced by a code comment ("keep the two in sync"), and comments
  don't fail builds. The drift only produced a symptom when a student actually picked one of the
  subjects — and the symptom (student's "missing subject" loop) was invisible to tests because
  both sides were consistent *within themselves*.
  System change: `test_subject_drift.py` now parses the frontend file from the backend test suite
  and fails on any asymmetry — plus a parse-sanity guard so a restructure of subjects.ts can't
  silently turn the test into a no-op. (Lesson generalised in `docs/lessons.md`.)
- **`test_decision_cooloff.py`'s fixtures never walked the real release path, so they pinned the
  buggy behaviour as green.** Root cause: fixtures created applications directly in the target
  status, skipping `release_decision` — the very step that stamps the field the bug keyed on.
  System change: the new regression test goes through `release_decision`; noted in lessons.md that
  a state-machine test must enter states via the real transitions, not by constructing them.

## Design Decisions

Logged in `docs/decisions.md`:
- Restore-to-snapshot (not restore-to-fixed-status) for cancel-decline; legacy rows without a
  snapshot fall back to the old `'interviewed'` behaviour.
- `_send_decline_for` stamps BOTH `decline_email_sent_at` (authoritative for cancel) and
  `decision_email_sent_at` (back-compat, "a decision email went out").
- YTD-alone is unusable (conservative None) rather than attempting months-elapsed inference — the
  slip month is itself an OCR field and a wrong divisor is worse than an interview check.

## Numbers

- 3,185 backend tests (1,986 scholarship + 1,199 courses/reports), 0 failures; +12 net new tests.
- 1 migration (`scholarship/0090`, additive, migrate-first).
- Files touched: 8 (4 source, 3 test, 1 migration). No frontend change, no i18n change.
- Prod DDL verified: both columns present with correct types/defaults.
