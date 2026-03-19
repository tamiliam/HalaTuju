# NRIC Hard Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make NRIC the hard identity gate — no Supabase account or Django profile created until NRIC is verified. Returning users bypass IC via Google/phone match.

**Architecture:** Replace the current auth-first-then-profile flow with identity-first design. Students browse anonymously (localStorage only). When the auth gate triggers, Google/phone proves "I'm real", then NRIC proves "I'm this specific student." Supabase anonymous sign-in provides JWT for anonymous browsing without creating a permanent auth user. Account creation happens only after NRIC verification.

**Tech Stack:** Supabase Auth (anonymous sign-in + `linkIdentity()`), Next.js 14, Django REST, React Context

---

## Current Architecture (What's Wrong)

1. Google OAuth immediately creates a Supabase auth user
2. 5 backend endpoints call `get_or_create(supabase_user_id=...)` creating profiles without NRIC
3. AuthGateModal IC step can be bypassed via direct URL navigation
4. No middleware enforcement — every new endpoint must remember to check NRIC

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ANONYMOUS ZONE (no account, localStorage only)             │
│  Dashboard, Search, Course Details, Pathways                │
│  JWT: anonymous Supabase user (is_anonymous=true)           │
└──────────────────────┬──────────────────────────────────────┘
                       │ Auth gate triggers (save, quiz, report, etc.)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Verify identity (Google / Phone)                   │
│  "I am a real person"                                       │
│  Google/phone already in Supabase? → RETURNING USER         │
│  Google/phone NOT in Supabase? → NEW USER                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐     ┌──────────────────────────┐
│  RETURNING USER  │     │  NEW USER                │
│  Has NRIC already│     │  STEP 2: Enter NRIC      │
│  Skip IC step    │     │  "I am THIS student"     │
│  Restore profile │     │  NRIC in DB? → recover   │
│  Full access     │     │  NRIC new? → create      │
└──────────────────┘     │  Full access             │
                         └──────────────────────────┘
```

## Three User Paths

| Path | Trigger | Steps | Result |
|------|---------|-------|--------|
| **Returning user** | Google/phone matches existing Supabase user | Login → has NRIC → done | Session restored, profile synced |
| **New user** | Google/phone not in Supabase | Login → IC → NRIC not in DB → create | New account + profile |
| **Account recovery** | Google/phone is new, but NRIC matches existing profile | Login → IC → NRIC in DB → transfer | Profile transferred to new auth user |

## Dismissed Auth Gate

If the student dismisses at any point:
- No account created
- Returns to anonymous state (localStorage only)
- Next auth gate trigger restarts from step 1

---

## Task Breakdown

### Task 1: Enable Supabase Anonymous Sign-In

**Context:** Supabase has built-in anonymous sign-in. We need to enable it in the dashboard and add a helper function. Anonymous users get a JWT with `is_anonymous=true` in the claims, so the backend middleware already works — it just sees a valid JWT.

**Files:**
- Modify: `halatuju-web/src/lib/supabase.ts`

**Step 1: Enable anonymous sign-ins in Supabase dashboard**

Go to Supabase Dashboard → Authentication → Providers → Enable "Anonymous Sign-Ins"

Also enable "Manual Linking" under Authentication → Providers (needed for `linkIdentity()`).

**Step 2: Add `signInAnonymously()` helper**

In `halatuju-web/src/lib/supabase.ts`, add:

```typescript
export async function signInAnonymously() {
  const { data, error } = await getSupabase().auth.signInAnonymously()
  return { data, error }
}

export async function linkIdentity(provider: 'google') {
  const { data, error } = await getSupabase().auth.linkIdentity({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })
  return { data, error }
}
```

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/supabase.ts
git commit -m "feat: add anonymous sign-in and linkIdentity helpers"
```

---

### Task 2: Auto-Sign-In Anonymously on First Visit

**Context:** When a student first visits, they should get an anonymous Supabase session automatically. This gives them a JWT for API calls without creating a real account. The `AuthProvider` currently only checks for existing sessions — we add anonymous sign-in if no session exists.

**Files:**
- Modify: `halatuju-web/src/lib/auth-context.tsx`

**Step 1: Update `AuthProvider` to auto-sign-in anonymously**

In the `useEffect` that calls `getSession()`, if no session exists, call `signInAnonymously()`:

