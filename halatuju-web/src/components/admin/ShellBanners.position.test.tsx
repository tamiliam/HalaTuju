/**
 * @jest-environment jsdom
 *
 * Request #69 (2026-11-17, board 4): the one-tap "highest position" question in the console's
 * top-banner slot. It shows only when nothing important is missing (or the important banner was hidden
 * by its X), never to someone who has answered, never on My Profile, never beside another banner; the X
 * hides it for 7 days (the profile banner's own store); one tap saves through `PATCH admin/me/`,
 * thanks the reader and then goes away by itself. Review round: never asked of someone the server leaves
 * the item out for (a source user or a referral partner).
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import ShellBanners, { THANKS_MS } from './ShellBanners'
import type { CompletionKey, ProfileCompletion } from '@/lib/admin-api'
import { updateAdminMe } from '@/lib/admin-api/profiles'
import { getOverdueSummary } from '@/lib/admin-api/invoices'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}(${Object.values(v).join('|')})` : k) }),
}))
jest.mock('next/link', () => ({ __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }))
jest.mock('@/lib/admin-api/profiles', () => ({
  ...jest.requireActual('@/lib/admin-api/profiles'),
  updateAdminMe: jest.fn(),
}))
jest.mock('@/lib/admin-api/invoices', () => ({ getOverdueSummary: jest.fn() }))

const DAY = 24 * 60 * 60 * 1000
const KEYS: CompletionKey[] = ['photo', 'name', 'job_title', 'highest_position', 'about', 'phone']
const completion = (answered: boolean, missing: CompletionKey[] = []): ProfileCompletion => ({
  items: KEYS.map((key) => ({ key, done: key === 'highest_position' ? answered : !missing.includes(key) })),
  done: 4, total: 6, percent: 67, important_missing: missing })
const props = (over: Partial<React.ComponentProps<typeof ShellBanners>> = {}) => ({
  pathname: '/admin/scholarship', accountId: 7, completion: completion(false),
  profileHref: '/admin/profile', token: 'tok', ...over })
const save = updateAdminMe as jest.Mock

beforeEach(() => {
  window.localStorage.clear(); save.mockReset(); (getOverdueSummary as jest.Mock).mockReset()
  jest.restoreAllMocks()
})

it('asks the question with the four full choices as 44 px buttons, the why line and the X, in blue', () => {
  render(<ShellBanners {...props()} />)
  const banner = screen.getByTestId('top-banner-position')
  expect(banner.getAttribute('role')).toBe('status')
  expect(banner.className).toContain('bg-info-50')
  expect(banner.textContent).toContain('admin.nudge.positionQuestion')
  expect(banner.textContent).toContain('admin.nudge.positionWhy')
  for (const k of ['c_level', 'head', 'manager', 'individual']) {
    const b = screen.getByRole('button', { name: `admin.position.${k}` })
    expect(b.className).toContain('min-h-11')
    expect(b.className).toContain('border-info-200')
    expect(b.className).toContain('text-info-700')
  }
  expect(screen.getByRole('button', { name: 'admin.nudge.hide7' }).className).toMatch(/\bh-11\b.*\bw-11\b/)
})

it('the important profile banner wins; the question waits (never two banners)', () => {
  render(<ShellBanners {...props({ completion: completion(false, ['photo']) })} />)
  expect(screen.getByTestId('top-banner-profile')).toBeTruthy()
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
})

it('the overdue banner wins too', async () => {
  (getOverdueSummary as jest.Mock).mockResolvedValue({ overdue: {
    invoice_id: 1, number: 'INV-1', currency: 'MYR', balance_myr: '10.00', due_on: '2026-11-01',
    days_overdue: 3, count: 1, more: 0 } })
  render(<ShellBanners {...props({ billingLive: true })} />)
  expect(await screen.findByTestId('top-banner-overdue')).toBeTruthy()
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
})

it('once the important banner is hidden by its X, the question may take the slot', () => {
  render(<ShellBanners {...props({ completion: completion(false, ['photo']) })} />)
  fireEvent.click(screen.getByRole('button', { name: 'admin.nudge.hide7' }))
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
  expect(screen.getAllByRole('status')).toHaveLength(1)
  expect(screen.getByTestId('top-banner-position')).toBeTruthy()
})

it('is never shown to someone who has answered, on My Profile, or with no completion', () => {
  const { rerender } = render(<ShellBanners {...props({ completion: completion(true) })} />)
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
  rerender(<ShellBanners {...props({ pathname: '/admin/profile' })} />)
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
  rerender(<ShellBanners {...props({ completion: null })} />)
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
})

it('the X only hides it — 7 days, this account, nothing saved', () => {
  const t0 = Date.UTC(2026, 10, 17)
  const now = jest.spyOn(Date, 'now').mockReturnValue(t0)
  const { unmount } = render(<ShellBanners {...props()} />)
  fireEvent.click(screen.getByRole('button', { name: 'admin.nudge.hide7' }))
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
  expect(save).not.toHaveBeenCalled()
  expect(window.localStorage.getItem('halatuju.banner.position.7')).not.toBeNull()
  unmount()
  now.mockReturnValue(t0 + 6 * DAY)
  const again = render(<ShellBanners {...props()} />)
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
  again.unmount()
  now.mockReturnValue(t0 + 7 * DAY)
  render(<ShellBanners {...props()} />)
  expect(screen.getByTestId('top-banner-position')).toBeTruthy()
})

it('one tap saves, hands back the completion, thanks the reader and goes away by itself', async () => {
  jest.useFakeTimers()
  try {
    const answered = completion(true)
    save.mockResolvedValue({ highest_position: 'head', completion: answered })
    const onCompletion = jest.fn()
    render(<ShellBanners {...props({ onCompletion })} />)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'admin.position.head' })) })
    expect(save).toHaveBeenCalledWith({ highest_position: 'head' }, { token: 'tok' })
    expect(onCompletion).toHaveBeenCalledWith(answered)
    expect(screen.queryByTestId('top-banner-position')).toBeNull()
    expect(screen.getByTestId('top-banner-position-thanks').textContent).toContain('admin.nudge.positionThanks')
    act(() => { jest.advanceTimersByTime(THANKS_MS) })
    expect(screen.queryByTestId('top-banner-position-thanks')).toBeNull()
    expect(screen.queryByTestId('top-banner-position')).toBeNull()
  } finally { jest.useRealTimers() }
})

it('a failed save says so and keeps the buttons', async () => {
  save.mockRejectedValue(Object.assign(new Error('x'), { status: 500 }))
  render(<ShellBanners {...props()} />)
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'admin.position.manager' })) })
  expect(screen.getByRole('alert').textContent).toBe('admin.nudge.positionFailed')
  expect((screen.getByRole('button', { name: 'admin.position.manager' }) as HTMLButtonElement).disabled).toBe(false)
  expect(screen.queryByTestId('top-banner-position-thanks')).toBeNull()
})

it('not asked when the served items leave the highest position out (a source user or a referral partner)', () => {
  const items = KEYS.filter((k) => k !== 'highest_position').map((key) => ({ key, done: true }))
  render(<ShellBanners {...props({ completion: { items, done: 5, total: 5, percent: 100, important_missing: [] } })} />)
  expect(screen.queryByTestId('top-banner-position')).toBeNull()
  expect(screen.queryByRole('button', { name: 'admin.position.head' })).toBeNull()
})
