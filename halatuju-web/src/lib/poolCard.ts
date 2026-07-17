// Pure, node-testable helpers for the sponsor pool card + detail redesign.

/** Whole days from `now` until an ISO date (course start). null when absent/unparseable.
 *  Negative when the date has passed. `now` is injectable for deterministic tests. */
export function daysUntil(iso: string | null | undefined, now: Date = new Date()): number | null {
  if (!iso) return null
  const target = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(target.getTime())) return null
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const ms = target.getTime() - startOfToday.getTime()
  return Math.round(ms / 86_400_000)
}

export type Countdown = { kind: 'today' | 'one' | 'many'; days: number } | null

/** The countdown state a card/sidebar renders — null (hidden) when no date or already past. */
export function countdown(iso: string | null | undefined, now: Date = new Date()): Countdown {
  const d = daysUntil(iso, now)
  if (d === null || d < 0) return null
  if (d === 0) return { kind: 'today', days: 0 }
  if (d === 1) return { kind: 'one', days: 1 }
  return { kind: 'many', days: d }
}

/** Whole-ringgit with thousands grouping, no decimals: "2000.00" -> "2,000". */
export function rmWhole(v: string | number | null | undefined): string {
  if (v === null || v === undefined || String(v).trim() === '') return ''
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

