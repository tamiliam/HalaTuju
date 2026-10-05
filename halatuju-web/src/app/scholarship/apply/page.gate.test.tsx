/**
 * @jest-environment jsdom
 *
 * One application per organisation (owner's ruling on TD-337, 2026-10-05) — the apply page OBEYS
 * the server's gate (`GET /scholarship/apply-gate/`) and keeps no rule of its own.
 *
 * FIRST STATE FIRST (yesterday's lesson): the signed-out bare and coded visits come before any
 * signed-in case, and neither may ask the gate at all. Then, signed in: allowed → the form;
 * `application_in_progress` → her application; `already_applied` → a card on this page; a failed
 * gate → the form; a pick re-asks; and a student whose application in gift A is finished applies to
 * gift B end to end. Last, TD-340: a server refusal at submit stays on screen.
 *
 * `t` echoes its key, so assertions read against i18n keys; gift names and copy are data.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import { claimNric, getApplyGate, getScholarshipIntake, submitScholarshipApplication } from '@/lib/api'
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
  claimNric: jest.fn(() => Promise.resolve({ status: 'claimed' })),
  submitScholarshipApplication: jest.fn(() => Promise.resolve({})),
  checkEligibility: jest.fn(() => Promise.resolve({ pathway_stats: {}, eligible_courses: [] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [] })),
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [] })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}))
// The real closed card, counted: "never a flash of the closed card" is asserted on its renders,
// not only on what is left on screen at the end.
const mockClosedRenders = jest.fn()
jest.mock('@/components/scholarship/GiftClosed', () => {
  const Actual = jest.requireActual('@/components/scholarship/GiftClosed').default
  return {
    __esModule: true,
    default: (p: object) => { mockClosedRenders(); return require('react').createElement(Actual, p) },
  }
})

const intake = getScholarshipIntake as jest.Mock
const gate = getApplyGate as jest.Mock
const submit = submitScholarshipApplication as jest.Mock
const claim = claimNric as jest.Mock

const SABAH = 'BrightPath Bursary, Sabah'
const TWO_OPEN = { open: true, cohort_name: '', programme_code: '', apply_copy: {},
  choices: [{ code: 'bp', name: 'BrightPath Bursary Programme 2026' }, { code: 'sabah', name: SABAH }] }
const SABAH_OPEN = { open: true, cohort_name: SABAH, programme_code: 'sabah', choices: [],
  apply_copy: { en: { title: 'Sabah bursary', intro: 'For students in Sabah.', criteria: ['Live in Sabah'] } } }
const ONE_OPEN = { open: true, cohort_name: 'B40 2026', programme_code: 'bp', choices: [], apply_copy: {} }

const ALLOWED = { allowed: true, reason: '', application_id: null }
const IN_PROGRESS = { allowed: false, reason: 'application_in_progress', application_id: 7 }
const ALREADY = { allowed: false, reason: 'already_applied', application_id: 7 }

function serveIntake(bare: object, byCode: Record<string, object> = {}) {
  intake.mockImplementation((code?: string) =>
    Promise.resolve(code ? (byCode[code] ?? { open: false, cohort_name: '', choices: [] }) : bare))
}
/** The gate: `byCode[code]` for a coded question, `bare` for a bare one. */
function serveGate(bare: object, byCode: Record<string, object> = {}) {
  gate.mockImplementation((code: string) => Promise.resolve(code ? (byCode[code] ?? ALLOWED) : bare))
}

const profile = { ...sandboxProfileSpm, results_held: 'spm', nric: '080101-14-1234', nric_verified: true }
const mountAs = (status: string) => render(
  <AuthContext.Provider value={{
    status, profile: status === 'ready' ? profile : null, token: status === 'ready' ? 'tkn' : null,
    showAuthGate: () => {},
  } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)
const formShown = () => screen.findAllByText('scholarship.apply.section.results')

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

/** Signed in, a complete form restored, the last tab, Submit pressed. */
async function submitComplete() {
  stashApplyForm(complete)
  mountAs('ready')
  await screen.findByTestId('apply-gift-line')
  fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
  })
  await waitFor(() => expect(submit).toHaveBeenCalled())
}
const refusal = (status: number, bodyCode = '') =>
  Object.assign(new Error(`API error: ${status}`), { status, code: '', bodyCode })

