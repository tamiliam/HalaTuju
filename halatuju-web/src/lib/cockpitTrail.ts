/**
 * Officer cockpit — the header timeline, org reject, reviewer / witness cards, rejection trail and assignment options.
 *
 * One of five modules `officerCockpit.ts` was split into (audit A3.3, structure only — every line
 * below is the line it was). `officerCockpit.ts` re-exports all five, so `@/lib/officerCockpit`
 * still serves every importer.
 */

import { isPreSubmissionStage } from './cockpitStages'

// ── Header lifecycle timeline ─────────────────────────────────────────────────

/** One chip in the cockpit header timeline. `labelKey` is the suffix under
 *  `admin.scholarship.*`; `at` is an ISO date (null → the step is pending, "—"). */
export interface HeaderTimelineStep { labelKey: string; at: string | null }

/** Minimal shape the timeline needs (a subset of AdminApplicationDetail). */
export interface TimelineSource {
  status: string
  submitted_at?: string | null
  recommended_at?: string | null
  awarded_at?: string | null
  active_at?: string | null
  maintenance_at?: string | null
}

// Once funded-and-executing, the header pivots to the post-award trio.
const TIMELINE_ACTIVE_PHASE = new Set(['active', 'maintenance', 'closed'])
// QC-cleared but not yet executing: the recommendation → award trio.
const TIMELINE_RECOMMENDED_PHASE = new Set(['recommended', 'awarded'])

/**
 * The three date chips for the header, chosen by lifecycle phase:
 *   • recommended / awarded            → Submitted · Recommended · Awarded
 *   • active / maintenance / closed    → Awarded · Active · Maintenance
 *   • anything earlier                 → null (the header keeps its default
 *                                        Submitted · Applied · Assigned line).
 * A step whose date is null renders as pending ("—").
 */
export function headerTimeline(app: TimelineSource): HeaderTimelineStep[] | null {
  if (TIMELINE_ACTIVE_PHASE.has(app.status)) {
    return [
      { labelKey: 'awarded', at: app.awarded_at ?? null },
      { labelKey: 'active', at: app.active_at ?? null },
      { labelKey: 'maintenance', at: app.maintenance_at ?? null },
    ]
  }
  if (TIMELINE_RECOMMENDED_PHASE.has(app.status)) {
    return [
      { labelKey: 'submitted', at: app.submitted_at ?? null },
      { labelKey: 'recommended', at: app.recommended_at ?? null },
      { labelKey: 'awarded', at: app.awarded_at ?? null },
    ]
  }
  return null
}

// ── Org-admin reject gate (owner 2026-07-21) ─────────────────────────────────

/**
 * Statuses an org admin may reject a student FROM.
 *
 * MIRRORS `services.ORG_REJECT_FROM` in the API — keep the two in step. The reject
 * action is immediate and irreversible, so a card rendered outside this set is not a
 * cosmetic bug: it is a button that looks live and answers 400 (lessons.md 2026-07-16 —
 * the offer-set and the accept-set are one unit of change).
 *
 * drift-test: halatuju-web/src/lib/__tests__/officerGateDrift.test.ts
 */
export const ORG_REJECT_FROM = new Set<string>(['shortlisted'])

/**
 * May this admin reject this application outright?
 *
 * Deliberately NARROWER than every other per-application write. The API's
 * `_require_app_write` also admits a `qc` and the ASSIGNED reviewer, but
 * `AdminOrgRejectView` then narrows to super/org_admin — "rejection is a super feature;
 * the org admin is the super of the organisation" (owner). Mirror that narrowing here so
 * the card never offers what the endpoint refuses.
 *
 * drift-test: halatuju-web/src/lib/__tests__/officerGateDrift.test.ts
 */
export function canOrgReject(
  opts: { isSuper: boolean; role: string | null | undefined; status: string }
): boolean {
  const roleAllowed = opts.isSuper || opts.role === 'org_admin'
  return roleAllowed && ORG_REJECT_FROM.has(opts.status)
}

// ── Right-column card stages (owner 2026-07-22) ──────────────────────────────

