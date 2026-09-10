/**
 * The COST side of /admin/billing — pure presentation helpers (2026-09-11).
 *
 * Node-testable, no React, no i18n objects: label KEYS only, the page resolves them.
 *
 * ⚠ **Money never becomes a number here.** Every amount arrives as a string because it is a
 * Decimal on the server, and a JavaScript number cannot hold one without drifting. These helpers
 * FORMAT and ORDER; they never add. All the arithmetic already happened where the audit trail is.
 */
import type {
  BillingCharge, BillingCostsPayload, BillingRateRow, PlatformCostBlock,
} from '@/lib/admin-api'

/** Cost sources in the order the breakdown renders them: biggest and most permanent first, so
 *  the reader meets the bill in the order it actually matters. Each maps to an i18n key
 *  admin.billing.cost.source.<source>. Anything unrecognised is appended alphabetically. */
export const COST_SOURCE_ORDER: string[] = ['gcp', 'supabase', 'workspace', 'twilio', 'brevo', 'other']

/** How far either side of today the rates screen offers an effective-from month. */
export const RATE_MONTHS_BACK = 6
export const RATE_MONTHS_FORWARD = 6

/**
 * Months offered as a rate's effective-from, oldest first, as 'YYYY-MM'.
 *
 * ⚠ A MONTH LIST, not a date input. A rate only ever applies from the first of a billed month
 * (`platform_cost._month_start`), and a native date box follows the BROWSER's own locale — the
 * trap that made a time field untypeable and left Save asleep with no error. A plain `<select>`
 * has no locale and no silent empty state.
 *
 * It lives here rather than beside the page because a Next.js page file may export nothing but
 * `default` and the framework's own reserved names.
 */
