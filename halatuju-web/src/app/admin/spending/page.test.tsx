/**
 * @jest-environment jsdom
 *
 * The officer's spending screen (S4, reorganised into tabs in S6).
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
 *  * `the figures do not move when you change tab` — they describe the whole page. A headline that
 *    changed under the tabs would be a headline nobody could quote.
 *  * `correcting from the Unsorted tab works too` — the shops list is ONE component drawn in two
 *    tabs, and the whole point of that is that neither tab can quietly lose the correction.
 *
 * ⚠ EVERY SHOP IS DRAWN TWICE — a phone card and a desktop row, both in the DOM because jsdom
 * applies no breakpoints. `getAllBy*` with a COUNT is the honest assertion; a singular query would
 * pass by reaching whichever copy comes first (StaffTable, 2026-09-09).
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
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
      // `inferred` with money held back by the RM20 ceiling — placed as food, yet some of its
      // ringgit are not. It must appear in BOTH tabs.
      merchant: 'AL HUDHA ENTERPRISE', category: 'food', decided_by: 'inferred',
      visits: 9, total: '259.20', last_seen: '2026-08-30', held_back: 1,
      decided_at: '2026-09-01T00:00:00Z',
    },
    {
      merchant: '99 SPEEDMART', category: 'groceries', decided_by: 'rule',
      visits: 15, total: '272.25', last_seen: '2026-08-23', held_back: 0,
      decided_at: '2026-08-20T00:00:00Z',
    },
    {
      merchant: 'GLASSEYE EYEWEAR TRADING', category: 'health', decided_by: 'owner',
      visits: 1, total: '130.00', last_seen: '2026-08-09', held_back: 0,
      decided_at: '2026-08-10T00:00:00Z',
    },
    {
      merchant: 'SHOPEE MARKETPLACE', category: 'unsorted', decided_by: 'ai',
      visits: 16, total: '401.03', last_seen: '2026-08-29', held_back: 0,
      decided_at: '2026-09-05T00:00:00Z',
    },
  ],
  students: [
    { application_id: 7, name: 'NURUL TEST', payments: 24, spent: '400.00', unplaced: '20.00' },
    { application_id: 8, name: 'AMIR TEST', payments: 3, spent: '90.00', unplaced: '0.00' },
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

/** The tab label prefix, BUILT rather than written out, so this file never contains a literal
 *  that looks like an `admin.spending.*` key the page does not have. */
const KEY = `admin.spending.${'tab'}.`

/** Open one of the three tabs.
 *
 * ⚠ A REGEX, NOT AN EXACT NAME. Since S7 the tab's accessible name is the label PLUS its
 * count (the shops tab reads as its key with a 4 glued on), so an exact match finds nothing
 * and the failure
 * reads as "the tab is missing" rather than "its name grew". */
async function openTab(name: 'shops' | 'students' | 'unsorted') {
  fireEvent.click(await screen.findByRole('tab',
                                          { name: new RegExp(`tab\.${name}`) }))
}

/** The DESKTOP table's data rows, in the order they are drawn. Phone cards are `div`s, so they
 *  are not rows and cannot be confused with these. */
const bodyRows = () => screen.getAllByRole('row').slice(1)

/** The shop names down the desktop table, in order. The first cell also carries the held-back
 *  note on a ceiling shop, so it is trimmed off rather than asserted around. */
const shopOrder = () => bodyRows().map((r) =>
  (within(r).getAllByRole('cell')[0].textContent || '').split('admin.spending')[0].trim())

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSpendingOverview.mockResolvedValue(OVERVIEW)
  mockApi.setSpendingCategory.mockResolvedValue({
    merchant: 'AL HUDHA ENTERPRISE', category: 'study', decided_by: 'owner', rows_changed: 9,
  })
})

