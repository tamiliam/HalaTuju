/**
 * @jest-environment jsdom
 *
 * Organisation → Mentors (student maintenance S7a; reshaped by the S7b follow-up, 2026-11-01), rendered:
 * a MANAGEMENT page like People — only arrived mentors (Active / Inactive), Deactivate / Reactivate
 * where the row is `manageable`, the waiting count from the Invitations payload, "Invite a mentor →" as
 * a link to Invitations → Mentor, the People tab bar (Mentors · Emails · Terms disabled), and Emails
 * showing only the mentor's invitation.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import MentorsAdminScreen, { languagesLine } from './MentorsAdmin'
import InvitationEmailsCard from '@/components/admin/InvitationEmailsCard'

/** The screen as the route mounts it: the Emails card handed in (review fix 5). */
const MentorsAdmin = () => <MentorsAdminScreen EmailsCard={InvitationEmailsCard} />

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
// The Emails tab's card is the real InvitationEmailsCard; its editor is not under test here.
jest.mock('@/components/sources/PartnerTemplateEditor', () => () => null)
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (over: Partial<api.MentorRow>): api.MentorRow => ({
  id: 1, name: 'Dr Kavitha Raman', email: 'kavitha@example.org', phone: '12-345 6789', status: 'active',
  area: 'Accounting, finance', languages: { en: 'fluent', ms: 'conversational', ta: 'fluent' },
  other_language: '', invited_at: '2026-10-01T00:00:00Z', signed_in: true,
  last_seen_at: '2026-10-30T00:00:00Z', deactivated_at: null, manageable: true, scholars_now: 4, ...over,
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
  mockRole = { role: 'org_admin' }
  mockApi.getMentors.mockResolvedValue(payload())
  mockApi.getInvitations.mockResolvedValue({ waiting: { mentor: 2 } } as unknown as api.InvitationsPayload)
  mockApi.getInvitationEmails.mockResolvedValue({ templates: [
    { kind: 'invite_mentor', subject: 'S', body: 'B' }, { kind: 'invite_admin', subject: 'S', body: 'B' },
  ] } as unknown as api.PartnerEmailsPayload)
  window.confirm = jest.fn(() => true)
})

it('lists only ARRIVED mentors: Active and Inactive chips, no invited row', async () => {
  render(<MentorsAdmin />)
  const chip = await screen.findByTestId('mentor-chip-active')
  expect(chip.getAttribute('aria-pressed')).toBe('true')
  expect(chip.textContent).toContain('1')
  expect(screen.queryByTestId('mentor-chip-invited')).toBeNull()
  expect(screen.getByTestId('mentor-row-1')).toBeTruthy()
  expect(screen.queryByTestId('mentor-row-2')).toBeNull()
  fireEvent.click(screen.getByTestId('mentor-chip-inactive'))
  const inactive = await screen.findByTestId('mentor-row-3')
  expect(within(inactive).getByText('admin.mentors.action.reactivate')).toBeTruthy()
  expect(screen.queryByText('admin.mentors.action.resend')).toBeNull()
  expect(screen.queryByText('admin.mentors.action.revoke')).toBeNull()
})

it('says how many are waiting, from the Invitations payload, and links to the Mentor tab', async () => {
  render(<MentorsAdmin />)
  const line = await screen.findByTestId('mentors-waiting')
  expect(line.textContent).toContain('admin.mentors.waiting {"count":"2"}')
  expect(within(line).getByRole('link').getAttribute('href')).toBe('/admin/organisation/staff?kind=mentor')
  expect(mockApi.getInvitations).toHaveBeenCalledWith('mentor', { token: 'tok' })
})

it('"Invite a mentor" is a LINK to Invitations → Mentor, and there is no form here', async () => {
  render(<MentorsAdmin />)
  const link = await screen.findByTestId('mentor-invite-link')
  expect(link.tagName).toBe('A')
  expect(link.getAttribute('href')).toBe('/admin/organisation/staff?kind=mentor')
  expect(screen.queryByTestId('mentor-invite-form')).toBeNull()
})

