/**
 * @jest-environment jsdom
 *
 * Request #26, owner ruling B — "Shared phone — call the parent" as a FILTER on the Applications
 * list, offered to super and org_admin only (the roles that see the flag and Record call). The
 * server is the gate (`?parent_call=needed` 403s anyone else); this pins that the chip is offered
 * to the right roles and that pressing it reaches the request.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let authRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: authRole }) }))
jest.mock('@/lib/admin-api')
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/programmeScope', () => ({ useProgrammeScope: () => ({ chosen: '', programme: null }) }))

const mockApi = api as jest.Mocked<typeof api>
const EMPTY: api.AdminScholarshipListData = {
  count: 0, total_count: 0, total_pages: 1, page: 1, page_size: 25,
  next: null, previous: null, applications: [],
}
const chip = () => screen.queryByRole('button', { name: 'admin.scholarship.call.needs' })

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarshipApplications.mockResolvedValue(EMPTY)
  mockApi.getAssignableAdmins.mockResolvedValue({ admins: [], past_assignees: [] })
  mockApi.getSources.mockResolvedValue({ sources: [] })   // the Source filter's names (2026-10-08)
})

it.each([
  [{ role: 'org_admin' }], [{ role: 'super', is_super_admin: true }],
])('is offered to %o and pressing it asks for parent_call=needed', async (role) => {
  authRole = role
  render(<AdminScholarshipList />)
  await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
  fireEvent.click(chip()!)
  await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenLastCalledWith(
    expect.objectContaining({ parentCall: 'needed', page: 1 }), { token: 'tok' }))
  expect(chip()!.getAttribute('aria-pressed')).toBe('true')
})

it.each(['admin', 'reviewer', 'qc'])('is not offered to %s', async (role) => {
  authRole = { role }
  render(<AdminScholarshipList />)
  await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
  expect(chip()).toBeNull()
  expect(mockApi.getScholarshipApplications).toHaveBeenLastCalledWith(
    expect.objectContaining({ parentCall: undefined }), { token: 'tok' })
})
