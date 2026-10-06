# Retrospective — Auth Flow Canonical Refactor

**Sprint:** Auth Flow Canonical Refactor
**Date:** 2026-03-20
**Duration:** ~1 session (plan + 8 tasks across 3 phases + hotfix)

---

## What Was Built

Refactored the entire frontend auth/routing flow so that **AuthProvider is the single routing authority**. Previously, multiple components independently read localStorage to determine user state — leading to stale cache bugs and race conditions. Now:

- `AuthProvider` holds `status: 'loading' | 'anonymous' | 'needs-nric' | 'ready'` and `profile: StudentProfile | null`
- All routing decisions read from context, never localStorage
- localStorage is a write-only performance cache (AuthProvider writes it as a side effect)
- Callback page reduced from complex profile-restore logic to ~20 lines
- `profile-restore.ts` deleted entirely
- AuthGateModal reads status/profile from context instead of calling `getProfile()`
- useOnboardingGuard reads AuthProvider instead of localStorage
- IC page, dashboard, saved, profile pages all use AuthProvider status
- STPM fields (`exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band`) added to TypeScript `StudentProfile` interface

**Commits:** 11 (feat + 6 refactors + 2 fixes + 1 chore + 1 docs)

---

## What Went Well

1. **Subagent-driven development worked smoothly** — 8 tasks dispatched to fresh subagents with spec + code quality review after each. Caught the STPM type gap during spec review that would have been a runtime bug.

2. **Phased approach (A/B/C) prevented breakage** — Phase A was backwards-compatible (added profile/status to AuthProvider without changing consumers). Phase B switched consumers. Phase C cleaned up. No intermediate state was broken.

3. **Advisor-driven plan updates** — Using Supabase Advisor to review the plan before execution caught 4 issues: phase structure, grep verification, pendingProfileRedirect pattern, and hasGrades check.

4. **Git worktree isolation** — Developed in `.worktrees/auth-canonical`, merged via fast-forward. Main branch stayed clean throughout.

---

## What Went Wrong

1. **Rules of Hooks crash in production**
   - **Symptom:** "Application error: a client-side exception has occurred" when opening the auth modal after deploy.
   - **Root cause:** The Task 5 subagent placed a `useEffect` (for `pendingProfileRedirect`) AFTER an early `return null` in AuthGateModal. When `authGateReason` changed from null to a value, React saw a different number of hooks and crashed. The subagent also left a duplicate useEffect after the early return.
   - **Fix:** Moved the useEffect before the early return, removed the duplicate. Committed as `ee8d802`.
   - **System change:** Added to lessons.md — React hook ordering must be verified when early returns exist. Spec reviewers should check hook placement relative to conditional returns.

2. **STPM type gap missed until spec review**
   - **Symptom:** `StudentProfile` TypeScript interface didn't include `stpm_grades`, `stpm_cgpa`, `muet_band`, `exam_type`. AuthProvider's cache didn't write STPM data.
   - **Root cause:** The implementation plan didn't account for STPM fields because the original profile interface pre-dated STPM support. The implementer subagent worked from the plan, which didn't mention these fields.
   - **Fix:** Added 4 fields to StudentProfile in api.ts, added STPM caching to AuthProvider.
   - **System change:** Plans that touch profile/auth should always cross-reference the full StudentProfile model fields (backend `models.py`) against the frontend type definition.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| AuthProvider as single routing authority | Eliminates stale-cache routing bugs; one place to reason about auth state |
| localStorage as write-only cache | Prevents the class of bugs where cached data diverges from server state |
| `pendingProfileRedirect` flag + useEffect | Avoids stale closure over `profile` in `finishAndClose`; useEffect sees fresh values |
| Status enum over boolean flags | `'loading' | 'anonymous' | 'needs-nric' | 'ready'` is exhaustive and self-documenting |

---

## Numbers

| Metric | Value |
|--------|-------|
| Files changed | 8 |
| Files deleted | 1 (`profile-restore.ts`) |
| Lines added (approx) | ~120 |
| Lines removed (approx) | ~150 |
| Backend tests | 966 (unchanged) |
| Frontend tests | 17 (unchanged) |
| Production incidents | 1 (Rules of Hooks — fixed within 1 commit) |
| Total commits | 11 |
