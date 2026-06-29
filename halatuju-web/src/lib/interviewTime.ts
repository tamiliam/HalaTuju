/** Shared helpers for rendering interview times in Malaysia time (MYT).
 *
 * Everyone in this programme is in a single timezone (Asia/Kuala_Lumpur), so we
 * store UTC and always display MYT. The reviewer proposes times with a native
 * <input type="datetime-local"> whose value is a naive local string — the backend
 * reads that as MYT, so we send it as-is (no client-side tz conversion needed).
 */
const MYT = 'Asia/Kuala_Lumpur'

/** Format an ISO timestamp as e.g. "Mon, 23 Jun 2026, 8:00 PM (MYT)". */
export function formatMyt(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const s = new Intl.DateTimeFormat('en-GB', {
    timeZone: MYT, weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: true,
  }).format(d)
  return `${s} (MYT)`
}

/** True if `iso` is within `hours` of now (i.e. inside the reschedule/cancel cutoff). */
export function withinCutoff(iso: string | null | undefined, hours: number): boolean {
  if (!iso) return false
  const start = new Date(iso).getTime()
  if (isNaN(start)) return false
  return start - Date.now() < hours * 3600 * 1000
}

/** Grace window (hours) after a booked interview's start before the booked card
 *  retires its Join/reschedule/cancel actions. Errs long on purpose: it keeps the
 *  Join link live through a late start or an overrun. */
export const INTERVIEW_GRACE_HOURS = 6

/** True once we're more than `graceHours` past the interview start — i.e. the interview
 *  is over and the booked card should stop looking upcoming (show a "completed" note
 *  instead of Join/reschedule/cancel). False for a missing/invalid date. */
export function interviewGracePassed(iso: string | null | undefined, graceHours: number): boolean {
  if (!iso) return false
  const start = new Date(iso).getTime()
  if (isNaN(start)) return false
  return Date.now() > start + graceHours * 3600 * 1000
}