export function rateMonthOptions(today: Date): string[] {
  const out: string[] = []
  for (let i = -RATE_MONTHS_BACK; i <= RATE_MONTHS_FORWARD; i++) {
    // Day 1 with an out-of-range month index: the Date constructor rolls the year for us, so
    // December + 1 is next January rather than month 13.
    const d = new Date(today.getFullYear(), today.getMonth() + i, 1)
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return out
}

/** The three rate categories, in the order the rates screen lists them. */
export const RATE_CATEGORIES: string[] = ['infrastructure', 'metered', 'development']

/** The two kinds a rate can be. A category may carry either, both, or neither. */
export const RATE_KINDS: string[] = ['margin_pct', 'hourly_rate']

/** Ringgit for display: "RM1,800.00". Null/blank becomes an em dash, NEVER "RM0.00" — a figure
 *  we do not have and a figure that is zero are different claims, and only one of them is safe
 *  to put in front of somebody about to send an invoice. */
export function formatMyr(amount: string | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') return '—'
  const n = Number(amount)
  if (!Number.isFinite(n)) return '—'
  return `RM${n.toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/** "15%" from "15.00". Trailing zeros dropped: a margin reads as a term, not as a measurement. */
export function formatPct(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('en-MY', { maximumFractionDigits: 2 })}%`
}

/** Hours for display: "27.5h". */
export function formatHours(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('en-MY', { maximumFractionDigits: 1 })}h`
}

/** A month's by-source lines, ordered. Returns a new array; never mutates the input. */
export function orderedCostSources(
  costs: PlatformCostBlock | null | undefined
): { source: string; amount: string | null }[] {
  const by = costs?.by_source || {}
  const rank = (s: string) => {
    const i = COST_SOURCE_ORDER.indexOf(s)
    return i === -1 ? COST_SOURCE_ORDER.length : i
  }
  return Object.keys(by)
    .map((source) => ({ source, amount: by[source] }))
    .sort((a, b) => {
      const ra = rank(a.source)
      const rb = rank(b.source)
      return ra !== rb ? ra - rb : a.source.localeCompare(b.source)
    })
}

/**
 * Does this month's total need a health warning, and which one?
 *
 * ⚠ This is the reason the cost section exists at all rather than a bare total. The module's
 * own words: **a total that mixes measured and hand-typed figures without saying so is not an
 * audit.** Three separate things can make a number less true than it looks, and each has to say
 * so in its own words:
 *
 *   - `incomplete` — an invoice we hold but cannot state in ringgit. The total is a FLOOR.
 *   - `entered`    — some sources are somebody's reading of a PDF, not measured data.
 *   - `caveat`     — a provider whose billing window is not the calendar month.
 *
 * Returned in that order: severity first. A floor is a wrong number; the other two are true
 * numbers that need context.
 */
export function costCaveats(
  costs: PlatformCostBlock | null | undefined
): { kind: 'incomplete' | 'entered' | 'caveat'; detail: string }[] {
  if (!costs) return []
  const out: { kind: 'incomplete' | 'entered' | 'caveat'; detail: string }[] = []
  if (costs.is_complete === false) {
    out.push({
      kind: 'incomplete',
      detail: (costs.unconverted || [])
        .map((u) => `${u.source} ${u.currency} ${u.amount_original ?? '?'}${u.invoice_ref ? ` (${u.invoice_ref})` : ''}`)
        .join(', '),
    })
  }
  if ((costs.entered_sources || []).length > 0) {
    out.push({ kind: 'entered', detail: costs.entered_sources.join(', ') })
  }
  for (const c of costs.period_caveats || []) {
    out.push({ kind: 'caveat', detail: c })
  }
  return out
}

/** True when this month's bill was reduced — the discount gets its own visible line, never a
 *  quietly smaller total. */
export function hasDiscount(charge: BillingCharge | null | undefined): boolean {
  if (!charge) return false
  const n = Number(charge.discount_pct)
  return Number.isFinite(n) && n > 0
}

/** Requests still waiting to be billed, grouped by the organisation that owes them. */
export function unbilledByOrg(
  payload: BillingCostsPayload | null | undefined
): { organisation_id: number; organisation: string; rows: BillingCostsPayload['unbilled_requests'] }[] {
  const groups = new Map<number, { organisation_id: number; organisation: string; rows: BillingCostsPayload['unbilled_requests'] }>()
  for (const r of payload?.unbilled_requests || []) {
    const g = groups.get(r.organisation_id)
      || { organisation_id: r.organisation_id, organisation: r.organisation, rows: [] }
    g.rows.push(r)
    groups.set(r.organisation_id, g)
  }
  // `Array.from`, not a spread: the build target here predates downlevel iteration (TD-221).
  return Array.from(groups.values())
    .sort((a, b) => a.organisation.localeCompare(b.organisation))
}

/**
 * The rate table as a grid: one row per (category, kind), holding the value IN FORCE NOW and
 * everything it replaced.
 *
 * ⚠ A missing pair is returned with `current: null`, deliberately — **not skipped**. An hourly
 * rate nobody has set is the single most important thing this screen can say, because until it
 * exists no development work can be billed at all. A row that simply is not drawn says nothing;
 * a row that says "not set" gets acted on.
 */
export function rateGrid(rows: BillingRateRow[] | null | undefined): {
  category: string
  kind: string
  current: BillingRateRow | null
  history: BillingRateRow[]
}[] {
  const all = rows || []
  const out: { category: string; kind: string; current: BillingRateRow | null; history: BillingRateRow[] }[] = []
  for (const category of RATE_CATEGORIES) {
    for (const kind of RATE_KINDS) {
      // Newest first. `effective_from` is 'YYYY-MM-DD', so a plain string compare is a date
      // compare — no Date objects, and therefore no timezone to get wrong.
      const matching = all
        .filter((r) => r.category === category && r.kind === kind)
        .sort((a, b) => b.effective_from.localeCompare(a.effective_from))
      out.push({
        category,
        kind,
        current: matching[0] || null,
        history: matching.slice(1),
      })
    }
  }
  return out
}
