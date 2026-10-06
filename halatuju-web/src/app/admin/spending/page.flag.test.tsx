/**
 * @jest-environment jsdom
 *
 * Flag a shop for review, with a notes log (request #28 follow-up, 2026-10-06) — mounted through
 * the REAL spending page, because the subject is behaviour: a click opens a dialog, focus moves,
 * Escape closes, a filter narrows. Written from the harm:
 *
 *  * `a modal, outside the table` — `TableFrame` clips, so a popover inside a row would be sliced
 *    off (the Intake years defect). The dialog must not be a descendant of the table.
 *  * `a note is required, and clearing needs one too` — a flag says why; so does clearing it.
 *  * `the page re-reads after a change` — the filled flag and "Flagged only" must agree with the log.
 *  * `flagged only` — the filter narrows to this organisation's flagged shops.
 *
 * ⚠ The dialog is a LAZY chunk (`LazyMerchantFlagDialog`), so every wait is a `findBy`.
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import SpendingPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (merchant: string, flagged: boolean): api.SpendingMerchantRow => ({
  merchant, category: 'food', decided_by: 'rule', visits: 2, total: '20.00',
  last_seen: '2026-08-30', held_back: 0, decided_at: '2026-09-01T00:00:00Z', flagged,
})

const OVERVIEW: api.SpendingOverview = {
  totals: { spent: '40.00', placed: '40.00', unplaced: '0.00', placed_pct: 100, merchants_to_check: 0 },
  merchants: [row('PLAIN STALL', false), row('WATCHED STALL', true)],
  students: [],
  wallet_gaps: { unseen_students: [], shared_wallets: {}, data_to: '2026-08-31' },
  categories: [{ code: 'food', label: 'Food & drink' }, { code: 'unsorted', label: 'Not yet sorted' }],
}

const OPEN_NOTE = { kind: 'open' as const, body: 'Looks like a person, not a shop.',
                    author: 'a@example.test', at: '2026-10-01T09:00:00Z' }
const LATER_NOTE = { kind: 'note' as const, body: 'Asked the student.',
                     author: 'b@example.test', at: '2026-10-02T10:00:00Z' }

/** The flag buttons for one shop — one in the phone card, one in the desktop row. */
const flagsOf = (shop: string) => screen.findAllByRole('button', {
  name: (n: string) => n.startsWith(`admin.spending.flag.col — ${shop}`),
})

/** Is this button switched off? (No jest-dom here, so the property is read directly.) */
const off = (el: HTMLElement) => (el as HTMLButtonElement).disabled

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSpendingOverview.mockResolvedValue(OVERVIEW)
  mockApi.getMerchantFlag.mockResolvedValue({ merchant: 'PLAIN STALL', flagged: false, notes: [] })
})

describe('the flag button', () => {
  it('is on every shop in BOTH renderings, names the shop, and is filled when flagged', async () => {
    render(<SpendingPage />)
    const plain = await flagsOf('PLAIN STALL')
    const watched = await flagsOf('WATCHED STALL')
    expect(plain).toHaveLength(2)
    expect(watched).toHaveLength(2)
    for (const b of watched) {
      expect(b.getAttribute('aria-label')).toBe(
        'admin.spending.flag.col — WATCHED STALL (admin.spending.flag.opened)')
      expect(b.querySelector('svg')?.getAttribute('fill')).toBe('currentColor')
    }
    for (const b of plain) {
      expect(b.getAttribute('aria-label')).toBe('admin.spending.flag.col — PLAIN STALL')
      expect(b.querySelector('svg')?.getAttribute('fill')).toBe('none')
    }
  })
})

