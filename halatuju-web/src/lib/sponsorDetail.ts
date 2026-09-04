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

/**
 * Whether this credit's STATE allows a void.
 *
 * A confirmed credit can never be cancelled — it is reversed by a compensating entry
 * (decisions.md, 2026-07-26). Offering a Void button on one would promise something the
 * service refuses. The role half of the question lives in `creditActions`, which calls
 * this rather than re-testing the status, so the two can never disagree.
 */
export function canVoid(credit: AdminSponsorCredit): boolean {
  return credit.status !== 'confirmed' && credit.status !== 'cancelled'
}

/** Which step of the chain a credit is waiting on, and what this viewer may do about it. */
export interface CreditActions {
  /** The step awaiting a signature, or null once the credit is settled. */
  nextStep: 'recorded' | 'checked' | 'approved' | null
  /** True when this viewer's role owns `nextStep`. */
  canSign: boolean
  /**
   * Set when the viewer cannot sign for a reason worth SAYING rather than hiding: an
   * org_admin looking at a credit that is waiting on the finance check sees nothing amiss
   * from their seat, so the service answers `finance_check_required` rather than a bare
   * wrong_role — and the screen should say the same thing.
   */
  blocked: 'awaiting_finance' | null
  canVoid: boolean
}

/**
 * The per-credit action set, mirroring `sponsorship.sign_admin_credit` step for step.
 *
 * **The service is the authority** — every rule here is enforced there, and this mirror
 * exists only so the screen doesn't draw a control the endpoint would refuse (the same
 * relationship `paymentStatus.signOffView` has with `payments.sign`). Two rules are
 * deliberately NOT mirrored:
 *
 * - **`same_signer`** — the payload carries signer NAMES, not emails, and the service keys
 *   distinctness on email precisely because production has two active admins sharing the
 *   name "Ve. Elanjelian". A name comparison here would be wrong in both directions, so the
 *   button is offered and the server's refusal is rendered.
 * - **`name_mismatch`** — the typed name is checked against `PartnerAdmin.name` server-side.
 *
 * `financeArmed` is read from the payload (`finance_check_required`), never derived, because
 * appointing a finance admin arms the middle step for a credit already in flight.
 */
export function creditActions(
  credit: AdminSponsorCredit,
  financeArmed: boolean,
  viewerRole: string,
): CreditActions {
  const isSuper = viewerRole === 'super'
  const may = (role: string) => isSuper || viewerRole === role
  // Void is the maker's or the approver's power, and only before the money is spendable.
  const voidable = canVoid(credit) && (may('admin') || may('org_admin'))

  if (credit.status === 'draft') {
    return { nextStep: 'recorded', canSign: may('admin'), blocked: null, canVoid: voidable }
  }
  if (credit.status === 'admin_signed' && financeArmed) {
    return {
      nextStep: 'checked',
      canSign: may('finance'),
      blocked: viewerRole === 'org_admin' ? 'awaiting_finance' : null,
      canVoid: voidable,
    }
  }
  if (credit.status === 'admin_signed' || credit.status === 'finance_checked') {
    return { nextStep: 'approved', canSign: may('org_admin'), blocked: null, canVoid: voidable }
  }
  return { nextStep: null, canSign: false, blocked: null, canVoid: false }
}

/**
 * Who may RECORD a credit: the maker (`admin`) or a super.
 *
 * `org_admin` is deliberately excluded, matching `record_admin_credit`. On production the
 * person who does this work is a plain `admin`, and the approver has to stay free to
 * countersign — a maker who is also the approver cannot complete their own chain.
 */
export function canRecordCredit(viewerRole: string): boolean {
  return viewerRole === 'super' || viewerRole === 'admin'
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

/**
 * Who may accept a benefactor into a gift, or take it back.
 *
 * ⚠ DELIBERATELY NARROWER THAN `canRecordCredit`, and in the other direction. Recording a
 * credit is bookkeeping an `admin` does; deciding **who may fund your students** is the
 * organisation's own decision, so it sits with `org_admin` — the same gate as sponsor
 * vetting. The server holds the same pair; this only decides whether to draw the panel.
 */
export function canSetMembership(viewerRole: string): boolean {
  return viewerRole === 'super' || viewerRole === 'org_admin'
}

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
  'same_signer', 'finance_check_required',
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
