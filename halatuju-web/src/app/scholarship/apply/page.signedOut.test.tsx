/**
 * @jest-environment jsdom
 *
 * The apply page's FIRST state — signed out, no parameters — with two gifts open (the owner's live
 * test of the apply-gift-clarity sprint, 2026-10-05).
 *
 * The chooser had been built and tested only for a SIGNED-IN student: the sign-in gate returned
 * before it, so a stranger on a bare `/scholarship/apply` — the most common way anyone arrives — saw
 * the platform default heading and BrightPath-style criteria ("5 A's…") and a sign-in button, with
 * no ask. And on every visit the default heading flashed before the gift's own words replaced it.
 * Now the ask comes first for everyone, and nothing names a gift until the intake has answered.
 *
 * `t` echoes its key, so the platform default reads as `scholarship.apply.title` /
 * `scholarship.apply.criteria1`; gift copy and names are data.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { getApplyGate, getMyScholarshipApplications, getScholarshipIntake } from '@/lib/api'

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
  getApplyGate: jest.fn(),
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
const gate = getApplyGate as jest.Mock
const IN_PROGRESS = { allowed: false, reason: 'application_in_progress', application_id: 1 }

const SABAH = 'BrightPath Bursary, Sabah'
const TWO_OPEN = { open: true, cohort_name: '', programme_code: '', apply_copy: {},
  choices: [{ code: 'bp', name: 'BrightPath Bursary Programme 2026' }, { code: 'sabah', name: SABAH }] }
const SABAH_OPEN = { open: true, cohort_name: SABAH, programme_code: 'sabah', choices: [],
  apply_copy: { en: { title: 'Sabah bursary', intro: 'For students in Sabah.', criteria: ['Live in Sabah'] } } }

function serveIntake(bare: object, byCode: Record<string, object> = {}) {
  intake.mockImplementation((code?: string) =>
    Promise.resolve(code ? (byCode[code] ?? { open: false, cohort_name: '', choices: [] }) : bare))
}

const mountAs = (status: string) => render(
  <AuthContext.Provider value={{ status, profile: null, token: null, showAuthGate: () => {} } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)

beforeEach(() => {
  jest.clearAllMocks()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/scholarship/apply')
  myApps.mockResolvedValue({ applications: [] })
  gate.mockResolvedValue({ allowed: true, reason: '', application_id: null })
  serveIntake(TWO_OPEN, { sabah: SABAH_OPEN })
})

describe('signed out, bare link, two gifts open — the ask comes first', () => {
  it.each(['anonymous', 'needs-nric'])(
    '%s: the chooser IS the page — no default heading, no default criteria, no sign-in button',
    async (status) => {
      mountAs(status)
      await screen.findByText('scholarship.apply.chooseTitle')
      expect(screen.queryByRole('heading', { level: 1 })).toBeNull()
      expect(screen.queryByText('scholarship.apply.title')).toBeNull()
      expect(screen.queryByText('scholarship.apply.criteria1')).toBeNull()
      expect(screen.queryByText('scholarship.apply.signInButton')).toBeNull()
      // never pre-selected
      expect((screen.getByTestId('apply-choose-continue') as HTMLButtonElement).disabled).toBe(true)
      expect(gate).not.toHaveBeenCalled()       // a signed-out visitor is never asked (TD-337)
    },
  )

  it("a pick shows THAT gift's heading and criteria, then the sign-in gate", async () => {
    mountAs('anonymous')
    await screen.findByText('scholarship.apply.chooseTitle')
    fireEvent.click(screen.getByLabelText(SABAH))
    fireEvent.click(screen.getByTestId('apply-choose-continue'))

    expect(await screen.findByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    expect(screen.getByText('Live in Sabah')).toBeTruthy()
    expect(screen.getByText('scholarship.apply.signInButton')).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.criteria1')).toBeNull()
    expect(screen.queryByText('scholarship.apply.chooseTitle')).toBeNull()
    // the pick rides in the URL, so signing in returns to it (applyPagePath)
    expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/apply?p=sabah')
    expect(intake).toHaveBeenCalledWith('sabah')
  })

  it("a gift's own link goes straight to that gift and the gate, as before", async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    mountAs('anonymous')
    expect(await screen.findByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    expect(screen.getByText('scholarship.apply.signInButton')).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.chooseTitle')).toBeNull()
    expect(gate).not.toHaveBeenCalled()
  })
})

describe('a NAMED gift that has closed says so (owner, 2026-10-05) — no silent redirect', () => {
  const CLOSED = { ...SABAH_OPEN, open: false, cohort_name: '', programme_code: '' }
  beforeEach(() => { window.history.replaceState({}, '', '/scholarship/apply?p=sabah') })

  it('signed out: the closed card under the gift\'s own title — no criteria, no sign-in, no redirect', async () => {
    serveIntake(TWO_OPEN, { sabah: CLOSED })
    mountAs('anonymous')
    expect(await screen.findByTestId('apply-gift-closed')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
    expect(screen.getByText('scholarship.landing.closed.btn')).toBeTruthy()
    expect(screen.getByText('scholarship.landing.closed.note')).toBeTruthy()
    expect(screen.getByText('scholarship.landing.closed.continue')).toBeTruthy()
    expect(screen.queryByText('Live in Sabah')).toBeNull()
    expect(screen.queryByText('scholarship.apply.criteria1')).toBeNull()
    expect(screen.queryByText('scholarship.apply.signInButton')).toBeNull()
    expect(mockRouter.replace).not.toHaveBeenCalledWith('/scholarship')
  })

  it('another gift open → ONE opt-in link to the bare page, which then asks (never pre-selected)', async () => {
    serveIntake(TWO_OPEN, { sabah: CLOSED })
    mountAs('anonymous')
    fireEvent.click(await screen.findByTestId('apply-gift-others'))
    expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/apply')
    expect(await screen.findByText('scholarship.apply.chooseTitle')).toBeTruthy()
    expect((screen.getByTestId('apply-choose-continue') as HTMLButtonElement).disabled).toBe(true)
  })

  it('nothing else open → no such link', async () => {
    serveIntake({ open: false, cohort_name: '', programme_code: '', choices: [] }, { sabah: CLOSED })
    mountAs('anonymous')
    expect(await screen.findByTestId('apply-gift-closed')).toBeTruthy()
    await waitFor(() => expect(intake).toHaveBeenCalledWith())
    expect(screen.queryByTestId('apply-gift-others')).toBeNull()
  })

  it('a signed-in applicant on her CLOSED gift\'s link is sent to her application, not the closed card', async () => {
    // The server answers the in-play half with no open round (TD-337 round 2), so this is the real
    // api's answer on her own link: in progress → her application, before the closed card.
    serveIntake(TWO_OPEN, { sabah: CLOSED })
    gate.mockResolvedValue(IN_PROGRESS)
    render(
      <AuthContext.Provider value={{ status: 'ready', profile: null, token: 'tkn', showAuthGate: () => {} } as never}>
        <ScholarshipApplyPage />
      </AuthContext.Provider>,
    )
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
    expect(gate).toHaveBeenCalledWith('sabah', { token: 'tkn' })
    expect(mockRouter.replace.mock.calls).toEqual([['/scholarship/application']])
    expect(screen.queryByTestId('apply-gift-closed')).toBeNull()
  })

  it('a BARE visit with nothing open anywhere still goes to the landing (unchanged), once, unasked', async () => {
    window.history.replaceState({}, '', '/scholarship/apply')
    serveIntake({ open: false, cohort_name: '', programme_code: '', choices: [] })
    mountAs('anonymous')
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship'))
    await act(async () => { await Promise.resolve() })
    expect(mockRouter.replace.mock.calls).toEqual([['/scholarship']])
    expect(gate).not.toHaveBeenCalled()
  })
})

describe('no flash of the wrong gift', () => {
  it('draws the loading state, not the platform default, until the intake answers', async () => {
    window.history.replaceState({}, '', '/scholarship/apply?p=sabah')
    // Hold the CODED question open (the bare "is another gift open?" one answers at once).
    let answer: (v: object) => void = () => {}
    intake.mockImplementation((code?: string) => (code
      ? new Promise((r) => { answer = r })
      : Promise.resolve(TWO_OPEN)))
    mountAs('anonymous')
    await waitFor(() => expect(intake).toHaveBeenCalledWith('sabah'))
    expect(screen.getByText('scholarship.apply.loading')).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.title')).toBeNull()
    expect(screen.queryByText('scholarship.apply.criteria1')).toBeNull()
    expect(screen.queryByText('scholarship.apply.signInButton')).toBeNull()

    answer(SABAH_OPEN)
    expect(await screen.findByRole('heading', { level: 1, name: 'Sabah bursary' })).toBeTruthy()
  })

  it('a FAILED intake settles too — the page as before (platform default and the gate)', async () => {
    intake.mockImplementation(() => Promise.reject(new Error('network')))
    mountAs('anonymous')
    expect(await screen.findByText('scholarship.apply.signInButton')).toBeTruthy()
    expect(screen.getByText('scholarship.apply.title')).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.loading')).toBeNull()
  })

  it('the in-progress bounce is not held back by an unanswered intake', async () => {
    intake.mockImplementation(() => new Promise(() => {}))         // never answers
    gate.mockResolvedValue(IN_PROGRESS)
    render(
      <AuthContext.Provider value={{ status: 'ready', profile: null, token: 'tkn', showAuthGate: () => {} } as never}>
        <ScholarshipApplyPage />
      </AuthContext.Provider>,
    )
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith('/scholarship/application'))
  })
})
