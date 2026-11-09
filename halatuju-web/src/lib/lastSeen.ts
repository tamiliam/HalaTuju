/**
 * Sprint T3 (M1, owner 2026-11-09): a person page's **Last seen**, worded relative to now ("2 days
 * ago"); the page puts the exact date and time in the `title`. A month or more back it is the date
 * itself — "34 days ago" asks the reader to do the sum.
 *
 * ⚠ Answers an i18n KEY and its variables, never words: the page owns the wording, in three languages.
 * ⚠ A time in the future (a clock a little ahead of ours) reads "just now", never "-1 minutes ago".
 * ⚠ DAYS ARE CALENDAR DAYS IN MALAYSIA (T3 review fix 4), not 24-hour gaps: "Yesterday" is the previous
 * calendar day in Asia/Kuala_Lumpur, and "2 days ago" is two midnights back there. So 23:00 last night
 * read at 08:00 is "Yesterday" (not "9 hours ago"), and 21:00 two evenings ago read at 20:00 is "2 days
 * ago" (not "Yesterday"). Under an hour it is still minutes, midnight or not. Malaysia keeps UTC+8 all
 * year (no daylight saving), so a fixed offset is exact and needs no time-zone data.
 */
export type SeenAgo =
  | { key: 'now' | 'minute' | 'hour' | 'yesterday' }
  | { key: 'minutes' | 'hours' | 'days'; n: number }
  | { key: 'on'; date: Date }

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
/** From this many calendar days back the date is shown instead. */
export const SEEN_AS_DATE_DAYS = 30
/** Asia/Kuala_Lumpur: UTC+8, no daylight saving. */
const KL_OFFSET = 8 * HOUR

/** The calendar day in Kuala Lumpur, as a day number. */
const klDay = (ms: number) => Math.floor((ms + KL_OFFSET) / DAY)

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
  const n = Math.max(0, klDay(now) - klDay(ms))
  if (n === 0) {
    const h = Math.floor(gap / HOUR)
    return h === 1 ? { key: 'hour' } : { key: 'hours', n: h }
  }
  if (n === 1) return { key: 'yesterday' }
  if (n < SEEN_AS_DATE_DAYS) return { key: 'days', n }
  return { key: 'on', date: at }
}
