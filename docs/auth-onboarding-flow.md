# HalaTuju: Authentication & Onboarding Flow

> Complete documentation of how users move from anonymous landing through onboarding, registration, and returning login. Written to support a fresh review of technical debt.

---

## Architecture Overview

**Three data stores** hold user state:

| Store | Role | Lifetime |
|-------|------|----------|
| **AuthProvider** (React context) | Single source of truth for auth status, session, profile | Per-session (memory) |
| **localStorage** | Write-only cache + anonymous-only data store | Persistent (browser) |
| **Backend** (Supabase PostgreSQL via Django API) | Permanent record | Permanent |

**Canonical rule (from Auth Canonical Refactor):** AuthProvider fetches from API, writes to localStorage as a cache. Routing reads AuthProvider, never localStorage.

**Current exception:** `useOnboardingGuard` reads localStorage as fallback for grades during the transition from onboarding to dashboard (profile may not have synced yet).

---

## AuthProvider State Machine

```
status = isLoading ? 'loading'
       : isAnonymous ? 'anonymous'
       : hasIdentity ? 'ready'     // hasIdentity = !!profile.nric
       : 'needs-nric'
```

| Status | Session | Is Anonymous | NRIC | Meaning |
|--------|---------|-------------|------|---------|
| `loading` | unknown | unknown | unknown | Initial load |
| `anonymous` | yes | yes | N/A | Supabase anonymous session |
| `needs-nric` | yes | no | no | Signed in but no IC verified |
| `ready` | yes | no | yes | Full access |

---

## Flow 1: Anonymous User — Landing to Dashboard

### Step 0: App Initialisation

**On any page load**, `AuthProvider` runs:

1. `getSession()` — check for existing Supabase session
2. If no session → `signInAnonymously()` → creates anonymous session
3. `setSession(session)`, `setIsLoading(false)`
4. If `!is_anonymous` → `getProfile(token)` → populate `profile`, `hasIdentity`
5. Subscribe to `onAuthStateChange` for future session changes

**For anonymous user:** `status = 'anonymous'`, `profile = null`, `token = anonymous_jwt`

**localStorage write (if profile fetched):** AuthProvider caches profile data:
- `KEY_GRADES`, `KEY_PROFILE`, `KEY_QUIZ_SIGNALS`, `KEY_EXAM_TYPE`
- `KEY_STPM_GRADES`, `KEY_STPM_CGPA`, `KEY_MUET_BAND`

### Step 1: Landing Page (`/`)

User sees marketing page with CTAs:
- **"Start Your Journey"** → navigates to `/onboarding/exam-type` (no auth needed)
- **"Get Started" in nav** → `showAuthGate('profile')` (triggers auth modal)

No localStorage reads or API calls. Anonymous users go straight to onboarding.

### Step 2: Select Exam Type (`/onboarding/exam-type`)

Simple choice: SPM or STPM.

| Action | localStorage Write | Navigation |
|--------|--------------------|------------|
| Click "SPM" | `KEY_EXAM_TYPE = 'spm'` | `/onboarding/grades` |
| Click "STPM" | `KEY_EXAM_TYPE = 'stpm'` | `/onboarding/stpm-grades` |

No auth checks. No API calls. No guards.

### Step 3A: SPM Grades (`/onboarding/grades`)

User enters grades for 6 core + 4 stream + 0-2 elective subjects.

**On load — localStorage reads:**
- `KEY_STREAM`, `KEY_ALIRAN`, `KEY_ELEKTIF`, `KEY_GRADES` (restore previous input)

**During input — API call (debounced 400ms):**
- `POST /api/v1/eligibility/calculate-merit/` → returns `{academic_merit, final_merit}`
- CoQ score input writes `coqScore` into `KEY_PROFILE` immediately

**On "Continue":**

| localStorage Write | Value |
|--------------------|-------|
| `KEY_GRADES` | `{bm: 'A', eng: 'B+', ...}` |
| `KEY_ALIRAN` | `['subj1', 'subj2', 'subj3', 'subj4']` |
| `KEY_ELEKTIF` | `['subj1', 'subj2']` (0-2 items) |
| `KEY_MERIT` | merit score as string |
| `KEY_STREAM` | already written on stream change |

**Navigation:** `/onboarding/profile`

**No backend sync of grades.** Grades exist only in localStorage at this point.

### Step 3B: STPM Grades (`/onboarding/stpm-grades`)

