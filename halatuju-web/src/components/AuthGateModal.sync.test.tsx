/**
 * @jest-environment jsdom
 *
 * TD-069 review F2 — the sign-in gate SENDS what the login hydrate is about to overwrite.
 *
 * The race: a student enters SPM prerequisites on device B, signed out, then signs in. The
 * provider's hydrate writes the server's copies (device A's, older) into localStorage on every
 * sign-in. The gate's sync reads localStorage FIRST — so whatever it sends reaches the server, and
 * whatever it leaves out is silently replaced by device A's copy. Before the fix it left out the
 * STPM path's three fields (and v2.21.0's `elective_subjects`).
 *
 * `t` echoes its key.
 */
import { render, waitFor } from '@testing-library/react'

import AuthGateModal from './AuthGateModal'
import * as api from '@/lib/api'
import {
  KEY_ELEKTIF, KEY_GRADES, KEY_SPM_ELEKTIF, KEY_SPM_PREREQ, KEY_SPM_STREAM,
} from '@/lib/storage'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/dashboard',
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
    authGateReason: 'save',
    authGateCourseId: null,
    hideAuthGate: jest.fn(),
    isAuthenticated: true,          // a RETURNING user: the gate syncs and closes
    isAnonymous: false,
    token: 'tkn',
    session: { user: { user_metadata: {} } },
    status: 'ready',
    profile: null,
    refreshProfile: jest.fn(() => Promise.resolve()),
  }),
}))

const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  localStorage.clear()
  jest.clearAllMocks()
})

it("sends this device's STPM-path SPM prerequisites before the hydrate can replace them", async () => {
  const fresh = { bm: 'A+', eng: 'A', hist: 'A', math: 'A', ekonomi: 'A', geo: 'B+' }
  localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(fresh))
  localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(['ekonomi', 'geo']))
  localStorage.setItem(KEY_SPM_STREAM, 'arts')
  localStorage.setItem(KEY_ELEKTIF, JSON.stringify(['poa']))
  localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))

  render(<AuthGateModal />)

  await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
  const sent = mockApi.syncProfile.mock.calls[0][0]
  expect(sent.spm_prereq_grades).toEqual(fresh)
  expect(sent.spm_elective_subjects).toEqual(['ekonomi', 'geo'])
  expect(sent.spm_stream).toBe('arts')
  expect(sent.elective_subjects).toEqual(['poa'])
  // positive control: the fields the gate always sent are still sent
  expect(sent.grades).toEqual({ bm: 'A' })
})

it('sends none of them when this device never entered any', async () => {
  localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))
  render(<AuthGateModal />)
  await waitFor(() => expect(mockApi.syncProfile).toHaveBeenCalled())
  const sent = mockApi.syncProfile.mock.calls[0][0]
  expect(sent).not.toHaveProperty('spm_prereq_grades')
  expect(sent).not.toHaveProperty('spm_elective_subjects')
  expect(sent).not.toHaveProperty('spm_stream')
  expect(sent.grades).toEqual({ bm: 'A' })
})
