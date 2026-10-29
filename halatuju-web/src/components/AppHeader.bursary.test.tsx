/**
 * @jest-environment jsdom
 *
 * Student maintenance S3: the BrightPath menu offers "My Bursary" ONLY to a signed-in student the
 * pages have seen with a file (`rememberBursaryFile`, from the server's `has_file`). A display
 * hint, never a gate — the hub's own endpoint 404s a student with no file.
 */
import { act, render, screen } from '@testing-library/react'
import AppHeader from './AppHeader'
import { KEY_HAS_BURSARY_FILE, rememberBursaryFile } from '@/lib/storage'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en', setLocale: jest.fn() }) }))
let mockAuthed = true
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ session: null, isAuthenticated: mockAuthed, isAnonymous: false, showAuthGate: jest.fn() }),
}))
jest.mock('@/lib/useProfileCompleteness', () => ({ useProfileCompleteness: () => ({ incompleteCount: 0 }) }))
jest.mock('@/lib/supabase', () => ({ signOut: jest.fn() }))
jest.mock('./LanguageSelector', () => () => null)
jest.mock('./ThemeSelector', () => () => null)
jest.mock('./AuthButtons', () => () => null)
jest.mock('@/components/BrandLogo', () => () => null)
jest.mock('next/navigation', () => ({
  usePathname: () => '/dashboard', useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))

beforeEach(() => { localStorage.clear(); mockAuthed = true })

it('offers My Bursary to a student with a file', async () => {
  localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
  render(<AppHeader />)
  expect((await screen.findAllByText('scholarship.subnav.bursary')).length).toBeGreaterThan(0)
})

it('does not offer it without the hint, or when signed out', () => {
  render(<AppHeader />)
  expect(screen.queryByText('scholarship.subnav.bursary')).toBeNull()
  localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
  mockAuthed = false
  render(<AppHeader />)
  expect(screen.queryByText('scholarship.subnav.bursary')).toBeNull()
})

it('appears the moment a page writes the hint (no navigation needed)', async () => {
  render(<AppHeader />)
  expect(screen.queryByText('scholarship.subnav.bursary')).toBeNull()
  act(() => rememberBursaryFile(true))
  expect((await screen.findAllByText('scholarship.subnav.bursary')).length).toBeGreaterThan(0)
  act(() => rememberBursaryFile(false))
  expect(screen.queryByText('scholarship.subnav.bursary')).toBeNull()
})
