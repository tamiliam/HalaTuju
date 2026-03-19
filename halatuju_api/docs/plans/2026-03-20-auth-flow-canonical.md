# Auth Flow Canonical Refactor — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make AuthProvider the single routing authority so that navigation decisions depend on API-fetched state, not localStorage.

**Architecture:** AuthProvider fetches the student profile once, holds it in React state, and exposes a `status` field (`'loading' | 'anonymous' | 'needs-nric' | 'ready'`) that all routing logic reads. localStorage remains as a write-only cache for fast rendering on subsequent loads. The callback page, AuthGateModal, and useOnboardingGuard all read from AuthProvider instead of localStorage. No new dependencies.

**Tech Stack:** Next.js 15, React 18, Supabase Auth, TypeScript

---

## Context

### The problem

Routing decisions (dashboard vs onboarding vs IC page) currently read localStorage to check if grades exist. On a fresh browser, localStorage is empty — even for returning users with a full profile in the database. Every auth entry path must remember to populate localStorage before routing checks run. When one forgets, the user gets sent to the wrong page.

### What this plan fixes

1. AuthProvider fetches profile once, holds it in state, exposes `status` + `profile`
2. Routing reads AuthProvider state, not localStorage
3. Callback page becomes minimal — establishes session, redirects, lets AuthProvider handle the rest
4. AuthGateModal stops fetching profile independently — reads from context
5. `useOnboardingGuard` waits for AuthProvider to resolve instead of reading localStorage synchronously
6. `profile-restore.ts` is deleted — AuthProvider writes localStorage as a side effect

### What this plan does NOT touch

- Dashboard's localStorage reads for building API payloads (rendering, not routing)
- Onboarding pages reading localStorage to pre-fill forms
- Quiz/search pages reading localStorage for grades — these are rendering concerns, not routing
- Backend code — no changes needed

### Files inventory

| File | Change | Purpose |
|------|--------|---------|
| `src/lib/auth-context.tsx` | Major modify | Add `profile` state, `status` field, cache side effect |
| `src/lib/profile-restore.ts` | Delete | Replaced by AuthProvider side effect |
| `src/app/auth/callback/page.tsx` | Simplify | Remove profile fetch, just establish session + redirect |
| `src/components/AuthGateModal.tsx` | Modify | Read `status`/`profile` from context, remove `getProfile` calls |
| `src/lib/useOnboardingGuard.ts` | Rewrite | Read `status`/`profile` from context, return loading state |
| `src/app/dashboard/page.tsx` | Minor modify | Use new guard API (handles loading state) |
| `src/app/onboarding/ic/page.tsx` | Minor modify | Read `status` from context instead of `isAnonymous` + localStorage |
| `src/app/search/page.tsx` | Minor modify | Use new guard API |

---

## Phase A: Backwards-Compatible Foundation (Tasks 1–4)

> Tasks 1–4 add new fields to AuthProvider and update consumers. All existing behaviour is preserved — old fields (`isAuthenticated`, `isAnonymous`, `hasSession`) still work. Safe to deploy independently. If anything goes wrong, revert Phase A only.

### Task 1: Extend AuthProvider — add `profile` state and `status` field

**Files:**
- Modify: `halatuju-web/src/lib/auth-context.tsx`

**Step 1: Update the AuthContextValue interface**

Replace the current interface with:

```typescript
export type AuthStatus = 'loading' | 'anonymous' | 'needs-nric' | 'ready'

interface AuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean          // keep for backwards compat during migration
  isAuthenticated: boolean    // keep: true when status === 'ready'
  isAnonymous: boolean
  hasSession: boolean
  status: AuthStatus          // NEW: the single routing authority
  profile: StudentProfile | null  // NEW: full profile in memory

  // Auth gate (unchanged)
  authGateReason: AuthGateReason
  authGateCourseId: string | null
  showAuthGate: (reason: NonNullable<AuthGateReason>, options?: AuthGateOptions) => void
  hideAuthGate: () => void
}
```

Where `StudentProfile` is imported from `@/lib/api` (it already exists there).

**Step 2: Add profile state and derive status**

In `AuthProvider`, add:

