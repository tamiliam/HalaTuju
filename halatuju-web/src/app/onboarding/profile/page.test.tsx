/**
 * @jest-environment jsdom
 *
 * "A Few More Details" — the School box, rendered (request #35, 2026-10-19: "we ask for school
 * twice").
 *
 * A student on the apply form presses add/correct results, walks exam-type → grades → this page,
 * and is asked School again — empty, though she had just answered it on "About Me". Two rules:
 *   (a) the school in the apply form's stash prefills the box when the profile holds none;
 *   (b) on the way back to the application, with a school already known (stash or profile), the
 *       box is hidden — and the known school is still saved, never blanked.
 * Outside that return trip the page is exactly as before.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProfileInputPage from './page'
import { getProfile, syncProfile } from '@/lib/api'
import { APPLY_RETURN_KEY, stashApplyForm, type ApplyFormState } from '@/lib/scholarship'
import { KEY_PROFILE } from '@/lib/storage'

const push = jest.fn()

jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ token: 'tkn', isAnonymous: false, refreshProfile: jest.fn(() => Promise.resolve()) }),
}))
jest.mock('@/lib/api', () => ({
  getProfile: jest.fn(),
  syncProfile: jest.fn(() => Promise.resolve({})),
}))
jest.mock('@/components/BrandLogo', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ProgressStepper', () => ({ __esModule: true, default: () => null }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const profileMock = getProfile as jest.Mock
const syncMock = syncProfile as jest.Mock

/** The apply form's detour: stash the form (which also sets the return flag). */
const detourFrom = (school: string) =>
  stashApplyForm({ school, homeState: 'Selangor' } as unknown as ApplyFormState)

const schoolBox = () => screen.queryByTestId('onboarding-school')
const schoolInput = () => (schoolBox() as HTMLElement).querySelector('input') as HTMLInputElement

async function mount() {
  render(<ProfileInputPage />)
  await waitFor(() => expect(profileMock).toHaveBeenCalled())
  await act(async () => { await Promise.resolve() })
}

async function pressContinue() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /onboarding\.(saveReturnToApplication|seeRecommendations)/ }))
  })
  await waitFor(() => expect(push).toHaveBeenCalled())
}

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
  profileMock.mockResolvedValue({ gender: 'female', school: '' })
})

describe('(a) the apply stash prefills the school', () => {
  it('shows the school typed on "About Me" when the profile has none', async () => {
    detourFrom('SMK Taman Desa')
    sessionStorage.removeItem(APPLY_RETURN_KEY)      // shown, so the prefill can be seen
    await mount()
    expect(schoolInput().value).toBe('SMK Taman Desa')
  })

  it("the profile's own school wins over the stash", async () => {
    detourFrom('SMK Taman Desa')
    sessionStorage.removeItem(APPLY_RETURN_KEY)
    profileMock.mockResolvedValue({ gender: 'female', school: 'SMK Bukit Jalil' })
    await mount()
    expect(schoolInput().value).toBe('SMK Bukit Jalil')
  })
})

describe('(b) on the way back to the application', () => {
  it('hides the School box when the stash knows the school — and saves that school', async () => {
    detourFrom('SMK Taman Desa')
    await mount()
    expect(screen.getByText('onboarding.saveReturnToApplication')).toBeTruthy()
    expect(schoolBox()).toBeNull()
    await pressContinue()
    expect(syncMock.mock.calls[0][0].school).toBe('SMK Taman Desa')
    expect(push).toHaveBeenCalledWith('/scholarship/apply')
  })

  it('hides it when only the profile knows the school, and saving does not erase it', async () => {
    detourFrom('')
    profileMock.mockResolvedValue({ gender: 'female', school: 'SMK Bukit Jalil' })
    await mount()
    expect(schoolBox()).toBeNull()
    await pressContinue()
    expect(syncMock.mock.calls[0][0].school).toBe('SMK Bukit Jalil')
    expect(JSON.parse(localStorage.getItem(KEY_PROFILE) as string).school).toBe('SMK Bukit Jalil')
  })

  it('shows it, empty, when no school is known — and it stays while she types and clears it', async () => {
    detourFrom('')
    await mount()
    expect(schoolInput().value).toBe('')
    fireEvent.change(schoolInput(), { target: { value: 'SMK Seri' } })
    expect(schoolBox()).toBeTruthy()                 // never vanishes under a typist
    fireEvent.change(schoolInput(), { target: { value: '' } })
    expect(schoolInput().value).toBe('')
    await pressContinue()
    expect(syncMock.mock.calls[0][0]).not.toHaveProperty('school')   // a blank is never sent
  })
})

describe('outside the return trip nothing changes', () => {
  it('shows the School box with the profile school, as before', async () => {
    profileMock.mockResolvedValue({ gender: 'female', school: 'SMK Bukit Jalil' })
    await mount()
    expect(screen.getByText('onboarding.seeRecommendations')).toBeTruthy()
    expect(schoolInput().value).toBe('SMK Bukit Jalil')
    await pressContinue()
    expect(push).toHaveBeenCalledWith('/dashboard')
  })
})
