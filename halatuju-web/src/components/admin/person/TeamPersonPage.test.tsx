/**
 * @jest-environment jsdom
 *
 * Sprint T3 (owner 2026-11-09; D8, D9, M1–M6): ONE person page for every team member, rendered once
 * per kind of person — a reviewer, an Admin, a Finance person, a pure mentor, an organisation admin,
 * and somebody in two tables. Each shows:
 *   * the same two tabs, Profile and Permissions, for every viewer (Q1: an admin or finance reader's
 *     Permissions tab holds one line and fetches nothing);
 *   * under the name, the tables they sit in as the "Also in" chips — and NO ROLE WORD (D9);
 *   * Status · Joined · Last seen, in that order, Last seen relative with the exact time in `title` (M1);
 *   * every profile field, "Not given" where it is empty, never an address (M3).
 * A pure mentor's Permissions tab is read-only, with the Add-to-table path only for a viewer who may
 * add (D8); an organisation admin's shows locked switches under one line (M2); somebody in two tables
 * shows both tables' parts (M6).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import TeamPersonPage from './TeamPersonPage'
import * as admins from '@/lib/admin-api/admins'
import * as mentors from '@/lib/admin-api/mentors'
import * as reviewers from '@/lib/admin-api/reviewers'
import { formatDateTime } from '@/lib/formatDate'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    <a href={href} {...rest}>{children}</a>,
}))
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush }) }))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let viewer: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: viewer }) }))
// The three modules the barrel re-exports: mocked at the source, so the page's every import is the mock.
jest.mock('@/lib/admin-api/admins')
jest.mock('@/lib/admin-api/mentors')
jest.mock('@/lib/admin-api/reviewers')
const mA = admins as jest.Mocked<typeof admins>
const mM = mentors as jest.Mocked<typeof mentors>
const mR = reviewers as jest.Mocked<typeof reviewers>

const TWO_DAYS_AGO = new Date(Date.now() - 2 * 24 * 3600 * 1000 - 60_000).toISOString()

const person = (over: Partial<admins.TeamPersonBlock> = {}): admins.TeamPersonBlock => ({
  admin_id: 5, mentor_id: null, name: 'Kavitha Raman', email: 'kavitha@example.org', tables: ['reviewers'],
  lead: false, mentor_only: false, is_active: true, paused: false, joined_at: '2026-03-01T00:00:00Z',
  signed_in: true, last_seen_at: TWO_DAYS_AGO,
  profile: { job_title: 'Lecturer', about: '', qualification: 'MSc', university: '', graduation_year: null,
    field_of_study: '', phone: '', languages: ['en', 'ta'], other_language: '' },
  ...over,
})

const reviewerDetail = (p: admins.TeamPersonBlock, over: Record<string, unknown> = {}) => ({
  id: p.admin_id, name: p.name, email: p.email, role: 'reviewer', languages: ['ta', 'en'], open_now: 1,
  awaiting_review: 1, interviewing: 0, completed: 4, turnaround_days: 3, paused: false, paused_at: null,
  recommended: 3, declined: 1, rejected_after_review: 0, awaiting_qc: 0, created_at: p.joined_at,
  qualification: 'MSc', university: '', graduation_year: null, field_of_study: '', phone: '',
  share_phone_with_students: false, gifts: [], organisation_id: 1, programmes: [], reopens: [],
  is_active: true, deletable: false, work: { assigned_applications: 1 }, pausable: true, person: p, ...over,
}) as unknown as reviewers.AdminReviewerDetail

const KEYS = ['review', 'see_all', 'qc', 'spending']
const staffView = (p: admins.TeamPersonBlock, over: Partial<admins.StaffPermissionsView> = {}): admins.StaffPermissionsView => ({
  id: p.admin_id, name: p.name, role: 'admin', is_active: true, editable: true, preset: ['see_all'],
  permissions: ['see_all'], custom: false, keys: KEYS, email: p.email, created_at: p.joined_at ?? '',
  signed_in: true, paused: false, history: [], tables: p.tables, deletable: true, work: {}, person: p, ...over,
})

const mentorRow = (over: Partial<mentors.MentorRow> = {}): mentors.MentorRow => ({
  id: 3, name: 'Ravi Kumar', email: 'ravi@example.org', phone: '', status: 'active', area: '',
  languages: { en: 'fluent', ms: '', ta: '' }, other_language: '', invited_at: null, signed_in: true,
  last_seen_at: TWO_DAYS_AGO, deactivated_at: null, manageable: true, scholars_now: 1, staff_role: null,
  tables: ['mentors'], lead: false, meetings_90: 2, last_meeting: '2026-10-28', concerns_open: 0,
  deletable: false, work: { mentor_assignments: 1 }, ...over,
})
const mentorDetail = (p: admins.TeamPersonBlock, over: Partial<mentors.MentorDetail> = {}): mentors.MentorDetail => ({
  mentor: mentorRow(), mentoring_since: '2026-09-02T00:00:00Z', sees_scholars: true,
  figures: { scholars_now: 1, meetings_90: 2, average_gap_days: 14, concerns_raised: 0, concerns_open: 0,
    last_meeting: '2026-10-28' },
  current: [{ application_id: 104, name: 'Nur Aisyah', since: '2026-09-02T00:00:00Z', ended: null, meetings: 2,
    last_meeting: '2026-10-28', standing: 'performing', has_file: true, concern: null }],
  past: [], may_add: [], person: p, ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  viewer = { role: 'org_admin' }
  window.history.replaceState(null, '', '/')
  window.confirm = jest.fn(() => true)
})

const draw = async (entry: 'reviewer' | 'admin' | 'mentor', id: number, backTable: 'admins' | 'reviewers' | 'mentors') => {
  render(<TeamPersonPage entry={entry} id={id} backTable={backTable} />)
  await waitFor(() => expect(screen.getByTestId('person-header')).toBeTruthy())
}

/** What every person page shows, whoever they are (D9, M1, M3). */
function expectTheCommonPage(chips: string[]) {
  expect(screen.getAllByRole('tab').map((b) => b.textContent))
    .toEqual(['admin.person.tabProfile', 'admin.person.tabPermissions'])
  // D9: the tables as chips, and no role word anywhere on the Profile.
  expect(within(screen.getByTestId('person-tables')).getAllByText(/admin\.team\.chip\./).map((c) => c.textContent))
    .toEqual(chips)
  expect(document.body.textContent).not.toMatch(/admin\.role\.|admin\.reviewers\.role\./)
  // M1: Status · Joined · Last seen, in that order; relative, the exact time in the title.
  const facts = screen.getByTestId('person-facts')
  const order = ['person-status', 'person-joined', 'person-last-seen'].map((id) => within(facts).getByTestId(id))
  for (let i = 1; i < order.length; i++) {
    expect(order[i - 1].compareDocumentPosition(order[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  }
  const seen = within(facts).getByTestId('person-last-seen')
  expect(seen.textContent).toContain('admin.person.lastSeen')
  expect(seen.textContent).toContain('admin.person.seen.days')
  expect(seen.getAttribute('title')).toBe(formatDateTime(TWO_DAYS_AGO))
  // M3: an empty field reads Not given; the address is never a row.
  expect(screen.getByTestId('person-field-university').textContent).toBe('admin.reviewers.detail.phoneNone')
  expect(screen.queryByTestId('person-field-address')).toBeNull()
}

describe('one page per kind of person', () => {
  it('a reviewer: the Reviewer chip, Pause, the figures, outcomes and reopens; the editor on Permissions', async () => {
    const p = person()
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    await draw('reviewer', 5, 'reviewers')
    expectTheCommonPage(['admin.team.chip.reviewers'])
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
    expect(screen.getByTestId('reviewer-figures')).toBeTruthy()
    expect(screen.getByTestId('reviewer-outcomes')).toBeTruthy()
    expect(screen.getByTestId('reviewer-reopens')).toBeTruthy()
    expect(within(screen.getByTestId('person-action-row')).getByText('admin.revoke')).toBeTruthy()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()      // the reviewer detail carries the actions
    expect(mM.getMentorDetail).not.toHaveBeenCalled()
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'reviewer', preset: ['review'], permissions: ['review'] }))
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(await screen.findByTestId('permission-editor')).toBeTruthy()
  })

  it('an Admin: the Admin chip, no Pause, no reviewer parts; editable switches on Permissions', async () => {
    const p = person({ admin_id: 14, name: 'Arun Pillai', email: 'arun@example.org', tables: ['admins'] })
    mA.getStaffPermissions.mockResolvedValue(staffView(p))
    await draw('admin', 14, 'admins')
    expectTheCommonPage(['admin.team.chip.admins'])
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.queryByTestId('reviewer-figures')).toBeNull()
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(screen.getByTestId('person-back').getAttribute('href')).toBe('/admin/organisation/reviewers?tab=admins')
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    const editor = await screen.findByTestId('permission-editor')
    expect(within(editor).getAllByRole('switch').some((b) => !(b as HTMLButtonElement).disabled)).toBe(true)
    expect(screen.queryByTestId('perm-fixed')).toBeNull()
    expect(mA.getStaffPermissions).toHaveBeenCalledTimes(1)   // the card is handed the page's GET
  })

  it('a Finance person: the same page — the Admin chip, both tabs, no role word', async () => {
    const p = person({ admin_id: 15, name: 'Balan Kumar', email: 'balan@example.org', tables: ['admins'] })
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'finance', preset: ['spending'] }))
    await draw('admin', 15, 'admins')
    expectTheCommonPage(['admin.team.chip.admins'])
    expect(screen.queryByText('admin.role.finance')).toBeNull()
  })

  it('an organisation admin: the Admin (lead) chip; Permissions shows LOCKED switches under one line (M2)', async () => {
    const p = person({ admin_id: 1, name: 'Suresh Nair', email: 'suresh@example.org', tables: ['admins'], lead: true })
    viewer = { role: 'reviewer', is_super_admin: true }
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'org_admin', editable: false, permissions: ['see_all', 'spending'] }))
    await draw('admin', 1, 'admins')
    expectTheCommonPage(['admin.team.chip.lead'])
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect((await screen.findByTestId('perm-fixed')).textContent).toContain('admin.permEditor.fixed')
    const switches = screen.getAllByRole('switch')
    expect(switches.length).toBeGreaterThan(0)
    for (const b of switches) expect((b as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByText('admin.permEditor.save')).toBeNull()
  })

  it('a pure mentor: the Mentor chip, their figures and scholars, the area row; Revoke in the same place (M5)', async () => {
    const p = person({ admin_id: 9, mentor_id: 3, name: 'Ravi Kumar', email: 'ravi@example.org', tables: ['mentors'],
      mentor_only: true })
    mM.getMentorDetail.mockResolvedValue(mentorDetail(p))
    await draw('mentor', 3, 'mentors')
    expectTheCommonPage(['admin.team.chip.mentors'])
    expect(await screen.findByTestId('mentor-figures')).toBeTruthy()
    expect(screen.getByTestId('mentor-work')).toBeTruthy()
    expect(screen.getByTestId('person-field-area').textContent).toBe('admin.reviewers.detail.phoneNone')
    expect(within(screen.getByTestId('person-action-row')).getByTestId('mentor-person-actions')).toBeTruthy()
    expect(screen.getByTestId('person-back').getAttribute('href')).toBe('/admin/organisation/reviewers?tab=mentors')
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()      // a mentor holds no permissions
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    // Invitations I4 (merged with T3): the gifts they mentor in sit in the header card.
    expect(within(screen.getByTestId('person-header')).getByTestId('mentor-gifts')).toBeTruthy()
  })

  it('somebody in two tables (a reviewer who mentors): both chips and both tables\' parts (M6)', async () => {
    const p = person({ mentor_id: 3, tables: ['reviewers', 'mentors'] })
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    mM.getMentorDetail.mockResolvedValue(mentorDetail(p, { mentor: mentorRow({ staff_role: 'reviewer' }) }))
    await draw('reviewer', 5, 'reviewers')
    expect(await screen.findByTestId('mentor-work')).toBeTruthy()
    expectTheCommonPage(['admin.team.chip.reviewers', 'admin.team.chip.mentors'])
    expect(mM.getMentorDetail).toHaveBeenCalledWith(3, { token: 'tok' })
    for (const id of ['reviewer-figures', 'reviewer-outcomes', 'reviewer-reopens', 'mentor-figures']) {
      expect(screen.getByTestId(id)).toBeTruthy()
    }
    // Their actions are their STAFF actions (one row, once); the mentor ones are for a pure mentor only.
    expect(screen.queryByTestId('mentor-person-actions')).toBeNull()
    expect(screen.getAllByTestId('person-actions')).toHaveLength(1)
  })

  it('the same person through the mentor door: the reviewer detail is read by their staff id', async () => {
    const p = person({ mentor_id: 3, tables: ['reviewers', 'mentors'] })
    mM.getMentorDetail.mockResolvedValue(mentorDetail(p, { mentor: mentorRow({ staff_role: 'reviewer' }) }))
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    await draw('mentor', 3, 'mentors')
    await waitFor(() => expect(screen.getByTestId('reviewer-outcomes')).toBeTruthy())
    expect(mR.getReviewerDetail).toHaveBeenCalledWith(5, { token: 'tok' })
    expectTheCommonPage(['admin.team.chip.reviewers', 'admin.team.chip.mentors'])
  })
})