```typescript
const [profile, setProfile] = useState<StudentProfile | null>(null)
```

Replace the `getProfile` calls (lines 58-62, 91-95) that currently only extract `!!profile.nric`. Instead, store the full profile:

```typescript
// In the init useEffect, after session is established:
if (session?.access_token && !session.user?.is_anonymous) {
  getProfile({ token: session.access_token }).then(p => {
    setProfile(p)
    setHasIdentity(!!p.nric)
  }).catch(() => {
    setProfile(null)
    setHasIdentity(false)
  })
}
```

Same pattern in the `onAuthStateChange` handler for `SIGNED_IN`.

Derive `status`:

```typescript
const status: AuthStatus = isLoading
  ? 'loading'
  : isAnonymous
    ? 'anonymous'
    : hasIdentity
      ? 'ready'
      : 'needs-nric'
```

**Step 3: Add localStorage cache side effect**

Replace the `restoreProfileToLocalStorage` import and calls with a side effect:

```typescript
// Write profile to localStorage as a cache (side effect, not routing)
useEffect(() => {
  if (!profile) return
  if (profile.grades && Object.keys(profile.grades).length > 0) {
    localStorage.setItem(KEY_GRADES, JSON.stringify(profile.grades))
  }
  const demo: Record<string, unknown> = {}
  if (profile.gender) demo.gender = profile.gender
  if (profile.nationality) demo.nationality = profile.nationality
  if (profile.colorblind != null) demo.colorblind = profile.colorblind
  if (profile.disability != null) demo.disability = profile.disability
  if (Object.keys(demo).length > 0) {
    localStorage.setItem(KEY_PROFILE, JSON.stringify(demo))
  }
  if (profile.student_signals) {
    localStorage.setItem(KEY_QUIZ_SIGNALS, JSON.stringify(profile.student_signals))
  }
}, [profile])
```

**Step 4: Remove the `restoreProfileToLocalStorage` import**

Remove `import { restoreProfileToLocalStorage } from '@/lib/profile-restore'` and the two inline calls to it.

Import `KEY_GRADES, KEY_PROFILE, KEY_QUIZ_SIGNALS` from `@/lib/storage` (re-add them since profile-restore was providing them indirectly).

**Step 5: Remove the pending auth action recovery (with verification)**

Lines 67-81 in the current code read `KEY_PENDING_AUTH_ACTION` from localStorage and re-open the auth gate. This was needed when the callback page deferred to the AuthProvider to re-open the gate. With the new design, the callback handles everything — remove this block.

**Before deleting**, verify no other code depends on this mechanism:

```bash
grep -rn "KEY_PENDING_AUTH_ACTION\|pending.auth.action\|pendingAuthAction" halatuju-web/src/
```

Expected: Only hits in `auth-context.tsx` (the block being removed) and `callback/page.tsx` (which clears it). If any other file reads this key, update it first.

**Step 6: Expose new fields in the context value**

```typescript
const value: AuthContextValue = {
  session,
  token: session?.access_token ?? null,
  isLoading,
  isAuthenticated: hasIdentity,
  isAnonymous,
  hasSession: !!session,
  status,           // NEW
  profile,          // NEW
  authGateReason,
  authGateCourseId,
  showAuthGate,
  hideAuthGate,
}
```

**Step 7: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes with no errors.

**Step 8: Commit**

```bash
git add halatuju-web/src/lib/auth-context.tsx
git commit -m "feat: add profile state and status field to AuthProvider"
```

---

### Task 2: Rewrite useOnboardingGuard to read AuthProvider

**Files:**
- Modify: `halatuju-web/src/lib/useOnboardingGuard.ts`

**Step 1: Rewrite the guard**

Replace the entire file:

