# Retrospective — B40 Assistance Programme, Phase 1 Sprint 4b

**Date:** 2026-05-21
**Sprint goal:** Post-shortlist next-steps flow (frontend) — completes Sprint 4.
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `ScholarshipNextSteps` component — 3-step checklist from the `completeness` block; quiz gate
  links to the existing `/quiz`; about-you + funding-need form with a live total → PATCH.
- `scholarship.ts` helpers (`fundingTotal`, `buildDetailsPayload`, `applicationToDetailsForm`).
- `api.ts`: extended `ScholarshipApplication` type + `updateScholarshipDetails` PATCH.
- Apply page routes shortlisted → next-steps. EN/MS/TA i18n.

## What Went Well
- The component owns its own application-state copy and refreshes it from the PATCH response, so
  the checklist updates without any page-level state juggling.
- Reusing `/quiz` for the gate meant zero new quiz code; the `completeness` contract from 4a made
  the checklist a thin renderer.
- All three gates (check-i18n, jest, `next build`) green; the pure-helper tests covered the logic.

## What Went Wrong
- Minor: editing the three message files again required re-reading them first (the Edit-needs-Read
  rule). Already captured as the Sprint 2/3 process note — no new lesson.

## What's Not Verified
- PATCH round-trip + quiz-then-return flow not exercised against a live backend (browser smoke test
  before Phase 1 ships).

## Numbers
- ~8 files. Tests: 5 new; frontend suite **35 pass**. i18n **819 keys × 3**. `next build` OK.
