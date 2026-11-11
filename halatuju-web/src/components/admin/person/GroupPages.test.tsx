/**
 * @jest-environment jsdom
 *
 * Sprint M2a (owner U2, 2026-11-11): one page per GROUP — `AdminGroupPage`, `ReviewerGroupPage`,
 * `MentorGroupPage`. These are T3's `TeamPersonPage` tests moved onto the page each behaviour now lives on;
 * every rule they pinned is still pinned here (the fence messages, not found, `#permissions`, read-only for a
 * fellow organisation admin, a pure mentor's Permissions, Remove from Mentors, Last seen, the phone classes).
 * What M2a CHANGED (U2 supersedes T3's M6): a page reads ONE detail and draws only its own group's parts; a
 * staff mentor's mentor page has no Permissions tab. `GroupPages.split.test.tsx` pins the split itself.
 *
 * Every page still shows: under the name the groups they sit in as chips and NO ROLE WORD (D9); Status ·
 * Joined · Last seen, Last seen relative with the exact time in `title` (M1); every About field, "Not given"
 * where it is empty, never an address (M3).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AdminGroupPage from './AdminGroupPage'
import ReviewerGroupPage from './ReviewerGroupPage'
import MentorGroupPage from './MentorGroupPage'
import * as admins from '@/lib/admin-api/admins'
import * as mentors from '@/lib/admin-api/mentors'
import * as reviewers from '@/lib/admin-api/reviewers'
import { formatDateTime } from '@/lib/formatDate'
import { TWO_DAYS_AGO, mentorDetail, mentorRow, person, reviewerDetail, staffView } from '@/test/teamPerson'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    <a href={href} {...rest}>{children}</a>,
}))
const mockReplace = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: mockReplace }) }))
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

beforeEach(() => {
  jest.clearAllMocks()
  viewer = { role: 'org_admin' }
  window.history.replaceState(null, '', '/')
  window.confirm = jest.fn(() => true)
})

type Group = 'admins' | 'reviewers' | 'mentors'
const PAGE = { admins: AdminGroupPage, reviewers: ReviewerGroupPage, mentors: MentorGroupPage }
const view = (group: Group, id: number) => { const Page = PAGE[group]; return render(<Page id={id} />) }
const draw = async (group: Group, id: number) => {
  view(group, id)
  await waitFor(() => expect(screen.getByTestId('person-header')).toBeTruthy())
}
const BOTH_TABS = ['admin.person.tabProfile', 'admin.person.tabPermissions']

/** What every group page shows, whoever they are (D9, M1, M3). */
function expectTheCommonPage(chips: string[], tabs: string[] = BOTH_TABS) {
  expect(screen.queryAllByRole('tab').map((b) => b.textContent)).toEqual(tabs)
  // D9: the groups as chips, and no role word anywhere on the page.
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
  // U3 + M3: About on every page; an empty field reads Not given; the address is never a row.
  expect(screen.getByTestId('person-profile')).toBeTruthy()
  expect(screen.getByTestId('person-field-university').textContent).toBe('admin.reviewers.detail.phoneNone')
  expect(screen.queryByTestId('person-field-address')).toBeNull()
}

