/**
 * @jest-environment jsdom
 *
 * Request #73 (2026-11-16): the "New note" mark (a dot plus words) by a student's name, on the phone rows AND
 * in the desktop table, from the row's SERVED `new_note`. The server clears it when that person opens the
 * student's notes, so the next read of the list comes back without it and the mark is gone.
 */
import { render, screen, waitFor, within } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    vars ? `${k}|${Object.values(vars).join(',')}` : k }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: jest.requireActual('@/test/staffPresets').servedViewer('org_admin') }) }))
jest.mock('@/lib/admin-api')
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/lib/programmeScope', () => ({ useProgrammeScope: () => ({ chosen: '', programme: null }) }))

const mockApi = api as jest.Mocked<typeof api>
type Row = api.AdminScholarshipListData['applications'][number]
const row = (id: number, extra: Partial<Row> = {}) => ({
  id, name: `Pelajar ${id}`, profile_id: null, cohort_code: 'c', qualification: 'spm', spm_a_count: 6,
  stpm_pngk: null, referral_source: null, merit_score: 80, call_language: '', status: 'interviewing',
  bucket: 'A', shortlist_reason: '', submitted_at: '2026-10-21T00:00:00Z', profile_completed_at: null,
  assigned_to_id: null, assigned_to_name: null, assignable: true, ready_for_assignment: true, ...extra,
}) as Row
const list = (rows: Row[]) => ({
  count: rows.length, total_count: rows.length, total_pages: 1, page: 1, page_size: 25, next: null,
  previous: null, applications: rows,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getAssignableAdmins.mockResolvedValue({ admins: [], past_assignees: [] } as unknown as
    Awaited<ReturnType<typeof api.getAssignableAdmins>>)
  mockApi.getSourceNames.mockResolvedValue({ sources: [] })
})

const MARK = 'admin.scholarship.newNote'

it('shows "New note" by the name of the student with an unseen note, on the phone and on the desktop', async () => {
  mockApi.getScholarshipApplications.mockResolvedValue(list([row(1, { new_note: true }), row(2)]))
  render(<AdminScholarshipList />)
  const phone = await screen.findByTestId('application-cards')
  await waitFor(() => expect(within(phone).getAllByText(/^Pelajar /)).toHaveLength(2))

  const phoneMarks = phone.querySelectorAll('[data-new-note]')
  expect(phoneMarks).toHaveLength(1)
  expect(phoneMarks[0].textContent).toBe(MARK)
  expect(phoneMarks[0].querySelector('[aria-hidden="true"]')).not.toBeNull()   // the dot, beside the words
  expect(within(phone).getByText('Pelajar 1').closest('[data-app-row]')?.contains(phoneMarks[0])).toBe(true)

  const table = screen.getByRole('table')
  const desktopMarks = table.querySelectorAll('[data-new-note]')
  expect(desktopMarks).toHaveLength(1)
  expect(within(table).getByText('Pelajar 1').closest('tr')?.contains(desktopMarks[0])).toBe(true)
  expect(within(table).getByText('Pelajar 2').closest('tr')?.querySelector('[data-new-note]')).toBeNull()
})

it('is gone once the person has opened the notes (the next read of the list serves new_note false)', async () => {
  mockApi.getScholarshipApplications.mockResolvedValue(list([row(1, { new_note: true })]))
  const first = render(<AdminScholarshipList />)
  await waitFor(() => expect(document.querySelectorAll('[data-new-note]')).toHaveLength(2))
  first.unmount()

  mockApi.getScholarshipApplications.mockResolvedValue(list([row(1, { new_note: false })]))
  render(<AdminScholarshipList />)
  const phone = await screen.findByTestId('application-cards')
  await waitFor(() => expect(within(phone).getByText('Pelajar 1')).toBeTruthy())
  expect(document.querySelectorAll('[data-new-note]')).toHaveLength(0)
  expect(screen.queryByText(MARK)).toBeNull()
})
