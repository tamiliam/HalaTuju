/**
 * @jest-environment jsdom
 *
 * TD-472 (owner D10, option B, 2026-11-11): the console's language control is on the Profile page —
 * the same `LanguageSegments` the student and sponsor menus show, outside the form (a choice applies
 * at once and is not part of Save), for every role.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import ProfilePage from './page'
import { ME } from '@/components/source/testFixtures'

const mockSetLocale = jest.fn(() => Promise.resolve())
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en', setLocale: mockSetLocale }),
  LOCALE_LABELS: { en: 'English', ms: 'Bahasa Melayu', ta: 'தமிழ்' },
}))
let mockAuth: Record<string, unknown> = {}
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => mockAuth }))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/admin-supabase', () => ({ getAdminSupabase: () => ({ auth: {} }), adminSignInWithPassword: jest.fn() }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const STAFF_ME: api.AdminMe = { ...ME, name: 'Priya', role: 'admin', source: null, permissions: ['see_all'],
  phone: '12-345 6789', completion: null }

function signIn(role: string) {
  mockAuth = {
    token: 'tok', refreshRole: jest.fn(() => Promise.resolve()), setPhotoUrl: jest.fn(), setProfileCompletion: jest.fn(),
    session: { user: { app_metadata: { providers: ['email'] } } },
    role: { role, is_admin: true, is_super_admin: role === 'super', permissions: [], reviewer_profile_complete: true },
  }
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getAdminMe.mockResolvedValue(STAFF_ME)
  mockApi.getMyActivity.mockResolvedValue({ results: [], next: null })
})

it('the Profile page shows the three languages, the current one chosen, outside the form', async () => {
  signIn('admin')
  render(<ProfilePage />)
  const section = await screen.findByTestId('profile-language')
  const group = within(section).getByRole('radiogroup', { name: 'settings.language' })
  const radios = within(group).getAllByRole('radio')
  expect(radios.map((r) => r.textContent)).toEqual(['English', 'Bahasa Melayu', 'தமிழ்'])
  expect(radios.map((r) => r.getAttribute('aria-checked'))).toEqual(['true', 'false', 'false'])
  expect(screen.getByTestId('admin-profile').contains(section)).toBe(false)
})

it('choosing a language changes the locale and saves nothing', async () => {
  signIn('admin')
  render(<ProfilePage />)
  const section = await screen.findByTestId('profile-language')
  fireEvent.click(within(section).getByRole('radio', { name: 'Bahasa Melayu' }))
  expect(mockSetLocale).toHaveBeenCalledWith('ms')
  expect(mockApi.updateAdminMe).not.toHaveBeenCalled()
})
