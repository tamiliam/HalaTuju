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
