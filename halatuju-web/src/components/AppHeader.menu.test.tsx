/**
 * @jest-environment jsdom
 *
 * Mobile M2: the ONE student header's menus.
 *
 * What these pin, each the defect it prevents:
 *   - the phone menu lists every destination ONCE (Profile and Saved used to appear twice, and
 *     "Saved" and "My Applications" were two names for the same /saved);
 *   - signed out it offers Sign up FIRST and the three logins; signed in it offers neither, and
 *     ends with Log out;
 *   - "My Bursary" only for a signed-in student the pages have seen with a file;
 *   - Log out wipes the student's `halatuju_` keys (and only hers) and ends the session;
 *   - the menu opens with focus on its first item (never a field, never the ×);
 *   - the desktop BrightPath menu opens on a CLICK — nothing of it exists until then, so no hover
 *     is needed to reach it (the iPad sticky-hover dependency, decisions.md Mobile M2).
 */
import type { ReactNode } from 'react'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AppHeader from './AppHeader'
import { KEY_HAS_BURSARY_FILE } from '@/lib/storage'

const mockSetLocale = jest.fn((_l: string) => Promise.resolve())
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en', setLocale: mockSetLocale }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'தமிழ்' },
}))
const mockShowAuthGate = jest.fn()
let mockAuth: { session: unknown; isAuthenticated: boolean; isAnonymous?: boolean; hasSession?: boolean } = { session: null, isAuthenticated: false }
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ ...mockAuth, isAnonymous: false, showAuthGate: mockShowAuthGate }),
}))
jest.mock('@/lib/useProfileCompleteness', () => ({ useProfileCompleteness: () => ({ incompleteCount: 2 }) }))
const mockSignOut = jest.fn(() => Promise.resolve({ error: null }))
jest.mock('@/lib/supabase', () => ({ signOut: () => mockSignOut(), getSupabase: () => ({ auth: { stopAutoRefresh: jest.fn() } }) }))
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: jest.fn() }) }))
jest.mock('@/components/BrandLogo', () => () => null)
// The desktop Log in ▾ / Sign Up pair (its own guard is navLayout.test.ts); out of the way so the
// phone bar's single Log in is the only one.
jest.mock('./AuthButtons', () => () => null)
const mockPush = jest.fn()
let mockPath = '/search'
jest.mock('next/navigation', () => ({ usePathname: () => mockPath, useRouter: () => ({ push: mockPush, replace: jest.fn() }) }))
// A plain anchor that forwards its ref, as next/link does (the menu focuses its first link).
jest.mock('next/link', () => {
  const { forwardRef } = jest.requireActual('react')
  const MockLink = forwardRef(({ href, children, ...rest }: { href: string; children: ReactNode }, ref: never) => (
    <a ref={ref} href={href} {...rest}>{children}</a>
  ))
  return { __esModule: true, default: MockLink }
})

const SIGNED_IN = {
  isAuthenticated: true,
  session: { user: { email: 'aish@example.com', user_metadata: { full_name: 'Aishwarya Kumar' } } },
}

beforeEach(() => {
  localStorage.clear()
  mockAuth = { session: null, isAuthenticated: false }
  mockPath = '/search'
  mockShowAuthGate.mockClear(); mockSignOut.mockClear(); mockPush.mockClear(); mockSetLocale.mockClear()
})

async function openPhoneMenu() {
  fireEvent.click(screen.getByRole('button', { name: 'common.menu' }))
  return within(await screen.findByRole('dialog'))
}

const hrefs = (menu: ReturnType<typeof within>) =>
  menu.queryAllByRole('link').map((a: HTMLElement) => a.getAttribute('href'))

