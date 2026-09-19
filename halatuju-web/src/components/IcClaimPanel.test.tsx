/**
 * @jest-environment jsdom
 *
 * TD-254 — the IC-claim step of the sign-in gate, rendered.
 *
 * What this pins, in order of how badly it would hurt:
 *
 *  1. **No holder is ever named.** The panel is not given one and renders none. A sentinel that
 *     no id, timestamp or i18n key could produce is asserted absent from the whole rendered
 *     tree, and a POSITIVE CONTROL proves the sentinel really does render when something asks
 *     for it — otherwise the absence assertion is passing on a string that never existed
 *     (docs/lessons.md, the H1 sentinel lesson). The leak's real entry point — a legacy server
 *     still sending `name` — is pinned next door in `AuthGateModal.claim.test.tsx`.
 *  2. The channels on offer are the ones the SERVER said, as bare types.
 *  3. Every refusal code maps to its own copy, and none of them is a blank panel.
 *  4. "This is not me" goes back to IC entry and sends nothing.
 *
 * `t` echoes its key (house style, as in `ScholarshipDocuments.test.tsx`), so assertions read
 * against i18n keys and copy changes cannot break this file. `fireEvent`, not `user-event`:
 * this project does not carry that dependency and the "no dead weight" standard means a test
 * may not add one.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import IcClaimPanel from './IcClaimPanel'
import * as api from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  sendClaimCode: jest.fn(),
  confirmClaimCode: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))

const mockApi = api as jest.Mocked<typeof api>

/** ⚠ A string no id, timestamp or i18n key can produce. */
const SENTINEL_HOLDER = 'QXSENTINELHOLDER ZZNAME'

const IC = '030303-14-9107'

let consoleErrors: unknown[][] = []
let realConsoleError: typeof console.error

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.sendClaimCode.mockResolvedValue({ status: 'sent', channel: 'email' })
  mockApi.confirmClaimCode.mockResolvedValue({ status: 'claimed' })
  consoleErrors = []
  realConsoleError = console.error
  console.error = (...args: unknown[]) => { consoleErrors.push(args) }
})

afterEach(() => {
  console.error = realConsoleError
  // A React warning is a real defect report; the cockpit harness treats one as a failure and so
  // does this file.
  expect(consoleErrors).toEqual([])
})

function mount(props: Partial<React.ComponentProps<typeof IcClaimPanel>> = {}) {
  const onClaimed = jest.fn()
  const onNotMe = jest.fn()
  render(
    <IcClaimPanel
      ic={IC}
      token="test-token"
      lang="en"
      channels={['phone', 'email']}
      onClaimed={onClaimed}
      onNotMe={onNotMe}
      {...props}
    />,
  )
  return { onClaimed, onNotMe }
}

const button = (name: string) => screen.getByRole('button', { name })

describe('it never names anybody', () => {
  it('renders no holder name', () => {
    mount({ channels: ['email'] })
    expect(screen.getByText('authGate.icExistsMessage')).toBeTruthy()
    expect(document.body.textContent).not.toContain(SENTINEL_HOLDER)
  })

  it('POSITIVE CONTROL: the sentinel does render when something actually asks for it', () => {
    render(<p>{SENTINEL_HOLDER}</p>)
    expect(document.body.textContent).toContain(SENTINEL_HOLDER)
  })

  it('takes no holder identity at all — the prop does not exist', () => {
    // The structural half: there is nothing to render because nothing is passed. Stated as a
    // test so a future prop called `name` has to argue with this line first.
    const props = Object.keys({
      ic: '', token: '', lang: '', channels: [], onClaimed: () => {}, onNotMe: () => {},
    } satisfies React.ComponentProps<typeof IcClaimPanel>)
    expect(props).not.toContain('name')
    expect(props.sort()).toEqual(
      ['channels', 'ic', 'lang', 'onClaimed', 'onNotMe', 'token'])
  })
})

describe('the channels on offer are the ones the server named', () => {
  it('offers both when both are verified', () => {
    mount({ channels: ['phone', 'email'] })
    expect(screen.getByText('authGate.claim.helpBoth')).toBeTruthy()
    expect(button('authGate.claim.channelPhone')).toBeTruthy()
    expect(button('authGate.claim.channelEmail')).toBeTruthy()
  })

  it('offers only the phone when only the phone is verified', () => {
    mount({ channels: ['phone'] })
    expect(screen.getByText('authGate.claim.helpPhone')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'authGate.claim.channelEmail' })).toBeNull()
  })

  it('offers only the email when only the email is verified', () => {
    mount({ channels: ['email'] })
    expect(screen.getByText('authGate.claim.helpEmail')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'authGate.claim.channelPhone' })).toBeNull()
  })

  it('offers no door at all when nothing on that profile is verified', () => {
    // ⚠ The 90% case (674 profiles hold an IC; 70 have a verified contact). The honest answer
    // is a human, not a button that cannot work.
    mount({ channels: [] })
    expect(screen.getByText('authGate.claim.refusal.noContact')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'authGate.claim.channelPhone' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'authGate.claim.channelEmail' })).toBeNull()
    expect(mockApi.sendClaimCode).not.toHaveBeenCalled()
  })
})

