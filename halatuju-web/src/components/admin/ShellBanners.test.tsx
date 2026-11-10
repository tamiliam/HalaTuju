/**
 * @jest-environment jsdom
 *
 * Staff nudges (2026-11-08): the console's top-banner slot and its profile banner (decision 4) —
 * blue, names what is missing, "Complete profile", not on My Profile, X hides it for 7 days, it
 * returns while still incomplete and is gone once filled. Rendered, with the real dismissal store.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import ShellBanners, { joinList } from './ShellBanners'
import { LazyShellBanners } from './LazyShellBanners'
import type { ProfileCompletion } from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}(${Object.values(v).join('|')})` : k) }),
}))
jest.mock('next/link', () => ({ __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }))

const DAY = 24 * 60 * 60 * 1000
const completion = (missing: ProfileCompletion['important_missing']): ProfileCompletion => ({
  items: [], done: 3, total: 5, percent: 60, important_missing: missing })
const props = (over: Partial<React.ComponentProps<typeof ShellBanners>> = {}) => ({
  pathname: '/admin/scholarship', accountId: 7, completion: completion(['photo', 'phone']),
  profileHref: '/admin/profile', ...over })

beforeEach(() => { window.localStorage.clear(); jest.restoreAllMocks() })

it('names what is missing, links to the profile, and is a status (blue), not an alert', () => {
  render(<ShellBanners {...props()} />)
  const banner = screen.getByTestId('top-banner-profile')
  expect(banner.getAttribute('role')).toBe('status')
  expect(banner.className).toContain('bg-info-50')
  expect(banner.textContent).toContain('admin.nudge.missing(admin.nudge.item.photo admin.nudge.and admin.nudge.item.phone)')
  expect(banner.textContent).toContain('admin.nudge.helpMany')
  expect(screen.getByRole('link', { name: 'admin.nudge.link' }).getAttribute('href')).toBe('/admin/profile')
  expect(screen.getByRole('button', { name: 'admin.nudge.hide7' })).toBeTruthy()
})

it('one missing item reads in the singular', () => {
  render(<ShellBanners {...props({ completion: completion(['phone']) })} />)
  expect(screen.getByTestId('top-banner-profile').textContent).toContain('admin.nudge.missing(admin.nudge.item.phone) admin.nudge.helpOne')
})

it('is not shown on My Profile itself', () => {
  render(<ShellBanners {...props({ pathname: '/admin/profile' })} />)
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
})

it('is gone once the important items are filled, and for a super (no completion)', () => {
  const { rerender } = render(<ShellBanners {...props({ completion: completion([]) })} />)
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
  rerender(<ShellBanners {...props({ completion: null })} />)
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
  rerender(<ShellBanners {...props({ accountId: null })} />)
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
})

it('the X hides it for 7 days for this account, then it returns while still incomplete', () => {
  const t0 = Date.UTC(2026, 10, 8)
  const now = jest.spyOn(Date, 'now').mockReturnValue(t0)
  const { unmount } = render(<ShellBanners {...props()} />)
  fireEvent.click(screen.getByRole('button', { name: 'admin.nudge.hide7' }))
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
  unmount()

  now.mockReturnValue(t0 + 6 * DAY)
  const second = render(<ShellBanners {...props()} />)
  expect(screen.queryByTestId('top-banner-profile')).toBeNull()
  second.unmount()
  // Another account in the same browser is not hidden by it.
  const other = render(<ShellBanners {...props({ accountId: 8 })} />)
  expect(screen.getByTestId('top-banner-profile')).toBeTruthy()
  other.unmount()

  now.mockReturnValue(t0 + 7 * DAY)
  render(<ShellBanners {...props()} />)
  expect(screen.getByTestId('top-banner-profile')).toBeTruthy()
})

it('the X is a 44 x 44 target and the link is 44 px tall (Mobile Standard)', () => {
  render(<ShellBanners {...props()} />)
  expect(screen.getByRole('button', { name: 'admin.nudge.hide7' }).className).toMatch(/\bh-11\b.*\bw-11\b/)
  expect(screen.getByRole('link', { name: 'admin.nudge.link' }).className).toContain('min-h-11')
})

it('the lazy slot renders the banner once its chunk arrives', async () => {
  render(<LazyShellBanners {...props()} />)
  expect(await screen.findByTestId('top-banner-profile')).toBeTruthy()
})

it('joins a list in the reader\'s words', () => {
  expect(joinList(['a'], 'and')).toBe('a')
  expect(joinList(['a', 'b'], 'dan')).toBe('a dan b')
  expect(joinList(['a', 'b', 'c'], 'and')).toBe('a, b and c')
})