```typescript
import { useAuth } from '@/lib/auth-context'

/**
 * Guards pages that require a completed profile with grades.
 * Reads from AuthProvider state — never from localStorage.
 *
 * Returns:
 * - { ready: false, loading: true } — AuthProvider still resolving
 * - { ready: false, loading: false } — no grades, caller should redirect
 * - { ready: true, loading: false } — grades present, page can render
 */
export function useOnboardingGuard() {
  const { status, profile } = useAuth()

  if (status === 'loading') {
    return { ready: false, loading: true }
  }

  if (status !== 'ready') {
    return { ready: false, loading: false }
  }

  const hasGrades = profile?.grades && Object.keys(profile.grades).length > 0
  const hasStpmGrades = profile?.stpm_grades && Object.keys(profile.stpm_grades).length > 0

  return { ready: !!(hasGrades || hasStpmGrades), loading: false }
}
```

Note: The guard no longer calls `router.replace()` itself. The caller decides what to do. This is cleaner — the guard reports state, the page acts on it.

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes. Dashboard and search pages use `{ ready: onboarded }` — they'll need updating in Task 4.

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/useOnboardingGuard.ts
git commit -m "refactor: useOnboardingGuard reads AuthProvider, not localStorage"
```

---

### Task 3: Simplify auth callback page

**Files:**
- Modify: `halatuju-web/src/app/auth/callback/page.tsx`

**Step 1: Rewrite the callback**

Replace the entire file:

```typescript
'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { KEY_PENDING_AUTH_ACTION } from '@/lib/storage'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      // Small delay to let Supabase process the OAuth callback
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }

      // Clear pending auth action — AuthProvider handles the rest
      localStorage.removeItem(KEY_PENDING_AUTH_ACTION)

      // Always go to dashboard. AuthProvider will:
      // 1. Detect the session
      // 2. Fetch profile from API
      // 3. Set status to 'ready', 'needs-nric', or 'anonymous'
      // 4. Write profile to localStorage as cache
      // The dashboard's onboarding guard will redirect if no grades.
      router.replace('/dashboard')
    }
    handle()
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-gray-500">Redirecting...</div>
    </div>
  )
}
```

This is 30 lines. The current version is 45. No profile fetching, no routing decisions — the callback just establishes the session and sends the user to dashboard. AuthProvider + the dashboard guard handle the rest.

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes.

**Step 3: Commit**

```bash
git add halatuju-web/src/app/auth/callback/page.tsx
git commit -m "refactor: callback page just establishes session, delegates routing to AuthProvider"
```

---

### Task 4: Update dashboard and search pages for new guard API

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx:50`
- Modify: `halatuju-web/src/app/search/page.tsx` (if it uses `useOnboardingGuard`)

**Step 1: Update dashboard page**

The current code (line 50):
```typescript
const { ready: onboarded } = useOnboardingGuard()
```

Replace with:
```typescript
const { ready: onboarded, loading: guardLoading } = useOnboardingGuard()
```

Add routing logic near the top of the component (after hooks, before any early returns):
```typescript
const router = useRouter()  // already exists

// Wait for auth to resolve before rendering
if (guardLoading) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-gray-500">Loading...</div>
    </div>
  )
}

// Redirect if not ready (no grades or not authenticated)
if (!onboarded) {
  router.replace('/onboarding/exam-type')
  return null
}
```

Remove or replace the existing `if (!onboarded) return null` pattern if present.

**Step 2: Check if search page uses the guard**

```bash
grep -n "useOnboardingGuard" halatuju-web/src/app/search/page.tsx
```

If it does, apply the same pattern. If not, skip.

**Step 3: Check if any other pages use the guard**

```bash
grep -rn "useOnboardingGuard" halatuju-web/src/
```

Update all callers with the same `{ ready, loading }` pattern.

**Step 4: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes.

**Step 5: Commit**

```bash
git add halatuju-web/src/app/dashboard/page.tsx halatuju-web/src/app/search/page.tsx
git commit -m "refactor: dashboard and search use new guard with loading state"
```

---

## Phase B: Breaking Changes (Tasks 5–7)

> Tasks 5–7 remove old code paths and delete temporary files. These are NOT backwards-compatible — AuthGateModal stops fetching its own profile, IC page changes its guard, and `profile-restore.ts` is deleted. Deploy Phase B only after Phase A is verified in production.

### Task 5: Simplify AuthGateModal — remove profile fetching

**Files:**
- Modify: `halatuju-web/src/components/AuthGateModal.tsx`