describe('the code round trip', () => {
  it('sends down the channel the student picked, then takes the code', async () => {
    mount({ channels: ['phone', 'email'] })
    fireEvent.click(button('authGate.claim.channelPhone'))
    await waitFor(() => expect(mockApi.sendClaimCode).toHaveBeenCalled())
    expect(mockApi.sendClaimCode.mock.calls[0][0]).toBe(IC)
    expect(mockApi.sendClaimCode.mock.calls[0][1]).toBe('phone')
    expect(await screen.findByText('authGate.claim.codeHelpPhone')).toBeTruthy()
  })

  it('a right code finishes the flow exactly as a claim used to', async () => {
    const { onClaimed } = mount({ channels: ['email'] })
    fireEvent.click(button('authGate.claim.channelEmail'))
    const box = await screen.findByLabelText('authGate.claim.codeLabel')
    fireEvent.change(box, { target: { value: '123456' } })
    fireEvent.click(button('authGate.claim.confirm'))
    await waitFor(() => expect(onClaimed).toHaveBeenCalled())
    expect(mockApi.confirmClaimCode.mock.calls[0][0]).toBe(IC)
    expect(mockApi.confirmClaimCode.mock.calls[0][1]).toBe('123456')
  })

  it('the code box takes digits only, and Confirm sleeps until there are six', async () => {
    mount({ channels: ['email'] })
    fireEvent.click(button('authGate.claim.channelEmail'))
    const box = await screen.findByLabelText('authGate.claim.codeLabel') as HTMLInputElement
    expect((button('authGate.claim.confirm') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(box, { target: { value: '12ab34' } })
    expect(box.value).toBe('1234')
    expect((button('authGate.claim.confirm') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(box, { target: { value: '123456' } })
    expect((button('authGate.claim.confirm') as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('every refusal says something true', () => {
  const ON_SEND: Array<[string, string]> = [
    ['no_verified_contact', 'authGate.claim.refusal.noContact'],
    ['caller_has_verified_nric', 'authGate.claim.refusal.cannotMerge'],
    ['caller_has_application', 'authGate.claim.refusal.cannotMerge'],
    ['already_claimed', 'authGate.claim.refusal.cannotMerge'],
    ['caller_is_staff', 'authGate.claim.refusal.cannotMerge'],
    ['channel_unavailable', 'authGate.claim.refusal.unavailable'],
    ['confirm_removed', 'authGate.claim.refusal.unavailable'],
    ['not_claimable', 'authGate.claim.refusal.unavailable'],
    ['rate_limited', 'authGate.claim.refusal.tooMany'],
    ['send_failed', 'authGate.claim.refusal.sendFailed'],
    ['unconfigured', 'authGate.claim.refusal.sendFailed'],
    ['a_code_from_the_future', 'authGate.claimError'],
  ]

  it.each(ON_SEND)('a %s on send reads as %s', async (code, key) => {
    mockApi.sendClaimCode.mockRejectedValueOnce(Object.assign(new Error('refused'), { code }))
    mount({ channels: ['email'] })
    fireEvent.click(button('authGate.claim.channelEmail'))
    expect(await screen.findByText(key)).toBeTruthy()
  })

  const ON_CONFIRM: Array<[string, string]> = [
    ['code_incorrect', 'authGate.claim.refusal.codeIncorrect'],
    ['code_expired', 'authGate.claim.refusal.codeExpired'],
    ['no_pending_code', 'authGate.claim.refusal.codeExpired'],
    ['code_required', 'authGate.claim.refusal.codeExpired'],
    ['too_many_attempts', 'authGate.claim.refusal.tooManyAttempts'],
  ]

  it.each(ON_CONFIRM)('a %s on confirm reads as %s, and claims nothing', async (code, key) => {
    mockApi.confirmClaimCode.mockRejectedValueOnce(
      Object.assign(new Error('refused'), { code }))
    const { onClaimed } = mount({ channels: ['email'] })
    fireEvent.click(button('authGate.claim.channelEmail'))
    const box = await screen.findByLabelText('authGate.claim.codeLabel')
    fireEvent.change(box, { target: { value: '000000' } })
    fireEvent.click(button('authGate.claim.confirm'))
    expect(await screen.findByText(key)).toBeTruthy()
    expect(onClaimed).not.toHaveBeenCalled()
  })
})

describe('"this is not me"', () => {
  it('goes back to IC entry and sends nothing', () => {
    const { onNotMe } = mount({ channels: ['email'] })
    fireEvent.click(button('authGate.icNotMe'))
    expect(onNotMe).toHaveBeenCalled()
    expect(mockApi.sendClaimCode).not.toHaveBeenCalled()
  })

  it('is offered even when there is no door', () => {
    const { onNotMe } = mount({ channels: [] })
    fireEvent.click(button('authGate.icNotMe'))
    expect(onNotMe).toHaveBeenCalled()
  })

  it('is offered from the code step too', async () => {
    const { onNotMe } = mount({ channels: ['email'] })
    fireEvent.click(button('authGate.claim.channelEmail'))
    await screen.findByLabelText('authGate.claim.codeLabel')
    fireEvent.click(button('authGate.icNotMe'))
    expect(onNotMe).toHaveBeenCalled()
  })
})
