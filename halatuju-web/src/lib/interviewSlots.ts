/** The shape of the interview slot rules the reviewer's picker draws from.
 *
 *  Everyone in this programme is in one timezone (Asia/Kuala_Lumpur). Times are
 *  proposed as a naive local string `YYYY-MM-DDThh:mm` which the backend reads as
 *  MYT (see interviewTime.ts) — so the chip values are built in that exact shape.
 *
 *  ⚠ THE RULES ARE SERVED, NOT MIRRORED (Org Config Sprint D). The window, the step and the
 *  minimum notice are the ORGANISATION's — they arrive on the interview payload
 *  (`slotRulesFrom`), resolved by `apps/scholarship/scheduling.py` for that application's
 *  tenant. The constants below are the PLATFORM DEFAULT ONLY: they exist so a payload that
 *  predates the fields still draws a sane grid, and so the pure helpers can be called without
 *  a payload in hand. Do not read them where a payload is available — that re-creates the
 *  lock-step copy this sprint deleted, and a copy cannot be per-organisation. */
export const SLOT_WINDOW_START_MIN = 8 * 60        // 08:00
export const SLOT_WINDOW_END_MIN = 21 * 60 + 30    // 21:30 (latest start)
export const SLOT_STEP_MIN = 30
// Minimum scheduling notice: the earliest proposable slot is this far ahead, so the student
// has time to see the email, pick, and prepare. (owner: 24h)
export const MIN_LEAD_HOURS = 24

export interface SlotRules {
  windowStartMin: number
  windowEndMin: number
  stepMin: number
  minLeadHours: number
}

/** The platform default grid — what an organisation that has tuned nothing gets. */
export const DEFAULT_SLOT_RULES: SlotRules = {
  windowStartMin: SLOT_WINDOW_START_MIN,
  windowEndMin: SLOT_WINDOW_END_MIN,
  stepMin: SLOT_STEP_MIN,
  minLeadHours: MIN_LEAD_HOURS,
}

/** Read the served rules off an interview payload, falling back per FIELD.
 *
 *  Per field, not per object: a payload from a build that served only some of them still
 *  contributes what it has, and a nonsense value (0 step → an endless loop below) is
 *  refused on its own rather than discarding the three good numbers beside it. */
export function slotRulesFrom(served?: {
  slot_window_start_min?: number
  slot_window_end_min?: number
  slot_step_min?: number
  slot_min_lead_hours?: number
} | null): SlotRules {
  const num = (v: number | undefined, fallback: number, min = 1) =>
    (typeof v === 'number' && Number.isFinite(v) && v >= min ? v : fallback)
  return {
    windowStartMin: num(served?.slot_window_start_min, SLOT_WINDOW_START_MIN, 0),
    windowEndMin: num(served?.slot_window_end_min, SLOT_WINDOW_END_MIN, 0),
    stepMin: num(served?.slot_step_min, SLOT_STEP_MIN),
    minLeadHours: num(served?.slot_min_lead_hours, MIN_LEAD_HOURS),
  }
}
// On a reviewer RESCHEDULE the candidate has already waited through the original notice, so the
// 24h floor is relaxed to a short lead — the reviewer can offer nearer slots. (TD-137, owner 2026-06-21.)
// The backend (`propose_slots`) already accepts any future slot, so this is a UI-only relaxation.
export const RESCHEDULE_MIN_LEAD_HOURS = 2

const pad = (n: number) => String(n).padStart(2, '0')

/** Every allowed "HH:MM" start label for a day, e.g. ["08:00","08:30",…,"21:30"].
 *  Pass the organisation's served rules; omitting them uses the platform default grid. */
export function allSlotTimes(rules: SlotRules = DEFAULT_SLOT_RULES): string[] {
  const out: string[] = []
  for (let m = rules.windowStartMin; m <= rules.windowEndMin; m += rules.stepMin) {
    out.push(`${pad(Math.floor(m / 60))}:${pad(m % 60)}`)
  }
  return out
}

/** A `YYYY-MM-DD` date in the reviewer's local clock (assumed MYT). */
export function todayStr(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/** The earliest selectable moment (now + the lead window). `leadHours` defaults to the 24h
 *  first-propose floor; pass RESCHEDULE_MIN_LEAD_HOURS on a reschedule. */
export function earliestStart(now: Date = new Date(), leadHours: number = MIN_LEAD_HOURS): Date {
  return new Date(now.getTime() + leadHours * 3600_000)
}

/** The earliest selectable DATE (`YYYY-MM-DD`) — days before this are fully disabled. */
export function earliestDateStr(now: Date = new Date(), leadHours: number = MIN_LEAD_HOURS): string {
  return todayStr(earliestStart(now, leadHours))
}

export interface DaySlot {
  value: string      // "YYYY-MM-DDThh:mm" — sent to the backend verbatim
  label: string      // "HH:MM"
  tooEarly: boolean  // before the minimum-lead cutoff → not selectable
}

/** The slots for a given date. Times before the minimum-lead cutoff are flagged so the
 *  UI can drop them. `value` is the naive-MYT string the backend expects. */
export function daySlots(dateStr: string, now: Date = new Date(), leadHours: number = MIN_LEAD_HOURS,
                         rules: SlotRules = DEFAULT_SLOT_RULES): DaySlot[] {
  const earliest = earliestStart(now, leadHours).getTime()
  return allSlotTimes(rules).map((label) => {
    const value = `${dateStr}T${label}`
    return { value, label, tooEarly: new Date(value).getTime() < earliest }
  })
}

/** Minutes past midnight → the "HH:MM" the rest of this module speaks (600 → "10:00"). The
 *  served window bounds arrive as minutes and every label helper here takes "HH:MM", so this
 *  is the one join between the two. */
export function minuteLabel(mins: number): string {
  const m = Math.max(0, Math.min(1439, Math.round(mins)))
  return `${pad(Math.floor(m / 60))}:${pad(m % 60)}`
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
