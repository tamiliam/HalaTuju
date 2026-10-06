# Retrospective — NRIC Hard Gate Sprint (2026-03-20)

## What Was Built

Implemented NRIC as the hard identity gate for HalaTuju. No Supabase account or Django profile is created until a student's NRIC is verified. This closes the loophole where students could save courses and access protected features without providing NRIC.

### Key Components
1. **Backend middleware** (`NricGateMiddleware`) — blocks all non-anonymous authenticated users without NRIC from protected endpoints
2. **Supabase anonymous sign-in** — students browse with anonymous JWT, no permanent account created
3. **AuthGateModal rewrite** — 3-step flow (login → otp → ic) using `linkIdentity()` for Google and `claimNric()` for NRIC
4. **Auth context overhaul** — `isAuthenticated` redefined from "has session" to "has NRIC"
5. **RLS policies** — 5 restrictive policies blocking anonymous users from student data tables
6. **Orphan cleanup** — 16 users without NRIC deleted from production

## What Went Well

- **Subagent-driven development** worked efficiently — 14 tasks dispatched to fresh subagents with two at a time (where independent), keeping context clean
- **Middleware approach** (user's insistence on hard gate vs endpoint-by-endpoint) was the right call — one enforcement point instead of checking NRIC everywhere
- **Test suite stability** — only 31 tests needed NRIC added to fixtures after middleware was introduced, all fixed in one pass
- **Frontend build caught a bug** — `showAuthGate` used before declaration, caught by TypeScript compilation, fixed immediately

## What Went Wrong

1. **Subagent placed `useEffect` before callback declaration**
   - Symptom: Frontend build failed — `showAuthGate` used before its `useCallback` declaration
   - Root cause: Task 11 subagent added a `useEffect` referencing `showAuthGate` above where `showAuthGate` was defined. JavaScript block scoping (`const`) doesn't allow this.
   - Fix: Moved the `useEffect` after the callback definitions. System change: always verify frontend builds after subagent work on TSX files.

2. **Commit `df412ed` not in the plan**
   - Symptom: A commit "unify course display limit to 9, sort explore filters" appeared in the branch that wasn't part of the NRIC gate plan
   - Root cause: A subagent made an unrelated change while working on a task. Context pollution from unscoped instructions.
   - Fix: Review each subagent commit diff before marking task complete. For future sprints, use `--stat` on each commit.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Middleware over per-endpoint checks | Single enforcement point; new endpoints are automatically protected |
| Anonymous sign-in over no-session browsing | Provides JWT for API calls without creating permanent accounts |
| `linkIdentity()` before `signInWithOAuth()` | Attaches Google to anonymous user (same user ID, no orphan) — falls back to normal sign-in for existing Google users |
| `isAuthenticated` = has NRIC | All existing auth gate triggers work without modification — `!isAuthenticated` still means "show gate" |
| Restrictive RLS policies | RESTRICTIVE + PERMISSIVE = AND logic — anonymous users blocked even if they somehow bypass middleware |

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 948 | 958 (+10) |
| Frontend build | Pass | Pass |
| Golden masters | SPM 5319, STPM 2026 | Unchanged |
| Orphan users | 16 | 0 |
| Auth gate steps | 4 (login→otp→ic→profile) | 3 (login→otp→ic) |
| `get_or_create` leak points | 5 | 2 (whitelisted only) |
| RLS restrictive policies | 0 | 5 |