describe('one page per group', () => {
  it('a reviewer: the Reviewer chip, Pause, the figures, outcomes and reopens; the editor on Permissions', async () => {
    const p = person()
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    await draw('reviewers', 5)
    expectTheCommonPage(['admin.team.chip.reviewers'])
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
    expect(screen.getByTestId('reviewer-figures')).toBeTruthy()
    expect(screen.getByTestId('reviewer-outcomes')).toBeTruthy()
    expect(screen.getByTestId('reviewer-reopens')).toBeTruthy()
    expect(screen.getByTestId('person-back').getAttribute('href')).toBe('/admin/organisation/team?tab=reviewers')
    // M1b (owner O3): Suspend and Delete are on Team -> Staff only — the page keeps Pause.
    expect(within(screen.getByTestId('person-action-row')).queryByText('admin.revoke')).toBeNull()
    expect(screen.queryByText('admin.delete')).toBeNull()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    expect(mM.getMentorDetail).not.toHaveBeenCalled()
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'reviewer', preset: ['review'], permissions: ['review'] }))
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(await screen.findByTestId('permission-editor')).toBeTruthy()
  })

  it('an Admin: the Admin chip, no Pause, no reviewer parts; editable switches on Permissions', async () => {
    const p = person({ admin_id: 14, name: 'Arun Pillai', email: 'arun@example.org', tables: ['admins'] })
    mA.getStaffPermissions.mockResolvedValue(staffView(p))
    await draw('admins', 14)
    expectTheCommonPage(['admin.team.chip.admins'])
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.queryByTestId('reviewer-figures')).toBeNull()
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(screen.getByTestId('person-back').getAttribute('href')).toBe('/admin/organisation/team?tab=admins')
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    const editor = await screen.findByTestId('permission-editor')
    expect(within(editor).getAllByRole('switch').some((b) => !(b as HTMLButtonElement).disabled)).toBe(true)
    expect(screen.queryByTestId('perm-fixed')).toBeNull()
    expect(mA.getStaffPermissions).toHaveBeenCalledTimes(1)   // the card is handed the page's GET
  })

  it('a Finance person: the same admin page — the Admin chip, both tabs, no role word', async () => {
    const p = person({ admin_id: 15, name: 'Balan Kumar', email: 'balan@example.org', tables: ['admins'] })
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'finance', preset: ['spending'] }))
    await draw('admins', 15)
    expectTheCommonPage(['admin.team.chip.admins'])
    expect(screen.queryByText('admin.role.finance')).toBeNull()
  })

  it('an organisation admin: the Admin (lead) chip; Permissions shows LOCKED switches under one line (M2)', async () => {
    const p = person({ admin_id: 1, name: 'Suresh Nair', email: 'suresh@example.org', tables: ['admins'], lead: true })
    viewer = { role: 'reviewer', is_super_admin: true }
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'org_admin', editable: false, permissions: ['see_all', 'spending'] }))
    await draw('admins', 1)
    expectTheCommonPage(['admin.team.chip.lead'])
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect((await screen.findByTestId('perm-fixed')).textContent).toContain('admin.permEditor.fixed')
    const switches = screen.getAllByRole('switch')
    expect(switches.length).toBeGreaterThan(0)
    for (const b of switches) expect((b as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByText('admin.permEditor.save')).toBeNull()
  })

  it('a pure mentor: the Mentor chip, their figures and scholars, the area row; no actions (M1b, O3)', async () => {
    const p = person({ admin_id: 9, mentor_id: 3, name: 'Ravi Kumar', email: 'ravi@example.org', tables: ['mentors'],
      mentor_only: true })
    mM.getMentorDetail.mockResolvedValue(mentorDetail(p))
    await draw('mentors', 3)
    expectTheCommonPage(['admin.team.chip.mentors'])
    expect(await screen.findByTestId('mentor-figures')).toBeTruthy()
    expect(screen.getByTestId('mentor-work')).toBeTruthy()
    expect(screen.getByTestId('person-field-area').textContent).toBe('admin.reviewers.detail.phoneNone')
    expect(screen.queryByTestId('person-action-row')).toBeNull()        // Suspend and Delete: Team -> Staff
    expect(screen.getByTestId('person-back').getAttribute('href')).toBe('/admin/organisation/team?tab=mentors')
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()      // a mentor holds no permissions
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    // Invitations I4 (merged with T3): the gifts they mentor in sit in the header card.
    expect(within(screen.getByTestId('person-header')).getByTestId('mentor-gifts')).toBeTruthy()
  })

  it('a reviewer who mentors, on the mentor page: the mentor parts only, Remove from Mentors greyed (O17, O18)', async () => {
    const p = person({ mentor_id: 3, tables: ['reviewers', 'mentors'] })
    mM.getMentorDetail.mockResolvedValue(mentorDetail(p, { mentor: mentorRow({ staff_role: 'reviewer' }) }))
    await draw('mentors', 3)
    expect(await screen.findByTestId('mentor-work')).toBeTruthy()
    // A staff mentor's mentor page has no Permissions tab (U2: mentoring is not a permission).
    expectTheCommonPage(['admin.team.chip.reviewers', 'admin.team.chip.mentors'], [])
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    for (const id of ['reviewer-figures', 'reviewer-outcomes', 'reviewer-reopens']) {
      expect(screen.queryByTestId(id)).toBeNull()
    }
    const row = screen.getByTestId('person-action-row')
    expect(within(row).getByTestId('mentor-person-stop-greyed')).toBeTruthy()
    expect(within(row).queryByText('admin.revoke')).toBeNull()
    expect(within(row).queryByText('admin.delete')).toBeNull()
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
    await draw('mentors', 3)
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
    await draw('mentors', 3)
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    const tab = screen.getByTestId('mentor-only-permissions')
    expect(within(tab).queryByText(/admin\.person\.mentorOnly\.more/)).toBeNull()
    expect(within(tab).queryAllByRole('button')).toHaveLength(0)
  })

  it('opens on the tab from #permissions', async () => {
    window.history.replaceState(null, '', '/x#permissions')
    mM.getMentorDetail.mockResolvedValue(mentorDetail(MENTOR))
    await draw('mentors', 3)
    expect(screen.getByTestId('mentor-only-permissions')).toBeTruthy()
  })
})

