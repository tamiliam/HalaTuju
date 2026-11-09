/**
 * Canonical date formatting for HalaTuju — British DD/MM/YYYY throughout.
 *
 * Formats by hand (day/month/year, zero-padded) rather than `toLocaleDateString`
 * so the output is deterministic: a bare `toLocaleDateString()` inherits the
 * runtime's locale (US on the server → American M/D/YYYY), and a locale-tagged
 * call can still differ between the SSR (Node ICU) and browser passes, risking a
 * hydration mismatch. Manual formatting sidesteps both. Uses the local timezone,
 * matching the calls this replaces.
 */
/** `YYYY-MM-DD` with nothing after it — a calendar day, not an instant. */
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/

export function formatDate(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  // ⚠ A DATE-ONLY STRING IS READ BY HAND, as the local calendar day. `new Date('2026-10-01')` is UTC
  // midnight, which every timezone west of Greenwich renders as 30 September (S5b review L7).
  const day = typeof value === 'string' ? value.match(DATE_ONLY) : null
  if (day) return `${day[3]}/${day[2]}/${day[1]}`
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  return `${dd}/${mm}/${yyyy}`
}

/**
 * The same date with a 24-hour clock — `01/08/2026 19:08`.
 *
 * For lists where several rows can share a day and the reader has to tell them APART. The
 * engineer's analyses are the motivating case: two drafts staged seven minutes apart rendered an
 * identical `01/08/2026` beside an identical badge, identical hours and identical cited files, so
 * nothing on screen distinguished the one to approve from the one to discard.
 *
 * ⚠ Renders in the VIEWER's timezone, like `formatDate`. Safe wherever the value arrives from a
 * client-side fetch (there is no server pass to disagree with), which is every current caller —
 * but a time is far likelier to expose a hydration mismatch than a date is, so do not reach for
 * this in a server-rendered component without pinning the zone first.
 */
export function formatDateTime(value: string | number | Date | null | undefined): string {
  const day = formatDate(value)
  if (!day) return ''
  const d = value instanceof Date ? value : new Date(value as string | number)
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${day} ${hh}:${min}`
}

/**
 * Sprint P1 (owner, 2026-11-09, P1-e): WHEN a log row happened, relative to now — "2 hours ago",
 * "Yesterday", "9 days ago", and from {@link RELATIVE_AS_DATE_DAYS} days back the date itself ("34 days
 * ago" asks the reader to do the sum). The caller puts the exact `formatDateTime` in a `title` and in
 * screen-reader text.
 *
 * ⚠ ANSWERS AN i18n KEY AND ITS VARIABLES, NEVER WORDS (`admin.relativeTime.<key>`), the shape of T3's
 * `seenAgo` (`lib/lastSeen.ts`, not on main yet) so the two can become one helper.
 * ⚠ THE DAYS ARE CALENDAR DAYS IN MALAYSIA (Asia/Kuala_Lumpur, UTC+8 all year, no daylight saving):
 * "Yesterday" is the previous day there, so 23:50 to 00:10 is "20 minutes ago", and 22:00 to 08:00 the
 * next morning is "Yesterday", never "10 hours ago". T3's `seenAgo` counts 24-hour gaps instead.
 * ⚠ A time a little in the future (a clock ahead of ours) reads "just now", never "-1 minutes ago".
 */
export type RelativeTime =
  | { key: 'now' | 'minute' | 'hour' | 'yesterday' }
  | { key: 'minutes' | 'hours' | 'days'; n: number }
  | { key: 'on'; date: Date }

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
/** Malaysia is UTC+8 all year. */
const MALAYSIA_OFFSET = 8 * HOUR
/** From this many calendar days back the date is shown instead. */
export const RELATIVE_AS_DATE_DAYS = 30

const malaysianDay = (ms: number) => Math.floor((ms + MALAYSIA_OFFSET) / DAY)

export function relativeTime(value: string | Date, now: number = Date.now()): RelativeTime | null {
  const at = value instanceof Date ? value : new Date(value)
  const ms = at.getTime()
  if (Number.isNaN(ms)) return null
  const gap = Math.max(0, now - ms)
  if (gap < MINUTE) return { key: 'now' }
  if (gap < HOUR) {
    const n = Math.floor(gap / MINUTE)
    return n === 1 ? { key: 'minute' } : { key: 'minutes', n }
  }
  const days = Math.max(0, malaysianDay(now) - malaysianDay(ms))
  if (days === 0) {
    const n = Math.floor(gap / HOUR)
    return n === 1 ? { key: 'hour' } : { key: 'hours', n }
  }
  if (days === 1) return { key: 'yesterday' }
  if (days < RELATIVE_AS_DATE_DAYS) return { key: 'days', n: days }
  return { key: 'on', date: at }
}
