/**
 * @jest-environment jsdom
 *
 * THE APPLY DRAFT on the page (Mobile M4, owner ruling: this tab only). An iOS tab kill is a remount
 * of the page with this tab's sessionStorage intact — so every case here unmounts and mounts again.
 * Also the two submit doors M4 closed: Enter before the last step means Next, and a press while a
 * submit is in flight sends nothing.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import { getApplyGate, getScholarshipIntake, submitScholarshipApplication } from '@/lib/api'
import { APPLY_DRAFT_KEY } from '@/lib/applyDraft'
import { type ApplyFormState } from '@/lib/scholarship'
import { consentAndSign, seedApplyDraft, signAndSubmit, testSession, TEST_UID } from '@/test/applyDraftSeed'

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
  claimNric: jest.fn(() => Promise.resolve({ status: 'claimed' })),
  submitScholarshipApplication: jest.fn(() => Promise.resolve({})),
  getPathwayOfferings: jest.fn(() => Promise.resolve({ pathway: '', institutions: [], courses: [] })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}))

const intake = getScholarshipIntake as jest.Mock
const gate = getApplyGate as jest.Mock
const submit = submitScholarshipApplication as jest.Mock

const ONE_OPEN = { open: true, cohort_name: 'B40 2026', programme_code: 'bp', choices: [], apply_copy: {} }
const ALLOWED = { allowed: true, reason: '', application_id: null }
const profile = { ...sandboxProfileSpm, results_held: 'spm', nric: '080101-14-1234', nric_verified: true }

const complete: ApplyFormState = {
  name: 'Priya', school: 'SMK Taman Desa', nric: '080101-14-1234', referringOrg: 'other',
  homeState: 'Selangor', phone: '012-345 6789',
  householdIncome: '2500', householdSize: '5', receivesStr: true, receivesJkm: false,
  parentName: 'Rajan', parentPhone: '012-777 8888', callLanguage: '',
  pathwayCertainty: 'sure', chosenPathway: 'poly',
  chosenProgramme: { courseId: 'C1', courseName: 'Diploma in Engineering', fieldKey: 'engineering' },
  preUTrack: '', preUInstitution: '', uncertaintyReasons: [], uncertaintyNote: '',
  pathwaysConsidered: [], topChoices: [], upuStatus: '', fieldOfStudy: '',
  otherScholarships: [], otherScholarshipsText: '', intendsTertiary2026: true,
  helpUniversity: '', helpScholarship: '', anythingElse: '', consentToContact: true,
  declarationName: 'Priya',
}

const mount = (session: object | null = testSession) => render(
  <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', session, showAuthGate: () => {} } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)
const stored = () => JSON.parse(sessionStorage.getItem(APPLY_DRAFT_KEY) || 'null')
const stepLine = () => screen.getByTestId('apply-progress').textContent || ''

beforeEach(() => {
  jest.clearAllMocks()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/scholarship/apply')
  intake.mockResolvedValue(ONE_OPEN)
  gate.mockResolvedValue(ALLOWED)
})

describe('an iOS tab kill (a remount, the tab storage kept)', () => {
  it('her typing and her step come back', async () => {
    seedApplyDraft(complete, 'family', 'bp')               // she is on My Family
    const view = mount()
    await screen.findByTestId('apply-gift-line')
    fireEvent.change(await screen.findByDisplayValue('Rajan'), { target: { value: 'Rajan a/l Muthu' } })
    // iOS puts the tab away: `pagehide` writes at once (the debounce timer may never fire).
    act(() => { window.dispatchEvent(new Event('pagehide')) })
    expect(stored()?.form?.parentName).toBe('Rajan a/l Muthu')
    expect(stored().uid).toBe(TEST_UID)
    expect(stored().programme).toBe('bp')
    view.unmount()                                       // iOS reclaims the tab

    mount()
    await screen.findByTestId('apply-gift-line')
    expect(stepLine()).toContain('scholarship.apply.section.family')
    expect(await screen.findByDisplayValue('Rajan a/l Muthu')).toBeTruthy()
  })

  it('the signature and the consent are NOT restored — given afresh before she can submit', async () => {
    seedApplyDraft(complete, 'support', 'bp')
    mount()
    await screen.findByTestId('apply-gift-line')
    expect(((await screen.findByPlaceholderText('scholarship.apply.declaration.signPlaceholder')) as HTMLInputElement).value).toBe('')
    expect(screen.getByRole('switch', { name: 'scholarship.apply.consentLabel' }).getAttribute('aria-checked')).toBe('false')
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    expect(submit).not.toHaveBeenCalled()
  })

  it("ANOTHER student signed in on this tab gets the profile's form, never the draft — and it is deleted", async () => {
    seedApplyDraft(complete, 'support', 'bp', 'somebody-else')
    mount()
    await screen.findByTestId('apply-gift-line')
    expect(stepLine()).toContain('scholarship.apply.section.personal')
    expect(screen.queryByDisplayValue('012-777 8888')).toBeNull()
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()
  })

  it('nothing is written before she changes anything', async () => {
    mount()
    await screen.findByTestId('apply-gift-line')
    await act(async () => { await new Promise((r) => setTimeout(r, 700)) })
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()
  })
})

describe('review F1 — another account signs in (in another tab) while this form is open', () => {
  it("A's typing is dropped, nothing is stored under B, and the form starts from B's own profile", async () => {
    seedApplyDraft(complete, 'family', 'bp')                       // A's draft (TEST_UID), on My Family
    const ctx = (session: object | null, prof: object) => (
      <AuthContext.Provider value={{ status: 'ready', profile: prof, token: 'tkn', session, showAuthGate: () => {} } as never}>
        <ScholarshipApplyPage />
      </AuthContext.Provider>
    )
    const view = render(ctx(testSession, profile))
    fireEvent.change(await screen.findByDisplayValue('Rajan'), { target: { value: 'Rajan a/l Muthu' } })

    // B signs in: the context's id changes first, the old profile is still in memory for a moment...
    const B = { user: { id: 'student-b' } }
    view.rerender(ctx(B, profile))
    act(() => { window.dispatchEvent(new Event('pagehide')) })           // a flush at the worst moment
    expect(screen.queryByDisplayValue('Rajan a/l Muthu')).toBeNull()
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()

    // ...then B's own profile arrives and seeds the form — on About Me, with B's name.
    const profileB = { ...profile, name: 'Siti Contoh', nric: '090202-10-2222' }
    view.rerender(ctx(B, profileB))
    expect(await screen.findByDisplayValue('Siti Contoh')).toBeTruthy()
    expect(stepLine()).toContain('scholarship.apply.section.personal')
    act(() => { window.dispatchEvent(new Event('pagehide')) })
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()        // nothing changed by B: nothing kept
    expect(screen.queryByDisplayValue('Rajan a/l Muthu')).toBeNull()
  })

  it('signing out (id gone) drops the form as well', async () => {
    seedApplyDraft(complete, 'family', 'bp')
    const view = mount()
    await screen.findByDisplayValue('Rajan')
    view.rerender(
      <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', session: null, showAuthGate: () => {} } as never}>
        <ScholarshipApplyPage />
      </AuthContext.Provider>)
    expect(screen.queryByDisplayValue('Rajan')).toBeNull()
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()
  })
})

describe('when it goes', () => {
  it('a successful submit deletes it — nothing of the form stays on the phone', async () => {
    seedApplyDraft(complete, 'support', 'bp')
    mount()
    await screen.findByTestId('apply-gift-line')
    await signAndSubmit('Priya')
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
    await act(async () => { await new Promise((r) => setTimeout(r, 700)) })   // no late write either
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()
  })

  it('a failed submit keeps it (she may try again after a reload)', async () => {
    submit.mockRejectedValueOnce(Object.assign(new Error('API error: 500'), { status: 500, code: '', bodyCode: '' }))
    seedApplyDraft(complete, 'support', 'bp')
    mount()
    await screen.findByTestId('apply-gift-line')
    await signAndSubmit('Priya')
    expect(await screen.findByText('scholarship.apply.error.generic')).toBeTruthy()
    expect(stored()?.form?.name).toBe('Priya')
  })

  it('the server says she has already applied: deleted', async () => {
    gate.mockResolvedValue({ allowed: false, reason: 'already_applied', application_id: 7 })
    seedApplyDraft(complete, 'family', 'bp')
    mount()
    await screen.findByTestId('apply-already-applied')
    expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull()
  })

  it('the programme has closed: deleted', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=bp')
    intake.mockResolvedValue({ open: false, cohort_name: '', choices: [] })
    seedApplyDraft(complete, 'family', 'bp')
    mount()
    await waitFor(() => expect(sessionStorage.getItem(APPLY_DRAFT_KEY)).toBeNull())
  })
})

describe('the submit doors (Mobile M4)', () => {
  it('Enter in a field before the last step means NEXT — nothing is sent', async () => {
    seedApplyDraft(complete, 'personal', 'bp')
    mount()
    await screen.findByTestId('apply-gift-line')
    const name = await screen.findByDisplayValue('Priya')
    await act(async () => { fireEvent.submit(name.closest('form') as HTMLFormElement) })
    expect(stepLine()).toContain('scholarship.apply.section.family')
    expect(submit).not.toHaveBeenCalled()
  })

  it('a second press while the submit is in flight sends nothing', async () => {
    submit.mockImplementation(() => new Promise(() => {}))        // hangs
    seedApplyDraft(complete, 'support', 'bp')
    mount()
    await screen.findByTestId('apply-gift-line')
    await consentAndSign('Priya')
    const form = screen.getByRole('button', { name: 'scholarship.apply.submit' }).closest('form') as HTMLFormElement
    await act(async () => { fireEvent.submit(form) })
    await act(async () => { fireEvent.submit(form) })             // Enter in the signature box
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('the phone footer is sticky, clears the home bar, and holds Back + Continue', async () => {
    seedApplyDraft(complete, 'family', 'bp')
    mount()
    await screen.findByDisplayValue('Rajan')                     // the draft has landed on My Family
    const footer = screen.getByTestId('apply-footer')
    expect(footer.className).toMatch(/\bsticky bottom-0\b/)
    expect(footer.className).toContain('env(safe-area-inset-bottom)')
    expect(footer.textContent).toContain('scholarship.apply.back')
    expect(footer.textContent).toContain('scholarship.apply.continue')
    expect(screen.getByTestId('apply-draft-note').textContent).toBe('scholarship.apply.commitNote')
  })
})
