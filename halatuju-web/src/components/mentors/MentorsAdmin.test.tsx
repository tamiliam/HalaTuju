/**
 * @jest-environment jsdom
 *
 * Team tables T3 (2026-11-03): Team → Mentors (the old Organisation → Mentors page's list, moved under Team)
 * and the mentor detail page, rendered.
 * - The list is the old page's, unchanged: only ARRIVED mentors plus every staff mentor, Active · n /
 *   Inactive · n, "n waiting to accept: see Invitations" from the Invitations payload.
 * - Columns: Mentor (the name links to the detail page) · Also in · Area · Languages · Scholars now ·
 *   Meetings (90 days) · Last meeting · Concerns open · the action.
 * - No "Invite a mentor" and no Emails tab here any more. Add Mentor = 7d's staff Sheet (no email).
 * - Remove = 7d: a staff mentor's Stop mentoring, a pure mentor's Deactivate — confirmed in the shared Sheet;
 *   under Inactive, Mentor again / Reactivate. Nothing offered where the row is not `manageable`.
 * - The detail page: figures, current and past scholars, standing and concern chips, '-' for no gap; never a
 *   meeting note (the payload carries none; the page draws only what it is given).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import TeamMentorsScreen, { MentorDetail, actionOf, languagesLine, mentorHref } from './MentorsAdmin'
import { AlsoIn } from '@/components/admin/TeamTables'

/** The screen as the Team page mounts it: its own "Also in" chips handed in. */
const TeamMentors = () => <TeamMentorsScreen AlsoIn={AlsoIn} />

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (over: Partial<api.MentorRow>): api.MentorRow => ({
  id: 1, name: 'Dr Kavitha Raman', email: 'kavitha@example.org', phone: '12-345 6789', status: 'active',
  area: 'Accounting, finance', languages: { en: 'fluent', ms: 'conversational', ta: 'fluent' },
  other_language: '', invited_at: '2026-10-01T00:00:00Z', signed_in: true,
  last_seen_at: '2026-10-30T00:00:00Z', deactivated_at: null, manageable: true, scholars_now: 4,
  staff_role: null, tables: ['mentors'], lead: false, meetings_90: 9, last_meeting: '2026-10-28', concerns_open: 1,
  ...over,
})
const ACTIVE = row({})
const INVITED = row({ id: 2, name: 'Ms Priya Devi', status: 'invited', signed_in: false, last_seen_at: null })
const INACTIVE = row({ id: 3, name: 'Encik Faizal', status: 'inactive', deactivated_at: '2026-10-20T00:00:00Z' })
// A staff mentor who has not signed in yet (their sign-in is People's): listed all the same.
const STAFF = row({ id: 5, name: 'Suresh', staff_role: 'org_admin', signed_in: false, lead: true,
  tables: ['admins', 'reviewers', 'mentors'], meetings_90: 3, last_meeting: '2026-10-20', concerns_open: 0 })
const STOPPED = row({ id: 6, name: 'Stopped Staff', staff_role: 'reviewer', status: 'inactive',
  deactivated_at: '2026-10-20T00:00:00Z', tables: ['reviewers'] })

const payload = (mentors = [ACTIVE, INVITED, INACTIVE, STAFF, STOPPED]): api.MentorsPayload =>
  ({ mentors, counts: { active: 2, invited: 1, inactive: 2 }, can_invite: true })

beforeEach(() => {
  jest.clearAllMocks()
  mockRole = { role: 'org_admin' }
  mockApi.getMentors.mockResolvedValue(payload())
  mockApi.getInvitations.mockResolvedValue({ waiting: { mentor: 2 } } as unknown as api.InvitationsPayload)
  mockApi.getStaffMentorCandidates.mockResolvedValue({ staff: [
    { id: 11, name: 'Siti Nur Haliza', email: 'haliza@example.org', role: 'reviewer', organisation: 'BP' },
    { id: 12, name: 'Ravi Kumar', email: 'ravi@example.org', role: 'qc', organisation: 'BP' },
  ] })
  mockApi.addStaffMentor.mockResolvedValue(row({ id: 9, name: 'Ravi Kumar', staff_role: 'qc' }))
  mockApi.mentorAction.mockResolvedValue({ ...ACTIVE, emailed: null })
  window.confirm = jest.fn(() => true)
})

