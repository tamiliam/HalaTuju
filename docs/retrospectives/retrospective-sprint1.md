# Sprint 1 Retrospective — Git Housekeeping + Auth Enforcement

**Date**: 2026-02-16
**Branch**: `feature/v1.1-stream-logic`
**Commit**: `729a92f`

## What Was Built

1. **Version control**: All project code (`halatuju_api/`, `halatuju-web/`, `tools/`) committed to git for the first time. Previously only the legacy Streamlit code was tracked.
2. **Auth enforcement**: `SavedCoursesView`, `SavedCourseDetailView`, `ProfileView` now require a valid Supabase JWT via `SupabaseIsAuthenticated` DRF permission class.
3. **Auth tests**: 11 tests covering rejection of anonymous requests (403), acceptance of authenticated requests (200), and public endpoints remaining open.
4. **Sprint roadmap**: 15-sprint migration plan across 4 phases, written and approved.
5. **Migration 0002**: Fixes table name mismatch (`student_profiles` -> `api_student_profiles`) and adds missing fields.

## What Went Well

- **Codebase exploration was thorough**: Three parallel Explore agents mapped out the entire backend, frontend, and data layer before any planning began. This avoided surprises during implementation.
- **DRF permission class is clean**: `SupabaseIsAuthenticated` is a one-liner that integrates naturally with DRF's permission system. No custom middleware hacks needed.
- **Tests are solid**: Mock-patching `jwt.decode` at the middleware level is a clean pattern that avoids needing a real JWT secret in tests.

## What Went Wrong

1. **`nul` file created by Windows redirect**: Using `2>nul` in bash commands on Windows created actual files named `nul`. Had to delete them manually. **Lesson**: Don't use Windows-specific redirects in Git Bash.

2. **403 vs 401 confusion**: Initially expected DRF to return 401 for unauthenticated requests. DRF returns 403 when `get_authenticate_header()` returns `None` (no `WWW-Authenticate` header configured). Wasted time debugging before reading the DRF source. **Lesson**: DRF's 403-vs-401 behaviour is documented but non-obvious. Our tests now document this explicitly.

3. **Middleware `jwt_secret` set at init time**: `SupabaseAuthMiddleware.__init__` reads `settings.SUPABASE_JWT_SECRET` once at startup. `@override_settings` in tests doesn't affect it because the middleware is already instantiated. Had to patch `jwt.decode` directly instead. **Lesson**: Django middleware initialises once — don't try to override settings that were read at init time.

4. **Missing migration for table rename**: Model had `db_table = 'api_student_profiles'` but migration 0001 created `student_profiles`. This only surfaced when authenticated tests tried to query the table. **Lesson**: Always run `makemigrations` after reading models to check for drift.

5. **Git identity not configured**: First commit failed because `user.name` and `user.email` weren't set in the repo. **Lesson**: Set git identity as the first step of any new project setup.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| DRF permission class over decorator | Works natively with class-based views, consistent with DRF patterns |
| Keep `require_auth` decorator | Still useful for any future function-based views |
| Expect 403 not 401 | DRF standard when no WWW-Authenticate header; documented in tests |
| Patch `jwt.decode` not the middleware attribute | Middleware init is one-time; patching decode is more reliable |
| Eligibility stays public | Guest access by design — users shouldn't need to sign in to check eligibility |

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests | 42 | 53 |
| Golden master | 8280 | 8280 |
| Files tracked in git | ~30 (Streamlit only) | 79+ (full project) |
| Auth-protected endpoints | 0 | 5 (3 views) |

## Next Steps

Sprint 2: Saved Courses Fix + Missing Page Shells
- Fix `unsaveCourse` DELETE in frontend
- Wire dashboard saved state to API
- Create 6 shell pages
- Add saved course API tests
