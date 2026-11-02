/**
 * @jest-environment jsdom
 *
 * Mobile M4b: the student tab bar — four tabs, the current one marked, BrightPath to My Bursary only
 * for a student with a file, and Saved signed out going to the sign-in sheet (or onboarding with no
 * results yet), exactly as the header menu's Saved does. When it SHOWS is CSS (globals.css), pinned
 * in mobileStandard.test.ts; jsdom does not apply it, so these read the markup.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import StudentTabBar from './StudentTabBar'
import { KEY_GRADES, KEY_HAS_BURSARY_FILE, rememberBursaryFile } from '@/lib/storage'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
let mockAuthed = true
const mockGate = jest.fn()
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ isAuthenticated: mockAuthed, showAuthGate: mockGate }),
}))
let mockPath = '/dashboard'
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({ usePathname: () => mockPath, useRouter: () => ({ push: mockPush }) }))

beforeEach(() => { localStorage.clear(); mockAuthed = true; mockPath = '/dashboard'; jest.clearAllMocks() })

const tab = (name: string) => screen.getByRole('link', { name })

it('draws four tabs with existing words and the organisation\'s own short name', () => {
  render(<StudentTabBar />)
  const links = screen.getAllByRole('link')
  expect(links.map((l) => l.textContent)).toEqual(['common.dashboard', 'search.nav', 'common.saved', 'BrightPath'])
  expect(links.map((l) => l.getAttribute('href'))).toEqual(['/dashboard', '/search', '/saved', '/scholarship'])
  expect(screen.getByRole('navigation', { name: 'common.menu' }).hasAttribute('data-tab-bar')).toBe(true)
})

it('marks the page she is on, and BrightPath on every scholarship page', () => {
  mockPath = '/search'
  const { unmount } = render(<StudentTabBar />)
  expect(tab('search.nav').getAttribute('aria-current')).toBe('page')
  expect(tab('common.dashboard').getAttribute('aria-current')).toBeNull()
  unmount()
  mockPath = '/scholarship/application'
  render(<StudentTabBar />)
  expect(tab('BrightPath').getAttribute('aria-current')).toBe('page')
  expect(screen.getAllByRole('link').filter((l) => l.getAttribute('aria-current')).length).toBe(1)
})

it('no tab is current on Home (the logo is the way home)', () => {
  mockPath = '/'
  render(<StudentTabBar />)
  expect(screen.getAllByRole('link').some((l) => l.getAttribute('aria-current'))).toBe(false)
})

it('BrightPath opens My Bursary for a signed-in student with a file — and at once when a page writes the hint', () => {
  render(<StudentTabBar />)
  expect(tab('BrightPath').getAttribute('href')).toBe('/scholarship')
  act(() => { rememberBursaryFile(true) })
  expect(tab('BrightPath').getAttribute('href')).toBe('/scholarship/bursary')
})

it('the hint alone is not enough signed out', () => {
  localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
  mockAuthed = false
  render(<StudentTabBar />)
  expect(tab('BrightPath').getAttribute('href')).toBe('/scholarship')
})

it('signed out, Saved opens the sign-in sheet — or onboarding when there are no results yet', () => {
  mockAuthed = false
  const { unmount } = render(<StudentTabBar />)
  fireEvent.click(tab('common.saved'))
  expect(mockPush).toHaveBeenCalledWith('/onboarding/exam-type')
  expect(mockGate).not.toHaveBeenCalled()
  unmount()
  localStorage.setItem(KEY_GRADES, JSON.stringify({ bm: 'A' }))
  render(<StudentTabBar />)
  fireEvent.click(tab('common.saved'))
  expect(mockGate).toHaveBeenCalledWith('save')
})

it('signed in, Saved is a plain link', () => {
  render(<StudentTabBar />)
  fireEvent.click(tab('common.saved'))
  expect(mockGate).not.toHaveBeenCalled()
  expect(mockPush).not.toHaveBeenCalled()
})