describe('Team → Mentors', () => {
  it('lists only ARRIVED mentors and every staff mentor, Active and Inactive, no invited row', async () => {
    render(<TeamMentors />)
    const chip = await screen.findByTestId('mentor-chip-active')
    expect(chip.getAttribute('aria-pressed')).toBe('true')
    expect(chip.textContent).toContain('2')
    expect(screen.getByTestId('mentor-row-1')).toBeTruthy()
    expect(screen.getByTestId('mentor-row-5')).toBeTruthy()   // staff, not signed in: listed
    expect(screen.queryByTestId('mentor-row-2')).toBeNull()   // invited: on Invitations
    fireEvent.click(screen.getByTestId('mentor-chip-inactive'))
    expect(await screen.findByTestId('mentor-row-3')).toBeTruthy()
    expect(screen.getByTestId('mentor-row-6')).toBeTruthy()
  })

  it('draws the board columns: the name links to the detail page, Also in, the work figures', async () => {
    render(<TeamMentors />)
    const r = await screen.findByTestId('mentor-row-1')
    expect(within(r).getByTestId('mentor-link-1').getAttribute('href')).toBe('/admin/organisation/reviewers/mentors/1')
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'admin.mentors.col.mentor', 'admin.team.colAlsoIn', 'admin.mentors.col.area', 'admin.mentors.col.languages',
      'admin.mentors.col.scholarsNow', 'admin.mentors.col.meetings90', 'admin.mentors.col.lastMeeting',
      'admin.mentors.col.concernsOpen', 'admin.mentors.col.actions'])
    expect(screen.getByTestId('mentor-scholars-1').textContent).toBe('4')
    expect(screen.getByTestId('mentor-meetings-1').textContent).toBe('9')
    expect(screen.getByTestId('mentor-concerns-1').textContent).toBe('1')
    expect(within(r).getByText('28/10/2026')).toBeTruthy()
    // A pure mentor sits at no other table; the lead who mentors reads "Admin (lead)" and "Reviewer".
    expect(within(r).queryByTestId('also-in')).toBeNull()
    const staff = within(screen.getByTestId('mentor-row-5')).getByTestId('also-in')
    expect(staff.textContent).toBe('admin.team.chip.leadadmin.team.chip.reviewers')
  })

  it('says how many are waiting, from the Invitations payload, and links there; no invite button', async () => {
    render(<TeamMentors />)
    const line = await screen.findByTestId('mentors-waiting')
    expect(line.textContent).toContain('admin.mentors.waiting {"count":"2"}')
    expect(within(line).getByRole('link').getAttribute('href')).toBe('/admin/organisation/staff?kind=mentor')
    expect(screen.queryByTestId('mentor-invite-link')).toBeNull()
    expect(screen.queryByRole('tab')).toBeNull()   // no Emails / Terms tabs here: Team's own bar
  })

  it('Remove is 7d: Stop mentoring for staff, Deactivate for a mentor login — confirmed in the Sheet', async () => {
    render(<TeamMentors />)
    expect((await screen.findByTestId('mentor-action-1')).textContent).toBe('admin.mentors.action.deactivate')
    fireEvent.click(screen.getByTestId('mentor-action-5'))
    const sheet = await screen.findByTestId('mentor-remove')
    expect(sheet.textContent).toContain('admin.mentors.confirm.stop {"name":"Suresh"}')
    expect(mockApi.mentorAction).not.toHaveBeenCalled()
    fireEvent.click(within(sheet).getByTestId('mentor-remove-confirm'))
    await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(5, 'stop', { token: 'tok' }))
    expect(window.confirm).not.toHaveBeenCalled()
    await waitFor(() => expect(mockApi.getMentors).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByTestId('mentor-action-1'))
    fireEvent.click(within(await screen.findByTestId('mentor-remove')).getByTestId('mentor-remove-confirm'))
    await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(1, 'deactivate', { token: 'tok' }))
  })

  it('under Inactive: Mentor again (staff) and Reactivate (mentor login), straight away', async () => {
    render(<TeamMentors />)
    fireEvent.click(await screen.findByTestId('mentor-chip-inactive'))
    expect((await screen.findByTestId('mentor-action-3')).textContent).toBe('admin.mentors.action.reactivate')
    fireEvent.click(screen.getByTestId('mentor-action-6'))
    await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(6, 'resume', { token: 'tok' }))
  })

  it('a refused action reads in its own words', async () => {
    mockApi.mentorAction.mockRejectedValue(Object.assign(new Error('x'), { code: 'active' }))
    render(<TeamMentors />)
    fireEvent.click(await screen.findByTestId('mentor-chip-inactive'))
    fireEvent.click(await screen.findByTestId('mentor-action-3'))
    expect((await screen.findByRole('alert')).textContent).toBe('admin.mentors.error.active')
  })

  it('Add Mentor is the 7d staff Sheet, with no email', async () => {
    render(<TeamMentors />)
    fireEvent.click(await screen.findByTestId('team-add-mentors-open'))
    const sheet = await screen.findByTestId('staff-mentor-sheet')
    expect(sheet.textContent).toContain('admin.mentors.staffSheet.intro')
    fireEvent.change(within(sheet).getByRole('searchbox'), { target: { value: 'ravi' } })
    await waitFor(() => expect(within(sheet).queryByTestId('staff-candidate-11')).toBeNull())
    fireEvent.click(within(sheet).getByTestId('staff-candidate-12'))
    fireEvent.click(within(sheet).getByTestId('staff-mentor-add'))
    await waitFor(() => expect(mockApi.addStaffMentor).toHaveBeenCalledWith(12, { token: 'tok' }))
    expect(await screen.findByText('admin.mentors.done.added {"name":"Ravi Kumar"}')).toBeTruthy()
  })

  it('the Sheet says the server refusal', async () => {
    mockApi.addStaffMentor.mockRejectedValue(Object.assign(new Error('x'), { code: 'not_eligible' }))
    render(<TeamMentors />)
    fireEvent.click(await screen.findByTestId('team-add-mentors-open'))
    const sheet = await screen.findByTestId('staff-mentor-sheet')
    fireEvent.click(await within(sheet).findByTestId('staff-candidate-11'))
    fireEvent.click(within(sheet).getByTestId('staff-mentor-add'))
    expect(await within(sheet).findByText('admin.mentors.error.not_eligible')).toBeTruthy()
  })

  it('an admin (read-only) sees the table, no Add Mentor, no action, no waiting line', async () => {
    mockRole = { role: 'admin' }
    mockApi.getMentors.mockResolvedValue(payload([ACTIVE, STAFF].map((m) => ({ ...m, manageable: false }))))
    render(<TeamMentors />)
    const r = await screen.findByTestId('mentor-row-1')
    expect(within(r).queryByRole('button')).toBeNull()
    expect(screen.queryByTestId('team-add-mentors-open')).toBeNull()
    expect(mockApi.getInvitations).not.toHaveBeenCalled()
    expect(mockApi.getStaffMentorCandidates).not.toHaveBeenCalled()
  })

  it('T3 review: a null Concerns open (no See all students) reads as a dash, not 0', async () => {
    mockApi.getMentors.mockResolvedValue({ ...payload([{ ...ACTIVE, concerns_open: null }]), sees_scholars: false })
    render(<TeamMentors />)
    expect((await screen.findByTestId('mentor-concerns-1')).textContent).toBe('-')
  })

  it('with nobody arrived yet, the empty state points at Invitations and Add Mentor', async () => {
    mockApi.getMentors.mockResolvedValue(payload([INVITED]))
    render(<TeamMentors />)
    expect((await screen.findByTestId('mentors-empty')).textContent).toBe('admin.mentors.emptyNone')
  })

  it('a mentor switched off before signing in is not listed', async () => {
    const early = row({ id: 4, status: 'inactive', signed_in: false, deactivated_at: '2026-10-25T00:00:00Z' })
    mockApi.getMentors.mockResolvedValue(payload([ACTIVE, INACTIVE, early]))
    render(<TeamMentors />)
    const chip = await screen.findByTestId('mentor-chip-inactive')
    expect(chip.textContent).toContain('1')
    fireEvent.click(chip)
    expect(await screen.findByTestId('mentor-row-3')).toBeTruthy()
    expect(screen.queryByTestId('mentor-row-4')).toBeNull()
  })

  it('helpers: languages, the row action, the detail link', () => {
    expect(languagesLine(ACTIVE)).toBe('EN · MS · TA')
    expect(languagesLine({ ...ACTIVE, languages: { en: '', ms: '', ta: '' }, other_language: 'Mandarin' })).toBe('Mandarin')
    expect([ACTIVE, INACTIVE, STAFF, STOPPED].map(actionOf)).toEqual(['deactivate', 'reactivate', 'stop', 'resume'])
    expect(mentorHref(7)).toBe('/admin/organisation/reviewers/mentors/7')
  })
})