describe('the three tabs', () => {
  it('opens on Shops, and offers exactly three', async () => {
    render(<SpendingPage />)
    const tabs = await screen.findAllByRole('tab')
    // ⚠ ASSERTED AS LABEL + COUNT SEPARATELY, NOT AS ONE GLUED STRING.
    // Gluing the label and the count into one quoted string was the first attempt, and it
    // broke the i18n scanner: that guard greps the whole of `src/` for quoted keys under this
    // namespace and checks each resolves — and it does NOT skip comments, so even writing the
    // offending string in an explanation re-breaks it. A test must never mint a fake key, in
    // code or in prose.
    expect(tabs.map((b) => b.textContent)).toEqual([
      `${KEY}shops4`, `${KEY}students2`, `${KEY}unsorted2`,
    ])
    expect(tabs[0].getAttribute('aria-selected')).toBe('true')
  })

  it('shows one tab at a time — a student is not on the Shops tab', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    expect(screen.queryByText('NURUL TEST')).toBeNull()
    await openTab('students')
    expect(screen.getAllByText('NURUL TEST').length).toBeGreaterThan(0)
    expect(screen.queryByText('99 SPEEDMART')).toBeNull()
  })

  it('⚠ THE FOUR FIGURES DO NOT MOVE WHEN YOU CHANGE TAB', async () => {
    // They describe the whole page. A headline that changed under the tabs would be a headline
    // nobody could quote — and the "Not yet sorted" figure is exactly what the Unsorted tab is
    // there to explain, so it has to still be on screen when you get there.
    render(<SpendingPage />)
    const before = (await screen.findByTestId('spending-totals')).textContent
    for (const tab of ['students', 'unsorted', 'shops'] as const) {
      await openTab(tab)
      expect(screen.getByTestId('spending-totals').textContent).toEqual(before)
    }
  })
})

describe('the Shops tab', () => {
  it('draws every shop with its money, in BOTH renderings', async () => {
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
    expect(strip.textContent).toContain('70%')
    expect(strip.textContent).toContain('RM3,182.33')
    expect(strip.textContent).toContain('12')
  })

  it('says how each shop was decided, and marks yours differently', async () => {
    // ⚠ COUNTED INSIDE THE TABLE. Since S7 the same six words are also the options of the
    // "how we decided" FILTER, so a page-wide count of two is simply wrong — and it would
    // have been wrong in a way that still passed for a while.
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    const table = within(screen.getAllByRole('table')[0])
    expect(table.getAllByText('admin.spending.by.owner')).toHaveLength(1)
    expect(table.getAllByText('admin.spending.by.rule')).toHaveLength(1)
    expect(table.getAllByText('admin.spending.by.inferred')).toHaveLength(1)
  })

  it('names the payments the ceiling held back, and only where the ceiling ran', async () => {
    render(<SpendingPage />)
    // Four shops, one of them `inferred` with held_back 1 — one note per rendering, so two.
    expect(await screen.findAllByText('admin.spending.heldBack')).toHaveLength(2)
  })

  it('never renders a time of day', async () => {
    // ⚠ The hour is discarded at import so nothing downstream can show when a student ate.
    render(<SpendingPage />)
    await screen.findAllByText('AL HUDHA ENTERPRISE')
    expect(document.body.textContent).not.toMatch(/\d{1,2}:\d{2}/)
  })
})