```typescript
import { getSession, getSupabase, signInAnonymously } from '@/lib/supabase'

// In the useEffect:
getSession()
  .then(async ({ session }) => {
    if (!session) {
      // No session — sign in anonymously
      const { data } = await signInAnonymously()
      session = data?.session ?? null
    }
    setSession(session ?? null)
    setIsLoading(false)

    // Only restore profile for non-anonymous returning users
    if (session?.access_token && !session.user?.is_anonymous) {
      restoreProfileToLocalStorage(session.access_token)
    }

    // ... rest of pending auth action logic
  })
```

**Step 2: Add `isAnonymous` to auth context**

The context needs to expose whether the user is anonymous so components can distinguish:

```typescript
interface AuthContextValue {
  // ... existing fields
  isAnonymous: boolean  // true if anonymous session
}

// In AuthProvider:
const isAnonymous = session?.user?.is_anonymous ?? true

// Update isAuthenticated to mean "has completed identity verification"
// For now, keep isAuthenticated as !!session (we'll refine in Task 5)
```

**Step 3: Update `onAuthStateChange` handler**

Only restore profile for non-anonymous users:

```typescript
if (event === 'SIGNED_IN' && session?.access_token && !session.user?.is_anonymous) {
  restoreProfileToLocalStorage(session.access_token)
}
```

**Step 4: Commit**

```bash
git add halatuju-web/src/lib/auth-context.tsx
git commit -m "feat: auto-sign-in anonymously on first visit"
```

---

### Task 3: Rewrite AuthGateModal Flow

**Context:** The current modal has 4 steps: login → otp → ic → profile. The new flow:
- Step 1 (`login`): Google/phone — proves "I'm real"
- Step 2 (`ic`): NRIC + name + referral — proves "I'm this student" (new users only)
- Step 3 (`profile`): Removed — name is collected in IC step, demographics are in the profile page
- The `otp` step stays (for phone flow)

The key change: after Google/phone succeeds, check if this is a returning user (has NRIC) → skip IC → go straight through. Only new users see IC.

**Files:**
- Modify: `halatuju-web/src/components/AuthGateModal.tsx`

**Step 1: Change the login step to use `linkIdentity()` for Google**

For new users (anonymous session), Google login should use `linkIdentity()` to attach Google to the anonymous user, not `signInWithOAuth()` which creates a new user.

But if Google is already linked to an existing Supabase user, `linkIdentity()` will fail. In that case, fall back to `signInWithOAuth()` which will sign in as the existing user.

```typescript
const handleGoogleLogin = async () => {
  // Store pending action before redirect
  localStorage.setItem(
    KEY_PENDING_AUTH_ACTION,
    JSON.stringify({ reason: authGateReason, courseId: authGateCourseId })
  )
  setLoading(true)
  setError(null)

  if (session?.user?.is_anonymous) {
    // Try linking Google to anonymous user
    const { error } = await linkIdentity('google')
    if (error) {
      // Google already belongs to an existing user — sign in normally
      const { error: signInError } = await signInWithGoogle()
      if (signInError) {
        setError(signInError.message)
        setLoading(false)
      }
    }
  } else {
    // Not anonymous — just sign in
    const { error } = await signInWithGoogle()
    if (error) {
      setError(error.message)
      setLoading(false)
    }
  }
  // Browser redirects to Google — no further code runs
}
```

**Step 2: Update post-auth logic to check returning vs new user**

After Google/phone auth succeeds, the `useEffect` that watches `isAuthenticated` needs to:
1. Check if user is still anonymous → shouldn't happen after successful link/login
2. Call `getProfile()` → if has NRIC → skip IC, close modal, sync data
3. If no NRIC → show IC step

The existing code at lines 66-91 already does this check — keep the logic but adjust:

```typescript
useEffect(() => {
  if (!authGateReason || !token) return
  if (session?.user?.is_anonymous) return  // Still anonymous — don't advance

  // Non-anonymous user — check NRIC
  getProfile({ token }).then(profile => {
    if (profile.nric) {
      // RETURNING USER — has NRIC, skip IC
      // Sync localStorage → backend, then close
      handleReturningUser(profile)
    } else {
      // NEW USER — needs IC
      const googleName = session?.user?.user_metadata?.full_name
        || session?.user?.user_metadata?.name
      if (googleName && !name) setName(googleName)
      setStep('ic')
    }
  }).catch(() => setStep('ic'))
}, [token, authGateReason, session])
```

**Step 3: Update IC step to call `claimNric()` instead of just storing locally**

The IC step in the modal currently just validates and moves to profile step. It needs to:
1. Call `claimNric(ic, false, { token })` on the backend
2. Handle `created` / `exists` / `linked` / `claimed` responses
3. On success: sync localStorage data, close modal

