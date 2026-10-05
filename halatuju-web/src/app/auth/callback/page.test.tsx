/**
 * @jest-environment jsdom
 *
 * "Apply gift clarity" D3 (2026-10-05) — after Google sign-in from the apply form, `/auth/callback`
 * sends the student back to the form FOR THE SAME GIFT.
 *
 * The gift's code survives the Google redirect in sessionStorage (same tab), but a bare
 * `/scholarship/apply` now asks afresh, so the callback puts the code back in the URL.
 */
import { render, waitFor } from '@testing-library/react'

import AuthCallback from './page'
import { APPLY_PROGRAMME_KEY } from '@/lib/applyReturn'
import { KEY_PENDING_AUTH_ACTION } from '@/lib/storage'

const mockReplace = jest.fn()
const mockRouter = { push: jest.fn(), replace: mockReplace }
jest.mock('next/navigation', () => ({ useRouter: () => mockRouter }))
jest.mock('@/lib/supabase', () => ({
  getSession: jest.fn(() => Promise.resolve({ session: { user: {} } })),
}))

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  jest.clearAllMocks()
})

it('an apply sign-in returns to the form with the gift it started from', async () => {
  localStorage.setItem(KEY_PENDING_AUTH_ACTION, JSON.stringify({ reason: 'apply' }))
  sessionStorage.setItem(APPLY_PROGRAMME_KEY, 'sabah')
  render(<AuthCallback />)
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/scholarship/apply?p=sabah'),
    { timeout: 3000 })
})

it('an apply sign-in with no gift named returns to the bare form', async () => {
  localStorage.setItem(KEY_PENDING_AUTH_ACTION, JSON.stringify({ reason: 'apply' }))
  render(<AuthCallback />)
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/scholarship/apply'), { timeout: 3000 })
})

it('any other sign-in still lands on the dashboard (control)', async () => {
  sessionStorage.setItem(APPLY_PROGRAMME_KEY, 'sabah')
  render(<AuthCallback />)
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/dashboard'), { timeout: 3000 })
})
