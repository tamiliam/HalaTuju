'use client'
// The sponsor's spending panel (sponsor spending S5) — categories and totals, nothing else.
//
// ⚠⚠ THIS COMPONENT RENDERS ONLY WHAT THE SERVER SENDS, AND THE SERVER SENDS CATEGORIES AND
// TOTALS. There is no merchant name, no transaction id, no wallet, no purchase date and no time in
// `SponsorSpending` — by construction, not by omission (`spend_sponsor.py`). If a future field
// arrives here that names a shop or a day, the question to answer is whether a SPONSOR may see it,
// and the answer so far has always been no.
//
// ⚠ TWO SHAPES FOR TWO QUESTIONS, AND THEY MUST NOT MERGE. "How much has been released?" is a
// horizontal bar (a fuel gauge). "What was it spent on?" is a donut beside a ranked list. A single
// chart answering both would answer neither.
//
// ⚠ THE LIST IS NOT DECORATION. People read the list; the donut is the shape of it. They get equal
// weight, and the list carries the ringgit.
//
// ⚠ NO CHART LIBRARY. The donut is one SVG circle per slice with a `strokeDasharray` — about
// thirty lines — and the project carries no charting dependency for it.

import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'

/** What the card draws — the SPONSOR's payload and the STUDENT's (S5b) both fit it. Categories by
 *  CODE; the label is always this card's own translation, never a server string. */
export interface SpendingFigures {
  promised: string
  released: string
  spent: string
  left: string
  as_at: string
  categories: Array<{ code: string; total: string }>
}

/* ⚠ THE WORDS ARE THE CALLER'S, AND THERE IS NO DEFAULT (S5b). The sponsor page passes its own
 * `sponsorPortal…spend` prefix, the student's page `bursaryTabs.spend`. A default here would
 * put a sponsor-slice key inside this file, and the slice guard (`sliceReach.test.ts`) would rightly
 * flag every student route that renders the card — her page must never need the sponsor slice. */

/** Slice colours, in rank order.
 *
 * ⚠ NO RAW HEX. The whole product runs on tokens, and the theme guard reads SVG fills and lib
 * constants precisely because colour hides there. `category-N` is the family for this job:
 * eight swatches that MEAN NOTHING in themselves, so one arbitrary category can be told from
 * the next. Never a TONE here — `positive`/`critical` say something about a state, and a
 * spending category is not a state. Nothing on this card should read as a warning.
 *
 * ⚠ `other` takes a GROUND token, not a ninth swatch: it is not a category, it is the absence
 * of one, and it should recede.
 */
const SLICE_STROKE = [
  'stroke-category-1-dot', 'stroke-category-2-dot', 'stroke-category-3-dot',
  'stroke-category-4-dot', 'stroke-category-5-dot', 'stroke-category-6-dot',
]
const SLICE_DOT = [
  'bg-category-1-dot', 'bg-category-2-dot', 'bg-category-3-dot',
  'bg-category-4-dot', 'bg-category-5-dot', 'bg-category-6-dot',
]
const OTHER_STROKE = 'stroke-ground-300'
const OTHER_DOT = 'bg-ground-300'

const num = (v: string) => Number(v) || 0

/** Thousands grouping, hand-formatted so server and browser render identically (no locale drift).
 *  ⚠ The value arrives as a STRING and is only parsed for the CHART geometry, never for display. */
