# Retrospective — Post-award S6 (FINAL): manual closure + reasons + thank-you re-gating

**Date:** 2026-06-28
**Branch:** `feat/post-award-s6-closure`
**Migration:** `0078_closure_stamp` (additive `closed_at` / `closed_by`, migrate-first)

## What Was Built — the lifecycle is now complete end-to-end
The terminal step of the post-award lifecycle: an admin manually closes a funded file with a
reason. `recommended → awarded → active → maintenance → **closed**` now runs the full arc.

- **`closed_at` / `closed_by`** audit stamp on `ScholarshipApplication` (mirrors
  `rejected_at`/`rejected_by`). `closure_reason` already existed from S2.
- **`closure.py`** core: `close_application(application, *, closure_reason, by_email)` —
  gated to funded states (active/maintenance) + a valid (non-blank) reason; stamps + flips to
  `closed`. `POSITIVE_REASONS = (graduated, completed)` for copy. Terminal (no reopen path).
- **Closure-safety money invariant:** `disbursement.release_tranche` now also requires a funded
  state (`_require_funded`), so a leftover scheduled tranche on a closed file is un-releasable.
- **Thank-you re-gating:** `in_programme.submit_graduation_message` now uses `_require_can_thank`
  (active/maintenance/**closed**) — a graduated/completed student can still write to their sponsor
  after the file is closed. Semester results / promo consent stay funded-only.
- **Surfaces:** cockpit closure panel (reason selector + offboarding checklist + Close, plus a
  closed summary with reason badge + who/when); the student in-programme page reached by a closed
  student too, with a warm graduated/completed (or neutral) banner and the thank-you kept open, the
  results form hidden; `admin.closure.*` + `scholarship.inProgramme.closed.*` i18n en/ms/ta.
- **Reviewer-gated** `POST …/applications/<pk>/close/ {closure_reason}`.

## What Went Well
- The lifecycle's earlier groundwork made the capstone small: `closure_reason` (S2) and the
  status value `closed` (S2, already excluded from pool/progress) were in place, so S6 was one
  additive audit stamp + a writer + two re-gatings.
- The release-after-close gap was caught by a test I wrote **before** finding it
  (`test_cannot_release_tranche_after_close` failed → added `_require_funded` to `release_tranche`).
  Test-first paid for itself within the sprint.
- Branching off `origin/main` again — `0078` numbered first try, no collision.

## What Went Wrong
1. **`next build` caught a missing FE type field (`closure_reason` on `ScholarshipApplication`).**
   *Symptom:* the student page used `app.closure_reason` but the lib/api type lacked it → TS compile
   error (not caught by jest, which is node-env and doesn't type-check the page). *Root cause:* I
   added the field to the backend serializer + the page, but updated only the *admin* type, not the
   *student* `ScholarshipApplication` type. *Fix:* added it; rebuilt clean. **Recurring shape:** a
   new read-serializer field needs its FE type updated in *every* type that mirrors that endpoint —
   here the student `ScholarshipApplication`, not just `AdminScholarshipDetail`. `next build` (raw)
   is the reliable catch; jest is not.
2. **`ScholarshipCohort.name` drift, 6th sprint.** Hand-wrote `0078_closure_stamp.py` to omit it
   (reflex). TD-147 (logged S5) still stands — retire it in the next consolidation/small-change.

## Design Decisions
- **Closure is manual + terminal (no auto-close, no reopen here).** A human confirms the
  relationship ended and WHY; auto-closing on graduation/last-tranche would lose that judgement. A
  mistaken close is rare and can be handled by a deliberate admin DB action, not a self-serve reopen.
- **The thank-you relay outlives closure; the funded-only writes don't.** A separate
  `_require_can_thank` gate (active/maintenance/closed) keeps semester results / promo consent
  funded-only while letting gratitude flow after the file closes.
- **`release_tranche` enforces funded-state, not just on-hold.** Closure safety belongs in the money
  writer (an invariant the UI can't bypass), not only in the close action.

## Numbers
- Migration: `0078_closure_stamp` (additive columns, migrate-first).
- Tests: backend 1676 pytest (+11 `test_closure.py`), frontend 383 jest.
- i18n: parity 2943×3 (+23 keys).
- Files touched: ~16.

## Post-award lifecycle — DONE
All 6 sprints shipped (S1 rename → S2 statuses → S3 award/signing → S4 disbursement → S5 maintenance
loop → S6 closure). The whole arc is dark (no live awarded students); go-live still gated on bursary
Phase-0 (TD-140) + real disbursement (TD-075). Outstanding small item: TD-147 (retire the cohort drift).