```typescript
const handleIcSubmit = async (e: React.FormEvent) => {
  e.preventDefault()
  const err = validateIc(ic)
  if (err) { setError(err); return }
  if (!token) return

  setLoading(true)
  setError(null)

  try {
    const { claimNric } = await import('@/lib/api')
    const result = await claimNric(ic, false, { token })

    if (result.status === 'created' || result.status === 'linked') {
      // Sync all localStorage data to backend
      await syncLocalStorageToBackend(token)
      finishAndClose()
    } else if (result.status === 'exists') {
      setExistingName(result.name || null)
      setShowConfirm(true)
      setLoading(false)
    }
  } catch {
    setError(t('errors.saveFailed'))
    setLoading(false)
  }
}

const handleConfirmClaim = async () => {
  setLoading(true)
  try {
    const { claimNric } = await import('@/lib/api')
    await claimNric(ic, true, { token: token! })
    await syncLocalStorageToBackend(token!)
    finishAndClose()
  } catch {
    setError(t('errors.claimFailed'))
    setLoading(false)
  }
}
```

**Step 4: Extract `syncLocalStorageToBackend()` and `finishAndClose()` helpers**

```typescript
async function syncLocalStorageToBackend(token: string) {
  const syncData: SyncProfileData = {}
  try {
    const grades = localStorage.getItem(KEY_GRADES)
    if (grades) syncData.grades = JSON.parse(grades)
    const prof = localStorage.getItem(KEY_PROFILE)
    if (prof) {
      const p = JSON.parse(prof)
      if (p.gender) syncData.gender = p.gender
      if (p.nationality) syncData.nationality = p.nationality
      if (p.state) syncData.preferred_state = p.state
      if (p.colorblind) syncData.colorblind = p.colorblind
      if (p.disability) syncData.disability = p.disability
    }
    const signals = localStorage.getItem(KEY_QUIZ_SIGNALS)
    if (signals) syncData.student_signals = JSON.parse(signals)
  } catch { /* ignore */ }
  if (name.trim()) syncData.name = name.trim()
  const ref = localStorage.getItem(KEY_REFERRAL_SOURCE)
  if (ref) syncData.referral_source = ref
  await syncProfile(syncData, { token })
}

function finishAndClose() {
  // Store resume action
  if (authGateReason === 'save' && authGateCourseId) {
    localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'save', courseId: authGateCourseId }))
  } else if (authGateReason === 'report') {
    localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'report' }))
  } else if (authGateReason === 'eligible') {
    localStorage.setItem(KEY_RESUME_ACTION, JSON.stringify({ action: 'eligible' }))
  }
  localStorage.removeItem(KEY_PENDING_AUTH_ACTION)
  hideAuthGate()
  setLoading(false)
  if (authGateReason === 'quiz') router.push('/quiz')
}
```

**Step 5: Remove the `profile` step entirely**

The modal no longer needs a `profile` step. Name is collected in the IC step. Demographics are on the profile page.

Change `ModalStep` type:
```typescript
type ModalStep = 'login' | 'otp' | 'ic'
```

**Step 6: Add NRIC confirm dialog (exists case) to IC step UI**

Port the confirm/deny UI from `onboarding/ic/page.tsx` into the modal's IC step. The existing `showConfirm` and `existingName` state already exist — add the JSX.

**Step 7: Commit**

```bash
git add halatuju-web/src/components/AuthGateModal.tsx
git commit -m "feat: rewrite auth gate — NRIC-first identity flow"
```

---

### Task 4: Backend NRIC Middleware (Hard Gate)

**Context:** Instead of checking NRIC in every endpoint, add middleware that rejects authenticated (non-anonymous) requests that have no NRIC. Only whitelist the endpoints needed to establish identity.

**Files:**
- Modify: `halatuju_api/halatuju/middleware/supabase_auth.py`
- Test: `halatuju_api/apps/courses/tests/test_nric_gate.py`

**Step 1: Write failing tests**

