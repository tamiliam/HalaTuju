# Retrospective — Bug Fixes & Auth Gating (2026-03-15)

## What Was Built
- Centralised localStorage key management (storage.ts)
- Auth gating for anon users: My Profile, Load More, profile page
- Saved courses UX: status toggle fix, institution names, course IDs
- Next.js error boundary pages (error, loading, 404)
- Removed "No sign-ups" tagline (sign-up now required for key features)

## What Went Well
- Recovered cleanly from a crashed session — 19 modified + 4 new files were uncommitted but complete and consistent
- All changes were purely additive — no regressions, TypeScript compiled clean, 424 backend tests passing
- Auth gating reused existing `showAuthGate` pattern — no new infrastructure needed

## What Went Wrong
- Nothing significant. Small scope, clean execution.

## Numbers
- Files changed: 26 (commit 1) + 9 (commit 2)
- Backend tests: 424 passing
- i18n keys added: 8 (error/loading/not-found pages) + 6 (auth gate reasons)
- localStorage constants centralised: 22