it('the tab bar is Mentors · Emails · Terms, with Terms disabled', async () => {
  render(<MentorsAdmin />)
  await screen.findByTestId('mentor-row-1')
  const tabs = screen.getAllByRole('tab')
  expect(tabs.map((b) => b.textContent)).toEqual(
    ['admin.mentors.tab.mentors', 'admin.reviewers.tabEmails', 'admin.reviewers.tabTermsadmin.soon'])   // Terms carries "Soon"
  expect(tabs[2].hasAttribute('disabled')).toBe(true)
})

it('Emails shows ONLY the mentor invitation, with the "no other email" note', async () => {
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByRole('tab', { name: 'admin.reviewers.tabEmails' }))
  expect(await screen.findByText('admin.invitations.emails.kind.invite_mentor')).toBeTruthy()
  expect(screen.queryByText('admin.invitations.emails.kind.invite_admin')).toBeNull()
  expect(screen.getByTestId('invitation-emails-note').textContent).toBe('admin.mentors.emailsNote')
})

it('an admin (read-only) sees the list and the Emails tab (the template editor gate), no invite link, no actions', async () => {
  mockRole = { role: 'admin' }
  mockApi.getMentors.mockResolvedValue(payload({
    can_invite: false, mentors: [ACTIVE, INVITED, INACTIVE].map((m) => ({ ...m, manageable: false })),
  }))
  render(<MentorsAdmin />)
  const active = await screen.findByTestId('mentor-row-1')
  expect(within(active).queryByRole('button')).toBeNull()
  expect(screen.queryByTestId('mentor-invite-link')).toBeNull()
  // Review fix 3: the same gate as Invitations → Emails (super, org_admin, admin).
  expect(screen.getByRole('tab', { name: 'admin.reviewers.tabEmails' })).toBeTruthy()
  expect(mockApi.getInvitations).not.toHaveBeenCalled()
})

it('with nobody arrived yet, the empty state points at the invite', async () => {
  mockApi.getMentors.mockResolvedValue(payload({ mentors: [INVITED], counts: { active: 0, invited: 1, inactive: 0 } }))
  render(<MentorsAdmin />)
  expect((await screen.findByTestId('mentors-empty')).textContent).toBe('admin.mentors.emptyNone')
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
  mockApi.mentorAction.mockRejectedValue(Object.assign(new Error('x'), { code: 'active' }))
  render(<MentorsAdmin />)
  fireEvent.click(await screen.findByTestId('mentor-chip-inactive'))
  fireEvent.click(within(await screen.findByTestId('mentor-row-3')).getByText('admin.mentors.action.reactivate'))
  expect((await screen.findByRole('alert')).textContent).toBe('admin.mentors.error.active')
})

it('names the languages spoken well enough, with the fourth language by name', () => {
  expect(languagesLine(ACTIVE)).toBe('EN · MS · TA')
  expect(languagesLine({ ...INVITED, other_language: 'Mandarin' })).toBe('Mandarin')
  expect(languagesLine(INVITED)).toBe('')
})

it('S7b: "Scholars now" shows how many scholars each mentor has now', async () => {
  render(<MentorsAdmin />)
  expect(await screen.findByText('admin.mentors.col.scholarsNow')).toBeTruthy()
  expect(screen.getByTestId('mentor-scholars-1').textContent).toBe('4')
})

it('review fix 3: finance (not an editor of the invitation letters) gets no Emails tab', async () => {
  mockRole = { role: 'finance' }
  render(<MentorsAdmin />)
  await screen.findByTestId('mentor-row-1')
  expect(screen.queryByRole('tab', { name: 'admin.reviewers.tabEmails' })).toBeNull()
})

it('review fix 4: a mentor switched off before signing in is not listed, and Inactive counts only arrivals', async () => {
  const revokedEarly = row({ id: 4, name: 'Never Arrived', status: 'inactive', signed_in: false,
    deactivated_at: '2026-10-25T00:00:00Z' })
  mockApi.getMentors.mockResolvedValue(payload({ mentors: [ACTIVE, INVITED, INACTIVE, revokedEarly],
    counts: { active: 1, invited: 1, inactive: 2 } }))
  render(<MentorsAdmin />)
  const chip = await screen.findByTestId('mentor-chip-inactive')
  expect(chip.textContent).toContain('1')
  fireEvent.click(chip)
  expect(await screen.findByTestId('mentor-row-3')).toBeTruthy()
  expect(screen.queryByTestId('mentor-row-4')).toBeNull()
})
