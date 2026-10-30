/**
 * @jest-environment jsdom
 *
 * Third results route S2b — the apply form for a Matriculation / Asasi / Diploma holder.
 *
 *  - "My Results" names the qualification and shows the SERVER's overall CGPA (`overall_cgpa`),
 *    never an SPM A-count and never "we don't have your results yet".
 *  - "My Plans": a tertiary student names a university, then a degree, and for this route the
 *    picker is UNFILTERED (ruling D2: no entry rules exist for these qualifications) — every degree
 *    from the catalogue (`/courses/offerings/?pathway=degree` since 2026-10-30; `/stpm/search/`
 *    before), never an STPM eligibility check fed no STPM grades, and no "Eligible only" switch.
 *
 * Mounted, because both claims are about what the page draws and which call it makes. `t` echoes.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import { checkEligibility, checkStpmEligibility, getPathwayOfferings } from '@/lib/api'

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
  getPathwayOfferings: jest.fn(() => Promise.resolve({
    pathway: 'degree',
    institutions: [
      { id: 'UM', institution_id: 'UM', name: 'Universiti Malaya', state: 'Kuala Lumpur', course_ids: ['UM1'] },
      { id: 'UKM', institution_id: 'UKM', name: 'Universiti Kebangsaan Malaysia', state: 'Selangor', course_ids: ['UKM2'] },
    ],
    courses: [
      { course_id: 'UM1', course_name: 'Bachelor of Accounting', field_key: 'acc', aliran: null },
      { course_id: 'UKM2', course_name: 'Bachelor of Science', field_key: 'sci', aliran: null },
    ],
  })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const MATRIC = {
  ...sandboxProfileSpm, exam_type: 'matric', results_exam_type: 'matric', results_held: 'matric',
  grades: {}, spm_prereq_grades: { bm: 'A', eng: 'A', hist: 'B', math: 'A' },
  higher_cgpa: 3.5, higher_koko: 8, completed_qualifications: ['spm', 'matric'], overall_cgpa: 3.47,
}

const mount = (profile: Record<string, unknown>) => render(
  <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)

const openTab = async (key: string, heading: RegExp) => {
  const tabs = await screen.findAllByText(key)
  fireEvent.click(tabs[0].closest('button') as HTMLButtonElement)
  await screen.findByText(heading)
}

beforeEach(() => {
  (checkEligibility as jest.Mock).mockClear();
  (checkStpmEligibility as jest.Mock).mockClear();
  (getPathwayOfferings as jest.Mock).mockClear()
})

it('My Results names the qualification and shows the served overall CGPA', async () => {
  mount(MATRIC)
  await openTab('scholarship.apply.section.results', /^3\. scholarship\.apply\.section\.results$/)
  expect(screen.getByText('3.47')).toBeTruthy()
  expect(screen.getByText(/onboarding\.higherKind\.matric/)).toBeTruthy()
  expect(screen.queryByText('scholarship.apply.noResultsTitle')).toBeNull()
  expect(screen.queryByText(/scholarship\.apply\.aGradesWord/)).toBeNull()
  expect(screen.queryByText('scholarship.apply.pngkLabel')).toBeNull()      // not an STPM PNGK
})

it.each(['matric', 'asasi', 'diploma'])('My Plans offers a %s holder EVERY degree, unfiltered (D2)', async (kind) => {
  mount({ ...MATRIC, exam_type: kind, results_exam_type: kind, results_held: kind })
  await openTab('scholarship.apply.section.plans', /^4\. scholarship\.apply\.section\.plans$/)
  fireEvent.click((await screen.findByText('scholarship.apply.plan.sure')).closest('button') as HTMLButtonElement)
  // Every degree, Bumiputera-only ones included (Option A) — the catalogue, not a check.
  await waitFor(() => expect(getPathwayOfferings).toHaveBeenCalledWith('degree'))
  expect(checkStpmEligibility).not.toHaveBeenCalled()
  expect(checkEligibility).not.toHaveBeenCalled()
  expect(screen.queryByRole('switch', { name: 'search.eligibleOnly' })).toBeNull()   // no entry rules to narrow by
})

it('the offer branch is University → Degree, fed by that list', async () => {
  mount(MATRIC)
  await openTab('scholarship.apply.section.plans', /^4\. scholarship\.apply\.section\.plans$/)
  fireEvent.click((await screen.findByText('scholarship.apply.plan.sure')).closest('button') as HTMLButtonElement)
  expect(screen.queryByLabelText('scholarship.apply.plan.pathwayLabel')).toBeNull()
  const uni = await screen.findByLabelText('scholarship.apply.plan.institutionLabel.university')
  fireEvent.change(uni, { target: { value: 'UKM' } })
  expect(screen.getByText('scholarship.apply.plan.degreeLabel')).toBeTruthy()
  fireEvent.focus(screen.getByPlaceholderText('scholarship.apply.plan.programmePlaceholder'))
  expect(screen.getByText('Bachelor of Science')).toBeTruthy()
  expect(screen.queryByText('Bachelor of Accounting')).toBeNull()   // UM's, not UKM's
})
