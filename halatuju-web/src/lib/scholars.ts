/**
 * The Scholars screens' small shared pieces (student maintenance Sprint 2): the tone of a sub-state
 * and of a standing chip. (How an activity entry reads is `lib/scholarActivity.ts` — moved out in
 * S6b so the Scholars LIST, which sits at the bundle median, stops carrying timeline wording; TD-427.)
 *
 * Tones are the console's STATE tones (positive / caution / critical / info / ground), the same
 * four the cockpit's sub-state chip uses (`PostAwardPanels.tsx`), never a category colour.
 */
import type { MaintenanceSubstate, ScholarStanding } from '@/lib/admin-api'

export const SUBSTATE_TONE: Record<MaintenanceSubstate, string> = {
  on_track: 'bg-positive-100 text-positive-700',
  probation: 'bg-caution-100 text-caution-700',
  on_hold: 'bg-critical-100 text-critical-700',
  ready_to_close: 'bg-info-100 text-info-700',
}

/** S4a: the standing chip (`standing.py`) — performing positive, underperforming caution, failing
 *  critical; awaiting review / no result yet are not judgements, so calm ground tones. */
export const STANDING_TONE: Record<ScholarStanding, string> = {
  performing: 'bg-positive-100 text-positive-700',
  underperforming: 'bg-caution-100 text-caution-700',
  failing: 'bg-critical-100 text-critical-700',
  not_submitted: 'bg-critical-100 text-critical-700',
  awaiting_review: 'bg-ground-100 text-ground-700',
  no_result_yet: 'bg-ground-100 text-ground-500',
}

/** S4a: a result's review chip on the officer's Results tab. */
export const REVIEW_TONE: Record<string, string> = {
  pending: 'bg-ground-100 text-ground-700',
  accepted: 'bg-positive-100 text-positive-700',
  queried: 'bg-caution-100 text-caution-700',
}
