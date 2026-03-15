# Retrospective — Tech Debt Quick Wins Sprint (2026-03-15)

## What Was Built

Resolved 4 low-risk tech debt items:
- **TD-027**: Removed dead `LEGACY_KEY_MAP` from engine.py
- **TD-030**: Updated stale model docstrings (CSV references → Supabase table names)
- **TD-037**: Deleted `db.sqlite3` from working directory
- **TD-049**: Removed `as any` type assertion, properly typed profile page state vars

## What Went Well

- All 4 items completed in a single pass with zero test regressions
- TD-049 fix also caught and fixed two pre-existing TypeScript errors (gender/nationality state vars typed as `string` instead of literal unions) — the `as any` had been masking them
- Minimal scope, minimal risk — exactly the right sprint for end-of-day cleanup

## What Went Wrong

- **`as any` removal exposed hidden type errors**: Removing `as any` from the profile page revealed that `gender` and `nationality` state vars were typed as plain `string`, not their literal union types. The `as any` was silently masking multiple type safety violations, not just the colorblind/disability one.
  - **Root cause**: The original `as any` was a shotgun fix that papered over several distinct type mismatches at once.
  - **System change**: When encountering `as any` in future, check what types it's masking before removing — the fix may need to address multiple underlying issues, not just one.

## Design Decisions

No architectural decisions made — all changes were mechanical cleanup.

## Numbers

| Metric | Value |
|--------|-------|
| Backend tests | 425 pass, 0 fail |
| TypeScript | 0 errors |
| Files changed | 5 (engine.py, models.py, api.ts, profile/page.tsx, technical-debt.md) |
| Tech debt resolved | 4 items (TD-027, TD-030, TD-037, TD-049) |
| Total resolved | 25/52 |
| Duration | ~15 minutes |
