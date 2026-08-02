/**
 * The reviewers table's own sort rules (request #10, 2026-08-02).
 *
 * `tableView` owns the mechanics; this owns what each column MEANS when you sort by it — the same
 * split as `sponsorTable`. Every header is sortable except Languages, which is a set, not a scale.
 */
import type { AdminReviewer } from './admin-api'
import { byNumber, byText, sortRows, type SortDir } from './tableView'

export const REVIEWER_SORT_KEYS = [
  'name', 'role', 'openNow', 'completed', 'turnaround', 'status',
] as const
export type ReviewerSortKey = (typeof REVIEWER_SORT_KEYS)[number]

/** Which i18n label heads each sortable column — the panel's keep-in-sync pair with the table. */
export const REVIEWER_SORT_LABEL: Record<ReviewerSortKey, string> = {
  name: 'admin.reviewers.colName',
  role: 'admin.reviewers.colRole',
  openNow: 'admin.reviewers.colOpen',
  completed: 'admin.reviewers.colCompleted',
  turnaround: 'admin.reviewers.colTurnaround',
  status: 'admin.reviewers.colStatus',
}

/**
 * Role order: **by what the person may do to a case**, not alphabetical.
 *
 * A super can decide anything, QC clears what a reviewer recommended, a reviewer recommends. That
 * is the order somebody scans when deciding who to hand a case to. Alphabetical would interleave
 * the three for no reason.
 */
export const ROLE_ORDER: Record<string, number> = {
  super: 0,
  qc: 1,
  reviewer: 2,
}

/**
 * **Paused first** (the same principle as the sponsors' status column, 2026-07-28): a status
 * column exists to find the exception, and on a list of thirteen volunteers the exception is the
 * person who has stepped back. Active-first would bury them.
 */
export function statusRank(r: AdminReviewer): number {
  return r.paused ? 0 : 1
}

/**
 * **Who is carrying the most, right now.** This is the question the page is opened to answer —
 * an org_admin comes here before handing out the next case, not to browse a staff list.
 */
export const DEFAULT_SORT: { key: ReviewerSortKey; dir: SortDir } = {
  key: 'openNow', dir: 'desc',
}

/**
 * Which direction a column starts in on first click.
 *
 * The three figures open DESCENDING because the interesting end is the top — the fullest caseload,
 * the most reviews completed, and the SLOWEST turnaround (a fast one needs nobody's attention).
 * Name, role and status open ascending.
 */
const FIRST_DIR: Record<ReviewerSortKey, SortDir> = {
  name: 'asc', role: 'asc', openNow: 'desc', completed: 'desc',
  turnaround: 'desc', status: 'asc',
}

export function firstDirFor(key: ReviewerSortKey): SortDir {
  return FIRST_DIR[key]
}

const COMPARE: Record<ReviewerSortKey, (a: AdminReviewer, b: AdminReviewer) => number> = {
  name: (a, b) => byText(a.name, b.name),
  role: (a, b) => byNumber(ROLE_ORDER[a.role] ?? 99, ROLE_ORDER[b.role] ?? 99),
  openNow: (a, b) => byNumber(a.open_now, b.open_now),
  completed: (a, b) => byNumber(a.completed, b.completed),
  turnaround: (a, b) => byNumber(a.turnaround_days, b.turnaround_days),
  status: (a, b) => byNumber(statusRank(a), statusRank(b)),
}

/**
 * Rows sorted for display.
 *
 * `turnaround` passes an unknown-test so a reviewer with **no completed review** stays at the
 * bottom whichever way the column points. `null` there means we have no measurement — treating it
 * as 0 would make "sort by slowest" put every brand-new volunteer at the fast end and every
 * "fastest" sort crown somebody who has never decided a case. Six of the thirteen are in that
 * state today, so this is the common row, not the edge one.
 */
export function sortReviewers(
  rows: AdminReviewer[], key: ReviewerSortKey, dir: SortDir,
): AdminReviewer[] {
  const isUnknown = key === 'turnaround'
    ? (r: AdminReviewer) => r.turnaround_days === null
    : undefined
  return sortRows(rows, COMPARE[key], dir, isUnknown)
}
