/**
 * @jest-environment jsdom
 *
 * Staff nudges sprint 3 (2026-11-09): the red overdue banner (decisions 5-7) in the console's top-banner
 * slot — the SERVER's summary (`GET billing/overdue/`, drift-test: invoice_overdue.org_summary), never
 * derived here; the oldest invoice, what is owed, how many days late, "and N more"; "View invoice" opens
 * Billing; it wins over the profile banner; the X hides it until the next sign-in. Rendered, with the
 * real dismissal store.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import ShellBanners from './ShellBanners'
import type { ProfileCompletion } from '@/lib/admin-api'
import type { OverdueSummary } from '@/lib/admin-api/invoices'
import * as invoicesApi from '@/lib/admin-api/invoices'
import { clearSignInDismissals } from '@/lib/topBanner'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}(${Object.values(v).join('|')})` : k) }),
}))
jest.mock('next/link', () => ({ __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }))
jest.mock('@/lib/admin-api/invoices', () => ({ getOverdueSummary: jest.fn() }))

const getOverdue = invoicesApi.getOverdueSummary as jest.Mock
const SUMMARY: OverdueSummary = {
  invoice_id: 3, number: 'INV-2026-0003', currency: 'MYR', balance_myr: '1234.00', due_on: '2026-10-28',
  days_overdue: 12, count: 1, more: 0,
}
const completion: ProfileCompletion = { items: [], done: 3, total: 5, percent: 60, important_missing: ['photo'] }
const props = (over: Partial<React.ComponentProps<typeof ShellBanners>> = {}) => ({
  pathname: '/admin/scholarship', accountId: 7, completion, profileHref: '/admin/profile',
  token: 'tok', billingLive: true, signInStamp: '2026-11-09T01:00:00Z', ...over })

async function renderBanners(over: Partial<React.ComponentProps<typeof ShellBanners>> = {}) {
  const view = render(<ShellBanners {...props(over)} />)
  await act(async () => { await Promise.resolve() })
  return view
}

beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); getOverdue.mockReset(); getOverdue.mockResolvedValue({ overdue: SUMMARY }) })

it('shows the oldest overdue invoice in red, as an alert, over the profile banner', async () => {
  await renderBanners()
  const banner = screen.getByTestId('top-banner-overdue')
  expect(banner.getAttribute('role')).toBe('alert')
  expect(banner.className).toContain('bg-critical-50')
  expect(banner.textContent).toContain('admin.nudge.overdueTitle')
  expect(banner.textContent).toContain('admin.nudge.overdueMany(INV-2026-0003|RM1,234.00|12)')
  expect(banner.textContent).not.toContain('overdueMore')
  expect(screen.getByRole('link', { name: 'admin.nudge.overdueLink' }).getAttribute('href')).toBe('/admin/billing')
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()   // one at a time: overdue first
  expect(getOverdue).toHaveBeenCalledWith({ token: 'tok' })
})

it('says "and N more" when several are overdue, and reads one day in the singular', async () => {
  getOverdue.mockResolvedValue({ overdue: { ...SUMMARY, days_overdue: 1, count: 3, more: 2 } })
  await renderBanners()
  const text = screen.getByTestId('top-banner-overdue').textContent
  expect(text).toContain('admin.nudge.overdueOne(')
  expect(text).toContain('admin.nudge.overdueMoreMany(2)')
})

it('is not there when nothing is overdue, on a refusal, or while billing is not live', async () => {
  getOverdue.mockResolvedValue({ overdue: null })
  const a = await renderBanners()
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
  expect(screen.getByTestId('top-banner-profile')).toBeTruthy()   // the profile banner takes the slot
  a.unmount()

  getOverdue.mockRejectedValue(new Error('403'))
  const b = await renderBanners()
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
  b.unmount()

  getOverdue.mockClear()
  await renderBanners({ billingLive: false })
  expect(getOverdue).not.toHaveBeenCalled()
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
})

it('the X hides it until the next sign-in, for this account only', async () => {
  const first = await renderBanners()
  fireEvent.click(screen.getByRole('button', { name: 'admin.nudge.overdueHide' }))
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
  first.unmount()

  // Same sign-in, a new page: still hidden.
  const again = await renderBanners()
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
  again.unmount()
  // Another account in this browser is not hidden by it.
  const other = await renderBanners({ accountId: 8 })
  expect(screen.getByTestId('top-banner-overdue')).toBeTruthy()
  other.unmount()
  // Signing out and in again (a new stamp) brings it back while it is still overdue.
  clearSignInDismissals()
  await renderBanners({ signInStamp: '2026-11-10T01:00:00Z' })
  expect(screen.getByTestId('top-banner-overdue')).toBeTruthy()
})

it('without a sign-in stamp the X still hides it for this page view', async () => {
  await renderBanners({ signInStamp: null })
  fireEvent.click(screen.getByRole('button', { name: 'admin.nudge.overdueHide' }))
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
})

it('is not shown on Billing itself (its chip says it), is not asked there, and is asked afresh on the way out', async () => {
  const view = await renderBanners()
  expect(getOverdue).toHaveBeenCalledTimes(1)
  expect(screen.getByTestId('top-banner-overdue')).toBeTruthy()
  view.rerender(<ShellBanners {...props({ pathname: '/admin/billing' })} />)
  await act(async () => { await Promise.resolve() })
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
  expect(screen.getByTestId('top-banner-profile')).toBeTruthy()   // the slot falls to the next banner
  expect(getOverdue).toHaveBeenCalledTimes(1)                     // not asked on Billing
  // Still overdue: it shows again elsewhere.
  view.rerender(<ShellBanners {...props({ pathname: '/admin/scholarship' })} />)
  await act(async () => { await Promise.resolve() })
  expect(getOverdue).toHaveBeenCalledTimes(2)
  expect(screen.getByTestId('top-banner-overdue')).toBeTruthy()
  // Declared (or paid) on Billing: gone on the way out.
  view.rerender(<ShellBanners {...props({ pathname: '/admin/billing' })} />)
  getOverdue.mockResolvedValue({ overdue: null })
  view.rerender(<ShellBanners {...props({ pathname: '/admin/scholarship' })} />)
  await act(async () => { await Promise.resolve() })
  expect(getOverdue).toHaveBeenCalledTimes(3)
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
})

it('the X holds for this tab even when the account\'s sign-in stamp moves (a sign-in on another device)', async () => {
  const first = await renderBanners()
  fireEvent.click(screen.getByRole('button', { name: 'admin.nudge.overdueHide' }))
  first.unmount()
  await renderBanners({ signInStamp: '2026-11-09T05:00:00Z' })
  expect(screen.queryByTestId('top-banner-overdue')).toBeNull()
})

it('the X is a 44 x 44 target and the link is 44 px tall (Mobile Standard)', async () => {
  await renderBanners()
  expect(screen.getByRole('button', { name: 'admin.nudge.overdueHide' }).className).toMatch(/\bh-11\b.*\bw-11\b/)
  expect(screen.getByRole('link', { name: 'admin.nudge.overdueLink' }).className).toContain('min-h-11')
})
