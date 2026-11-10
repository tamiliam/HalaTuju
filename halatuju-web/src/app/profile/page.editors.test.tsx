/**
 * @jest-environment jsdom
 *
 * A3.9 review fixes: the lazy edit chunk. Pins (1) a section whose Edit was tapped before the chunk
 * landed keeps its Edit button, shows a loading line, then the form once the panel arrives; (2) a
 * failed chunk fetch toasts ONCE per tap, closes the section, and the next tap retries the import.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProfilePage from './page'
import IdentitySection from './sections/IdentitySection'
import { getProfile } from '@/lib/api'

const mockRouter = { push: jest.fn(), replace: jest.fn() }
const mockAuth = {
  session: { user: { email: 'stu@example.com' } }, token: 'tkn', isAuthenticated: true, isLoading: false,
  showAuthGate: jest.fn(), refreshProfile: jest.fn(() => Promise.resolve()),
}
const mockT = { t: (k: string) => k, locale: 'en' }
const mockToast = { showToast: jest.fn() }
const mockGuard = { ready: true, loading: false, needsNric: false }
const mockPostcode = { edited: jest.fn(), lookup: jest.fn() }
const mockChunk = { mode: 'fail' as 'fail' | 'ok', attempts: 0 }

jest.mock('next/navigation', () => ({ useRouter: () => mockRouter }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
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
  sendVerificationEmail: jest.fn(() => Promise.resolve({})),
  sendPhoneVerification: jest.fn(), checkPhoneVerification: jest.fn(),
}))
jest.mock('@/components/AppHeader', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/SchoolSelect', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/FamilyRosterFields', () => ({ __esModule: true, default: () => <div data-testid="roster" /> }))
jest.mock('@/components/Toggle', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/profile/LazyGuardianContactSection', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/profile/LazyCourseInterestsSection', () => ({
  __esModule: true, default: () => <div data-testid="interests" />,
}))
jest.mock('@/components/scholarship/LazyPathwayPicker', () => ({
  __esModule: true, default: () => <div data-testid="pathway-picker" />,
}))
// The edit chunk: a failing import until the test flips it to 'ok'.
jest.mock('./sections/edit', () => {
  mockChunk.attempts += 1
  if (mockChunk.mode === 'fail') throw new Error('chunk load failed')
  return jest.requireActual('./sections/edit')
})

const BASE = {
  name: 'TEST STUDENT', gender: 'female', nationality: 'malaysian', nric: '050202-02-2022',
  preferred_state: 'Kedah', address: '12 Jalan A', postal_code: '08000', city: 'Sungai Petani',
  household_income: 2500, household_size: 5, angka_giliran: 'AB123C456',
  contact_email: 'c@example.com', contact_email_verified: true, contact_phone: '012-345 6789',
  merit_score: 88.5, school: 'SMK Test', nric_locked: true,
}

describe('an Edit tapped before the edit chunk has landed', () => {
  const ed = (editingSection: string | null) => ({ editingSection, startEditing: jest.fn() }) as never
  const f = { name: 'A', nric: '', gender: '', bumiputera: null, colorblind: null, disability: null,
    identityVerified: false, icFlagCodes: [], malaysian: true, icEditable: true, identityIncomplete: 0 } as never

  it('keeps the Edit button and shows a loading line, then the form when the panel arrives', () => {
    const Panel = () => <div data-testid="panel" />
    const { rerender } = render(<IdentitySection f={f} ed={ed('identity')} />)
    expect(screen.getByText('profile.edit')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toBe('common.loading')
    expect(screen.queryByTestId('panel')).toBeNull()
    rerender(<IdentitySection f={f} ed={ed('identity')} Edit={Panel} />)
    expect(screen.getByTestId('panel')).toBeTruthy()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('hides the Edit button of the OTHER sections while one is open (as before)', () => {
    render(<IdentitySection f={f} ed={ed('family')} />)
    expect(screen.queryByText('profile.edit')).toBeNull()
  })
})

describe('the edit chunk fails to load', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    window.history.replaceState({}, '', '/profile')
  })

  it('toasts once per tap, closes the section, and the next tap retries the import', async () => {
    ;(getProfile as jest.Mock).mockResolvedValue({ ...BASE })
    render(<ProfilePage />)
    await waitFor(() => expect(screen.getAllByText('profile.edit').length).toBe(5))
    await waitFor(() => expect(mockChunk.attempts).toBeGreaterThanOrEqual(1))
    const before = mockChunk.attempts

    fireEvent.click(screen.getAllByText('profile.edit')[0])
    await waitFor(() => expect(mockToast.showToast).toHaveBeenCalledTimes(1))
    expect(mockToast.showToast).toHaveBeenCalledWith('errors.unexpectedError', 'error')
    await waitFor(() => expect(screen.getAllByText('profile.edit')).toHaveLength(5))   // section cancelled
    expect(screen.queryByText('profile.save')).toBeNull()
    expect(mockChunk.attempts).toBe(before + 1)   // the tap retried the import once

    fireEvent.click(screen.getAllByText('profile.edit')[1])
    await waitFor(() => expect(mockToast.showToast).toHaveBeenCalledTimes(2))   // once per tap, no loop
    expect(mockChunk.attempts).toBe(before + 2)

    mockChunk.mode = 'ok'   // the network is back: the next tap retries and the form opens
    fireEvent.click(screen.getAllByText('profile.edit')[0])
    await waitFor(() => expect(screen.getByText('profile.save')).toBeTruthy())
    expect(mockToast.showToast).toHaveBeenCalledTimes(2)
  })
})
