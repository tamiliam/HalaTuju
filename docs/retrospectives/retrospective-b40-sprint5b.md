# Retrospective — B40 Assistance Programme, Phase 1 Sprint 5b

**Date:** 2026-05-22
**Sprint goal:** Document upload + referee + consent UI (frontend) — completes Sprint 5.
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `ScholarshipDocuments` (sign → PUT → record + list/delete), `ScholarshipReferee`,
  `ScholarshipConsent` (guardian fields for minors) — wired as next-steps steps 4–6.
- `api.ts`: 10 client functions + types; `scholarship.ts` `DOC_TYPES` + `formatFileSize`.
- EN/MS/TA i18n.

## What Went Well
- Three small focused components kept `ScholarshipNextSteps` a thin orchestrator.
- The signed-URL upload (sign → PUT direct to Storage → record) keeps file bytes off our API and
  reuses the 5a endpoints cleanly.
- Extracting `DOC_TYPES` + `formatFileSize` gave the only pure logic a unit test under node-env Jest.

## What Went Wrong
- Nothing significant. As expected, most of the sprint is UI + network glue with no DOM-render tests
  possible (node-env Jest), so verification is compile + i18n + the two helper tests.

## What's Not Verified
- The upload PUT-to-Storage + consent round-trip (needs the live `b40-documents` bucket — deploy
  carry-forward, same as the apply OAuth flow).

## Numbers
- ~9 files. Tests: 2 new; frontend suite **37 pass**. i18n **856 keys × 3**. `next build` OK.
