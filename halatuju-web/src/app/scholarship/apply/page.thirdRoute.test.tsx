/**
 * @jest-environment jsdom
 *
 * Third results route S2b — the apply form for a Matriculation / Asasi / Diploma holder.
 *
 *  - "My Results" names the qualification and shows the SERVER's overall CGPA (`overall_cgpa`),
 *    never an SPM A-count and never "we don't have your results yet".
 *  - "My Plans": a tertiary student picks a degree directly, and for this route the picker is
 *    UNFILTERED (ruling D2: no entry rules exist for these qualifications) — every degree from
 *    `/stpm/search/`, never an STPM eligibility check fed no STPM grades.
 *
 * Mounted, because both claims are about what the page draws and which call it makes. `t` echoes.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileSpm } from '@/sandbox/fixtures/scholarship'
import { checkEligibility, checkStpmEligibility, searchStpmCourses } from '@/lib/api'

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
  searchStpmCourses: jest.fn(() => Promise.resolve({
    total_count: 2, filters: { universities: [], streams: [] },
    courses: [
      { course_id: 'UM1', course_name: 'Bachelor of Accounting', university: 'UM', stream: 'arts', field: '', min_cgpa: 3, min_muet_band: 3, stpm_req_physics: false, req_interview: false, no_colorblind: false, merit_score: 80 },
      { course_id: 'UKM2', course_name: 'Bachelor of Science', university: 'UKM', stream: 'science', field: '', min_cgpa: 3.5, min_muet_band: 4, stpm_req_physics: true, req_interview: false, no_colorblind: false, merit_score: 95 },
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
  (searchStpmCourses as jest.Mock).mockClear()
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
  // Every degree, Bumiputera-only ones included (owner ruling 2026-10-28, Bumi coverage Option A).
  await waitFor(() => expect(searchStpmCourses).toHaveBeenCalledWith({ bumiputera: true }, { token: 'tkn' }))
  expect(checkStpmEligibility).not.toHaveBeenCalled()
  expect(checkEligibility).not.toHaveBeenCalled()
})

it('the decided branch is the degree picker, fed by that list', async () => {
  mount(MATRIC)
  await waitFor(() => expect(searchStpmCourses).toHaveBeenCalled())
  await openTab('scholarship.apply.section.plans', /^4\. scholarship\.apply\.section\.plans$/)
  fireEvent.click(screen.getByText('scholarship.apply.plan.sure').closest('button') as HTMLButtonElement)
  expect(screen.getByText('scholarship.apply.plan.degreeLabel')).toBeTruthy()
  expect(screen.queryByText('scholarship.apply.plan.pathwayLabel')).toBeNull()
})
