/**
 * @jest-environment jsdom
 *
 * The Applications list, rendered (owner's item 3 — the gift switcher).
 *
 * ⚠ THE HEADING WAS ACTIVELY WRONG, AND THAT IS WHY IT IS TESTED FIRST. `admin.scholarship.title`
 * is `'{programmeName} Applicants'`, and `programmeName` is one of the five BRANDING auto-tokens
 * `t()` injects — the tenant's flagship name, never the selected gift. So it read "BrightPath
 * Bursary Applicants" while the breadcrumb said Test Programme, over 143 people who were not Test
 * Programme's. A rendered test is the only thing that can see it: the string is right, the wiring
 * was not.
 *
 * ⚠ AND THE SWITCHER MUST REACH THE ENDPOINT. Both halves are asserted from the outside — what the
 * heading SAYS, and what the request CARRIES — because a fix to one without the other leaves the
 * console still describing one gift while listing another's students.
 */
import { render, screen, waitFor } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
// Re-pointed per test, so the page's own role guard can be exercised from the outside.
let authRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: authRole }),
}))
jest.mock('@/lib/admin-api')

// The breadcrumb's chosen gift. Re-pointed per test — the page reads the same context the crumb
// does, which is the whole reason the two can never disagree about which gift is open.
let scope: { chosen: string; programme: { code: string; name: string } | null } =
  { chosen: '', programme: null }
jest.mock('@/lib/programmeScope', () => ({
  useProgrammeScope: () => scope,
}))

const mockApi = api as jest.Mocked<typeof api>

const EMPTY_LIST: api.AdminScholarshipListData = {
  count: 0, total_count: 0, total_pages: 1, page: 1, page_size: 25,
  next: null, previous: null, applications: [],
}

beforeEach(() => {
  jest.clearAllMocks()
  authRole = { role: 'org_admin' }
  scope = { chosen: '', programme: null }
  mockApi.getScholarshipApplications.mockResolvedValue(EMPTY_LIST)
  mockApi.getAssignableAdmins.mockResolvedValue({ admins: [], past_assignees: [] })
})

const heading = () => screen.getByRole('heading', { level: 1 }).textContent

describe('the heading names the gift you are looking at', () => {
  it('names the SELECTED gift, not the tenant brand', async () => {
    scope = { chosen: 'bp-sabah', programme: { code: 'bp-sabah', name: 'Test Programme' } }
    render(<AdminScholarshipList />)
    // The explicit param shadows the branding auto-token, so one string serves both and the
    // ms/ta translations need no new key.
    await waitFor(() => expect(heading()).toBe('admin.scholarship.title|Test Programme'))
  })

  it('drops to a neutral heading when no gift is chosen', async () => {
    // ⚠ Several gifts and none chosen is a REAL state. The heading must not name one — that is
    // the defect — and must not read as an error, because listing every gift is a useful answer.
    render(<AdminScholarshipList />)
    await waitFor(() => expect(heading()).toBe('admin.scholarship.titleAll'))
  })
})

describe('the switcher reaches the endpoint', () => {
  it('sends the chosen gift so the server can narrow the list', async () => {
    scope = { chosen: 'bp-sabah', programme: { code: 'bp-sabah', name: 'Test Programme' } }
    render(<AdminScholarshipList />)
    await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
    expect(mockApi.getScholarshipApplications.mock.calls[0][0])
      .toEqual(expect.objectContaining({ programme: 'bp-sabah' }))
  })

  it('sends NO gift when none is chosen, and that lists every gift', async () => {
    // ⚠ Undefined, never an empty string: the server treats a blank the same way, but sending
    // nothing is what says "no narrowing was asked for" rather than "narrow to nothing".
    render(<AdminScholarshipList />)
    await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
    // The filters argument is optional on the client, so prove it was passed BEFORE reading it —
    // an optional chain alone would pass vacuously if the call carried no filters at all.
    const [filters] = mockApi.getScholarshipApplications.mock.calls[0]
    expect(filters).toBeDefined()
    expect(filters?.programme).toBeUndefined()
  })
})

/*
 * ⚠ THIS PAGE HAD NO ROLE GUARD, AND A REAL ROLE WAS BEING ROUTED HERE (2026-09-08).
 *
 * The registry omits `finance` from `applications` deliberately — `_b40_scope` is 'none', so every
 * call it makes here can only 403 — yet the old landing rule sent finance to `/admin`, which
 * bounced it straight to this page. Their first screen after signing in was a list built for
 * somebody else, failing silently. `defaultRoute` is the real fix; this is the second line of it.
 */
describe('the page refuses a role the registry never gave it', () => {
  it('shows a refusal to finance and asks the server for nothing', async () => {
    authRole = { role: 'finance' }
    render(<AdminScholarshipList />)
    expect(screen.queryByRole('heading', { level: 1 })).toBeNull()
    await waitFor(() => expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy())
    // ⚠ NOT MERELY HIDDEN. A guard that renders a refusal while still fetching would put a 403 in
    // the console and a wasted round trip on the wire every time somebody lands here.
    expect(mockApi.getScholarshipApplications).not.toHaveBeenCalled()
  })

  it('still lets every role the registry DOES list through', async () => {
    for (const role of ['super', 'org_admin', 'admin', 'qc', 'reviewer']) {
      authRole = { role }
      const { unmount } = render(<AdminScholarshipList />)
      await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeTruthy())
      unmount()
    }
  })
})
