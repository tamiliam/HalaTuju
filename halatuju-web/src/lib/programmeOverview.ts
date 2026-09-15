/**
 * Programme Overview — the arithmetic behind the page, kept OUT of the components.
 *
 * Pure: no React, no fetch, no i18n. Node-testable exactly like `officerCockpit.ts`, and that is
 * the point — chart geometry is the half of a chart that can be silently wrong, so it is the half
 * that gets its own tests rather than being asserted through a rendered SVG.
 *
 * ⚠⚠ **MONEY ARRIVES AS A STRING AND IS PARSED HERE FOR GEOMETRY ONLY.** `num()` exists so a bar
 * can have a height; nothing in this module ever hands a parsed number back to the screen. Every
 * figure a person reads is rendered from the STRING the server sent (`rm`), because a money value
 * that has been through a float is a money value we have rounded (sponsor spending S5).
 *
 * ⚠ **A NUMBER SHOWN TO A HUMAN CARRIES AN IMPLIED "OF WHAT".** Every layout below returns its
 * `figures` alongside its shapes so the caller can render them as text — a chart whose values are
 * only in its pixels is unreadable to a screen reader and unquotable to everybody else.
 */

/** ⚠ Parsed for GEOMETRY ONLY — see the module note. `Number('')` is 0, and so is a bad string. */
export const num = (v: string | number): number => (typeof v === 'number' ? v : Number(v) || 0)

/**
 * Thousands grouping, hand-formatted so the server and the browser render identically.
 *
 * ⚠ LIFTED FROM `SpendingCard`, not re-derived. It was the fourth money formatter in the app and
 * the sponsor card's is the one that already survived review; a second spelling of "group the
 * thousands" is a second place for a rounding difference to appear between two screens showing
 * the same ringgit.
 *
 * ⚠ It knows nothing about a minus sign, deliberately — the one negative figure on this page (the
 * running gap) is signed by its caller, which is where the decision "this is allowed to be
 * negative" belongs.
 */
