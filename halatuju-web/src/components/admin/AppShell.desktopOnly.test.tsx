/**
 * @jest-environment jsdom
 *
 * Mobile M7b (owner): on a phone the shared "use a computer" panel REPLACES a desktop-only page, with one way back;
 * from md the page is unchanged. The shell mounts the panel ONCE, for exactly the routes `mobileClass.ts` classes
 * `desktop` (the route list itself is pinned by `desktopOnly.test.ts`). jsdom applies no media query, so this
 * reads the classes that do the replacing: the panel is `md:hidden`, the page `max-md:hidden`.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { AppShell } from './AppShell'

const mockPush = jest.fn()
const mockBack = jest.fn()
jest.mock('next/navigation', () => ({
  usePathname: () => '/admin',
  useRouter: () => ({ push: mockPush, replace: jest.fn(), back: mockBack }),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ role: { role: 'super', admin_name: 'T', is_super_admin: true }, token: null }),
}))
jest.mock('@/lib/admin-supabase', () => ({ adminSignOut: jest.fn() }))
jest.mock('@/lib/admin-api', () => ({
  getPendingSponsorCount: jest.fn(() => Promise.resolve({ count: 0 })),
  getOrgRequestCount: jest.fn(() => Promise.reject(new Error('404'))),
  getBillingUsage: jest.fn(() => Promise.reject(new Error('404'))),
  getAdminScopes: jest.fn(() => Promise.resolve({ organisations: [], programmes: [] })),
  getPaymentRuns: jest.fn(() => Promise.resolve({ runs: [] })),
  getSystemHealth: jest.fn(() => Promise.resolve({ overall: 'green', checked_at: '', rows: [] })),
}))

const page = () => screen.getByText('THE PAGE').closest('[class]') as HTMLElement
const hiddenOnPhone = (el: Element) => !!el.closest('.max-md\\:hidden')

it.each([
  ['/admin/billing-rates', 'billingRates'], ['/admin/billing', 'billing'], ['/admin/course-data', 'courseData'],
  ['/admin/contracts', 'contracts'], ['/admin/contracts/12', 'contract'], ['/admin/sponsors/terms/3', 'sponsorTerms'],
])('%s: the panel replaces the page below md, with its own reason', async (path, key) => {
  render(<AppShell path={path}><p>THE PAGE</p></AppShell>)
  await act(async () => {})
  const panels = document.querySelectorAll('[data-desktop-only]')
  expect(panels).toHaveLength(1)
  expect(panels[0].className.split(' ')).toContain('md:hidden')
  expect(hiddenOnPhone(panels[0])).toBe(false)
  expect(hiddenOnPhone(page())).toBe(true)
  expect(screen.getByText(`admin.desktopOnly.whyLabel admin.desktopOnly.why.${key}`)).toBeTruthy()
})

it.each(['/admin/scholars', '/admin/billing-rates/x', '/admin/contracts/12/edit', '/admin/sponsors', '/admin'])(
  '%s: no panel, and the page is not hidden at any width', async (path) => {
    render(<AppShell path={path}><p>THE PAGE</p></AppShell>)
    await act(async () => {})
    expect(document.querySelector('[data-desktop-only]')).toBeNull()
    expect(hiddenOnPhone(page())).toBe(false)
  })

describe('one way back, 44 px', () => {
  const original = window.history.length
  afterEach(() => Object.defineProperty(window.history, 'length', { value: original, configurable: true }))

  it('with a page to go back to, it goes back', async () => {
    Object.defineProperty(window.history, 'length', { value: 3, configurable: true })
    render(<AppShell path="/admin/billing"><p>THE PAGE</p></AppShell>)
    await act(async () => {})
    const backs = document.querySelectorAll('[data-desktop-only-back]')
    expect(backs).toHaveLength(1)
    expect(backs[0].className.split(' ')).toContain('min-h-11')
    fireEvent.click(backs[0])
    expect(mockBack).toHaveBeenCalledTimes(1)
  })

  it('opened directly (nothing to go back to), it links to the start page', async () => {
    Object.defineProperty(window.history, 'length', { value: 1, configurable: true })
    render(<AppShell path="/admin/billing"><p>THE PAGE</p></AppShell>)
    await act(async () => {})
    const backs = document.querySelectorAll('[data-desktop-only-back]')
    expect(backs).toHaveLength(1)
    expect(backs[0].getAttribute('href')).toBe('/admin')
  })
})
