/**
 * @jest-environment jsdom
 *
 * Admin sign-in → where the owed-password-change flag is READ (TD-322, review F4d).
 *
 * The server writes `must_change_password` to `app_metadata` (only the service role can); any
 * signed-in browser can rewrite `user_metadata`. So the page must follow `app_metadata` whenever it
 * carries the flag, and fall back to `user_metadata` only for an account no server writer has
 * touched since the move. The api's set-password gate decides for itself; this pins the routing.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AdminLoginPage from './page'

const push = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push, replace: jest.fn() }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/BrandLogo', () => () => null)
jest.mock('@/lib/oauthOrigin', () => ({ enforceCanonicalOrigin: jest.fn() }))
jest.mock('@/lib/sessionPolicy', () => ({
  enforceSingleScope: jest.fn().mockResolvedValue(undefined),
  consumeSuperseded: () => false,
}))
const signIn = jest.fn()
const signOut = jest.fn().mockResolvedValue(undefined)
jest.mock('@/lib/admin-supabase', () => ({
  adminSignInWithPassword: (...a: unknown[]) => signIn(...a),
  adminSignInWithGoogle: jest.fn(),
  adminResetPassword: jest.fn(),
  adminSignOut: () => signOut(),
}))

const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString()

function signInAs(user: { app_metadata?: object; user_metadata?: object }) {
  signIn.mockResolvedValue({ data: { session: { access_token: 'tok', user } }, error: null })
}

async function submit() {
  render(<AdminLoginPage />)
  fireEvent.change(screen.getByPlaceholderText('admin@organisation.com'),
    { target: { value: 'a@example.org' } })
  fireEvent.change(screen.getByPlaceholderText('admin.enterPassword'),
    { target: { value: 'secret-pass' } })
  fireEvent.click(screen.getByRole('button', { name: 'admin.signIn' }))
}

beforeEach(() => {
  push.mockReset(); signIn.mockReset(); signOut.mockClear()
  global.fetch = jest.fn().mockResolvedValue({
    json: async () => ({ is_admin: true, role: 'org_admin', temp_password_ttl_days: 7 }),
  }) as unknown as typeof fetch
})

describe('admin sign-in reads the owed-password flag from app_metadata first (TD-322)', () => {
  it('sends a server-flagged account to set its password', async () => {
    signInAs({ app_metadata: { must_change_password: true, temp_password_issued_at: daysAgo(1) } })
    await submit()
    await waitFor(() => expect(push).toHaveBeenCalledWith('/admin/set-password'))
  })

  it('ignores a flag the browser wrote when app_metadata says it is done', async () => {
    signInAs({
      app_metadata: { must_change_password: false },
      user_metadata: { must_change_password: true, temp_password_issued_at: daysAgo(1) },
    })
    await submit()
    await waitFor(() => expect(push).toHaveBeenCalled())
    expect(push).not.toHaveBeenCalledWith('/admin/set-password')
  })

  it('falls back to user_metadata only when app_metadata carries no flag', async () => {
    signInAs({
      app_metadata: { provider: 'email' },
      user_metadata: { must_change_password: true, temp_password_issued_at: daysAgo(1) },
    })
    await submit()
    await waitFor(() => expect(push).toHaveBeenCalledWith('/admin/set-password'))
  })

  it('refuses an unchanged temp password past the served TTL, read from app_metadata', async () => {
    signInAs({ app_metadata: { must_change_password: true, temp_password_issued_at: daysAgo(10) } })
    await submit()
    await waitFor(() => expect(screen.getByText('errors.tempPasswordExpired')).toBeTruthy())
    expect(signOut).toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
  })
})
