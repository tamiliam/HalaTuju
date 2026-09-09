/**
 * What a staff row's STATUS pill says — the one home for a rule two tables kept getting wrong.
 *
 * ⚠ **REVOKED BEATS PAUSED, AND ONLY ONE OF THE TWO TABLES KNEW.** A revoked account cannot be
 * brought back by un-pausing, so "Paused" over a closed account names the smaller of two facts.
 * `StaffTable` learned this on 2026-09-08; the Reviewers table did not — it read `paused` alone and
 * would have printed "Active" beside somebody with no access the moment Revoke arrived on it
 * (2026-09-09). The same pair of screens had already disagreed about Paused itself until
 * 2026-08-03. Two copies of this rule is how that keeps happening, so there is one.
 */
export interface StaffStanding {
  is_active?: boolean
  paused?: boolean
}

export type StaffStatusKey = 'revoked' | 'paused' | 'active'

/** The status key, in priority order. `is_active` undefined means active — a payload predating
 *  the field, which is what both screens assumed before it was served. */
export function staffStatusKey(a: StaffStanding): StaffStatusKey {
  if (a.is_active === false) return 'revoked'
  if (a.paused) return 'paused'
  return 'active'
}

/** The pill's colours, keyed the same way. Critical for revoked, caution for paused: losing access
 *  is not the same event as stepping back, and the two must not share a colour. */
export const STAFF_STATUS_TONE: Record<StaffStatusKey, string> = {
  revoked: 'bg-critical-100 text-critical-600',
  paused: 'bg-caution-100 text-caution-700',
  active: 'bg-positive-100 text-positive-700',
}
