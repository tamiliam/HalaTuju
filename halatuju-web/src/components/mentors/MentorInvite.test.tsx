/**
 * @jest-environment jsdom
 *
 * Invitations → Mentor (student maintenance S7b follow-up), rendered: the form posts the ONE mentor
 * invite (`inviteMentor`) and says the server's refusals in plain words; the roster lists the waiting
 * mentor invitations, and its Resend / Cancel invitation (= revoke) call the MENTOR actions (`admin/mentors/<id>/…`) —
 * never the generic Cancel — only where the mentor row is `manageable`.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import { MentorInviteForm, MentorRoster } from './MentorInvite'
import { TH } from '@/components/admin/TableFrame'

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
    { name: 'Priya', email: 'p@example.org', programme_ids: [] }, { token: 'tok' }))   // I4: Every gift
  await waitFor(() => expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' })))
})

it('a team member refused as a mentor invite is pointed to Mentors (request 57)', async () => {
  mockApi.inviteMentor.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'already_team' }))
  render(<MentorInviteForm token="tok" t={t} onDone={jest.fn()} />)
  const form = screen.getByTestId('mentor-invite-form')
  fireEvent.change(within(form).getByLabelText('admin.mentors.invite.name'), { target: { value: 'Ravi' } })
  fireEvent.change(within(form).getByLabelText('admin.emailLabel'), { target: { value: 'r@example.org' } })
  fireEvent.submit(form)
  expect((await within(form).findByRole('alert')).textContent).toBe('admin.mentors.error.already_team')
})

// ⚠ I1 (2026-11-08): the link reads "Cancel invitation" like every other tab's — only the WORD changed.
// It still calls the mentor REVOKE, with its confirm; the generic Cancel refuses a mentor invitation.
it('Resend and "Cancel invitation" call the mentor endpoints, never the generic Cancel', async () => {
  const onDone = jest.fn()
  mockApi.mentorAction.mockResolvedValue({ ...MENTOR, emailed: true })
  render(<MentorRoster data={DATA} token="tok" t={t} canManage onDone={onDone} />)
  const row = screen.getByTestId('mentor-waiting-41')
  fireEvent.click(within(row).getByText('admin.resend'))
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(7, 'resend', { token: 'tok' }))
  await waitFor(() => expect((within(row).getByText('admin.invitations.cancel') as HTMLButtonElement).disabled).toBe(false))
  expect(within(row).queryByText('admin.mentors.action.revoke')).toBeNull()
  fireEvent.click(within(row).getByText('admin.invitations.cancel'))
  expect(window.confirm).toHaveBeenCalledWith('admin.mentors.confirm.revoke {"name":"Priya Devi"}')
  await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(7, 'revoke', { token: 'tok' }))
  expect(mockApi.cancelInvitation).not.toHaveBeenCalled()
})

it('a refused confirm revokes nothing', () => {
  window.confirm = jest.fn(() => false)
  render(<MentorRoster data={DATA} token="tok" t={t} canManage onDone={jest.fn()} />)
  fireEvent.click(within(screen.getByTestId('mentor-waiting-41')).getByText('admin.invitations.cancel'))
  expect(mockApi.mentorAction).not.toHaveBeenCalled()
})

it('I1: draws the one waiting table — TH headings, Waiting (date), a red Cancel invitation', () => {
  render(<MentorRoster data={DATA} token="tok" t={t} canManage onDone={jest.fn()} />)
  const heads = screen.getAllByRole('columnheader')
  expect(heads.map((h) => h.textContent)).toEqual(
    ['admin.nameHeader', 'admin.emailHeader', 'admin.statusHeader', 'admin.actionHeader'])
  for (const h of heads) expect(h.className).toBe(TH)
  const row = screen.getByTestId('mentor-waiting-41')
  expect(within(row).getByText(/^admin\.invitations\.status\.invited \(/)).toBeTruthy()
  expect(within(row).getByText('admin.invitations.cancel').className).toContain('text-critical-600')
  expect(screen.getByTestId('invitations-table').querySelector('[data-phone-rows]')).toBeTruthy()
})

it('I1: the form wears the one layout — labels, the note under the fields, Send Invite at the left', () => {
  render(<MentorInviteForm token="tok" t={t} onDone={jest.fn()} />)
  const foot = screen.getByTestId('invite-foot')
  expect(screen.getByTestId('mentor-invite-form').contains(foot)).toBe(true)
  expect(within(foot).getByTestId('invite-note').textContent).toBe('admin.mentors.invite.note')
  expect(within(foot).getByText('admin.sendInvite').parentElement).toBe(foot)
  expect(foot.className).not.toContain('justify-between')
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

// ── Invitations I4 (2026-11-08): the gifts they will mentor in ─────────────────────────────────────
const GIFTS = [{ id: 3, code: 'flagship', name: 'Flagship Bursary' }, { id: 5, code: 'sabah', name: 'Sabah Bursary' }]

function fill(form: HTMLElement) {
  fireEvent.change(within(form).getByLabelText('admin.mentors.invite.name'), { target: { value: 'Asha' } })
  fireEvent.change(within(form).getByLabelText('admin.emailLabel'), { target: { value: 'a@example.org' } })
}

it('I4: the tick list starts at Every gift, offers the served gifts, and sends the ticked ids', async () => {
  mockApi.inviteMentor.mockResolvedValue({ id: 9, mentor: MENTOR, emailed: true, message: '' })
  render(<MentorInviteForm token="tok" t={t} onDone={jest.fn()} options={GIFTS} />)
  const form = screen.getByTestId('mentor-invite-form')
  expect(within(form).getByRole('group').getAttribute('aria-labelledby')).toBe('invite-mentor-gift-label')
  expect(screen.getByText('admin.mentors.invite.giftLabel')).toBeTruthy()
  const every = screen.getByTestId('invite-mentor-gift-every') as HTMLInputElement
  const sabah = screen.getByTestId('invite-mentor-gift-gift-5') as HTMLInputElement
  expect(every.checked).toBe(true)
  expect(sabah.disabled).toBe(true)                     // greyed while Every gift is on
  expect(screen.getByText('Flagship Bursary')).toBeTruthy()
  fireEvent.click(every)                                // un-tick Every gift, then pick Sabah
  fireEvent.click(screen.getByTestId('invite-mentor-gift-gift-5'))
  fill(form)
  fireEvent.submit(form)
  await waitFor(() => expect(mockApi.inviteMentor).toHaveBeenCalledWith(
    { name: 'Asha', email: 'a@example.org', programme_ids: [5] }, { token: 'tok' }))
  // After a send the form is back at Every gift.
  await waitFor(() => expect((screen.getByTestId('invite-mentor-gift-every') as HTMLInputElement).checked).toBe(true))
})

it('I4: with no gifts served it still offers (and sends) Every gift', async () => {
  mockApi.inviteMentor.mockResolvedValue({ id: 9, mentor: MENTOR, emailed: true, message: '' })
  render(<MentorInviteForm token="tok" t={t} onDone={jest.fn()} />)
  expect(screen.queryByTestId('invite-mentor-gift-gift-3')).toBeNull()
  const form = screen.getByTestId('mentor-invite-form')
  fill(form)
  fireEvent.submit(form)
  await waitFor(() => expect(mockApi.inviteMentor).toHaveBeenCalledWith(
    expect.objectContaining({ programme_ids: [] }), { token: 'tok' }))
})

it('I4: a gift the server will not take reads as a gift refusal, not a missing staff member', async () => {
  mockApi.inviteMentor.mockRejectedValueOnce(Object.assign(new Error('x'), { code: 'not_found' }))
  render(<MentorInviteForm token="tok" t={t} onDone={jest.fn()} options={GIFTS} />)
  const form = screen.getByTestId('mentor-invite-form')
  fill(form)
  fireEvent.submit(form)
  expect((await within(form).findByRole('alert')).textContent).toBe('admin.mentors.error.gift_not_found')
})

it('I4: the waiting table names each mentor invitation\'s gifts, or Every gift', () => {
  const rows = [
    { ...DATA.invitations[0], gifts: [GIFTS[1]], every_gift: false, programme: 'sabah', programme_name: 'Sabah Bursary' },
    { ...DATA.invitations[0], id: 42, mentor_id: 8, gifts: [], every_gift: true },
  ]
  render(<MentorRoster data={{ ...DATA, invitations: rows } as api.InvitationsPayload} token="tok" t={t}
    canManage onDone={jest.fn()} />)
  expect(within(screen.getByTestId('mentor-waiting-41')).getByText('Sabah Bursary')).toBeTruthy()
  expect(within(screen.getByTestId('mentor-waiting-42')).getByText('admin.invitations.reviewerGiftEvery')).toBeTruthy()
})
