/**
 * @jest-environment jsdom
 *
 * TD-057 — an ABANDONED edit-results detour no longer sends a later onboarding to the apply page.
 *
 * The apply form's "edit results" sends the student through onboarding with a return marker in
 * sessionStorage (`halatuju_apply_return`); the final onboarding step reads it and goes back to
 * `/scholarship/apply`. A student who abandoned that detour and later started an ORDINARY
 * onboarding in the same tab was still sent to the apply page at the end. The marker was cleared
 * only on a normal apply-page visit; now a dashboard visit clears it too (the entry's second
 * option — one effect in one page, rather than threading a query parameter through every
 * onboarding step and every link into them).
 *
 * The path, rendered end to end with the two real pages: detour starts → student goes to the
 * dashboard → an ordinary onboarding's last step → lands on `/dashboard`. And the control: the
 * same path WITHOUT the dashboard still returns to the apply form, so the detour itself still works.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import DashboardPage from './page'
import ProfileInputPage from '../onboarding/profile/page'
import { APPLY_RETURN_KEY, stashApplyForm, type ApplyFormState } from '@/lib/scholarship'
import { KEY_PROFILE } from '@/lib/storage'

const mockPush = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  usePathname: () => '/dashboard',
}))
jest.mock('next/link', () => ({ __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span> }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({
  isAuthenticated: false, token: null, isAnonymous: false, profile: null,
  showAuthGate: jest.fn(), refreshProfile: jest.fn(),
}) }))
// The dashboard's data hooks, held in their "still loading" state: this test is about what the
// page does on ARRIVAL, not about the recommendations it would go on to draw.
jest.mock('@/lib/useOnboardingGuard', () => ({
  useOnboardingGuard: () => ({ ready: false, loading: true, needsNric: false }) }))
jest.mock('@/hooks/useCachedResults', () => ({
  useCachedResults: () => ({ results: { view: 'none' }, ready: false }) }))
jest.mock('@/hooks/useSavedCourses', () => ({
  useSavedCourses: () => ({ savedIds: new Set(), toggleSave: jest.fn() }) }))
jest.mock('@/components/Toast', () => ({ useToast: () => ({ showToast: jest.fn() }) }))
jest.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: undefined, isLoading: false, error: null }) }))
jest.mock('@/lib/api', () => ({ __esModule: true,
  ...jest.requireActual('@/lib/api'), getProfile: jest.fn(), syncProfile: jest.fn() }))
for (const c of ['AppHeader', 'AppFooter', 'ScholarshipBanner', 'CourseCard', 'PathwayCards',
                 'BrandLogo', 'ProgressStepper', 'SchoolSelect']) {
  jest.mock(`@/components/${c}`, () => ({ __esModule: true, default: () => null }))
}

beforeEach(() => {
  jest.clearAllMocks()
  sessionStorage.clear()
  localStorage.clear()
  localStorage.setItem(KEY_PROFILE, JSON.stringify({ gender: 'male', state: 'Johor' }))
})

/** The apply form's "edit results": the stash and the return marker, exactly as it writes them. */
const startDetour = () => stashApplyForm({} as ApplyFormState)

/** An onboarding's last step, pressed: where does it send the student? */
async function finishOnboarding(): Promise<string> {
  const view = render(<ProfileInputPage />)
  const button = await screen.findByRole('button',
    { name: /^onboarding\.(seeRecommendations|saveReturnToApplication|saveAndReturn)$/ })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  await act(async () => { fireEvent.click(button) })
  await waitFor(() => expect(mockPush).toHaveBeenCalled())
  view.unmount()
  return mockPush.mock.calls[mockPush.mock.calls.length - 1][0]
}

it('abandon the detour → visit the dashboard → an ordinary onboarding ends on /dashboard', async () => {
  startDetour()
  expect(sessionStorage.getItem(APPLY_RETURN_KEY)).toBe('1')
  const dash = render(<DashboardPage />)
  await waitFor(() => expect(sessionStorage.getItem(APPLY_RETURN_KEY)).toBeNull())
  dash.unmount()
  mockPush.mockClear()
  expect(await finishOnboarding()).toBe('/dashboard')
})

it('the control: the detour itself, with no dashboard visit, still returns to the apply form', async () => {
  startDetour()
  expect(await finishOnboarding()).toBe('/scholarship/apply')
})
