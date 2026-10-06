# Retrospective — B40 Assistance Programme, Phase 1 Sprint 6a

**Date:** 2026-05-22
**Sprint goal:** AI sponsor-profile drafting + MyNadi admin API (backend half of the final sprint).
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `SponsorProfile` model (draft/edited markdown + status; migration 0005, RLS).
- `profile_engine.py`: Gemini-cascade sponsor-profile drafting from application data.
- Admin API (list / detail / generate / edit / publish) reusing `PartnerAdminMixin`.

## What Went Well
- Reusing `PartnerAdminMixin` meant the admin endpoints needed no new auth — super-admin access and
  the UID/email lookup + backfill came for free.
- Mirroring `report_engine`'s Gemini cascade kept the profile engine consistent and mockable; tests
  patch `generate_sponsor_profile` at the view boundary.
- 80 scholarship + 1086 backend tests green first run.

## What Went Wrong
- Nothing significant. Gemini draft quality is only verifiable with a real API call (mocked in
  tests) — a known AI gap, surfaced via the admin's edit-before-publish step rather than auto-publish.

## Design Decisions (logged in `docs/decisions.md`)
- AI-draft → admin-edit → publish workflow (draft/edited separation; regenerate reverts published).

## Numbers
- ~9 files. Tests: 9 new; backend suite **1086 pass**. Golden masters unchanged.