describe('flagging a shop', () => {
  it('opens a MODAL outside the table; Flag waits for a note, then sends it and re-reads', async () => {
    mockApi.changeMerchantFlag.mockResolvedValue({
      merchant: 'PLAIN STALL', flagged: true, notes: [{ ...OPEN_NOTE, body: 'why' }] })
    render(<SpendingPage />)
    fireEvent.click((await flagsOf('PLAIN STALL'))[1])
    const dialog = await screen.findByRole('dialog', { name: 'admin.spending.flag.col — PLAIN STALL' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(dialog.closest('table')).toBeNull()           // ⚠ TableFrame clips; this cannot be
    await waitFor(() => expect(mockApi.getMerchantFlag)
      .toHaveBeenCalledWith('PLAIN STALL', undefined, { token: 'tok' }))
    const flag = await within(dialog).findByRole('button', { name: 'admin.spending.flag.col' })
    expect(off(flag)).toBe(true)                          // no note, no flag
    const note = within(dialog).getByRole('textbox', { name: 'common.note' })
    expect(document.activeElement).toBe(note)            // focus went into the dialog
    fireEvent.change(note, { target: { value: '   ' } })
    expect(off(flag)).toBe(true)                          // blank is not a note
    fireEvent.change(note, { target: { value: '  why  ' } })
    expect(off(flag)).toBe(false)
    const readsBefore = mockApi.getSpendingOverview.mock.calls.length
    fireEvent.click(flag)
    await waitFor(() => expect(mockApi.changeMerchantFlag)
      .toHaveBeenCalledWith('PLAIN STALL', 'open', 'why', undefined, { token: 'tok' }))
    expect(await within(dialog).findByText('why')).not.toBeNull()
    await waitFor(() => expect(mockApi.getSpendingOverview.mock.calls.length)
      .toBeGreaterThan(readsBefore))
  })

  it('shows a flagged shop’s log, adds a note, and will not clear without a closing note', async () => {
    mockApi.getMerchantFlag.mockResolvedValue({
      merchant: 'WATCHED STALL', flagged: true, notes: [OPEN_NOTE, LATER_NOTE] })
    mockApi.changeMerchantFlag.mockResolvedValue({
      merchant: 'WATCHED STALL', flagged: false, notes: [OPEN_NOTE, LATER_NOTE,
        { ...OPEN_NOTE, kind: 'close', body: 'Her aunt’s stall; fine.' }] })
    render(<SpendingPage />)
    fireEvent.click((await flagsOf('WATCHED STALL'))[0])
    const dialog = await screen.findByRole('dialog')
    const log = await within(dialog).findByTestId('flag-log')
    const entries = within(log).getAllByRole('listitem')
    // Oldest first, each with what it was, who wrote it and the note.
    expect(entries.map((e) => e.textContent)).toEqual([
      expect.stringContaining('admin.spending.flag.opened'),
      expect.stringContaining('common.note'),
    ])
    expect(entries[0].textContent).toContain('a@example.test')
    expect(entries[0].textContent).toContain(OPEN_NOTE.body)
    expect(entries[1].textContent).toContain(LATER_NOTE.body)

    const clear = within(dialog).getByRole('button', { name: 'admin.spending.flag.clear' })
    const save = within(dialog).getByRole('button', { name: 'common.save' })
    expect(within(dialog).queryByRole('button', { name: 'admin.spending.flag.col' })).toBeNull()
    expect(off(clear)).toBe(true)                         // ⚠ clearing REQUIRES a closing note
    expect(off(save)).toBe(true)
    fireEvent.click(clear)
    expect(mockApi.changeMerchantFlag).not.toHaveBeenCalled()
    fireEvent.change(within(dialog).getByRole('textbox', { name: 'common.note' }),
                     { target: { value: 'Her aunt’s stall; fine.' } })
    fireEvent.click(clear)
    await waitFor(() => expect(mockApi.changeMerchantFlag).toHaveBeenCalledWith(
      'WATCHED STALL', 'close', 'Her aunt’s stall; fine.', undefined, { token: 'tok' }))
    // The closing note joins the log; a cleared flag offers Flag again (it reopens the same one).
    expect(await within(dialog).findByText('admin.spending.flag.closed')).not.toBeNull()
    expect(within(dialog).getByRole('button', { name: 'admin.spending.flag.col' })).not.toBeNull()
  })

  it('adds a note to an open flag with Save', async () => {
    mockApi.getMerchantFlag.mockResolvedValue({
      merchant: 'WATCHED STALL', flagged: true, notes: [OPEN_NOTE] })
    mockApi.changeMerchantFlag.mockResolvedValue({
      merchant: 'WATCHED STALL', flagged: true, notes: [OPEN_NOTE, LATER_NOTE] })
    render(<SpendingPage />)
    fireEvent.click((await flagsOf('WATCHED STALL'))[0])
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findByTestId('flag-log')
    fireEvent.change(within(dialog).getByRole('textbox', { name: 'common.note' }),
                     { target: { value: 'Asked the student.' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(mockApi.changeMerchantFlag).toHaveBeenCalledWith(
      'WATCHED STALL', 'note', 'Asked the student.', undefined, { token: 'tok' }))
  })

  it('Escape closes it and gives focus back to the flag that opened it', async () => {
    render(<SpendingPage />)
    const button = (await flagsOf('PLAIN STALL'))[1]
    button.focus()
    fireEvent.click(button)
    const dialog = await screen.findByRole('dialog')
    await waitFor(() => expect(document.activeElement).not.toBe(button))
    fireEvent.keyDown(within(dialog).getByRole('textbox', { name: 'common.note' }),
                      { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(document.activeElement).toBe(button)
  })

  it('says so when the server refuses', async () => {
    mockApi.changeMerchantFlag.mockRejectedValue(
      Object.assign(new Error('unknown_merchant'), { code: 'unknown_merchant' }))
    render(<SpendingPage />)
    fireEvent.click((await flagsOf('PLAIN STALL'))[0])
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findByRole('button', { name: 'admin.spending.flag.col' })
    fireEvent.change(within(dialog).getByRole('textbox', { name: 'common.note' }),
                     { target: { value: 'n' } })
    await waitFor(() => expect(off(within(dialog).getByRole('button', { name: 'admin.spending.flag.col' })))
      .toBe(false))
    fireEvent.click(within(dialog).getByRole('button', { name: 'admin.spending.flag.col' }))
    expect((await within(dialog).findByRole('alert')).textContent)
      .toBe('admin.spending.error.unknown_merchant')
  })
})

describe('"Flagged only"', () => {
  it('narrows the list to the flagged shops, in both renderings, and clears back', async () => {
    render(<SpendingPage />)
    await flagsOf('PLAIN STALL')
    fireEvent.click(screen.getByRole('checkbox', { name: 'admin.spending.flag.only' }))
    expect(screen.queryAllByText('PLAIN STALL')).toHaveLength(0)
    expect(screen.getAllByText('WATCHED STALL')).toHaveLength(2)
    fireEvent.click(screen.getByRole('button', { name: 'admin.spending.filter.clear' }))
    expect(screen.getAllByText('PLAIN STALL')).toHaveLength(2)
  })
})