```python
# test_nric_gate.py
from django.test import TestCase, RequestFactory
from halatuju.middleware.supabase_auth import NricGateMiddleware
from apps.courses.models import StudentProfile


class NricGateMiddlewareTest(TestCase):
    """Middleware blocks non-anonymous users without NRIC from protected endpoints."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = NricGateMiddleware(lambda req: HttpResponse(200))

    def test_allows_anonymous_users(self):
        """Anonymous JWT (is_anonymous=true) should pass through."""
        request = self.factory.get('/api/v1/saved-courses/')
        request.user_id = 'anon-123'
        request.supabase_user = {'is_anonymous': True}
        response = self.middleware(request)
        assert response.status_code == 200

    def test_allows_whitelisted_endpoints(self):
        """Profile GET and claim-nric should work without NRIC."""
        for path in ['/api/v1/profile/', '/api/v1/profile/claim-nric/']:
            request = self.factory.get(path)
            request.user_id = 'user-123'
            request.supabase_user = {'is_anonymous': False}
            response = self.middleware(request)
            assert response.status_code == 200

    def test_blocks_user_without_nric(self):
        """Non-anonymous user without NRIC should get 403."""
        StudentProfile.objects.create(supabase_user_id='user-123', nric='')
        request = self.factory.post('/api/v1/saved-courses/')
        request.user_id = 'user-123'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        assert response.status_code == 403

    def test_allows_user_with_nric(self):
        """Non-anonymous user WITH NRIC should pass through."""
        StudentProfile.objects.create(supabase_user_id='user-123', nric='010101-01-1234')
        request = self.factory.post('/api/v1/saved-courses/')
        request.user_id = 'user-123'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        assert response.status_code == 200

    def test_allows_public_endpoints(self):
        """Unauthenticated requests (user_id=None) pass through — views decide."""
        request = self.factory.post('/api/v1/eligibility/check/')
        request.user_id = None
        request.supabase_user = None
        response = self.middleware(request)
        assert response.status_code == 200

    def test_allows_profile_sync(self):
        """Profile sync is whitelisted (called right after NRIC claim)."""
        request = self.factory.post('/api/v1/profile/sync/')
        request.user_id = 'user-123'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        assert response.status_code == 200

    def test_allows_admin_endpoints(self):
        """Admin endpoints are not subject to NRIC gate."""
        request = self.factory.get('/api/v1/admin/role/')
        request.user_id = 'admin-123'
        request.supabase_user = {'is_anonymous': False}
        response = self.middleware(request)
        assert response.status_code == 200
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest apps/courses/tests/test_nric_gate.py -v
```

**Step 3: Implement the middleware**

Add `NricGateMiddleware` to `halatuju/middleware/supabase_auth.py`:

```python
from django.http import JsonResponse

# Endpoints that work without NRIC (identity establishment + admin)
NRIC_GATE_WHITELIST = [
    '/api/v1/profile/',           # GET to check NRIC status
    '/api/v1/profile/claim-nric/',# POST to claim NRIC
    '/api/v1/profile/sync/',      # POST to sync after NRIC claim
    '/api/v1/admin/',             # All admin endpoints (prefix match)
]


class NricGateMiddleware:
    """
    Hard gate: non-anonymous authenticated users MUST have NRIC
    to access any protected endpoint. Whitelist allows identity
    establishment endpoints through.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip if no auth (public endpoints) or anonymous user
        user_id = getattr(request, 'user_id', None)
        if not user_id:
            return self.get_response(request)

        supabase_user = getattr(request, 'supabase_user', None) or {}
        if supabase_user.get('is_anonymous', False):
            return self.get_response(request)

        # Skip whitelisted paths
        path = request.path
        for allowed in NRIC_GATE_WHITELIST:
            if path.startswith(allowed):
                return self.get_response(request)

        # Check if user has NRIC
        from apps.courses.models import StudentProfile
        try:
            profile = StudentProfile.objects.only('nric').get(
                supabase_user_id=user_id
            )
            if not profile.nric:
                return JsonResponse(
                    {'error': 'NRIC verification required', 'code': 'nric_required'},
                    status=403
                )
        except StudentProfile.DoesNotExist:
            return JsonResponse(
                {'error': 'NRIC verification required', 'code': 'nric_required'},
                status=403
            )

        return self.get_response(request)
```

**Step 4: Register middleware in settings**

In `halatuju/settings/base.py`, add after `SupabaseAuthMiddleware`:

```python
MIDDLEWARE = [
    # ...
    'halatuju.middleware.supabase_auth.SupabaseAuthMiddleware',
    'halatuju.middleware.supabase_auth.NricGateMiddleware',  # NEW
    # ...
]
```

**Step 5: Run tests**

```bash
python -m pytest apps/courses/tests/test_nric_gate.py -v
```

Expected: all pass.

**Step 6: Run full test suite to check nothing broke**

