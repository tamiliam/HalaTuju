/**
 * @jest-environment jsdom
 *
 * TD-458 (A1.9b) — the shared phone, when a session ends WITHOUT the sign-out button.
 *
 * (2) The grades and profile in localStorage are tagged with their owner's user id. Data tagged to
 *     another account is wiped (as the sign-out button would, keeping only the language) before the
 *     auth gate's sign-in sync could upload it into the next account. Untagged data is a signed-out
 *     visitor's own and still reaches their account, as before.
 * (1) The back button after a sign-out: a page restored from the back-forward cache for a session
 *     whose data is no longer on this browser reloads.
 *
 * Mounts the REAL AuthProvider, so the listener is the one every student route runs.
 */
import { act, render, waitFor } from '@testing-library/react'

import { AuthProvider } from '@/lib/auth-context'
import {
  KEY_GRADES, KEY_LOCALE, KEY_OWNER, KEY_PROFILE, KEY_REFERRAL_SOURCE, claimStudentData,
} from '@/lib/storage'

type Listener = (event: string, session: unknown) => void
let listener: Listener | null = null
let mockSession: unknown = null

jest.mock('next/navigation', () => ({ usePathname: () => '/dashboard' }))
jest.mock('@/lib/api', () => ({ getProfile: jest.fn(() => Promise.resolve({})) }))
jest.mock('@/lib/supabase', () => ({
  getSession: () => Promise.resolve({ session: mockSession }),
  signInAnonymously: jest.fn(() => Promise.resolve({ data: { session: null } })),
  getSupabase: () => ({
    auth: {
      onAuthStateChange: (cb: Listener) => {
        listener = cb
        return { data: { subscription: { unsubscribe: jest.fn() } } }
      },
    },
  }),
}))

const real = (id: string) => ({ access_token: `tkn-${id}`, user: { id, is_anonymous: false } })
const anon = { access_token: 'anon', user: { id: 'anon-1', is_anonymous: true } }

const holdGradesOf = (owner: string | null) => {
  localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))
  localStorage.setItem(KEY_PROFILE, JSON.stringify({ gender: 'female' }))
  localStorage.setItem(KEY_REFERRAL_SOURCE, 'partner-x')
  localStorage.setItem(KEY_LOCALE, 'ta')
  if (owner) localStorage.setItem(KEY_OWNER, owner)
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  listener = null
  mockSession = null
})

describe('claimStudentData', () => {
  it('wipes another owner\'s data, keeps the language, and tags the new owner', () => {
    holdGradesOf('user-a')
    sessionStorage.setItem('halatuju_apply_return', '1')
    claimStudentData('user-b')
    expect(localStorage.getItem(KEY_GRADES)).toBeNull()
    expect(localStorage.getItem(KEY_PROFILE)).toBeNull()
    expect(localStorage.getItem(KEY_REFERRAL_SOURCE)).toBeNull()
    expect(sessionStorage.getItem('halatuju_apply_return')).toBeNull()
    expect(localStorage.getItem(KEY_LOCALE)).toBe('ta')
    expect(localStorage.getItem(KEY_OWNER)).toBe('user-b')
  })

  it('an anonymous session drops tagged data and leaves no tag', () => {
    holdGradesOf('user-a')
    claimStudentData(null)
    expect(localStorage.getItem(KEY_GRADES)).toBeNull()
    expect(localStorage.getItem(KEY_OWNER)).toBeNull()
  })

  it('the same owner keeps everything', () => {
    holdGradesOf('user-a')
    claimStudentData('user-a')
    expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()
    expect(localStorage.getItem(KEY_OWNER)).toBe('user-a')
  })

  it('UNTAGGED data is a signed-out visitor\'s own: kept, and it now belongs to who signs in', () => {
    holdGradesOf(null)
    claimStudentData(null)
    expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()   // anonymous visitor: untouched
    claimStudentData('user-b')
    expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()   // goes up with the sign-in sync
    expect(localStorage.getItem(KEY_OWNER)).toBe('user-b')
  })

  it('never wipes the admin or sponsor sessions', () => {
    holdGradesOf('user-a')
    localStorage.setItem('halatuju_admin_session', 'adm')
    localStorage.setItem('halatuju_sponsor_session', 'sp')
    claimStudentData('user-b')
    expect(localStorage.getItem('halatuju_admin_session')).toBe('adm')
    expect(localStorage.getItem('halatuju_sponsor_session')).toBe('sp')
  })
})

describe('AuthProvider', () => {
  it('a page load with an anonymous session drops the last account\'s tagged grades', async () => {
    holdGradesOf('user-a')
    mockSession = anon
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(localStorage.getItem(KEY_GRADES)).toBeNull())
    expect(localStorage.getItem(KEY_LOCALE)).toBe('ta')
  })

  it('a page load with no session at all (offline) wipes nothing', async () => {
    holdGradesOf('user-a')
    mockSession = null
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(listener).not.toBeNull())
    await act(async () => { await Promise.resolve() })
    expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()
  })

  it('a SIGNED_IN of another account wipes A\'s data synchronously, before the sync can read it', async () => {
    mockSession = real('user-a')
    holdGradesOf('user-a')
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(listener).not.toBeNull())
    await act(async () => { listener!('SIGNED_IN', real('user-b')) })
    expect(localStorage.getItem(KEY_GRADES)).toBeNull()
    expect(localStorage.getItem(KEY_OWNER)).toBe('user-b')
  })

  it('a SIGNED_OUT (revoked, refreshed out) drops the tagged data', async () => {
    mockSession = real('user-a')
    holdGradesOf('user-a')
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(listener).not.toBeNull())
    await act(async () => { listener!('SIGNED_OUT', null) })
    expect(localStorage.getItem(KEY_GRADES)).toBeNull()
  })

  it('a token refresh for the same account touches nothing', async () => {
    mockSession = real('user-a')
    holdGradesOf('user-a')
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(listener).not.toBeNull())
    await act(async () => { listener!('TOKEN_REFRESHED', real('user-a')) })
    await act(async () => { listener!('SIGNED_IN', real('user-a')) })
    expect(localStorage.getItem(KEY_GRADES)).not.toBeNull()
  })
})

describe('the back-forward cache (pageshow)', () => {
  // jsdom cannot navigate: location.reload() reports "Not implemented: navigation" through
  // console.error instead of reloading. That report is how the test sees a reload was asked for.
  const reloads = (spy: jest.SpyInstance) =>
    spy.mock.calls.filter((c) => String(c[0]?.message ?? c[0]).includes('navigation')).length

  const showFromCache = (persisted: boolean) => {
    const e = new Event('pageshow') as Event & { persisted: boolean }
    Object.defineProperty(e, 'persisted', { value: persisted })
    window.dispatchEvent(e)
  }

  it('reloads a cached signed-in page once its data is no longer on this browser', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {})
    mockSession = real('user-a')
    render(<AuthProvider><div>app</div></AuthProvider>)
    await waitFor(() => expect(localStorage.getItem(KEY_OWNER)).toBe('user-a'))

    showFromCache(false)                       // an ordinary load: never
    showFromCache(true)                        // restored, still hers: no reload
    expect(reloads(spy)).toBe(0)

    localStorage.clear()                       // the sign-out button's clearAll
    showFromCache(true)
    expect(reloads(spy)).toBe(1)
    spy.mockRestore()
  })
})