describe('D8: a pure mentor\'s Permissions tab is read-only', () => {
  const MENTOR = person({ admin_id: 9, mentor_id: 3, name: 'Ravi Kumar', email: 'ravi@example.org', tables: ['mentors'],
    mentor_only: true })

  it('says what a mentor sees, draws no switch, and offers Add to a table this viewer may add them to', async () => {
    mM.getMentorDetail.mockResolvedValue(mentorDetail(MENTOR, { may_add: ['admins', 'reviewers'] }))
    mA.getTeamCandidates.mockResolvedValue({ candidates: [
      { id: 9, name: 'Ravi Kumar', email: 'ravi@example.org', lead: false, mentor_only: true, tables: ['mentors'] },
      { id: 11, name: 'Someone Else', email: 'else@example.org', lead: false, mentor_only: false, tables: [] },
    ] } as never)
    mA.changeTeamTable.mockResolvedValue({ consequences: [] } as never)
    await draw('mentor', 3, 'mentors')
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    const tab = screen.getByTestId('mentor-only-permissions')
    expect(within(tab).getByText(/admin\.person\.mentorOnly\.students/)).toBeTruthy()
    expect(within(tab).getByText(/admin\.person\.mentorOnly\.scholars/)).toBeTruthy()   // sprint S1
    expect(within(tab).getByText(/admin\.person\.mentorOnly\.profile/)).toBeTruthy()
    expect(within(tab).queryByRole('switch')).toBeNull()
    expect(screen.queryByTestId('permission-editor')).toBeNull()
    fireEvent.click(within(tab).getByTestId('mentor-add-reviewers'))
    await waitFor(() => expect(mA.getTeamCandidates).toHaveBeenCalledWith('reviewers', { token: 'tok' }))
    // The Team page's own Add sheet, narrowed to this one person.
    const sheet = await screen.findByTestId('team-add-reviewers')
    await waitFor(() => expect(within(sheet).getByTestId('team-candidate-9')).toBeTruthy())
    expect(within(sheet).queryByTestId('team-candidate-11')).toBeNull()
    // Narrowed to one person, they come already picked: the dry run is asked for them alone.
    await waitFor(() => expect(mA.changeTeamTable).toHaveBeenCalledWith('reviewers', 9, 'add', true, { token: 'tok' }))
  })

  it('offers no Add path to a viewer who may not add (`may_add` empty)', async () => {
    viewer = { role: 'admin' }
    mM.getMentorDetail.mockResolvedValue(mentorDetail(MENTOR, { may_add: [] }))
    await draw('mentor', 3, 'mentors')
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    const tab = screen.getByTestId('mentor-only-permissions')
    expect(within(tab).queryByText(/admin\.person\.mentorOnly\.more/)).toBeNull()
    expect(within(tab).queryAllByRole('button')).toHaveLength(0)
  })

  it('opens on the tab from #permissions', async () => {
    window.history.replaceState(null, '', '/x#permissions')
    mM.getMentorDetail.mockResolvedValue(mentorDetail(MENTOR))
    await draw('mentor', 3, 'mentors')
    expect(screen.getByTestId('mentor-only-permissions')).toBeTruthy()
  })
})