beforeEach(() => {
  jest.clearAllMocks()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/scholarship/apply')
  serveIntake(ONE_OPEN, { sabah: SABAH_OPEN, bp: ONE_OPEN })
  serveGate(ALLOWED)
})

describe('FIRST STATE FIRST — a signed-out visitor is never asked the gate', () => {
  it('signed out, bare: the page as before (the gift, the sign-in gate) — no gate request', async () => {
    mountAs('anonymous')
    expect(await screen.findByText('scholarship.apply.signInButton')).toBeTruthy()
    expect(gate).not.toHaveBeenCalled()
    expect(mockRouter.replace).not.toHaveBeenCalledWith('/scholarship/application')
  })

  it('signed out, coded: that gift and the sign-in gate — no gate request', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    mountAs('anonymous')
    expect(await screen.findByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    expect(screen.getByText('scholarship.apply.signInButton')).toBeTruthy()
    expect(gate).not.toHaveBeenCalled()
  })

  it('needs-nric is not signed in for the gate either', async () => {
    mountAs('needs-nric')
    expect(await screen.findByText('scholarship.apply.signInButton')).toBeTruthy()
    expect(gate).not.toHaveBeenCalled()
  })
})

describe('signed in — the page obeys the served verdict', () => {
  it('allowed → the form, asked with the URL code', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    mountAs('ready')
    await formShown()
    expect(gate).toHaveBeenCalledWith('sabah', { token: 'tkn' })
    expect(screen.queryByTestId('apply-already-applied')).toBeNull()
  })

  it('application_in_progress → sent to her application; the form never draws', async () => {
    serveGate(IN_PROGRESS)
    mountAs('ready')
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
    expect(screen.queryAllByText('scholarship.apply.section.results')).toHaveLength(0)
    expect(screen.getByText('scholarship.apply.loading')).toBeTruthy()
  })

  it('already_applied → a card on THIS page, linking to her application — no bounce, no form', async () => {
    serveGate(ALREADY)
    mountAs('ready')
    expect(await screen.findByTestId('apply-already-applied')).toBeTruthy()
    expect(screen.getByText('scholarship.apply.alreadyApplied')).toBeTruthy()
    expect(screen.getByText(/scholarship\.application\.title/).closest('a')?.getAttribute('href'))
      .toBe('/scholarship/application')
    expect(screen.queryAllByText('scholarship.apply.section.results')).toHaveLength(0)
    expect(mockRouter.replace).not.toHaveBeenCalledWith('/scholarship/application')
    // one gift open: nothing else to offer
    expect(screen.queryByTestId('apply-already-others')).toBeNull()
  })

  it('already_applied with another gift open → the opt-in "See programmes that are open" → the chooser', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    serveGate(ALLOWED, { sabah: ALREADY })
    mountAs('ready')
    fireEvent.click(await screen.findByTestId('apply-already-others'))
    expect(await screen.findByText('scholarship.apply.chooseTitle')).toBeTruthy()
    expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/apply')
    expect(gate).toHaveBeenLastCalledWith('', { token: 'tkn' })        // re-asked for the bare page
  })

  it('the gate request FAILS → the form (the server still refuses at submit)', async () => {
    gate.mockRejectedValue(new Error('network'))
    mountAs('ready')
    await formShown()
    expect(mockRouter.replace).not.toHaveBeenCalledWith('/scholarship/application')
  })

  it('loading until the gate answers — no flash of the form', async () => {
    let answer: (v: object) => void = () => {}
    gate.mockImplementation(() => new Promise((r) => { answer = r }))
    mountAs('ready')
    await waitFor(() => expect(gate).toHaveBeenCalled())
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('scholarship.apply.loading')).toBeTruthy()
    expect(screen.queryAllByText('scholarship.apply.section.results')).toHaveLength(0)
    await act(async () => { answer(ALLOWED) })
    await formShown()
  })

  it('a pick re-asks for THAT gift — and a gift she is in progress with sends her away', async () => {
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    serveGate(ALLOWED, { sabah: IN_PROGRESS })
    mountAs('ready')
    await screen.findByText('scholarship.apply.chooseTitle')
    expect(gate).toHaveBeenCalledWith('', { token: 'tkn' })
    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    await waitFor(() => expect(gate).toHaveBeenCalledWith('sabah', { token: 'tkn' }))
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
  })

  it('a pick re-asks — already applied to that one this year → the card', async () => {
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
    serveGate(ALLOWED, { sabah: ALREADY })
    mountAs('ready')
    await screen.findByText('scholarship.apply.chooseTitle')
    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    expect(await screen.findByTestId('apply-already-applied')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
  })

  it('END TO END: finished in gift A, applying to gift B — the form, and submit sends B', async () => {
    // What the server answers for her: in A (bp) she already applied this year; B (sabah) is open
    // to her because a FINISHED application never blocks another programme.
    serveIntake(TWO_OPEN, { sabah: SABAH_OPEN, bp: ONE_OPEN })
    serveGate(ALLOWED, { bp: ALREADY, sabah: ALLOWED })
    stashApplyForm(complete)
    mountAs('ready')
    await screen.findByText('scholarship.apply.chooseTitle')
    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))
    expect((await screen.findByTestId('apply-gift-line')).textContent).toContain(SABAH)
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    await waitFor(() => expect(submit).toHaveBeenCalled())
    expect(submit.mock.calls[0][0].programme_code).toBe('sabah')
    expect(mockRouter.replace).toHaveBeenLastCalledWith('/scholarship/application')   // filed: her page
  })
})

