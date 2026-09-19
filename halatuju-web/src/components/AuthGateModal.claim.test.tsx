/**
 * @jest-environment jsdom
 *
 * TD-254 — the sign-in gate's IC step, from the modal down.
 *
 * ⚠ **THE ONE ASSERTION THIS FILE EXISTS FOR:** a LEGACY SERVER still answering `exists` with
 * the holder's `name` must change nothing on the screen. The old build interpolated that name
 * into the confirm question; the new one has nowhere to put it. A deploy is two services, so
 * "the API stopped sending it" is not a guarantee the browser can lean on.
 *
 * The rest: the panel appears on `exists`, "this is not me" returns to IC entry, and a
 * successful claim resumes the flow exactly as `created`/`linked` do — which is what makes the
 * claim invisible to everything downstream.
 *
 * `t` echoes its key, so assertions read against i18n keys.
 */
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'

import AuthGateModal from './AuthGateModal'
import * as api from '@/lib/api'

/** ⚠ A string no id, timestamp or i18n key can produce. */
const SENTINEL_HOLDER = 'QXSENTINELHOLDER ZZNAME'
const IC = '030303-14-9107'

const push = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: (...a: unknown[]) => push(...a), replace: jest.fn() }),
  usePathname: () => '/dashboard',
}))
jest.mock('@/lib/supabase', () => ({
  signInWithPhone: jest.fn(), verifyOTP: jest.fn(), signInWithGoogle: jest.fn(),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  claimNric: jest.fn(),
  sendClaimCode: jest.fn(),
  confirmClaimCode: jest.fn(),
  syncProfile: jest.fn(() => Promise.resolve({})),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))

const hideAuthGate = jest.fn()
const refreshProfile = jest.fn(() => Promise.resolve())
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({
    authGateReason: 'profile',
    authGateCourseId: null,
    hideAuthGate: () => hideAuthGate(),
    isAuthenticated: false,
    isAnonymous: false,
    token: 'test-token',
    session: { user: { user_metadata: {} } },
    status: 'needs-nric',
    profile: null,
    refreshProfile: () => refreshProfile(),
  }),
}))

const mockApi = api as jest.Mocked<typeof api>

let consoleErrors: unknown[][] = []
let realConsoleError: typeof console.error

beforeEach(() => {
  jest.clearAllMocks()
  consoleErrors = []
  realConsoleError = console.error
  console.error = (...args: unknown[]) => { consoleErrors.push(args) }
  mockApi.sendClaimCode.mockResolvedValue({ status: 'sent', channel: 'email' })
  mockApi.confirmClaimCode.mockResolvedValue({ status: 'claimed' })
})

afterEach(() => {
  console.error = realConsoleError
  expect(consoleErrors).toEqual([])
})

const button = (name: string) => screen.getByRole('button', { name })

/** The IC box. ⚠ By PLACEHOLDER, not by label: `IcInput` draws its `<label>` without an
 *  `htmlFor`, so the two are not associated and `findByLabelText` cannot see it. */
const icBox = () => screen.findByPlaceholderText('XXXXXX-XX-XXXX')

/** Type the IC and submit the IC step. */
async function submitIc() {
  render(<AuthGateModal />)
  fireEvent.change(await icBox(), { target: { value: IC } })
  // ⚠ `act`, because the submit is ASYNC: the claim resolves and sets state after the click
  // returns, and an unwrapped update is a React warning — which this file treats as a failure.
  await act(async () => { fireEvent.click(button('authGate.icContinue')) })
}

describe('an IC that belongs to somebody else', () => {
  it('shows the claim panel and NAMES NOBODY — even if the server sends a name', async () => {
    // ⚠ The legacy shape, on purpose: `name` is exactly what the old API returned here.
    mockApi.claimNric.mockResolvedValue(
      { status: 'exists', channels: ['email'], name: SENTINEL_HOLDER } as
        Awaited<ReturnType<typeof api.claimNric>>)
    await submitIc()
    expect(await screen.findByText('authGate.icExistsMessage')).toBeTruthy()
    expect(document.body.textContent).not.toContain(SENTINEL_HOLDER)
  })

  it('POSITIVE CONTROL: that sentinel really was in the response the modal handled', async () => {
    mockApi.claimNric.mockResolvedValue(
      { status: 'exists', channels: ['email'], name: SENTINEL_HOLDER } as
        Awaited<ReturnType<typeof api.claimNric>>)
    await submitIc()
    await screen.findByText('authGate.icExistsMessage')
    const answered = await mockApi.claimNric.mock.results[0].value
    expect(JSON.stringify(answered)).toContain(SENTINEL_HOLDER)
  })

  it('never posts confirm: true — the takeover door is not called at all', async () => {
    mockApi.claimNric.mockResolvedValue({ status: 'exists', channels: ['email'] })
    await submitIc()
    await screen.findByText('authGate.icExistsMessage')
    expect(mockApi.claimNric).toHaveBeenCalledTimes(1)
    expect(mockApi.claimNric.mock.calls[0][1]).toBe(false)
  })

  it('"this is not me" returns to IC entry', async () => {
    mockApi.claimNric.mockResolvedValue({ status: 'exists', channels: ['email'] })
    await submitIc()
    fireEvent.click(await screen.findByRole('button', { name: 'authGate.icNotMe' }))
    expect(await icBox()).toBeTruthy()
    expect(screen.queryByText('authGate.icExistsMessage')).toBeNull()
  })

  it('a completed claim resumes the flow exactly as a plain sign-in does', async () => {
    mockApi.claimNric.mockResolvedValue({ status: 'exists', channels: ['email'] })
    await submitIc()
    const send = await screen.findByRole('button', { name: 'authGate.claim.channelEmail' })
    await act(async () => { fireEvent.click(send) })
    const box = await screen.findByLabelText('authGate.claim.codeLabel')
    fireEvent.change(box, { target: { value: '123456' } })
    await act(async () => { fireEvent.click(button('authGate.claim.confirm')) })
    await waitFor(() => expect(hideAuthGate).toHaveBeenCalled())
    expect(refreshProfile).toHaveBeenCalled()
    expect(mockApi.syncProfile).toHaveBeenCalled()
  })
})

describe('an IC that is free, or already the caller’s', () => {
  it.each(['created', 'linked'] as const)('%s closes the gate without a panel', async (status) => {
    mockApi.claimNric.mockResolvedValue({ status })
    await submitIc()
    await waitFor(() => expect(hideAuthGate).toHaveBeenCalled())
    expect(screen.queryByText('authGate.icExistsMessage')).toBeNull()
  })

  it('a refused look-up reads as copy, never as a raw key', async () => {
    mockApi.claimNric.mockRejectedValue(
      Object.assign(new Error('refused'), { code: 'nric_locked' }))
    await submitIc()
    expect(await screen.findByText('authGate.icError')).toBeTruthy()
  })
})