**Step 1: Remove the `getProfile` import and calls**

The modal currently imports `getProfile` from `@/lib/api` and calls it in a `useEffect` (lines 63-82) to check if a returning user has NRIC. It also imports `restoreProfileToLocalStorage`.

Remove these. Instead, read `status` and `profile` from `useAuth()`:

```typescript
const {
  authGateReason,
  authGateCourseId,
  hideAuthGate,
  isAuthenticated,
  isAnonymous,
  token,
  session,
  status,    // NEW
  profile,   // NEW
} = useAuth()
```

**Step 2: Replace the "advance when user authenticates" useEffect**

Current (lines 63-82): fetches profile, checks NRIC, advances to IC or calls `handleReturningUser`.

Replace with:
```typescript
// Advance when user authenticates mid-modal
useEffect(() => {
  if (!authGateReason || status === 'loading' || status === 'anonymous') return
  if (step === 'ic') return

  if (status === 'ready') {
    // RETURNING USER — has NRIC, sync and close
    handleReturningUser()
  } else if (status === 'needs-nric') {
    // NEW USER — needs NRIC verification
    const googleName = session?.user?.user_metadata?.full_name
      || session?.user?.user_metadata?.name
    if (googleName && !name) setName(googleName)
    setStep('ic')
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [status, authGateReason])
```

**Step 3: Simplify `handleReturningUser`**

Remove the `restoreProfileToLocalStorage` call — AuthProvider already populated the profile in state and wrote it to localStorage via the side effect.

```typescript
const handleReturningUser = async () => {
  if (!token) return
  await syncLocalStorageToBackend(token)
  finishAndClose()
}
```

**Step 4: Replace `finishAndClose` redirect with a `useEffect` watching `status`**

The problem with reading `profile` inside `finishAndClose` is that the closure may capture a stale `profile` (from before the auth flow completed). Instead, `finishAndClose` should only persist resume actions and close the modal. A separate `useEffect` watches `status` and performs the redirect once AuthProvider has resolved.

Simplify `finishAndClose` to only handle resume actions and cleanup:

```typescript
const finishAndClose = () => {
  const reason = authGateReason
  const courseId = authGateCourseId
  if (reason === 'save' && courseId) {
    localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'save', courseId }))
  } else if (reason === 'report') {
    localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'report' }))
  } else if (reason === 'eligible') {
    localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'eligible' }))
  }
  localStorage.removeItem(KEY_PENDING_AUTH_ACTION)
  hideAuthGate()
  setLoading(false)
  if (reason === 'quiz') {
    router.push('/quiz')
  }
  // 'profile' reason: redirect handled by useEffect below (avoids stale closure)
}
```

Add a new `useEffect` that watches `status` and redirects after the modal closes for `reason === 'profile'`:

```typescript
// Redirect after profile-reason auth completes — reads fresh status, not stale closure
const [pendingProfileRedirect, setPendingProfileRedirect] = useState(false)

// In finishAndClose, replace the 'profile' redirect:
// } else if (reason === 'profile') {
//   setPendingProfileRedirect(true)  // trigger the effect below
// }

useEffect(() => {
  if (!pendingProfileRedirect || status === 'loading') return
  setPendingProfileRedirect(false)
  if (status === 'ready') {
    const hasGrades = profile?.grades && Object.keys(profile.grades).length > 0
    router.push(hasGrades ? '/dashboard' : '/onboarding/exam-type')
  } else {
    router.push('/onboarding/exam-type')
  }
}, [pendingProfileRedirect, status, profile, router])
```

This ensures we always read `profile` from the latest React state, never from a stale closure.

**Step 5: Remove unused imports**

Remove `getProfile` from the `@/lib/api` import (keep `syncProfile`, `claimNric`).
Remove `restoreProfileToLocalStorage` import.
Remove `KEY_GRADES` from storage imports if no longer used in this file.

**Step 6: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes.

**Step 7: Commit**

```bash
git add halatuju-web/src/components/AuthGateModal.tsx
git commit -m "refactor: AuthGateModal reads status/profile from context, no more getProfile calls"
```

---

### Task 6: Update IC page guard

