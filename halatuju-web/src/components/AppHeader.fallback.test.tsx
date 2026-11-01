/**
 * @jest-environment jsdom
 *
 * Mobile M2 review: the menus' chunk can fail to load (a tab open across a deploy asks for a chunk
 * that no longer exists). The header must keep a way in and a way out without it, close the menu it
 * could not open, and try again on the next tap.
 */
import type { ReactNode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AppHeader from './AppHeader'

let mockAttempts = 0
jest.mock('./StudentMenus', () => {
  mockAttempts += 1
  throw new Error('ChunkLoadError: Loading chunk failed')
})
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
const mockShowAuthGate = jest.fn()
let mockAuth: { session: unknown; isAuthenticated: boolean } = { session: null, isAuthenticated: false }
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ ...mockAuth, showAuthGate: mockShowAuthGate }) }))
jest.mock('@/lib/useProfileCompleteness', () => ({ useProfileCompleteness: () => ({ incompleteCount: 0 }) }))
const mockSignOutStudent = jest.fn(() => Promise.resolve())
jest.mock('@/lib/studentSignOut', () => ({ signOutStudent: () => mockSignOutStudent() }))
jest.mock('@/components/BrandLogo', () => () => null)
let mockPath = '/search'
jest.mock('next/navigation', () => ({ usePathname: () => mockPath, useRouter: () => ({ push: jest.fn() }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => <a href={href} {...rest}>{children}</a>,
}))

beforeEach(() => {
  mockAttempts = 0
  mockAuth = { session: null, isAuthenticated: false }
  mockPath = '/search'
  mockShowAuthGate.mockClear()
  mockSignOutStudent.mockClear()
})

it('signed out: a failed chunk leaves a Log in on the desktop row too (the student gate)', async () => {
  render(<AppHeader />)
  // The phone bar's Log in, plus the desktop fallback once the chunk has failed.
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'header.login.label' })).toHaveLength(2))
  fireEvent.click(screen.getAllByRole('button', { name: 'header.login.label' })[1])
  expect(mockShowAuthGate).toHaveBeenCalledWith('profile')
  expect(screen.queryByText('header.logout')).toBeNull()
})

it('signed in: a failed chunk still offers Log out, through the safe sign-out', async () => {
  mockAuth = { isAuthenticated: true, session: { user: { email: 'a@b.invalid', user_metadata: { full_name: 'A B' } } } }
  render(<AppHeader />)
  // Desktop row fallback and the phone bar's, beside the menu button.
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'header.logout' })).toHaveLength(2))
  fireEvent.click(screen.getAllByRole('button', { name: 'header.logout' })[0])
  expect(mockSignOutStudent).toHaveBeenCalledTimes(1)
})

it('the menu button does not claim to be open when nothing could open, and a second tap tries again', async () => {
  render(<AppHeader />)
  await waitFor(() => expect(mockAttempts).toBe(1))  // the wide-screen load at mount (no matchMedia here)
  const menu = screen.getByRole('button', { name: 'common.menu' })
  fireEvent.click(menu)
  await waitFor(() => expect(mockAttempts).toBe(2))
  await waitFor(() => expect(menu.getAttribute('aria-expanded')).toBe('false'))
  fireEvent.click(menu)
  await waitFor(() => expect(mockAttempts).toBe(3))
  expect(screen.queryByRole('dialog')).toBeNull()
})
