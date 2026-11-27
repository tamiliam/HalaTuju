/**
 * @jest-environment jsdom
 *
 * #86 (review round 2): the Google sign-in comes back to `/admin/auth/callback`, which takes the page
 * the login was sent from out of this tab's sessionStorage ONCE per mount — so every path clears it,
 * a bad stored value falls back to the landing, and the dev StrictMode second effect run still lands
 * on the remembered case.
 */
import { StrictMode } from 'react'
import { render, waitFor } from '@testing-library/react'
import AdminAuthCallbackPage from './page'
import { adminLanding } from '@/lib/adminLanding'

const replace = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/oauthOrigin', () => ({ oauthOriginMismatchAtEntry: () => false }))
jest.mock('@/lib/sessionPolicy', () => ({ enforceSingleScope: jest.fn().mockResolvedValue(undefined) }))
let mockSession: object | null = null
jest.mock('@/lib/admin-supabase', () => ({
  ADMIN_STORAGE_KEY: 'test-admin',
  getAdminSupabase: () => ({
    auth: {
      getSession: async () => ({ data: { session: mockSession } }),
      exchangeCodeForSession: async () => ({ data: { session: null }, error: { message: 'invalid_grant' } }),
      signOut: jest.fn(),
    },
  }),
}))

const KEY = 'halatuju_admin_next'
const CASE = '/admin/scholarship/513'
const ROLE = { is_admin: true, role: 'org_admin' }

beforeEach(() => {
  replace.mockReset()
  window.sessionStorage.clear()
  mockSession = { access_token: 'tok' }
  global.fetch = jest.fn().mockResolvedValue({ json: async () => ROLE }) as unknown as typeof fetch
})

it('lands on the remembered case and clears it', async () => {
  window.sessionStorage.setItem(KEY, CASE)
  render(<AdminAuthCallbackPage />)
  await waitFor(() => expect(replace).toHaveBeenCalledWith(CASE))
  expect(window.sessionStorage.getItem(KEY)).toBeNull()
})

it('a bad stored value lands on the default', async () => {
  window.sessionStorage.setItem(KEY, '//evil.example')
  render(<AdminAuthCallbackPage />)
  await waitFor(() => expect(replace).toHaveBeenCalledWith(adminLanding(ROLE)))
  expect(replace).not.toHaveBeenCalledWith('//evil.example')
  expect(window.sessionStorage.getItem(KEY)).toBeNull()
})

it('a failed sign-in clears the remembered page too', async () => {
  mockSession = null
  window.history.pushState({}, '', '/admin/auth/callback?code=x')
  window.sessionStorage.setItem(KEY, CASE)
  const { findByText } = render(<AdminAuthCallbackPage />)
  await findByText('errors.authFailed')
  expect(window.sessionStorage.getItem(KEY)).toBeNull()
  expect(replace).not.toHaveBeenCalled()
  window.history.pushState({}, '', '/')
})

it('under StrictMode (the effect runs twice) every landing is the remembered case', async () => {
  window.sessionStorage.setItem(KEY, CASE)
  render(<StrictMode><AdminAuthCallbackPage /></StrictMode>)
  await waitFor(() => expect(replace).toHaveBeenCalledTimes(2))
  expect(replace.mock.calls.map((c) => c[0])).toEqual([CASE, CASE])
})
