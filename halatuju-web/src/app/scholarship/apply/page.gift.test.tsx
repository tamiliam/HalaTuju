/**
 * @jest-environment jsdom
 *
 * "Apply gift clarity" (2026-10-05) — the apply form, rendered, with two gifts open at once.
 *
 *   D1 — who is sent away from the form: any non-expired application (the server's duplicate rule),
 *        not `applications[0]`. An expired one lets the student start again, as the server does.
 *   D2 — a pick in the chooser re-reads the intake for THAT gift, so its own heading shows (and a
 *        gift that closed in the meantime bounces, like a closed link).
 *   D3 — a bare visit asks again instead of reusing a code an earlier visit stored.
 *   D4 — the form names the gift; "Change" appears only when another gift is open, and keeps edits.
 *
 * `t` echoes its key, so assertions read against i18n keys; gift names and gift copy are data.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import { getMyScholarshipApplications, getScholarshipIntake, submitScholarshipApplication } from '@/lib/api'
import { APPLY_PROGRAMME_KEY, stashApplyForm, type ApplyFormState } from '@/lib/scholarship'
import { readWeb } from '@/test/sourceGuard'

// ONE router object: the page's effects depend on it (see page.results.test.tsx).
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
  getMyScholarshipApplications: jest.fn(),
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
const myApps = getMyScholarshipApplications as jest.Mock
const submit = submitScholarshipApplication as jest.Mock

const SABAH = 'BrightPath Bursary, Sabah'
const TWO_OPEN = { open: true, cohort_name: '', apply_copy: {},
  choices: [{ code: 'bp', name: 'BrightPath Bursary Programme 2026' }, { code: 'sabah', name: SABAH }] }
const SABAH_OPEN = { open: true, cohort_name: SABAH, choices: [],
  apply_copy: { en: { title: 'Sabah bursary', intro: 'For students in Sabah.', criteria: ['Live in Sabah'] } } }

/** The intake endpoint: the bare question gets `bare`, a coded one gets `byCode[code]`. */
function serveIntake(bare: object, byCode: Record<string, object> = {}) {
  intake.mockImplementation((code?: string) =>
    Promise.resolve(code ? (byCode[code] ?? { open: false, cohort_name: '', choices: [] }) : bare))
}

const profile = { ...sandboxProfileSpm, results_held: 'spm', nric: '080101-14-1234', nric_verified: true }
const mount = () => render(
  <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)
const formShown = () => screen.findAllByText('scholarship.apply.section.results')

beforeEach(() => {
  jest.clearAllMocks()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/scholarship/apply')
  myApps.mockResolvedValue({ applications: [] })
  serveIntake({ open: true, cohort_name: 'B40 2026', choices: [], apply_copy: {} })
})

describe('D1 — who the form sends away (the server duplicate rule)', () => {
  it('a lone EXPIRED application stays on the form — the server lets her start again', async () => {
    myApps.mockResolvedValue({ applications: [{ id: 1, status: 'expired' }] })
    mount()
    await formShown()
    expect(mockRouter.replace).not.toHaveBeenCalledWith('/scholarship/application')
  })

  it('a lone REJECTED application is sent to her application page', async () => {
    myApps.mockResolvedValue({ applications: [{ id: 1, status: 'rejected' }] })
    mount()
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
  })
})

describe('D2 — a pick in the chooser shows the chosen gift', () => {
  it("re-reads the intake for the pick and shows that gift's own heading and name", async () => {
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    mount()
    await screen.findByText('scholarship.apply.chooseTitle')
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('scholarship.apply.title')
    // never pre-selected
    expect((screen.getByTestId('apply-choose-continue') as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))

    expect(await screen.findByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    expect(intake).toHaveBeenCalledWith('sabah')
    // the pick rides in the URL, so a refresh keeps it
    expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/apply?p=sabah')
    expect(sessionStorage.getItem(APPLY_PROGRAMME_KEY)).toBe('sabah')
    expect((await screen.findByTestId('apply-gift-line')).textContent).toContain(SABAH)
  })

  it('a picked gift that has just closed bounces to the landing, like a closed link', async () => {
    serveIntake(TWO_OPEN, { sabah: { ...SABAH_OPEN, open: false } })
    mount()
    await screen.findByText('scholarship.apply.chooseTitle')
    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship'))
  })
})

describe('D3 — a bare visit does not reuse an old code', () => {
  it('asks again, and forgets the stored code', async () => {
    sessionStorage.setItem(APPLY_PROGRAMME_KEY, 'sabah')     // an earlier visit in this tab
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    mount()
    await screen.findByText('scholarship.apply.chooseTitle')
    expect(intake).not.toHaveBeenCalledWith('sabah')
    expect(sessionStorage.getItem(APPLY_PROGRAMME_KEY)).toBeNull()
  })

  it("a link's code is used and kept", async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    mount()
    expect(await screen.findByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    expect(sessionStorage.getItem(APPLY_PROGRAMME_KEY)).toBe('sabah')
    expect(screen.queryByText('scholarship.apply.chooseTitle')).toBeNull()
  })
})

describe('D4 — the form names the gift', () => {
  it('names the only open gift, with no "Change" when there is nothing to change to', async () => {
    mount()
    expect((await screen.findByTestId('apply-gift-line')).textContent).toContain('B40 2026')
    expect(screen.getByText('scholarship.apply.applyingTo', { exact: false })).toBeTruthy()
    expect(screen.queryByTestId('apply-gift-change')).toBeNull()
  })

  it('"Change" returns to the chooser (nothing pre-selected) and keeps what she typed', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    mount()
    const change = await screen.findByTestId('apply-gift-change')
    const nameBox = screen.getByDisplayValue(String(profile.name))
    fireEvent.change(nameBox, { target: { value: 'Typed Before Change' } })

    fireEvent.click(change)
    await screen.findByText('scholarship.apply.chooseTitle')
    expect(sessionStorage.getItem(APPLY_PROGRAMME_KEY)).toBeNull()
    expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/apply')
    expect((screen.getByTestId('apply-choose-continue') as HTMLButtonElement).disabled).toBe(true)

    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    expect(await screen.findByDisplayValue('Typed Before Change')).toBeTruthy()
  })
})

