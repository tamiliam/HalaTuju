/**
 * The Overview's per-organisation layout — the list arithmetic, kept OUT of the editor.
 *
 * Pure: no React, no fetch, no i18n. Node-testable exactly like `programmeOverview.ts`, and for the
 * same reason: reordering a list is the half of an editor that can be silently wrong, and the
 * arithmetic deserves a test that names every end case rather than one buried in a click. The
 * rendered tests next door then prove the SCREEN reaches this arithmetic and the save carries it.
 *
 * ⚠⚠ **THE LIST IS THE WHOLE LIST, ALWAYS.** The server validates `sections` as a PERMUTATION of
 * the five customisable widgets — no unknown key, no duplicate, nothing missing — so every helper
 * below returns a full list and the editor PUTs a full list. A diff would have to be re-expanded
 * somewhere, and the place it would be re-expanded wrongly is the place the order lives.
 *
 * ⚠ **`mine` AND `qc` ARE NOT IN HERE AND NEVER WILL BE.** They are a reviewer's and a checker's
 * whole page rather than a widget on somebody else's, so they are outside the catalogue and cannot
 * be switched off by an org admin (`overview_layout.CUSTOMISABLE` on the server says the same).
 *
 * ⚠ **A NO-OP RETURNS THE SAME REFERENCE, DELIBERATELY.** Dropping a card on itself, or on a key
 * that is not in the list, must not wake Save — and the cheapest honest way to say "nothing
 * happened" to a React caller is to hand back the array it already had.
 */

/** One row of the organisation's layout: a widget and whether it is drawn. */
export interface LayoutRow {
  key: string
  on: boolean
}

/**
 * The five widgets an organisation may switch off, in the order a fresh organisation gets them.
 *
 * ⚠ THIS LIST IS THE i18n GUARD'S ENUMERATION TOO (`admin-programme-overview-i18n.test.ts` imports
 * it to build `${NS}.sections.${key}`). Add a widget to the server's catalogue and the missing
 * label surfaces there, not in front of an admin as a raw dotted string.
 */
export const SECTION_KEYS = [
  'funnel', 'money', 'attention', 'applications_series', 'money_series',
] as const

/** Set one row's flag, leaving the order alone. Returns a NEW list — never mutates. */
export function setOn(list: readonly LayoutRow[], key: string, on: boolean): LayoutRow[] {
  return list.map((row) => (row.key === key ? { ...row, on } : row))
}

/**
 * Has the editor drifted from what was loaded?
 *
 * ⚠ ORDER COUNTS AS A CHANGE, not only the flags. The arrows move cards without touching a switch,
 * and a Save that slept through a reorder would strand the one edit the person came to make
 * (request #6, 2026-08-01 — a sleeping Save is the dangerous direction).
 */
export function isDirty(a: readonly LayoutRow[], b: readonly LayoutRow[]): boolean {
  if (a.length !== b.length) return true
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].key !== b[i].key || a[i].on !== b[i].on) return true
  }
  return false
}

/**
 * Move the row at `index` by `delta`, returning a NEW array.
 *
 * The shape of `sponsorTerms.moveSection` minus its `renumber` — position IS the order here, so
 * there is no number to keep honest. A move off either end is refused by returning the input
 * UNCHANGED (the same reference, as `reorderByDrop` does), which is what lets the up/down buttons
 * at the ends be harmless as well as disabled.
 */
export function moveItem(list: readonly LayoutRow[], index: number, delta: number): LayoutRow[] {
  const target = index + delta
  if (index < 0 || index >= list.length || target < 0 || target >= list.length) {
    return list as LayoutRow[]
  }
  const next = list.slice()
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  return next
}

/**
 * ⚠ KEPT, UNUSED: the editor ships with arrows only (Sprint B, 2026-09-19 — five rows do not
 * justify drag-and-drop, and a jsdom drop proves nothing), so this is the arithmetic a mouse-drag
 * would need on the day one is added. It carries its own tests and costs nothing to keep.
 *
 * Drop `fromKey` onto `toKey`: the dragged row is lifted out and re-inserted AT the target's
 * position, so dragging down lands after the target and dragging up lands before it — which is
 * what the pointer under the cursor promised.
 *
 * ⚠ THE SAME REFERENCE COMES BACK ON A NO-OP (same key, or either key unknown). A drop on itself
 * is the commonest gesture in a list nobody meant to change, and HTML5 drag-and-drop will hand us
 * a stale `text/plain` payload from another page without apology — neither may wake Save.
 */
export function reorderByDrop(
  list: readonly LayoutRow[], fromKey: string, toKey: string,
): LayoutRow[] {
  if (fromKey === toKey) return list as LayoutRow[]
  const from = list.findIndex((row) => row.key === fromKey)
  const to = list.findIndex((row) => row.key === toKey)
  if (from === -1 || to === -1) return list as LayoutRow[]
  const next = list.slice()
  const [moved] = next.splice(from, 1)
  next.splice(to, 0, moved)
  return next
}