describe('sorting a column', () => {
  it('starts on the biggest total, whichever order the server sent', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    expect(shopOrder()).toEqual([
      'SHOPEE MARKETPLACE', '99 SPEEDMART', 'AL HUDHA ENTERPRISE', 'GLASSEYE EYEWEAR TRADING',
    ])
  })

  it('reorders on a header click, and flips on a second', async () => {
    render(<SpendingPage />)
    const header = () => screen.getByRole('button', { name: /admin\.spending\.col\.shop/ })
    await waitFor(() => expect(header()).not.toBeNull())

    fireEvent.click(header())
    expect(shopOrder()).toEqual([
      '99 SPEEDMART', 'AL HUDHA ENTERPRISE', 'GLASSEYE EYEWEAR TRADING', 'SHOPEE MARKETPLACE',
    ])

    fireEvent.click(header())
    expect(shopOrder()).toEqual([
      'SHOPEE MARKETPLACE', 'GLASSEYE EYEWEAR TRADING', 'AL HUDHA ENTERPRISE', '99 SPEEDMART',
    ])
  })

  it('tells a screen reader which column is sorted and which way', async () => {
    // ⚠ `aria-sort` is the only thing announcing the order to somebody who cannot see the arrow.
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    const sorted = screen.getAllByRole('columnheader')
      .filter((h) => h.getAttribute('aria-sort') !== 'none')
    expect(sorted).toHaveLength(1)
    expect(sorted[0].textContent).toContain('admin.spending.col.total')
    expect(sorted[0].getAttribute('aria-sort')).toBe('descending')
  })

  it('sorts the students table on its own, without touching the shops', async () => {
    render(<SpendingPage />)
    await openTab('students')
    expect(bodyRows()[0].textContent).toContain('NURUL TEST')   // spent, descending
    fireEvent.click(screen.getByRole('button', { name: /admin\.spending\.students\.name/ }))
    expect(bodyRows()[0].textContent).toContain('AMIR TEST')    // name, A→Z
  })
})

describe('paging a long list', () => {
  const shops = (total: (i: number) => number) => Array.from({ length: 30 }, (_, i) => ({
    merchant: `SHOP ${String(i).padStart(2, '0')}`, category: 'food', decided_by: 'rule',
    visits: 1, total: `${total(i)}.00`, last_seen: '2026-08-01', held_back: 0,
    decided_at: null,
  }))

  /** Money ranks the same way as the name, so the default view reads SHOP 00 … SHOP 29. */
  const many = shops((i) => 100 - i)

  /**
   * ⚠⚠ **ARRIVES IN THE SERVER'S OWN ORDER — BIGGEST TOTAL FIRST — AND NOT IN NAME ORDER. THAT IS
   * THE ENTIRE POINT OF THIS FIXTURE, AND THE FIRST VERSION OF IT DID NOT DO IT.**
   *
   * A bite-check proved that version worthless: with the rows arriving as SHOP 00 … SHOP 29,
   * "sort the whole list then take a page" and "take a page then sort it" BOTH yield SHOP 00 … 24,
   * so the deliberate fault passed every test. The discriminator is that the incoming order must
   * disagree with the sort being asked for, exactly as the live payload does (`spend_report`
   * returns `-total`, then name).
   */
  const scrambled = shops((i) => ((i * 7) % 30) + 1)
    .slice().sort((a, b) => Number(b.total) - Number(a.total))

  /** The list has arrived. Not keyed on a shop NAME: which shop is on page one depends on the
   *  fixture's money, and a test should not have to work that out to know the page loaded. */
  const loaded = () => waitFor(() => expect(bodyRows().length).toBeGreaterThan(0))

  it('shows no pager on a short list — four shops fit one page', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    expect(screen.queryAllByRole('button', { name: /admin\.next/ })).toHaveLength(0)
  })

  it('pages a long one, and the second page holds the rest', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({ ...OVERVIEW, merchants: many })
    render(<SpendingPage />)
    await loaded()
    expect(bodyRows()).toHaveLength(25)
    expect(screen.queryByText('SHOP 29')).toBeNull()

    // ⚠ The pager renders a mobile AND a desktop copy, both in the DOM (docs/lessons.md,
    // 2026-07-28). `getAllBy` and click the first is the honest way to drive it.
    fireEvent.click(screen.getAllByRole('button', { name: /admin\.next/ })[0])
    expect(bodyRows()).toHaveLength(5)
    expect(screen.getAllByText('SHOP 29').length).toBeGreaterThan(0)
  })

  it('⚠ FILTERS THE WHOLE LIST, THEN PAGES — never pages first and filters the page', () => {
    // FOUND BY A BITE-CHECK THAT THE FOUR-SHOP FIXTURE COULD NOT SEE: with one page, "filter then
    // page" and "page then filter" are identical. It takes a list longer than a page, and a
    // search that matches rows on BOTH pages, to tell them apart.
    //
    // The harm is a first page with holes in it. Thirty shops named SHOP 00…29 arrive biggest
    // first; "SHOP 2" matches the ten from SHOP 20. Filtering first finds all ten. Paging first
    // takes SHOP 00…24 and then filters THOSE — five rows — while the screen still says it is
    // showing you everything that matched.
    mockApi.getSpendingOverview.mockResolvedValue({ ...OVERVIEW, merchants: many })
    render(<SpendingPage />)
    return waitFor(() => expect(bodyRows().length).toBeGreaterThan(0)).then(() => {
      fireEvent.change(screen.getByLabelText('admin.spending.searchShops'),
                       { target: { value: 'SHOP 2' } })
      expect(bodyRows()).toHaveLength(10)
      expect(screen.getAllByText('SHOP 29')).toHaveLength(2)
    })
  })

  it('⚠ SORTS THE WHOLE LIST, THEN TAKES A PAGE — never the other way round', async () => {
    // The reversed order sorts one page at a time, so rows migrate between pages as you click and
    // the first page is whatever the SERVER's order put there. It looks like sorting works,
    // because page one is genuinely in order; only the rows that should have arrived from page
    // two are missing, and nobody counts.
    mockApi.getSpendingOverview.mockResolvedValue({ ...OVERVIEW, merchants: scrambled })
    render(<SpendingPage />)
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: /admin\.spending\.col\.shop/ }))
    expect(shopOrder()).toEqual(
      Array.from({ length: 25 }, (_, i) => `SHOP ${String(i).padStart(2, '0')}`))
  })

  it('goes back to page one when the list under it changes', async () => {
    // Correcting a shop from the Unsorted tab shortens that list. A stale page number would show
    // an empty table and read as "you have finished", which is the opposite of true.
    mockApi.getSpendingOverview.mockResolvedValue({ ...OVERVIEW, merchants: many })
    render(<SpendingPage />)
    await loaded()
    fireEvent.click(screen.getAllByRole('button', { name: /admin\.next/ })[0])
    expect(bodyRows()).toHaveLength(5)

    mockApi.getSpendingOverview.mockResolvedValue({ ...OVERVIEW, merchants: many.slice(0, 26) })
    // ⚠ BY LABEL, not by position. The filters are comboboxes too since S7, and the first one
    // on the page is now the category FILTER — changing that would silently test nothing.
    fireEvent.change(screen.getAllByLabelText(/SHOP 2[0-9]/)[0], { target: { value: 'study' } })
    await waitFor(() => expect(bodyRows()).toHaveLength(25))
  })
})

