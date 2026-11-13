'use client'

/**
 * Sprint M2d A2 (owner, 2026-11-13): every Team table header sorts, except Action — the rules the five
 * tables (Members, Admins, Reviewers, Mentors, Invitations) share, in one place.
 *
 * The rules the owner set:
 *  - **Ties break by name**, A to Z whichever way the column points (`tableView.sortRows`' `tie`).
 *  - **Last seen**: "Not recorded" goes LAST in both directions — it is no record, not "longest ago".
 *  - **Also in**: by the group names as the cell shows them; a row in no other group ("—") goes last.
 *  - **Status**: the Members table's order — the exception first (revoked, then paused, then active).
 *
 * Sorting stays client-side: every one of these tables arrives whole in one payload (`tableView` has the
 * reasoning). `tableView` owns the mechanics; this file owns what the shared columns MEAN.
 */
import { useState } from 'react'

import { type StaffStanding, type StaffStatusKey, staffStatusKey } from './staffStatus'
import { byDate, byText, nextSort, sortRows, type SortDir } from './tableView'

type T = (key: string) => string

/** Status, exception first — the order the Members table set (suspended before active). */
export const STAFF_STATUS_RANK: Record<StaffStatusKey, number> = { revoked: 0, paused: 1, active: 2 }

export function staffStatusRank(r: StaffStanding): number {
  return STAFF_STATUS_RANK[staffStatusKey(r)]
}

/** One group chip's words: "Admin (lead)" for the organisation admin's Admins seat. ⚠ THE ONE HOME of the
 *  chip label — `TableChips` draws it, the "Also in" sort orders by it, so the order is the words shown. */
export function teamChipLabel(group: string, lead: boolean | undefined, t: T): string {
  return group === 'admins' && lead ? t('admin.team.chip.lead') : t(`admin.team.chip.${group}`)
}

/** The "Also in" cell's words, in the order the chips are drawn; '' when the cell shows "—". */
export function alsoInWords(row: { tables?: readonly string[]; lead?: boolean }, here: string, t: T): string {
  return (row.tables ?? []).filter((x) => x !== here).map((x) => teamChipLabel(x, row.lead, t)).join(', ')
}

export interface Named { name?: string | null }

export const byName = (a: Named, b: Named): number => byText(a.name, b.name)

/** One sortable column: how two rows compare, which rows hold no value (last, both directions) and the
 *  direction a first click starts in (default A to Z). */
export interface TeamColumn<R> {
  compare: (a: R, b: R) => number
  unknown?: (r: R) => boolean
  first?: SortDir
}

/** "Last seen": the date, with "Not recorded" last whichever way the column points. */
export function lastSeenColumn<R extends { last_seen_at?: string | null }>(): TeamColumn<R> {
  return { compare: (a, b) => byDate(a.last_seen_at, b.last_seen_at), unknown: (r) => !r.last_seen_at, first: 'desc' }
}

/** "Also in" over the words the cell shows; a row in no other group last. */
export function alsoInColumn<R extends { tables?: readonly string[]; lead?: boolean }>(
  here: string, t: T,
): TeamColumn<R> {
  return {
    compare: (a, b) => byText(alsoInWords(a, here, t), alsoInWords(b, here, t)),
    unknown: (r) => !alsoInWords(r, here, t),
  }
}

/** A table's sort: a key, or `null` for the server's own order (no heading active). */
export type TeamSort<K extends string> = { key: K | null; dir: SortDir }

/** The rows in the chosen column's order, ties by name; unchanged while no column is chosen. */
export function sortTeamRows<R extends Named, K extends string>(
  rows: R[], columns: Record<K, TeamColumn<R>>, sort: TeamSort<K>,
): R[] {
  if (!sort.key) return rows
  const c = columns[sort.key]
  return sortRows(rows, c.compare, sort.dir, c.unknown, byName)
}

/** Sort state for a Team table: starts in the server's order unless told otherwise; a click on a new
 *  column starts in that column's own first direction, a second click flips it. */
export function useTeamSort<R, K extends string>(
  columns: Record<K, TeamColumn<R>>, initial: TeamSort<K> = { key: null, dir: 'asc' },
) {
  const [sort, setSort] = useState<TeamSort<K>>(initial)
  const onSort = (col: K) => setSort(nextSort(sort, col, columns[col].first ?? 'asc'))
  return { sort, onSort }
}
