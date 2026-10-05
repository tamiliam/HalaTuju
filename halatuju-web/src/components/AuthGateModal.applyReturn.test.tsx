/**
 * @jest-environment jsdom
 *
 * "Apply gift clarity" D3 (2026-10-05) — the sign-in gate opened from the apply form sends the
 * student back to the form FOR THE SAME GIFT.
 *
 * A bare `/scholarship/apply` now asks afresh which gift (it used to reuse a code stored by any
 * earlier visit in the tab). So this legitimate round trip carries the code in the URL instead.
 * The Google path through `/auth/callback` is pinned next door in `app/auth/callback/page.test.tsx`.
 *
 * `t` echoes its key.
 */
import { render, waitFor } from '@testing-library/react'

import AuthGateModal from './AuthGateModal'
import { APPLY_PROGRAMME_KEY } from '@/lib/applyReturn'

const mockPush = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  usePathname: () => '/scholarship/apply',
}))
jest.mock('@/lib/supabase', () => ({
  signInWithPhone: jest.fn(), verifyOTP: jest.fn(), signInWithGoogle: jest.fn(),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  claimNric: jest.fn(),
  syncProfile: jest.fn(() => Promise.resolve({})),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({
    authGateReason: 'apply',
    authGateCourseId: null,
    hideAuthGate: jest.fn(),
    isAuthenticated: true,          // a RETURNING user: the gate syncs and closes at once
    isAnonymous: false,
    token: 'tkn',
    session: { user: { user_metadata: {} } },
    status: 'ready',
    profile: null,
    refreshProfile: jest.fn(() => Promise.resolve()),
  }),
}))

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  jest.clearAllMocks()
})

it('returns to the apply form carrying the gift the student arrived for', async () => {
  sessionStorage.setItem(APPLY_PROGRAMME_KEY, 'sabah')
  render(<AuthGateModal />)
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/scholarship/apply?p=sabah'))
})

it('returns to a bare form when no gift was named (the chooser then asks)', async () => {
  render(<AuthGateModal />)
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/scholarship/apply'))
})
