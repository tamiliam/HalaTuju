# Retrospective — B40 Assistance Programme, Phase 1 Sprint 2

**Date:** 2026-05-21
**Sprint goal:** Native application form + single front door (frontend), wired to the Sprint 1 API.
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `/scholarship/apply` page — trilingual, status-gated (loading → sign-in gate → form →
  success/already-applied), pre-filled from the AuthProvider profile.
- `src/lib/scholarship.ts` — pure helpers (`countAGrades`, `profileToApplyDefaults`,
  `buildApplicationPayload`, `applyFormError`) + 13 tests.
- API client: `submitScholarshipApplication`, `getMyScholarshipApplications`.
- New `'apply'` AuthGateReason reusing the Google sign-in + NRIC-claim flow.
- "B40 Aid" header nav link; full EN/MS/TA i18n.

## What Went Well
- Putting all logic in a pure module made testing trivial under the project's **node-env** Jest —
  no component-rendering harness needed (mirrors the existing `ic-utils` pattern).
- Reusing the AuthProvider/AuthGateModal/NRIC machinery meant the front door needed only a small,
  contained extension (one new reason), not a parallel auth path.
- The three gates (check-i18n, jest, `next build`) caught everything at compile time; no rework.

## What Went Wrong
- **Symptom:** my first attempt to edit the three message files failed — the Edit tool requires a
  file to have been Read in-session, and I had only grepped them.
- **Root cause:** I treated a Grep hit as equivalent to having opened the file.
- **System change:** when editing files I've only searched, Read the target region first. (Process
  note for this agent — not a codebase lesson.)

## Design Decisions (logged in `docs/decisions.md`)
- New `'apply'` AuthGateReason extending the shared auth flow (vs a parallel auth path).
- Lightweight self-reported academics in the apply form (vs forcing full grades onboarding).

## What's Not Verified
- The OAuth redirect-and-return-to-apply round trip was implemented and type-checks/builds, but was
  **not** exercised against a live Supabase/backend this session. Manual smoke test needed before
  Phase 1 ships.

## Numbers
- ~10 files (1 page, 1 lib, 1 test; edits to api, auth-context, AuthGateModal, AppHeader, 3 i18n).
- Tests: 13 new; frontend suite **30 pass**. i18n **793 keys × 3**. `next build` OK.
