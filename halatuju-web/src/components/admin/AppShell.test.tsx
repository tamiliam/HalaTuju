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
import { fireEvent, render, screen, within } from '@testing-library/react'

import { AppShell } from './AppShell'
import type { AdminRoleName } from '@/lib/navigation'

let mockRole: Record<string, unknown> = {}

const mockPush = jest.fn()

jest.mock('next/navigation', () => ({
  usePathname: () => '/admin/scholarship',
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
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

// ── N4: the rail's pin, and the G-then-X chord ───────────────────────────────
describe('the rail pin', () => {
  beforeEach(() => window.localStorage.clear())

  it('starts hover-open — the first paint must not depend on storage', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    expect(sidebar().style.width).toBe('48px')
  })

  it('pins on click, and says so to a screen reader', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    const pin = screen.getByRole('button', { name: 'admin.shell.pinNav' })
    expect(pin.getAttribute('aria-pressed')).toBe('false')

    fireEvent.click(pin)
    expect(sidebar().style.width).toBe('216px')
    expect(screen.getByRole('button', { name: 'admin.shell.unpinNav' })
      .getAttribute('aria-pressed')).toBe('true')
  })

  it('remembers the choice for the next visit', () => {
    asRole('org_admin')
    const first = render(<AppShell>content</AppShell>)
    fireEvent.click(screen.getByRole('button', { name: 'admin.shell.pinNav' }))
    first.unmount()

    render(<AppShell>content</AppShell>)
    expect(sidebar().style.width).toBe('216px')
  })

  it('survives storage being unavailable rather than taking the shell down', () => {
    const boom = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError: storage disabled')
    })
    asRole('org_admin')
    expect(() => render(<AppShell>content</AppShell>)).not.toThrow()
    boom.mockRestore()
  })
})

describe('G then a letter jumps', () => {
  const press = (key: string) => fireEvent.keyDown(document, { key })

  beforeEach(() => { mockPush.mockClear(); window.localStorage.clear() })

  it('opens the page the chord names', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    press('g'); press('t')
    expect(mockPush).toHaveBeenCalledWith('/admin/organisation/staff')
  })

  it('does nothing for a letter nobody claims', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    press('g'); press('z')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('will not carry a reviewer to a page their menu does not offer', () => {
    asRole('reviewer')
    render(<AppShell>content</AppShell>)
    press('g'); press('p')          // Sponsors — organisation scope, not theirs
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('ignores the chord while someone is typing', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    press('g'); press('t')
    expect(mockPush).not.toHaveBeenCalled()
    input.remove()
  })

  it('needs the prefix — a bare letter navigates nowhere', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    press('t')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('disarms after a wrong second key instead of staying armed', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    press('g'); press('z')          // consumed, goes nowhere
    press('t')                      // must NOT be read as the second half
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('is not fired by Ctrl-G — that belongs to the browser', () => {
    asRole('org_admin')
    render(<AppShell>content</AppShell>)
    fireEvent.keyDown(document, { key: 'g', ctrlKey: true })
    press('t')
    expect(mockPush).not.toHaveBeenCalled()
  })
})
