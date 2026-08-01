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
export function formatDate(value: string | number | Date | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
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
