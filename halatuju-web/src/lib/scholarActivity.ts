/**
 * How one entry on a scholar's activity timeline reads (student maintenance Sprint 2; letters S6b).
 *
 * MOVED VERBATIM from `lib/scholars.ts` in S6b (TD-427), plus the three letter events: only
 * `components/admin/ScholarActivity.tsx` uses these, and the Scholars LIST page — which imports
 * `lib/scholars` for its chip tones and sits at the bundle median — was carrying them for nothing.
 */
import type { ScholarActivity } from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'

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
    case 'result_reviewed':
      return t(`admin.scholars.event.result_${str(m.new) === 'queried' ? 'queried' : 'accepted'}`,
        { semester: str(m.semester) || '—' })
    case 'results_overdue':
      return t('admin.scholars.event.results_overdue', { date: m.due_on ? formatDate(str(m.due_on)) : '—' })
    case 'closed':
      return t('admin.scholars.event.closed', {
        reason: m.reason ? t(`admin.closure.reason.${str(m.reason)}`) : '—' })
    // S6b: letters (the subject is the letter's own, as issued).
    case 'letter_issued':
    case 'letter_withdrawn':
    case 'letter_acknowledged':
      return t(`admin.scholars.event.${a.event}`, { subject: str(m.subject) || '—' })
    default:
      return t('admin.scholars.event.other')
  }
}
