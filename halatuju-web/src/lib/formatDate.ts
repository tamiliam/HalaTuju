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
