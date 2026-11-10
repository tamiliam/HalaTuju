/**
 * @jest-environment jsdom
 *
 * A3.9 PINNING TESTS for /profile — written BEFORE the page was split into section components
 * and hooks, and kept passing after it. They pin what a student sees and what a Save sends:
 * the five sections, the view rows, the validation messages, the save flows, and that every
 * `t('...')` key the page's files use exists in en, ms and ta.
 */
import fs from 'fs'
import path from 'path'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProfilePage from './page'
import { KEY_PROFILE } from '@/lib/storage'
import { claimNric, getProfile, sendVerificationEmail, updateProfile } from '@/lib/api'

const mockRouter = { push: jest.fn(), replace: jest.fn() }
const mockAuth = {
  session: { user: { email: 'stu@example.com' } }, token: 'tkn', isAuthenticated: true, isLoading: false,
  showAuthGate: jest.fn(), refreshProfile: jest.fn(() => Promise.resolve()),
}
const mockT = { t: (k: string) => k, locale: 'en' }
const mockToast = { showToast: jest.fn() }
const mockGuard = { ready: true, loading: false, needsNric: false }
const mockPostcode = { edited: jest.fn(), lookup: jest.fn() }

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

const profileMock = getProfile as jest.Mock
const updateMock = updateProfile as jest.Mock
const claimMock = claimNric as jest.Mock

const BASE = {
  name: 'TEST STUDENT', gender: 'female', nationality: 'malaysian', nric: '050202-02-2022',
  preferred_state: 'Kedah', address: '12 Jalan A', postal_code: '08000', city: 'Sungai Petani',
  household_income: 2500, household_size: 5, angka_giliran: 'AB123C456',
  contact_email: 'c@example.com', contact_email_verified: true, contact_phone: '012-345 6789',
  merit_score: 88.5, school: 'SMK Test', nric_locked: true,
}

async function mount(profile: Record<string, unknown> = {}) {
  profileMock.mockResolvedValue({ ...BASE, ...profile })
  render(<ProfilePage />)
  await waitFor(() => expect(screen.getAllByText('profile.edit').length).toBeGreaterThan(0))
}

// Edit buttons, in section order: identity, contact details, location, family, application.
const editSection = (i: number) => fireEvent.click(screen.getAllByText('profile.edit')[i])
const save = () => act(async () => { fireEvent.click(screen.getByText('profile.save')) })

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  window.history.replaceState({}, '', '/profile')
})

describe('the page', () => {
  it('shows the loading line until the profile arrives', async () => {
    let release: (v: unknown) => void = () => {}
    profileMock.mockReturnValue(new Promise(r => { release = r }))
    render(<ProfilePage />)
    expect(screen.getByText('common.loading')).toBeTruthy()
    release({ ...BASE })
    await waitFor(() => expect(screen.getByText('profile.title')).toBeTruthy())
  })

  it('draws the title, five sections and the course interests', async () => {
    await mount()
    for (const k of ['profile.title', 'profile.subtitle', 'profile.personalDetails', 'profile.contactDetails',
      'profile.contactLocation', 'profile.familyBackground', 'profile.applicationTracking']) {
      expect(screen.getByText(k)).toBeTruthy()
    }
    expect(screen.getAllByText('profile.edit')).toHaveLength(5)
    expect(screen.getByTestId('interests')).toBeTruthy()
  })

  it('asks for sign-in when not authenticated', async () => {
    mockAuth.isAuthenticated = false
    try {
      render(<ProfilePage />)
      await waitFor(() => expect(mockAuth.showAuthGate).toHaveBeenCalledWith('profile'))
    } finally { mockAuth.isAuthenticated = true }
  })

  it('sends a student with no grades to onboarding', async () => {
    mockGuard.ready = false
    try {
      profileMock.mockResolvedValue({ ...BASE })
      render(<ProfilePage />)
      await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/onboarding/exam-type'))
    } finally { mockGuard.ready = true }
  })

  it('offers a way back when started from the application', async () => {
    window.history.replaceState({}, '', '/profile?next=/scholarship/apply')
    await mount()
    expect(screen.getByText(/scholarship\.apply\.backToApplication/)).toBeTruthy()
  })

  it('ignores a next target that is not a scholarship path', async () => {
    window.history.replaceState({}, '', '/profile?next=https://evil.example')
    await mount()
    expect(screen.queryByText(/scholarship\.apply\.backToApplication/)).toBeNull()
  })

  it('opens the application section for #pathway', async () => {
    window.history.replaceState({}, '', '/profile#pathway')
    profileMock.mockResolvedValue({ ...BASE })
    render(<ProfilePage />)
    await waitFor(() => expect(screen.getByTestId('pathway-picker')).toBeTruthy())
  })
})

