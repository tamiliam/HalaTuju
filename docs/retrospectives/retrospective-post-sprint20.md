# Post-Sprint 20 Retrospective — Polish + Course Search + Deploy Fix

**Date**: 2026-02-25
**Goal**: Ship post-S20 UI polish, course search page, and fix stale deployment.

## What Was Built

- **Profile page polish** (v1.22.4): Replaced emoji icons with inline SVGs, renamed "Non-Malaysian" to "Foreign"
- **Course search/explorer** (v1.23.0): `/search` page with text search, 4 filters (type, level, state, field), eligible-only toggle, 10 backend tests
- **Top matches UX**: Changed from 5 to 6, load-more in batches of 6
- **Default sort fix**: Sort by credential → institution type → merit → name
- **Deploy fix** (v1.23.1): Suspense boundary for `useSearchParams()`, migrated from stale gcr.io to Artifact Registry

## What Went Well

- Course search shipped cleanly — backend endpoint + frontend page + i18n in one pass
- State filter population bug caught and fixed same session (search filters preserved on back-navigation)
- 10 new backend tests for search endpoint covering all filter combinations

## What Went Wrong

1. **Stale gcr.io image deployed**: A previous failed deployment pushed a stale image to `gcr.io` (old Container Registry). When Cloud Run was later pointed at `gcr.io`, it served that stale image. The fix was to always deploy from source (`--source .`) which uses Artifact Registry (`asia-southeast1-docker.pkg.dev`).

2. **Next.js Suspense boundary missing**: The `/search` page used `useSearchParams()` at the top level without a `<Suspense>` wrapper. Next.js 14 requires this for static generation/prerendering. The build failed during Cloud Run deploy with: `useSearchParams() should be wrapped in a suspense boundary at page "/search"`. Fixed by splitting into `SearchPage` (with Suspense) and `SearchPageInner` (with the hook).

3. **Agent crash during diagnosis**: A Claude Code agent investigating the stale deployment crashed with exit code 3221226505 (STATUS_STACK_BUFFER_OVERRUN). The diagnosis was correct but the fix wasn't applied before the crash. Required manual continuation in a new session.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Suspense wrapper pattern | Next.js 14 requires `<Suspense>` around `useSearchParams()` for prerendering. Pattern: export a wrapper component, put the real logic in an inner component. |
| Deploy from `--source .` always | Never use `--image gcr.io/...` — gcr.io may contain stale images from failed builds. Source deploys use Artifact Registry. |
| Client-side eligible filter | Eligible IDs from localStorage filtered client-side rather than server-side — avoids sending 200+ IDs in query params. |
| 200 course limit on search | Fetch up to 200 courses per search, paginate client-side in batches of 6. Keeps API simple, search data is small enough. |

## Numbers

| Metric | Value |
|--------|-------|
| CHANGELOG entries | 5 (v1.22.1 → v1.23.1) |
| New backend tests | 10 (search endpoint) |
| Total backend tests | 173 passing + 13 pre-existing failures |
| Golden master | 8280 (unchanged) |
| Frontend rev | 33 → 35 |
| Backend rev | 30 (unchanged) |
| Deploys | 2 (1 failed Suspense, 1 successful) |
