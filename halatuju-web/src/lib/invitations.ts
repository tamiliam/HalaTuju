import type { AdminItem } from './admin-api'

/**
 * Reading an invitation and a person's standing off the staff payload.
 *
 * ⚠ The SERVER decides an invitation's status word (`invitation.status`) — this file never
 * re-derives it, the same split `_reviewer_dict` / `reviewerTable.ts` uses. What lives here is the
 * PERSON's standing, which is a display question about rows the server already told us everything
 * about, and the ordering the two tables read in.
 */

/** What an invitation is doing. Mirrors `invitations.status_of` — the server is the authority. */
export type InvitationStatus = 'invited' | 'expired' | 'no_reply' | 'accepted' | 'revoked'

/** What a PERSON is doing. Derived here; see `standingOf` for the precedence and why. */
export type Standing = 'revoked' | 'paused' | 'dormant' | 'active' | 'notRecorded'

/** Days without opening the console before somebody reads as dormant. Descriptive, never a gate. */
export const DORMANT_DAYS = 90

/**
 * ⚠ PRECEDENCE IS ORDERED, AND EACH STEP EARNS ITS PLACE.
 *
 * - **revoked** first: the account is gone, and nothing below it can be acted on.
 * - **paused** next: they are here and chose to step back — un-pause is the control, not restore.
 * - **dormant** only then, because dormancy is an observation about somebody whose account is
 *   perfectly fine. It must never look like paused or revoked; this repo has already been bitten
 *   once by two flags that nearly meant the same thing.
 * - **notRecorded** is NOT "never signed in". Everyone predating the sign-in signal has an empty
 *   column, so the honest word is that we do not know.
 */
export function standingOf(a: AdminItem, now: Date = new Date()): Standing {
  if (!a.is_active) return 'revoked'
  if (a.paused) return 'paused'
  if (!a.last_seen_at) return 'notRecorded'
  const days = (now.getTime() - new Date(a.last_seen_at).getTime()) / 86_400_000
  return days > DORMANT_DAYS ? 'dormant' : 'active'
}

/** Somebody whose invitation is still unanswered — the top table's membership rule. */
export function isOutstanding(a: AdminItem): boolean {
  const s = a.invitation?.status
  return s === 'invited' || s === 'expired' || s === 'no_reply'
}

/** Outstanding invitations, the ones needing action first. */
const OUTSTANDING_RANK: Record<string, number> = { expired: 0, no_reply: 1, invited: 2 }

export function outstanding(rows: AdminItem[]): AdminItem[] {
  return rows.filter(isOutstanding).sort((x, y) => {
    const rx = OUTSTANDING_RANK[x.invitation?.status ?? ''] ?? 9
    const ry = OUTSTANDING_RANK[y.invitation?.status ?? ''] ?? 9
    if (rx !== ry) return rx - ry
    // Then oldest first: the one waiting longest is the one to chase.
    return (x.invitation?.sent_at ?? '').localeCompare(y.invitation?.sent_at ?? '')
  })
}

/**
 * How to describe the last send. Three outcomes, not two.
 *
 * ⚠ `last_send_ok === null` is NOT a failure — it is every backfilled row, where whether a historic
 * email arrived is unknowable. Rendering it as a failure would accuse us of bouncing mail we have
 * no evidence about.
 */
export type SendState = 'sent' | 'failed' | 'notRecorded'

export function sendState(a: AdminItem): SendState {
  const inv = a.invitation
  if (!inv || !inv.sent_at) return 'notRecorded'
  if (inv.last_send_ok === null || inv.last_send_ok === undefined) return 'notRecorded'
  return inv.last_send_ok ? 'sent' : 'failed'
}