describe('submit still names the gift', () => {
  const complete: ApplyFormState = {
    name: 'Priya', school: 'SMK Taman Desa', nric: '080101-14-1234', referringOrg: 'cumig',
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

  it('sends the code in force as programme_code — after a My Results detour back', async () => {
    // The detour's return: the stash, and the URL carrying ?p= (applyPagePath).
    stashApplyForm(complete)
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    mount()
    await screen.findByTestId('apply-gift-line')
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    await waitFor(() => expect(submit).toHaveBeenCalled())
    expect(submit.mock.calls[0][0].programme_code).toBe('sabah')
    expect(sessionStorage.getItem(APPLY_PROGRAMME_KEY)).toBeNull()   // forgotten once submitted
  })

  /** Land on the last tab with a complete form and press Submit. */
  async function submitComplete() {
    stashApplyForm(complete)
    mount()
    await screen.findByTestId('apply-gift-line')
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    await waitFor(() => expect(submit).toHaveBeenCalled())
    return submit.mock.calls[0][0]
  }

  it('⚠ a BARE visit with one gift open submits the code the shown name was resolved from', async () => {
    // Without it the server re-resolves at submit: if that round closed and another opened while
    // she typed, she would be filed under the other gift with no error anywhere.
    serveIntake({ open: true, cohort_name: SABAH, programme_code: 'sabah', choices: [], apply_copy: {} })
    expect((await submitComplete()).programme_code).toBe('sabah')
  })

  it('a link via a retired alias submits the CANONICAL code the server answered with', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah-old')
    serveIntake(TWO_OPEN, { 'sabah-old': { ...SABAH_OPEN, programme_code: 'sabah' } })
    expect((await submitComplete()).programme_code).toBe('sabah')
  })

  it('an older api that sends no programme_code: the URL code is submitted (and none on a bare visit)', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })               // SABAH_OPEN carries no programme_code
    expect((await submitComplete()).programme_code).toBe('sabah')
  })

  it('an older api on a bare visit sends no code at all, exactly as before', async () => {
    expect((await submitComplete())).not.toHaveProperty('programme_code')
  })

  it('a 409 programme_required at submit returns her to the chooser with her form kept', async () => {
    // The server could not tell which gift (e.g. a second round opened while she typed).
    const refusal = Object.assign(new Error('API error: 409'),
      { status: 409, code: 'We could not tell which programme this application is for.',
        bodyCode: 'programme_required' })
    submit.mockRejectedValueOnce(refusal)
    // First intake: one gift open (older api, no code); after the refusal the bare ask sees two.
    intake.mockResolvedValueOnce({ open: true, cohort_name: 'B40 2026', choices: [], apply_copy: {} })
    intake.mockImplementation((code?: string) =>
      Promise.resolve(code ? SABAH_OPEN : TWO_OPEN))
    await submitComplete()

    await screen.findByText('scholarship.apply.chooseTitle')
    expect(screen.queryByText('scholarship.apply.error.generic')).toBeNull()
    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    // Her typed answers survived: the support tab is still showing her signed declaration.
    expect(await screen.findByDisplayValue('Priya')).toBeTruthy()
    expect(screen.getByTestId('apply-gift-line').textContent).toContain(SABAH)
  })

  it('any other submit failure does not re-ask or re-route (control)', async () => {
    submit.mockRejectedValueOnce(Object.assign(new Error('API error: 409'),
      { status: 409, code: 'No open application round is currently available.', bodyCode: '' }))
    await submitComplete()
    const asked = intake.mock.calls.length          // the arrival's own ask
    // ⚠ Not asserting the generic error text: the page's live-revalidate effect clears ANY error
    // once the form itself is valid, so a server-side submit error vanishes at once. Pre-existing,
    // out of this change's scope — the claim here is only that nothing re-asks or re-routes.
    await act(async () => { await Promise.resolve() })
    expect(intake.mock.calls.length).toBe(asked)
    expect(mockRouter.replace).not.toHaveBeenCalledWith('/scholarship/apply')
    expect(screen.queryByText('scholarship.apply.chooseTitle')).toBeNull()
    expect(screen.getByTestId('apply-gift-line').textContent).toContain('B40 2026')
  })
})

describe('the chooser is loaded on demand (bundle)', () => {
  it('the apply page reaches GiftChooser only through the lazy boundary', () => {
    // A source read, like LazyStpmSchoolPicker.test.tsx: jest cannot weigh the bundle.
    const page = readWeb('src/app/scholarship/apply/page.tsx', 'first-load JS of /scholarship/apply')
    expect(page).toContain("from '@/components/scholarship/LazyGiftChooser'")
    expect(page).not.toMatch(/from\s+'@\/components\/scholarship\/GiftChooser'/)
    const lazy = readWeb('src/components/scholarship/LazyGiftChooser.tsx', 'the lazy boundary')
    expect(lazy).toContain("import('./GiftChooser')")
    expect(lazy).not.toMatch(/from\s+'\.\/GiftChooser'/)
  })
})
