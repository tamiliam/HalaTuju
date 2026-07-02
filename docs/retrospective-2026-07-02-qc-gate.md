# Retrospective — QC gate (repurposed `interviewed` stage) — 2026-07-02

## What shipped
A proper quality-control step between a reviewer's verdict and `recommended`, formalising the owner's
previous manual "watch and reopen" habit — **without a new status**. The `interviewed` stage is repurposed
as **AWAITING QC**:
- Submitting interview *findings* no longer advances the status (`submit_interview`): a case stays
  `interviewing` (reviewer's working state) until the verdict is submitted.
- The reviewer's verify-accept ("submit verdict") lands the case in `interviewed` (awaiting QC), not
  `recommended`.
- A new **`qc` role** (or super) uses a **Quality Control** box in the cockpit (below the Decision box):
  **Accept** → `recommended`; **Reopen** → gaps note → case back to `interviewing` (reopened banner) +
  the assigned reviewer emailed the comments.

## Implementation notes
- One endpoint `POST …/qc-decision/ {decision, comments}` gated by a new `_require_qc` (super or `qc`,
  case must be `interviewed`). QC reads all (`_b40_scope('qc')='all'`) but has no reviewer write.
- QC-Reopen reuses `reopen_decision`/`DecisionReopen` verbatim (reason, audit, correction-count). The
  reopen status mapping became two-step and **invertible** — `recommended↔interviewed`,
  `interviewed↔interviewing` — so `cancel_reopen` stays unambiguous by current status.
- Choices-only migrations (courses 0060 role, scholarship 0088 status relabel) — **no DDL**.

## What went well
- **Reuse paid off:** the reopen machinery + `decision_reopen_reason` surfacing + the reviewer-email
  helper family meant QC-Reopen was mostly wiring, not new mechanism.
- **The flagged "main risk" evaporated on inspection:** the reviewer verdict nudge keys on
  `verdict_decided_at IS NULL`, not `status=='interviewed'`, so keeping cases in `interviewing` longer
  needed no re-keying. Reading the actual selector beat assuming.
- **Re-checking migration numbers caught a collision:** the pre-flight fast-forward pulled in a fresh
  `scholarship 0087`; numbering off the stale tree would have double-booked (the exact TD-152/migration
  lesson). Numbered 0088 correctly.
- Test breakage from the transition change was small and expected (5 tests), fixed to assert the new
  semantics rather than patched around.

## What to watch / lessons
- **`next build` type-check OOMs on this 8 GB box after a full pytest run** (Jest-worker `WorkerError`,
  after "✓ Compiled successfully"). It's memory, not a code error — confirmed by a clean `tsc --noEmit`
  at Next's target (es2018 + downlevelIteration) with zero app-code errors. Cloud Build (more RAM)
  completes it, as it does for main. Lesson: don't run the heavy pytest suite and `next build` back-to-back
  on this box; trust "Compiled successfully" + a targeted `tsc` when the worker dies.
- Bare `npx tsc --noEmit` is **not** faithful to `next build` (it uses the tsconfig target, surfacing
  `TS2802 Set-iteration` noise in test files that Next's injected target resolves). Use
  `--target es2018 --downlevelIteration` to get a representative signal.

## Deferred
- The invite-UI button for the `qc` role (backend already accepts it; the owner's QC role is granted via
  DB in rollout — a partial button risked missing i18n keys).
- Auto-defaulting the QC user's scholarship-list filter to the awaiting-QC queue (cosmetic; the status
  filter + relabel already make it easy).
- QC over reviewer **rejections** (accept-path only this sprint).

## Verification
3090 backend tests pass (scholarship + courses), incl. 11 new (`test_qc_gate.py`) + 5 updated. `next build`
compiled successfully; app code type-clean at Next's target. Choices-only migration (no DDL).

## Follow-up (same day) — senior `qc` role + BrightPath/HalaTuju nav split
The owner refined the model live: Suresh (a co-founder) wants **one** account that (a) reviews his assigned
students *and* (b) QCs others, plus (c) keeps a view-all admin surface — but only the **bursary** side.
Delivered:
- **`qc` = senior superset:** assignable (`services._can_review` + assignable list include `qc`) and can
  review its assigned cases (the assignment-based `_can_review_app` already permits it); **self-QC guard**
  in `_require_qc` (403 `self_qc_forbidden`) + the cockpit hides the QC box when the qc is the assigned
  reviewer — encoding the owner's "I'll QC the student he's reviewing" rule in code.
- **Nav split by product:** `admin`+`qc` (BrightPath) → `Scholarship · Sponsors · Profile · Guide · FAQ`;
  the HalaTuju course-selector pages (Dashboard/Students/Course-Data) stay with `super` (+ `partner`, the
  HalaTuju org rep). BrightPath roles landing on `/admin` now redirect to `/admin/scholarship`.
- No migration. +5 pytest (3107 scholarship+courses green). `next build` exit 0.
- **What went well:** the assignment-based permission from earlier the same day meant "qc can review its
  assigned case" needed *zero* new write logic — only making `qc` an assignable target + the self-QC guard.
- **Deferred:** partner Scholarship view → **TD-155**; the auto-default QC queue filter (cosmetic).