**Files:**
- Modify: `halatuju-web/src/app/onboarding/ic/page.tsx`

**Step 1: Read current guard logic**

The IC page currently checks `isAnonymous` and localStorage for grades. Replace with `status` from AuthProvider.

```typescript
const { status, profile } = useAuth()
const router = useRouter()

useEffect(() => {
  if (status === 'loading') return
  if (status === 'anonymous') { router.replace('/'); return }
  if (status === 'ready') {
    // Already has NRIC — check if they have grades too
    const hasGrades = profile?.grades && Object.keys(profile.grades).length > 0
    router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
    return
  }
  // status === 'needs-nric' — stay on this page
}, [status, profile, router])
```

Note: Without the `hasGrades` check, a user with NRIC but no grades would be sent to `/dashboard`, which would then redirect to `/onboarding/exam-type` — causing a visible double redirect. This avoids that.

**Step 2: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes.

**Step 3: Commit**

```bash
git add halatuju-web/src/app/onboarding/ic/page.tsx
git commit -m "refactor: IC page guard reads status from AuthProvider"
```

---

### Task 7: Delete profile-restore.ts

**Files:**
- Delete: `halatuju-web/src/lib/profile-restore.ts`

**Step 1: Verify no remaining imports**

```bash
grep -rn "profile-restore" halatuju-web/src/
```

Expected: No results (all imports were removed in Tasks 1 and 5).

If any remain, remove them first.

**Step 2: Delete the file**

```bash
rm halatuju-web/src/lib/profile-restore.ts
```

**Step 3: Verify build**

Run: `cd halatuju-web && npx next build`
Expected: Build passes.

**Step 4: Commit**

```bash
git add -A halatuju-web/src/lib/profile-restore.ts
git commit -m "chore: delete profile-restore.ts — AuthProvider handles caching"
```

---

## Phase C: Cleanup (Task 8)

### Task 8: Remove TD-003 from Known Issues, update CLAUDE.md

**Files:**
- Modify: `halatuju_api/CLAUDE.md`

**Step 1: Remove the TD-003 entry**

Delete the line:
```
- **TD-003: localStorage as routing authority** — ...
```

**Step 2: Update test counts if any tests changed**

Check if any frontend tests reference `profile-restore` or the old guard API. If so, update them.

**Step 3: Verify full build one final time**

Run: `cd halatuju-web && npx next build`
Expected: Build passes.

**Step 4: Commit**

```bash
git add halatuju_api/CLAUDE.md
git commit -m "docs: remove TD-003 — auth flow refactored, localStorage no longer routing authority"
```

---

## Verification checklist

After all tasks, verify these scenarios work:

1. **Fresh browser, returning user (has NRIC + grades):** Landing → Login → Google → callback → dashboard (not onboarding)
2. **Fresh browser, new user:** Landing → Login → Google → callback → IC page → NRIC → onboarding
3. **Direct dashboard URL, not logged in:** Shows loading → anonymous → auth gate or redirect
4. **Already logged in, refresh dashboard:** Shows loading briefly → profile loads from API → renders
5. **Auth gate from save button:** Click save → gate opens → Google → callback → dashboard → save resumes

Run: `cd halatuju-web && npx next build`
Expected: Build passes with no errors.

---

## What's NOT in this plan (and why)

- **Dashboard localStorage reads for rendering** — These read grades/profile to build API payloads. They're rendering concerns, not routing. They can stay reading localStorage as a fast cache. Moving them to context would require passing profile down as props or reading from context in every page, which is a separate (lower priority) refactor.
- **Onboarding form pre-fill from localStorage** — Same reasoning. The grades page reads localStorage to pre-fill the form. This is fine — it's reading a cache for display, not making a routing decision.
- **Anonymous user cleanup** — Ops task, not a code change. Add a monthly `DELETE FROM auth.users WHERE is_anonymous = true AND created_at < now() - interval '7 days'` to the maintenance runbook.
- **Phone login implementation** — Future feature. The refactored AuthProvider will handle it cleanly because phone auth completes in-modal (no redirect), `onAuthStateChange` fires, AuthProvider fetches profile, status updates, modal reads status.