```bash
python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

Expected: 932+ pass, 0 fail. Some existing tests may need the test user to have NRIC — fix any failures.

**Step 7: Commit**

```bash
git add halatuju/middleware/supabase_auth.py halatuju/settings/base.py apps/courses/tests/test_nric_gate.py
git commit -m "feat: NRIC hard gate middleware — blocks protected endpoints without NRIC"
```

---

### Task 5: Update Auth Context — `isAuthenticated` Means "Has Identity"

**Context:** Currently `isAuthenticated = !!session`. With anonymous sign-in, every visitor has a session. We need `isAuthenticated` to mean "has completed identity verification (non-anonymous + has NRIC)". Components that trigger auth gates use this flag.

**Files:**
- Modify: `halatuju-web/src/lib/auth-context.tsx`

**Step 1: Add `hasIdentity` state**

```typescript
const [hasIdentity, setHasIdentity] = useState(false)

// After session is set and is non-anonymous, check profile for NRIC:
if (session?.access_token && !session.user?.is_anonymous) {
  getProfile({ token: session.access_token }).then(profile => {
    setHasIdentity(!!profile.nric)
    if (profile.nric) restoreProfileToLocalStorage(session.access_token)
  }).catch(() => setHasIdentity(false))
}
```

**Step 2: Redefine `isAuthenticated`**

```typescript
// OLD: isAuthenticated: !!session  (anyone with a session)
// NEW: isAuthenticated means "has completed identity verification"
isAuthenticated: hasIdentity,

// Add separate flags for components that need finer control:
isAnonymous: session?.user?.is_anonymous ?? true,
hasSession: !!session,  // true for everyone including anonymous
```

**Step 3: Update `AuthContextValue` interface**

```typescript
interface AuthContextValue {
  session: Session | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean  // true = has NRIC, full access
  isAnonymous: boolean      // true = anonymous session
  hasSession: boolean       // true = has any session (including anonymous)
  authGateReason: AuthGateReason
  authGateCourseId: string | null
  showAuthGate: (reason: NonNullable<AuthGateReason>, options?: AuthGateOptions) => void
  hideAuthGate: () => void
}
```

**Step 4: Update `onAuthStateChange` to recalculate `hasIdentity`**

When SIGNED_IN fires (after Google link or login):

```typescript
if (event === 'SIGNED_IN' && session?.access_token && !session.user?.is_anonymous) {
  getProfile({ token: session.access_token }).then(profile => {
    setHasIdentity(!!profile.nric)
    if (profile.nric) restoreProfileToLocalStorage(session.access_token)
  }).catch(() => setHasIdentity(false))
}
```

**Step 5: Commit**

```bash
git add halatuju-web/src/lib/auth-context.tsx
git commit -m "feat: isAuthenticated now means has-NRIC, add isAnonymous flag"
```

---

### Task 6: Update All Auth Gate Triggers

**Context:** Components that currently check `isAuthenticated` to decide whether to show the auth gate need to keep working. Since `isAuthenticated` now means "has NRIC", the auth gate logic should still work: `!isAuthenticated` → show gate. But we need to verify each call site.

**Files:**
- Verify: `halatuju-web/src/hooks/useSavedCourses.ts`
- Verify: `halatuju-web/src/app/dashboard/page.tsx`
- Verify: `halatuju-web/src/app/quiz/page.tsx`
- Verify: `halatuju-web/src/app/stpm/quiz/page.tsx`
- Verify: `halatuju-web/src/app/search/page.tsx`
- Verify: `halatuju-web/src/app/profile/page.tsx`
- Verify: `halatuju-web/src/app/saved/page.tsx`
- Verify: `halatuju-web/src/components/AppHeader.tsx`
- Verify: `halatuju-web/src/components/AppFooter.tsx`

**Step 1: Check each file**

For each file, verify that `isAuthenticated` checks still make sense:
- `useSavedCourses`: `if (!isAuthenticated) showAuthGate('save')` — correct, saves need identity
- Dashboard: `if (!isAuthenticated) showAuthGate('quiz')` — correct
- Quiz/STPM quiz pages: if they check auth — correct
- Profile page: needs `isAuthenticated` to show profile data — correct
- Saved page: needs `isAuthenticated` to load saved courses — correct
- AppHeader: may show login/logout based on `isAuthenticated` — needs update: show "Sign In" for anonymous users, "Sign Out" for identified users

**Step 2: Update AppHeader**

The header currently shows different UI based on `isAuthenticated`. With anonymous sessions, it should:
- Anonymous user → show "Sign In" or nothing (no logout for anonymous)
- Identified user → show profile icon + "Sign Out"

```typescript
// In AppHeader:
const { isAuthenticated, isAnonymous } = useAuth()

