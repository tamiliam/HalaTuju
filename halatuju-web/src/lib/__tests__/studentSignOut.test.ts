/**
 * @jest-environment jsdom
 *
 * The student sign-out (Mobile M2 review). auth-js returns `{ error }` on a network or 5xx failure
 * and then KEEPS the stored session — we used to reload anyway, so on a shared phone the next person
 * was signed in as her. Now a failed sign-out still forgets her on this device.
 */
const PROJECT = 'https://abcdefghijkl.supabase.co'
const KEY = 'sb-abcdefghijkl-auth-token'

let mockOutcome: () => Promise<{ error: unknown }> = () => Promise.resolve({ error: null })
jest.mock('@/lib/supabase', () => ({
  ...jest.requireActual('@/lib/supabase'),
  signOut: () => mockOutcome(),
}))

import { signOutStudent } from '@/lib/studentSignOut'
import { clearStudentTab } from '@/lib/storage'
import { APPLY_PROGRAMME_KEY, APPLY_RETURN_KEY, APPLY_STASH_KEY, abandonApplyDetour } from '@/lib/applyReturn'
import { ONBOARDING_RETURN_KEY } from '@/lib/scholarship'
import { readWeb } from '@/test/sourceGuard'

beforeAll(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = PROJECT
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key'
})

function seed() {
  localStorage.clear()
  localStorage.setItem(KEY, '{"access_token":"hers"}')
  localStorage.setItem(`${KEY}-code-verifier`, 'v')
  localStorage.setItem(`${KEY}-user`, '{"id":"hers"}')
  localStorage.setItem('halatuju_grades', '{"BM":"A"}')
  localStorage.setItem('halatuju_profile', '{}')
  localStorage.setItem('halatuju_admin_session', 'admin-keeps')
  localStorage.setItem('halatuju_sponsor_session', 'sponsor-keeps')
  localStorage.setItem('other_app', 'keeps')
}

function expectHerDataGone() {
  expect(localStorage.getItem('halatuju_grades')).toBeNull()
  expect(localStorage.getItem('halatuju_profile')).toBeNull()
  expect(localStorage.getItem('halatuju_admin_session')).toBe('admin-keeps')
  expect(localStorage.getItem('halatuju_sponsor_session')).toBe('sponsor-keeps')
  expect(localStorage.getItem('other_app')).toBe('keeps')
}

it('a sign-out the server refuses (network / 5xx) still removes her session from this device', async () => {
  seed()
  mockOutcome = () => Promise.resolve({ error: { status: 503, message: 'unavailable' } })
  const go = jest.fn()
  await signOutStudent(go)
  expect(localStorage.getItem(KEY)).toBeNull()
  expect(localStorage.getItem(`${KEY}-code-verifier`)).toBeNull()
  expect(localStorage.getItem(`${KEY}-user`)).toBeNull()
  expectHerDataGone()
  expect(go).toHaveBeenCalledWith('/')
})

it('a sign-out that throws does the same', async () => {
  seed()
  mockOutcome = () => Promise.reject(new TypeError('Failed to fetch'))
  const go = jest.fn()
  await signOutStudent(go)
  expect(localStorage.getItem(KEY)).toBeNull()
  expectHerDataGone()
  expect(go).toHaveBeenCalledWith('/')
})

it('a sign-out that succeeds leaves the session to auth-js (it removed it) and still reloads', async () => {
  seed()
  mockOutcome = () => Promise.resolve({ error: null })
  const go = jest.fn()
  await signOutStudent(go)
  // Our local fallback did not run: the key is auth-js's business on success (here it is a stub).
  expect(localStorage.getItem(KEY)).toBe('{"access_token":"hers"}')
  expectHerDataGone()
  expect(go).toHaveBeenCalledWith('/')
})

it('anything a screen writes while the sign-out is in flight is wiped too', async () => {
  seed()
  mockOutcome = () => {
    localStorage.setItem('halatuju_grades', '{"BM":"A+"}')   // e.g. a sync landing mid-sign-out
    return Promise.resolve({ error: null })
  }
  await signOutStudent(jest.fn())
  expect(localStorage.getItem('halatuju_grades')).toBeNull()
})

