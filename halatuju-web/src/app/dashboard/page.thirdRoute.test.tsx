/**
 * @jest-environment jsdom
 *
 * Third results route S2b, ruling D2 — the course guide for a Matriculation / Asasi / Diploma
 * holder BROWSES every degree programme, says why, and shows NO High / Fair / Low merit band (no
 * entry rules exist for these qualifications). It never runs the SPM eligibility check on the
 * empty SPM grades of this view, and never reads as "no profile". Mounted: the claims are what
 * the page draws and which calls it makes.
 */
import { render, screen, waitFor } from '@testing-library/react'

import DashboardPage from './page'
import { checkEligibility, searchStpmCourses } from '@/lib/api'

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/dashboard',
}))
jest.mock('next/link', () => ({ __esModule: true,
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({
  isAuthenticated: true, token: 'tkn', isAnonymous: false, profile: { higher_cgpa: 3.5 },
  showAuthGate: jest.fn(), refreshProfile: jest.fn(),
}) }))
jest.mock('@/lib/useOnboardingGuard', () => ({
  useOnboardingGuard: () => ({ ready: true, loading: false, needsNric: false }) }))
jest.mock('@/hooks/useCachedResults', () => ({
  useCachedResults: () => ({
    ready: true,
    results: {
      view: 'higher',
      profile: { grades: {}, gender: 'female', nationality: 'malaysian', colorblind: false, disability: false },
      higher: { kind: 'asasi', cgpa: 3.4, spmGrades: { bm: 'A' } },
    },
  }) }))
jest.mock('@/hooks/useSavedCourses', () => ({
  useSavedCourses: () => ({ savedIds: new Set(), toggleSave: jest.fn() }) }))
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: jest.fn() }) }))
const mockUseQuery = jest.fn((opts: { enabled?: boolean; queryFn: () => unknown }) => {
  if (opts.enabled) opts.queryFn()
  return { data: undefined, isLoading: false, error: null }
})
jest.mock('@tanstack/react-query', () => ({ useQuery: (o: never) => mockUseQuery(o) }))
jest.mock('@/lib/api', () => ({ __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getReports: jest.fn(() => Promise.resolve({ reports: [] })),
  checkEligibility: jest.fn(() => Promise.resolve({ eligible_courses: [] })),
  searchStpmCourses: jest.fn(() => Promise.resolve({
    total_count: 2, filters: { universities: [], streams: [] },
    courses: [
      { course_id: 'UM1', course_name: 'Bachelor of Accounting', university: 'UM', stream: 'arts', field: '', min_cgpa: 3, min_muet_band: 3, stpm_req_physics: false, req_interview: false, no_colorblind: false, merit_score: 80 },
      { course_id: 'UKM2', course_name: 'Bachelor of Science', university: 'UKM', stream: 'science', field: '', min_cgpa: 3.5, min_muet_band: 4, stpm_req_physics: true, req_interview: false, no_colorblind: false, merit_score: 95 },
    ],
  })),
}))
const cards: Array<Record<string, unknown>> = []
jest.mock('@/components/CourseCard', () => ({ __esModule: true,
  default: (p: { course: Record<string, unknown> }) => { cards.push(p.course); return <div>{String(p.course.course_name)}</div> } }))
jest.mock('@/components/AppHeader', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/AppFooter', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/ScholarshipBanner', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/PathwayCards', () => ({ __esModule: true, default: () => null }))

beforeEach(() => { cards.length = 0; jest.clearAllMocks() })

it('lists every degree with the plain note, and no merit band on any card', async () => {
  render(<DashboardPage />)
  expect(await screen.findByText('Bachelor of Accounting')).toBeTruthy()
  expect(screen.getByText('Bachelor of Science')).toBeTruthy()
  expect(screen.getByText('dashboard.higherBrowseNote')).toBeTruthy()
  expect(searchStpmCourses).toHaveBeenCalledWith({})
  for (const c of cards) {
    expect(c.merit_label).toBeNull()
    expect(c.merit_cutoff).toBeNull()
    expect(c.student_merit).toBeNull()
  }
  expect(screen.queryByText('dashboard.meritHigh')).toBeNull()
  expect(screen.queryByText('dashboard.noProfile')).toBeNull()
})

it('runs no SPM eligibility check, and edits results on the third-route page', async () => {
  render(<DashboardPage />)
  await screen.findByText('Bachelor of Accounting')
  await waitFor(() => expect(searchStpmCourses).toHaveBeenCalled())
  expect(checkEligibility).not.toHaveBeenCalled()
  expect(screen.getByText('dashboard.editProfile').closest('a')?.getAttribute('href'))
    .toBe('/onboarding/higher-grades')
})
