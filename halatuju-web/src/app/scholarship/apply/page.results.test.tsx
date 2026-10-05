/**
 * @jest-environment jsdom
 *
 * TD-218 review F1 — the apply form's "My Results" step reads the SERVER's answer to "which
 * results do we hold?", so it cannot contradict the review card that reads the same answer.
 *
 * The Form Six explorer: she answered STPM at "Choose Your Exam" (the exam she is heading for),
 * holds ten SPM grades, and has no STPM results. The step used to look where the declaration
 * pointed, find no CGPA, and tell her "we don't have your results yet" while her grades sat on
 * file — and, after Now sprint 4 switched the review card, the two screens of one application
 * disagreed. A mount, not a source guard: the claim is what the step DRAWS.
 *
 * `t` echoes its key, so assertions read against i18n keys.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileFormSix, sandboxProfileSpm, sandboxProfileStpm } from '@/sandbox/fixtures/scholarship'
import { checkEligibility, checkStpmEligibility } from '@/lib/api'

// ONE router object: the page's effects depend on it, and a fresh object per render re-runs
// the applications fetch for ever (the page never leaves "loading").
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
  getScholarshipIntake: jest.fn(() => Promise.resolve({ open: true, choices: [] })),
  getMyScholarshipApplications: jest.fn(() => Promise.resolve({ applications: [] })),
  getApplyGate: jest.fn(() => Promise.resolve({ allowed: true, reason: '', application_id: null })),
  checkEligibility: jest.fn(() => Promise.resolve({ pathway_stats: {}, eligible_courses: [] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [] })),
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [] })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const openResults = async (profile: Record<string, unknown>) => {
  render(
    <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
      <ScholarshipApplyPage />
    </AuthContext.Provider>,
  )
  const tabs = await screen.findAllByText('scholarship.apply.section.results')
  fireEvent.click(tabs[0].closest('button') as HTMLButtonElement)
  // the step's own heading ("3. …") is drawn once the tab is active
  await screen.findByText(/^3\. scholarship\.apply\.section\.results$/)
}

describe('the Results step for the Form Six explorer', () => {
  it('shows her SPM results when the server says SPM is what she holds', async () => {
    // What the profile GET serves for her since review F1: declared STPM, held SPM.
    await openResults({ ...sandboxProfileFormSix, results_held: 'spm' })
    expect(screen.getByText(/scholarship\.apply\.aGradesWord/)).toBeTruthy()
    expect(screen.queryByText('scholarship.apply.noResultsTitle')).toBeNull()
    expect(screen.queryByText('scholarship.apply.pngkLabel')).toBeNull()
  })

  it('still says "no results" for an older payload with no served answer (the fallback)', async () => {
    // Pins the fallback as the OLD behaviour, so the served field is what made the difference.
    await openResults({ ...sandboxProfileFormSix })
    expect(screen.getByText('scholarship.apply.noResultsTitle')).toBeTruthy()
  })

  it('leaves an ordinary SPM student exactly as she was', async () => {
    await openResults({ ...sandboxProfileSpm, results_held: 'spm' })
    expect(screen.getByText(/scholarship\.apply\.aGradesWord/)).toBeTruthy()
  })
})

// TD-325 (2026-10-04): the PLANS step picks its branch — the SPM pathway dropdown or the STPM
// degree picker — by the results we HOLD, not the declared exam. Both branches are eligibility
// checks on results, so the explorer was sent to an STPM degree check fed no STPM grades and
// shown an empty picker. Which check the page asks for is what decides the branch.
describe('the Plans step chooses its eligibility check by the results held (TD-325)', () => {
  const mount = (profile: Record<string, unknown>) => render(
    <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
      <ScholarshipApplyPage />
    </AuthContext.Provider>,
  )
  beforeEach(() => {
    (checkEligibility as jest.Mock).mockClear();
    (checkStpmEligibility as jest.Mock).mockClear()
  })

  it('asks the SPM check for the Form Six explorer the server says holds SPM', async () => {
    mount({ ...sandboxProfileFormSix, results_held: 'spm' })
    await waitFor(() => expect(checkEligibility).toHaveBeenCalled())
    expect(checkStpmEligibility).not.toHaveBeenCalled()
  })

  it('asks the STPM degree check for a student who holds STPM results', async () => {
    mount({ ...sandboxProfileStpm, results_held: 'stpm' })
    await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
    expect(checkEligibility).not.toHaveBeenCalled()
  })
})
