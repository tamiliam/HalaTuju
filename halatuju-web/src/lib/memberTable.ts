/**
 * Sprint M2c (owner R4): the Members table's own rules — what each column MEANS when you sort by it, the
 * name search and the status filter. `tableView` owns the mechanics; this file owns the meaning, the same
 * split as `reviewerTable`.
 *
 * ⚠ SEARCH IS ON THE NAME ONLY: a Members row carries no email (owner O16), so there is nothing else to match.
 *
 * M2d A2 (owner, 2026-11-13): Last seen sorts too, "Not recorded" last both ways (`lib/teamSort`); every
 * column breaks its ties by name, A to Z whichever way it points.
 */
import type { StaffRow } from './admin-api'
import { byName, lastSeenColumn } from './teamSort'
import { byNumber, byText, sortRows, type SortDir } from './tableView'

export const MEMBER_SORT_KEYS = ['name', 'groups', 'status', 'lastSeen'] as const
export type MemberSortKey = (typeof MEMBER_SORT_KEYS)[number]

/** Which i18n label heads each sortable column. */
export const MEMBER_SORT_LABEL: Record<MemberSortKey, string> = {
  name: 'admin.nameHeader',
  groups: 'admin.staff.colGroups',
  status: 'admin.reviewers.colStatus',
  lastSeen: 'admin.reviewers.colLastSeen',
}

/** The server's own order (`name, id`), so the first paint matches what the list showed before M2c. */
export const DEFAULT_MEMBER_SORT: { key: MemberSortKey; dir: SortDir } = { key: 'name', dir: 'asc' }

export type MemberFilter = 'all' | 'active' | 'suspended'
export const MEMBER_FILTERS: readonly MemberFilter[] = ['all', 'active', 'suspended']

const GROUP_ORDER: Record<string, number> = { admins: 0, reviewers: 1, mentors: 2 }

/** People in the same groups sit together, in the order Admins, Reviewers, Mentors; "No group" comes first
 *  ascending (the rows a Delete is open for, owner R2). */
export function groupsRank(r: StaffRow): string {
  return r.groups.map((g) => GROUP_ORDER[g] ?? 9).sort().join('')
}

/** Suspended first, as the Reviewers table puts the paused first: a status column exists to find the exception. */
export const statusRank = (r: StaffRow) => (r.suspended ? 0 : 1)

// Plain code-point order: `byText` puts a blank (No group) last, and No group belongs first ascending.
const byRank = (x: string, y: string) => (x < y ? -1 : x > y ? 1 : 0)

const LAST_SEEN = lastSeenColumn<StaffRow>()

const COMPARE: Record<MemberSortKey, (a: StaffRow, b: StaffRow) => number> = {
  name: (a, b) => byText(a.name, b.name),
  groups: (a, b) => byRank(groupsRank(a), groupsRank(b)),
  status: (a, b) => byNumber(statusRank(a), statusRank(b)),
  lastSeen: LAST_SEEN.compare,
}

/** A click on Last seen starts at the most recent; the others A to Z. */
export const MEMBER_FIRST_DIR: Partial<Record<MemberSortKey, SortDir>> = { lastSeen: 'desc' }

export function sortMembers(rows: StaffRow[], key: MemberSortKey, dir: SortDir): StaffRow[] {
  return sortRows(rows, COMPARE[key], dir, key === 'lastSeen' ? LAST_SEEN.unknown : undefined, byName)
}

/** The rows a search and a status filter leave: the name contains the words typed, case and spacing aside. */
export function filterMembers(rows: StaffRow[], query: string, status: MemberFilter): StaffRow[] {
  const q = query.trim().toLowerCase()
  return rows.filter((r) =>
    (status === 'all' || (status === 'suspended') === r.suspended)
    && (!q || (r.name || '').toLowerCase().includes(q)))
}
