/**
 * @jest-environment jsdom
 *
 * The officer's spending screen (sponsor spending S4).
 *
 * ⚠ THE TESTS THAT CARRY THIS FILE ARE WRITTEN FROM THE HARM:
 *
 *  * `the category control is a native select` — `TableFrame` establishes TWO clipping contexts,
 *    so a hand-rolled absolute dropdown inside a cell is sliced off at the table's edge. That is
 *    not hypothetical: it happened to the Intake years badge on 2026-09-08 and the owner reported
 *    a panel that opens and cannot be seen. A native `<select>` is drawn by the browser outside
 *    the document and cannot be clipped — so this asserts the ELEMENT, not the styling.
 *  * `a correction re-reads everything` — one change moves the shop, every payment at it, and all
 *    four headline figures. Patching the row in place would leave the percentage at the top
 *    disagreeing with the table beneath it, with nothing failing.
 *  * `finance cannot open this page` — the neighbouring Payments page admits finance and this one
 *    must not; `_b40_scope` promises a finance admin never sees student data beyond the Payments
 *    allowlist, and this screen carries names beside purchases.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SpendingPage from './page'
import * as api from '@/lib/admin-api'
import { canAccess } from '@/lib/navigation'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', owning_org_id: 11 } }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const OVERVIEW: api.SpendingOverview = {
  totals: {
    spent: '10650.22', placed: '7467.89', unplaced: '3182.33',
    placed_pct: 70, merchants_to_check: 12,
  },
  merchants: [
    {
      merchant: 'AL HUDHA ENTERPRISE', category: 'food', decided_by: 'inferred',
      visits: 9, total: '259.20', last_seen: '2026-08-30', held_back: 1,
    },
    {
      merchant: '99 SPEEDMART', category: 'groceries', decided_by: 'rule',
      visits: 15, total: '272.25', last_seen: '2026-08-23', held_back: 0,
    },
    {
      merchant: 'GLASSEYE EYEWEAR TRADING', category: 'health', decided_by: 'owner',
      visits: 1, total: '130.00', last_seen: '2026-08-09', held_back: 0,
    },
  ],
  students: [
    { application_id: 7, name: 'NURUL TEST', payments: 24, spent: '400.00', unplaced: '20.00' },
  ],
  model_decisions: [
    {
      merchant: 'EY VENTURE', category: 'groceries', reason: 'spend-cat-v1',
      decided_at: '2026-09-09T10:00:00Z',
    },
  ],
  wallet_gaps: { students_without_wallet: [], shared_wallets: {} },
  categories: [
    { code: 'food', label: 'Food & drink' },
    { code: 'groceries', label: 'Groceries' },
    { code: 'study', label: 'Books & study supplies' },
    { code: 'health', label: 'Health & pharmacy' },
    { code: 'unsorted', label: 'Not yet sorted' },
  ],
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSpendingOverview.mockResolvedValue(OVERVIEW)
  mockApi.setSpendingCategory.mockResolvedValue({
    merchant: 'AL HUDHA ENTERPRISE', category: 'study', decided_by: 'owner', rows_changed: 9,
  })
})

describe('the screen', () => {
  it('draws every shop with its money, in BOTH renderings', async () => {
    // ⚠ Every shop is drawn twice — a phone card and a desktop row. Asserting only the one a
    // query happens to reach first is how a fix lands on the half nobody looks at (StaffTable,
    // 2026-09-09). Both are pinned by count.
    render(<SpendingPage />)
    expect(await screen.findAllByText('AL HUDHA ENTERPRISE')).toHaveLength(2)
    expect(screen.getAllByText('99 SPEEDMART')).toHaveLength(2)
    expect(screen.getAllByText('RM272.25')).toHaveLength(2)
  })

  it('groups the thousands without turning money into a number', async () => {
    render(<SpendingPage />)
    expect(await screen.findByText('RM10,650.22')).not.toBeNull()
  })

  it('shows the four figures the server computed', async () => {
    render(<SpendingPage />)
    const strip = await screen.findByTestId('spending-totals')
    expect((strip).textContent).toContain('70%')
    expect((strip).textContent).toContain('RM3,182.33')
    expect((strip).textContent).toContain('12')
  })

  it('says how each shop was decided, and marks yours differently', async () => {
    render(<SpendingPage />)
    expect(await screen.findAllByText('admin.spending.by.owner')).toHaveLength(2)
    expect(screen.getAllByText('admin.spending.by.rule')).toHaveLength(2)
    expect(screen.getAllByText('admin.spending.by.inferred')).toHaveLength(2)
  })

  it('names the payments the ceiling held back, and only where the ceiling ran', async () => {
    render(<SpendingPage />)
    // Three shops, one of them `inferred` with held_back 1 — one note per rendering, so two.
    expect(await screen.findAllByText('admin.spending.heldBack')).toHaveLength(2)
  })

  it('never renders a time of day', async () => {
    // ⚠ The hour is discarded at import so nothing downstream can show when a student ate.
    render(<SpendingPage />)
    await screen.findAllByText('AL HUDHA ENTERPRISE')
    expect(document.body.textContent).not.toMatch(/\d{1,2}:\d{2}/)
  })
})

describe('the correction', () => {
  it('the category control is a native select, so the table cannot clip it', async () => {
    // ⚠ THE HARM: TableFrame clips. A custom absolute panel inside a cell is sliced off at the
    // table's edge — the Intake years defect, 2026-09-08. Assert the ELEMENT.
    render(<SpendingPage />)
    const controls = await screen.findAllByLabelText(/AL HUDHA ENTERPRISE/)
    expect(controls).toHaveLength(2)          // the phone card AND the desktop row
    for (const control of controls) expect(control.tagName).toBe('SELECT')
  })

  it('offers exactly the categories the server sent, never a hard-coded list', async () => {
    render(<SpendingPage />)
    const controls = await screen.findAllByLabelText(/99 SPEEDMART/)
    for (const control of controls) {
      expect(Array.from(control.querySelectorAll('option')).map((o) => o.textContent))
        .toEqual(OVERVIEW.categories.map((c) => c.label))
    }
  })

  it('sends the change with the shop it belongs to, from EITHER rendering', async () => {
    for (const index of [0, 1]) {
      jest.clearAllMocks()
      mockApi.getSpendingOverview.mockResolvedValue(OVERVIEW)
      mockApi.setSpendingCategory.mockResolvedValue({
        merchant: 'AL HUDHA ENTERPRISE', category: 'study', decided_by: 'owner', rows_changed: 9,
      })
      const view = render(<SpendingPage />)
      const controls = await screen.findAllByLabelText(/AL HUDHA ENTERPRISE/)
      fireEvent.change(controls[index], { target: { value: 'study' } })
      await waitFor(() => expect(mockApi.setSpendingCategory)
        .toHaveBeenCalledWith('AL HUDHA ENTERPRISE', 'study', { token: 'tok' }))
      view.unmount()
    }
  })

  it('re-reads everything afterwards, so the figures cannot disagree with the table', async () => {
    // ⚠ One change moves the shop, every payment at it, and all four headline figures.
    render(<SpendingPage />)
    const controls = await screen.findAllByLabelText(/AL HUDHA ENTERPRISE/)
    expect(mockApi.getSpendingOverview).toHaveBeenCalledTimes(1)
    fireEvent.change(controls[0], { target: { value: 'study' } })
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledTimes(2))
  })

  it('says so when the change did not save', async () => {
    mockApi.setSpendingCategory.mockRejectedValue(new Error('unknown_merchant'))
    render(<SpendingPage />)
    const controls = await screen.findAllByLabelText(/AL HUDHA ENTERPRISE/)
    fireEvent.change(controls[0], { target: { value: 'study' } })
    expect((await screen.findByRole('alert')).textContent).toContain('admin.spending.error.unknown_merchant')
  })

  it('falls back to a plain failure message for a code it does not know', async () => {
    mockApi.setSpendingCategory.mockRejectedValue(new Error('Admin API error: 500'))
    render(<SpendingPage />)
    const controls = await screen.findAllByLabelText(/AL HUDHA ENTERPRISE/)
    fireEvent.change(controls[0], { target: { value: 'study' } })
    expect((await screen.findByRole('alert')).textContent).toContain('admin.spending.saveFailed')
  })

  it('promises, in words, that a correction is kept', async () => {
    render(<SpendingPage />)
    expect(await screen.findByText('admin.spending.kept')).not.toBeNull()
  })
})

describe('the other sections', () => {
  it('lists each student and what they spent', async () => {
    render(<SpendingPage />)
    expect(await screen.findByText('NURUL TEST')).not.toBeNull()
    expect(screen.getByText('RM400.00')).not.toBeNull()
  })

  it('lists what the model decided lately', async () => {
    render(<SpendingPage />)
    expect((await screen.findByTestId('model-decisions')).textContent).toContain('EY VENTURE')
  })

  it('says the unmatched wallet is emailed rather than shown', async () => {
    // ⚠ A wallet matching NO student is never stored, so it CANNOT be shown here. Saying so on
    // the page is what stops a reader assuming an empty section means "nothing is wrong".
    render(<SpendingPage />)
    expect(await screen.findByText('admin.spending.gaps.note')).not.toBeNull()
  })

  it('shows the wallet gaps when there are any', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({
      ...OVERVIEW,
      wallet_gaps: { students_without_wallet: [42], shared_wallets: { '8000400170001': [7, 8] } },
    })
    render(<SpendingPage />)
    const gaps = await screen.findByTestId('wallet-gaps')
    expect((gaps).textContent).toContain('42')
    expect((gaps).textContent).toContain('8000400170001')
  })
})

describe('who may open it', () => {
  it('admits the officer roles', () => {
    for (const role of ['super', 'org_admin', 'admin'] as const) {
      expect(canAccess('/admin/spending', role)).toBe(true)
    }
  })

  it('refuses finance, unlike the Payments page next door', () => {
    // ⚠ `_b40_scope` promises a finance admin never sees student data beyond the Payments
    // allowlist. This screen carries names beside purchases, so the pair must stay apart.
    expect(canAccess('/admin/payments', 'finance')).toBe(true)
    expect(canAccess('/admin/spending', 'finance')).toBe(false)
  })

  it('refuses a reviewer and a partner', () => {
    expect(canAccess('/admin/spending', 'reviewer')).toBe(false)
    expect(canAccess('/admin/spending', 'partner')).toBe(false)
  })
})

describe('when it will not load', () => {
  it('says so rather than showing an empty screen that looks like no spending', async () => {
    mockApi.getSpendingOverview.mockRejectedValue(new Error('nope'))
    render(<SpendingPage />)
    expect((await screen.findByRole('alert')).textContent).toContain('admin.spending.loadFailed')
  })
})