describe('the view rows', () => {
  it('shows the masked IC, the verified badge, contact, address, household and plans', async () => {
    await mount({ identity_verified: true, chosen_pathway: 'degree', ic_flags: [] })
    expect(screen.getByText('****-**-2022')).toBeTruthy()
    expect(screen.getAllByText('profile.verified').length).toBeGreaterThan(1)
    expect(screen.getByText('c@example.com')).toBeTruthy()
    expect(screen.getByText('Google (stu@example.com)')).toBeTruthy()
    expect(screen.getByText('12 Jalan A, 08000 Sungai Petani, Kedah')).toBeTruthy()
    expect(screen.getByText('RM 2,500')).toBeTruthy()
    expect(screen.getByText('AB123C456')).toBeTruthy()
    expect(screen.getByText('88.5')).toBeTruthy()
    expect(screen.getByText('scholarship.apply.plan.pathway.degree')).toBeTruthy()
  })

  it('counts incomplete fields per section', async () => {
    await mount({ name: '', gender: '', household_income: null, household_size: null, angka_giliran: '' })
    expect(screen.getAllByText(/profile\.incomplete/).length).toBeGreaterThanOrEqual(3)
  })

  it('flags an IC that disagrees with the card', async () => {
    await mount({ ic_flags: ['name_differs'] })
    expect(screen.getByText('profile.icNeedsCheck')).toBeTruthy()
  })

  it('card merit goes to the grades editor and stashes the return', async () => {
    await mount()
    fireEvent.click(screen.getByText('88.5'))
    expect(mockRouter.push).toHaveBeenCalledWith(expect.stringContaining('/onboarding'))
  })
})

