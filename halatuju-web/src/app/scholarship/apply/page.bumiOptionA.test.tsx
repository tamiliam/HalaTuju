/**
 * @jest-environment jsdom
 *
 * Owner ruling 2026-10-28 (Bumi coverage, Option A): the apply form's programme picker offers EVERY
 * course — Bumiputera-only ones included — to EVERY student, and never reads the Bumiputera answer.
 * That answer is course-guide only (the s44(6) stance: the bursary does not collect ethnicity); a
 * wrong pick is corrected by the offer letter.
 *
 * Mounted: the claims are about the request the page makes and the list the student can pick from.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ScholarshipApplyPage from './page'
import { AuthContext } from '@/lib/auth-context'
import { sandboxProfileStpm } from '@/sandbox/fixtures/scholarship'
import { checkStpmEligibility } from '@/lib/api'

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
const UITM = {
  course_id: 'UITM-BUMI', course_name: 'Ijazah Sarjana Muda Seni Bina (UiTM)', university: 'UiTM',
  stream: 'arts', field: '', min_cgpa: 3, min_muet_band: 3, stpm_req_physics: false,
  req_interview: false, no_colorblind: false, merit_score: 80,
}
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getScholarshipIntake: jest.fn(() => Promise.resolve({ open: true, choices: [] })),
  getMyScholarshipApplications: jest.fn(() => Promise.resolve({ applications: [] })),
  getApplyGate: jest.fn(() => Promise.resolve({ allowed: true, reason: '', application_id: null })),
  checkEligibility: jest.fn(() => Promise.resolve({ pathway_stats: {}, eligible_courses: [] })),
  calculatePathways: jest.fn(() => Promise.resolve({ pathways: [] })),
  // What the server answers to bumiputera=true: the Bumi-only UiTM course is in the list.
  checkStpmEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [UITM], total_eligible: 1 })),
  searchStpmCourses: jest.fn(() => Promise.resolve({ courses: [], total_count: 0, filters: {} })),
}))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const STPM = { ...sandboxProfileStpm, results_exam_type: 'stpm', results_held: 'stpm', nationality: 'malaysian' }

const mount = (profile: Record<string, unknown>) => render(
  <AuthContext.Provider value={{ status: 'ready', profile, token: 'tkn', showAuthGate: () => {} } as never}>
    <ScholarshipApplyPage />
  </AuthContext.Provider>,
)

beforeEach(() => { (checkStpmEligibility as jest.Mock).mockClear() })

it.each([
  ['answered No', { bumiputera: false }],
  ['never answered', { bumiputera: null }],
  ['an older profile without the field', {}],
])('a student who %s is offered the Bumi-only course in the programme picker', async (_label, answer) => {
  mount({ ...STPM, ...answer })
  await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
  expect((checkStpmEligibility as jest.Mock).mock.calls[0][0].bumiputera).toBe(true)   // include everything

  const tabs = await screen.findAllByText('scholarship.apply.section.plans')
  fireEvent.click(tabs[0].closest('button') as HTMLButtonElement)
  fireEvent.click((await screen.findByText('scholarship.apply.plan.sure')).closest('button') as HTMLButtonElement)
  fireEvent.focus(await screen.findByRole('combobox'))
  expect(await screen.findByText(/Seni Bina \(UiTM\)/)).toBeTruthy()
})

it('never reads the stored Bumiputera answer', async () => {
  const reads: string[] = []
  const profile = new Proxy({ ...STPM, bumiputera: false }, {
    get(target, key, recv) {
      if (key === 'bumiputera') reads.push(new Error().stack ?? '')
      return Reflect.get(target, key, recv)
    },
  })
  mount(profile)
  await waitFor(() => expect(checkStpmEligibility).toHaveBeenCalled())
  expect(reads).toEqual([])
})
