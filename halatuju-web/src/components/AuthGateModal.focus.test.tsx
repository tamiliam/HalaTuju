/**
 * @jest-environment jsdom
 *
 * Mobile M1b review — the sign-in gate opens with focus on GOOGLE, not the phone box.
 *
 * The shared Sheet focuses the first field in its body unless told otherwise. In the gate that is
 * the phone number box — but phone sign-in is off (`signInWithPhone` only says "coming soon"), and
 * on a phone a focused field raises the keyboard, which shrinks the sheet and pushes the Google
 * button, the one way in that works, out of view. Before the Sheet, nothing was focused.
 *
 * `t` echoes its key.
 */
import { render, screen, waitFor } from '@testing-library/react'

import AuthGateModal from './AuthGateModal'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/search',
}))
jest.mock('@/lib/supabase', () => ({
  signInWithPhone: jest.fn(), verifyOTP: jest.fn(), signInWithGoogle: jest.fn(),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  claimNric: jest.fn(),
  syncProfile: jest.fn(() => Promise.resolve({})),
  getProfile: jest.fn(() => Promise.resolve({})),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({
    authGateReason: 'save',
    authGateCourseId: null,
    hideAuthGate: jest.fn(),
    isAuthenticated: false,         // a visitor: the gate shows its sign-in step
    isAnonymous: true,
    token: null,
    session: null,
    status: 'ready',
    profile: null,
    refreshProfile: jest.fn(() => Promise.resolve()),
  }),
}))

test('the gate opens with focus on the Google button, not the phone field', async () => {
  render(<AuthGateModal />)
  const google = await screen.findByRole('button', { name: /authGate\.googleLogin/ })
  await waitFor(() => expect(document.activeElement).toBe(google))
  expect(document.activeElement?.getAttribute('type')).not.toBe('tel')
})
