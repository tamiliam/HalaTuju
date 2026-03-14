# Retrospective — API Consistency Sprint (2026-03-14)

## What Was Built

Two tech debt items resolved to improve API consistency:

1. **TD-004: DRF status constants** — Replaced raw integer status codes (`400`, `201`, `404`) with DRF constants (`status.HTTP_400_BAD_REQUEST`, etc.) in `SavedCoursesView` and `SavedCourseDetailView`.

2. **TD-011: 401 instead of 403 for unauthenticated requests** — Added `SupabaseAuthentication` DRF authentication class that provides `WWW-Authenticate: Bearer` header. DRF now correctly returns 401 Unauthorized (not 403 Forbidden) for unauthenticated requests, per RFC 7235.

TD-005, TD-006, and TD-026 were deferred as they require coordinated frontend changes.

## What Went Well

- The DRF authentication class approach is the canonical solution — not a workaround. It follows the same pattern as DRF's built-in `TokenAuthentication` and third-party `JWTAuthentication`.
- Test count increased from 382 to 387 (5 tests that previously asserted 403 now correctly assert 401 and pass, plus new auth tests picking up the change).

## What Went Wrong

1. **Initial approach for TD-011 didn't work.** Changed `SupabaseIsAuthenticated.has_permission()` to raise `NotAuthenticated` exception instead of returning `False`. Expected DRF to return 401, but it returned 403.
   - **Root cause:** DRF's `APIView.permission_denied()` only returns 401 when at least one authenticator provides a `WWW-Authenticate` header via `authenticate_header()`. Without any DRF authenticators registered, `NotAuthenticated` exceptions become 403.
   - **Fix:** Added `SupabaseAuthentication` class with `authenticate_header()` returning `'Bearer'`, registered in `DEFAULT_AUTHENTICATION_CLASSES`. This is the framework's intended mechanism.

## Design Decisions

- `SupabaseAuthentication.authenticate()` returns `None` (doesn't perform auth) — actual authentication is handled by the Django middleware (`SupabaseAuthMiddleware`). The DRF class exists solely to provide the `WWW-Authenticate` header.
- Auth tests (`test_auth.py`, `test_outcomes.py`) updated to expect 401 instead of 403 for unauthenticated requests.

## Numbers

- Tests: 387 pass, 0 fail, 0 skip (+5 from previous sprint)
- Tech debt resolved: 2 (TD-004, TD-011)
- Total resolved: 15/52
- Files changed: 5 (`views.py`, `supabase_auth.py`, `base.py`, `test_auth.py`, `test_outcomes.py`)