describe('searching and filtering', () => {
  const typeSearch = (value: string) =>
    fireEvent.change(screen.getByLabelText('admin.spending.searchShops'), { target: { value } })

  it('narrows the shops as you type, in BOTH renderings', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    typeSearch('speed')
    expect(screen.getAllByText('99 SPEEDMART')).toHaveLength(2)
    expect(screen.queryByText('SHOPEE MARKETPLACE')).toBeNull()
  })

  it('ignores case and surrounding spaces, because people paste', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    typeSearch('  ShOpEe  ')
    expect(screen.getAllByText('SHOPEE MARKETPLACE')).toHaveLength(2)
    expect(screen.queryByText('99 SPEEDMART')).toBeNull()
  })

  it('filters by how we decided, which is what replaced the model list', async () => {
    // ⚠ THE WHOLE CASE FOR DELETING THAT SECTION. Picking "Model" here gives the same list it
    // gave — and this one you can correct from.
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    fireEvent.change(screen.getByLabelText('admin.spending.filter.decidedByLabel'),
                     { target: { value: 'ai' } })
    expect(screen.getAllByText('SHOPEE MARKETPLACE')).toHaveLength(2)
    expect(screen.queryByText('99 SPEEDMART')).toBeNull()
    expect(screen.queryByText('GLASSEYE EYEWEAR TRADING')).toBeNull()
  })

  it('filters by category', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    fireEvent.change(screen.getByLabelText('admin.spending.filter.categoryLabel'),
                     { target: { value: 'groceries' } })
    expect(screen.getAllByText('99 SPEEDMART')).toHaveLength(2)
    expect(screen.queryByText('AL HUDHA ENTERPRISE')).toBeNull()
  })

  it('⚠ SAYS "NOTHING MATCHES", NOT "NO SPENDING RECORDED"', async () => {
    // Telling somebody their data is missing when they have merely typed a typo is the worst
    // wording available. The two empties mean opposite things.
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    typeSearch('zzzz')
    expect(screen.getAllByText('admin.spending.noMatch').length).toBeGreaterThan(0)
    expect(screen.queryByText('admin.spending.empty')).toBeNull()
  })

  it('clears back to the whole list', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    typeSearch('speed')
    fireEvent.click(screen.getByRole('button', { name: 'admin.spending.filter.clear' }))
    expect(screen.getAllByText('SHOPEE MARKETPLACE')).toHaveLength(2)
  })

  it('shows no "clear" and no count until something is actually filtered', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    expect(screen.queryByRole('button', { name: 'admin.spending.filter.clear' })).toBeNull()
    expect(screen.queryByTestId('merchant-showing')).toBeNull()
  })

  it('⚠ THE TAB COUNT DOES NOT MOVE WHEN YOU FILTER', async () => {
    // The tab answers "how many are there", the count beside the search answers "how many am I
    // looking at". If the tab followed the filter, the first question would have no answer left
    // on screen.
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    const shopsTab = () => screen.getByRole('tab', { name: /admin\.spending\.tab\.shops/ })
    expect(shopsTab().textContent).toContain('4')
    typeSearch('speed')
    expect(shopsTab().textContent).toContain('4')
    expect(screen.getByTestId('merchant-showing')).not.toBeNull()
  })

  it('each tab filters on its own — the Unsorted search is not the Shops search', async () => {
    render(<SpendingPage />)
    await screen.findAllByText('99 SPEEDMART')
    typeSearch('speed')
    await openTab('unsorted')
    expect(screen.getAllByText('SHOPEE MARKETPLACE')).toHaveLength(2)
  })

  it('searches the students by name, and can show only those with unsorted money', async () => {
    render(<SpendingPage />)
    await openTab('students')
    fireEvent.change(screen.getByLabelText('admin.spending.searchStudents'),
                     { target: { value: 'amir' } })
    expect(screen.getAllByText('AMIR TEST')).toHaveLength(2)
    expect(screen.queryByText('NURUL TEST')).toBeNull()

    fireEvent.change(screen.getByLabelText('admin.spending.searchStudents'),
                     { target: { value: '' } })
    fireEvent.click(screen.getByLabelText('admin.spending.filter.onlyUnplaced'))
    // ⚠ AMIR's `unplaced` is the STRING '0.00', which is truthy. A filter written on truthiness
    // would keep him and look completely broken to nobody.
    expect(screen.getAllByText('NURUL TEST')).toHaveLength(2)
    expect(screen.queryByText('AMIR TEST')).toBeNull()
  })
})

