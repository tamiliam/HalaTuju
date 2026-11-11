/**
 * @jest-environment jsdom
 *
 * Mobile M5: the sponsor portal's chrome — the three-tab bar on a phone (and the desktop row it mirrors),
 * the screens without tabs, and Log out, which must do exactly what the shell did before M5: end the
 * SPONSOR session only (`sponsorSignOut`, scope local) and go to /sponsor/login.
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import SponsorShell from './SponsorShell'
import { sponsorSignOut } from '@/lib/sponsor-supabase'

const replace = jest.fn()
let path = '/sponsor/students'
jest.mock('next/navigation', () => ({ usePathname: () => path, useRouter: () => ({ replace }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href, prefetch: _p, ...rest }: { children: React.ReactNode; href: string; prefetch?: boolean }) =>
    <a href={href} {...rest}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en', setLocale: jest.fn() }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'தமிழ்' } }))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => <span>logo</span> }))
jest.mock('@/components/ThemeSelector', () => ({ __esModule: true, default: () => <select aria-label="theme" /> }))
jest.mock('@/lib/sponsor-supabase', () => ({ sponsorSignOut: jest.fn() }))

const signOut = sponsorSignOut as jest.Mock

beforeEach(() => { jest.clearAllMocks(); path = '/sponsor/students'; signOut.mockResolvedValue({ error: null }) })

const tabBar = (c: HTMLElement) => c.querySelector('[data-tab-bar="sponsor"]') as HTMLElement | null

it('draws three tabs on a phone, the current one marked, and the same three in the desktop row', () => {
  const { container } = render(<SponsorShell nav><p>page</p></SponsorShell>)
  const bar = tabBar(container)!
  expect(bar).not.toBeNull()
  const links = within(bar).getAllByRole('link')
  expect(links.map((a) => a.getAttribute('href'))).toEqual(['/sponsor', '/sponsor/students', '/sponsor/account'])
  expect(links.map((a) => a.getAttribute('aria-current'))).toEqual([null, 'page', null])
  // The desktop row (hidden md:flex) carries the same three, current alike.
  const desktop = container.querySelector('header nav') as HTMLElement
  expect(within(desktop).getAllByRole('link').map((a) => a.getAttribute('aria-current'))).toEqual([null, 'page', null])
  // Never the student bar.
  expect(container.querySelector('[data-tab-bar]:not([data-tab-bar="sponsor"])')).toBeNull()
})

it('makes My Giving current on a supported student\'s page (where she came from)', () => {
  path = '/sponsor/my-students/801'
  const { container } = render(<SponsorShell nav><p>page</p></SponsorShell>)
  expect(within(tabBar(container)!).getAllByRole('link')[0].getAttribute('aria-current')).toBe('page')
})

it('draws no tabs on the screens without them, and keeps a phone Log out there', () => {
  const { container } = render(<SponsorShell><p>terms</p></SponsorShell>)
  expect(tabBar(container)).toBeNull()
  // One Log out for the phone (md:hidden) and one in the desktop row.
  const outs = screen.getAllByTestId('sponsor-logout')
  expect(outs).toHaveLength(2)
  expect(outs[0].className).toMatch(/\bmd:hidden\b/)
  expect(outs[0].className).toMatch(/\bmin-h-11\b/)
})

it('with tabs, the phone header has no Log out (it lives in My Account); the desktop row keeps one', () => {
  render(<SponsorShell nav><p>page</p></SponsorShell>)
  const outs = screen.getAllByTestId('sponsor-logout')
  expect(outs).toHaveLength(1)
  expect(outs[0].className).not.toMatch(/md:hidden/)
})

it('Log out ends the sponsor session only, then goes to the sponsor sign-in', async () => {
  render(<SponsorShell><p>terms</p></SponsorShell>)
  fireEvent.click(screen.getAllByTestId('sponsor-logout')[0])
  await waitFor(() => expect(replace).toHaveBeenCalledWith('/sponsor/login'))
  expect(signOut).toHaveBeenCalledTimes(1)
  expect(signOut).toHaveBeenCalledWith()
})
