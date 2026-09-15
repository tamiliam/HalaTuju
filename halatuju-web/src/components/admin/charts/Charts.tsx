'use client'
/**
 * The console's chart set — three shapes, about two hundred lines, no library.
 *
 * ⚠⚠ **THIS IS THE SECOND CHART, WHICH IS THE TRIGGER THE FIRST ONE NAMED.** `docs/decisions.md`
 * recorded the sponsor donut with its own revisit clause — *"when a second chart appears, build a
 * shared primitive"* — and this page is that second chart. The donut geometry below is the
 * sponsor card's, moved into `lib/programmeOverview.ts` so there is one of it rather than two.
 *
 * ⚠⚠ **NO `#` COLOUR ANYWHERE IN THIS FILE, AND THE TEST READS THE RENDERED MARKUP FOR ONE.**
 * The theme guards scan source for raw hex precisely because colour hides in SVG attributes —
 * `fill="#2563eb"` is invisible to a class-based scan and survives every theme swap unchanged.
 * Every colour here is a Tailwind token class (`fill-brand-shape`, `stroke-ground-200`,
 * `stroke-category-N-dot`), which is also what makes these charts legible in dark mode without a
 * second palette.
 *
 * ⚠ **FIXED `viewBox`, NO ResizeObserver.** An SVG with a viewBox scales itself; measuring the
 * container in JavaScript to draw the same picture again would buy a layout read, a second render
 * and a hydration mismatch.
 *
 * ⚠ **EVERY CHART RENDERS ITS FIGURES AS TEXT BENEATH IT.** Not decoration and not a fallback: a
 * value that exists only as a pixel height cannot be read aloud, quoted in an email, or checked
 * against the Payments footer. `role="img"` plus `aria-label` names the SHAPE; the `<ol>` carries
 * the numbers.
 */

import { barLayout, donutArcs, lineLayout, sliceClasses, type ChartBox, WIDE_BOX, DONUT_RADIUS } from '@/lib/programmeOverview'

/** One line of the text beneath a chart — the name of a column and what it was. */
export interface ChartFigure { label: string; value: string }

/** ⚠ `className` IS A COMPLETE LITERAL, passed in by the caller (`fill-brand-shape`), because
 *  Tailwind's scanner reads source text and cannot see a class assembled at runtime. */
export interface BarSeries {
  key: string
  className: string
  values: readonly number[]
}

function Figures({ testId, figures }: { testId: string; figures: readonly ChartFigure[] }) {
  return (
    <ol className="mt-2.5 flex flex-wrap gap-x-3.5 gap-y-1 text-[11px] tabular-nums text-ground-500"
      data-testid={`${testId}-figures`}>
      {figures.map((f) => (
        <li key={f.label}>
          {f.label} <span className="font-semibold text-ground-700">{f.value}</span>
        </li>
      ))}
    </ol>
  )
}

/** The first and last column, named under the axis. The rest are in the figures list. */
function EndLabels({ columns, box }: { columns: readonly string[]; box: ChartBox }) {
  if (columns.length === 0) return null
  const last = columns[columns.length - 1]
  return (
    <>
      <text x={box.side} y={box.height - 6} className="fill-ground-400 text-[9px]">{columns[0]}</text>
      {columns.length > 1 && (
        <text x={box.width - box.side} y={box.height - 6} textAnchor="end"
          className="fill-ground-400 text-[9px]">{last}</text>
      )}
    </>
  )
}

/**
 * Bars, one or two series per column, with an optional line across them.
 *
 * ⚠ THE LINE SHARES THE BARS' UNIT BUT NOT THEIR SCALE, AND THE CALLER IS TOLD SO IN WORDS. On
 * the money chart the bars are one month's ringgit and the line is the RUNNING total still sitting
 * in wallets, which is an order of magnitude larger by design. Forcing both onto one axis would
 * flatten every bar to nothing; giving the line its own is honest only because the figures table
 * beneath prints both, to the cent. (`lineLayout` keeps zero in its own domain, so a negative gap
 * still crosses the line it should.)
 */
export function BarChart({
  series, columns, figures, line, label, testId, box = WIDE_BOX,
}: {
  series: readonly BarSeries[]
  columns: readonly string[]
  figures: readonly ChartFigure[]
  line?: { values: readonly number[]; className: string }
  label: string
  testId: string
  box?: ChartBox
}) {
  const { bars, baseline } = barLayout(series.map((s) => s.values), box)
  const path = line ? lineLayout(line.values, box) : null
  return (
    <div data-testid={testId}>
      <svg viewBox={`0 0 ${box.width} ${box.height}`} className="block h-auto w-full"
        role="img" aria-label={label}>
        <line x1={box.side} y1={baseline} x2={box.width - box.side} y2={baseline}
          className="stroke-ground-200" strokeWidth="1" />
        {series.map((s, i) => (
          <g key={s.key} className={s.className}>
            {bars[i].map((b, j) => (
              <rect key={`${s.key}-${j}`} x={b.x} y={b.y} width={b.width} height={b.height} />
            ))}
          </g>
        ))}
        {path && path.points.length > 1 && (
          <polyline fill="none" strokeWidth="2" strokeDasharray="4 3"
            className={line!.className}
            points={path.points.map((p) => `${p.x},${p.y}`).join(' ')} />
        )}
        <EndLabels columns={columns} box={box} />
      </svg>
      <Figures testId={testId} figures={figures} />
    </div>
  )
}

