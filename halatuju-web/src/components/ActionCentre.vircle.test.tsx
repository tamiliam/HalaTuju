/**
 * @jest-environment jsdom
 *
 * V2a — THE VIRCLE SETUP CARD, MOUNTED.
 *
 * ⚠ THIS FILE REPLACES `ActionCentre.vircle.test.ts`, which read `ActionCentre.tsx` as SOURCE
 * TEXT. It settled for that because the component had never been rendered in a test; it asserted
 * things like `expect(SRC).toContain("disabled={!valid || !installed || busy}")`, which passes on
 * a file containing that exact string and says nothing about whether the button is ever actually
 * disabled. Every claim it made is re-made below from what a student can SEE and PRESS.
 *
 * What the card is for, and the three defects behind its rules:
 *
 *  * **The wallet-ID box is GONE (2026-09-09).** The eWallet ID arrives from Vircle's own
 *    Airtable callback AFTER the student confirms; typing it was the source of every wallet-id
 *    defect on record (DuitNow truncations, roll-over refusals). It must not come back "for
 *    completeness", so its absence is asserted, not assumed.
 *  * **The account-type self-check (owner, 2026-09-09).** The dropdown DEFAULTS to what Vircle's
 *    birth-year rule expects, and a disagreeing pick COACHES — it never blocks. An adult on a
 *    Child account is fine (the money goes to the parent's wallet and the parent passes it on);
 *    a minor cannot open a Parent account at all. Two directions, two different notes.
 *  * **The installed-and-registered tick (owner, 2026-09-10).** A real student confirmed here
 *    without ever registering in Vircle — "could not find his IC". The declaration is now an
 *    explicit checkbox, and the confirm must refuse without it: `disabled` alone is a style, so
 *    the handler's own guard is exercised by clicking the disabled button and asserting silence.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('./DocumentHelpCoach', () => ({
  __esModule: true, default: () => null, CoachCard: () => null,
}))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const VIRCLE_TASK = (expected: 'principal' | 'child' | null = 'principal'): ResolutionItem => ({
  id: 77, fact: 'other', code: 'vircle_setup_pending', params: {},
  prompt: 'Set up your Vircle wallet.', kind: 'confirm', doc_type: '', status: 'open',
  source: 'system', resolution_text: '', created_at: '2026-06-01T09:00:00.000Z',
  resolved_at: null, vircle_expected: expected,
})

/** Mount the Action Centre holding the one Vircle task, and wait for it to arrive. */
const mountVircle = async (expected: 'principal' | 'child' | null = 'principal') => {
  mockApi.getResolutionItems.mockResolvedValue({ open: [VIRCLE_TASK(expected)], resolved: [] })
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  const view = render(
    <ActionCentre token="test-token" studentName="Test Student 07" funded
      applicationId={7} contactPhone="0123456789" />)
  await screen.findByText('scholarship.actionCentre.vircle.title')
  return view
}

const confirmButton = () => screen.getByRole('button',
  { name: 'scholarship.actionCentre.vircle.confirm' }) as HTMLButtonElement
const tick = () => screen.getByRole('checkbox') as HTMLInputElement

beforeEach(() => jest.clearAllMocks())

describe('the card asks for the mobile and nothing else', () => {
  it('⚠ HAS NO WALLET-ID BOX', async () => {
    // The structural claim the old guard existed for, now asserted against the DOM instead of
    // against four strings that happened to be absent from the file.
    await mountVircle()
    const boxes = screen.getAllByRole('textbox') as HTMLInputElement[]
    expect(boxes).toHaveLength(1)
    expect(boxes[0].id).toBe('vircle-mobile')
    expect(screen.queryByLabelText(/wallet/i)).toBeNull()
  })

  it('pre-fills the mobile from the student’s own contact number', async () => {
    await mountVircle()
    expect((screen.getByLabelText('scholarship.actionCentre.vircle.mobile') as HTMLInputElement)
      .value).toBe('12-345 6789')
  })

  it('offers the way out for a student who is stuck', async () => {
    // A stuck student is looking at THIS card, not hunting back through their inbox.
    await mountVircle()
    for (const key of ['stuckTitle', 'stuckCard', 'stuckPhone', 'stuckSupport']) {
      expect(screen.getByText(`scholarship.actionCentre.vircle.${key}`)).toBeTruthy()
    }
  })
})

