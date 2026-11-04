/**
 * @jest-environment jsdom
 *
 * The Overview's pending cards (T5c P5b). Pinned: only served keys are drawn; a served zero stays, muted, "Nothing
 * waiting"; all-zero adds one calm line; each role's cards open the right page; tones; the count extras.
 */
import { render, screen, waitFor } from '@testing-library/react'

import PendingCards from './PendingCards'
import * as api from '@/lib/admin-api/myPending'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}|${Object.values(v).join(',')}` : k) }),
}))
jest.mock('@/lib/admin-api/myPending')
const mockApi = api as jest.Mocked<typeof api>
const serve = (cards: api.PendingCard[]) => mockApi.getMyPending.mockResolvedValue({ cards })
const href = (k: string) => screen.getByTestId(`pending-${k}`).getAttribute('href')

beforeEach(() => jest.clearAllMocks())

describe('per-role views', () => {
  it('admin: the main cards, due soon on Overdue, and the quieter row linking out', async () => {
    serve([{ key: 'unassigned', count: 4 }, { key: 'overdue', count: 2, due_soon: 3 }, { key: 'awaiting_qc', count: 1 },
      { key: 'sponsors_to_vet', count: 5 }, { key: 'invitations', count: 1 }, { key: 'payment_runs', count: 2 },
      { key: 'requests', count: 3 }])
    render(<PendingCards token="t" />)
    await screen.findByTestId('pending-unassigned')
    expect(href('unassigned')).toBe('/admin/scholarship?status=profile_complete&assigned=none&ready=1')
    expect(href('overdue')).toBe('/admin/scholarship?band=overdue')
    expect(href('awaiting_qc')).toBe('/admin/scholarship?status=interviewed')
    expect(href('sponsors_to_vet')).toBe('/admin/sponsors')
    expect(href('invitations')).toBe('/admin/organisation/staff')
    expect(href('payment_runs')).toBe('/admin/payments')
    expect(href('requests')).toBe('/admin/requests?tab=action')
    expect(screen.getByTestId('pending-overdue').textContent).toBe('admin.overview.overdue2')   // no subline
  })

  it('finance: runs, wallet credits, vetting, invitations; no scholarship cards', async () => {
    serve([{ key: 'payment_runs', count: 1 }, { key: 'wallet_credits', count: 2 },
      { key: 'sponsors_to_vet', count: 3 }, { key: 'invitations', count: 0 }])
    render(<PendingCards token="t" />)
    await screen.findByTestId('pending-wallet_credits')
    expect(href('wallet_credits')).toBe('/admin/sponsors')
    expect(screen.queryByTestId('pending-unassigned')).toBeNull()
  })

  it('qc: awaiting, no age subline', async () => {
    serve([{ key: 'qc_awaiting', count: 7, oldest_days: 12 }])
    render(<PendingCards token="t" />)
    const c = await screen.findByTestId('pending-qc_awaiting')
    expect(c.getAttribute('href')).toBe('/admin/programme/overview')
    expect(c.textContent).toBe('admin.overview.qcAwaiting7')
  })

  it('reviewer: due soon amber, overdue red', async () => {
    serve([{ key: 'my_open', count: 6 }, { key: 'my_due_soon', count: 2 }, { key: 'my_overdue', count: 1 }])
    render(<PendingCards token="t" />)
    await screen.findByTestId('pending-my_open')
    expect(screen.getByTestId('pending-count-my_due_soon').className).toContain('text-caution-700')
    expect(screen.getByTestId('pending-count-my_overdue').className).toContain('text-critical-600')
    expect(screen.getByTestId('pending-count-my_open').className).not.toContain('caution')
    expect(href('my_open')).toBe('/admin/scholarship?assigned=me')
    expect(href('my_due_soon')).toBe('/admin/scholarship?assigned=me&band=due_soon')
    expect(href('my_overdue')).toBe('/admin/scholarship?assigned=me&band=overdue')
  })

  it('mentor: cards open My students, and there is no "not met" card unless served', async () => {
    serve([{ key: 'mentees', count: 5 }, { key: 'asked_help', count: 1 }])
    render(<PendingCards token="t" />)
    await screen.findByTestId('pending-mentees')
    expect(href('mentees')).toBe('/admin/my-students')
    expect(href('asked_help')).toBe('/admin/my-students')
    expect(screen.queryByTestId('pending-not_met')).toBeNull()
  })
})

describe('the rules', () => {
  it('an absent card is not drawn, and an unknown key is ignored', async () => {
    serve([{ key: 'my_open', count: 1 }, { key: 'bogus' as never, count: 9 }])
    render(<PendingCards token="t" />)
    await screen.findByTestId('pending-my_open')
    expect(screen.queryByTestId('pending-my_overdue')).toBeNull()
    expect(screen.queryByTestId('pending-bogus')).toBeNull()
  })

  it('a zero card stays, muted, with no subline; others are not muted and there is no all-clear line', async () => {
    serve([{ key: 'unassigned', count: 0 }, { key: 'overdue', count: 2 }])
    render(<PendingCards token="t" />)
    const z = await screen.findByTestId('pending-unassigned')
    expect(z.getAttribute('data-zero')).toBe('true')
    expect(z.textContent).toBe('admin.overview.unassigned0')
    expect(screen.getByTestId('pending-overdue').getAttribute('data-zero')).toBe('false')
    expect(screen.queryByTestId('pending-all-clear')).toBeNull()
  })

  it('every card zero: one calm line above them', async () => {
    serve([{ key: 'unassigned', count: 0 }, { key: 'overdue', count: 0, due_soon: 0 }])
    render(<PendingCards token="t" />)
    expect((await screen.findByTestId('pending-all-clear')).textContent).toBe('admin.overview.allClear')
    expect(screen.getByTestId('pending-unassigned')).toBeTruthy()
  })

  it('a failed read draws nothing and does not throw', async () => {
    mockApi.getMyPending.mockRejectedValue(new Error('x'))
    const { container } = render(<PendingCards token="t" />)
    await waitFor(() => expect(mockApi.getMyPending).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="pending-cards"]')).toBeNull()
  })
})
