# Retrospective — B40 Assistance Programme, Phase 1 Sprint 4a

**Date:** 2026-05-21
**Sprint goal:** Funding need + deeper info + completeness (the backend half of Sprint 4).
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `FundingNeed` model (OneToOne → application, computed `total`) + deeper-info fields
  (`aspirations`, `plans`, `fears`, `justification`) on `ScholarshipApplication`.
- `PATCH` details endpoint (own, shortlisted-only); `funding_need` + `completeness` on the read
  serializer.
- `application_completeness()` + `save_application_details()` services. Migration 0003. RLS appended.

## What Went Well
- Splitting Sprint 4 into 4a (backend) / 4b (frontend) kept this session focused (~7 files) and
  gave the frontend a stable `completeness` contract to build against.
- Reusing the established patterns (HS256-token tests, OneToOne upsert, computed property) meant
  53 scholarship + 1059 backend tests went green on the first full run.

## What Went Wrong
- **Symptom:** I nearly used `getattr(app, 'funding_need', None)` to handle a possibly-absent
  reverse OneToOne.
- **Root cause:** Django's `RelatedObjectDoesNotExist` is **not** an `AttributeError`, so
  `getattr`'s default never fires — the access raises.
- **System change:** `lessons.md` entry — access an optional reverse OneToOne with
  `try/except Model.DoesNotExist`, never `getattr(..., None)`.

## Design Decisions (logged in `docs/decisions.md`)
- `FundingNeed` as a separate OneToOne model with a computed `total` (vs a JSON blob).

## Numbers
- ~7 files. Tests: 11 new; backend suite **1059 pass**. Golden masters unchanged.
