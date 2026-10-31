/**
 * @jest-environment jsdom
 *
 * Organisation → Mentors (student maintenance S7a, 2026-10-31; the MentorsAdmin board), rendered:
 * the status chips and their counts, the table's "Not filled in yet", the actions each status offers
 * (and only where the row is `manageable`), the invite form for super / org_admin only, and the
 * server's refusals in plain words.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import MentorsAdmin, { languagesLine } from './MentorsAdmin'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok' }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (over: Partial<api.MentorRow>): api.MentorRow => ({
  id: 1, name: 'Dr Kavitha Raman', email: 'kavitha@example.org', phone: '12-345 6789', status: 'active',
  area: 'Accounting, finance', languages: { en: 'fluent', ms: 'conversational', ta: 'fluent' },
  other_language: '', invited_at: '2026-10-01T00:00:00Z', signed_in: true,
  last_seen_at: '2026-10-30T00:00:00Z', deactivated_at: null, manageable: true, ...over,
})
const ACTIVE = row({})
const INVITED = row({ id: 2, name: 'Ms Priya Devi', email: 'priya@example.org', phone: '', status: 'invited',
  area: '', languages: { en: '', ms: '', ta: '' }, signed_in: false, last_seen_at: null })
const INACTIVE = row({ id: 3, name: 'Encik Faizal', status: 'inactive', deactivated_at: '2026-10-20T00:00:00Z' })

const payload = (over: Partial<api.MentorsPayload> = {}): api.MentorsPayload => ({
  mentors: [ACTIVE, INVITED, INACTIVE], counts: { active: 1, invited: 1, inactive: 1 }, can_invite: true,
  ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getMentors.mockResolvedValue(payload())
  window.confirm = jest.fn(() => true)
})

it('opens on Active with a count on every chip, and switches by chip', async () => {
  render(<MentorsAdmin />)
  const chip = await screen.findByTestId('mentor-chip-active')
  expect(chip.getAttribute('aria-pressed')).toBe('true')
  expect(chip.textContent).toContain('1')
  expect(screen.getByTestId('mentor-row-1')).toBeTruthy()
  expect(screen.queryByTestId('mentor-row-2')).toBeNull()
  fireEvent.click(screen.getByTestId('mentor-chip-invited'))
  const invited = await screen.findByTestId('mentor-row-2')
  // The mentor's own details are not filled in yet: said so, never left blank.
  expect(within(invited).getAllByText('admin.mentors.notFilled')).toHaveLength(2)
})

it('offers Deactivate for active, Resend · Revoke for invited, Reactivate for inactive', async () => {
  render(<MentorsAdmin />)
  const active = await screen.findByTestId('mentor-row-1')
  expect(within(active).getByText('admin.mentors.action.deactivate')).toBeTruthy()
  fireEvent.click(screen.getByTestId('mentor-chip-invited'))
  const invited = await screen.findByTestId('mentor-row-2')
  expect(within(invited).getByText('admin.mentors.action.resend')).toBeTruthy()
  expect(within(invited).getByText('admin.mentors.action.revoke')).toBeTruthy()
  fireEvent.click(screen.getByTestId('mentor-chip-inactive'))
  const inactive = await screen.findByTestId('mentor-row-3')
  expect(within(inactive).getByText('admin.mentors.action.reactivate')).toBeTruthy()
})

it('an admin (read-only) sees the list but no invite and no actions', async () => {
  mockApi.getMentors.mockResolvedValue(payload({
    can_invite: false, mentors: [ACTIVE, INVITED, INACTIVE].map((m) => ({ ...m, manageable: false })),
  }))
  render(<MentorsAdmin />)
  const active = await screen.findByTestId('mentor-row-1')
  expect(within(active).queryByRole('button')).toBeNull()
  expect(screen.queryByText('admin.mentors.inviteOpen')).toBeNull()
})

it('Deactivate asks first, then calls the endpoint and reloads', async () => {
  mockApi.mentorAction.mockResolvedValue({ ...ACTIVE, status: 'inactive', emailed: null })
  render(<MentorsAdmin />)
  const active = await screen.findByTestId('mentor-row-1')
  fireEvent.click(within(active).getByText('admin.mentors.action.deactivate'))
  expect(window.confirm).toHaveBeenCalled()
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(1, 'deactivate', { token: 'tok' }))
  expect(await screen.findByRole('status')).toBeTruthy()
  await waitFor(() => expect(mockApi.getMentors).toHaveBeenCalledTimes(2))
})

it('a refused action reads in its own words', async () => {
  mockApi.mentorAction.mockRejectedValue(Object.assign(new Error('x'), { code: 'already_joined' }))
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByTestId('mentor-chip-invited'))
  fireEvent.click(within(await screen.findByTestId('mentor-row-2')).getByText('admin.mentors.action.resend'))
  expect((await screen.findByRole('alert')).textContent).toBe('admin.mentors.error.already_joined')
})

it('invites with a name and an email, and shows the server refusal in plain words', async () => {
  mockApi.inviteMentor.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'already_staff' }))
  mockApi.inviteMentor.mockResolvedValueOnce({ id: 9, mentor: INVITED, emailed: true, message: '' })
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByText('admin.mentors.inviteOpen'))
  const form = screen.getByTestId('mentor-invite-form')
  fireEvent.change(within(form).getByLabelText('admin.mentors.invite.name'), { target: { value: ' Priya ' } })
  fireEvent.change(within(form).getByLabelText('admin.mentors.invite.email'), { target: { value: 'p@example.org' } })
  fireEvent.submit(form)
  expect((await within(form).findByRole('alert')).textContent).toBe('admin.mentors.error.already_staff')
  fireEvent.submit(form)
  await waitFor(() => expect(mockApi.inviteMentor).toHaveBeenLastCalledWith(
    { name: 'Priya', email: 'p@example.org' }, { token: 'tok' }))
  await waitFor(() => expect(screen.queryByTestId('mentor-invite-form')).toBeNull())
})

it('names the languages spoken well enough, with the fourth language by name', () => {
  expect(languagesLine(ACTIVE)).toBe('EN · MS · TA')
  expect(languagesLine({ ...INVITED, other_language: 'Mandarin' })).toBe('Mandarin')
  expect(languagesLine(INVITED)).toBe('')
})