describe('a staff member who mentors, on the mentor page (T3 review, M1b)', () => {
  // An Admin who mentors — the mentor page reads the mentor detail alone (U2).
  const ADMIN_MENTOR = person({ admin_id: 14, mentor_id: 3, name: 'Arun Pillai', email: 'arun@example.org',
    tables: ['admins', 'mentors'] })
  const drawAdminMentor = async (scholarsNow: number) => {
    mM.getMentorDetail.mockResolvedValue(mentorDetail(ADMIN_MENTOR, {
      mentor: mentorRow({ name: 'Arun Pillai', email: 'arun@example.org', staff_role: 'admin',
        scholars_now: scholarsNow }) }))
    mM.mentorAction.mockResolvedValue({} as never)
    await draw('mentors', 3)
    await waitFor(() => expect(screen.getByTestId('mentor-work')).toBeTruthy())
    await waitFor(() => expect(screen.getByTestId('person-action-row')).toBeTruthy())
  }

  it('the mentor parts and Remove from Mentors — no Suspend, no Delete (O3), no Permissions tab', async () => {
    await drawAdminMentor(0)
    expectTheCommonPage(['admin.team.chip.admins', 'admin.team.chip.mentors'], [])
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.queryByTestId('reviewer-outcomes')).toBeNull()
    const row = screen.getByTestId('person-action-row')
    expect(within(row).getByTestId('mentor-person-stop').textContent).toBe('admin.mentors.action.stop')
    expect(within(row).queryByText('admin.revoke')).toBeNull()
    expect(within(row).queryByText('admin.delete')).toBeNull()
    expect(screen.queryByText('admin.person.tabPermissions')).toBeNull()
    expect(screen.queryByTestId('permission-editor')).toBeNull()
  })

  it('greys Remove from Mentors while they mentor scholars, the count in its tip (O17, O18)', async () => {
    await drawAdminMentor(2)
    const b = within(screen.getByTestId('mentor-person-stop-greyed')).getByText('admin.mentors.action.stop')
    expect(b.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent)
      .toBe('admin.refusal.has_scholars.many {"n":"2"}')
    fireEvent.click(b)
    expect(mM.mentorAction).not.toHaveBeenCalled()
  })

  it('Remove from Mentors asks with the table\'s words, then sends `stop` and reads the page again', async () => {
    await drawAdminMentor(0)
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
    await draw('mentors', 3)
    await waitFor(() => expect(screen.getByTestId('mentor-work')).toBeTruthy())
    expect(screen.queryByTestId('person-action-row')).toBeNull()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    for (const k of ['jobTitle', 'about', 'qualification', 'university', 'fieldOfStudy', 'graduationYear']) {
      expect(screen.queryByTestId(`person-field-${k}`)).toBeNull()
    }
    for (const k of ['email', 'phone', 'languages', 'area']) expect(screen.getByTestId(`person-field-${k}`)).toBeTruthy()
  })
})