describe('the mentor detail page', () => {
  const scholar = (over: Partial<api.MentorScholarRow>): api.MentorScholarRow => ({
    application_id: 104, name: 'Nur Aisyah', since: '2026-09-02T00:00:00Z', ended: null, meetings: 3,
    last_meeting: '2026-10-28', standing: 'performing', has_file: true, concern: 'open', ...over,
  })
  const DETAIL: api.MentorDetail = {
    mentor: ACTIVE, mentoring_since: '2026-09-02T00:00:00Z', sees_scholars: true,
    figures: { scholars_now: 2, meetings_90: 9, average_gap_days: 18, concerns_raised: 3, concerns_open: 1,
      last_meeting: '2026-10-28' },
    current: [scholar({}), scholar({ application_id: 105, name: 'Thivya', meetings: 0, last_meeting: null,
      standing: 'no_result_yet', concern: null })],
    past: [scholar({ application_id: 90, name: 'Old Scholar', ended: '2026-08-01T00:00:00Z', concern: 'handled',
      standing: null, has_file: false })],
  }

  it('shows the header, the four figures, current and past scholars', async () => {
    mockApi.getMentorDetail.mockResolvedValue(DETAIL)
    render(<MentorDetail id={1} />)
    expect(await screen.findByText('Dr Kavitha Raman')).toBeTruthy()
    expect(mockApi.getMentorDetail).toHaveBeenCalledWith(1, { token: 'tok' })
    expect(screen.getByTestId('mentor-back').getAttribute('href')).toBe('/admin/organisation/reviewers?tab=mentors')
    const facts = screen.getByTestId('mentor-facts').textContent
    expect(facts).toContain('Accounting, finance')
    expect(facts).toContain('admin.mentors.detail.since {"date":"02/09/2026"}')
    expect(facts).toContain('admin.mentors.detail.lastSeen {"date":"30/10/2026"}')
    expect(screen.getByTestId('tile-scholars').textContent).toContain('2')
    expect(screen.getByTestId('tile-meetings').textContent).toContain('9')
    expect(screen.getByTestId('tile-gap').textContent).toContain('admin.mentors.detail.days {"n":"18"}')
    expect(screen.getByTestId('tile-concerns').textContent).toContain('3 / 1')
    const current = screen.getByTestId('mentor-current')
    expect(within(current).getByText('Nur Aisyah').getAttribute('href')).toBe('/admin/scholars/104')
    expect(within(current).getByText('admin.scholars.standing.performing')).toBeTruthy()
    expect(within(current).getByTestId('mentor-concern-104').textContent).toBe('admin.mentors.detail.concern.open')
    const past = screen.getByTestId('mentor-past')
    expect(within(past).getByText('Old Scholar').tagName).not.toBe('A')   // no file to open
    expect(within(past).getByText('01/08/2026')).toBeTruthy()
  })

  it("shows '-' for the gap when no scholar has had two meetings, and says when nobody is mentored now", async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, current: [], past: [],
      figures: { ...DETAIL.figures!, average_gap_days: null } })
    render(<MentorDetail id={1} />)
    expect((await screen.findByTestId('tile-gap')).textContent).toContain('-')
    expect(screen.getByTestId('mentor-current-none')).toBeTruthy()
    expect(screen.queryByTestId('mentor-past')).toBeNull()
  })

  it('T3 review: without See all students, the mentor only — a plain line, no figures or scholars', async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, sees_scholars: false, figures: null, current: [], past: [],
      mentor: { ...ACTIVE, concerns_open: null } })
    render(<MentorDetail id={1} />)
    expect((await screen.findByTestId('mentor-needs-see-all')).textContent).toBe('admin.mentors.detail.needSeeAll')
    expect(screen.getByText('Dr Kavitha Raman')).toBeTruthy()
    expect(screen.queryByTestId('tile-scholars')).toBeNull()
    expect(screen.queryByTestId('mentor-current')).toBeNull()
    expect(screen.queryByTestId('mentor-current-none')).toBeNull()
  })

  it('a 404 says not found; anything else says it could not load', async () => {
    mockApi.getMentorDetail.mockRejectedValue(Object.assign(new Error('x'), { status: 404 }))
    const { unmount } = render(<MentorDetail id={9} />)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.mentors.detail.notFound')
    unmount()
    mockApi.getMentorDetail.mockRejectedValue(Object.assign(new Error('x'), { status: 500 }))
    render(<MentorDetail id={9} />)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.mentors.loadError')
  })

  // ── Invitations I4 (2026-11-08): the details box shows and edits the gifts they mentor in ──
  const PROGRAMMES = [
    { id: 3, code: 'flagship', name: 'Flagship Bursary', is_active: true },
    { id: 5, code: 'sabah', name: 'Sabah Bursary', is_active: true },
  ]

  it('I4: shows Every gift for a mentor with none named, and their gifts otherwise', async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, programmes: PROGRAMMES,
      mentor: { ...ACTIVE, gifts: [], every_gift: true } })
    const { unmount } = render(<MentorDetail id={1} />)
    const box = await screen.findByTestId('mentor-gifts')
    expect(within(box).getByText('admin.mentors.gifts.label')).toBeTruthy()
    expect(within(box).getByText('admin.reviewers.gifts.every')).toBeTruthy()
    unmount()
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, programmes: PROGRAMMES,
      mentor: { ...ACTIVE, gifts: [{ id: 5, code: 'sabah', name: 'Sabah Bursary' }], every_gift: false } })
    render(<MentorDetail id={1} />)
    expect(within(await screen.findByTestId('mentor-gifts')).getByText('Sabah Bursary')).toBeTruthy()
  })

  it('I4: an edit saves the ticked gifts through the mentor endpoint and shows them', async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, programmes: PROGRAMMES,
      mentor: { ...ACTIVE, gifts: [], every_gift: true } })
    mockApi.setMentorGifts.mockResolvedValue({ id: 1, every_gift: false,
      gifts: [{ id: 5, code: 'sabah', name: 'Sabah Bursary' }] })
    render(<MentorDetail id={1} />)
    fireEvent.click(await screen.findByTestId('gifts-edit-1'))
    fireEvent.click(screen.getByTestId('gifts-ticks-1-every'))
    fireEvent.click(screen.getByTestId('gifts-ticks-1-gift-5'))
    fireEvent.click(screen.getByTestId('gifts-save-1'))
    await waitFor(() => expect(mockApi.setMentorGifts).toHaveBeenCalledWith(1, [5], { token: 'tok' }))
    expect(mockApi.setReviewerGifts).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByTestId('gifts-pop-1')).toBeNull())
    expect(within(screen.getByTestId('mentor-gifts')).getByText('Sabah Bursary')).toBeTruthy()
  })

  it('I4: a narrowing refused (current scholars outside) says how many, and changes nothing', async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, programmes: PROGRAMMES,
      mentor: { ...ACTIVE, gifts: [], every_gift: true } })
    mockApi.setMentorGifts.mockRejectedValue(Object.assign(new Error('x'),
      { code: 'mentor_has_scholars_outside', body: { code: 'mentor_has_scholars_outside', count: 2 } }))
    render(<MentorDetail id={1} />)
    fireEvent.click(await screen.findByTestId('gifts-edit-1'))
    fireEvent.click(screen.getByTestId('gifts-ticks-1-every'))
    fireEvent.click(screen.getByTestId('gifts-ticks-1-gift-5'))
    fireEvent.click(screen.getByTestId('gifts-save-1'))
    const alert = await within(screen.getByTestId('gifts-pop-1')).findByRole('alert')
    expect(alert.textContent).toBe('admin.mentors.gifts.outside {"count":"2"}')
    expect(within(screen.getByTestId('mentor-gifts')).getByText('admin.reviewers.gifts.every')).toBeTruthy()
  })

  it('I4: any other refusal reads as the plain could-not-save line', async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, programmes: PROGRAMMES })
    mockApi.setMentorGifts.mockRejectedValue(Object.assign(new Error('x'), { code: 'not_found' }))
    render(<MentorDetail id={1} />)
    fireEvent.click(await screen.findByTestId('gifts-edit-1'))
    fireEvent.click(screen.getByTestId('gifts-save-1'))
    expect((await screen.findByRole('alert')).textContent).toBe('admin.reviewers.detail.giftFailed')
  })

  it('I4: no pencil for a reader who may not manage the mentor, or on an older api', async () => {
    mockApi.getMentorDetail.mockResolvedValue({ ...DETAIL, programmes: PROGRAMMES,
      mentor: { ...ACTIVE, manageable: false } })
    const { unmount } = render(<MentorDetail id={1} />)
    await screen.findByTestId('mentor-gifts')
    expect(screen.queryByTestId('gifts-edit-1')).toBeNull()
    unmount()
    mockApi.getMentorDetail.mockResolvedValue(DETAIL)   // no `programmes`
    render(<MentorDetail id={1} />)
    await screen.findByTestId('mentor-gifts')
    expect(screen.queryByTestId('gifts-edit-1')).toBeNull()
  })
})