describe('the account-type self-check coaches, it never blocks', () => {
  it('defaults to what Vircle expects, and says nothing while they agree', async () => {
    await mountVircle('child')
    expect((screen.getByLabelText('scholarship.actionCentre.vircle.accountType') as
      HTMLSelectElement).value).toBe('child')
    expect(screen.queryByText(/scholarship\.actionCentre\.vircle\.warn/)).toBeNull()
  })

  it('an ADULT who picked Child is told how the money flows, not refused', async () => {
    // Owner, 2026-09-10: two real students run this way — the parent holds the wallet and
    // passes the money on. Never word this as a refusal.
    await mountVircle('principal')
    fireEvent.change(screen.getByLabelText('scholarship.actionCentre.vircle.accountType'),
                     { target: { value: 'child' } })
    expect(screen.getByText('scholarship.actionCentre.vircle.warnChildAdult')).toBeTruthy()
    fireEvent.click(tick())
    expect(confirmButton().disabled).toBe(false)     // coached, not blocked
  })

  it('a MINOR who picked Parent gets the other note', async () => {
    await mountVircle('child')
    fireEvent.change(screen.getByLabelText('scholarship.actionCentre.vircle.accountType'),
                     { target: { value: 'principal' } })
    expect(screen.getByText('scholarship.actionCentre.vircle.warnPrincipalMinor')).toBeTruthy()
  })
})

describe('the confirm will not run without the declaration', () => {
  it('⚠ IS REFUSED BY THE HANDLER, not only greyed out', async () => {
    // `disabled` is a style; a click that slips past it must still go nowhere.
    await mountVircle()
    expect(tick().checked).toBe(false)
    expect(confirmButton().disabled).toBe(true)
    fireEvent.click(confirmButton())
    expect(mockApi.resolveResolutionItem).not.toHaveBeenCalled()
  })

  it('is refused for an unusable mobile even once the box is ticked', async () => {
    await mountVircle()
    fireEvent.change(screen.getByLabelText('scholarship.actionCentre.vircle.mobile'),
                     { target: { value: '123' } })
    fireEvent.click(tick())
    expect(confirmButton().disabled).toBe(true)
    fireEvent.click(confirmButton())
    expect(mockApi.resolveResolutionItem).not.toHaveBeenCalled()
  })

  it('sends the mobile, the account type and the tick — and no wallet id', async () => {
    await mountVircle()
    fireEvent.click(tick())
    mockApi.resolveResolutionItem.mockResolvedValue(
      { ...VIRCLE_TASK(), status: 'resolved', resolved: true })
    mockApi.getResolutionItems.mockResolvedValue({ open: [], resolved: [] })
    fireEvent.click(confirmButton())
    await waitFor(() => expect(mockApi.resolveResolutionItem).toHaveBeenCalledWith(
      77, '+60123456789', { token: 'test-token' }, undefined, undefined, 'principal', true))
    // The success state: the task is gone from the queue.
    await waitFor(() =>
      expect(screen.queryByText('scholarship.actionCentre.vircle.title')).toBeNull())
  })
})

/**
 * The retired strings, checked in the CATALOGUES rather than in the component — a key nobody
 * references is still a key somebody re-wires. Imported rather than read off disk, so this file
 * is not a source-text guard.
 */
describe('the wallet-ID strings are gone from all three locales', () => {
  const locales = {
    en: jest.requireActual('@/messages/en.json') as Record<string, unknown>,
    ms: jest.requireActual('@/messages/ms.json') as Record<string, unknown>,
    ta: jest.requireActual('@/messages/ta.json') as Record<string, unknown>,
  }
  const vircle = (loc: Record<string, unknown>) => {
    const scholarship = loc.scholarship as { actionCentre?: { vircle?: Record<string, unknown> } }
    return scholarship?.actionCentre?.vircle ?? {}
  }

  it.each(Object.keys(locales) as Array<keyof typeof locales>)(
    '%s carries the declaration and none of the retired wallet-ID keys', (name) => {
      const keys = vircle(locales[name])
      expect(typeof keys.installedDeclare).toBe('string')
      for (const gone of ['walletId', 'walletIdHint', 'walletIdEcho', 'walletIdCheck',
                          'errorDuitnow']) {
        expect(keys).not.toHaveProperty(gone)
      }
    })
})