describe('M1b (owner O10, O12): read-only for a fellow organisation admin; one group\'s permissions', () => {
  const LEAD = person({ admin_id: 2, mentor_id: 4, name: 'Meena Example', email: 'meena@example.test',
    tables: ['admins', 'reviewers', 'mentors'], lead: true })

  it('a fellow organisation admin\'s admin page: no actions, no Pause, permissions shown not edited', async () => {
    mA.getStaffPermissions.mockResolvedValue(staffView(LEAD, { role: 'org_admin', editable: false, manageable: false,
      permissions: ['see_all', 'review'] } as Partial<admins.StaffPermissionsView>))
    await draw('admins', 2)
    expect(screen.queryByTestId('person-action-row')).toBeNull()
    expect(screen.queryByRole('button', { name: /admin\.revoke|admin\.delete|admin\.restore/ })).toBeNull()
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(await screen.findByTestId('perm-fixed')).toBeTruthy()
    for (const b of screen.getAllByRole('switch')) expect((b as HTMLButtonElement).disabled).toBe(true)
    expect(screen.queryByText('admin.permEditor.save')).toBeNull()
  })

  it('the same fellow on the reviewer page: no Pause and no action row either', async () => {
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(LEAD, { role: 'org_admin', pausable: true }))
    await draw('reviewers', 2)
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.queryByTestId('person-action-row')).toBeNull()
  })

  it('the same fellow on the mentor page: no Remove from Mentors (the mentor row\'s `manageable` is not enough)', async () => {
    mM.getMentorDetail.mockResolvedValue(mentorDetail(LEAD, {
      mentor: mentorRow({ id: 4, staff_role: 'org_admin', scholars_now: 0, manageable: true }) }))
    await draw('mentors', 4)
    await waitFor(() => expect(screen.getByTestId('mentor-work')).toBeTruthy())
    expect(screen.queryByTestId('person-action-row')).toBeNull()
  })

  it('a super still manages that organisation admin (Pause offered; Remove from Mentors offered)', async () => {
    viewer = { role: 'reviewer', is_super_admin: true }
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(LEAD, { role: 'org_admin', pausable: true }))
    const { unmount } = view('reviewers', 2)
    expect(await screen.findByText('admin.reviewers.detail.pause')).toBeTruthy()
    unmount()
    mM.getMentorDetail.mockResolvedValue(mentorDetail(LEAD, {
      mentor: mentorRow({ id: 4, staff_role: 'org_admin', scholars_now: 0, manageable: true }) }))
    await draw('mentors', 4)
    expect(await screen.findByTestId('mentor-person-stop')).toBeTruthy()
  })

  it('the admin page\'s Permissions draws ONLY the Admins section (O12)', async () => {
    const p = person({ admin_id: 14, name: 'Arun Pillai', email: 'arun@example.org', tables: ['admins', 'reviewers'] })
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { permissions: ['see_all', 'review'] }))
    await draw('admins', 14)
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(await screen.findByTestId('perm-section-admins')).toBeTruthy()
    expect(screen.queryByTestId('perm-section-reviewers')).toBeNull()
  })

  it('the reviewer page\'s, ONLY the Reviewers section (O12)', async () => {
    const p = person({ tables: ['admins', 'reviewers'] })
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    mA.getStaffPermissions.mockResolvedValue(staffView(p, { role: 'reviewer', permissions: ['see_all', 'review'] }))
    await draw('reviewers', 5)
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(await screen.findByTestId('perm-section-reviewers')).toBeTruthy()
    expect(screen.queryByTestId('perm-section-admins')).toBeNull()
  })
})