describe('identity section', () => {
  it('a locked IC cannot be edited', async () => {
    await mount({ nric_locked: true })
    editSection(0)
    expect((screen.getByLabelText('profile.icMasked') as HTMLInputElement).disabled).toBe(true)
    expect(screen.getByText('profile.icLockedNote')).toBeTruthy()
  })

  it('shows the card flags and what is fixable when the IC is editable', async () => {
    await mount({ nric_locked: false, ic_flags: ['name_differs'], ic_card_nric: '050202-02-2023', ic_card_name: 'CARD NAME' })
    editSection(0)
    expect(screen.getByText('profile.icFlagTitle')).toBeTruthy()
    expect(screen.getByText('050202-02-2023')).toBeTruthy()
    expect(screen.getByText('CARD NAME')).toBeTruthy()
  })

  it('refuses an invalid IC with the inline and toast message', async () => {
    await mount({ nric_locked: false })
    editSection(0)
    fireEvent.change(screen.getByLabelText('profile.icMasked'), { target: { value: '12' } })
    await save()
    expect(mockToast.showToast).toHaveBeenCalledWith('profile.icInvalid', 'error')
    expect(screen.getByText('profile.icInvalid')).toBeTruthy()
    expect(updateMock).not.toHaveBeenCalled()
    expect(claimMock).not.toHaveBeenCalled()
  })

  it('refuses an IC that belongs to someone else and never sends confirm', async () => {
    claimMock.mockResolvedValue({ status: 'exists' })
    await mount({ nric_locked: false })
    editSection(0)
    fireEvent.change(screen.getByLabelText('profile.icMasked'), { target: { value: '060303-03-3033' } })
    await save()
    expect(claimMock).toHaveBeenCalledWith('060303-03-3033', false, { token: 'tkn' })
    expect(mockToast.showToast).toHaveBeenCalledWith('profile.icTaken', 'error')
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('a server refusal of the IC is a flat refusal', async () => {
    claimMock.mockRejectedValue(new Error('403'))
    await mount({ nric_locked: false })
    editSection(0)
    fireEvent.change(screen.getByLabelText('profile.icMasked'), { target: { value: '060303-03-3033' } })
    await save()
    expect(mockToast.showToast).toHaveBeenCalledWith('profile.icRefused', 'error')
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('saves the whole profile payload without the nric, then refreshes and leaves the editor', async () => {
    await mount()
    editSection(0)
    fireEvent.change(screen.getAllByRole('textbox').find(el => (el as HTMLInputElement).value === 'TEST STUDENT')!,
      { target: { value: 'NEW NAME' } })
    await save()
    await waitFor(() => expect(updateMock).toHaveBeenCalled())
    const body = updateMock.mock.calls[0][0]
    expect(body).toMatchObject({
      name: 'NEW NAME', gender: 'female', nationality: 'malaysian', preferred_state: 'Kedah',
      address: '12 Jalan A', postal_code: '08000', household_income: 2500, household_size: 5,
      angka_giliran: 'AB123C456', school: 'SMK Test', contact_email: 'c@example.com',
    })
    expect(body).not.toHaveProperty('nric')
    expect(updateMock.mock.calls[0][1]).toEqual({ token: 'tkn' })
    await waitFor(() => expect(mockAuth.refreshProfile).toHaveBeenCalled())
    await waitFor(() => expect(screen.queryByText('profile.save')).toBeNull())
    expect(JSON.parse(localStorage.getItem(KEY_PROFILE) as string)).toMatchObject({ gender: 'female' })
  })

  it('goes back to the application after a save when it was started from there', async () => {
    window.history.replaceState({}, '', '/profile?next=/scholarship/apply')
    await mount()
    editSection(0)
    await save()
    await waitFor(() => expect(mockRouter.push).toHaveBeenCalledWith('/scholarship/apply'))
  })

  it('Cancel puts the old name back and shows no save button', async () => {
    await mount()
    editSection(0)
    fireEvent.change(screen.getAllByRole('textbox').find(el => (el as HTMLInputElement).value === 'TEST STUDENT')!,
      { target: { value: 'CHANGED' } })
    fireEvent.click(screen.getByText('profile.cancel'))
    expect(screen.getByText('TEST STUDENT')).toBeTruthy()
    expect(screen.queryByText('profile.save')).toBeNull()
  })

  it('only one section edits at a time', async () => {
    await mount()
    editSection(0)
    expect(screen.queryAllByText('profile.edit')).toHaveLength(0)
  })
})

describe('contact details section', () => {
  it('refuses an invalid phone number on save', async () => {
    await mount()
    editSection(1)
    fireEvent.change(screen.getByPlaceholderText('012-345 6789'), { target: { value: '123' } })
    await save()
    expect(mockToast.showToast).toHaveBeenCalledWith('profile.invalidPhone', 'error')
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('says phone verification is paused when it is off', async () => {
    await mount({ contact_phone_verified: false, phone_verify_enabled: false })
    editSection(1)
    expect(screen.getByText('profile.phoneVerifyPaused')).toBeTruthy()
  })

  it('saves the contact email then sends the verification, and says so', async () => {
    await mount({ contact_email_verified: false })
    editSection(1)
    await act(async () => { fireEvent.click(screen.getByText('profile.verify')) })
    await waitFor(() => expect(sendVerificationEmail).toHaveBeenCalledWith('c@example.com', 'en', { token: 'tkn' }))
    expect(updateMock).toHaveBeenCalledWith({ contact_email: 'c@example.com' }, { token: 'tkn' })
    expect(mockToast.showToast).toHaveBeenCalledWith('profile.verificationSent', 'success')
  })

  it('a failed verification email toasts an error', async () => {
    ;(sendVerificationEmail as jest.Mock).mockRejectedValueOnce(new Error('x'))
    await mount({ contact_email_verified: false })
    editSection(1)
    await act(async () => { fireEvent.click(screen.getByText('profile.verify')) })
    await waitFor(() => expect(mockToast.showToast).toHaveBeenCalledWith('Failed to send verification email.', 'error'))
  })
})

describe('location section', () => {
  it('saves a changed street', async () => {
    await mount()
    editSection(2)
    fireEvent.change(screen.getByPlaceholderText('No. 12, Jalan ABC, Taman XYZ'), { target: { value: '99 Jalan B' } })
    await save()
    await waitFor(() => expect(updateMock).toHaveBeenCalled())
    expect(updateMock.mock.calls[0][0].address).toBe('99 Jalan B')
  })

  it('keeps only five digits of the postcode and looks it up', async () => {
    await mount()
    editSection(2)
    fireEvent.change(screen.getByPlaceholderText('08000'), { target: { value: '12a3456' } })
    expect((screen.getByPlaceholderText('08000') as HTMLInputElement).value).toBe('12345')
    expect(mockPostcode.lookup).toHaveBeenCalledWith('12345')
  })

  it('marks a hand edit of city or state so a late postcode answer cannot overwrite it', async () => {
    await mount()
    editSection(2)
    fireEvent.change(screen.getByPlaceholderText('Sungai Petani'), { target: { value: 'X' } })
    expect(mockPostcode.edited).toHaveBeenCalled()
  })
})

describe('family section', () => {
  it('shows the roster editor and the helper text when valid', async () => {
    await mount()
    editSection(3)
    expect(screen.getByTestId('roster')).toBeTruthy()
    expect(screen.getByText('profile.householdIncomeHelper')).toBeTruthy()
    expect(screen.getByText('profile.householdSizeHelper')).toBeTruthy()
  })

  it('a bad household size shows its message and blocks Save', async () => {
    await mount()
    editSection(3)
    fireEvent.change(screen.getByDisplayValue('5'), { target: { value: '25' } })
    expect(screen.getByText('profile.invalidHouseholdSize')).toBeTruthy()
    expect((screen.getByText('profile.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('a blank household income shows its message and blocks Save', async () => {
    await mount()
    editSection(3)
    fireEvent.change(screen.getByDisplayValue('2500'), { target: { value: '' } })
    expect(screen.getByText('profile.invalidHouseholdIncome')).toBeTruthy()
    expect((screen.getByText('profile.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('saves valid household numbers as integers and the roster', async () => {
    await mount({ father_name: 'Ravi', father_occupation: 'other', father_occupation_other: ' Driver ' })
    editSection(3)
    fireEvent.change(screen.getByDisplayValue('5'), { target: { value: '6' } })
    await save()
    await waitFor(() => expect(updateMock).toHaveBeenCalled())
    expect(updateMock.mock.calls[0][0]).toMatchObject({
      household_size: 6, household_income: 2500, father_name: 'Ravi', father_occupation_other: 'Driver',
    })
  })

  it('shows the read-only family summary with the profession', async () => {
    await mount({ father_name: 'Ravi', father_occupation: 'farmer', mother_name: '', siblings_in_school: 2 })
    expect(screen.getByText('Ravi (scholarship.nextSteps.story.cardA.prof.farmer)')).toBeTruthy()
  })
})

describe('application section', () => {
  it('a malformed Angka Giliran shows its message and blocks Save', async () => {
    await mount()
    editSection(4)
    fireEvent.change(screen.getByPlaceholderText('AB123C456'), { target: { value: 'zz' } })
    expect(screen.getByText('profile.angkaGiliranInvalid')).toBeTruthy()
    expect((screen.getByText('profile.save') as HTMLButtonElement).disabled).toBe(true)
  })

  it('uppercases and trims Angka Giliran to nine characters', async () => {
    await mount()
    editSection(4)
    fireEvent.change(screen.getByPlaceholderText('AB123C456'), { target: { value: 'ab123c4567890' } })
    expect((screen.getByPlaceholderText('AB123C456') as HTMLInputElement).value).toBe('AB123C456')
  })

  it('the plans row opens the picker, and a third-route holder reads the CGPA label', async () => {
    await mount({ results_held: 'matric', overall_cgpa: 3.456 })
    expect(screen.getByText('onboarding.cgpaLabel')).toBeTruthy()
    expect(screen.getByText('3.46')).toBeTruthy()
    fireEvent.click(screen.getByText('profile.pathwayTapAdd'))
    expect(screen.getByTestId('pathway-picker')).toBeTruthy()
  })

  it('saves the plans fields in snake shape', async () => {
    await mount({ pathway_certainty: 'sure', chosen_pathway: 'degree', pre_u_track: 'x' })
    editSection(4)
    await save()
    await waitFor(() => expect(updateMock).toHaveBeenCalled())
    expect(updateMock.mock.calls[0][0]).toMatchObject({
      pathway_certainty: 'sure', chosen_pathway: 'degree', pre_u_track: 'x', pathways_considered: [],
    })
  })
})

describe('a failed load or save', () => {
  it('toasts when the profile cannot load', async () => {
    profileMock.mockRejectedValue(new Error('boom'))
    render(<ProfilePage />)
    await waitFor(() => expect(mockToast.showToast).toHaveBeenCalledWith('Failed to load profile. Please try again.', 'error'))
  })

  it('toasts when the save fails and keeps the editor open', async () => {
    await mount()
    editSection(0)
    updateMock.mockRejectedValueOnce(new Error('boom'))
    await save()
    await waitFor(() => expect(mockToast.showToast).toHaveBeenCalledWith('Failed to save profile. Please try again.', 'error'))
    expect(screen.getByText('profile.save')).toBeTruthy()
  })
})

describe('i18n', () => {
  const dirs = [path.join(__dirname), path.join(__dirname, 'sections'), path.join(__dirname, 'sections', 'edit'), path.join(__dirname, '..', '..', 'components', 'profile')]
  const sources = dirs.flatMap(d => fs.readdirSync(d)
    .filter(f => /\.(tsx?)$/.test(f) && !/\.test\./.test(f))
    .map(f => fs.readFileSync(path.join(d, f), 'utf8')))
  const used = new Set<string>()
  for (const s of sources) for (const m of s.matchAll(/\bt\(\s*'([a-zA-Z0-9_.]+)'\s*\)/g)) used.add(m[1])
  const flat = (o: Record<string, unknown>, p = ''): string[] =>
    Object.entries(o).flatMap(([k, v]) => (v && typeof v === 'object'
      ? flat(v as Record<string, unknown>, `${p}${k}.`) : [`${p}${k}`]))
  const msgs = (l: string) => new Set(flat(JSON.parse(
    fs.readFileSync(path.join(__dirname, '..', '..', 'messages', `${l}.json`), 'utf8'))))

  it('uses a meaningful number of keys', () => { expect(used.size).toBeGreaterThan(60) })

  for (const l of ['en', 'ms', 'ta']) {
    it(`every literal key the profile files use exists in ${l}`, () => {
      const have = msgs(l)
      expect([...used].filter(k => !have.has(k))).toEqual([])
    })
  }
})
