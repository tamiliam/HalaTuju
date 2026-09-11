/**
 * Sorting and grouping for the spending screen's tables (S6, 2026-09-11).
 *
 * Pure functions, no React, no fetching — the same shape as `lib/sponsorTable.ts`, and here for the
 * same reason: a comparator is the part of a table most easily wrong in a way nobody sees. The
 * page renders; this decides.
 *
 * ⚠ **MONEY ARRIVES AS A STRING AND IS COMPARED WITH `byNumber`, NEVER `byText`.** `'9000.00'`
 * sorts above `'20000.00'` as text — plausible-looking, and the worst kind of wrong. The shared
 * comparator already handles it; the rule is written here because this file is where somebody
 * would add the eleventh column.
 */
import { byDate, byNumber, byText, sortRows, type SortDir } from './tableView'
import type { SpendingMerchantRow, SpendingStudentRow } from './admin-api'

/*
 * ⚠⚠ **SORTING GOES THROUGH `sortRows`, NOT THROUGH A LOOP WRITTEN HERE.** The first draft of this
 * file hand-rolled `[...rows].sort()` with `dir === 'asc' ? c : -c`, and its own tests caught two
 * bugs on the first run: a shop never seen and a student with no name recorded both jumped to the
 * TOP when the column was reversed. `byDate` and `byText` already answer "unknown sorts last" by
 * returning ±1 regardless of direction — and negating the whole comparison throws that answer
 * away. `sortRows` exists precisely to hold the unknowns down through a flip; use it.
 */

// ── shops ─────────────────────────────────────────────────────────────────────

export type MerchantSortKey =
  'shop' | 'countedAs' | 'decidedBy' | 'visits' | 'total' | 'lastSeen' | 'decidedAt'

export const MERCHANT_SORT_LABEL: Record<MerchantSortKey, string> = {
  shop: 'admin.spending.col.shop',
  countedAs: 'admin.spending.col.countedAs',
  decidedBy: 'admin.spending.col.decidedBy',
  visits: 'admin.spending.col.visits',
  total: 'admin.spending.col.total',
  lastSeen: 'admin.spending.col.lastSeen',
  decidedAt: 'admin.spending.col.decidedAt',
}

/**
 * How settled each verdict is. **Not alphabetical, and deliberately not.**
 *
 * The labels are translated, so an alphabetical sort on "How we decided" would order the column
 * differently in English, Malay and Tamil and mean nothing in any of them. What an officer wants
 * from this column is a queue: ascending puts the answers nobody needs to look at first, and
 * descending brings the guesses to the top. `owner` leads because your own answer outranks every
 * rung of the sorter for ever; the blank at the end is a shop the sorter has never reached.
 */
const DECIDED_RANK: Record<string, number> = {
  owner: 0, rule: 1, duitnow: 2, inferred: 3, ai: 4,
}
const DECIDED_UNKNOWN = 5

/** The tables start biggest/newest-first; names start A→Z. Clicking flips from there. */
const MERCHANT_FIRST_DIR: Record<MerchantSortKey, SortDir> = {
  shop: 'asc', countedAs: 'asc', decidedBy: 'desc',
  visits: 'desc', total: 'desc', lastSeen: 'desc', decidedAt: 'desc',
}

export function merchantFirstDir(key: MerchantSortKey): SortDir {
  return MERCHANT_FIRST_DIR[key]
}

export const MERCHANT_DEFAULT_SORT: { key: MerchantSortKey; dir: SortDir } =
  { key: 'total', dir: 'desc' }

/**
 * Sort the shops.
 *
 * ⚠ `labels` maps a category CODE to the words on screen, and "Counted as" sorts by the WORDS. A
 * reader ordering that column is ordering what they can see; sorting by the code would put
 * `clothing` above `food` in every language while the screen showed something else. This is the
 * same reasoning as the sponsor card's tie-break, which also sorts on the label.
 */
export function sortMerchants(
  rows: SpendingMerchantRow[],
  key: MerchantSortKey,
  dir: SortDir,
  labels: Record<string, string> = {},
): SpendingMerchantRow[] {
  const shown = (code: string) => labels[code || 'unsorted'] ?? (code || 'unsorted')
  const compare: Record<MerchantSortKey, (a: SpendingMerchantRow, b: SpendingMerchantRow) => number> = {
    shop: (a, b) => byText(a.merchant, b.merchant),
    countedAs: (a, b) => byText(shown(a.category), shown(b.category)),
    decidedBy: (a, b) => byNumber(DECIDED_RANK[a.decided_by] ?? DECIDED_UNKNOWN,
                                  DECIDED_RANK[b.decided_by] ?? DECIDED_UNKNOWN),
    visits: (a, b) => byNumber(a.visits, b.visits),
    total: (a, b) => byNumber(a.total, b.total),
    lastSeen: (a, b) => byDate(a.last_seen, b.last_seen),
    decidedAt: (a, b) => byDate(a.decided_at, b.decided_at),
  }
  // ⚠ `isUnknown` for the DATE column only. A shop never seen has no `last_seen`, which is "no
  // record", not "longest ago" — it belongs at the bottom whichever way the column points.
  // "How we decided" looks similar and is NOT an unknown: a blank there is a real rung (the
  // sorter has not reached this shop), ranked last, so reversing the column correctly brings it
  // to the top — which is the queue an officer wants.
  //
  // Ties keep the order the server sent, because `Array.sort` is stable and the server's own
  // order is deterministic (`-total`, then name). So the list does not reshuffle itself when a
  // correction re-fetches it.
  const unknown: Partial<Record<MerchantSortKey, (r: SpendingMerchantRow) => boolean>> = {
    lastSeen: (r) => !r.last_seen,
    decidedAt: (r) => !r.decided_at,
  }
  return sortRows(rows, compare[key], dir, unknown[key])
}

