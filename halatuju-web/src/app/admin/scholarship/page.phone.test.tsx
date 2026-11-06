/**
 * @jest-environment jsdom
 *
 * Mobile M6a — the case list on a phone (owner-approved mock-up): rows that open the case as a whole, the
 * filters in the shared Sheet over the SAME state as the desktop row, a Sort select over the SAME server sort
 * the table headers drive, and the Assign control's reasons written out instead of hidden in a tooltip.
 * jsdom has no media queries, so the phone block and the desktop table are both in the DOM; every query
 * here is scoped to the phone block (`application-cards`, `list-phone-tools`) or the Sheet.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }) }))
jest.mock('@/lib/admin-api')
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/programmeScope', () => ({ useProgrammeScope: () => ({ chosen: '', programme: null }) }))

const mockApi = api as jest.Mocked<typeof api>
type Row = api.AdminScholarshipListData['applications'][number]
const row = (id: number, extra: Partial<Row> = {}) => ({
  id, name: `Pelajar ${id}`, profile_id: null, cohort_code: 'c', qualification: 'spm', spm_a_count: 6,
  stpm_pngk: null, referral_source: null, merit_score: 80, call_language: '', status: 'profile_complete',
  bucket: 'A', shortlist_reason: '', submitted_at: '2026-10-21T00:00:00Z', profile_completed_at: null,
  assigned_to_id: null, assigned_to_name: null, assignable: true, ready_for_assignment: true, ...extra,
}) as Row

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarshipApplications.mockResolvedValue({
    count: 3, total_count: 3, total_pages: 1, page: 1, page_size: 25, next: null, previous: null,
    applications: [row(1), row(2, { assignable: false }), row(3, { ready_for_assignment: false })],
  })
  mockApi.getAssignableAdmins.mockResolvedValue({
    admins: [{ id: 7, name: 'Balan', email: 'b@x.invalid', role: 'reviewer', languages: [] }],
    past_assignees: [],
  } as unknown as Awaited<ReturnType<typeof api.getAssignableAdmins>>)
  mockApi.getSourceNames.mockResolvedValue({ sources: [] })
})

const phone = async () => screen.findByTestId('application-cards')
const lastCall = () => mockApi.getScholarshipApplications.mock.calls.at(-1)?.[0]

describe('the case list on a phone (Mobile M6a)', () => {
  it('the WHOLE row opens the case: name, status and merit are inside one link, Assign is outside it', async () => {
    render(<AdminScholarshipList />)
    const list = await phone()
    await waitFor(() => expect(within(list).getAllByText(/^Pelajar /)).toHaveLength(3))
    const link = within(list).getByText('Pelajar 1').closest('a') as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/admin/scholarship/1')
    expect(link.textContent).toContain('admin.scholarship.merit')
    expect(link.querySelector('select')).toBeNull()
    const firstRow = link.closest('[data-app-row]') as HTMLElement
    expect(within(firstRow).getByRole('combobox', { name: 'admin.scholarship.assigned' }).closest('a')).toBeNull()
  })

  it('says WHY an Assign is asleep in words, never in a hover-only title', async () => {
    render(<AdminScholarshipList />)
    const list = await phone()
    await waitFor(() => expect(within(list).getAllByRole('combobox')).toHaveLength(3))
    expect(list.querySelector('[title]')).toBeNull()
    const reasons = Array.from(list.querySelectorAll('[data-assign-reason]')).map((n) => n.textContent)
    expect(reasons).toEqual(['admin.scholarship.assign.error.not_assignable', 'admin.scholarship.assign.error.not_ready'])
  })

  it('an assign that fails shows its reason under the row, as the table does', async () => {
    mockApi.assignApplication.mockRejectedValue(new Error('reviewer_paused'))
    render(<AdminScholarshipList />)
    const list = await phone()
    await waitFor(() => expect(within(list).getAllByRole('combobox')).toHaveLength(3))
    fireEvent.change(within(list).getAllByRole('combobox')[0], { target: { value: '7' } })
    expect(await within(list).findByText('admin.scholarship.assign.error.reviewer_paused')).toBeTruthy()
  })

  it('TD-501: a gift_mismatch refusal says so in words, not the generic error', async () => {
    mockApi.assignApplication.mockRejectedValue(new Error('gift_mismatch'))
    render(<AdminScholarshipList />)
    const list = await phone()
    await waitFor(() => expect(within(list).getAllByRole('combobox')).toHaveLength(3))
    fireEvent.change(within(list).getAllByRole('combobox')[0], { target: { value: '7' } })
    expect(await within(list).findByText('admin.scholarship.assign.error.gift_mismatch')).toBeTruthy()
  })

  it('Sort asks the SERVER for the column and direction the table headers would', async () => {
    render(<AdminScholarshipList />)
    const tools = await screen.findByTestId('list-phone-tools')
    const sort = within(tools).getByRole('combobox', { name: 'admin.scholarship.sortLabel' })
    fireEvent.change(sort, { target: { value: 'merit:desc' } })
    await waitFor(() => expect(lastCall()).toMatchObject({ sort: 'merit', dir: 'desc', page: 1 }))
    fireEvent.change(sort, { target: { value: '' } })
    await waitFor(() => expect(lastCall()?.sort).toBeUndefined())
  })

  it('Filters open the shared Sheet with the SAME controls; a choice there filters the list', async () => {
    render(<AdminScholarshipList />)
    const tools = await screen.findByTestId('list-phone-tools')
    fireEvent.click(within(tools).getByRole('button', { name: 'admin.scholarship.filters' }))
    const sheet = await screen.findByTestId('list-filter-sheet')
    const status = within(sheet).getByRole('combobox', { name: 'admin.scholarship.allStatuses' })
    fireEvent.change(status, { target: { value: 'interviewing' } })
    await waitFor(() => expect(lastCall()).toMatchObject({ status: 'interviewing', page: 1 }))
    // The count of active filters is on the button the next time she looks.
    expect(within(tools).getByRole('button', { name: /admin\.scholarship\.filters/ }).textContent).toContain('1')
  })
})
