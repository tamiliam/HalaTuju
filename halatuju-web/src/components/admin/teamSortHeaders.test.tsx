/**
 * @jest-environment jsdom
 *
 * Sprint M2d A2 (owner, 2026-11-13): Members, Mentors and Invitations — every heading sorts except Action,
 * and "Not recorded" goes last in both directions. Reviewers and Admins are
 * `app/admin/organisation/team/page.sort.test.tsx`'s; the rules themselves `lib/__tests__/teamSort.test.ts`'s.
 * Synthetic names only.
 */
import { fireEvent, render, waitFor, within } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import StaffList from './StaffList'
import InvitationsTable from './InvitationsTable'
import TeamMentorsScreen from '@/components/mentors/MentorsAdmin'
import { AlsoIn } from '@/components/admin/TeamTables'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const SEEN: Array<[number, string, string | null]> = [
  [1, 'Zara', null], [2, 'Old', '2026-01-01T00:00:00Z'], [3, 'Ana', null], [4, 'New', '2026-11-01T00:00:00Z'],
]
const NO_WORK = { admins: {}, reviewers: { open_cases: 0 }, mentors: { scholars_now: 0 } }
const member = ([id, name, last_seen_at]: [number, string, string | null]): api.StaffRow => ({
  id, kind: 'staff', mentor_id: null, name: `${name} Test`, photo_url: null, last_seen_at, groups: ['reviewers'],
  lead: false, suspended: false, manageable: true, work: NO_WORK, deletable: false, delete_never: null,
  delete_outcome: null, revocable: true,
})
const mentor = ([id, name, last_seen_at]: [number, string, string | null]) => ({
  id, name: `${name} Test`, email: `m${id}@example.org`, status: 'active', area: '', languages: {},
  // Signed in, all of them (an arrived mentor is listed): a sign-in that predates the column has no date.
  other_language: '', invited_at: null, signed_in: true, last_seen_at, deactivated_at: null,
  manageable: true, scholars_now: 0, staff_role: null, tables: ['mentors'], lead: false, meetings_90: 0,
  last_meeting: null, concerns_open: 0,
}) as unknown as api.MentorRow
const invite = (id: number, name: string, status: api.InvitationRow['status']) => ({
  id, name, email: `i${id}@example.org`, role: 'reviewer', status, sent_at: null, send_count: 1, last_send_ok: null,
  last_send_error: '', accepted_at: null, admin_id: id, is_active: true, paused: false, programme: '',
  programme_name: '',
}) as api.InvitationRow

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getStaffList.mockResolvedValue({ staff: SEEN.map(member) })
  mockApi.getMentors.mockResolvedValue({ mentors: SEEN.map(mentor), counts: { active: 4, invited: 0, inactive: 0 },
    can_invite: true })
  window.confirm = jest.fn(() => true)
})

const table = () => document.querySelector('table') as HTMLElement
const headings = () => Array.from(table().querySelectorAll('thead th')) as HTMLElement[]
const heading = (label: string) => within(table()).getByRole('button', { name: label })
const order = () => Array.from(table().querySelectorAll('tbody tr'))
  .map((tr) => ['Zara', 'Old', 'Ana', 'New', 'Cut', 'Late', 'Wait'].find((n) => tr.textContent?.includes(n)))

function sortableExceptAction(labels: string[]) {
  const ths = headings()
  expect(ths.map((th) => th.textContent?.replace(/[▲▼]/g, ''))).toEqual([...labels, 'admin.actionHeader'])
  expect(ths[ths.length - 1].querySelector('button')).toBeNull()
  for (const th of ths.slice(0, -1)) {
    expect(th.querySelectorAll('button')).toHaveLength(1)
    expect(th.hasAttribute('aria-sort')).toBe(true)
  }
}

function notRecordedLastBothWays() {
  fireEvent.click(heading('admin.reviewers.colLastSeen'))
  expect(order()).toEqual(['New', 'Old', 'Ana', 'Zara'])   // first click: the newest first
  fireEvent.click(heading('admin.reviewers.colLastSeen'))
  expect(order()).toEqual(['Old', 'New', 'Ana', 'Zara'])
}

describe('Members', () => {
  const draw = async () => {
    render(<StaffList token="tok" canManage viewerSuper={false} />)
    await waitFor(() => expect(table()).toBeTruthy())
  }

  it('every heading is a sort button except Action', async () => {
    await draw()
    sortableExceptAction(['admin.nameHeader', 'admin.staff.colGroups', 'admin.reviewers.colStatus',
      'admin.reviewers.colLastSeen'])
  })

  it('Last seen: "Not recorded" last both ways', async () => {
    await draw()
    notRecordedLastBothWays()
  })
})

describe('Mentors', () => {
  const draw = async () => {
    render(<TeamMentorsScreen AlsoIn={AlsoIn} adding={false} onAddClose={() => {}} />)
    await waitFor(() => expect(table()?.querySelectorAll('tbody tr').length).toBe(4))
  }

  it('every heading is a sort button except Action', async () => {
    await draw()
    const K = 'admin.mentors'
    sortableExceptAction(['admin.nameHeader', 'admin.team.colAlsoIn', `${K}.col.scholarsNow`, `${K}.col.meetings90`,
      `${K}.col.lastMeeting`, `${K}.col.concernsOpen`, 'admin.statusHeader', 'admin.reviewers.colLastSeen'])
  })

  it('Last seen: "Not recorded" last both ways', async () => {
    await draw()
    notRecordedLastBothWays()
  })
})

describe('Invitations', () => {
  const ROWS = [invite(1, 'Wait Test', 'no_reply'), invite(2, 'Cut Test', 'revoked'), invite(3, 'Late Test', 'expired')]

  it('every heading is a sort button except Action, the lead column too', () => {
    render(<InvitationsTable rows={ROWS} canAct onResend={() => {}}
      lead={{ header: 'Source', cell: (r) => r.email, sortText: (r) => r.email }} />)
    sortableExceptAction(['Source', 'admin.nameHeader', 'admin.emailHeader', 'admin.roleHeader',
      'admin.statusHeader'])
  })

  it('Status reads the exception first: cancelled, expired, then no reply', () => {
    render(<InvitationsTable rows={ROWS} canAct onResend={() => {}} />)
    expect(order()).toEqual(['Wait', 'Cut', 'Late'])          // the server's order until a click
    fireEvent.click(heading('admin.statusHeader'))
    expect(order()).toEqual(['Cut', 'Late', 'Wait'])
  })
})
