# Retrospective — Remote-station batch, 2026-07-12→14

Three coherent deliverables built in one remote-station stint and pushed to `main` as they
landed, but never formally closed. This retro closes them together. All code is **live** (last
build `cdf2a44`, 14 Jul); the final commit (`92d30877`) is docs-only (the Check-2 #117 plan).

## What Was Built

**A. Vircle eWallet onboarding** (`e3bd641`…`3d092f1`, 8 commits)
- The award email now carries the onboarding ask (install Vircle → confirm in the Action Centre),
  with the guide PDF attached — one email, not two. Amount / sponsor / bank-details stay out.
- A `vircle_setup_pending` confirm task behind `VIRCLE_SETUP_ENABLED` (default OFF/dark), raised on
  the SEND (never a sync), with the resolve-lock and set-aside carve-outs it needs to be resolvable.
- A generated relay sheet (mirror of the DB, least-privilege scopes, owner columns, generated-columns-
  only wipe, first-come ordering) — the list handed to Vircle and the chase list.

**B. Query / assignment stage-gates** (`9864d5b`, `9d34f29`)
- The machine asks only during *Completed*; the officer through *interviewing*; nobody before or after.
  Two predicates (`auto_queries_allowed` / `officer_queries_allowed`) are the single source of truth.
- A case may only change hands while there is a review to do (`ASSIGNABLE_STATUSES` / `is_assignable`),
  gating assign/reassign/unassign alike; the dropdown is disabled with a hover reason when the server
  would refuse.

**C. Income-doc reslot + payslip-driven EPF chain (#126)** (`ea0d1a4`…`cdf2a44`, 4 commits)
- A suppressed informal-earner payslip request re-opens when the student says he DOES have one
  (`payslip_claim`, negation-first).
- `vision.reference_names()` widens income-doc name-matching to the roster (no more false mismatch on
  a genuine parent's EPF).
- `epf_no_employer()` reads the all-zeros employer number from either field (unemployment proof no
  longer dropped).
- `_reslot_income_doc` re-files an EPF uploaded into the payslip slot (deterministic, KWSP-anchored).
- The payslip decides whether to ask for the EPF (`slip_epf_evidence`); occupation becomes the
  fallback. `salary_doc` **MODEL_VERSION 1.0.0 → 1.1.0** (adds a `kwsp` marker; re-scores nothing).

## What Went Well

- **The commit trail is retrospective-grade.** Every commit states the symptom, the root cause, the
  fix, and the test count. This close was reconstructable in full from `git log` alone — the discipline
  paid for itself.
- **Owner-in-the-loop bug-finding.** Four of the sharpest fixes (#126 silent non-answer, the all-zeros
  employer number, the "Emailed, not confirmed" mislabel, the A:Z sheet wipe) were spotted by the owner
  reading a real file/sheet, not by a test — and each was turned into a test on the way out.
- **Conservative-by-construction.** Every re-opening path checks negation first; the reslot moves a doc
  only on a positive KWSP recognition; the model bump changes no existing ask until a slip is re-read.
  Nothing here can retroactively harm a live case.

## What Went Wrong

1. **The work was pushed but never sprint-closed** (symptom: 18 commits on `main`, CHANGELOG/retro/
   CLAUDE.md all still at 10 July, memory registry stale).
   **Root cause:** a multi-day remote-station stint has no natural "close" moment the way a single local
   sprint does — each fix was shipped the instant it was green, and the ceremony that normally rides the
   last commit never came.
   **Prevention:** a remote/multi-day stint ends with an explicit close pass (this document). Added as a
   lesson so a future remote stint schedules the close, not just the pushes.

2. **51, then a further set of, test fixtures encoded an impossible state** (`status='shortlisted'` +
   `profile_completed_at`), and failed the moment the stage-gates were tightened.
   **Root cause:** fixtures were hand-built to whatever a test needed, not to a state production can
   actually reach (verified 0 such rows live). They passed only because nothing had ever asserted the
   pairing was illegal.
   **Prevention:** the gates were tightened and the fixtures corrected (never the reverse). Lesson
   captured: a fixture is a claim about a reachable state — when a new gate fails a pile of fixtures at
   once, suspect the fixtures.

3. **The same check, hand-written twice, carried the same bug twice** — recurred *three* times this
   batch: `employer_number` (unemployment corroboration + implied-salary short-circuit), the EPF
   reference-name list (upload + re-extract paths), and the award-email `offer_emailed_at` stamp (fixed
   in the sibling command months ago, missed here).
   **Root cause:** a decision made in two places drifts; the second copy never learns the first's fix.
   **Prevention:** each was converged onto one shared definition (`epf_no_employer`, `reference_names`,
   the success-only stamp). This is the same class the 10 July `_can_review` role-drift bug taught —
   the lesson is reinforced, not new.

## Design Decisions

Logged to `docs/decisions.md`:
- Vircle confirmation is a CLAIM, not a verification (no back-channel from Vircle).
- The onboarding ask rides the award email (one email), not a separate follow-up.
- The payslip's KWSP line — not the occupation code — decides whether to ask for the EPF.
- Stage-gates gate only the CREATE branch; auto-resolve and answering open items run at every stage.

## Numbers

- **Scholarship pytest:** 2361 → **2409** (+48) — 2408 collected locally on close.
- **jest:** ~490 (unchanged; +2 for the reslot/email copy).
- **i18n parity:** 3261 → 3264 × en/ms/ta.
- **Migrations:** none across the whole batch.
- **Deploys:** each code commit built green; last live build `cdf2a44` (14 Jul). No re-deploy at close
  (docs + CLAUDE.md only; the CLAUDE.md edit triggers one no-op rebuild of already-live code).
- **Model version:** `salary_doc` 1.0.0 → **1.1.0** (marker-only; activates per-slip on next read).
