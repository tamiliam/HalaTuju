/**
 * Sprint M2c (owner R4): the Members table's sort, search and filter rules.
 */
import type { StaffRow } from '../admin-api'
import { filterMembers, groupsRank, sortMembers } from '../memberTable'

const NO_WORK = { admins: {}, reviewers: { open_cases: 0 }, mentors: { scholars_now: 0 } }
const row = (id: number, name: string, groups: StaffRow['groups'], suspended = false): StaffRow => ({
  id, kind: 'staff', mentor_id: null, name, photo_url: null, last_seen_at: null, groups, lead: false, suspended,
  manageable: true, work: NO_WORK, deletable: true, delete_never: null, delete_outcome: 'erase', revocable: true,
})
const ids = (rows: StaffRow[]) => rows.map((r) => r.id)

const ROWS = [
  row(1, 'Bala', ['mentors', 'admins']),
  row(2, 'aruna', ['reviewers']),
  row(3, 'Chitra', [], true),
  row(4, 'Devi', ['admins', 'mentors'], true),
]

describe('memberTable', () => {
  it('groupsRank ignores the order the groups arrive in', () => {
    expect(groupsRank(ROWS[0])).toBe(groupsRank(ROWS[3]))
    expect(groupsRank(ROWS[2])).toBe('')
  })

  it('sorts by name, case aside, both ways', () => {
    expect(ids(sortMembers(ROWS, 'name', 'asc'))).toEqual([2, 1, 3, 4])
    expect(ids(sortMembers(ROWS, 'name', 'desc'))).toEqual([4, 3, 1, 2])
  })

  it('sorts by groups: No group first, then Admins, Reviewers, Mentors; ties by name', () => {
    expect(ids(sortMembers(ROWS, 'groups', 'asc'))).toEqual([3, 1, 4, 2])
  })

  it('sorts by status: suspended first; ties by name', () => {
    expect(ids(sortMembers(ROWS, 'status', 'asc'))).toEqual([3, 4, 2, 1])
  })

  it('filters by a name fragment and by status, and leaves the input alone', () => {
    expect(ids(filterMembers(ROWS, ' RUN ', 'all'))).toEqual([2])
    expect(ids(filterMembers(ROWS, '', 'suspended'))).toEqual([3, 4])
    expect(ids(filterMembers(ROWS, '', 'active'))).toEqual([1, 2])
    expect(ids(filterMembers(ROWS, 'devi', 'active'))).toEqual([])
    expect(ROWS).toHaveLength(4)
  })
})
