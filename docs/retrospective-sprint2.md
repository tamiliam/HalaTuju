# Sprint 2 Retrospective — Saved Courses Fix + Page Shells

**Date**: 2026-02-16
**Branch**: `feature/v1.1-stream-logic`

## What Was Built

1. **Fixed `unsaveCourse` API call**: Changed from body-based DELETE to URL-based DELETE (`/api/v1/saved-courses/<course_id>/`), matching the backend route.
2. **Dashboard bookmark button**: Logged-in users now see a save/unsave icon on each course card with optimistic UI updates and rollback on failure.
3. **Saved courses page** (`/saved`): Full functional page — lists saved courses from API, remove button, login prompt for guests.
4. **Settings page** (`/settings`): Navigation hub linking to edit grades, saved courses, about, privacy, terms.
5. **About page** (`/about`): Project description and mission.
6. **Privacy policy** (`/privacy`): Data collection, usage, and storage disclosure.
7. **Terms of service** (`/terms`): Disclaimer and liability.
8. **Auth callback** (`/auth/callback`): Handles OAuth redirect from Supabase, redirects to dashboard.
9. **3 saved course API tests**: Save (201), list (appears), delete (removed).

## What Went Well

- **Clean sprint scope**: All deliverables were well-defined in the roadmap. No surprises, no scope creep.
- **Optimistic updates pattern**: The save/unsave button updates instantly and reverts on API failure. Good UX pattern to reuse in future sprints.
- **No backend changes needed**: The saved course API was already correct — only the frontend call was wrong. This confirms the backend was well-built in the initial migration.
- **Tests passed first try**: All 56 tests passed on the first run. The mock-patching `jwt.decode` pattern from Sprint 1 worked cleanly for the new saved course tests.

## What Went Wrong

1. **Wrong GCP account active**: Deploy failed because `admin@myskills.org.my` was the active account instead of `tamiliam@gmail.com`. Had to `gcloud config set account` before deploying. **Lesson**: Added account name to CLAUDE.md next to the GCP project ID so this is always visible.

2. **`getSavedCourses` return type was wrong**: The frontend type said `string[]` but the backend returns full `Course` objects. Caught during implementation, not from a test. **Lesson**: Type mismatches between frontend and backend are invisible until runtime. A future sprint should consider generating types from the API schema.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Optimistic save/unsave | Better UX — instant feedback, revert on failure. No loading spinner needed. |
| Save button only when logged in | No session = no save API to call. Button is simply not rendered. |
| CourseCard split into div+link | Needed separate click targets for save button vs course detail link. A single `<Link>` wrapper would navigate on save click. |
| `/saved` page is functional, not a shell | The page needs real API calls to be useful. A static shell would be misleading. |
| Static about/privacy/terms pages | Content is simple text — no need for CMS or dynamic content at this stage. |

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests | 53 | 56 |
| Golden master | 8280 | 8280 |
| Frontend pages | 7 | 13 (+6) |
| Frontend deploy revision | 00006 | 00007 |

## Next Steps

Sprint 3: Quiz API Backend
- Port `src/quiz_data.py` → `halatuju_api/apps/courses/quiz_data.py`
- Port `src/quiz_manager.py` → `halatuju_api/apps/courses/quiz_engine.py`
- New endpoints: `POST /api/v1/quiz/questions/`, `POST /api/v1/quiz/submit/`
- 8-10 tests (signal accumulation, taxonomy mapping, edge cases)
