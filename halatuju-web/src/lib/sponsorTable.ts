/**
 * The sponsors table's own sort rules (2026-07-28).
 *
 * `tableView` owns the mechanics; this owns what each column MEANS when you sort by it — which is
 * where the judgement is. Every header except Actions is sortable.
 */
import type { AdminSponsor } from './admin-api'
import { byDate, byNumber, byText, sortRows, type SortDir } from './tableView'

export const SPONSOR_SORT_KEYS = [
  'name', 'status', 'given', 'students', 'lastSeen', 'registered',
] as const
export type SponsorSortKey = (typeof SPONSOR_SORT_KEYS)[number]

/** Which i18n label heads each sortable column — the panel's keep-in-sync pair with the table. */
export const SPONSOR_SORT_LABEL: Record<SponsorSortKey, string> = {
  name: 'admin.sponsors.name',
  status: 'admin.sponsors.status',
  given: 'admin.sponsors.colGiven',
  students: 'admin.sponsors.colStudents',
  lastSeen: 'admin.sponsors.colLastSeen',
  registered: 'admin.sponsors.registered',
}

/**
 * Status order: **the ones waiting on you first** (owner, 2026-07-28), not alphabetical.
 *
 * The column exists to find work. Alphabetical would put `approved` at the top and bury the
 * sponsors awaiting vetting in the middle, which is the opposite of why anyone sorts by it.
 */
export const STATUS_ORDER: Record<string, number> = {
  pending: 0,
  approved: 1,
  suspended: 2,
  rejected: 3,
}

/** Newest registration first — what the list already did before it became sortable. */
export const DEFAULT_SORT: { key: SponsorSortKey; dir: SortDir } = {
  key: 'registered', dir: 'desc',
}

/**
 * Which direction a column starts in on first click.
 *
 * Money, students and the two dates open DESCENDING because the interesting end is the top —
 * the biggest giver, the most students, the most recent. Text and status open ascending.
 */
const FIRST_DIR: Record<SponsorSortKey, SortDir> = {
  name: 'asc', status: 'asc', given: 'desc', students: 'desc',
  lastSeen: 'desc', registered: 'desc',
}

export function firstDirFor(key: SponsorSortKey): SortDir {
  return FIRST_DIR[key]
}

const COMPARE: Record<SponsorSortKey, (a: AdminSponsor, b: AdminSponsor) => number> = {
  name: (a, b) => byText(a.name, b.name),
  status: (a, b) => byNumber(STATUS_ORDER[a.status] ?? 99, STATUS_ORDER[b.status] ?? 99),
  given: (a, b) => byNumber(a.given, b.given),
  students: (a, b) => byNumber(a.students, b.students),
  lastSeen: (a, b) => byDate(a.last_seen_at, b.last_seen_at),
  registered: (a, b) => byDate(a.created_at, b.created_at),
}

/**
 * Rows sorted for display.
 *
 * `lastSeen` passes an unknown-test so a sponsor with **no sign-in recorded** stays at the bottom
 * whichever way the column points: that null means we have no record, not that they were last
 * here longest ago, and the column only started recording on 2026-07-27.
 */
export function sortSponsors(
  rows: AdminSponsor[], key: SponsorSortKey, dir: SortDir,
): AdminSponsor[] {
  const isUnknown = key === 'lastSeen' ? (r: AdminSponsor) => !r.last_seen_at : undefined
  return sortRows(rows, COMPARE[key], dir, isUnknown)
}