it('signed out: Sign up first (and focused), the three logins, no destination twice, no Log out', async () => {
  render(<AppHeader />)
  const menu = await openPhoneMenu()
  const signUp = menu.getByRole('button', { name: 'header.signUp' })
  await waitFor(() => expect(document.activeElement).toBe(signUp))
  // Sign up is the first control in the list.
  expect(menu.getAllByRole('button').find((b) => b.closest('nav'))).toBe(signUp)
  expect(menu.getByRole('button', { name: 'header.login.student' })).toBeTruthy()
  const links = hrefs(menu)
  expect(links).toEqual(expect.arrayContaining(['/dashboard', '/search', '/scholarship', '/sponsor', '/sponsor/login', '/admin/login']))
  expect(new Set(links).size).toBe(links.length)
  expect(menu.queryByText('header.logout')).toBeNull()
  // Saved needs an account: a button to the gate, not a link.
  expect(links).not.toContain('/saved')
  expect(menu.getByRole('button', { name: 'common.saved' })).toBeTruthy()
})

it('signed in: each destination once, profile and settings, Log out last; no Sign up or logins', async () => {
  mockAuth = SIGNED_IN
  render(<AppHeader />)
  const menu = await openPhoneMenu()
  await waitFor(() => expect(document.activeElement?.getAttribute('href')).toBe('/dashboard'))
  const links = hrefs(menu)
  expect(links).toEqual(['/dashboard', '/search', '/saved', '/scholarship', '/sponsor', '/profile', '/settings'])
  expect(menu.queryByText('header.signUp')).toBeNull()
  expect(menu.queryByText('header.login.student')).toBeNull()
  expect(menu.getByText('Aishwarya Kumar')).toBeTruthy()
  expect(menu.getByRole('button', { name: 'header.logout' })).toBeTruthy()
  // The current page is marked.
  expect(menu.getByRole('link', { name: 'search.nav' }).getAttribute('aria-current')).toBe('page')
})

it('TD-454: a Google student still on her NRIC step sees her name and Log out, not the signed-out header, and no account links', async () => {
  mockAuth = { ...SIGNED_IN, isAuthenticated: false, isAnonymous: false, hasSession: true }
  render(<AppHeader />)
  const menu = await openPhoneMenu()
  expect(menu.getByText('Aishwarya Kumar')).toBeTruthy()
  expect(menu.getByRole('button', { name: 'header.logout' })).toBeTruthy()
  expect(menu.queryByText('header.signUp')).toBeNull()
  expect(menu.queryByText('header.login.student')).toBeNull()
  expect(hrefs(menu)).not.toContain('/profile')
  expect(hrefs(menu)).not.toContain('/settings')
})

it('TD-454: an unverified student gets a Finish signing in row (phone menu) that reopens the sign-in step', async () => {
  mockAuth = { ...SIGNED_IN, isAuthenticated: false, isAnonymous: false, hasSession: true }
  render(<AppHeader />)
  const menu = await openPhoneMenu()
  fireEvent.click(menu.getByRole('button', { name: 'scholarship.finishSignIn' }))
  expect(mockShowAuthGate).toHaveBeenCalledWith('profile')
})

it('TD-454: the desktop account panel offers Finish signing in for an unverified student only', async () => {
  mockAuth = { ...SIGNED_IN, isAuthenticated: false, isAnonymous: false, hasSession: true }
  const { unmount } = render(<AppHeader />)
  fireEvent.click(await screen.findByRole('button', { name: 'header.myProfile', expanded: false }))
  fireEvent.click(screen.getByRole('button', { name: 'scholarship.finishSignIn' }))
  expect(mockShowAuthGate).toHaveBeenCalledWith('profile')
  unmount()

  mockShowAuthGate.mockClear()
  mockAuth = SIGNED_IN
  render(<AppHeader />)
  fireEvent.click(await screen.findByRole('button', { name: 'header.myProfile', expanded: false }))
  expect(screen.queryByRole('button', { name: 'scholarship.finishSignIn' })).toBeNull()
})

it('My Bursary only for a signed-in student with a file', async () => {
  localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
  const { unmount } = render(<AppHeader />)
  expect(hrefs(await openPhoneMenu())).not.toContain('/scholarship/bursary')
  unmount()

  mockAuth = SIGNED_IN
  render(<AppHeader />)
  expect(hrefs(await openPhoneMenu())).toContain('/scholarship/bursary')
})