/**
 * Statuses at which the REVIEWER ASSIGNED card is hidden because the reviewer is settled and
 * already named in the Recommendation box ("Recommended by … · date", plus "QC accepted by …").
 * Keeping a locked, greyed dropdown next to that is duplicate information.
 *
 * Terminal off-ramps are included: `rejected` shows the reviewer in the decline trail, and a
 * withdrawn/expired case has no reviewer decision left to change (owner: "Yes, rejected as well").
 */
const REVIEWER_CARD_HIDDEN_FROM = new Set<string>([
  'recommended', 'awarded', 'active', 'maintenance', 'closed',
  'rejected', 'withdrawn', 'expired',
])

/**
 * Show the "Reviewer assigned" card? Visible only across the window where the assignment can
 * still change: `profile_complete` → `interviewed`.
 *
 * A super REOPEN needs no special case here, because `reopen.reopen_decision` walks the status
 * back — `recommended → interviewed`, `interviewed → interviewing` — and both land below this
 * threshold, so the card returns by itself (owner: "should that happen, the reviewer box may
 * reappear at Awaiting QC and below"). The one exception is a FUNDED case (awarded/active/
 * maintenance), which reopen deliberately leaves in place: the card stays hidden there and the
 * reviewer can't be swapped from this screen. Accepted — rarer than a reopen, and the reviewer
 * is still named in the Recommendation box.
 */
export function showsReviewerAssignedCard(status: string | null | undefined): boolean {
  if (isPreSubmissionStage(status)) return false     // shortlisted — the Reject card takes this slot
  return !REVIEWER_CARD_HIDDEN_FROM.has(status || '')
}

/**
 * Statuses at which the WITNESS ORGANISATION card is offered.
 *
 * Only a student who will SIGN an agreement needs a witness org, i.e. an AWARDED one — but the
 * card is surfaced one stage earlier, from AWAITING QC, so an org_admin can assign ahead of the
 * award rather than scrambling at signing time (owner 2026-07-22). Deliberately excludes
 * `rejected`/`withdrawn`/`expired`: those students never sign, so the control is noise there.
 *
 * This is the STAGE gate only — the card is additionally limited to SOURCELESS students (no
 * `source`, which would otherwise witness the agreement itself) and to
 * super/admin/org_admin, both of which the cockpit already applies.
 */
const WITNESS_CARD_FROM = new Set<string>([
  'interviewed', 'recommended', 'awarded', 'active', 'maintenance', 'closed',
])

export function showsWitnessCard(status: string | null | undefined): boolean {
  return WITNESS_CARD_FROM.has(status || '')
}

// ── Reporting-date entry (owner 2026-07-23) ─────────────────────────────────

/**
 * Show the "record the reporting date" box?
 *
 * The date is not cosmetic: it sizes the bursary (a course begun before the cohort year = a
 * continuing student, one year of funding left), gates payment eligibility, and triggers the
 * semester-result request. QC now REFUSES to accept a case without one, so a case whose offer
 * letter carries no readable date needs a human to record it — this is where.
 *
 * Deliberately scoped to the reviewer's working window (owner): `interviewing`, or any case whose
 * decision has been REOPENED. A reopen is checked explicitly rather than by status because it
 * lands in two different places — `recommended → interviewed`, `interviewed → interviewing` — so
 * a case bounced back from Recommended would otherwise miss the box. QC cannot fill it in place:
 * they reopen, which returns the case to the reviewer who owns the case's facts.
 *
 * Hidden when the LETTER already carries a date — then the value syncs itself and a manual box
 * would only invite contradicting the document.
 */
export function showsReportingDateBox(opts: {
  status: string | null | undefined
  decisionReopened?: boolean | null
  letterHasDate?: boolean | null
}): boolean {
  if (opts.letterHasDate) return false
  return (opts.status || '') === 'interviewing' || !!opts.decisionReopened
}

// ── Rejection decision trail (owner 2026-07-25) ─────────────────────────────

/**
 * One step of the recorded decision history on a REJECTED case.
 *
 * `reviewerDeclined`/`reviewerRecommended` is the reviewer's own recorded verdict;
 * `qcAcceptedDecline`/`qcAcceptedRecommendation` is the second pair of eyes upholding it;
 * `reopened` is a QC (or super) bouncing the case back; `declined` is a rejection with no
 * separable QC step (the engine's own buckets, an org-admin reject, a post-award contractual
 * decline, or a super who both recorded and confirmed).
 */
