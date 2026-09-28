/**
 * @jest-environment jsdom
 *
 * Payments — the URL carries the gift (TD-296) and the newest reply wins (TD-298), 2026-09-28.
 *
 * ⚠ THE CASE THAT MATTERS MOST IS A SHARED LINK. `/admin/payments?programme=bpb-sabah-2026`, pasted
 * into an org_admin's chat, must open straight into that gift's runs — no bounce to the Programmes
 * page, no question. The 2026-09-28 gate redirects exactly this role when no gift is known, so the
 * query has to be applied BEFORE the gate decides; these tests pin that ordering from the outside,
 * including the cold load where the scopes list arrives after the page has mounted.
 *
 * And the neighbours of that state (docs/lessons.md, "state neighbours"): a code the list does not
 * know, a DRAFT, an earlier different pick, a single-gift tenant, and leaving by Back.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import PaymentsLandingPage from './page'
import * as api from '@/lib/admin-api'
import { useProgrammeScope } from '@/lib/programmeScope'
import { GiftScope, TWO_GIFTS, crumbText, scopeChosen } from '@/test/giftScope'
import { address, deferred, openAt, switchCrumbTo, urlRouter } from '@/test/giftUrl'

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
const DOOR = '/admin/organisation'
const asRole = (role: string) => { mockRole = { role, is_super_admin: role === 'super', owning_org_id: 11 } }

const run = (id: number, reference: string) => ({
  id, reference, payment_date: '2026-10-01', period_month: '2026-10-01', status: 'draft',
  students: 1, total: '100',
}) as unknown as api.PaymentRunSummary
const runs = (...r: api.PaymentRunSummary[]) =>
  ({ runs: r }) as unknown as Awaited<ReturnType<typeof api.getPaymentRuns>>
const NO_FUNDING = { rows: [], totals: {} } as unknown as api.FundingSummary

beforeEach(() => {
  jest.clearAllMocks()
  asRole('org_admin')
  openAt('/admin/payments')
  mockApi.getPaymentRuns.mockResolvedValue(runs())
  mockApi.getFundingSummary.mockResolvedValue(NO_FUNDING)
})

const page = (choices = TWO_GIFTS, settled = true) =>
  <GiftScope choices={choices} settled={settled}><PaymentsLandingPage /></GiftScope>
const runsAskedFor = () => mockApi.getPaymentRuns.mock.calls.map((c) => c[0])

describe('(a) a shared link opens INTO its gift', () => {
  it('an org_admin lands on that gift’s runs: no redirect, no box', async () => {
    openAt(`/admin/payments?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    expect(mockApi.getFundingSummary).toHaveBeenCalledWith(SABAH, { token: 'tok' })
    expect(await screen.findByText(/admin.payments.newRun/)).toBeTruthy()
    expect(urlRouter.replace).not.toHaveBeenCalled()
    expect(screen.queryByTestId('choose-programme')).toBeNull()
    expect(crumbText()).toContain('Sabah Bursary 2026')
    // Never asked for anything but the link's gift — not every gift, not the other one.
    expect(runsAskedFor()).toEqual([SABAH])
  })

  it('⚠ on a COLD load the list arrives after the page: still no bounce, still that gift', async () => {
    // The real shape of a pasted link: the shell mounts, the page mounts, and only then does the
    // scopes fetch answer. Nothing may be decided — or fetched — until the link's gift is known.
    openAt(`/admin/payments?programme=${SABAH}`)
    // A REAL fresh load (review F5): the shell's list is EMPTY until its fetch answers — not the
    // two gifts with a "not settled" flag, which no browser ever produces.
    const view = render(page([], false))
    expect(screen.getByTestId('gift-wait')).toBeTruthy()
    await new Promise((r) => setTimeout(r, 20))
    expect(mockApi.getPaymentRuns).not.toHaveBeenCalled()
    view.rerender(page(TWO_GIFTS, true))
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    expect(urlRouter.replace).not.toHaveBeenCalled()
    expect(runsAskedFor()).toEqual([SABAH])
  })

  it('admin and finance open into it too — no box', async () => {
    for (const role of ['admin', 'finance']) {
      jest.clearAllMocks()
      asRole(role)
      openAt(`/admin/payments?programme=${FLAGSHIP}`)
      const view = render(page())
      await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
      expect(screen.queryByTestId('choose-programme')).toBeNull()
      view.unmount()
    }
  })
})

describe('(b) a code the list does not know never selects', () => {
  it('an org_admin is sent to the Programmes page, exactly as with no code', async () => {
    openAt('/admin/payments?programme=not-a-gift')
    render(page())
    await waitFor(() => expect(urlRouter.replace).toHaveBeenCalledWith(DOOR))
    expect(mockApi.getPaymentRuns).not.toHaveBeenCalled()
    expect(scopeChosen()).toBe('(none)')
  })

  it('an admin is asked on the page', async () => {
    asRole('admin')
    openAt('/admin/payments?programme=not-a-gift')
    render(page())
    expect(await screen.findByTestId('choose-programme')).toBeTruthy()
    expect(mockApi.getPaymentRuns).not.toHaveBeenCalled()
  })

  it('⚠ on a SINGLE-gift tenant it is still no gift — never "the only one" (2026-09-03)', async () => {
    // The only gift is not what the link asked for. Opening it would show one gift's money under
    // a link that named another — the substitution the scope's guard exists to make impossible.
    asRole('admin')
    openAt('/admin/payments?programme=not-a-gift')
    render(page([TWO_GIFTS[0]]))
    expect(await screen.findByTestId('choose-programme')).toBeTruthy()
    expect(mockApi.getPaymentRuns).not.toHaveBeenCalled()
    expect(screen.queryByText(/admin.payments.newRun/)).toBeNull()
  })
})

describe('⚠ REVIEW F2: a mistyped link is judged once, then FORGOTTEN', () => {
  it('bad link → redirected once → a plain Payments visit later opens normally', async () => {
    // The reviewer's probe: the unknown code used to stay stored as the person's pick, so on a
    // single-gift tenant every later plain visit redirected again (and the rail hid the rows).
    openAt('/admin/payments?programme=not-a-gift')
    const view = render(page([TWO_GIFTS[0]]))
    await waitFor(() => expect(urlRouter.replace).toHaveBeenCalledWith(DOOR))
    // The redirect lands: the page goes, the shell (and its scope) stays.
    view.rerender(<GiftScope choices={[TWO_GIFTS[0]]}>{null}</GiftScope>)
    expect(scopeChosen()).toBe(FLAGSHIP)
    // Later, a plain visit — exactly as before this sprint: the single gift resolves itself.
    jest.clearAllMocks()
    openAt('/admin/payments')
    view.rerender(page([TWO_GIFTS[0]]))
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
    expect(urlRouter.replace).not.toHaveBeenCalled()
  })

  it('an earlier REAL pick survives leaving — only the unrecognised code is forgotten', async () => {
    function PickSabah() {
      const { select } = useProgrammeScope()
      return <button type="button" onClick={() => select(SABAH)}>pick-sabah</button>
    }
    asRole('admin')
    openAt('/admin/payments?programme=not-a-gift')
    const view = render(page())
    expect(await screen.findByTestId('choose-programme')).toBeTruthy()
    // The person answers the box: a real pick, which leaving must NOT clear.
    fireEvent.click(screen.getByRole('button', { name: 'Sabah Bursary 2026' }))
    await waitFor(() => expect(scopeChosen()).toBe(SABAH))
    view.rerender(<GiftScope><PickSabah /></GiftScope>)
    expect(scopeChosen()).toBe(SABAH)
  })
})

describe('(c) a DRAFT gift in the link is not payable', () => {
  const LIVE_AND_DRAFT = [TWO_GIFTS[0], { ...TWO_GIFTS[1], isActive: false }]

  it('every role is ASKED, offered the live gift only — no runs, no New-run button', async () => {
    for (const role of ['org_admin', 'super', 'admin', 'finance']) {
      jest.clearAllMocks()
      asRole(role)
      openAt(`/admin/payments?programme=${SABAH}`)
      const view = render(page(LIVE_AND_DRAFT))
      const box = await screen.findByTestId('choose-programme')
      expect(Array.from(box.querySelectorAll('button')).map((b) => b.textContent))
        .toEqual(['Flagship Bursary'])
      // Not redirected: the Programmes page lists the draft's own card, a bounce back waiting.
      expect(urlRouter.replace).not.toHaveBeenCalled()
      expect(mockApi.getPaymentRuns).not.toHaveBeenCalled()
      expect(screen.queryByText(/admin.payments.newRun/)).toBeNull()
      view.unmount()
    }
  })

  it('answering the box opens the live gift and the address bar follows it', async () => {
    openAt(`/admin/payments?programme=${SABAH}`)
    render(page(LIVE_AND_DRAFT))
    fireEvent.click(await screen.findByRole('button', { name: 'Flagship Bursary' }))
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
    await waitFor(() => expect(address()).toBe(`/admin/payments?programme=${FLAGSHIP}`))
  })
})

describe('(d) the link outranks an earlier pick', () => {
  function PickFlagship() {
    const { select } = useProgrammeScope()
    return <button type="button" onClick={() => select(FLAGSHIP)}>pick-flagship</button>
  }

  it('the query wins on mount — it is the more specific instruction', async () => {
    const view = render(<GiftScope><PickFlagship /></GiftScope>)
    fireEvent.click(screen.getByText('pick-flagship'))
    expect(scopeChosen()).toBe(FLAGSHIP)
    openAt(`/admin/payments?programme=${SABAH}`)
    view.rerender(page())
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    expect(scopeChosen()).toBe(SABAH)
    expect(runsAskedFor()).not.toContain(FLAGSHIP)
  })
})

describe('(e)(g) after mount the query FOLLOWS the crumb — with replace, never push', () => {
  it('switching gift rewrites the address bar in place', async () => {
    openAt(`/admin/payments?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(urlRouter.replace).toHaveBeenCalledWith(
      `/admin/payments?programme=${FLAGSHIP}`, { scroll: false }))
    expect(urlRouter.push).not.toHaveBeenCalled()
    expect(address()).toBe(`/admin/payments?programme=${FLAGSHIP}`)
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
  })

  it('⚠ Back does not become a gift-switcher: switching adds NO history entry', async () => {
    openAt(`/admin/payments?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalled())
    const before = window.history.length
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(address()).toContain(FLAGSHIP))
    switchCrumbTo('Sabah Bursary 2026')
    await waitFor(() => expect(address()).toContain(SABAH))
    expect(window.history.length).toBe(before)
  })

  it('a page that arrived with no query and a known gift is left exactly as it arrived', async () => {
    render(page([TWO_GIFTS[0]]))
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
    expect(urlRouter.replace).not.toHaveBeenCalled()
    expect(address()).toBe('/admin/payments')
  })

  it('(review F4) a REAL fresh load of a single-gift tenant writes the gift in, once, in place',
    async () => {
      // What the docstring now says, pinned: the list arrives after mount, `chosen` goes '' → the
      // only gift, and that change is written with `replace` — the address bar then names what the
      // page shows. No history entry; nothing written again afterwards.
      const before = window.history.length
      const view = render(page([], false))
      view.rerender(page([TWO_GIFTS[0]], true))
      await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
      await waitFor(() => expect(address()).toBe(`/admin/payments?programme=${FLAGSHIP}`))
      expect(urlRouter.replace).toHaveBeenCalledTimes(1)
      expect(urlRouter.push).not.toHaveBeenCalled()
      expect(window.history.length).toBe(before)
    })

  it('keeps any other query the page carries', async () => {
    openAt(`/admin/payments?programme=${SABAH}&x=1`)
    render(page())
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalled())
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(address()).toBe(`/admin/payments?programme=${FLAGSHIP}&x=1`))
  })
})

describe('(j) TD-298 — a reply for the gift you LEFT never overwrites the new one', () => {
  it('replies resolved out of order: the list shows the gift the crumb names', async () => {
    const forSabah = deferred<Awaited<ReturnType<typeof api.getPaymentRuns>>>()
    const forFlagship = deferred<Awaited<ReturnType<typeof api.getPaymentRuns>>>()
    mockApi.getPaymentRuns.mockImplementation(
      (code) => (code === SABAH ? forSabah.promise : forFlagship.promise))
    openAt(`/admin/payments?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(SABAH, { token: 'tok' }))
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(FLAGSHIP, { token: 'tok' }))
    // The NEW gift answers first; the slow reply for the gift we left lands after it.
    forFlagship.resolve(runs(run(2, 'PR-FLAGSHIP')))
    expect((await screen.findAllByText('PR-FLAGSHIP')).length).toBeGreaterThan(0)
    // Inside `act`, so a state update the stale reply makes is FLUSHED before we look — outside
    // it, nothing guarantees the render happened, and the assertion below could pass vacuously.
    await act(async () => { forSabah.resolve(runs(run(1, 'PR-SABAH'))) })
    expect(screen.queryAllByText('PR-SABAH')).toHaveLength(0)
    expect(screen.getAllByText('PR-FLAGSHIP').length).toBeGreaterThan(0)
    expect(crumbText()).toContain('Flagship Bursary')
  })
})
