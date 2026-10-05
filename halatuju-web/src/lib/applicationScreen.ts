/**
 * ONE RULE FOR TWO PAGES: has this student applied, and what does her application screen show?
 *
 * `/scholarship/apply` and `/scholarship/application` used to answer that separately, and they
 * disagreed. The form sent away anyone with ANY row (`applications[0]`); the application screen
 * showed only a LIVE one (shortlisted and later). A student whose only application was `submitted`
 * — the status every application starts in — was told "You haven't applied yet", pressed "Start
 * your application", and was sent straight back. Both pages now read one rule, and
 * `applicationScreen.test.ts` asserts, over every status and every pair, that the form sends her
 * away EXACTLY when the screen has something other than "you haven't applied" to show.
 *
 * The form's half (`mustLeaveApplyPage`, and the status list with its deliberate scope note) lives
 * in the leaf `./applyGate` so the apply page does not download this screen rule; it is re-exported
 * here so the pair reads as one.
 *
 * Pure: no React, no storage.
 */
import { liveApplications } from './scholarship'
import { standingApplications } from './applyGate'

export { REAPPLY_ALLOWED_STATUSES, mustLeaveApplyPage } from './applyGate'

export type ApplicationScreen<T> =
  | { kind: 'one'; app: T }
  | { kind: 'finished'; app: T | null }
  | { kind: 'several'; count: number }
  | { kind: 'none' }

/**
 * What `/scholarship/application` shows.
 *
 *   1. Exactly one LIVE application → that one ('one'), whatever else sits beside it.
 *   2. More than one live → 'several', with the count. ⚠ The M1 decision ("the application screen
 *      shows nothing rather than one of several", docs/decisions.md) is unchanged: position is not
 *      an answer to "which application is this".
 *   3. None live, among the standing (non-expired) ones:
 *        • exactly one `submitted` → that one ('one' — the neutral "received" card);
 *        • two or more `submitted` → 'several', with how many are submitted;
 *        • no `submitted` (only rejected / withdrawn / closed …) → 'finished': a neutral "this
 *          application is closed" card. It carries the app when there is exactly one, so the page
 *          can name its gift; with several it names none.
 *   4. Only expired rows, or nothing → 'none' ("You haven't applied yet") — and the form lets her in.
 */
export function applicationScreen<T extends { status: string }>(apps: readonly T[]): ApplicationScreen<T> {
  const live = liveApplications(apps)
  if (live.length === 1) return { kind: 'one', app: live[0] }
  if (live.length > 1) return { kind: 'several', count: live.length }
  const rest = standingApplications(apps)
  if (!rest.length) return { kind: 'none' }
  const submitted = rest.filter((a) => a.status === 'submitted')
  if (submitted.length === 1) return { kind: 'one', app: submitted[0] }
  if (submitted.length > 1) return { kind: 'several', count: submitted.length }
  return { kind: 'finished', app: rest.length === 1 ? rest[0] : null }
}