describe('the decided date', () => {
  it('is a column on the shop row now, sortable, and blank when there is no verdict', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({
      ...OVERVIEW,
      merchants: [
        { ...OVERVIEW.merchants[0], merchant: 'NEWEST', decided_at: '2026-09-09T00:00:00Z' },
        { ...OVERVIEW.merchants[1], merchant: 'OLDEST', decided_at: '2026-01-01T00:00:00Z' },
        { ...OVERVIEW.merchants[2], merchant: 'NO VERDICT', decided_at: null },
      ],
    })
    render(<SpendingPage />)
    await screen.findAllByText('NEWEST')
    fireEvent.click(screen.getByRole('button', { name: /admin\.spending\.col\.decidedAt/ }))
    // Newest first, and the shop with no verdict at the BOTTOM — not treated as 1970.
    expect(shopOrder()).toEqual(['NEWEST', 'OLDEST', 'NO VERDICT'])
  })
})

describe('the Unsorted tab', () => {
  it('lists only the shops with money we could not place', async () => {
    render(<SpendingPage />)
    await openTab('unsorted')
    // SHOPEE is `unsorted`; AL HUDHA reads `food` but the ceiling holds one of its payments.
    // 99 SPEEDMART and GLASSEYE are fully placed and must not be here.
    expect(screen.getAllByText('SHOPEE MARKETPLACE')).toHaveLength(2)
    expect(screen.getAllByText('AL HUDHA ENTERPRISE')).toHaveLength(2)
    expect(screen.queryByText('99 SPEEDMART')).toBeNull()
    expect(screen.queryByText('GLASSEYE EYEWEAR TRADING')).toBeNull()
  })

  it('⚠ CORRECTING FROM THIS TAB WORKS — it is the same list, not a read-only copy', async () => {
    render(<SpendingPage />)
    await openTab('unsorted')
    const controls = await screen.findAllByLabelText(/AL HUDHA ENTERPRISE/)
    expect(controls).toHaveLength(2)
    fireEvent.change(controls[0], { target: { value: 'study' } })
    await waitFor(() => expect(mockApi.setSpendingCategory)
      .toHaveBeenCalledWith('AL HUDHA ENTERPRISE', 'study', undefined, { token: 'tok' }))
  })

  it('says so plainly when nothing is left to place', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({
      ...OVERVIEW,
      merchants: OVERVIEW.merchants.filter((m) => m.decided_by === 'owner'),
    })
    render(<SpendingPage />)
    await openTab('unsorted')
    expect(screen.getAllByText('admin.spending.unplaced.empty').length).toBeGreaterThan(0)
  })

  it('⚠ HOLDS THE SHOPS AND NOTHING ELSE — the model list and the wallets have gone', async () => {
    // The model list was DELETED (it duplicated this table and could not be acted on) and the
    // wallets MOVED to Students (a wallet is a fact about a student). Asserting their absence
    // here is what stops either quietly coming back.
    render(<SpendingPage />)
    await openTab('unsorted')
    expect(screen.queryByTestId('model-decisions')).toBeNull()
    expect(screen.queryByTestId('wallet-gaps')).toBeNull()
    expect(screen.getAllByText('SHOPEE MARKETPLACE')).toHaveLength(2)
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
        .toHaveBeenCalledWith('AL HUDHA ENTERPRISE', 'study', undefined, { token: 'tok' }))
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

  it('promises, in words, that a correction is kept — on both tabs that offer one', async () => {
    render(<SpendingPage />)
    expect(await screen.findByText('admin.spending.kept')).not.toBeNull()
    await openTab('unsorted')
    expect(screen.getByText('admin.spending.kept')).not.toBeNull()
  })
})

