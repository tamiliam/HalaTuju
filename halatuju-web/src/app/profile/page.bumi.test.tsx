/**
 * @jest-environment jsdom
 *
 * Bumi coverage Sprint B (owner ruling 2026-10-28): /profile lets the student see and change the
 * Bumiputera answer — course guide only, asked only of a Malaysian. A Foreign student is never
 * Bumiputera: switching to Foreign hides the question and saves null (the server agrees).
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProfilePage from './page'
import { getProfile, updateProfile } from '@/lib/api'
import { KEY_PROFILE } from '@/lib/storage'

// Stable objects: the page keys effects on these, so a fresh one per render would re-run them.
const mockRouter = { push: jest.fn(), replace: jest.fn() }
const mockAuth = {
  session: null, token: 'tkn', isAuthenticated: true, isLoading: false,
  showAuthGate: jest.fn(), refreshProfile: jest.fn(() => Promise.resolve()),
}
const mockT = { t: (k: string) => k, locale: 'en' }
const mockToast = { showToast: jest.fn() }
const mockGuard = { ready: true, loading: false, needsNric: false }
const mockPostcode = { edited: jest.fn() }

jest.mock('next/navigation', () => ({ useRouter: () => mockRouter }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => mockT }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => mockAuth }))
jest.mock('@/lib/useOnboardingGuard', () => ({ useOnboardingGuard: () => mockGuard }))
jest.mock('@/components/ToastContext', () => ({ useToast: () => mockToast }))
jest.mock('@/lib/usePostcodeAutofill', () => ({ usePostcodeAutofill: () => mockPostcode }))
jest.mock('@/lib/api', () => ({
  getProfile: jest.fn(),
  getSavedCourses: jest.fn(() => Promise.resolve({ saved_courses: [] })),
  updateProfile: jest.fn(() => Promise.resolve({ message: 'ok' })),
  claimNric: jest.fn(), unsaveCourse: jest.fn(), updateSavedCourseStatus: jest.fn(),
  sendVerificationEmail: jest.fn(), sendPhoneVerification: jest.fn(), checkPhoneVerification: jest.fn(),
}))
jest.mock('@/components/AppHeader', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/SchoolSelect', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/FamilyRosterFields', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/Toggle', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/profile/LazyGuardianContactSection', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/scholarship/LazyPathwayPicker', () => ({ __esModule: true, default: () => null }))

const profileMock = getProfile as jest.Mock
const updateMock = updateProfile as jest.Mock

async function mount(profile: Record<string, unknown>) {
  profileMock.mockResolvedValue({ name: 'TEST STUDENT', gender: 'female', ...profile })
  render(<ProfilePage />)
  await waitFor(() => expect(screen.getAllByText('onboarding.nationality').length).toBeGreaterThan(0))
}

const openIdentity = () => fireEvent.click(screen.getAllByText('profile.edit')[0])
const save = async () => {
  await act(async () => { fireEvent.click(screen.getByText('profile.save')) })
  await waitFor(() => expect(updateMock).toHaveBeenCalled())
}

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
})

it('shows a Malaysian student her stored answer', async () => {
  await mount({ nationality: 'malaysian', bumiputera: true })
  expect(screen.getByText('onboarding.bumiputera')).toBeTruthy()
  expect(screen.getByText('onboarding.bumiYes')).toBeTruthy()
})

it('shows nothing about it to a Foreign student', async () => {
  await mount({ nationality: 'non_malaysian', bumiputera: null })
  expect(screen.queryByText('onboarding.bumiputera')).toBeNull()
})

it('a changed answer is saved to the server and to this browser', async () => {
  await mount({ nationality: 'malaysian', bumiputera: false })
  openIdentity()
  expect(screen.getByTestId('profile-bumiputera')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'onboarding.bumiYes' }))
  await save()
  expect(updateMock.mock.calls[0][0].bumiputera).toBe(true)
  expect(JSON.parse(localStorage.getItem(KEY_PROFILE) as string).bumiputera).toBe(true)
})

it('switching to Foreign hides the question and saves null, never the old yes', async () => {
  await mount({ nationality: 'malaysian', bumiputera: true })
  openIdentity()
  fireEvent.click(screen.getByRole('button', { name: 'onboarding.nonMalaysian' }))
  expect(screen.queryByTestId('profile-bumiputera')).toBeNull()
  await save()
  expect(updateMock.mock.calls[0][0]).toHaveProperty('bumiputera', null)
  expect(JSON.parse(localStorage.getItem(KEY_PROFILE) as string).bumiputera).toBeNull()
})

it('a stale yes in this browser is overwritten with null on a switch to Foreign, never spread back', async () => {
  localStorage.setItem(KEY_PROFILE, JSON.stringify({ nationality: 'malaysian', bumiputera: true }))
  await mount({ nationality: 'malaysian', bumiputera: true })
  openIdentity()
  fireEvent.click(screen.getByRole('button', { name: 'onboarding.nonMalaysian' }))
  await save()
  expect(JSON.parse(localStorage.getItem(KEY_PROFILE) as string)).toMatchObject({
    nationality: 'non_malaysian', bumiputera: null })
})

it('Malaysian -> Foreign -> Malaysian leaves the answer unset, not the old yes', async () => {
  await mount({ nationality: 'malaysian', bumiputera: true })
  openIdentity()
  fireEvent.click(screen.getByRole('button', { name: 'onboarding.nonMalaysian' }))
  fireEvent.click(screen.getByRole('button', { name: 'onboarding.malaysian' }))
  const field = screen.getByTestId('profile-bumiputera')
  expect(field.querySelectorAll('.bg-primary-50').length).toBe(0)     // neither Yes nor No chosen
  await save()
  expect(updateMock.mock.calls[0][0]).toHaveProperty('bumiputera', null)
  expect(JSON.parse(localStorage.getItem(KEY_PROFILE) as string).bumiputera).toBeNull()
})

it("the stored value 'Warganegara' reads as Malaysian, so the question shows", async () => {
  await mount({ nationality: 'Warganegara', bumiputera: false })
  expect(screen.getByText('onboarding.malaysian')).toBeTruthy()
  expect(screen.getByText('onboarding.bumiputera')).toBeTruthy()
  expect(screen.getByText('onboarding.bumiNo')).toBeTruthy()
})

it('Cancel puts the stored answer back', async () => {
  await mount({ nationality: 'malaysian', bumiputera: false })
  openIdentity()
  fireEvent.click(screen.getByRole('button', { name: 'onboarding.bumiYes' }))
  fireEvent.click(screen.getByText('profile.cancel'))
  expect(screen.getByText('onboarding.bumiNo')).toBeTruthy()
  expect(screen.queryByText('onboarding.bumiYes')).toBeNull()
})
