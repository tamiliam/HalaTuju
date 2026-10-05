/**
 * What `/scholarship/application` shows: which of her applications, or none, or "several".
 *
 * `/scholarship/apply` and `/scholarship/application` used to answer "has she applied?" separately,
 * and they disagreed (2026-10-05, "apply gift clarity"). Since the owner's ruling on TD-337 the apply
 * page keeps NO rule of its own: it asks the server (`GET /scholarship/apply-gate/`,
 * `halatuju_api/apps/scholarship/services/apply_gate.py`) and is sent here only when the server says
 * `application_in_progress`. The pair still has to agree — whenever the server says that, this
 * screen must show THE application the gate named (`kind: 'one'`, same id): not "you haven't
 * applied", not the closed card, not "several", not another one. `studentScreenDrift.test.ts` reads
 * the server's IN_PLAY / FINISHED lists and asserts it over every list the rule can produce.
 *
 * Pure: no React, no storage.
 */
import { liveApplications } from './scholarship'

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
 *   4. Only expired rows, or nothing → 'none' ("You haven't applied yet").
 *
 * A finished application in one gift beside a submitted or live one in another (reachable since
 * TD-337) shows the submitted / live one, by rules 1 and 3.
 */
export function applicationScreen<T extends { status: string }>(apps: readonly T[]): ApplicationScreen<T> {
  const live = liveApplications(apps)
  if (live.length === 1) return { kind: 'one', app: live[0] }
  if (live.length > 1) return { kind: 'several', count: live.length }
  // An auto-closed ('expired') application is history, never something on screen.
  const rest = apps.filter((a) => a.status !== 'expired')
  if (!rest.length) return { kind: 'none' }
  const submitted = rest.filter((a) => a.status === 'submitted')
  if (submitted.length === 1) return { kind: 'one', app: submitted[0] }
  if (submitted.length > 1) return { kind: 'several', count: submitted.length }
  return { kind: 'finished', app: rest.length === 1 ? rest[0] : null }
}
