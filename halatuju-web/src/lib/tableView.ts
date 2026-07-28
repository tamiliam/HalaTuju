/**
 * Client-side sorting and paging for small admin tables (2026-07-28).
 *
 * **Why client-side.** These tables are small and their rows arrive in one payload the server has
 * already fenced and computed: 9 sponsors, 38 sponsorships at the worst, 8 invitations, 1 credit.
 * Sorting and slicing what the server sent is instant, needs no API change, and — the part that
 * matters — cannot disagree with the fenced figures, because it reorders the very numbers the
 * fence produced. Paging them server-side would mean three new endpoints for the detail tables
 * (they share ONE payload) and a `Subquery` annotation so `students` could be ordered without
 * reintroducing the join fan-out that inflates `given`. That is real machinery for tables of
 * eight rows.
 *
 * The boundary: move to the server if a list passes a few hundred rows. The applications list
 * already has the paged envelope to copy.
 *
 * Pair these with `components/Pagination` — but gate that component on `shouldPaginate`, because
 * it renders its page-size selector even on a single page when given options.
 */

/** Below this many rows a table shows no pagination at all (owner, 2026-07-28). */
export const PAGINATION_MIN_ROWS = 10

export const DEFAULT_PAGE_SIZE = 10
export const PAGE_SIZE_OPTIONS = [10, 25, 50]

export type SortDir = 'asc' | 'desc'

/** Whether the footer should appear. Deliberately strict `>`: exactly ten rows fit one page. */
export function shouldPaginate(rowCount: number, pageSize = DEFAULT_PAGE_SIZE): boolean {
  return rowCount > PAGINATION_MIN_ROWS && rowCount > pageSize
}

export function totalPages(rowCount: number, pageSize: number): number {
  return Math.max(1, Math.ceil(rowCount / Math.max(1, pageSize)))
}

/** One page of rows. Clamps the page, so a stale page number after a filter can't blank the table. */
export function pageOf<T>(rows: T[], page: number, pageSize: number): T[] {
  const last = totalPages(rows.length, pageSize)
  const safe = Math.min(Math.max(1, page), last)
  const start = (safe - 1) * pageSize
  return rows.slice(start, start + pageSize)
}

// ── comparators ───────────────────────────────────────────────────────────────
//
// Each returns a number for `Array.sort`, and each exists because the naive version is wrong for
// this data in a specific way.

/** Locale-aware text. Blanks sort LAST in both directions — an empty name is not "before A". */
export function byText(a: string | null | undefined, b: string | null | undefined): number {
  const x = (a || '').trim()
  const y = (b || '').trim()
  if (!x && !y) return 0
  if (!x) return 1
  if (!y) return -1
  return x.localeCompare(y, 'en-MY', { sensitivity: 'base' })
}

/**
 * Money and counts as NUMBERS.
 *
 * The API sends money as a 2-decimal STRING (`'20000.00'`), and sorting those as text puts
 * `'9000.00'` above `'20000.00'` — plausible-looking and wrong, which is the worst kind.
 */
export function byNumber(a: string | number | null | undefined,
                         b: string | number | null | undefined): number {
  const x = a === null || a === undefined || a === '' ? 0 : Number(a)
  const y = b === null || b === undefined || b === '' ? 0 : Number(b)
  return (Number.isNaN(x) ? 0 : x) - (Number.isNaN(y) ? 0 : y)
}

/**
 * Dates, with **nulls last in both directions**.
 *
 * A null `last_seen_at` means *no record*, not *longest ago* — treating it as an old date would
 * make "sort by last seen" claim nine sponsors were last here in 1970. Nulls belong at the end
 * whichever way the column is pointed, so the flip below deliberately does not reach them.
 */
export function byDate(a: string | null | undefined, b: string | null | undefined): number {
  if (!a && !b) return 0
  if (!a) return 1
  if (!b) return -1
  return new Date(a).getTime() - new Date(b).getTime()
}

/**
 * Sort by a comparator, honouring direction — but keeping "unknown" at the bottom.
 *
 * `desc` reverses the comparison for real values only. A comparator that has already decided a
 * blank or null sorts last (returning ±1 regardless of direction) keeps that answer, so flipping
 * the column never drags the unknowns to the top.
 */
export function sortRows<T>(
  rows: T[],
  compare: (a: T, b: T) => number,
  dir: SortDir,
  isUnknown?: (row: T) => boolean,
): T[] {
  const out = [...rows]
  out.sort((a, b) => {
    if (isUnknown) {
      const ua = isUnknown(a)
      const ub = isUnknown(b)
      if (ua !== ub) return ua ? 1 : -1      // unknowns last, both directions
      if (ua && ub) return 0
    }
    const c = compare(a, b)
    return dir === 'asc' ? c : -c
  })
  return out
}

/** Click a header: same column flips direction, a new column starts at `firstDir`. */
export function nextSort<K extends string>(
  current: { key: K; dir: SortDir }, clicked: K, firstDir: SortDir = 'asc',
): { key: K; dir: SortDir } {
  if (current.key !== clicked) return { key: clicked, dir: firstDir }
  return { key: clicked, dir: current.dir === 'asc' ? 'desc' : 'asc' }
}

/** The arrow a header shows. '' for the columns that are not the active sort. */
export function sortIndicator(active: boolean, dir: SortDir): string {
  return active ? (dir === 'asc' ? '▲' : '▼') : ''
}
