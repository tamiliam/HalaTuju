'use client'

import { sortIndicator, type SortDir } from '@/lib/tableView'

/**
 * A clickable column heading. **The console's one sortable `<th>`.**
 *
 * ⚠ **THIS EXISTS BECAUSE THE SAME MARKUP HAD BEEN COPIED TWICE ALREADY** — Reviewers and Sponsors
 * each carried a byte-identical local `SortHeader`, differing only in the key type and the label
 * map. The spending screen needed two more, and a fourth copy is how one table quietly stops
 * announcing `aria-sort`, or loses the arrow, or grows a different hover colour. Both originals
 * were moved onto this component in the same change: a partial extraction is more dangerous than
 * none, because it looks finished. (S6, 2026-09-11.)
 *
 * ⚠ It renders a `<th>` and must therefore sit **directly inside a `<tr>`** — wrapping it in a
 * fragment-returning helper is fine, wrapping it in a `<div>` is not.
 *
 * The label arrives **already translated**. Each table keeps its own key→label map beside its
 * comparators (`lib/sponsorTable`, `lib/spendingTable`, …), so the column's name and the rule for
 * ordering it stay in one file rather than drifting apart across two.
 */
export default function SortHeader<K extends string>({ col, label, sort, onSort, align }: {
  col: K
  label: string
  sort: { key: K; dir: SortDir }
  onSort: (col: K) => void
  align?: 'right'
}) {
  const active = sort.key === col
  return (
    <th className={`px-4 py-3 ${align === 'right' ? 'text-right' : 'text-left'}`}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onSort(col)}
        className={`inline-flex items-center gap-1 font-semibold text-xs uppercase tracking-wider hover:text-primary-600 ${
          active ? 'text-primary-600' : 'text-ground-600'}`}>
        {label}
        <span aria-hidden className="text-[9px] leading-none">
          {sortIndicator(active, sort.dir)}
        </span>
      </button>
    </th>
  )
}