function rm(v: string) {
  const [whole, cents = '00'] = String(v).split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`
}

export default function SpendingCard({ spending, copy }: {
  spending: SpendingFigures
  /** The message prefix for every word on the card (`title`, `asAt`, `promised`… `cat.<code>`). */
  copy: string
}) {
  const { t } = useT()

  // ⚠ Parsed ONLY for the bar's geometry. Every figure on screen is rendered from the STRING the
  // server sent, never from these — money is not arithmetic the browser should be redoing.
  const promised = num(spending.promised)
  const released = num(spending.released)

  // ⚠ "Spent" CAN exceed "released" — the wallet is the student's own and a parent may top it up.
  // The bar must not overflow its track and the copy must never imply the student overspent our
  // money. Both widths are clamped; `left` is already floored at zero by the server.
  const pct = (value: number) =>
    promised > 0 ? Math.max(0, Math.min(100, (value / promised) * 100)) : 0

  const rows = spending.categories
  const total = rows.reduce((sum, r) => sum + num(r.total), 0)

  // Donut geometry: one circle per slice, offset by everything before it.
  const R = 56
  const C = 2 * Math.PI * R
  let offset = 0
  const arcs = rows.map((r, i) => {
    const share = total > 0 ? num(r.total) / total : 0
    const arc = {
      code: r.code,
      stroke: r.code === 'other' ? OTHER_STROKE : SLICE_STROKE[i % SLICE_STROKE.length],
      dash: share * C, gap: C - share * C, offset,
    }
    offset += share * C
    return arc
  })

  const label = (code: string) =>
    code === 'other' ? t(`${copy}.other`)
      : t(`${copy}.cat.${code}`)

  return (
    <section className="mt-6 rounded-xl border border-ground-200 bg-ground-0 p-5"
      data-testid="spending-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-ground-900">
          {t(`${copy}.title`)}
        </h2>
        {/* ⚠ The date we last UPDATED, never the day the student last bought something. */}
        <span className="text-xs text-ground-400">
          {t(`${copy}.asAt`, { date: formatDate(spending.as_at) })}
        </span>
      </div>

      {/* ── the money bar: released against promised ── */}
      <div className="mt-4 h-2.5 w-full overflow-hidden rounded-full bg-ground-100"
        role="img"
        aria-label={t(`${copy}.barLabel`)}>
        <div className="h-full rounded-full bg-primary-500"
          style={{ width: `${pct(released)}%` }} data-testid="released-bar" />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="spending-figures">
        {([['promised', spending.promised], ['released', spending.released],
           ['spent', spending.spent], ['left', spending.left]] as const).map(([key, value]) => (
          <div key={key}>
            <dt className="text-[10px] font-semibold uppercase tracking-wider text-ground-400">
              {t(`${copy}.${key}`)}
            </dt>
            <dd className="mt-0.5 text-base font-medium tabular-nums text-ground-900">
              RM{rm(value)}
            </dd>
          </div>
        ))}
      </dl>

      {/* ── the donut and the list, equal weight ── */}
      <div className="mt-6 flex flex-col gap-6 border-t border-ground-100 pt-6 sm:flex-row sm:items-center">
        <svg viewBox="0 0 140 140" className="h-40 w-40 shrink-0 -rotate-90"
          role="img" aria-label={t(`${copy}.chartLabel`)}
          data-testid="spending-donut">
          <circle cx="70" cy="70" r={R} fill="none" className="stroke-ground-100" strokeWidth="18" />
          {arcs.map((a) => (
            <circle key={a.code} cx="70" cy="70" r={R} fill="none"
              className={a.stroke} strokeWidth="18"
              strokeDasharray={`${a.dash} ${a.gap}`} strokeDashoffset={-a.offset} />
          ))}
        </svg>

        <ul className="min-w-0 flex-1 space-y-1.5" data-testid="spending-list">
          {rows.map((r, i) => (
            <li key={r.code} className="flex items-baseline gap-2 text-sm">
              <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                r.code === 'other' ? OTHER_DOT : SLICE_DOT[i % SLICE_DOT.length]}`} />
              <span className="min-w-0 flex-1 truncate text-ground-700">{label(r.code)}</span>
              <span className="tabular-nums text-ground-900">RM{rm(r.total)}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* ── the assumptions note (brief §4d). ⚠ It names no shop, states no threshold, and does
          not apologise: it is a statement of method, not a disclaimer. ── */}
      <p className="mt-6 rounded-lg bg-ground-50 p-3 text-xs leading-relaxed text-ground-600">
        <span className="font-semibold text-ground-700">
          {t(`${copy}.noteTitle`)}
        </span>{' '}
        {t(`${copy}.note`)}
      </p>
    </section>
  )
}
