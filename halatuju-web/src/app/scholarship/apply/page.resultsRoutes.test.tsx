/**
 * @jest-environment jsdom
 *
 * TD-773: Step 3 ("My Results") says what the gift does with the results it holds, from the
 * intake's `results_routes` (read from the criteria tree the gate reads; display only):
 *  * A - a gift that needs post-SPM results, an SPM-only holder: a caution box under the card;
 *  * B - a gift that judges each student on their own results, a post-SPM holder: a small hint
 *    (the PNGK for STPM, the overall CGPA for Matriculation / Asasi / Diploma).
 * Neither blocks Continue. And D: "Results wrong? Edit them" clears a stale profile return first,
 * so the results editors come back HERE, not to wherever an older detour pointed.
 *
 * `t` echoes its key, so assertions read against i18n keys.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm, sandboxProfileStpm } from '@/sandbox/fixtures/scholarship'
import { getScholarshipIntake } from '@/lib/api'
import { ONBOARDING_RETURN_KEY } from '@/lib/scholarship'

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
  getPathwayOfferings: jest.fn((p: string) => Promise.resolve({ pathway: p, institutions: [], courses: [] })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const SPM = { ...sandboxProfileSpm, results_held: 'spm' }
const STPM = { ...sandboxProfileStpm, results_held: 'stpm' }
const third = (kind: 'matric' | 'asasi' | 'diploma') => ({
  ...sandboxProfileSpm, exam_type: kind, results_exam_type: kind, results_held: kind, higher_cgpa: 3.5,
  higher_koko: kind === 'diploma' ? null : 8, completed_qualifications: ['spm', kind], overall_cgpa: 3.47,
})
const NO_RESULTS = { ...sandboxProfileSpm, grades: {}, results_held: null }

const WARN = 'documentsTab.resultsNote.postSpmTitle'
const PNGK = 'documentsTab.resultsNote.pngkOnly'
const CGPA = 'documentsTab.resultsNote.cgpaOnly'

const openResults = async (profile: Record<string, unknown>, routes: string | null | undefined) => {
  (getScholarshipIntake as jest.Mock).mockResolvedValue(
    routes === undefined ? { open: true, choices: [] } : { open: true, choices: [], results_routes: routes })
  render(
    <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
      <ScholarshipApplyPage />
    </AuthContext.Provider>,
  )
  const tabs = await screen.findAllByText('scholarship.apply.section.results')
  fireEvent.click(tabs[0].closest('button') as HTMLButtonElement)
  await screen.findByText(/^3\. scholarship\.apply\.section\.results$/)
}

/** The lazy note has had every chance to arrive: a note that is not here now is not coming. */
const settle = () => new Promise((r) => setTimeout(r, 0))
const noNotes = async () => {
  await settle()
  for (const k of [WARN, PNGK, CGPA]) expect(screen.queryByText(k)).toBeNull()
}

beforeEach(() => {
  mockRouter.push.mockClear()
  sessionStorage.clear()
  localStorage.clear()
})

describe('A: a gift that needs post-SPM results', () => {
  it('warns an SPM-only holder under the card, and Continue still works', async () => {
    await openResults(SPM, 'post_spm')
    expect(await screen.findByText(WARN)).toBeTruthy()
    expect(screen.getByText('documentsTab.resultsNote.postSpmBody')).toBeTruthy()
    expect(screen.getByText('documentsTab.resultsNote.postSpmAdd')).toBeTruthy()
    expect(screen.queryByText(PNGK)).toBeNull()
    // No button of its own, and the footer's Continue stays live (the note feeds no form check).
    const box = screen.getByText(WARN).closest('[data-results-note]') as HTMLElement
    expect(box.querySelector('button')).toBeNull()
    expect((screen.getByRole('button', { name: 'scholarship.apply.continue' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it.each([['STPM', STPM], ['Matriculation', third('matric')], ['Asasi', third('asasi')], ['Diploma', third('diploma')]])(
    'says nothing to a %s holder', async (_n, profile) => {
      await openResults(profile, 'post_spm')
      await noNotes()
    })

  it('says nothing to a student with no results yet (the card already asks for them)', async () => {
    await openResults(NO_RESULTS, 'post_spm')
    expect(screen.getByText('scholarship.apply.noResultsTitle')).toBeTruthy()
    await noNotes()
  })
})

describe('B: a gift that judges each student on their own results', () => {
  it('tells an STPM holder only the PNGK counts', async () => {
    await openResults(STPM, 'both')
    expect(await screen.findByText(PNGK)).toBeTruthy()
    expect(screen.queryByText(WARN)).toBeNull()
  })

  it.each(['matric', 'asasi', 'diploma'] as const)('tells a %s holder only the overall CGPA counts', async (kind) => {
    await openResults(third(kind), 'both')
    expect(await screen.findByText(CGPA)).toBeTruthy()
    expect(screen.queryByText(PNGK)).toBeNull()
  })

  it('says nothing to an SPM holder', async () => {
    await openResults(SPM, 'both')
    await noNotes()
  })
})

describe('every other answer shows no note', () => {
  it.each([
    ['spm', SPM], ['spm', STPM], ['either', SPM], ['either', STPM], ['either', third('matric')],
    [null, SPM], [null, STPM], [undefined, SPM], [undefined, STPM],
  ] as const)('results_routes %s', async (routes, profile) => {
    await openResults(profile, routes)
    await noNotes()
  })
})

describe('D: "Results wrong? Edit them" comes back to this form', () => {
  it('clears a stale profile return before it sets its own, then goes to the results editor', async () => {
    sessionStorage.setItem(ONBOARDING_RETURN_KEY, '/profile')
    await openResults(SPM, 'spm')
    fireEvent.click(screen.getByText('scholarship.apply.resultsWrong'))
    expect(sessionStorage.getItem(ONBOARDING_RETURN_KEY)).toBeNull()
    await waitFor(() => expect(mockRouter.push).toHaveBeenCalledWith('/onboarding/exam-type'))
  })
})