User enters STPM subjects + grades, MUET band, CoQ score, and SPM prerequisite grades.

**On load — localStorage reads:**
- `KEY_STPM_STREAM`, `KEY_STPM_GRADES`, `KEY_MUET_BAND`, `KEY_KOKO_SCORE`
- `KEY_SPM_PREREQ`, `KEY_SPM_STREAM`, `halatuju_spm_aliran`, `halatuju_spm_elektif`

**During input — API call (debounced 400ms):**
- `POST /api/v1/stpm-courses/calculate-cgpa/` → returns `{academic_cgpa, cgpa}`

**On "Continue":**

| localStorage Write | Value |
|--------------------|-------|
| `KEY_STPM_STREAM` | `'science'` or `'arts'` |
| `KEY_STPM_GRADES` | `{PA: 'A', MATH_T: 'B+', ...}` |
| `KEY_STPM_CGPA` | CGPA as string |
| `KEY_MUET_BAND` | band number as string |
| `KEY_KOKO_SCORE` | koko score as string |
| `KEY_SPM_PREREQ` | SPM grades object |
| `KEY_SPM_STREAM` | SPM stream |
| `halatuju_spm_aliran` | SPM aliran subjects |
| `halatuju_spm_elektif` | SPM electives |
| `KEY_EXAM_TYPE` | `'stpm'` |

**Navigation:** `/onboarding/profile`

**No backend sync.** All data in localStorage only.

### Step 4: Profile Demographics (`/onboarding/profile`)

User enters gender (required), nationality, state, colorblind, disability.

**On load — localStorage reads:**
- `KEY_PROFILE` (restore previous demographics)

**On load — API call (if token exists):**
- `GET /api/v1/profile/` → override local state with backend values

**On "Continue":**

| localStorage Write | Value |
|--------------------|-------|
| `KEY_PROFILE` | `{gender, nationality, state, colorblind, disability, coqScore}` |

**If user has token (any session, including anonymous):**
1. Build sync payload from form state + localStorage grades:
   - Demographics: `gender`, `nationality`, `preferred_state`, `colorblind`, `disability`
   - SPM: `grades` from `KEY_GRADES`
   - STPM: `exam_type`, `stpm_grades`, `stpm_cgpa`, `muet_band` from localStorage
2. `POST /api/v1/profile/sync/` with full payload
3. `await refreshProfile()` — re-fetches profile from API into AuthProvider
4. Navigate to `/dashboard`

**Critical note:** For anonymous users, `syncProfile` will work (anonymous JWT passes auth middleware) but the NRIC gate will block it since anonymous users skip the gate entirely. So for anonymous users the sync actually succeeds — the profile is created on the backend tied to the anonymous user ID.

**Wait — is this correct?** Let me re-examine...

The NRIC gate middleware skips anonymous users entirely (`is_anonymous → pass through`). So `POST /api/v1/profile/sync/` WILL work for anonymous users, and `ProfileSyncView.get_or_create` will create a `StudentProfile` with the anonymous `supabase_user_id` but no NRIC. **This is a source of empty profiles.**

### Step 5: Dashboard (`/dashboard`)

**Onboarding guard check (`useOnboardingGuard`):**

```
if status === 'loading'    → { ready: false, loading: true }
if status === 'needs-nric' → { ready: false, needsNric: true }
if status === 'anonymous'  → check localStorage for grades → { ready: hasLocalGrades }
if status === 'ready'      → check profile.grades, fallback to localStorage
```

**Redirect logic:**
- `needsNric` → `/onboarding/ic`
- `!onboarded` → `/onboarding/exam-type`
- Otherwise → stay, render dashboard

**Data load (localStorage reads):**

| Key | Used For |
|-----|----------|
| `KEY_EXAM_TYPE` | Determine SPM vs STPM rendering |
| `KEY_GRADES` | Build profile object for eligibility check |
| `KEY_PROFILE` | Gender, nationality, colorblind for eligibility |
| `KEY_MERIT` | Student merit score |
| `KEY_QUIZ_SIGNALS` | Quiz signals for ranking (if taken) |
| `KEY_STPM_GRADES` | STPM eligibility check |
| `KEY_STPM_CGPA` | STPM CGPA |
| `KEY_MUET_BAND` | MUET band |
| `KEY_SPM_PREREQ` | SPM prereq for STPM eligibility |