describe('T3 review: a staff member who mentors, on the mentor route', () => {
  // An Admin who mentors — not a reviewer: no reviewer detail, the permissions view carries the actions.
  const ADMIN_MENTOR = person({ admin_id: 14, mentor_id: 3, name: 'Arun Pillai', email: 'arun@example.org',
    tables: ['admins', 'mentors'] })
  const drawAdminMentor = async (scholarsNow: number) => {
    mM.getMentorDetail.mockResolvedValue(mentorDetail(ADMIN_MENTOR, {
      mentor: mentorRow({ name: 'Arun Pillai', email: 'arun@example.org', staff_role: 'admin',
        scholars_now: scholarsNow }) }))
    mA.getStaffPermissions.mockResolvedValue(staffView(ADMIN_MENTOR))
    mA.revokeAdmin.mockResolvedValue({} as never)
    mM.mentorAction.mockResolvedValue({} as never)
    await draw('mentor', 3, 'mentors')
    await waitFor(() => expect(screen.getByTestId('mentor-work')).toBeTruthy())
    await waitFor(() => expect(screen.getByTestId('person-actions')).toBeTruthy())
  }

  it('reads as one page: both chips, the mentor parts, their staff actions and Remove from Mentors', async () => {
    await drawAdminMentor(2)
    expectTheCommonPage(['admin.team.chip.admins', 'admin.team.chip.mentors'])
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(mA.getStaffPermissions).toHaveBeenCalledWith(14, { token: 'tok' })
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.queryByTestId('reviewer-outcomes')).toBeNull()
    const row = screen.getByTestId('person-action-row')
    expect(within(row).getAllByTestId('person-actions')).toHaveLength(1)
    expect(within(row).queryByTestId('mentor-person-actions')).toBeNull()   // a pure mentor's pair only
    expect(within(row).getByTestId('mentor-person-stop').textContent).toBe('admin.mentors.action.stop')
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(await screen.findByTestId('permission-editor')).toBeTruthy()
  })

  it('Revoke says their scholars\' mentoring ends and Restore will not bring it back', async () => {
    await drawAdminMentor(2)
    fireEvent.click(within(screen.getByTestId('person-action-row')).getByText('admin.revoke'))
    const asked = (window.confirm as jest.Mock).mock.calls[0][0] as string
    expect(asked).toContain('admin.reviewers.revokeConfirm')
    expect(asked).toContain('admin.person.revokeEndsMentoring {"n":"2"}')
    await waitFor(() => expect(mA.revokeAdmin).toHaveBeenCalledWith(14, 'revoke', { token: 'tok' }))
  })

  it('with no scholars now, Revoke keeps the plain confirm', async () => {
    await drawAdminMentor(0)
    fireEvent.click(within(screen.getByTestId('person-action-row')).getByText('admin.revoke'))
    expect((window.confirm as jest.Mock).mock.calls[0][0]).not.toContain('admin.person.revokeEndsMentoring')
  })

  it('Remove from Mentors asks with the table\'s words, then sends `stop` and reads the page again', async () => {
    await drawAdminMentor(2)
    const calls = mM.getMentorDetail.mock.calls.length
    fireEvent.click(screen.getByTestId('mentor-person-stop'))
    expect((window.confirm as jest.Mock).mock.calls[0][0]).toBe('admin.mentors.confirm.stop {"name":"Arun Pillai"}')
    await waitFor(() => expect(mM.mentorAction).toHaveBeenCalledWith(3, 'stop', { token: 'tok' }))
    await waitFor(() => expect(mM.getMentorDetail.mock.calls.length).toBeGreaterThan(calls))
  })

  it('an `admin` reader: no actions, and the background fields the server withheld are not drawn (fix 1)', async () => {
    viewer = { role: 'admin' }
    const p = { ...ADMIN_MENTOR, profile_full: false,
      profile: { ...ADMIN_MENTOR.profile, job_title: '', qualification: '' } }
    mM.getMentorDetail.mockResolvedValue(mentorDetail(p, {
      mentor: mentorRow({ staff_role: 'admin', manageable: false }) }))
    await draw('mentor', 3, 'mentors')
    await waitFor(() => expect(screen.getByTestId('mentor-work')).toBeTruthy())
    expect(screen.queryByTestId('person-action-row')).toBeNull()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    for (const k of ['jobTitle', 'about', 'qualification', 'university', 'fieldOfStudy', 'graduationYear']) {
      expect(screen.queryByTestId(`person-field-${k}`)).toBeNull()
    }
    for (const k of ['email', 'phone', 'languages', 'area']) expect(screen.getByTestId(`person-field-${k}`)).toBeTruthy()
  })
})

