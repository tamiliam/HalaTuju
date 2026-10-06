# Retrospective — Review & submit flow (live‑testing refinements)

**Date:** 2026-06-07
**Commits:** `1cc5f65` → `a533637` (5 commits on `main`)
**Scope:** Frontend only. No backend change, no migration.
**Gates at close:** 758 scholarship + 1037 courses/reports pytest · 267 jest · next build clean · i18n parity 2084.

This sprint built out the previously‑PARKED **post‑consent summary + lock‑at‑Continue** item and polished it
through live testing on prod, with the user testing each deploy and feeding back.

## What Was Built

1. **Review is a post‑consent page, not a 6th navigable tab.** `NEXT_STEP_ORDER` reverts to the 5 wizard steps
   (quiz · story · funding · documents · consent). `ScholarshipReview` renders via a `reviewing` state reached only by
   the **"Review & submit"** CTA shown once all 5 steps are complete. Back returns to the steps; Submit on the review
   page is the only commit; `handleConfirm` then reloads into the post‑submit "received" screen.
2. **Consent step is read‑only once given.** The dead‑end Edit link is gone; the step now shows the **full consent text
   read‑only** plus who gave it and when (new `consent.givenHeading` / `givenMetaSelf` / `givenMetaGuardian`).
3. **Dynamic step counter** — "Step n of {total}" (was hardcoded "of 5").
4. **"What happens next" moved to the post‑submit "received" screen** (off the still‑to‑submit wizard). It now reads
   review → **email query** (Check 2 / reviewer may ask for more documents or clarification *by email* — please reply) →
   **may‑call** (kept as a "may") → decision by email. The doubled email note was de‑duped via `nav({email})`.
5. **Submit‑flow copy unified on "submit"** across the "all set" banner, the review subtitle (now with a scroll cue),
   and the button. The banner no longer says "submit for review" (it opens the student's own read‑back, not a third‑party
   review); the lock note was reworded so it no longer implies editing reopens after we contact them.
6. **De‑duped the doubled "Your application" title** on the Review page.

Plus two **prod data operations** on the test account (admin@tamilfoundation.org, app 16): deactivated the active
consent to see the read‑only→form transition, then fully reset (status → `shortlisted`, `profile_completed_at` → NULL,
active consents → 0) so the whole flow can be re‑tested. Audit consent rows preserved (deactivated, not deleted).

## What Went Well

- **Clean crash recovery.** The session had crashed mid‑gate‑run; the working tree was intact, so recovery was just
  re‑running the gates, committing, and pushing — no work lost.
- **Tight test‑on‑prod loop.** Small FE‑only deploys with the user testing each one surfaced real UX issues (duplicate
  title, redundant notices, misleading copy) fast.
- **i18n discipline held** — every copy change went through a UTF‑8 Python script (the Windows console can't encode
  Tamil), parity stayed exact across en/ms/ta at each step (2080 → 2083 → 2084).

## What Went Wrong

1. **Design churn: Review was built as a 6th tab, then reworked into a post‑consent page within the same release cycle.**
   *Symptom:* `NEXT_STEP_ORDER` gained `review`, then had it removed two days later; tests and the changelog had to be
   re‑edited.
   *Root cause:* the screen sequence (steps → review → received) was coded before the state‑machine was validated with the
   user; "review should only exist after consent" emerged from testing, not design.
   *Fix:* for any multi‑screen flow, agree the screen sequence / state transitions with the user **before** coding, not
   after the first build.

2. **Duplicate UI elements (the "Your application" title and the email note) shipped and were caught only in live
   testing.**
   *Symptom:* the Review page showed the page title twice; the received screen showed two near‑identical email notices.
   *Root cause:* content was added to a child (`ScholarshipReview`, the received‑screen box) without checking what the
   parent wrapper (`application/page.tsx`'s `wrap()` / `nav()`) already rendered.
   *Fix:* when adding a heading or standing notice to a component, grep the parent wrapper for the same element first —
   added to lessons.md.

3. **An interrupted build's `EXIT=1` could have been misread as a failure.**
   *Symptom:* the pre‑crash build log showed `EXIT=1` even though it had compiled.
   *Root cause:* the build was killed by the crash mid‑run; a non‑zero exit from a killed process isn't a compile failure.
   *Fix:* after a crash, always re‑run gates from clean rather than trusting a partial log — done here.

## Design Decisions

See `docs/decisions.md` — "Review as a post‑consent page (not a wizard tab, not an auto‑jump)".

## Numbers

- 5 commits, all FE‑only, no migration.
- i18n: +3 consent keys (`givenHeading`/`givenMetaSelf`/`givenMetaGuardian`), +1 `whatNext.step4`, reworded
  `allSetIntro` / `summary.subtitle` / `summary.lockNote`. Parity 2073 → 2084 across en/ms/ta.
- Tests: 267 jest throughout; backend pytest unchanged (758 scholarship + 1037 courses/reports).
- New debt: TD‑090 (`handleConfirm` full reload). Retired: TD‑088 (`formatNric` de‑dup) marked resolved.