**API calls:**
- SPM: `POST /api/v1/eligibility/check/` → eligible courses
- SPM + quiz: `POST /api/v1/ranking/` → ranked courses
- STPM: `POST /api/v1/stpm-courses/check-eligibility/` → eligible programmes
- STPM: `POST /api/v1/stpm-courses/rank/` → ranked programmes

**Auth-gated actions (trigger `showAuthGate`):**
- Take quiz → `showAuthGate('quiz')`
- Save course → `showAuthGate('save', { courseId })`
- Load more → `showAuthGate('loadmore')`
- Generate report → `showAuthGate('report')`

---

## Flow 2: Auth Gate — Sign In → IC Verification

### Trigger

Any `showAuthGate(reason)` call sets `authGateReason` in AuthProvider context, which makes `AuthGateModal` visible.

### AuthGateModal Step 1: Login

**On open:**
1. Reset all form fields
2. If `isAuthenticated` already → `hideAuthGate()` and return (returning user shortcut)
3. Set `step = 'login'`

**Google OAuth (primary path):**
1. Write `KEY_PENDING_AUTH_ACTION = { reason, courseId }` to localStorage
2. Call `signInWithOAuth({ provider: 'google', redirectTo: '/auth/callback' })`
3. Browser redirects to Google → user authenticates → redirects to `/auth/callback`

**Phone/OTP (not yet implemented):**
- Shows "Phone login is coming soon" error
- Would: send OTP → verify OTP → establish session

### Auth Callback (`/auth/callback`)

1. Wait 500ms for Supabase to process OAuth callback
2. `getSession()` — session now exists
3. Redirect to `/dashboard`
4. AuthProvider's `onAuthStateChange` fires `SIGNED_IN` event
5. AuthProvider fetches profile → sets `status`

**Critical issue:** After Google redirect, the `AuthGateModal` has lost its in-memory state (page navigated away). The `KEY_PENDING_AUTH_ACTION` is saved in localStorage but **nothing reads it after callback**. The auth callback just goes to `/dashboard`.

### AuthGateModal Step 2: Auto-advance

When AuthProvider's `status` changes (via `onAuthStateChange`), the modal's useEffect runs:

```javascript
if (status === 'ready')       → handleReturningUser() → close modal
if (status === 'needs-nric')  → pre-fill Google name → setStep('ic')
```

**But after Google OAuth:** The user is on `/dashboard`. The modal was mounted by `providers.tsx` and is always present. However, `authGateReason` was reset during navigation (component state lost). So the modal is NOT visible.

**What actually happens:** The `useOnboardingGuard` on the dashboard detects `needsNric` and redirects to `/onboarding/ic` (the standalone IC page).

### IC Verification — Two Paths

#### Path A: Standalone IC Page (`/onboarding/ic`)

Reached when dashboard guard detects `status === 'needs-nric'`.

**Guard:**
- `anonymous` → redirect to `/`
- `ready` → redirect to `/dashboard` or `/onboarding/exam-type`
- `needs-nric` → stay

**User enters:**
1. NRIC (validated format: `XXXXXX-XX-XXXX`)
2. Name (pre-filled from Google profile)
3. Referral source (optional pills)

**On submit:**
1. `POST /api/v1/profile/claim-nric/` with `{ nric, confirm: false }`
2. Response: `created` or `linked` → sync name + referral via `POST /api/v1/profile/sync/`
3. Response: `exists` → show confirmation dialog ("Is this you?")
4. On success → `router.replace('/onboarding/exam-type')`

**Note:** The IC page syncs only `name` and `referral_source`. It does NOT sync grades or demographics. Those were already in localStorage from the anonymous onboarding flow, and will be synced later on the profile page.

**Navigation after IC:** → `/onboarding/exam-type` → grades → profile (where full sync happens) → dashboard

#### Path B: AuthGateModal IC Step

Reached when modal is still open (e.g., phone/OTP path where no redirect occurs).

**Same NRIC flow** as standalone, but after claiming:
1. Calls `syncLocalStorageToBackend(token)` — syncs grades + demographics + signals + name + referral
2. Calls `finishAndClose()` — saves resume action, closes modal

**Key difference from Path A:** The modal sync includes ALL localStorage data. The standalone IC page syncs only name + referral.

---

## Flow 3: Returning User

### Session Restoration

1. User visits any page
2. AuthProvider's `getSession()` returns existing Supabase session
3. Since `!is_anonymous` → `getProfile(token)` → full profile
4. `status = 'ready'` (NRIC present)
5. AuthProvider caches profile to localStorage (grades, demographics, signals, STPM data)

