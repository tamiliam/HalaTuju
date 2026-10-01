/**
 * @jest-environment jsdom
 *
 * Payments — New run is offered only for a gift the server would accept (TD-299, TD-303).
 *
 * Mounted inside the REAL `AppShell`, because both defects live in the shell's half: the scopes
 * fetch (whose FAILURE is TD-303) and the mapping of `scopes.programmes[].organisation_id` onto
 * the scope's choices (which TD-299 reads). A harness that hands the provider a list directly
 * could not tell a failed fetch from an empty answer, nor prove the shell passes the id on.
 *
 *   · TD-299 — a super standing in ANOTHER organisation's gift used to see New run; Create then
 *     404'd (`create_run` reads the caller's own `owning_organisation`).
 *   · TD-303 — with the address naming a gift and the scopes list failed or empty, New run sent no
 *     gift and the server would have picked the org's only live one, not the one in the URL.
 * Neighbours (lessons.md): the caller's OWN gift, a caller with no organisation, and an empty or
 * failed list with NO gift in the address — all three keep the button exactly as before.
 */
import { render, screen, waitFor } from '@testing-library/react'

import { AppShell } from '@/components/admin/AppShell'
import PaymentsLandingPage from './page'
import * as api from '@/lib/admin-api'
import { openAt } from '@/test/giftUrl'

let mockRole: Record<string, unknown> = {}
jest.mock('next/navigation', () => ({
  ...jest.requireActual('@/test/giftUrl').navigationMock,
  usePathname: () => window.location.pathname,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ role: mockRole, token: 'tok' }) }))
jest.mock('@/lib/admin-supabase', () => ({ adminSignOut: jest.fn() }))
jest.mock('@/lib/admin-api', () => ({
  getPendingSponsorCount: jest.fn(() => Promise.resolve({ count: 0 })),
  getOrgRequestCount: jest.fn(() => Promise.reject(new Error('404'))),
  getBillingUsage: jest.fn(() => Promise.reject(new Error('404'))),
  getAdminScopes: jest.fn(),
  getPaymentRuns: jest.fn(() => Promise.resolve({ runs: [] })),
  getFundingSummary: jest.fn(() => Promise.resolve({ rows: [], totals: {} })),
  createPaymentRun: jest.fn(),
}))

const mockApi = api as jest.Mocked<typeof api>
const OURS = 'brightpath-flagship'
const THEIRS = 'other-tenant-gift'
const gift = (id: number, code: string, name: string, organisation_id: number) =>
  ({ id, code, name, organisation_id, is_active: true })
/** A super's list: every tenant's gifts. Org 11 is the caller's own. */
const BOTH = {
  organisations: [{ id: 11, code: 'bp', name: 'BP' }, { id: 22, code: 'ot', name: 'OT' }],
  programmes: [gift(1, OURS, 'Flagship Bursary', 11), gift(2, THEIRS, 'Other Tenant Bursary', 22)],
} as unknown as api.AdminScopes

const asSuper = (owning_org_id: number | null = 11) => {
  mockRole = { role: 'super', is_super_admin: true, admin_name: 'Test Person', owning_org_id }
}

beforeEach(() => {
  jest.clearAllMocks()
  asSuper()
  mockApi.getAdminScopes.mockResolvedValue(BOTH)
})

const mount = () => render(<AppShell><PaymentsLandingPage /></AppShell>)
const newRun = () => screen.queryByText(/admin\.payments\.newRun/)
const blocked = () => screen.queryByTestId('new-run-blocked')

describe('TD-299 — New run only inside the caller\'s OWN organisation\'s gift', () => {
  it('a super inside another organisation\'s gift: no New run, one line saying why', async () => {
    openAt(`/admin/payments?programme=${THEIRS}`)
    mount()
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(THEIRS, { token: 'tok' }))
    expect(newRun()).toBeNull()
    expect(blocked()?.textContent).toBe('admin.payments.otherOrgGift')
  })

  it('the same super inside their own organisation\'s gift: New run, no line', async () => {
    openAt(`/admin/payments?programme=${OURS}`)
    mount()
    expect(await screen.findByText(/admin\.payments\.newRun/)).toBeTruthy()
    expect(blocked()).toBeNull()
  })

  it('a caller with NO organisation keeps the button — the server\'s `no_org` answer is unchanged', async () => {
    asSuper(null)
    openAt(`/admin/payments?programme=${THEIRS}`)
    mount()
    expect(await screen.findByText(/admin\.payments\.newRun/)).toBeTruthy()
    expect(blocked()).toBeNull()
  })
})

describe('TD-303 — the address names a gift the list cannot confirm', () => {
  const failed = () => mockApi.getAdminScopes.mockRejectedValue(new Error('offline'))
  const empty = () => mockApi.getAdminScopes.mockResolvedValue(
    { organisations: [], programmes: [] } as unknown as api.AdminScopes)

  it('the scopes fetch FAILED: the page opens, no New run, and a line says the list could not load', async () => {
    failed()
    openAt(`/admin/payments?programme=${OURS}`)
    mount()
    // The page still opens (review F5's degrade): the runs are read, with no gift to send.
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(undefined, { token: 'tok' }))
    expect(newRun()).toBeNull()
    expect(blocked()?.textContent).toBe('admin.programmes.loadFailed')
  })

  it('review F4: the list came back EMPTY (no gifts at all): no New run, and NO "could not load" line', async () => {
    // The list loaded fine — it is genuinely empty — so saying it failed would be untrue.
    empty()
    openAt(`/admin/payments?programme=${OURS}`)
    mount()
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(undefined, { token: 'tok' }))
    expect(newRun()).toBeNull()
    expect(blocked()).toBeNull()
    expect(screen.queryByText('admin.programmes.loadFailed')).toBeNull()
  })

  for (const [state, arrange] of [
    ['the scopes fetch FAILED', failed],
    ['the scopes list came back EMPTY', empty],
  ] as const) {

    it(`${state} and NO gift in the address: the button stays, as before`, async () => {
      arrange()
      openAt('/admin/payments')
      mount()
      expect(await screen.findByText(/admin\.payments\.newRun/)).toBeTruthy()
      expect(blocked()).toBeNull()
    })
  }
})
