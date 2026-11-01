/**
 * @jest-environment jsdom
 *
 * Student maintenance S7d (2026-11-01): a STAFF member may also be a mentor. On Organisation → Mentors:
 * "Add a staff member as mentor" (super / org_admin) opens the shared Sheet with the server's eligible
 * staff — no email; a staff mentor's row says "Staff · <role>" and offers Stop mentoring (Active) or
 * Mentor again (Inactive), never Deactivate / Reactivate; a staff mentor is listed even before they
 * have signed in.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import MentorsAdminScreen from './MentorsAdmin'
import InvitationEmailsCard from '@/components/admin/InvitationEmailsCard'

const MentorsAdmin = () => <MentorsAdminScreen EmailsCard={InvitationEmailsCard} />

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/components/sources/PartnerTemplateEditor', () => () => null)
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (over: Partial<api.MentorRow>): api.MentorRow => ({
  id: 1, name: 'Dr Kavitha Raman', email: 'kavitha@example.org', phone: '', status: 'active',
  area: 'Accounting', languages: { en: 'fluent', ms: '', ta: '' }, other_language: '',
  invited_at: '2026-10-01T00:00:00Z', signed_in: true, last_seen_at: null, deactivated_at: null,
  manageable: true, scholars_now: 4, staff_role: null, ...over,
})
// A staff mentor who has not signed in yet (their sign-in is People's): listed all the same.
const STAFF = row({ id: 5, name: 'Siti Rahmah', email: 'siti@example.org', staff_role: 'org_admin',
  signed_in: false, area: '', scholars_now: 0 })
const STOPPED = row({ id: 6, name: 'Encik Faizal', staff_role: 'reviewer', status: 'inactive',
  deactivated_at: '2026-10-20T00:00:00Z' })

beforeEach(() => {
  jest.clearAllMocks()
  mockRole = { role: 'org_admin' }
  mockApi.getMentors.mockResolvedValue({ mentors: [row({}), STAFF, STOPPED],
    counts: { active: 2, invited: 0, inactive: 1 }, can_invite: true })
  mockApi.getInvitations.mockResolvedValue({ waiting: { mentor: 0 } } as unknown as api.InvitationsPayload)
  mockApi.getStaffMentorCandidates.mockResolvedValue({ staff: [
    { id: 11, name: 'Siti Nur Haliza', email: 'haliza@example.org', role: 'reviewer', organisation: 'BP' },
    { id: 12, name: 'Ravi Kumar', email: 'ravi@example.org', role: 'qc', organisation: 'BP' },
  ] })
  mockApi.addStaffMentor.mockResolvedValue(row({ id: 9, name: 'Ravi Kumar', staff_role: 'qc' }))
  mockApi.mentorAction.mockResolvedValue({ ...row({}), emailed: null })
  window.confirm = jest.fn(() => true)
})

it('tags a staff mentor and gives them Stop mentoring, never Deactivate', async () => {
  render(<MentorsAdmin />)
  const r = await screen.findByTestId('mentor-row-5')
  expect(within(r).getByTestId('mentor-staff-5').textContent)
    .toBe('admin.mentors.staffTag {"role":"admin.role.org_admin"}')
  expect(within(r).getByTestId('mentor-action-5').textContent).toBe('admin.mentors.action.stop')
  expect(within(screen.getByTestId('mentor-row-1')).getByTestId('mentor-action-1').textContent)
    .toBe('admin.mentors.action.deactivate')
  fireEvent.click(within(r).getByTestId('mentor-action-5'))
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(5, 'stop', { token: 'tok' }))
  expect(window.confirm).toHaveBeenCalledWith('admin.mentors.confirm.stop {"name":"Siti Rahmah"}')
})

it('offers Mentor again under Inactive for a stopped staff mentor', async () => {
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByTestId('mentor-chip-inactive'))
  const r = await screen.findByTestId('mentor-row-6')
  expect(within(r).getByTestId('mentor-action-6').textContent).toBe('admin.mentors.action.resume')
  fireEvent.click(within(r).getByTestId('mentor-action-6'))
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(6, 'resume', { token: 'tok' }))
})

it('adds a staff member from the Sheet, with no email', async () => {
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByTestId('staff-mentor-open'))
  const sheet = await screen.findByTestId('staff-mentor-sheet')
  expect(sheet.textContent).toContain('admin.mentors.staffSheet.intro')
  await within(sheet).findByTestId('staff-candidate-11')
  fireEvent.change(within(sheet).getByRole('searchbox'), { target: { value: 'ravi' } })
  expect(within(sheet).queryByTestId('staff-candidate-11')).toBeNull()
  expect(within(sheet).getByTestId('staff-mentor-add')).toHaveProperty('disabled', true)
  fireEvent.click(within(sheet).getByTestId('staff-candidate-12'))
  expect(within(sheet).getByTestId('staff-candidate-12').textContent).toContain('admin.role.qc')
  fireEvent.click(within(sheet).getByTestId('staff-mentor-add'))
  await waitFor(() => expect(mockApi.addStaffMentor).toHaveBeenCalledWith(12, { token: 'tok' }))
  expect(await screen.findByText('admin.mentors.done.added {"name":"Ravi Kumar"}')).toBeTruthy()
  expect(screen.queryByTestId('staff-mentor-sheet')).toBeNull()
})

it('says the server refusal in the Sheet', async () => {
  mockApi.addStaffMentor.mockRejectedValue(Object.assign(new Error('x'), { code: 'not_eligible' }))
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByTestId('staff-mentor-open'))
  const sheet = await screen.findByTestId('staff-mentor-sheet')
  fireEvent.click(await within(sheet).findByTestId('staff-candidate-11'))
  fireEvent.click(within(sheet).getByTestId('staff-mentor-add'))
  expect(await within(sheet).findByText('admin.mentors.error.not_eligible')).toBeTruthy()
})

it('an admin (read-only) sees the tag but no Add button and no action', async () => {
  mockRole = { role: 'admin' }
  mockApi.getMentors.mockResolvedValue({ mentors: [{ ...STAFF, manageable: false }],
    counts: { active: 1, invited: 0, inactive: 0 }, can_invite: false })
  render(<MentorsAdmin />)
  const r = await screen.findByTestId('mentor-row-5')
  expect(within(r).getByTestId('mentor-staff-5')).toBeTruthy()
  expect(within(r).queryByTestId('mentor-action-5')).toBeNull()
  expect(screen.queryByTestId('staff-mentor-open')).toBeNull()
  expect(mockApi.getStaffMentorCandidates).not.toHaveBeenCalled()
})