// ── searching and filtering ───────────────────────────────────────────────────
//
// ⚠ **FILTER FIRST, THEN SORT, THEN PAGE — and never any other order.** Sorting a filtered list is
// cheap and correct; paging before either is the fault the page tests already pin.

/** Case- and space-insensitive "does this text contain what was typed". */
function matches(haystack: string, needle: string): boolean {
  const q = needle.trim().toLowerCase()
  return !q || (haystack || '').toLowerCase().includes(q)
}

export interface MerchantFilters {
  /** Free text, matched against the shop name. */
  query?: string
  /** A category CODE, or '' for every category. */
  category?: string
  /** A `decided_by` value, or '' for any. `'none'` means the sorter has not reached it. */
  decidedBy?: string
}

/**
 * Narrow the shops. Pure, and deliberately separate from sorting.
 *
 * ⚠ **`decidedBy: 'none'` SELECTS THE BLANK**, because a blank is a real state — the sorter has
 * never reached this shop — and a dropdown cannot offer an empty string as a choosable value
 * without it looking like the "any" option. The same token names it in the pill and in `by.none`.
 */
export function filterMerchants(
  rows: SpendingMerchantRow[], f: MerchantFilters = {},
): SpendingMerchantRow[] {
  return rows.filter((r) => {
    if (!matches(r.merchant, f.query || '')) return false
    if (f.category && (r.category || 'unsorted') !== f.category) return false
    if (f.decidedBy && (r.decided_by || 'none') !== f.decidedBy) return false
    return true
  })
}

export interface StudentFilters {
  /** Free text, matched against the student's name. */
  query?: string
  /** Only students with money we could not place. */
  onlyUnplaced?: boolean
}

export function filterStudents(
  rows: SpendingStudentRow[], f: StudentFilters = {},
): SpendingStudentRow[] {
  return rows.filter((r) => {
    if (!matches(r.name, f.query || '')) return false
    // ⚠ Compared as a NUMBER. `unplaced` is a money STRING, so `'0.00'` is truthy — a plain
    // truthiness test here would show every student and look like a broken filter.
    if (f.onlyUnplaced && Number(r.unplaced || 0) <= 0) return false
    return true
  })
}

/**
 * The shops with money we could not place — what the **Unsorted** tab lists.
 *
 * ⚠ **THIS IS A QUESTION ABOUT MONEY, NOT ABOUT CONFIDENCE**, and the two are different lists.
 * "Shops to check" in the header counts shops whose verdict no human confirmed, including ones the
 * model placed perfectly well. This tab pairs with the other header figure — **Not yet sorted** —
 * so a reader clicking through from that number arrives at the shops it is made of, rather than at
 * a longer list that does not add up to it.
 *
 * Two ways a shop qualifies:
 *   * its category is blank (never sorted) or `unsorted` (sorted, honestly unplaceable), or
 *   * `held_back` is above zero — the shop IS counted as food, but the RM20 per-payment ceiling
 *     kept some of its payments out of that answer, and those ringgit are sitting in `unsorted`.
 *     Leaving these out would hide the six real payments (RM424) the ceiling holds on production.
 */
export function shopsWithUnplacedMoney(rows: SpendingMerchantRow[]): SpendingMerchantRow[] {
  return rows.filter((r) => !r.category || r.category === 'unsorted' || r.held_back > 0)
}

// ── students ──────────────────────────────────────────────────────────────────

export type StudentSortKey = 'name' | 'payments' | 'spent' | 'unplaced'

export const STUDENT_SORT_LABEL: Record<StudentSortKey, string> = {
  name: 'admin.spending.students.name',
  payments: 'admin.spending.students.payments',
  spent: 'admin.spending.students.spent',
  unplaced: 'admin.spending.students.unsorted',
}

const STUDENT_FIRST_DIR: Record<StudentSortKey, SortDir> = {
  name: 'asc', payments: 'desc', spent: 'desc', unplaced: 'desc',
}

export function studentFirstDir(key: StudentSortKey): SortDir {
  return STUDENT_FIRST_DIR[key]
}

export const STUDENT_DEFAULT_SORT: { key: StudentSortKey; dir: SortDir } =
  { key: 'spent', dir: 'desc' }

export function sortStudents(
  rows: SpendingStudentRow[], key: StudentSortKey, dir: SortDir,
): SpendingStudentRow[] {
  const compare: Record<StudentSortKey, (a: SpendingStudentRow, b: SpendingStudentRow) => number> = {
    name: (a, b) => byText(a.name, b.name),
    payments: (a, b) => byNumber(a.payments, b.payments),
    spent: (a, b) => byNumber(a.spent, b.spent),
    unplaced: (a, b) => byNumber(a.unplaced, b.unplaced),
  }
  // ⚠ A student with no name recorded sorts LAST in both directions — same reasoning as the date
  // column above. It is a missing record, not a name that begins with nothing.
  return sortRows(rows, compare[key], dir,
                  key === 'name' ? (r) => !(r.name || '').trim() : undefined)
}
