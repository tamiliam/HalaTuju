/**
 * Sponsor detail — the pure decisions behind `/admin/sponsors/[id]` (2026-07-27).
 *
 * The server is authoritative on everything that matters (who may see which money, whether
 * the finance step is armed, what a credit's status is). What lives here is only what the SCREEN
 * has to decide: how to phrase a date, which sign-off steps to draw, and whether an action
 * is offered. Nothing here re-derives a rule the server would refuse, so there is no pair to
 * keep honest.
 */
import type { AdminSponsorCredit, AdminSponsorDetail } from './admin-api'

/**
 * Is the check step armed for THIS credit? The server answers it per credit (`check_required`:
 * a holder of the key who has NOT signed this credit exists, A1.10a review fix), so a keyed Admin
 * who signed as maker never shows their own credit as waiting for a check nobody can do. A payload
 * without the per-credit field falls back to the screen-wide `finance_check_required`.
 */
export function creditArmed(credit: AdminSponsorCredit, financeCheckRequired: boolean): boolean {
  return credit.check_required ?? financeCheckRequired
}

/** How long since a sponsor was last seen, as a band the screen can colour. */
export type SeenBand = 'never' | 'today' | 'recent' | 'dormant'

/**
 * `never` means **no record**, NOT "never came back" — the column only started recording on
 * 2026-07-27, so every sponsor who joined before that reads `never` until their next visit.
 * The copy says so ("No sign-in recorded"); it originally said "Not since joining", which
 * asserted history this field does not have. `dormant` is 30+ days — long enough to mean
 * something for a giving relationship, short enough to still be actionable.
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

/** Which step of the chain a credit is waiting on, and what this viewer may do about it. */
export interface CreditActions {
  /** The step awaiting a signature, or null once the credit is settled. */
  nextStep: 'recorded' | 'checked' | 'approved' | null
  /** True when the next step is this viewer's (served `can_sign`). */
  canSign: boolean
  /**
   * Set when the viewer cannot sign for a reason worth SAYING rather than hiding: an approver
   * looking at a credit that waits on the check is told so (served `blocked`), as the service
   * answers `finance_check_required` rather than a bare wrong_role.
   */
  blocked: 'awaiting_finance' | null
  canVoid: boolean
}

/**
 * The per-credit action set. S3 / M4b (owner rulings Q-A to Q-C, 23 Nov): every seat is a switch,
 * and the server SERVES the answer per credit (`credit_steps.served`: `can_sign`, `blocked`,
 * `can_void`) — `same_signer` included, which the screen could never check from names. The screen
 * derives only WHICH step is next (a label), from the status and `financeArmed` (`creditArmed`).
 * A payload without the served flags offers nothing.
 */
export function creditActions(credit: AdminSponsorCredit, financeArmed: boolean): CreditActions {
  const settled = { nextStep: null, canSign: false, blocked: null, canVoid: false } as const
  let nextStep: CreditActions['nextStep']
  if (credit.status === 'draft') nextStep = 'recorded'
  else if (credit.status === 'admin_signed') nextStep = financeArmed ? 'checked' : 'approved'
  else if (credit.status === 'finance_checked') nextStep = 'approved'
  else return settled
  return {
    nextStep,
    canSign: credit.can_sign === true,
    blocked: credit.blocked ?? null,
    canVoid: credit.can_void === true,
  }
}

/**
 * Who may RECORD a credit — served (`can_record_credit`, `credit_steps.may_record`): Sponsors: edit
 * stored in the person's own seat, or a super. An organisation admin never records (owner Q-A,
 * 23 Nov): the approver has to stay free to countersign.
 */
export function canRecordCredit(detail: Pick<AdminSponsorDetail, 'can_record_credit'>): boolean {
  return detail.can_record_credit === true
}

/**
 * The gifts a credit may be recorded into: those the sponsor was ACCEPTED into.
 *
 * Not the wallet list — `record_admin_credit` refuses `sponsor_not_in_programme`, and a
 * sponsor accepted into a gift they have not yet given to holds no wallet, which is exactly
 * the case a first credit is for. A pending or revoked membership is not creditable.
 */
export function creditableProgrammes(
  detail: AdminSponsorDetail,
): Array<{ programme_id: number; programme_name: string }> {
  return detail.memberships
    .filter((m) => m.status === 'approved' && m.programme_id != null)
    .map((m) => ({ programme_id: m.programme_id as number, programme_name: m.programme_name }))
}

/*
 * Who may accept a benefactor into a gift, or take it back: since M3c (list W) the server's door
 * `sponsor_vet` (`sponsors.approve`), read on the page with `holdsDoor` — no role rule here. A team
 * member granted the key reaches only their own organisation's gifts (the server fences by gift).
 */

/** One gift, with where this benefactor stands in it. `status: ''` means NOT IN IT YET. */
export interface MembershipRow {
  programme_id: number
  programme_name: string
  is_active: boolean
  status: '' | 'pending' | 'approved' | 'rejected' | 'suspended' | string
}

/**
 * Every gift the admin may act on, joined to this benefactor's standing in each.
 *
 * ⚠ DRIVEN BY `assignable_programmes`, NOT by `memberships`. The memberships list says where
 * they already are; a panel built from it could only ever restate the status quo, and the
 * whole point is the gift they are **not** in — which is what the Sabah RM100,000 was waiting
 * on. A gift with no membership row shows `status: ''` rather than being hidden.
 *
 * A legacy membership whose gift is not in the assignable list (another tenant's, for a super
 * reading a fenced-out row) is not appended: this list is what the panel can WRITE to.
 */
export function membershipRows(detail: AdminSponsorDetail): MembershipRow[] {
  const held = new Map(
    detail.memberships
      .filter((m) => m.programme_id != null)
      .map((m) => [m.programme_id as number, m.status]),
  )
  return detail.assignable_programmes.map((p) => ({
    programme_id: p.id,
    programme_name: p.name,
    is_active: p.is_active,
    status: held.get(p.id) ?? '',
  }))
}

/**
 * Every error code the membership endpoint answers with, mapped to a copy key.
 *
 * Same allowlist discipline as `creditErrorKey` and for the same reason: `t()` returns the
 * key on a miss, so interpolating an unknown server code renders a raw dotted path on screen.
 */
const MEMBERSHIP_ERROR_CODES = [
  'programme_required', 'bad_status', 'account_not_approved', 'not_found',
] as const

export function membershipErrorKey(code: string | undefined): string {
  return (MEMBERSHIP_ERROR_CODES as readonly string[]).includes(code ?? '')
    ? (code as string)
    : 'unknown'
}

/**
 * Every error code the credit endpoints answer with, mapped to a copy key.
 *
 * An unrecognised code falls back to `unknown` rather than being interpolated into a key:
 * our `t()` returns the key itself on a miss, so a new server code would otherwise render as
 * `admin.sponsors.detail.creditError.some_new_code` on screen. That exact failure has shipped
 * here before — ~47 raw `sponsorPortal.*` key paths lived on production for four sprints
 * (L109) — so the allowlist is the guard.
 */
const CREDIT_ERROR_CODES = [
  'invalid_amount', 'external_reference_required', 'programme_required',
  'sponsor_not_in_programme', 'wrong_role', 'bad_state', 'name_mismatch',
  'same_signer', 'finance_check_required', 'stale',
] as const

export function creditErrorKey(code: string | undefined): string {
  return (CREDIT_ERROR_CODES as readonly string[]).includes(code ?? '')
    ? (code as string)
    : 'unknown'
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