export function rm(v: string): string {
  const [whole, cents = '00'] = String(v).split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`
}

// ── the drawing box ───────────────────────────────────────────────────────────────────────────
//
// ⚠ ONE FIXED `viewBox` PER CHART SHAPE, AND NO ResizeObserver ANYWHERE. An SVG with a viewBox
// scales itself to its container; measuring the container in JavaScript to draw it again would
// add a layout read, a second render and a class of hydration bug, to arrive at the same picture.

export interface ChartBox {
  width: number
  height: number
  /** Space above the tallest bar, below the baseline (for a label), and at each end. */
  top: number
  bottom: number
  side: number
}

export const WIDE_BOX: ChartBox = { width: 360, height: 120, top: 8, bottom: 20, side: 8 }
export const FULL_BOX: ChartBox = { width: 740, height: 150, top: 10, bottom: 24, side: 12 }
export const SMALL_BOX: ChartBox = { width: 240, height: 110, top: 8, bottom: 18, side: 10 }

export interface Bar { x: number; y: number; width: number; height: number }

/**
 * Bars for one or more series, grouped by column.
 *
 * ⚠ **EVERY SERIES SHARES ONE SCALE, BECAUSE THEY SHARE ONE UNIT.** Released and spent are both
 * ringgit; drawing them against separate maxima would make a small month look like a large one
 * beside it. Where that flattens a series, the figures beneath the chart carry the real numbers —
 * a second hidden axis would not.
 *
 * ⚠ AN ALL-ZERO CHART DRAWS NOTHING RATHER THAN EVERYTHING. With `max === 0` every bar is height
 * 0: a full-height bar for a zero would be a lie, and dividing by the max would be a crash.
 */
export function barLayout(
  series: ReadonlyArray<readonly number[]>,
  box: ChartBox = WIDE_BOX,
): { bars: Bar[][]; baseline: number; max: number } {
  const groups = series.reduce((n, s) => Math.max(n, s.length), 0)
  const baseline = box.height - box.bottom
  const plot = box.height - box.bottom - box.top
  let max = 0
  for (let s = 0; s < series.length; s += 1) {
    for (let i = 0; i < series[s].length; i += 1) max = Math.max(max, series[s][i])
  }
  if (groups === 0) return { bars: series.map(() => []), baseline, max }
  const slot = (box.width - box.side * 2) / groups
  // 72% of the slot is bars, the rest is the gutter between columns — two series therefore get
  // 36% each and still read as a pair rather than as two charts.
  const barWidth = (slot * 0.72) / Math.max(1, series.length)
  const bars = series.map((values, s) => {
    const out: Bar[] = []
    for (let i = 0; i < groups; i += 1) {
      const value = values[i] ?? 0
      const height = max > 0 ? Math.max(0, (value / max) * plot) : 0
      out.push({
        x: box.side + slot * i + slot * 0.14 + barWidth * s,
        y: baseline - height,
        width: barWidth,
        height,
      })
    }
    return out
  })
  return { bars, baseline, max }
}

export interface LinePoint { x: number; y: number }

/**
 * A polyline across the same columns the bars use — **and it supports a NEGATIVE value.**
 *
 * ⚠ THE DOMAIN INCLUDES ZERO WHENEVER ANYTHING IS NEGATIVE, and the zero line is returned so the
 * caller can draw it. The running gap on this page is `released − spent` and goes below zero when
 * a parent tops a wallet up; clamping it at zero would hide the one month an officer should ask
 * about (the same reasoning that leaves `spend_report.student_rows.balance` unfloored).
 *
 * ⚠ A FLAT SERIES SITS ON THE BASELINE, not in the middle. With `min === max` there is no range to
 * divide by, and centring a flat line invents a movement that did not happen.
 */
export function lineLayout(
  values: readonly number[],
  box: ChartBox = WIDE_BOX,
): { points: LinePoint[]; zeroY: number; min: number; max: number } {
  const baseline = box.height - box.bottom
  const plot = box.height - box.bottom - box.top
  let lo = 0
  let hi = 0
  for (let i = 0; i < values.length; i += 1) {
    lo = Math.min(lo, values[i])
    hi = Math.max(hi, values[i])
  }
  const span = hi - lo
  const y = (v: number) => (span > 0 ? baseline - ((v - lo) / span) * plot : baseline)
  const slot = values.length > 0 ? (box.width - box.side * 2) / values.length : 0
  const points = values.map((v, i) => ({ x: box.side + slot * i + slot / 2, y: y(v) }))
  return { points, zeroY: y(0), min: lo, max: hi }
}

// ── the donut ─────────────────────────────────────────────────────────────────────────────────

/** Geometry lifted from `SpendingCard` — one circle per slice, offset by everything before it. */
export const DONUT_RADIUS = 56
const CIRCUMFERENCE = 2 * Math.PI * DONUT_RADIUS

export interface DonutArc {
  code: string
  /** Rank among the slices that actually have money — what `sliceClasses` colours by. */
  rank: number
  dash: number
  gap: number
  offset: number
}

/**
 * Arcs for the slices with money in them.
 *
 * ⚠⚠ **A ZERO SLICE IS SKIPPED IN THE RING AND KEPT IN THE LEGEND.** A zero-length arc is
 * invisible, so drawing it would only consume a colour that the next real category then cannot
 * have. But the legend must still list it: `by_category` sends all eleven slices deliberately,
 * because "health: RM0" is information and an absent line is not (`programme_overview.by_category`).
 * The caller therefore iterates the ROWS for the legend and these ARCS for the ring.
 */
export function donutArcs(
  rows: ReadonlyArray<{ code: string; total: string }>,
): DonutArc[] {
  let total = 0
  for (let i = 0; i < rows.length; i += 1) total += num(rows[i].total)
  const arcs: DonutArc[] = []
  let offset = 0
  let rank = 0
  for (let i = 0; i < rows.length; i += 1) {
    const value = num(rows[i].total)
    if (value <= 0) continue
    const share = total > 0 ? value / total : 0
    arcs.push({
      code: rows[i].code,
      rank,
      dash: share * CIRCUMFERENCE,
      gap: CIRCUMFERENCE - share * CIRCUMFERENCE,
      offset,
    })
    offset += share * CIRCUMFERENCE
    rank += 1
  }
  return arcs
}

/**
 * ⚠ COMPLETE LITERAL CLASS NAMES. Tailwind's scanner reads source text, so `` `stroke-category-${n}-dot` ``
 * would ship unstyled. Eight swatches exist and no more (`tailwind.config.ts`).
 */
const SLICE_STROKE = [
  'stroke-category-1-dot', 'stroke-category-2-dot', 'stroke-category-3-dot',
  'stroke-category-4-dot', 'stroke-category-5-dot', 'stroke-category-6-dot',
  'stroke-category-7-dot', 'stroke-category-8-dot',
]
const SLICE_DOT = [
  'bg-category-1-dot', 'bg-category-2-dot', 'bg-category-3-dot',
  'bg-category-4-dot', 'bg-category-5-dot', 'bg-category-6-dot',
  'bg-category-7-dot', 'bg-category-8-dot',
]

/**
 * The stroke and the dot for one slice.
 *
 * ⚠⚠ **`none` AND `unsorted` TAKE GROUND TOKENS, NEVER A SWATCH AND NEVER A TONE.** They are the
 * two "we do not know" states — nothing has looked at the row yet, and the sorter looked and could
 * not place it — so they must RECEDE, the way `other` does on the sponsor card. A tone
 * (`caution`/`critical`) is out of the question for a different reason: a tone says something about
 * a STATE, and an unsorted purchase is not a problem, it is a gap in our own filing.
 *
 * ⚠ `rank % 8` because eight swatches exist and nine categories can carry money. Two categories
 * sharing a colour is a cosmetic collision; a class that does not exist is an invisible slice.
 *
 * ⚠ A NEGATIVE RANK MEANS "THIS SLICE WAS NOT DRAWN" — the legend row for a category with no
 * money at all. It takes the palest ground token rather than a swatch, because a coloured dot
 * beside RM0.00 promises a slice the reader will then hunt for in a ring that does not have one.
 */
export function sliceClasses(code: string, rank: number): { stroke: string; dot: string } {
  if (code === 'none') return { stroke: 'stroke-ground-200', dot: 'bg-ground-200' }
  if (code === 'unsorted') return { stroke: 'stroke-ground-300', dot: 'bg-ground-300' }
  if (rank < 0) return { stroke: 'stroke-ground-100', dot: 'bg-ground-100' }
  const i = rank % SLICE_STROKE.length
  return { stroke: SLICE_STROKE[i], dot: SLICE_DOT[i] }
}

// ── axis labels ───────────────────────────────────────────────────────────────────────────────
//
// ⚠ NUMERIC AND BRITISH, NOT A MONTH NAME. `formatDate` formats by hand for exactly this reason:
// a month name would have to be translated three ways for an axis nobody reads aloud, and
// `toLocaleDateString` inherits the runtime's locale, which differs between the server pass and
// the browser one. DD/MM and MM/YYYY are the same characters in every locale we ship.

/** `'2026-03-02'` → `'02/03'`. The ISO-week Monday, as a day and a month. */
export function weekLabel(iso: string): string {
  const [, m = '', d = ''] = String(iso).split('-')
  return d && m ? `${d}/${m}` : String(iso)
}

/** `'2026-07'` → `'07/2026'`. */
export function monthLabel(iso: string): string {
  const [y = '', m = ''] = String(iso).split('-')
  return y && m ? `${m}/${y}` : String(iso)
}

// ── role shaping, read from the payload ───────────────────────────────────────────────────────

/**
 * Is this section actually here?
 *
 * ⚠⚠ **THE PAGE RENDERS BY PRESENCE, NEVER BY ROLE.** `SECTIONS_BY_ROLE` chose the key set
 * server-side before anything was serialised, so the honest question on the client is "did it
 * arrive?" — and asking it this way means a client-side role check can never accidentally widen
 * what a reviewer sees, because there is no client-side role check to get wrong.
 *
 * ⚠ BOTH HALVES ARE CHECKED. `sections` must LIST it and the key must BE there: a listed-but-
 * missing section would render an empty panel that reads as "you have none of these", which is a
 * different claim from "this is not your section".
 */
export function has(
  data: { sections?: string[] } | null | undefined,
  section: string,
): boolean {
  if (!data || !data.sections) return false
  if (data.sections.indexOf(section) === -1) return false
  const value = (data as unknown as Record<string, unknown>)[section]
  return value !== undefined
}

/**
 * The chip for a CASE's verdict clock.
 *
 * ⚠⚠ **THE BAND IS ON THE CASE, NEVER ON THE PERSON** (`reviewerDetail.ts`, and it is not a style
 * note). These are unpaid volunteers, and a colour that calls somebody slow is the thing that page
 * refuses to draw. `overdue` is red because a student has been waiting past the promise we made
 * them; `open` is deliberately plain, because holding a case is the normal state of a reviewer.
 */
export function bandTone(band: string): string {
  if (band === 'overdue') return 'bg-critical-100 text-critical-700'
  if (band === 'due_soon') return 'bg-caution-100 text-caution-700'
  return 'bg-ground-100 text-ground-600'
}
