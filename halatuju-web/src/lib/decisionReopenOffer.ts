/**
 * Which control the Decision card offers a super beside a recorded decision (TD-349, 2026-10-06).
 *
 * The api REFUSES to reopen a decline whose email is still embargoed — `reopen_decision` raises
 * `decline_pending` when `decline_due_at` or `pending_rejection_category` is set. The way to
 * re-decide such a case is to cancel the pending decline (the cockpit header's existing control):
 * it restores the stage, the award and the sponsorship, leaves no reopen flag, and the student's
 * view does not move. So while a decline is pending the card offers that cancel in Reopen's place,
 * never a Reopen that would answer 400. The pending test mirrors the api's: either marker set.
 *
 * drift-test: halatuju-web/src/lib/__tests__/decisionReopenOffer.test.ts
 */
export type DecisionReopenOffer = 'reopen' | 'cancelPendingDecline' | null

export function isDeclinePending(
  app: { decline_due_at: string | null; pending_rejection_category: string },
): boolean {
  return !!(app.decline_due_at || app.pending_rejection_category)
}

export function decisionReopenOffer(
  opts: { decisionLocked: boolean; isSuper: boolean; declinePending: boolean },
): DecisionReopenOffer {
  if (!opts.decisionLocked || !opts.isSuper) return null
  return opts.declinePending ? 'cancelPendingDecline' : 'reopen'
}
