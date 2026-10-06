# Sprint 17 Retrospective — Outcome Tracking

**Date**: 2026-02-22
**Duration**: 1 session (combined with Sprint 16 deploy)

## What Was Built

- `AdmissionOutcome` model in `courses/models.py` — tracks student application outcomes per course+institution
- Migration 0009 (`add_admission_outcome`) applied to both local SQLite and Supabase
- Supabase: `admission_outcomes` table with RLS (5 policies: SELECT/INSERT/UPDATE/DELETE for user + service role)
- `OutcomeListView` (GET list, POST create) and `OutcomeDetailView` (PUT update, DELETE)
- 10 new tests covering CRUD, duplicate detection (409), auth enforcement, cross-user isolation
- Frontend: Outcome types + 4 API functions in `api.ts`
- Updated `/saved` page: "I Applied!" and "I Got an Offer!" buttons per course, "Track Applications" CTA
- New `/outcomes` page: lists outcomes with colour-coded status badges, inline status editing, delete
- 20 i18n keys × 3 locales (EN/BM/TA)

## What Went Well

- **Sprint 16 deployed in parallel**: While Cloud Run was building the Sprint 16 deploy, Sprint 17 backend was completed. Zero wasted time.
- **Clean test run**: All 10 new tests passed on first attempt. Full suite: 176 green.
- **Model kept in courses app**: Instead of creating a separate `apps/outcomes/` app (as originally planned), the model was added to `courses/models.py`. This avoided unnecessary boilerplate and kept related models together.
- **Frontend build passed first time**: No TypeScript errors. The outcomes page and saved page changes compiled cleanly.
- **Security advisor clean**: RLS policies applied correctly — only the known `django_migrations` warning remains.

## What Went Wrong

- Nothing significant. This was a clean sprint.

## Design Decisions

1. **Model in courses app, not separate app**: One model + 2 views doesn't warrant a whole Django app. Kept it simple.
2. **unique_together on [student, course, institution]**: Prevents duplicate outcomes for the same student-course-institution triple. Returns 409 on duplicates.
3. **GET_OR_CREATE for profile on outcome creation**: If a user creates an outcome before having a profile (edge case), the profile is auto-created.
4. **Optimistic UI for "I Applied!" button**: Button immediately shows success badge, catches 409 silently (duplicate is treated as success from user's perspective).
5. **Inline status editing on outcomes page**: Clicking "Update Status" reveals all status options as pill buttons. Simple, no modal needed.

## Numbers

| Metric | Value |
|--------|-------|
| Tests | 176 (+10 from Sprint 16's 166) |
| Golden master | 8280 (unchanged) |
| i18n keys added | 20 × 3 locales = 60 |
| New endpoints | 2 (GET/POST /outcomes/, PUT/DELETE /outcomes/<id>/) |
| New migration | 1 (0009) |
| New pages | 1 (/outcomes) |
| Files modified | ~10 |
| Deploy | Sprint 16 deployed (backend rev 21, frontend rev 17) |
