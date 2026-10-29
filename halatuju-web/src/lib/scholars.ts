/**
 * The Scholars screens' small shared pieces (student maintenance Sprint 2): the tone of a sub-state
 * and of a standing chip, and how one activity entry reads on the timeline.
 *
 * Tones are the console's STATE tones (positive / caution / critical / info / ground), the same
 * four the cockpit's sub-state chip uses (`PostAwardPanels.tsx`), never a category colour.
 */
import type { MaintenanceSubstate, ScholarActivity, ScholarStanding } from '@/lib/admin-api'

export const SUBSTATE_TONE: Record<MaintenanceSubstate, string> = {
  on_track: 'bg-positive-100 text-positive-700',
  probation: 'bg-caution-100 text-caution-700',
  on_hold: 'bg-critical-100 text-critical-700',
  ready_to_close: 'bg-info-100 text-info-700',
}

/** Only "has a result" / "no result yet" until Sprint 4 derives the real standing — neither is a
 *  judgement, so both are calm ground tones. */
export const STANDING_TONE: Record<ScholarStanding, string> = {
  has_result: 'bg-ground-100 text-ground-700',
  no_result_yet: 'bg-ground-100 text-ground-500',
}

/** The dot beside an entry: money green, a sub-state change amber, an officer's own entry blue,
 *  everything else the system grey. */
export function activityDot(a: ScholarActivity): string {
  if (a.kind !== 'system') return 'bg-info-500'
  if (a.event === 'payment_released') return 'bg-positive-500'
  if (a.event === 'substate_changed') return 'bg-caution-500'
  return 'bg-ground-400'
}

/** The words of one entry. A manual entry is its own body; a system entry is a translated sentence
 *  built from its event code and the few meta fields that event carries (never raw JSON). */
export function activityText(
  a: ScholarActivity, t: (k: string, p?: Record<string, string>) => string,
): string {
  if (a.kind !== 'system') return a.body
  const m = a.meta as Record<string, unknown>
  const str = (v: unknown) => (v === null || v === undefined ? '' : String(v))
  switch (a.event) {
    case 'substate_changed':
      return t('admin.scholars.event.substate_changed', {
        from: t(`admin.maintenance.substate.${str(m.old) || 'on_track'}`),
        to: t(`admin.maintenance.substate.${str(m.new) || 'on_track'}`),
      })
    case 'payment_released':
      return t('admin.scholars.event.payment_released', {
        amount: str(m.amount), ref: str(m.run || m.reference) })
    case 'result_submitted':
      return t('admin.scholars.event.result_submitted', { semester: str(m.semester) || '—' })
    case 'closed':
      return t('admin.scholars.event.closed', {
        reason: m.reason ? t(`admin.closure.reason.${str(m.reason)}`) : '—' })
    default:
      return t('admin.scholars.event.other')
  }
}
