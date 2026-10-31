/**
 * @jest-environment jsdom
 *
 * Invitations → Mentor (student maintenance S7b follow-up), rendered: the form posts the ONE mentor
 * invite (`inviteMentor`) and says the server's refusals in plain words; the roster lists the waiting
 * mentor invitations, and its Resend / Revoke call the MENTOR actions (`admin/mentors/<id>/…`) —
 * never the generic Cancel — only where the mentor row is `manageable`.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import { MentorInviteForm, MentorRoster } from './MentorInvite'

jest.mock('@/lib/admin-api')
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
const mockApi = api as jest.Mocked<typeof api>
const t = (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k)

const MENTOR = {
  id: 7, name: 'Priya Devi', email: 'priya@example.org', phone: '', status: 'invited', area: '',
  languages: { en: '', ms: '', ta: '' }, other_language: '', invited_at: null, signed_in: false,
  last_seen_at: null, deactivated_at: null, manageable: true, scholars_now: 0,
} as api.MentorRow
const DATA = {
  kind: 'mentor', invitations: [{ id: 41, name: 'Priya Devi', email: 'priya@example.org', role: 'mentor',
    status: 'invited', sent_at: '2026-10-31T00:00:00Z', send_count: 1, last_send_ok: true, last_send_error: '',
    accepted_at: null, admin_id: 99, is_active: true, paused: false, programme: '', programme_name: '', mentor_id: 7 }],
  mentors: [MENTOR],
} as unknown as api.InvitationsPayload

beforeEach(() => {
  jest.clearAllMocks()
  window.confirm = jest.fn(() => true)
})

it('invites with a name and an email; a refusal reads in plain words', async () => {
  const onDone = jest.fn()
  mockApi.inviteMentor.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'already_staff' }))
  mockApi.inviteMentor.mockResolvedValueOnce({ id: 9, mentor: MENTOR, emailed: true, message: '' })
  render(<MentorInviteForm token="tok" t={t} onDone={onDone} />)
  const form = screen.getByTestId('mentor-invite-form')
  fireEvent.change(within(form).getByLabelText('admin.mentors.invite.name'), { target: { value: ' Priya ' } })
  fireEvent.change(within(form).getByLabelText('admin.emailLabel'), { target: { value: 'p@example.org' } })
  fireEvent.submit(form)
  expect((await within(form).findByRole('alert')).textContent).toBe('admin.mentors.error.already_staff')
  fireEvent.submit(form)
  await waitFor(() => expect(mockApi.inviteMentor).toHaveBeenLastCalledWith(
    { name: 'Priya', email: 'p@example.org' }, { token: 'tok' }))
  await waitFor(() => expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' })))
})

it('Resend and Revoke call the mentor endpoints, never the generic Cancel', async () => {
  const onDone = jest.fn()
  mockApi.mentorAction.mockResolvedValue({ ...MENTOR, emailed: true })
  render(<MentorRoster data={DATA} token="tok" t={t} canManage onDone={onDone} />)
  const row = screen.getByTestId('mentor-waiting-41')
  fireEvent.click(within(row).getByText('admin.mentors.action.resend'))
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(7, 'resend', { token: 'tok' }))
  fireEvent.click(within(row).getByText('admin.mentors.action.revoke'))
  expect(window.confirm).toHaveBeenCalled()
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(7, 'revoke', { token: 'tok' }))
  expect(mockApi.cancelInvitation).not.toHaveBeenCalled()
})

it('offers no action on a row the caller may not manage, or to a reader', () => {
  const { unmount } = render(<MentorRoster data={{ ...DATA, mentors: [{ ...MENTOR, manageable: false }] }}
    token="tok" t={t} canManage onDone={jest.fn()} />)
  expect(within(screen.getByTestId('mentor-waiting-41')).queryByRole('button')).toBeNull()
  unmount()
  render(<MentorRoster data={DATA} token="tok" t={t} canManage={false} onDone={jest.fn()} />)
  expect(within(screen.getByTestId('mentor-waiting-41')).queryByRole('button')).toBeNull()
})

it('says so when nobody is waiting', () => {
  render(<MentorRoster data={{ ...DATA, invitations: [], mentors: [] }} token="tok" t={t} canManage onDone={jest.fn()} />)
  expect(screen.getByText('admin.invitations.mentor.noneWaiting')).toBeTruthy()
})