// Show sign-in button only for anonymous users
// Show sign-out and profile only for identified users
```

**Step 3: Commit**

```bash
git add halatuju-web/src/components/AppHeader.tsx
git commit -m "feat: update header for anonymous vs identified users"
```

---

### Task 7: Remove Standalone Login Page, Update Auth Callback

**Context:** The standalone `/login` page currently calls `signInWithGoogle()` which creates a Supabase user immediately. This page is no longer needed — all login happens through the AuthGateModal. The auth callback page needs updating to handle `linkIdentity()` redirects.

**Files:**
- Delete: `halatuju-web/src/app/login/page.tsx` (or redirect to `/`)
- Modify: `halatuju-web/src/app/auth/callback/page.tsx`

**Step 1: Replace login page with redirect**

```typescript
// app/login/page.tsx
'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const router = useRouter()
  useEffect(() => { router.replace('/') }, [router])
  return null
}
```

**Step 2: Update auth callback**

After OAuth redirect (from `linkIdentity()` or `signInWithOAuth()`), the callback should:
1. Get the session
2. Check if user is anonymous (shouldn't be after successful link/login)
3. Check if user has NRIC
4. Route appropriately:
   - Has NRIC → `/dashboard` (returning user)
   - No NRIC → handled by AuthGateModal (pending auth action will resume)
   - Has pending auth action → go back to the page that triggered the gate

```typescript
// app/auth/callback/page.tsx
'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getSession } from '@/lib/supabase'
import { getProfile } from '@/lib/api'
import { KEY_PENDING_AUTH_ACTION, KEY_GRADES, KEY_STPM_GRADES } from '@/lib/storage'

