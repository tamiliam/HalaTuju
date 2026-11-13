'use client'

import { sortIndicator, type SortDir } from '@/lib/tableView'
import { TH, TH_RIGHT } from '@/components/admin/TableFrame'

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
 *
 * M2d A2 (owner, 2026-11-13) — one placement for the arrow on every table. It shows only on the active
 * column and sits on the side AWAY from the column's edge: after the label on a left-aligned column,
 * BEFORE it on a right-aligned one, so a number column's heading ends exactly where its figures end. The
 * button is right-justified there too: a button centres wrapped text by default, which is why "Awaiting
 * review" read as centred with its arrow pushed right. The cell is the shared `TH` / `TH_RIGHT`, so a sortable
 * heading and a plain one (Action) are the same cell. `sort.key` may be `null` — a table still in the
 * server's own order, where no heading is active.
 */
export default function SortHeader<K extends string>({ col, label, sort, onSort, align }: {
  col: K
  label: string
  sort: { key: K | null; dir: SortDir }
  onSort: (col: K) => void
  align?: 'right'
}) {
  const active = sort.key === col
  const right = align === 'right'
  const arrow = active
    ? <span aria-hidden className="text-[9px] leading-none">{sortIndicator(true, sort.dir)}</span>
    : null
  return (
    <th className={right ? TH_RIGHT : TH}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onSort(col)}
        className={`inline-flex items-center gap-1 font-semibold text-xs uppercase tracking-wider hover:text-primary-600 ${
          right ? 'justify-end text-right' : 'text-left'} ${active ? 'text-primary-600' : 'text-ground-600'}`}>
        {right && arrow}
        {label}
        {!right && arrow}
      </button>
    </th>
  )
}