### Dashboard Access

- `useOnboardingGuard`: `status === 'ready'`, checks `profile.grades` → has grades → `ready: true`
- Dashboard loads, reads from localStorage (populated by AuthProvider cache)
- API calls: eligibility check, reports list, saved courses

### Auth-gated Actions

When a returning user triggers `showAuthGate`:
- Modal opens → detects `isAuthenticated` → `hideAuthGate()` immediately
- Action proceeds without interruption

---

## Known Issues & Technical Debt

### TD-1: Anonymous users create empty profiles

**Location:** `onboarding/profile/page.tsx` → `syncProfile()` + `ProfileSyncView.get_or_create`

**Problem:** Anonymous users have a token (anonymous JWT). The NRIC gate skips anonymous users. So when an anonymous user reaches the profile page and clicks Continue, `syncProfile` creates a `StudentProfile` with `supabase_user_id = anonymous_uuid` and no NRIC. These appear as empty profiles in admin.

**Impact:** Clutters admin view with anonymous profiles that may never convert.

**Options:**
1. Don't call `syncProfile` for anonymous users (only sync on profile page if `!isAnonymous`)
2. Skip `get_or_create` in `ProfileSyncView` — only update existing profiles
3. Filter anonymous profiles out of admin view

### TD-2: `KEY_PENDING_AUTH_ACTION` is written but never read

**Location:** AuthGateModal writes it before Google redirect. Auth callback page does not read it.

**Problem:** After Google OAuth redirect, the app goes to `/auth/callback` → `/dashboard`. The pending action (quiz, save, report) is lost. The user is not automatically resumed to their intended action.

**Impact:** User has to manually re-trigger the action (click quiz again, save again, etc.)

**Fix needed:** Auth callback (or dashboard) should check `KEY_PENDING_AUTH_ACTION` and resume the flow.

### TD-3: Two separate IC verification paths

**Location:** Standalone `onboarding/ic/page.tsx` + `AuthGateModal` IC step

**Problem:** Duplicated NRIC verification logic in two places. They behave differently:
- Standalone IC: syncs only `name` + `referral_source`, navigates to `/onboarding/exam-type`
- Modal IC: syncs ALL localStorage data, resumes the gated action

**Impact:** Maintenance burden, potential divergence. The standalone path doesn't sync grades (those get synced later on the profile page).

### TD-4: localStorage fallback in `useOnboardingGuard`

**Location:** `useOnboardingGuard.ts`

**Problem:** Breaks the canonical rule that routing reads AuthProvider, not localStorage. Exists because grades are entered during onboarding but only synced to the backend at the final profile page. Between grades entry and dashboard, AuthProvider's `profile.grades` may be empty.

**Impact:** Non-canonical, but functionally necessary for the current flow.

**Root cause:** Grades are not synced to the backend until the profile page (last onboarding step). If they were synced earlier, the guard could rely purely on AuthProvider.

### TD-5: Dashboard reads profile from localStorage, not AuthProvider

**Location:** `dashboard/page.tsx` lines 73-132

**Problem:** Dashboard builds its own `profile` object by reading localStorage directly, rather than using `useAuth().profile`. This is a separate `profile` state variable from AuthProvider's.

**Impact:** Two sources of truth for profile data on the dashboard. If AuthProvider's profile is updated (e.g., after quiz), the dashboard's local state is stale until page reload.

### TD-6: Onboarding profile page calls `syncProfile` with anonymous token

**Location:** `onboarding/profile/page.tsx` line 70 (`if (token)`)

**Problem:** The condition checks `if (token)` — anonymous users have a token (anonymous JWT). The sync call goes to `/api/v1/profile/sync/` which creates a profile via `get_or_create`. For anonymous users, this creates orphaned profiles.

**Fix:** Should be `if (token && !isAnonymous)` or better yet, check `status === 'ready'`.

### TD-7: Two localStorage keys not using KEY_ constants

**Location:** `onboarding/stpm-grades/page.tsx`

**Problem:** Uses raw strings `'halatuju_spm_aliran'` and `'halatuju_spm_elektif'` instead of constants from `storage.ts`. Inconsistent with the rest of the codebase.

---

## localStorage Key Reference