it('Log out wipes her halatuju_ keys (not the admin or sponsor session) and ends the session', async () => {
  mockAuth = SIGNED_IN
  localStorage.setItem('halatuju_grades', '{"BM":"A"}')
  localStorage.setItem('halatuju_has_bursary_file', '1')
  localStorage.setItem('halatuju_admin_session', 'keep')
  localStorage.setItem('halatuju_sponsor_session', 'keep')
  localStorage.setItem('other_app', 'keep')
  const err = jest.spyOn(console, 'error').mockImplementation(() => {}) // jsdom: "navigation not implemented"
  render(<AppHeader />)
  const menu = await openPhoneMenu()
  await act(async () => { fireEvent.click(menu.getByRole('button', { name: 'header.logout' })) })
  expect(localStorage.getItem('halatuju_grades')).toBeNull()
  expect(localStorage.getItem('halatuju_has_bursary_file')).toBeNull()
  expect(localStorage.getItem('halatuju_admin_session')).toBe('keep')
  expect(localStorage.getItem('halatuju_sponsor_session')).toBe('keep')
  expect(localStorage.getItem('other_app')).toBe('keep')
  expect(mockSignOut).toHaveBeenCalledTimes(1)
  err.mockRestore()
})

it('the phone bar: Log in opens the student sign-in gate; signed in, the avatar goes to the profile', () => {
  const { unmount } = render(<AppHeader />)
  fireEvent.click(screen.getByRole('button', { name: 'header.login.label' }))
  expect(mockShowAuthGate).toHaveBeenCalledWith('profile')
  unmount()
  mockAuth = SIGNED_IN
  render(<AppHeader />)
  expect(screen.queryByRole('button', { name: 'header.login.label' })).toBeNull()
  expect(screen.getAllByRole('link', { name: 'header.myProfile' })[0].getAttribute('href')).toBe('/profile')
})

it("on the sponsor side, the phone bar's Log in is the sponsor login, not the student gate", () => {
  mockPath = '/sponsor'
  render(<AppHeader />)
  const login = screen.getByRole('link', { name: 'header.login.label' })
  expect(login.getAttribute('href')).toBe('/sponsor/login')
  fireEvent.click(login)
  expect(mockShowAuthGate).not.toHaveBeenCalled()
})

it('desktop BrightPath opens on a click and closes on a second click or Escape — no hover needed', async () => {
  render(<AppHeader />)
  const button = await screen.findByRole('button', { name: 'scholarship.nav' })
  expect(screen.queryByRole('link', { name: 'scholarship.subnav.apply' })).toBeNull()
  fireEvent.click(button)
  expect(button.getAttribute('aria-expanded')).toBe('true')
  expect(screen.getByRole('link', { name: 'scholarship.subnav.apply' })).toBeTruthy()
  fireEvent.click(button)
  expect(screen.queryByRole('link', { name: 'scholarship.subnav.apply' })).toBeNull()
  fireEvent.click(button)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('link', { name: 'scholarship.subnav.apply' })).toBeNull()
})

it('theme and language are in the menu, as 44 px choices; picking a language asks for it', async () => {
  render(<AppHeader />)
  const menu = await openPhoneMenu()
  const theme = menu.getByRole('radiogroup', { name: 'theme.label' })
  expect(within(theme).getAllByRole('radio')).toHaveLength(3)
  const language = menu.getByRole('radiogroup', { name: 'settings.language' })
  const tamil = within(language).getByRole('radio', { name: 'தமிழ்' })
  expect(tamil.className).toMatch(/(^|\s)min-h-11(\s|$)/)
  await act(async () => { fireEvent.click(tamil) })
  expect(mockSetLocale).toHaveBeenCalledWith('ta')
  // The language already on screen is not asked for again.
  fireEvent.click(within(language).getByRole('radio', { name: 'English' }))
  expect(mockSetLocale).toHaveBeenCalledTimes(1)
})