export type DecisionTrailStep =
  | { kind: 'reviewerRecommended'; name: string; date: string | null }
  | { kind: 'reviewerDeclined'; name: string; date: string | null }
  | { kind: 'qcAcceptedRecommendation'; name: string; date: string | null }
  | { kind: 'qcAcceptedDecline'; name: string; date: string | null }
  | { kind: 'reopened'; name: string; date: string | null; reason: string }
  | { kind: 'declined'; name: string; date: string | null }

/** Shape of the pieces of the admin payload the trail reads. */
export type DecisionTrailInput = {
  officer_verdict?: { overall?: string } | null
  verdict_decided_by?: string | null
  verdict_decided_by_name?: string | null
  verdict_decided_at?: string | null
  recommended_by?: string | null
  recommended_by_name?: string | null
  recommended_at?: string | null
  rejected_by?: string | null
  rejected_by_name?: string | null
  rejected_at?: string | null
  last_decision_reopen?: {
    reopened_by?: string | null
    reopened_by_name?: string | null
    reviewer_name?: string | null
    reason?: string | null
    created_at?: string | null
  } | null
}

const NO_NAME = '—'

function whoDid(name: string | null | undefined, email: string | null | undefined): string {
  return (name || '').trim() || (email || '').trim() || NO_NAME
}

/**
 * The decision history to show on a REJECTED application, oldest step first.
 *
 * Why this exists: a decline is a TWO-PERSON decision exactly like a recommend — the reviewer
 * records the decline verdict, then a QC upholds it (`AdminQcDecisionView` accept on a decline
 * verdict → `admin_reject`, so `rejected_by` is the QC, not the reviewer). Rendering only
 * "Declined by {rejected_by}" credited the whole decision to the QC and erased the reviewer who
 * actually interviewed the student (#56, owner 2026-07-25) — while an ACCEPTED case named both.
 * This makes the two records symmetric.
 *
 * The QC step is emitted only when a second person is genuinely on record: for a decline, when
 * `rejected_by` differs from the verdict recorder (a `super` may legitimately do both, and
 * naming one person twice would invent a second pair of eyes); for a recommend, when
 * `recommended_by` was captured at QC-accept.
 *
 * A reopened case's reviewer line deliberately carries NO date: `verdict_decided_at` is the
 * LATEST re-recorded decision, not the earlier recommendation the reopen refers to.
 */
export function rejectionTrail(app: DecisionTrailInput): DecisionTrailStep[] {
  const steps: DecisionTrailStep[] = []
  const ro = app.last_decision_reopen || null
  const roReviewer = (ro?.reviewer_name || '').trim()
  const declined = (app.officer_verdict?.overall || '') === 'decline' && !!app.verdict_decided_at

  if (roReviewer || app.verdict_decided_at) {
    steps.push({
      kind: declined ? 'reviewerDeclined' : 'reviewerRecommended',
      name: roReviewer || whoDid(app.verdict_decided_by_name, app.verdict_decided_by),
      date: ro ? null : (app.verdict_decided_at || null),
    })
  }

  // A recommend that a QC upheld before the case was later declined (a post-award contractual
  // decline is the live case) — the QC identity lives on recommended_by, not rejected_by.
  if (!declined && (app.recommended_by || '').trim()) {
    steps.push({
      kind: 'qcAcceptedRecommendation',
      name: whoDid(app.recommended_by_name, app.recommended_by),
      date: app.recommended_at || null,
    })
  }

  if (ro) {
    steps.push({
      kind: 'reopened',
      name: whoDid(ro.reopened_by_name, ro.reopened_by),
      date: ro.created_at || null,
      reason: (ro.reason || '').trim(),
    })
  }

  const qcEmail = (app.rejected_by || '').trim().toLowerCase()
  const recorder = (app.verdict_decided_by || '').trim().toLowerCase()
  const qcUpheldDecline = declined && !!qcEmail && qcEmail !== recorder
  steps.push({
    kind: qcUpheldDecline ? 'qcAcceptedDecline' : 'declined',
    name: whoDid(app.rejected_by_name, app.rejected_by),
    date: app.rejected_at || null,
  })
  return steps
}

