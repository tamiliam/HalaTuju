/**
 * @jest-environment jsdom
 *
 * Spending — the URL carries the gift (TD-296) and the newest reply wins (TD-298), 2026-09-28.
 *
 * Payments and Spending move together (TD-241) and share one gate (`useGiftGate`), so this file
 * pins the same promises on the second money page rather than trusting that a shared hook means
 * a shared result: a shared link opens into its gift with no bounce, an unknown code never
 * selects, a switch rewrites the address bar in place, and a slow reply for the gift you left —
 * or for the correction's re-read — never lands over the gift you are in.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import SpendingPage from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS, crumbText, scopeChosen } from '@/test/giftScope'
import { address, crumbOffersAll, deferred, openAt, switchCrumbTo, urlRouter } from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
let mockRole: Record<string, unknown> = { role: 'org_admin', owning_org_id: 11 }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: mockRole }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const FLAGSHIP = 'brightpath-flagship'
const SABAH = 'bpb-sabah-2026'

/** An overview whose headline "spent" figure names which gift it came from. */
const overview = (spent: string) => ({
  totals: { spent, placed: '0', unplaced: '0', placed_pct: 0, merchants_to_check: 0 },
  categories: [], merchants: [], students: [],
  wallet_gaps: { unseen_students: [], shared_wallets: {}, data_to: null },
}) as unknown as api.SpendingOverview

/** The first headline figure — "spent" — which is the one these fixtures vary per gift. */
const spentOnScreen = () => screen.getByTestId('spending-totals').querySelectorAll('dd')[0]?.textContent

beforeEach(() => {
  jest.clearAllMocks()
  mockRole = { role: 'org_admin', owning_org_id: 11 }
  openAt('/admin/spending')
  mockApi.getSpendingOverview.mockResolvedValue(overview('1.00'))
})

const page = (choices = TWO_GIFTS, settled = true) =>
  <GiftScope choices={choices} settled={settled}><SpendingPage /></GiftScope>

describe('(a) a shared link opens INTO its gift', () => {
  it('an org_admin lands on that gift’s spending, cold: no redirect, no box', async () => {
    openAt(`/admin/spending?programme=${SABAH}`)
    const view = render(page([], false))   // a real fresh load: the list is empty until it answers
    view.rerender(page(TWO_GIFTS, true))
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    expect(urlRouter.replace).not.toHaveBeenCalled()
    expect(screen.queryByTestId('choose-programme')).toBeNull()
    expect(mockApi.getSpendingOverview.mock.calls.map((c) => c[0])).toEqual([SABAH])
    expect(crumbText()).toContain('Sabah Bursary 2026')
  })
})

describe('(b) a code the list does not know never selects', () => {
  it('an org_admin is sent to the Programmes page; nothing is fetched', async () => {
    openAt('/admin/spending?programme=not-a-gift')
    render(page())
    await waitFor(() => expect(urlRouter.replace).toHaveBeenCalledWith('/admin/organisation'))
    expect(mockApi.getSpendingOverview).not.toHaveBeenCalled()
    expect(scopeChosen()).toBe('(none)')
  })

  it('an admin is asked on the page — on a single-gift tenant too', async () => {
    mockRole = { role: 'admin', owning_org_id: 11 }
    openAt('/admin/spending?programme=not-a-gift')
    render(page([TWO_GIFTS[0]]))
    expect(await screen.findByTestId('choose-programme')).toBeTruthy()
    expect(mockApi.getSpendingOverview).not.toHaveBeenCalled()
  })
})

describe('(c) a draft in the link is not a gift to spend from', () => {
  it('is asked, offered the live gift only', async () => {
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page([TWO_GIFTS[0], { ...TWO_GIFTS[1], isActive: false }]))
    const box = await screen.findByTestId('choose-programme')
    expect(Array.from(box.querySelectorAll('button')).map((b) => b.textContent))
      .toEqual(['Flagship Bursary'])
    expect(mockApi.getSpendingOverview).not.toHaveBeenCalled()
  })
})

it('TD-302: the crumb offers no "All gifts" — this page needs a gift', async () => {
  openAt(`/admin/spending?programme=${SABAH}`)
  render(page())
  await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
  expect(crumbOffersAll()).toBe(false)
})

describe('(e)(g) the query follows the crumb with replace', () => {
  it('rewrites the address bar in place and adds no history entry', async () => {
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalled())
    const before = window.history.length
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(urlRouter.replace).toHaveBeenCalledWith(
      `/admin/spending?programme=${FLAGSHIP}`, { scroll: false }))
    expect(urlRouter.push).not.toHaveBeenCalled()
    expect(address()).toBe(`/admin/spending?programme=${FLAGSHIP}`)
    expect(window.history.length).toBe(before)
  })
})