describe('M1: Last seen', () => {
  it('reads Invited when no sign-in is recorded, and "not recorded" when signed in without a time', async () => {
    const p = person({ tables: ['admins'], signed_in: false, last_seen_at: null })
    mA.getStaffPermissions.mockResolvedValue(staffView(p))
    const { unmount } = render(<TeamPersonPage entry="admin" id={5} backTable="admins" />)
    expect((await screen.findByTestId('person-invited')).textContent).toBe('admin.person.invited')
    expect(screen.queryByTestId('person-last-seen')).toBeNull()
    unmount()
    mA.getStaffPermissions.mockResolvedValue(staffView({ ...p, signed_in: true }))
    await draw('admin', 5, 'admins')
    expect(screen.getByTestId('person-last-seen').textContent).toBe('admin.person.seenUnknown')
  })
})

describe('the gates', () => {
  it.each(['finance', 'admin'])('a %s reader: both tabs; Permissions holds one line and asks nothing (Q1); no actions',
    async (r) => {
      viewer = { role: r }
      const p = person()
      mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
      await draw('reviewer', 5, 'reviewers')
      expect(screen.getAllByRole('tab').map((b) => b.textContent))
        .toEqual(['admin.person.tabProfile', 'admin.person.tabPermissions'])
      expect(screen.getByTestId('person-profile')).toBeTruthy()
      expect(screen.queryByTestId('person-action-row')).toBeNull()
      fireEvent.click(screen.getByText('admin.person.tabPermissions'))
      expect(screen.getByTestId('person-perm-not-allowed').textContent).toBe('admin.person.notAllowed')
      expect(screen.queryByTestId('permission-editor')).toBeNull()
      expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    })

  it('a 404 is the shared not-found state; any other failure says the page could not load', async () => {
    mR.getReviewerDetail.mockRejectedValue(Object.assign(new Error('nope'), { status: 404 }))
    const { unmount } = render(<TeamPersonPage entry="reviewer" id={5} backTable="reviewers" />)
    await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
    expect(screen.queryByText('admin.person.loadFailed')).toBeNull()
    unmount()
    mR.getReviewerDetail.mockRejectedValue(Object.assign(new Error('boom'), { status: 500 }))
    render(<TeamPersonPage entry="reviewer" id={5} backTable="reviewers" />)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.person.loadFailed')
    expect(screen.queryByTestId('record-not-found')).toBeNull()
  })

  it('an id that names nobody is not found, and asks nothing', async () => {
    render(<TeamPersonPage entry="reviewer" id={0} backTable="reviewers" />)
    await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
  })

  it('an api without the person block says it could not load, never a half-drawn page', async () => {
    mR.getReviewerDetail.mockResolvedValue({ ...reviewerDetail(person()), person: undefined })
    render(<TeamPersonPage entry="reviewer" id={5} backTable="reviewers" />)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.person.loadFailed')
    expect(screen.queryByTestId('person-header')).toBeNull()
  })

  it.each([[false], [undefined]])('offers no Pause when `pausable` is %p (missing means no)', async (pausable) => {
    const p = person()
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p, { pausable }))
    await draw('reviewer', 5, 'reviewers')
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(within(screen.getByTestId('person-action-row')).getByText('admin.revoke')).toBeTruthy()
  })

  it('a mentor route the viewer may not read: refused, and nothing asked', async () => {
    viewer = { role: 'finance' }
    render(<TeamPersonPage entry="mentor" id={3} backTable="mentors" />)
    expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
    expect(mM.getMentorDetail).not.toHaveBeenCalled()
  })
})

describe('at 360 px', () => {
  it('lets the header lines wrap and keeps every control at 44 px on a phone', async () => {
    const p = person()
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    await draw('reviewer', 5, 'reviewers')
    expect(screen.getByTestId('person-facts').className).toContain('flex-wrap')
    expect(screen.getByTestId('person-action-row').className).toContain('flex-wrap')
    expect(screen.getByRole('heading', { level: 1 }).className).toContain('[overflow-wrap:anywhere]')
    expect(screen.getByTestId('person-back').className).toContain('max-md:min-h-11')
    expect(screen.getByText('admin.reviewers.detail.pause').className).toContain('max-md:min-h-11')
  })
})