describe('M1: Last seen', () => {
  it('reads Invited when no sign-in is recorded, and "not recorded" when signed in without a time', async () => {
    const p = person({ tables: ['admins'], signed_in: false, last_seen_at: null })
    mA.getStaffPermissions.mockResolvedValue(staffView(p))
    const { unmount } = view('admins', 5)
    expect((await screen.findByTestId('person-invited')).textContent).toBe('admin.person.invited')
    expect(screen.queryByTestId('person-last-seen')).toBeNull()
    unmount()
    mA.getStaffPermissions.mockResolvedValue(staffView({ ...p, signed_in: true }))
    await draw('admins', 5)
    expect(screen.getByTestId('person-last-seen').textContent).toBe('admin.person.seenUnknown')
  })
})

describe('the gates', () => {
  it.each(['finance', 'admin'])('a %s reader: both tabs; Permissions holds one line and asks nothing (Q1); no actions',
    async (r) => {
      viewer = { role: r }
      const p = person()
      mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
      await draw('reviewers', 5)
      expect(screen.getAllByRole('tab').map((b) => b.textContent)).toEqual(BOTH_TABS)
      expect(screen.getByTestId('person-profile')).toBeTruthy()
      expect(screen.queryByTestId('person-action-row')).toBeNull()
      fireEvent.click(screen.getByText('admin.person.tabPermissions'))
      expect(screen.getByTestId('person-perm-not-allowed').textContent).toBe('admin.person.notAllowed')
      expect(screen.queryByTestId('permission-editor')).toBeNull()
      expect(mA.getStaffPermissions).not.toHaveBeenCalled()
    })

  it.each(['finance', 'admin'])('a %s reader on an admin page: "only an organisation admin", and nothing asked', (r) => {
    viewer = { role: r }
    view('admins', 14)
    expect(screen.getByText('admin.person.notAllowed')).toBeTruthy()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
  })

  it('a 404 is the shared not-found state; any other failure says the page could not load', async () => {
    mR.getReviewerDetail.mockRejectedValue(Object.assign(new Error('nope'), { status: 404 }))
    const { unmount } = view('reviewers', 5)
    await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
    expect(screen.queryByText('admin.person.loadFailed')).toBeNull()
    unmount()
    mR.getReviewerDetail.mockRejectedValue(Object.assign(new Error('boom'), { status: 500 }))
    view('reviewers', 5)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.person.loadFailed')
    expect(screen.queryByTestId('record-not-found')).toBeNull()
  })

  it('an id that names nobody is not found, and asks nothing', async () => {
    view('reviewers', 0)
    await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
  })

  it('an api without the person block says it could not load, never a half-drawn page', async () => {
    mR.getReviewerDetail.mockResolvedValue({ ...reviewerDetail(person()), person: undefined })
    view('reviewers', 5)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.person.loadFailed')
    expect(screen.queryByTestId('person-header')).toBeNull()
  })

  it.each([[false], [undefined]])('offers no Pause when `pausable` is %p (missing means no)', async (pausable) => {
    const p = person()
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p, { pausable }))
    await draw('reviewers', 5)
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.queryByText('admin.revoke')).toBeNull()
  })

  it('a mentor page the viewer may not read: refused, and nothing asked', () => {
    viewer = { role: 'finance' }
    view('mentors', 3)
    expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
    expect(mM.getMentorDetail).not.toHaveBeenCalled()
  })
})

describe('at 360 px', () => {
  it('lets the header lines wrap and keeps every control at 44 px on a phone', async () => {
    const p = person({ mentor_id: 3, tables: ['reviewers', 'mentors'] })
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(p))
    await draw('reviewers', 5)
    expect(screen.getByTestId('person-facts').className).toContain('flex-wrap')
    expect(screen.getByTestId('person-action-row').className).toContain('flex-wrap')
    expect(screen.getByRole('heading', { level: 1 }).className).toContain('[overflow-wrap:anywhere]')
    expect(screen.getByTestId('person-back').className).toContain('max-md:min-h-11')
    expect(screen.getByText('admin.reviewers.detail.pause').className).toContain('max-md:min-h-11')
    // U4: a chip that links is a 44 px target on a phone, the pill inside it.
    const chip = screen.getByTestId('chip-link-mentors')
    expect(chip.className).toContain('max-md:min-h-11')
    expect(chip.className).toContain('max-md:min-w-11')
  })
})
