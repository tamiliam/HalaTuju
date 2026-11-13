/**
 * Sprint M2d A2 (owner, 2026-11-13): the rules every Team table sorts by — ties by name, "Not recorded"
 * last in BOTH directions, "Also in" by the words shown, Status in the Members table's order. The rendered
 * headers have their own tests (`components/admin/teamSortHeaders.test.tsx`, `team/page.sort.test.tsx`).
 * No real people: every name here is synthetic.
 */
import type { AdminReviewer, StaffRow } from '@/lib/admin-api'
import { sortMembers } from '@/lib/memberTable'
import { sortReviewers, statusRank } from '@/lib/reviewerTable'
import { sortRows } from '@/lib/tableView'
import {
  STAFF_STATUS_RANK, alsoInWords, byName, lastSeenColumn, sortTeamRows, staffStatusRank, teamChipLabel,
} from '@/lib/teamSort'

const t = (k: string) => k
const names = (rows: { name: string }[]) => rows.map((r) => r.name)

const member = (name: string, last_seen_at: string | null, over: Partial<StaffRow> = {}) => ({
  id: name.length, kind: 'staff', mentor_id: null, name, photo_url: null, last_seen_at, groups: [], lead: false,
  suspended: false, manageable: true, work: { admins: {}, reviewers: { open_cases: 0 }, mentors: { scholars_now: 0 } },
  deletable: false, delete_never: null, delete_outcome: null, revocable: true, ...over,
}) as StaffRow

const reviewer = (name: string, over: Partial<AdminReviewer> = {}) => ({
  id: name.length, name, email: '', role: 'reviewer', languages: [], open_now: 0, awaiting_review: 0, interviewing: 0,
  completed: 0, turnaround_days: null, paused: false, paused_at: null, is_active: true, last_seen_at: null,
  tables: ['reviewers'], ...over,
}) as unknown as AdminReviewer

// Two never seen, given in the WRONG name order, so a test only passes if the tie really is by name.
const SEEN = [
  member('Zara Test', null), member('Old Test', '2026-01-01T00:00:00Z'), member('Ana Test', null),
  member('New Test', '2026-11-01T00:00:00Z'),
]

describe('Last seen: "Not recorded" goes LAST in both directions', () => {
  it('Members, ascending and descending', () => {
    expect(names(sortMembers(SEEN, 'lastSeen', 'asc'))).toEqual(['Old Test', 'New Test', 'Ana Test', 'Zara Test'])
    expect(names(sortMembers(SEEN, 'lastSeen', 'desc'))).toEqual(['New Test', 'Old Test', 'Ana Test', 'Zara Test'])
  })

  it('Reviewers, ascending and descending', () => {
    const rows = SEEN.map((m) => reviewer(m.name, { last_seen_at: m.last_seen_at }))
    expect(names(sortReviewers(rows, 'lastSeen', 'asc'))).toEqual(['Old Test', 'New Test', 'Ana Test', 'Zara Test'])
    expect(names(sortReviewers(rows, 'lastSeen', 'desc'))).toEqual(['New Test', 'Old Test', 'Ana Test', 'Zara Test'])
  })

  it('the shared column the Admins and Mentors tables use', () => {
    const cols = { lastSeen: lastSeenColumn<StaffRow>() }
    for (const dir of ['asc', 'desc'] as const) {
      expect(names(sortTeamRows(SEEN, cols, { key: 'lastSeen', dir })).slice(2)).toEqual(['Ana Test', 'Zara Test'])
    }
    expect(cols.lastSeen.first).toBe('desc')   // a first click shows the most recent first
  })
})

describe('ties break by name, A to Z whichever way the column points', () => {
  it('sortRows applies the tie AFTER the direction', () => {
    const rows = [{ name: 'Cara', n: 1 }, { name: 'Ben', n: 2 }, { name: 'Abu', n: 1 }]
    const byN = (a: { n: number }, b: { n: number }) => a.n - b.n
    expect(names(sortRows(rows, byN, 'asc', undefined, byName))).toEqual(['Abu', 'Cara', 'Ben'])
    expect(names(sortRows(rows, byN, 'desc', undefined, byName))).toEqual(['Ben', 'Abu', 'Cara'])
  })

  it('Members: equal status, descending, still A to Z', () => {
    const rows = [member('Cara', null), member('Abu', null), member('Ben', null, { suspended: true })]
    expect(names(sortMembers(rows, 'status', 'desc'))).toEqual(['Abu', 'Cara', 'Ben'])
  })

  it('Reviewers: equal figures, either direction, A to Z', () => {
    const rows = [reviewer('Cara', { completed: 2 }), reviewer('Abu', { completed: 2 }), reviewer('Ben', { completed: 5 })]
    expect(names(sortReviewers(rows, 'completed', 'desc'))).toEqual(['Ben', 'Abu', 'Cara'])
    expect(names(sortReviewers(rows, 'completed', 'asc'))).toEqual(['Abu', 'Cara', 'Ben'])
  })
})

describe('Status: the Members order, the exception first', () => {
  it('revoked, then paused, then active', () => {
    expect(STAFF_STATUS_RANK).toEqual({ revoked: 0, paused: 1, active: 2 })
    expect(staffStatusRank({ is_active: false, paused: true })).toBe(0)   // revoked beats paused
    expect(staffStatusRank({ paused: true })).toBe(1)
    expect(staffStatusRank({})).toBe(2)
  })

  it('the Reviewers table reads a revoked row first, as its pill says', () => {
    const rows = [reviewer('Active Test'), reviewer('Paused Test', { paused: true }),
      reviewer('Revoked Test', { is_active: false, paused: true })]
    expect(names(sortReviewers(rows, 'status', 'asc'))).toEqual(['Revoked Test', 'Paused Test', 'Active Test'])
    expect(statusRank(rows[2])).toBeLessThan(statusRank(rows[1]))
  })
})

describe('Also in: by the group names shown; "—" last both ways', () => {
  it('the words are the chips, the lead reading "Admin (lead)"', () => {
    expect(teamChipLabel('admins', true, t)).toBe('admin.team.chip.lead')
    expect(teamChipLabel('admins', false, t)).toBe('admin.team.chip.admins')
    expect(alsoInWords({ tables: ['admins', 'reviewers', 'mentors'], lead: true }, 'reviewers', t))
      .toBe('admin.team.chip.lead, admin.team.chip.mentors')
    expect(alsoInWords({ tables: ['reviewers'] }, 'reviewers', t)).toBe('')
  })

  it('Reviewers sort by them, with a row in no other group last', () => {
    const words = (k: string) => ({ 'admin.team.chip.admins': 'Admin', 'admin.team.chip.mentors': 'Mentor' } as
      Record<string, string>)[k] ?? k
    const rows = [reviewer('Only Here'), reviewer('Mentors Too', { tables: ['reviewers', 'mentors'] }),
      reviewer('Admins Too', { tables: ['admins', 'reviewers'] })]
    expect(names(sortReviewers(rows, 'alsoIn', 'asc', words))).toEqual(['Admins Too', 'Mentors Too', 'Only Here'])
    expect(names(sortReviewers(rows, 'alsoIn', 'desc', words))).toEqual(['Mentors Too', 'Admins Too', 'Only Here'])
  })
})

it('no column chosen keeps the server order', () => {
  const cols = { lastSeen: lastSeenColumn<StaffRow>() }
  expect(sortTeamRows(SEEN, cols, { key: null, dir: 'asc' })).toBe(SEEN)
})