describe('(j) TD-298 — only the newest read lands', () => {
  it('a slow reply for the gift you LEFT does not overwrite the new gift’s figures', async () => {
    const forSabah = deferred<api.SpendingOverview>()
    const forFlagship = deferred<api.SpendingOverview>()
    mockApi.getSpendingOverview.mockImplementation(
      (code) => (code === SABAH ? forSabah.promise : forFlagship.promise))
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
    forFlagship.resolve(overview('222.00'))
    await waitFor(() => expect(spentOnScreen()).toBe('RM222.00'))
    // Inside `act`, so any render the stale reply causes is flushed before we look. (A plain
    // timeout here let this pass with the ticket deleted — a silent bite, 2026-09-28.)
    await act(async () => { forSabah.resolve(overview('111.00')) })
    expect(spentOnScreen()).toBe('RM222.00')
  })

  it('a correction’s re-read that lands after a gift switch is dropped too', async () => {
    mockApi.getSpendingOverview.mockResolvedValue({
      ...overview('111.00'),
      merchants: [{ merchant: 'THE SHOP', category: 'food', decided_by: 'ai', visits: 1,
                    total: '1.00', last_seen: '2026-08-01', held_back: 0,
                    decided_at: '2026-08-01T00:00:00Z' }],
      categories: [{ code: 'food', label: 'Food' }, { code: 'study', label: 'Study' }],
    } as unknown as api.SpendingOverview)
    const reRead = deferred<api.SpendingOverview>()
    mockApi.setSpendingCategory.mockResolvedValue({
      merchant: 'THE SHOP', category: 'study', decided_by: 'owner', rows_changed: 1,
    })
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(spentOnScreen()).toBe('RM111.00'))
    // The next read is the correction's re-read, and it is held; then the person switches gift.
    mockApi.getSpendingOverview.mockImplementationOnce(() => reRead.promise)
    const controls = await screen.findAllByRole('combobox', { name: /THE SHOP/ })
    fireEvent.change(controls[0], { target: { value: 'study' } })
    await waitFor(() => expect(mockApi.setSpendingCategory)
      .toHaveBeenCalledWith('THE SHOP', 'study', SABAH, { token: 'tok' }))
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledTimes(2))
    mockApi.getSpendingOverview.mockResolvedValue(overview('222.00'))
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(spentOnScreen()).toBe('RM222.00'))
    await act(async () => { reRead.resolve(overview('111.00')) })
    expect(spentOnScreen()).toBe('RM222.00')
  })

  it('⚠ REVIEW F1: a FAILED save on the old gift’s row, mid-switch, never strands the new gift',
    async () => {
      // The adversarial reviewer's probe. Switch Sabah → Flagship; while Flagship is still
      // loading, correct a row of Sabah's table (still on screen); the save fails. It used to take
      // the LIST's staleness ticket, so Flagship's reply and its end-of-loading were dropped, and
      // the catch never re-read: the crumb said Flagship over Sabah's RM111.00, loading for ever —
      // and the save went out with FLAGSHIP's code for a merchant from Sabah's table.
      const shop = { merchant: 'THE SHOP', category: 'food', decided_by: 'ai', visits: 1,
                     total: '1.00', last_seen: '2026-08-01', held_back: 0,
                     decided_at: '2026-08-01T00:00:00Z' }
      const withShop = (spent: string) => ({ ...overview(spent), merchants: [shop],
        categories: [{ code: 'food', label: 'Food' }, { code: 'study', label: 'Study' }],
      }) as unknown as api.SpendingOverview
      const forFlagship = deferred<api.SpendingOverview>()
      mockApi.getSpendingOverview.mockImplementation(
        (code) => (code === SABAH ? Promise.resolve(withShop('111.00')) : forFlagship.promise))
      mockApi.setSpendingCategory.mockRejectedValue(new Error('Admin API error: 500'))
      openAt(`/admin/spending?programme=${SABAH}`)
      render(page())
      await waitFor(() => expect(spentOnScreen()).toBe('RM111.00'))
      switchCrumbTo('Flagship Bursary')
      await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
      // Sabah's row is still on screen while Flagship loads. Correct it.
      fireEvent.change((await screen.findAllByRole('combobox', { name: /THE SHOP/ }))[0], { target: { value: 'study' } })
      await act(async () => { await new Promise((r) => setTimeout(r, 0)) })
      // (1) Never a save carrying a gift other than the one whose table the row came from.
      for (const call of mockApi.setSpendingCategory.mock.calls) expect(call[2]).toBe(SABAH)
      await act(async () => { forFlagship.resolve(withShop('222.00')) })
      // (2)(3) Flagship's own read lands, and the page is not left loading.
      await waitFor(() => expect(spentOnScreen()).toBe('RM222.00'))
      expect(crumbText()).toContain('Flagship Bursary')
      expect(screen.queryAllByText('common.loading')).toHaveLength(0)
    })

  it('a save still IN FLIGHT never holds back the new gift’s list (they share no token)', async () => {
    // Found by a SILENT bite: with the save taking the list's ticket again, the re-read after the
    // save healed the page — so every test passed. It does not heal while the save hangs: the new
    // gift's reply is dropped and the old gift's figures sit under the new crumb until it returns.
    const shop = { merchant: 'THE SHOP', category: 'food', decided_by: 'ai', visits: 1,
                   total: '1.00', last_seen: '2026-08-01', held_back: 0,
                   decided_at: '2026-08-01T00:00:00Z' }
    const withShop = (spent: string) => ({ ...overview(spent), merchants: [shop],
      categories: [{ code: 'food', label: 'Food' }, { code: 'study', label: 'Study' }],
    }) as unknown as api.SpendingOverview
    const forFlagship = deferred<api.SpendingOverview>()
    mockApi.getSpendingOverview.mockImplementation(
      (code) => (code === SABAH ? Promise.resolve(withShop('111.00')) : forFlagship.promise))
    mockApi.setSpendingCategory.mockImplementation(() => new Promise(() => {}))   // never answers
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(spentOnScreen()).toBe('RM111.00'))
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
    fireEvent.change((await screen.findAllByRole('combobox', { name: /THE SHOP/ }))[0], { target: { value: 'study' } })
    await waitFor(() => expect(mockApi.setSpendingCategory).toHaveBeenCalled())
    await act(async () => { forFlagship.resolve(withShop('222.00')) })
    expect(spentOnScreen()).toBe('RM222.00')
  })

  it('a failed save re-reads the CURRENT gift, so the page is never left inconsistent', async () => {
    const shop = { merchant: 'THE SHOP', category: 'food', decided_by: 'ai', visits: 1,
                   total: '1.00', last_seen: '2026-08-01', held_back: 0,
                   decided_at: '2026-08-01T00:00:00Z' }
    mockApi.getSpendingOverview.mockResolvedValue({ ...overview('111.00'), merchants: [shop],
      categories: [{ code: 'food', label: 'Food' }, { code: 'study', label: 'Study' }],
    } as unknown as api.SpendingOverview)
    mockApi.setSpendingCategory.mockRejectedValue(new Error('Admin API error: 500'))
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(spentOnScreen()).toBe('RM111.00'))
    fireEvent.change((await screen.findAllByRole('combobox', { name: /THE SHOP/ }))[0], { target: { value: 'study' } })
    expect((await screen.findByRole('alert')).textContent).toContain('admin.spending.saveFailed')
    await waitFor(() => expect(mockApi.getSpendingOverview).toHaveBeenCalledTimes(2))
    expect(mockApi.getSpendingOverview.mock.calls[1][0]).toBe(SABAH)
  })

  it('a gift switch while the correction is still SAVING makes its re-read stale too', async () => {
    // Found by the sprint's own review: the ticket was taken after the save, so a switch during
    // the save let the correction re-read the OLD gift, outrank the new gift's read, and leave the
    // page loading for ever.
    mockApi.getSpendingOverview.mockImplementation(async (code) => ({
      ...overview(code === SABAH ? '111.00' : '222.00'),
      merchants: [{ merchant: 'THE SHOP', category: 'food', decided_by: 'ai', visits: 1,
                    total: '1.00', last_seen: '2026-08-01', held_back: 0,
                    decided_at: '2026-08-01T00:00:00Z' }],
      categories: [{ code: 'food', label: 'Food' }, { code: 'study', label: 'Study' }],
    }) as unknown as api.SpendingOverview)
    const save = deferred<Awaited<ReturnType<typeof api.setSpendingCategory>>>()
    mockApi.setSpendingCategory.mockImplementation(() => save.promise)
    openAt(`/admin/spending?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(spentOnScreen()).toBe('RM111.00'))
    fireEvent.change((await screen.findAllByRole('combobox', { name: /THE SHOP/ }))[0], { target: { value: 'study' } })
    await waitFor(() => expect(mockApi.setSpendingCategory).toHaveBeenCalled())
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(spentOnScreen()).toBe('RM222.00'))
    const readsBefore = mockApi.getSpendingOverview.mock.calls.length
    await act(async () => {
      save.resolve({ merchant: 'THE SHOP', category: 'study', decided_by: 'owner', rows_changed: 1 })
    })
    expect(spentOnScreen()).toBe('RM222.00')
    // The old gift is not re-read at all once the person has left it.
    expect(mockApi.getSpendingOverview.mock.calls.slice(readsBefore).map((c) => c[0]))
      .not.toContain(SABAH)
  })
})
