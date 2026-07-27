/**
 * Sponsor detail — the pure decisions behind `/admin/sponsors/[id]` (2026-07-27).
 *
 * The server is authoritative on everything that matters (who may see which money, whether
 * the finance step is armed, what a credit's status is). This mirrors only what the SCREEN
 * has to decide: how to phrase a date, which sign-off steps to draw, and whether an action
 * is offered. Nothing here re-derives a rule the server would refuse.
 */
import type { AdminSponsorCredit, AdminSponsorDetail } from './admin-api'

/** How long since a sponsor was last seen, as a band the screen can colour. */
export type SeenBand = 'never' | 'today' | 'recent' | 'dormant'

/**
 * `never` is the one that matters: an approved sponsor who has not come back at all was
 * invisible before this field existed. `dormant` is 30+ days — long enough to mean something
 * for a giving relationship, short enough to still be actionable.
 */
export function seenBand(lastSeenAt: string | null, now: Date = new Date()): SeenBand {
  if (!lastSeenAt) return 'never'
  const days = (now.getTime() - new Date(lastSeenAt).getTime()) / 86_400_000
  if (days < 1) return 'today'
  return days >= 30 ? 'dormant' : 'recent'
}

/** One step of a credit's sign-off chain, for rendering — never for deciding who may sign. */
export interface ChainStep {
  key: 'recorded' | 'checked' | 'approved'
  done: boolean
  by: string
  at: string | null
}

/**
 * The chain as the screen should draw it: **keyed on the SIGNATURES collected**, not on the
 * organisation's current finance setting.
 *
 * That distinction is load-bearing and borrowed from `paymentStatus.signOffView`: a credit
 * confirmed before a finance admin existed has no finance signature, and must render as a
 * two-step chain rather than implying somebody skipped a step. `financeArmed` therefore only
 * adds the middle step for a credit still in flight.
 */
export function creditChain(credit: AdminSponsorCredit, financeArmed: boolean): ChainStep[] {
  const steps: ChainStep[] = [
    {
      key: 'recorded',
      done: !!credit.recorded_at,
      by: credit.recorded_by,
      at: credit.recorded_at,
    },
  ]
  const settled = credit.status === 'confirmed' || credit.status === 'cancelled'
  if (credit.finance_checked_at || (financeArmed && !settled)) {
    steps.push({
      key: 'checked',
      done: !!credit.finance_checked_at,
      by: credit.finance_checked_by,
      at: credit.finance_checked_at,
    })
  }
  steps.push({
    key: 'approved',
    done: !!credit.confirmed_at,
    by: credit.confirmed_by,
    at: credit.confirmed_at,
  })
  return steps
}

/**
 * Whether the screen may offer to VOID this credit.
 *
 * A confirmed credit can never be cancelled — it is reversed by a compensating entry
 * (decisions.md, 2026-07-26). Offering a Void button on one would promise something the
 * service refuses.
 */
export function canVoid(credit: AdminSponsorCredit): boolean {
  return credit.status !== 'confirmed' && credit.status !== 'cancelled'
}

/** Money that has NOT cleared the chain, summed — shown as an explicit caveat, never in a tile. */
export function pendingTotal(credits: AdminSponsorCredit[]): number {
  return credits
    .filter((c) => c.status !== 'confirmed' && c.status !== 'cancelled')
    .reduce((sum, c) => sum + Number(c.amount), 0)
}

/**
 * A sponsorship's stage, collapsed for display.
 *
 * `offered` is deliberately its own band rather than folded into "active": with award
 * acceptance switched off nothing ever reaches `active`, so calling an offered allocation
 * anything else would misreport the entire programme.
 */
export function studentStage(status: string): 'awaiting' | 'active' | 'ended' {
  if (status === 'offered') return 'awaiting'
  if (status === 'active') return 'active'
  return 'ended'
}

/** True when this sponsor has no wallet at all — the screen shows an honest empty state. */
export function hasNoMoney(detail: AdminSponsorDetail): boolean {
  return detail.programmes.length === 0
}
