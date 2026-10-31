/**
 * @jest-environment jsdom
 *
 * ⚠ A SOURCE USER'S PAGES NEVER CALL A STAFF ENDPOINT (source sign-in, 2026-10-30).
 *
 * The server refuses a source user every staff view (deny by default, S1), so a staff fetch from a
 * source screen is at best a 403 in the console and at worst a page that waits for ever. Each of the
 * seven console pages a source can open is rendered here AS A SOURCE USER with the whole admin API
 * mocked, and every function it holds that is NOT a source-console call must stay uncalled — while
 * the page's own `admin/source/` read must have happened (so the test cannot pass by rendering
 * nothing). A new staff hook placed above a page's role branch fails this.
 */
import { render, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import { AGREEMENT, APPLICATIONS, LISTED, ME, OVERVIEW, PROFILE, SCHOLAR, SCHOLARS } from './testFixtures'
import OverviewPage from '@/app/admin/programme/overview/page'
import ApplicationsPage from '@/app/admin/scholarship/page'
import StudentPage from '@/app/admin/scholarship/[id]/page'
import ScholarsPage from '@/app/admin/scholars/page'
import ScholarPage from '@/app/admin/scholars/[id]/page'
import ProfilePage from '@/app/admin/profile/page'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', refreshRole: jest.fn(),
                         role: { role: 'source_partner', is_admin: true, is_super_admin: false,
                                 source_id: 3, source_name: 'MUETMyWay', admin_name: 'Audrey',
                                 permissions: [] } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useParams: () => ({ id: '104' }),
  usePathname: () => '/admin',
  useSearchParams: () => new URLSearchParams(),
}))
jest.mock('@/lib/useGiftInUrl', () => ({ useGiftInUrl: () => true }))
jest.mock('@/lib/programmeScope', () => ({
  useProgrammeParam: () => 'flag',
  useProgrammeScope: () => ({ chosen: 'flag', programme: null, choices: [], select: () => {} }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

/** The ONLY calls a source page may make: `lib/admin-api/sourceConsole`, plus `getAdminMe` and
 *  `changeOwnPassword` (`admin/me/` GET and `admin/me/password/` POST, opted in for a source user —
 *  common profile S1, the shared Profile page). */
const SOURCE_CALLS = new Set([
  'getSourceProfile', 'updateSourceProfile', 'getSourceOverview', 'getSourceApplications',
  'getSourceApplication', 'getSourceAgreement', 'witnessAsSource', 'getSourceScholars', 'getSourceScholar',
  'getAdminMe', 'changeOwnPassword',
])

beforeEach(() => {
  jest.clearAllMocks()
  global.fetch = jest.fn(() => Promise.reject(new Error('no raw fetch from a source page'))) as unknown as typeof fetch
  mockApi.getSourceOverview.mockResolvedValue(OVERVIEW)
  mockApi.getSourceApplications.mockResolvedValue(APPLICATIONS)
  mockApi.getSourceApplication.mockResolvedValue(LISTED)
  mockApi.getSourceAgreement.mockResolvedValue(AGREEMENT)
  mockApi.getSourceScholars.mockResolvedValue(SCHOLARS)
  mockApi.getSourceScholar.mockResolvedValue(SCHOLAR)
  mockApi.getSourceProfile.mockResolvedValue(PROFILE)
  mockApi.getAdminMe.mockResolvedValue(ME)
})

const staffCalls = () => Object.entries(mockApi)
  .filter(([name, fn]) => !SOURCE_CALLS.has(name) && jest.isMockFunction(fn) && fn.mock.calls.length > 0)
  .map(([name]) => name)

it.each([
  ['Overview', OverviewPage, 'getSourceOverview'],
  ['Applications', ApplicationsPage, 'getSourceApplications'],
  ['one student', StudentPage, 'getSourceApplication'],
  ['Scholars', ScholarsPage, 'getSourceScholars'],
  ['one scholar', ScholarPage, 'getSourceScholar'],
  ['Profile', ProfilePage, 'getSourceProfile'],
] as const)('%s calls only admin/source/', async (_name, Page, own) => {
  render(<Page />)
  await waitFor(() => expect(mockApi[own]).toHaveBeenCalled())
  // Let any late effect run before judging.
  await new Promise((r) => setTimeout(r, 50))
  expect(staffCalls()).toEqual([])
  expect(global.fetch).not.toHaveBeenCalled()
})

it('the shared Profile shell renders every card a source is shown, and still calls only its allowlist', async () => {
  const { findByTestId } = render(<ProfilePage />)
  // Every card of the source's matrix has MOUNTED (each is a lazy chunk), so a staff call placed in
  // any of them would have run before this is judged.
  for (const id of ['you', 'access', 'organisation', 'signin']) await findByTestId(`profile-card-${id}`)
  await waitFor(() => expect(mockApi.getAdminMe).toHaveBeenCalled())
  await new Promise((r) => setTimeout(r, 50))
  expect(staffCalls()).toEqual([])
  expect(global.fetch).not.toHaveBeenCalled()
})

it('the witness step (one student, ?step=witness) calls only admin/source/', async () => {
  window.history.replaceState(null, '', '/admin/scholarship/104?step=witness')
  try {
    render(<StudentPage />)
    await waitFor(() => expect(mockApi.getSourceAgreement).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 50))
    expect(staffCalls()).toEqual([])
    expect(global.fetch).not.toHaveBeenCalled()
  } finally { window.history.replaceState(null, '', '/') }
})