// ── the assignment dropdown ───────────────────────────────────────────────────

/** One option in the assignee picker, already decided: shown, and whether it may be chosen. */
export interface AssignOption {
  id: number
  name: string
  role: string
  /** True when the option renders greyed. `reason` says which of the two reasons it is. */
  disabled: boolean
  /**
   * WHY this option is greyed, so the label can say so. A name that is simply unpickable
   * leaves the reader guessing; the whole point of disabling rather than removing is to
   * answer the next question.
   */
  reason: 'paused' | 'otherGift' | null
}

/**
 * Which assignable staff the picker offers, and which are choosable (#10, 2026-08-02).
 *
 * Two rules that look like tidy-up candidates and are not:
 *
 * ⚠ **A PAUSED reviewer is DISABLED, never removed.** The current assignee is unioned in from this
 * same list, so dropping anybody makes their case read "Unassigned" (bug #66); and a name that
 * simply vanishes leaves the reader guessing where it went. The label says why instead.
 *
 * ⚠ **THE CURRENT ASSIGNEE IS NEVER DISABLED**, even when paused. Pause stops NEW work — it does
 * not confiscate a case already theirs — and a `<select>` whose current value is disabled cannot
 * show its own state.
 *
 * ⚠ **A reviewer who does NOT COVER this case's gift gets exactly the same treatment** (S-ASSIGN,
 * 2026-09-04; multi-gift 2026-11-06): greyed as "Does not cover <gift>", never removed. Same two
 * reasons — the current assignee is unioned in from this list, and a vanished name is a mystery.
 *
 * ⚠ **AN EMPTY `gifts` LIST MEANS EVERY GIFT and must never grey anybody.** It is the
 * permissive default that all org-scoped staff on production still carry, so reading it as
 * "covers nothing" would grey out the entire live roster on the first render. Likewise an
 * UNKNOWN `applicationProgrammeId` (an older payload) greys nobody: a narrowing we cannot
 * evaluate must fall open, because the server is the authority. Since 2026-11-06 (owner ruling,
 * TD-501) the server REFUSES a new assignment across gifts (`gift_mismatch`, `assign_reviewer`);
 * it still allows an every-gift reviewer or a case of unknown gift, the same rule as here.
 *
 * Who is offered at all is the server's `bad_assignee` rule, SERVED per row as `assignable` (#39
 * S3: `may_assign_to`); a payload without it falls back to super = any, else `reviewer`. The org fence
 * and `is_active` are the LIST endpoint's job (`AdminAssignableAdminsView` filters both), so what
 * this function must get right is the ROLE narrowing — the list is deliberately wider.
 *
 * drift-test: halatuju-web/src/lib/__tests__/officerGateDrift.test.ts
 */
export function assignOptions<T extends {
  id: number; name: string; role: string; paused?: boolean; assignable?: boolean
  gifts?: ReadonlyArray<{ id: number }>
}>(
  admins: T[],
  { isSuper, currentAssigneeId, applicationProgrammeId }: {
    isSuper: boolean
    currentAssigneeId: number | null
    applicationProgrammeId?: number | null
  },
): AssignOption[] {
  return admins
    .filter((a) => a.id === currentAssigneeId || (a.assignable ?? (isSuper || a.role === 'reviewer')))
    .map((a) => {
      const isCurrent = a.id === currentAssigneeId
      // Multi-gift: they may cover several gifts; greyed only when NONE of them is this case's.
      const gifts = a.gifts ?? []
      const coversOther = gifts.length > 0 && !!applicationProgrammeId
        && !gifts.some((g) => g.id === applicationProgrammeId)
      // Paused wins the label: it is a fact about the PERSON (they have stepped back), while
      // the gift is a fact about this one case. Somebody who is both is unavailable either way.
      const reason: AssignOption['reason'] =
        isCurrent ? null : a.paused ? 'paused' : coversOther ? 'otherGift' : null
      return {
        id: a.id,
        name: a.name,
        role: a.role,
        disabled: reason !== null,
        reason,
      }
    })
}