describe('round 2 — closed is the normal state: ONE redirect, decided once intake and gate have answered', () => {
  const CLOSED = { ...SABAH_OPEN, open: false, cohort_name: '', programme_code: '' }
  const NOTHING_OPEN = { open: false, cohort_name: '', programme_code: '', choices: [] }
  /** The gate answers LATER than the intake — the race the page used to lose to `/scholarship`. */
  const slowGate = (answer: object) => gate.mockImplementation(
    () => new Promise((r) => { setTimeout(() => r(answer), 20) }))
  const leftOnce = async (to: string) => {
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalled())
    await act(async () => { await new Promise((r) => setTimeout(r, 40)) })
    expect(mockRouter.replace.mock.calls).toEqual([[to]])
  }

  it('(a) in progress, on her CLOSED gift\'s link → her application, never the closed card', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(NOTHING_OPEN, { sabah: CLOSED })
    slowGate(IN_PROGRESS)
    mountAs('ready')
    await leftOnce('/scholarship/application')
    expect(gate).toHaveBeenCalledWith('sabah', { token: 'tkn' })
    expect(mockClosedRenders).not.toHaveBeenCalled()
    expect(screen.queryByTestId('apply-gift-closed')).toBeNull()
  })

  it('(b) in progress, a BARE visit with nothing open → her application, never the landing', async () => {
    serveIntake(NOTHING_OPEN)
    slowGate(IN_PROGRESS)
    mountAs('ready')
    await leftOnce('/scholarship/application')
    expect(gate).toHaveBeenCalledWith('', { token: 'tkn' })
    expect(mockClosedRenders).not.toHaveBeenCalled()
  })

  it('(c) in progress, a BARE visit with one other gift of her organisation open → her application', async () => {
    serveIntake(ONE_OPEN)
    slowGate(IN_PROGRESS)
    mountAs('ready')
    await leftOnce('/scholarship/application')
    expect(screen.queryAllByText('scholarship.apply.section.results')).toHaveLength(0)
    expect(mockClosedRenders).not.toHaveBeenCalled()
  })

  it('a FINISHED student on her closed gift\'s link → the closed card, no redirect', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    serveIntake(NOTHING_OPEN, { sabah: CLOSED })
    slowGate(ALLOWED)
    mountAs('ready')
    expect(await screen.findByTestId('apply-gift-closed')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    await act(async () => { await new Promise((r) => setTimeout(r, 40)) })
    expect(mockRouter.replace).not.toHaveBeenCalled()
  })

  it('signed in, nothing in progress, a bare visit with nothing open → the landing, once — AFTER the gate', async () => {
    serveIntake(NOTHING_OPEN)
    // The gate is HELD until the test releases it — never a timing window. (A 5 ms wait against a
    // 20 ms gate raced under full-suite load: the gate had already answered. 2026-10-06.)
    let release: (answer: object) => void = () => {}
    gate.mockImplementation(() => new Promise((r) => { release = r }))
    mountAs('ready')
    await waitFor(() => expect(gate).toHaveBeenCalled())
    await act(async () => { await new Promise((r) => setTimeout(r, 40)) })
    expect(mockRouter.replace).not.toHaveBeenCalled()        // intake settled; the gate has not
    await act(async () => { release(ALLOWED) })
    await leftOnce('/scholarship')
  })

  it('signed out, a bare visit with nothing open → the landing, once, the gate never asked', async () => {
    serveIntake(NOTHING_OPEN)
    mountAs('anonymous')
    await leftOnce('/scholarship')
    expect(gate).not.toHaveBeenCalled()
  })
})

