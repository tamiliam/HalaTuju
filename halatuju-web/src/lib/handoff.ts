/**
 * Owner ruling 28 Nov 2026: may Recommend hand the case to QC? THE SERVER'S ANSWER, read here.
 *
 * The rule lives in ONE place, `halatuju_api/apps/scholarship/services/handoff.py`, and verify-accept
 * enforces it: a SUBMITTED case at interviewing / interviewed re-checks only the documents, the consent
 * and the guardian documents (what the Action Centre can still fix); every other case re-checks every
 * completeness part. The record-verdict payload serves the answer as `handoff: {ready, missing}`. This
 * file keeps no copy of the rule — it only reads that field.
 *
 * ⚠ `completeness.complete` is NOT the hand-off. It stays the full answer for every other screen; reading
 * it here is what stranded case 513 (its quiz was wiped by sign-in bug #81 and can never come back).
 * The one exception is a payload with no `handoff` at all (an api older than this change, during a
 * deploy): that falls back to the old served answer, which is what the gate was before the ruling.
 */
import type { AdminScholarshipDetail } from '@/lib/admin-api'

type HandoffSource = Partial<Pick<AdminScholarshipDetail, 'completeness' | 'handoff'>> | null | undefined

/** May the case be handed to QC — the server's `handoff.ready`. */
export function handoffReady(d: HandoffSource): boolean {
  if (d?.handoff) return !!d.handoff.ready
  return !!d?.completeness?.complete
}

/** The completeness part keys (`quiz_done`, `consent_done`, …) the hand-off still counts as not done. */
export function handoffMissing(d: HandoffSource): string[] {
  if (d?.handoff) return [...(d.handoff.missing ?? [])]
  const c = d?.completeness
  if (!c) return []
  return Object.entries(c).filter(([k, v]) => k !== 'complete' && v === false).map(([k]) => k)
}