| Constant | Value | Written By | Read By |
|----------|-------|-----------|---------|
| `KEY_EXAM_TYPE` | `halatuju_exam_type` | exam-type page, STPM grades page, AuthProvider cache | Dashboard, guard, profile sync |
| `KEY_GRADES` | `halatuju_grades` | SPM grades page, AuthProvider cache | Dashboard, guard, profile sync, modal sync |
| `KEY_PROFILE` | `halatuju_profile` | Profile page, grades page (coqScore), AuthProvider cache | Dashboard, profile page load, modal sync |
| `KEY_STREAM` | `halatuju_stream` | SPM grades page | SPM grades page (restore) |
| `KEY_ALIRAN` | `halatuju_aliran` | SPM grades page | SPM grades page (restore) |
| `KEY_ELEKTIF` | `halatuju_elektif` | SPM grades page | SPM grades page (restore) |
| `KEY_MERIT` | `halatuju_merit` | SPM grades page | Dashboard (SPM merit) |
| `KEY_QUIZ_SIGNALS` | `halatuju_quiz_signals` | AuthProvider cache | Dashboard (ranking), modal sync |
| `KEY_SIGNAL_STRENGTH` | `halatuju_signal_strength` | Quiz page | Quiz page |
| `KEY_REPORT_GENERATED` | `halatuju_report_generated` | Dashboard (report gen) | Dashboard (CTA visibility) |
| `KEY_STPM_GRADES` | `halatuju_stpm_grades` | STPM grades page, AuthProvider cache | Dashboard, guard, profile sync |
| `KEY_STPM_CGPA` | `halatuju_stpm_cgpa` | STPM grades page, AuthProvider cache | Dashboard, profile sync |
| `KEY_MUET_BAND` | `halatuju_muet_band` | STPM grades page, AuthProvider cache | Dashboard, profile sync |
| `KEY_SPM_PREREQ` | `halatuju_spm_prereq` | STPM grades page | Dashboard (STPM eligibility) |
| `KEY_STPM_STREAM` | `halatuju_stpm_stream` | STPM grades page | STPM grades page (restore) |
| `KEY_KOKO_SCORE` | `halatuju_koko_score` | STPM grades page | STPM grades page (restore) |
| `KEY_SPM_STREAM` | `halatuju_spm_stream` | STPM grades page | STPM grades page (restore) |
| `KEY_LOCALE` | `halatuju_locale` | Language switcher | I18nProvider |
| `KEY_PENDING_AUTH_ACTION` | `halatuju_pending_auth_action` | AuthGateModal (pre-Google redirect) | **Nothing** (dead code) |
| `KEY_RESUME_ACTION` | `halatuju_resume_action` | AuthGateModal (finishAndClose) | Dashboard (resume hooks) |
| `KEY_REFERRAL_SOURCE` | `halatuju_referral_source` | IC page (referral pills) | IC page, modal sync |
| `KEY_STPM_QUIZ_SIGNALS` | `halatuju_stpm_quiz_signals` | AuthProvider cache | Dashboard (STPM ranking) |
| `KEY_STPM_QUIZ_BRANCH` | `halatuju_stpm_quiz_branch` | STPM quiz page | STPM quiz page |

---

## API Endpoints by Flow

### Public (no auth)
- `POST /api/v1/eligibility/check/` — SPM eligibility
- `POST /api/v1/eligibility/calculate-merit/` — merit calculation
- `POST /api/v1/stpm-courses/check-eligibility/` — STPM eligibility
- `POST /api/v1/stpm-courses/calculate-cgpa/` — CGPA calculation
- `POST /api/v1/stpm-courses/rank/` — STPM ranking
- `POST /api/v1/ranking/` — SPM ranking
- `GET /api/v1/courses/`, `GET /api/v1/institutions/` — public listings

### Auth required (any session)
- `GET /api/v1/profile/` — whitelisted in NRIC gate (exact match)
- `POST /api/v1/profile/claim-nric/` — whitelisted in NRIC gate (exact match)

### Auth + NRIC required
- `POST /api/v1/profile/sync/` — **not** whitelisted, requires NRIC
- `PUT /api/v1/profile/` — **not** whitelisted, requires NRIC
- `GET/POST/DELETE /api/v1/saved-courses/` — requires NRIC
- `POST /api/v1/reports/generate/` — requires NRIC
- `GET /api/v1/reports/` — requires NRIC
- `POST/PUT/DELETE /api/v1/outcomes/` — requires NRIC

### Admin
- `GET /api/v1/admin/*` — prefix-whitelisted in NRIC gate, checked by admin auth