describe('a refused submit (TD-337 codes, and TD-340)', () => {
  it('409 application_in_progress → sent to her application', async () => {
    submit.mockRejectedValueOnce(refusal(409, 'application_in_progress'))
    await submitComplete()
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
    expect(intake).toHaveBeenCalledTimes(1)          // not mistaken for a closed gift: no re-ask
  })

  it('409 already_applied → the already-applied card, not an error', async () => {
    submit.mockRejectedValueOnce(refusal(409, 'already_applied'))
    await submitComplete()
    expect(await screen.findByTestId('apply-already-applied')).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.error.generic')).toBeNull()
  })

  it('TD-340: a 500 at submit STAYS on screen — across a tab change — until she edits something', async () => {
    submit.mockRejectedValueOnce(refusal(500))
    await submitComplete()
    expect(await screen.findByText('scholarship.apply.error.generic')).toBeTruthy()
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('scholarship.apply.error.generic')).toBeTruthy()

    fireEvent.click(screen.getByText('scholarship.apply.tab.personal').closest('button') as HTMLButtonElement)
    expect(screen.getByText('scholarship.apply.error.generic')).toBeTruthy()

    fireEvent.change(screen.getByDisplayValue('Priya'), { target: { value: 'Priya D' } })
    await waitFor(() => expect(screen.queryByText('scholarship.apply.error.generic')).toBeNull())
  })

  it('TD-340: a resubmit clears the old refusal before asking again', async () => {
    submit.mockRejectedValueOnce(refusal(500))
    await submitComplete()
    expect(await screen.findByText('scholarship.apply.error.generic')).toBeTruthy()
    submit.mockImplementationOnce(() => new Promise(() => {}))        // the second try hangs
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    expect(screen.getByRole('button', { name: 'scholarship.apply.submitting' })).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.error.generic')).toBeNull()
  })

  it('TD-340: a field rejected for length names the field and stays', async () => {
    submit.mockRejectedValueOnce(Object.assign(refusal(400), { fieldErrors: { anything_else: ['Too long.'] } }))
    await submitComplete()
    expect(await screen.findByText('scholarship.apply.error.tooLong')).toBeTruthy()
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('scholarship.apply.error.tooLong')).toBeTruthy()
  })

  it('TD-340: an NRIC already taken (a server answer) stays on the About Me tab', async () => {
    claim.mockResolvedValueOnce({ status: 'exists' })
    const unverified = { ...profile, nric_verified: false, nric: '080101-14-9999' }
    stashApplyForm(complete)
    render(
      <AuthContext.Provider value={{ status: 'ready', profile: unverified, token: 'tkn', showAuthGate: () => {} } as never}>
        <ScholarshipApplyPage />
      </AuthContext.Provider>,
    )
    await screen.findByTestId('apply-gift-line')
    fireEvent.click(screen.getByText('scholarship.apply.tab.support').closest('button') as HTMLButtonElement)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'scholarship.apply.submit' }))
    })
    expect(await screen.findByText('scholarship.apply.error.nricTaken')).toBeTruthy()
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText('scholarship.apply.error.nricTaken')).toBeTruthy()
    expect(submit).not.toHaveBeenCalled()
  })
})
