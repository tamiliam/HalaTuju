/**
 * @jest-environment jsdom
 *
 * TD-623 (owner 2026-11-15, "permissions determine what the admin views and edits"): the Applications list's
 * assignee filter follows the SERVED keys — whoever reads every application (`students.view`, the server's
 * `b40_scope` 'all') or assigns (the `assign` door) — never the role label. The keys are what `GET admin/role/`
 * serves each preset (`test/staffPresets.servedPageKeys`).
 */
import { render, screen, waitFor } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS } from '@/test/giftScope'
import { openAt } from '@/test/giftUrl'
import { servedPageKeys } from '@/test/staffPresets'

let mockRole: Record<string, unknown> = { role: 'admin' }
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  // NAVKEYS: the served permissions open the page (Applications asks see_all/qc/review); each case sets its own page_keys.
  useAdminAuth: () => ({ token: 'tok', role: { permissions: jest.requireActual('@/test/staffPresets').servedPermissions(mockRole.role), ...mockRole } }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const empty = {
  count: 0, total_count: 0, total_pages: 1, page: 1, page_size: 25, next: null, previous: null, applications: [],
} as unknown as api.AdminScholarshipListData

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarshipApplications.mockResolvedValue(empty)
  mockApi.getAssignableAdmins.mockResolvedValue({ admins: [], past_assignees: [] })
  mockApi.getSourceNames.mockResolvedValue({ sources: [] })
})

const filterShown = async (role: Record<string, unknown>) => {
  mockRole = role
  openAt('/admin/scholarship')
  const view = render(<GiftScope choices={TWO_GIFTS} settled><AdminScholarshipList /></GiftScope>)
  await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
  const shown = !!screen.queryByLabelText('admin.scholarship.allAssignees')
  view.unmount()
  return shown
}

describe('TD-623: the assignee filter reads the served keys, not the role', () => {
  it.each([
    ['super', true],
    ['org_admin', true],
    ['admin', true],      // students.view (its see_all)
    ['qc', true],         // students.view (qc reads every application) — gained: the old rule asked role 'admin'
    ['reviewer', false],  // its list is already its own assigned applicants (finance cannot open the page at all)
  ])('%s on its served keys: shown = %s', async (role, expected) => {
    expect(await filterShown({ role, is_super_admin: role === 'super', page_keys: servedPageKeys(role) }))
      .toBe(expected)
  })

  it('an admin label with no keys sees no filter (the old role arm is gone)', async () => {
    expect(await filterShown({ role: 'admin', page_keys: [] })).toBe(false)
    expect(await filterShown({ role: 'admin' })).toBe(false)
  })

  it('a reviewer label given students.view sees it (the key decides)', async () => {
    expect(await filterShown({ role: 'reviewer', page_keys: ['students.view', 'review'] })).toBe(true)
  })

  it('QC (no assign door) gets the reviewer list in the filter, not only All / Unassigned', async () => {
    mockApi.getAssignableAdmins.mockResolvedValue({
      admins: [{ id: 7, name: 'Balan Reviewer', role: 'reviewer', languages: [], assignable: true }],
      past_assignees: [],
    } as never)
    mockRole = { role: 'qc', page_keys: servedPageKeys('qc') }
    expect(servedPageKeys('qc')).not.toContain('students.edit')   // no assign door: the old load was skipped
    openAt('/admin/scholarship')
    render(<GiftScope choices={TWO_GIFTS} settled><AdminScholarshipList /></GiftScope>)
    await waitFor(() => expect(mockApi.getAssignableAdmins).toHaveBeenCalled())
    const filter = await screen.findByLabelText('admin.scholarship.allAssignees')
    await waitFor(() => expect(filter.querySelector('optgroup[label="admin.scholarship.byReviewer"]')).not.toBeNull())
    expect(Array.from(filter.querySelectorAll('option')).map((o) => o.textContent)).toContain('Balan Reviewer')
  })

  it('a reviewer (no filter, no assign) does not load the reviewer list', async () => {
    expect(await filterShown({ role: 'reviewer', page_keys: servedPageKeys('reviewer') })).toBe(false)
    expect(mockApi.getAssignableAdmins).not.toHaveBeenCalled()
  })
})
