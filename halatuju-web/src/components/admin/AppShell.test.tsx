/**
 * @jest-environment jsdom
 *
 * Renders the actual shell for every role. The registry snapshot in navigation.test.ts proves
 * `visibleNav` returns the right ids; this proves the SHELL puts them on screen — that the
 * groups compose, the reserved slots render disabled rather than as links, and a role sees no
 * scope it cannot reach.
 *
 * It is not a substitute for looking at it: this asserts structure, not whether the thing is
 * pleasant to use. The browser pass is still owed (see the sprint notes).
 */
import { render, screen, within } from '@testing-library/react'

import { AppShell } from './AppShell'
import type { AdminRoleName } from '@/lib/navigation'

let mockRole: Record<string, unknown> = {}

jest.mock('next/navigation', () => ({
  usePathname: () => '/admin/scholarship',
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ role: mockRole, token: null }) }))
jest.mock('@/lib/admin-supabase', () => ({ adminSignOut: jest.fn() }))
// No token, so the probe hook resolves to nothing and the badge never fetches — the dark
// features stay dark, which is the correct default (see canSee).
jest.mock('@/lib/admin-api', () => ({
  getPendingSponsorCount: jest.fn(() => Promise.resolve({ count: 0 })),
  getOrgRequestCount: jest.fn(() => Promise.reject(new Error('404'))),
  getBillingUsage: jest.fn(() => Promise.reject(new Error('404'))),
}))

const asRole = (role: AdminRoleName, extra: Record<string, unknown> = {}) => {
  mockRole = { role, admin_name: 'Test Person', is_super_admin: role === 'super', ...extra }
}

/** The desktop sidebar (the mobile drawer is not mounted until the hamburger is pressed). */
const sidebar = () => screen.getByRole('navigation', { name: 'admin.shell.primaryNav' })

describe('AppShell renders the scope sidebar per role', () => {
  it('gives a super all three scopes', () => {
    asRole('super')
    render(<AppShell>content</AppShell>)
    const nav = sidebar()
    expect(within(nav).getByText('admin.nav.group.platform')).toBeTruthy()
    expect(within(nav).getByText('admin.nav.group.organisation')).toBeTruthy()
    expect(within(nav).getByText('admin.nav.group.programme')).toBeTruthy()
  })

  it('gives a reviewer the programme scope only — no organisation, no platform', () => {
    asRole('reviewer')
    render(<AppShell>content</AppShell>)
    const nav = sidebar()
    expect(within(nav).getByText('admin.nav.group.programme')).toBeTruthy()
    expect(within(nav).queryByText('admin.nav.group.organisation')).toBeNull()
    expect(within(nav).queryByText('admin.nav.group.platform')).toBeNull()
  })

  it('gives finance the organisation scope and never Applications', () => {
    asRole('finance')
    render(<AppShell>content</AppShell>)
    const nav = sidebar()
    expect(within(nav).getByText('admin.nav.group.organisation')).toBeTruthy()
    expect(within(nav).queryByText('admin.scholarship.nav')).toBeNull()
  })

  it('never renders the utility scope in the sidebar — it lives in the account menu', () => {
    asRole('super')
    render(<AppShell>content</AppShell>)
    expect(within(sidebar()).queryByText('admin.nav.group.utility')).toBeNull()
  })

  it('renders a reserved slot as disabled text, never as a link', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    const nav = sidebar()
    const fund = within(nav).getByText('admin.nav.fund').closest('[aria-disabled]')
    expect(fund).toBeTruthy()
    // and it is not among the sidebar's links
    const hrefs = within(nav).getAllByRole('link').map((a) => a.getAttribute('href'))
    expect(hrefs).not.toContain('/admin/programme/fund')
  })

  it('marks the current page for a screen reader as well as visually', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    const current = within(sidebar()).getAllByRole('link')
      .filter((a) => a.getAttribute('aria-current') === 'page')
    expect(current).toHaveLength(1)
    expect(current[0].getAttribute('href')).toBe('/admin/scholarship')
  })

  it('shows the person and renders the page content', () => {
    asRole('org_admin', { org_name: 'BrightPath' })
    render(<AppShell>the page</AppShell>)
    expect(screen.getAllByText('Test Person').length).toBeGreaterThan(0)
    expect(screen.getByText('the page')).toBeTruthy()
  })
})
