/** The single source of truth for interview slot rules (reviewer propose + student
 *  booking both read this).
 *
 *  Everyone in this programme is in one timezone (Asia/Kuala_Lumpur). Times are
 *  proposed as a naive local string `YYYY-MM-DDThh:mm` which the backend reads as
 *  MYT (see interviewTime.ts) — so the chip values are built in that exact shape.
 *
 *  Window: 08:00–21:30 (last start), 30-minute steps → 28 slots/day. Mirrored
 *  server-side in `apps/scholarship/scheduling.py` (_slot_in_window); keep the two
 *  in lock-step if either changes. */
export const SLOT_WINDOW_START_MIN = 8 * 60        // 08:00
export const SLOT_WINDOW_END_MIN = 21 * 60 + 30    // 21:30 (latest start)
export const SLOT_STEP_MIN = 30
// Minimum scheduling notice: the earliest proposable slot is this far ahead, so the student
// has time to see the email, pick, and prepare. Mirrored in scheduling.py. (owner: 24h)
export const MIN_LEAD_HOURS = 24

const pad = (n: number) => String(n).padStart(2, '0')

/** Every allowed "HH:MM" start label for a day, e.g. ["08:00","08:30",…,"21:30"]. */
export function allSlotTimes(): string[] {
  const out: string[] = []
  for (let m = SLOT_WINDOW_START_MIN; m <= SLOT_WINDOW_END_MIN; m += SLOT_STEP_MIN) {
    out.push(`${pad(Math.floor(m / 60))}:${pad(m % 60)}`)
  }
  return out
}

/** A `YYYY-MM-DD` date in the reviewer's local clock (assumed MYT). */
export function todayStr(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** The earliest selectable moment (now + the minimum-lead window). */
export function earliestStart(now: Date = new Date()): Date {
  return new Date(now.getTime() + MIN_LEAD_HOURS * 3600_000)
}

/** The earliest selectable DATE (`YYYY-MM-DD`) — days before this are fully disabled. */
export function earliestDateStr(now: Date = new Date()): string {
  return todayStr(earliestStart(now))
}

export interface DaySlot {
  value: string      // "YYYY-MM-DDThh:mm" — sent to the backend verbatim
  label: string      // "HH:MM"
  tooEarly: boolean  // before the minimum-lead cutoff → not selectable
}

/** The slots for a given date. Times before the minimum-lead cutoff are flagged so the
 *  UI can drop them. `value` is the naive-MYT string the backend expects. */
export function daySlots(dateStr: string, now: Date = new Date()): DaySlot[] {
  const earliest = earliestStart(now).getTime()
  return allSlotTimes().map((label) => {
    const value = `${dateStr}T${label}`
    return { value, label, tooEarly: new Date(value).getTime() < earliest }
  })
}

/** "09:30" → "9:30am", "14:00" → "2:00pm", "21:30" → "9:30pm" (Calendly-style). */
export function slotLabel12h(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number)
  const period = h < 12 ? 'am' : 'pm'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return `${h12}:${pad(m)}${period}`
}

/** Calendar grid for a month (week starts Sunday). Returns day numbers padded with
 *  leading `null`s for the blanks before the 1st. `month` is 0-11. */
export function monthCells(year: number, month: number): (number | null)[] {
  const lead = new Date(year, month, 1).getDay()       // 0 = Sunday
  const days = new Date(year, month + 1, 0).getDate()
  const cells: (number | null)[] = Array(lead).fill(null)
  for (let d = 1; d <= days; d++) cells.push(d)
  return cells
}

/** `YYYY-MM-DD` for a calendar cell. */
export function cellDateStr(year: number, month: number, day: number): string {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

/** Map our app locale to an Intl locale for month/weekday/date chrome. */
export function intlLocale(locale: string): string {
  return { en: 'en-GB', ms: 'ms-MY', ta: 'ta-MY' }[locale] || 'en-GB'
}

/** Convert a stored ISO timestamp to the same naive-MYT slot key (`YYYY-MM-DDThh:mm`),
 *  so an already-proposed/booked slot can be matched against a chip's value. */
export function isoToSlotValue(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kuala_Lumpur', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(d)
  const get = (type: string) => parts.find((p) => p.type === type)?.value || ''
  const hour = get('hour') === '24' ? '00' : get('hour')
  return `${get('year')}-${get('month')}-${get('day')}T${hour}:${get('minute')}`
}
