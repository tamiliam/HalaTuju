/**
 * Sprint T3 (M1, owner 2026-11-09): a person page's **Last seen**, worded relative to now ("2 days
 * ago"); the page puts the exact date and time in the `title`. A month or more back it is the date
 * itself — "34 days ago" asks the reader to do the sum.
 *
 * ⚠ Answers an i18n KEY and its variables, never words: the page owns the wording, in three languages.
 * ⚠ A time in the future (a clock a little ahead of ours) reads "just now", never "-1 minutes ago".
 */
export type SeenAgo =
  | { key: 'now' | 'minute' | 'hour' | 'yesterday' }
  | { key: 'minutes' | 'hours' | 'days'; n: number }
  | { key: 'on'; date: Date }

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
/** From this many days back the date is shown instead. */
export const SEEN_AS_DATE_DAYS = 30

export function seenAgo(value: string, now: number = Date.now()): SeenAgo | null {
  const at = new Date(value)
  const ms = at.getTime()
  if (Number.isNaN(ms)) return null
  const gap = Math.max(0, now - ms)
  if (gap < MINUTE) return { key: 'now' }
  if (gap < HOUR) {
    const n = Math.floor(gap / MINUTE)
    return n === 1 ? { key: 'minute' } : { key: 'minutes', n }
  }
  if (gap < DAY) {
    const n = Math.floor(gap / HOUR)
    return n === 1 ? { key: 'hour' } : { key: 'hours', n }
  }
  const n = Math.floor(gap / DAY)
  if (n === 1) return { key: 'yesterday' }
  if (n < SEEN_AS_DATE_DAYS) return { key: 'days', n }
  return { key: 'on', date: at }
}