export default function AuthCallback() {
  const router = useRouter()

  useEffect(() => {
    const handle = async () => {
      await new Promise(r => setTimeout(r, 500))
      const { session } = await getSession()
      if (!session) { router.replace('/'); return }

      // Check for pending auth action (from AuthGateModal Google flow)
      const pending = localStorage.getItem(KEY_PENDING_AUTH_ACTION)
      if (pending) {
        // Go back to the page — AuthProvider will detect session + pending action
        // and re-open the auth gate at the right step
        const hasGrades = localStorage.getItem(KEY_GRADES) || localStorage.getItem(KEY_STPM_GRADES)
        router.replace(hasGrades ? '/dashboard' : '/')
        return
      }

      // Direct login (not from auth gate) — check NRIC
      try {
        const profile = await getProfile({ token: session.access_token })
        if (profile.nric) {
          const hasGrades = localStorage.getItem(KEY_GRADES) || localStorage.getItem(KEY_STPM_GRADES)
          router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
        } else {
          router.replace('/onboarding/ic')
        }
      } catch {
        router.replace('/onboarding/ic')
      }
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

**Step 3: Commit**

```bash
git add halatuju-web/src/app/login/page.tsx halatuju-web/src/app/auth/callback/page.tsx
git commit -m "feat: replace login page with redirect, update auth callback for NRIC-first flow"
```

---

### Task 8: Remove `get_or_create` from Backend Views

**Context:** Now that the middleware enforces NRIC, we can clean up the backend views. The 5 endpoints that did `get_or_create(supabase_user_id=...)` should use `get()` instead — the profile must already exist (created by `NricClaimView`). Only `NricClaimView` and `ProfileView GET` should create profiles.

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`

**Step 1: Update SavedCourseListView.post (line ~872)**

```python
# OLD:
profile, _ = StudentProfile.objects.get_or_create(supabase_user_id=request.user_id)

# NEW:
profile = StudentProfile.objects.get(supabase_user_id=request.user_id)
```

**Step 2: Update ProfileView.put (line ~977)**

```python
# OLD:
profile, _ = StudentProfile.objects.get_or_create(supabase_user_id=request.user_id)

# NEW:
profile = StudentProfile.objects.get(supabase_user_id=request.user_id)
```

**Step 3: Update ProfileSyncView.post (line ~1024)**

```python
# OLD:
profile, created = StudentProfile.objects.get_or_create(supabase_user_id=request.user_id)

# NEW:
profile, created = StudentProfile.objects.get_or_create(supabase_user_id=request.user_id)
# KEEP get_or_create here — ProfileSync is called right after NricClaim
# and the profile may not exist yet if this is a fresh NRIC claim.
# The middleware whitelist allows this endpoint through.
```

**Step 4: Update OutcomeListView.post (line ~1320)**

```python
# OLD:
profile, _ = StudentProfile.objects.get_or_create(supabase_user_id=request.user_id)

# NEW:
profile = StudentProfile.objects.get(supabase_user_id=request.user_id)
```

**Step 5: Keep ProfileView.get as-is**

`ProfileView.get` needs `get_or_create` because the auth callback calls it to check NRIC status before a profile exists. The middleware whitelist allows `/api/v1/profile/` through.

**Step 6: Run full test suite**

```bash
python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

Fix any test failures — tests that create profiles without NRIC may need updating.

**Step 7: Commit**

```bash
git add halatuju_api/apps/courses/views.py
git commit -m "fix: remove get_or_create from protected views — profiles must exist via NRIC claim"
```

---

### Task 9: Update Onboarding IC Page

**Context:** The standalone `/onboarding/ic` page is still needed for the direct login flow (login page → callback → IC). But it needs to work with the new flow — it should only show if the user is non-anonymous and has no NRIC.

**Files:**
- Modify: `halatuju-web/src/app/onboarding/ic/page.tsx`

**Step 1: Add guard — redirect if already has NRIC or is anonymous**

```typescript
const { token, session, isAnonymous } = useAuth()

useEffect(() => {
  if (isAnonymous) {
    router.replace('/')  // Anonymous users shouldn't be here
    return
  }
  if (token) {
    getProfile({ token }).then(profile => {
      if (profile.nric) {
        // Already has NRIC — go to dashboard or exam-type
        const hasGrades = localStorage.getItem(KEY_GRADES) || localStorage.getItem(KEY_STPM_GRADES)
        router.replace(hasGrades ? '/dashboard' : '/onboarding/exam-type')
      }
    }).catch(() => {})
  }
}, [token, isAnonymous])
```

**Step 2: Commit**

```bash
git add halatuju-web/src/app/onboarding/ic/page.tsx
git commit -m "feat: guard IC page — redirect if anonymous or already has NRIC"
```

---

### Task 10: Handle Backend `is_anonymous` Claim

**Context:** The Supabase middleware currently extracts `email`, `phone`, `role` from the JWT. We need to also extract `is_anonymous` so the NRIC gate middleware can check it.

**Files:**
- Modify: `halatuju_api/halatuju/middleware/supabase_auth.py`

**Step 1: Update `SupabaseAuthMiddleware` to extract `is_anonymous`**

In the section where `request.supabase_user` is set:

```python
request.supabase_user = {
    'id': payload.get('sub'),
    'email': payload.get('email', ''),
    'phone': payload.get('phone', ''),
    'role': payload.get('role', ''),
    'is_anonymous': payload.get('is_anonymous', False),  # NEW
}
```

**Step 2: Commit**

```bash
git add halatuju/middleware/supabase_auth.py
git commit -m "feat: extract is_anonymous from JWT in auth middleware"
```

---

### Task 11: Frontend Error Handling for 403 `nric_required`

**Context:** When the backend returns 403 with `code: 'nric_required'`, the frontend should show the auth gate IC step instead of a generic error.

**Files:**
- Modify: `halatuju-web/src/lib/api.ts`
- Modify: `halatuju-web/src/hooks/useSavedCourses.ts`

**Step 1: Update `apiRequest()` to detect NRIC-required errors**

In `api.ts`, the base `apiRequest()` function handles errors. Add detection for the NRIC gate:

```typescript
if (res.status === 403) {
  const body = await res.json()
  if (body.code === 'nric_required') {
    // Dispatch event that auth context can listen to
    window.dispatchEvent(new CustomEvent('nric-required'))
    throw new Error('NRIC verification required')
  }
}
```

**Step 2: Listen for `nric-required` event in AuthProvider**

In `auth-context.tsx`, add an event listener that triggers the auth gate:

```typescript
useEffect(() => {
  const handler = () => showAuthGate('profile')  // or a new 'nric' reason
  window.addEventListener('nric-required', handler)
  return () => window.removeEventListener('nric-required', handler)
}, [showAuthGate])
```

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/api.ts halatuju-web/src/lib/auth-context.tsx
git commit -m "feat: handle 403 nric_required — auto-show auth gate"
```

---

### Task 12: Supabase RLS for Anonymous Users

**Context:** Anonymous users should NOT be able to read/write student data via Supabase direct access (RLS). The `is_anonymous` claim in the JWT lets us restrict this.

**Files:**
- SQL migration via Supabase MCP

**Step 1: Add restrictive RLS policies**

For tables that store student data (`api_student_profiles`, `api_saved_courses`, `api_admission_outcomes`, `api_generated_reports`):

```sql
-- Block anonymous users from accessing student data
CREATE POLICY "Block anonymous users"
ON api_student_profiles AS RESTRICTIVE FOR ALL
TO authenticated
USING ((auth.jwt()->>'is_anonymous')::boolean IS FALSE);

CREATE POLICY "Block anonymous users"
ON api_saved_courses AS RESTRICTIVE FOR ALL
TO authenticated
USING ((auth.jwt()->>'is_anonymous')::boolean IS FALSE);

-- Repeat for api_admission_outcomes, api_generated_reports, api_email_verifications
```

**Step 2: Test that existing RLS still works for identified users**

**Step 3: Commit migration**

---

### Task 13: Clean Up Orphan Supabase Users

**Context:** Existing Supabase users without NRIC profiles are orphans from the old flow. Clean them up.

**Step 1: Identify orphans**

```sql
-- Find Supabase auth users whose ID doesn't have a profile with NRIC
SELECT au.id, au.email, au.created_at
FROM auth.users au
LEFT JOIN api_student_profiles sp ON sp.supabase_user_id = au.id::text
WHERE (sp.nric IS NULL OR sp.nric = '')
  AND au.is_anonymous IS NOT TRUE;
```

**Step 2: Review the list with the user before deleting**

**Step 3: Set up periodic cleanup for anonymous users**

```sql
-- Delete anonymous users older than 30 days (Supabase recommendation)
DELETE FROM auth.users
WHERE is_anonymous IS TRUE AND created_at < now() - interval '30 days';
```

---

### Task 14: Integration Testing

**Files:**
- Create: `halatuju_api/apps/courses/tests/test_nric_gate_integration.py`

**Step 1: Write integration tests for all three user paths**

```python
class NricGateIntegrationTest(TestCase):
    """End-to-end tests for NRIC-first identity flow."""

    def test_new_user_path(self):
        """New user: no NRIC → claim → profile created → can save courses."""

    def test_returning_user_path(self):
        """Returning user: has NRIC → protected endpoints work."""

    def test_account_recovery_path(self):
        """Recovery: new auth user → claim existing NRIC → profile transferred."""

    def test_anonymous_user_blocked_from_saves(self):
        """Anonymous user cannot save courses (middleware blocks)."""

    def test_no_profile_user_blocked_from_saves(self):
        """Authenticated user without NRIC cannot save courses."""

    def test_dismissed_gate_no_side_effects(self):
        """User who dismisses auth gate has no profile or data created."""
```

**Step 2: Run all tests**

```bash
python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

**Step 3: Commit**

```bash
git add apps/courses/tests/test_nric_gate_integration.py
git commit -m "test: integration tests for NRIC hard gate flow"
```

---

## Execution Order & Dependencies

```
Task 10 (extract is_anonymous in middleware) — no dependencies
Task 1  (Supabase anonymous sign-in setup) — no dependencies
    ↓
Task 2  (auto-sign-in anonymously) — depends on Task 1
Task 4  (backend NRIC middleware) — depends on Task 10
    ↓
Task 5  (update isAuthenticated meaning) — depends on Task 2
Task 8  (remove get_or_create) — depends on Task 4
    ↓
Task 3  (rewrite AuthGateModal) — depends on Task 1, 5
Task 6  (update auth gate triggers) — depends on Task 5
Task 7  (login page + callback) — depends on Task 3
Task 9  (update IC page) — depends on Task 5
Task 11 (frontend 403 handling) — depends on Task 4, 5
    ↓
Task 12 (Supabase RLS) — depends on Task 1
Task 13 (cleanup orphans) — after all deployed
Task 14 (integration tests) — after Tasks 4, 8
```

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Existing users lose access | `is_anonymous` check skips non-anonymous users who already have profiles |
| `linkIdentity()` fails for existing Google users | Fall back to `signInWithOAuth()` |
| Anonymous user abuse (DB bloat) | Supabase rate limits (30/hr) + periodic cleanup SQL |
| Test suite breaks (profiles without NRIC) | Task 4 Step 6 catches this — fix test fixtures |
| Admin auth affected | Middleware whitelist includes `/api/v1/admin/` prefix |