// ── This tab's sessionStorage (Mobile M4 audit) ──────────────────────────────────────────────
// The apply form stashes the WHOLE form in sessionStorage for the "edit my results" round trip, and
// sign-out reloads the SAME tab — so the next student to sign in on a shared phone opened the form
// pre-filled with the last student's IC, income, parent phone and typed signature.
describe('sign-out also wipes this tab', () => {
  function seedTab() {
    sessionStorage.clear()
    sessionStorage.setItem(APPLY_STASH_KEY, '{"v":1,"uid":"u1","form":{"householdIncome":"2400"}}')
    sessionStorage.setItem('halatuju_apply_stash', '{"nric":"010101-14-1234"}')   // a pre-M4 tab's whole-form stash
    sessionStorage.setItem(APPLY_RETURN_KEY, '1')
    sessionStorage.setItem(APPLY_PROGRAMME_KEY, 'BP2026')
    sessionStorage.setItem(ONBOARDING_RETURN_KEY, '/scholarship/apply')
    sessionStorage.setItem('halatuju_list_nav:scholarship', '[1,2,3]')
    sessionStorage.setItem('halatuju_sponsor_pending', '{"name":"S"}')
    sessionStorage.setItem('other_tab_key', 'keeps')
  }

  it('removes her apply form and markers, keeps the admin and sponsor tab state', async () => {
    seed(); seedTab()
    await signOutStudent(() => {})
    for (const k of [APPLY_STASH_KEY, 'halatuju_apply_stash', APPLY_RETURN_KEY, APPLY_PROGRAMME_KEY, ONBOARDING_RETURN_KEY]) {
      expect(k.startsWith('halatuju_')).toBe(true)   // a renamed key without the prefix would escape the wipe
      expect(sessionStorage.getItem(k)).toBeNull()
    }
    expect(sessionStorage.getItem('halatuju_list_nav:scholarship')).toBe('[1,2,3]')
    expect(sessionStorage.getItem('halatuju_sponsor_pending')).toBe('{"name":"S"}')
    expect(sessionStorage.getItem('other_tab_key')).toBe('keeps')
  })

  it('wipes the tab even when the server sign-out fails', async () => {
    seed(); seedTab()
    mockOutcome = () => Promise.resolve({ error: new Error('network') })
    try {
      await signOutStudent(() => {})
    } finally {
      mockOutcome = () => Promise.resolve({ error: null })
    }
    expect(sessionStorage.getItem(APPLY_STASH_KEY)).toBeNull()
  })

  it('a session that ends WITHOUT the button wipes the tab but never her grades (a signed-out visitor keeps them)', () => {
    seed(); seedTab()
    clearStudentTab()
    expect(sessionStorage.getItem(APPLY_STASH_KEY)).toBeNull()
    expect(sessionStorage.getItem('halatuju_list_nav:scholarship')).toBe('[1,2,3]')
    expect(localStorage.getItem('halatuju_grades')).toBe('{"BM":"A"}')
  })

  // Mobile M4: the abandoned detour drops only the MARKER. Her draft stays — it is bound to her user id
  // and programme and expires in 24 h (applyDraft.test.ts), so it pre-fills nobody else's form, and a
  // trip to the dashboard must not throw her typing away. Sign-out and SIGNED_OUT still wipe it (above).
  it('an abandoned detour drops the return marker and keeps her (id-bound) draft', () => {
    seedTab()
    abandonApplyDetour()
    expect(sessionStorage.getItem(APPLY_STASH_KEY)).not.toBeNull()
    expect(sessionStorage.getItem(APPLY_RETURN_KEY)).toBeNull()
    expect(sessionStorage.getItem(APPLY_PROGRAMME_KEY)).toBe('BP2026')
  })
})

describe('the wiring (Mobile M4 audit)', () => {
  it('ANY sign-out event wipes this tab, not only the button', () => {
    const src = readWeb('src/lib/auth-context.tsx', 'the auth listener')
    expect(src).toMatch(/if \(event === 'SIGNED_OUT'\) \{[^}]*clearStudentTab\(\)/)
  })
  it('the dashboard drops an abandoned detour WITH its stashed form', () => {
    const src = readWeb('src/app/dashboard/page.tsx', 'the dashboard')
    expect(src).toMatch(/useEffect\(\(\) => \{ abandonApplyDetour\(\) \}, \[\]\)/)
  })
})
