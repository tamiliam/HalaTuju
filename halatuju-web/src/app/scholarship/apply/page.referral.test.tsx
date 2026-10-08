/**
 * @jest-environment jsdom
 *
 * "Who referred you?" on the apply form — rendered (per-gift referral sources, Sprint 2, 2026-10-08).
 *
 * The owner's rulings, as a student meets them:
 *   • the list is THIS gift's served sources (by the server's names), then Halatuju.xyz,
 *     Facebook / WhatsApp and Other — always; a served code that collides with one of those is
 *     shown once; an intake with no `sources` (older api) or a failed intake → the three alone;
 *   • a saved choice the list does not offer is CLEARED, never silently resubmitted;
 *   • a submit the server refuses (`referral_source_not_offered`) re-reads the list, returns her
 *     to the field with a plain sentence, and loses nothing else she typed.
 *
 * `t` echoes its key; source names are data.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import { getApplyGate, getScholarshipIntake, submitScholarshipApplication } from '@/lib/api'
import { stashApplyForm, type ApplyFormState } from '@/lib/scholarship'

const mockRouter = { push: jest.fn(), replace: jest.fn() }
jest.mock('next/navigation', () => ({
  useRouter: () => mockRouter,
  usePathname: () => '/scholarship/apply',
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
  tOr: (t: (k: string) => string, k: string, fallback: string) => (t(k) === k ? fallback : t(k)),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getScholarshipIntake: jest.fn(),
  getMyScholarshipApplications: jest.fn(() => Promise.resolve({ applications: [] })),
  getApplyGate: jest.fn(),
  submitScholarshipApplication: jest.fn(() => Promise.resolve({})),
  checkEligibility: jest.fn(() => Promise.resolve({ pathway_stats: {}, eligible_courses: [] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [] })),
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [] })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const intake = getScholarshipIntake as jest.Mock
const gate = getApplyGate as jest.Mock
const submit = submitScholarshipApplication as jest.Mock

const SMC = { code: 'smc', name: 'Sri Murugan Centre' }
const CUMIG = { code: 'cumig', name: 'Concerned UM Indian Graduates' }
const OPEN = (sources?: object[]) => ({
  open: true, cohort_name: 'B40 2026', programme_code: 'bp', choices: [], apply_copy: {},
  ...(sources ? { sources } : {}),
})

const mount = (referral_source = '') => render(
  <AuthContext.Provider value={{
    status: 'ready', token: 'tkn', showAuthGate: () => {},
    profile: { ...sandboxProfileSpm, results_held: 'spm', nric: '080101-14-1234', nric_verified: true,
      referral_source },
  } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)

const select = () => screen.getByTestId('referral-select') as HTMLSelectElement
const optionCodes = () => Array.from(select().options).map((o) => o.value)
const optionLabels = () => Array.from(select().options).map((o) => o.textContent)

beforeEach(() => {
  jest.clearAllMocks()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/scholarship/apply')
  gate.mockResolvedValue({ allowed: true, reason: '', application_id: null })
})

describe('the options', () => {
  it("are the gift's sources by their served names, then the fixed three", async () => {
    intake.mockResolvedValue(OPEN([CUMIG, SMC]))
    mount()
    await screen.findByTestId('apply-gift-line')
    expect(optionCodes()).toEqual(['', 'cumig', 'smc', 'halatuju', 'social', 'other'])
    expect(optionLabels()).toEqual([
      'scholarship.apply.orgPlaceholder', 'Concerned UM Indian Graduates', 'Sri Murugan Centre',
      'scholarship.apply.org.halatuju', 'scholarship.apply.org.social', 'scholarship.apply.org.other',
    ])
  })

  it('show a source code that collides with a fixed choice once, as the fixed choice', async () => {
    intake.mockResolvedValue(OPEN([{ code: 'other', name: 'A source called other' }, SMC]))
    mount()
    await screen.findByTestId('apply-gift-line')
    expect(optionCodes()).toEqual(['', 'smc', 'halatuju', 'social', 'other'])
  })

  it('are the fixed three alone when the intake sends no `sources` (an older api)', async () => {
    intake.mockResolvedValue(OPEN())
    mount()
    await screen.findByTestId('apply-gift-line')
    expect(optionCodes()).toEqual(['', 'halatuju', 'social', 'other'])
  })

  it('are the fixed three alone when the intake fails', async () => {
    intake.mockRejectedValue(new Error('down'))
    mount()
    await waitFor(() => expect(screen.getByTestId('referral-select')).toBeTruthy())
    expect(optionCodes()).toEqual(['', 'halatuju', 'social', 'other'])
  })
})

describe('a saved choice', () => {
  it('that the list does not offer is CLEARED, never resubmitted (a retired code)', async () => {
    intake.mockResolvedValue(OPEN([SMC]))
    mount('pushparani')
    await screen.findByTestId('apply-gift-line')
    await waitFor(() => expect(select().value).toBe(''))
  })

  it('that another gift offered is cleared too', async () => {
    intake.mockResolvedValue(OPEN([SMC]))
    mount('cumig')
    await screen.findByTestId('apply-gift-line')
    await waitFor(() => expect(select().value).toBe(''))
  })

  // ── Review fix (2026-10-08): clear ONLY when the list is really known ──────────────────────
  it('is KEPT and shown when the intake fails — an intake blip never costs her the attribution', async () => {
    intake.mockRejectedValue(new Error('down'))
    mount('smc')
    await waitFor(() => expect(screen.getByTestId('referral-select')).toBeTruthy())
    await act(async () => { await Promise.resolve() })
    expect(select().value).toBe('smc')
    // Shown as an extra option labelled with its code — never the placeholder over a hidden value.
    expect(optionCodes()).toEqual(['', 'halatuju', 'social', 'other', 'smc'])
    expect(optionLabels()[4]).toBe('smc')
  })

  it('is KEPT when an older api sends no `sources` (the web deployed first)', async () => {
    intake.mockResolvedValue(OPEN())
    mount('smc')
    await screen.findByTestId('apply-gift-line')
    await act(async () => { await Promise.resolve() })
    expect(select().value).toBe('smc')
  })

  it('is KEPT on an ambiguous visit until a gift is picked — then the rule applies', async () => {
    const TWO = { open: true, cohort_name: '', programme_code: '', apply_copy: {}, sources: [],
      choices: [{ code: 'bp', name: 'BrightPath 2026' }, { code: 'sabah', name: 'Sabah 2026' }] }
    const coded = (code: string) => ({ ...OPEN(code === 'bp' ? [CUMIG] : [SMC]), programme_code: code,
      cohort_name: code === 'bp' ? 'BrightPath 2026' : 'Sabah 2026' })
    intake.mockImplementation((code?: string) => Promise.resolve(code ? coded(code) : TWO))
    mount('cumig')
    await screen.findByText('scholarship.apply.chooseTitle')
    // A gift that offers it: still there, so nothing cleared it while no gift was named.
    fireEvent.click(screen.getByLabelText('BrightPath 2026'))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    await screen.findByTestId('apply-gift-line')
    await act(async () => { await Promise.resolve() })
    expect(select().value).toBe('cumig')
    // Change to a gift that does not: now the list is known, and it is cleared.
    fireEvent.click(screen.getByTestId('apply-gift-change'))
    await screen.findByText('scholarship.apply.chooseTitle')
    fireEvent.click(screen.getByLabelText('Sabah 2026'))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    await screen.findByTestId('apply-gift-line')
    await waitFor(() => expect(select().value).toBe(''))
  })

  it('that the list offers is kept', async () => {
    intake.mockResolvedValue(OPEN([SMC]))
    mount('smc')
    await screen.findByTestId('apply-gift-line')
    await act(async () => { await Promise.resolve() })
    expect(select().value).toBe('smc')
  })
})

describe('the server refuses the code at submit', () => {
  const complete: ApplyFormState = {
    name: 'Priya', school: 'SMK Taman Desa', nric: '080101-14-1234', referringOrg: 'smc',
    homeState: 'Selangor', phone: '012-345 6789',
    householdIncome: '2500', householdSize: '5', receivesStr: true, receivesJkm: false,
    parentName: '', parentPhone: '', callLanguage: '',
    pathwayCertainty: 'sure', chosenPathway: 'poly',
    chosenProgramme: { courseId: 'C1', courseName: 'Diploma in Engineering', fieldKey: 'engineering' },
    preUTrack: '', preUInstitution: '', uncertaintyReasons: [], uncertaintyNote: '',
    pathwaysConsidered: [], topChoices: [], upuStatus: '', fieldOfStudy: '',
    otherScholarships: [], otherScholarshipsText: '', intendsTertiary2026: true,
    helpUniversity: '', helpScholarship: '', anythingElse: '', consentToContact: true,
    declarationName: 'Priya',
  }

  it('sends an offered source as referral_source', async () => {
    intake.mockResolvedValue(OPEN([SMC]))
    stashApplyForm(complete)
    mount()
    await screen.findByTestId('apply-gift-line')
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    await waitFor(() => expect(submit).toHaveBeenCalled())
    expect(submit.mock.calls[0][0].referral_source).toBe('smc')
  })

  it('re-reads the list, asks again by the field in plain words, and keeps everything else', async () => {
    // The source is switched off while she types: the first intake still lists it, the re-ask not.
    let switchedOff = false
    intake.mockImplementation(() => Promise.resolve(OPEN(switchedOff ? [CUMIG] : [SMC, CUMIG])))
    submit.mockImplementationOnce(() => {
      switchedOff = true
      return Promise.reject(Object.assign(new Error('API error: 400'),
        { status: 400, code: 'referral_source_not_offered', bodyCode: 'referral_source_not_offered' }))
    })
    stashApplyForm(complete)
    mount()
    await screen.findByTestId('apply-gift-line')
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })

    // Back on About Me, the field blank, the list re-read, the sentence beside it.
    expect(await screen.findByTestId('referral-refused')).toBeTruthy()
    expect(screen.getByTestId('referral-refused').textContent).toBe('scholarship.apply.error.orgNotOffered')
    expect(intake).toHaveBeenLastCalledWith('bp')
    expect(select().value).toBe('')
    expect(optionCodes()).toEqual(['', 'cumig', 'halatuju', 'social', 'other'])
    // Nothing else lost; no generic error over it.
    expect(screen.getByDisplayValue('Priya')).toBeTruthy()
    expect(screen.getByDisplayValue('SMK Taman Desa')).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.error.generic')).toBeNull()

    // Choosing again takes the sentence away, and the next submit sends the new choice.
    fireEvent.change(select(), { target: { value: 'cumig' } })
    expect(screen.queryByTestId('referral-refused')).toBeNull()
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2))
    expect(submit.mock.calls[1][0].referral_source).toBe('cumig')
    expect(submit.mock.calls[1][0].name).toBe('Priya')
  })
})
