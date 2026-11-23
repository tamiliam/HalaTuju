/**
 * @jest-environment jsdom
 *
 * Sponsor sign-in — a failed security check shows plain words (captcha repair, 2026-11-19).
 * The sign-in step offers Google, so its words add the "continue with Google" line; the reset
 * step has no Google button, so its words do not (review fix).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SponsorLoginPage from './page'

jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/messagesSponsor', () => ({}))
jest.mock('@/components/BrandLogo', () => () => null)
jest.mock('@/lib/oauthOrigin', () => ({ enforceCanonicalOrigin: jest.fn() }))
jest.mock('@/lib/sessionPolicy', () => ({
  enforceSingleScope: jest.fn().mockResolvedValue(undefined),
  consumeSuperseded: () => false,
}))
const signIn = jest.fn()
const resetPw = jest.fn()
jest.mock('@/lib/sponsor-supabase', () => ({
  sponsorSignInWithPassword: (...a: unknown[]) => signIn(...a),
  sponsorSignInWithGoogle: jest.fn(),
  sponsorResetPassword: (...a: unknown[]) => resetPw(...a),
}))

const blocked = { data: {}, error: { code: 'captcha_blocked', message: 'x', name: 'CaptchaError', status: 0 } }

beforeEach(() => { signIn.mockReset(); resetPw.mockReset() })

it('sign-in: the blocked words plus the Google line (Google is on screen)', async () => {
  signIn.mockResolvedValue(blocked)
  render(<SponsorLoginPage />)
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), { target: { value: 's@example.org' } })
  fireEvent.change(screen.getByPlaceholderText('sponsorAuth.enterPassword'), { target: { value: 'secret-pass' } })
  fireEvent.click(screen.getByRole('button', { name: 'sponsorAuth.signIn' }))
  await waitFor(() => expect(screen.getByText('sponsorAuth.captchaBlocked sponsorAuth.captchaGoogle')).toBeTruthy())
})

it('reset: the blocked words with NO Google line (no Google button on that step)', async () => {
  resetPw.mockResolvedValue(blocked)
  render(<SponsorLoginPage />)
  fireEvent.click(screen.getByRole('button', { name: 'sponsorAuth.forgotPassword' }))
  expect(screen.queryByRole('button', { name: /sponsorAuth.signInGoogle/ })).toBeNull()
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), { target: { value: 's@example.org' } })
  fireEvent.click(screen.getByRole('button', { name: 'sponsorAuth.sendResetLink' }))
  await waitFor(() => expect(screen.getByText('sponsorAuth.captchaBlocked')).toBeTruthy())
  expect(screen.queryByText(/errors\.captchaGoogle/)).toBeNull()
  expect(screen.queryByText(/captcha protection/)).toBeNull()
})