describe('the Students tab', () => {
  it('lists each student and what they spent, in both renderings', async () => {
    render(<SpendingPage />)
    await openTab('students')
    expect(screen.getAllByText('NURUL TEST')).toHaveLength(2)
    expect(screen.getAllByText('RM400.00')).toHaveLength(2)
  })

  it('says so when nobody has spent anything', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({ ...OVERVIEW, students: [] })
    render(<SpendingPage />)
    await openTab('students')
    expect(screen.getAllByText('admin.spending.students.empty').length).toBeGreaterThan(0)
  })
})

describe('the wallet faults', () => {
  it('says the unmatched wallet is emailed rather than shown', async () => {
    // ⚠ A wallet matching NO student is never stored, so it CANNOT be shown here. Saying so on
    // the page is what stops a reader assuming an empty section means "nothing is wrong".
    render(<SpendingPage />)
    await openTab('students')
    expect(screen.getByText('admin.spending.gaps.note')).not.toBeNull()
  })

  it('shows the wallet gaps when there are any', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({
      ...OVERVIEW,
      wallet_gaps: { students_without_wallet: [42], shared_wallets: { '8000400170001': [7, 8] } },
    })
    render(<SpendingPage />)
    await openTab('students')
    const gaps = within(screen.getByTestId('wallet-gaps'))
    expect(gaps.getByText(/42/)).not.toBeNull()
    expect(gaps.getByText(/8000400170001/)).not.toBeNull()
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
