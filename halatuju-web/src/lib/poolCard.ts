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

/** Funded fraction 0..1 = raised / target, for the funding bar. Guards nulls, a
 *  non-positive/absent target, and clamps to [0,1]. 0 when unfunded (the empty rail). */
export function fundedFraction(
  funded: string | number | null | undefined,
  award: string | number | null | undefined,
): number {
  const target = Number(award)
  const raised = Number(funded)
  if (!Number.isFinite(target) || target <= 0) return 0
  if (!Number.isFinite(raised) || raised <= 0) return 0
  return Math.max(0, Math.min(1, raised / target))
}

/** Whole-ringgit with thousands grouping, no decimals: "2000.00" -> "2,000". */
export function rmWhole(v: string | number | null | undefined): string {
  if (v === null || v === undefined || String(v).trim() === '') return ''
  const n = Number(v)
  if (!Number.isFinite(n)) return String(v)
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}


/**
 * The single lifecycle badge on a sponsored-student card, as token classes.
 *
 * ⚠ THIS USED TO EXIST TWICE — the same six-entry map in `my-students/[id]/page.tsx` and in the
 * My-students grid, the second carrying a comment saying it "mirrors" the first. `docs/lessons.md`
 * is blunt about that shape: the fix for a keep-in-sync pair is to DELETE ONE SIDE, not to sync
 * harder. A duplicated colour map is how one surface gets restyled and the other quietly does not.
 *
 * ⚠ `graduated` MOVED OFF INDIGO in Layer 1 F1, and it is the one deliberate visual change in that
 * sprint. Indigo was a fifth meaning the tone vocabulary does not name, on three uses against ~1,800
 * — too thin to mint a family from, and left raw it would have been the one badge that failed to
 * invert in dark mode. Graduation is the best outcome the programme has, so it is `positive`, given
 * the DEEPER weight so it still reads apart from `semester_completed` at a glance. Distinction by
 * intensity within a meaning, rather than by borrowing an unrelated hue.
 */
export const PORTFOLIO_BADGE_TONE: Record<string, string> = {
  on_track: 'bg-info-100 text-info-700',
  semester_completed: 'bg-positive-100 text-positive-700',
  needs_attention: 'bg-caution-100 text-caution-700',
  paused: 'bg-critical-100 text-critical-700',
  discontinued: 'bg-critical-100 text-critical-700',
  graduated: 'bg-positive-200 text-positive-800',
}

/** Fallback is a real state (an unrecognised status), so it is grey on purpose, not a bug. */
export const PORTFOLIO_BADGE_FALLBACK = 'bg-ground-100 text-ground-600'

export function portfolioBadgeTone(status: string | null | undefined): string {
  return (status && PORTFOLIO_BADGE_TONE[status]) || PORTFOLIO_BADGE_FALLBACK
}