/**
 * One line across the columns, with the latest point marked.
 *
 * ⚠ A SINGLE POINT DRAWS A DOT, NOT A LINE. One week of data is a fact; a polyline of one point
 * renders nothing at all, which reads as "no data" rather than "one week so far".
 */
export function LineChart({
  values, columns, figures, label, testId, className = 'stroke-brand-shape', box = WIDE_BOX,
}: {
  values: readonly number[]
  columns: readonly string[]
  figures: readonly ChartFigure[]
  label: string
  testId: string
  className?: string
  box?: ChartBox
}) {
  const { points, zeroY, min } = lineLayout(values, box)
  const latest = points.length > 0 ? points[points.length - 1] : null
  return (
    <div data-testid={testId}>
      <svg viewBox={`0 0 ${box.width} ${box.height}`} className="block h-auto w-full"
        role="img" aria-label={label}>
        <line x1={box.side} y1={box.height - box.bottom} x2={box.width - box.side}
          y2={box.height - box.bottom} className="stroke-ground-200" strokeWidth="1" />
        {/* ⚠ Drawn ONLY when something is actually negative — otherwise the zero line and the
            baseline are the same line, and two strokes on one pixel read as a heavier axis. */}
        {min < 0 && (
          <line x1={box.side} y1={zeroY} x2={box.width - box.side} y2={zeroY}
            className="stroke-ground-300" strokeWidth="1" strokeDasharray="2 2" />
        )}
        {points.length > 1 && (
          <polyline fill="none" strokeWidth="2" className={className}
            points={points.map((p) => `${p.x},${p.y}`).join(' ')} />
        )}
        {latest && <circle cx={latest.x} cy={latest.y} r="3" className="fill-brand-shape" />}
        <EndLabels columns={columns} box={box} />
      </svg>
      <Figures testId={testId} figures={figures} />
    </div>
  )
}

/**
 * The ring and the list, equal weight — the sponsor card's rule, kept.
 *
 * ⚠⚠ **EVERY ROW IS LISTED; ONLY THE NON-ZERO ONES ARE DRAWN.** `by_category` sends all eleven
 * slices on purpose, and a slice at zero is information — "nothing was spent on health" is an
 * answer. But a zero-length arc is invisible, so drawing it would spend a colour the next real
 * category then cannot have. The legend is the `<ol>` of figures for this chart; people read the
 * list, and the ring is the shape of it.
 */
export function Donut({
  rows, label, testId,
}: {
  rows: ReadonlyArray<{ code: string; label: string; display: string; total: string }>
  label: string
  testId: string
}) {
  const arcs = donutArcs(rows)
  // The colour a row gets depends on its rank among the rows that HAVE money, so the legend has to
  // read it back from the arcs rather than re-deriving it from its own index.
  const rankOf = (code: string) => {
    const hit = arcs.filter((a) => a.code === code)[0]
    return hit ? hit.rank : -1
  }
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
      <svg viewBox="0 0 140 140" className="h-32 w-32 shrink-0 -rotate-90"
        role="img" aria-label={label} data-testid={testId}>
        <circle cx="70" cy="70" r={DONUT_RADIUS} fill="none" className="stroke-ground-100"
          strokeWidth="18" />
        {arcs.map((a) => (
          <circle key={a.code} cx="70" cy="70" r={DONUT_RADIUS} fill="none" strokeWidth="18"
            className={sliceClasses(a.code, a.rank).stroke}
            strokeDasharray={`${a.dash} ${a.gap}`} strokeDashoffset={-a.offset} />
        ))}
      </svg>
      <ol className="min-w-0 flex-1 text-xs" data-testid={`${testId}-figures`}>
        {rows.map((r) => (
          <li key={r.code}
            className="flex items-center gap-2 border-b border-ground-100 py-1 last:border-b-0">
            <span className={`h-2 w-2 shrink-0 rounded-sm ${sliceClasses(r.code, rankOf(r.code)).dot}`} />
            <span className="min-w-0 flex-1 truncate text-ground-700">{r.label}</span>
            <span className="shrink-0 tabular-nums font-medium text-ground-900">{r.display}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
