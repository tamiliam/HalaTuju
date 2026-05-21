# Retrospective — B40 Assistance Programme, Phase 1 Sprint 5a

**Date:** 2026-05-22
**Sprint goal:** Document vault + referee + e-consent (the backend half of Sprint 5).
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `ApplicantDocument` / `Referee` / `Consent` models (migration 0004, RLS).
- `storage.py`: signed upload/download URLs (private bucket, stdlib `urllib`, service key, mockable).
- Endpoints: documents (sign-upload / list / record / delete), referees, consent.
- Consent guardian gate: a minor (age from NRIC) needs a guardian; versioned + superseding.

## What Went Well
- Using stdlib `urllib` for the Storage REST calls avoided adding a dependency and kept the module
  always-importable, so tests just mock the two functions.
- Keeping file bytes off Django (signed-URL direct upload) sidesteps Cloud Run request-size/memory
  limits and is the right private-storage pattern.
- 71 scholarship + 1077 backend tests green first run; the guardian gate is fully unit-covered.

## What Went Wrong
- Nothing significant. The storage layer can't be integration-tested locally (no bucket), so its
  real behaviour is verified only at deploy — a known external-dependency gap, mitigated by mocking
  + a 503 fallback when storage is unavailable.

## Design Decisions (logged in `docs/decisions.md`)
- Signed-URL direct-to-Supabase storage via stdlib `urllib` (file bytes never through Django).
- Versioned, guardian-gated consent keyed on NRIC-derived age.

## What's Not Verified
- Live storage round-trip (needs the `b40-documents` bucket — deploy carry-forward).

## Numbers
- ~10 files. Tests: 18 new; backend suite **1077 pass**. Golden masters unchanged.
