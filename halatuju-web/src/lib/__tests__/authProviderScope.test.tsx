/**
 * @jest-environment jsdom
 *
 * TD-182: the STUDENT auth stack must not run on the privileged consoles.
 *
 * The bug this pins: the student AuthProvider is mounted globally, so on
 * `/admin/auth/callback` it created the student supabase client, whose `detectSessionInUrl`
 * (on by default) claimed the `?code=` intended for the admin client. It holds no matching
 * PKCE verifier — the verifier is stored per storageKey — so the exchange failed, the
 * single-use code was burned, and the admin callback found no session. It then signed the
 * visitor in ANONYMOUSLY on an admin page for good measure.
 *
 * Whichever client initialises first wins, which is why this reproduced on a local origin and
 * not in production. A race is not a guarantee, so it is pinned here rather than left to luck.
 */
import { render } from '@testing-library/react'

import { AuthProvider } from '@/lib/auth-context'

let mockPath = '/'
jest.mock('next/navigation', () => ({
  usePathname: () => mockPath,
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))

const getSession = jest.fn(() => Promise.resolve({ session: null }))
const signInAnonymously = jest.fn(() => Promise.resolve({ data: { session: null } }))
const onAuthStateChange = jest.fn(() => ({ data: { subscription: { unsubscribe: jest.fn() } } }))

jest.mock('@/lib/supabase', () => ({
  getSession: () => getSession(),
  signInAnonymously: () => signInAnonymously(),
  getSupabase: () => ({ auth: { onAuthStateChange: () => onAuthStateChange() } }),
}))
jest.mock('@/lib/api', () => ({ getProfile: jest.fn(() => Promise.resolve({ nric: null })) }))

beforeEach(() => {
  getSession.mockClear()
  signInAnonymously.mockClear()
  onAuthStateChange.mockClear()
})

const mount = (path: string) => {
  mockPath = path
  render(<AuthProvider><div>page</div></AuthProvider>)
}

describe('the student AuthProvider stays out of the privileged consoles', () => {
  it.each(['/admin', '/admin/auth/callback', '/admin/scholarship', '/sponsor', '/sponsor/students'])(
    'touches no student auth on %s', (path) => {
      mount(path)
      // The decisive assertion: nothing here may create or use the student supabase client,
      // because creating it is what consumes the admin callback's ?code=.
      expect(getSession).not.toHaveBeenCalled()
      expect(onAuthStateChange).not.toHaveBeenCalled()
      // and no anonymous student session is minted on an admin page
      expect(signInAnonymously).not.toHaveBeenCalled()
    })

  it.each(['/', '/dashboard', '/scholarship/apply', '/search'])(
    'still bootstraps normally on the student route %s', (path) => {
      mount(path)
      expect(getSession).toHaveBeenCalled()
      expect(onAuthStateChange).toHaveBeenCalled()
    })

  it('does not treat a lookalike path as privileged', () => {
    // Guard against a careless `includes('/admin')` rewrite later.
    mount('/administrivia')
    expect(getSession).toHaveBeenCalled()
  })
})
