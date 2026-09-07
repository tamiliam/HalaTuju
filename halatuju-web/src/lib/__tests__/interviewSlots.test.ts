import {
  allSlotTimes, cellDateStr, daySlots, earliestDateStr, isoToSlotValue, minuteLabel, monthCells,
  slotLabel12h, slotRulesFrom, todayStr, DEFAULT_SLOT_RULES, RESCHEDULE_MIN_LEAD_HOURS,
} from '../interviewSlots'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

describe('interview slot rule', () => {
  test('allSlotTimes spans 08:00–21:30 in 30-min steps (28 slots)', () => {
    const times = allSlotTimes()
    expect(times[0]).toBe('08:00')
    expect(times[times.length - 1]).toBe('21:30')
    expect(times).toContain('09:30')
    expect(times).not.toContain('22:00')
    expect(times).not.toContain('07:30')
    // no off-boundary minutes
    expect(times.every((t) => /^\d{2}:(00|30)$/.test(t))).toBe(true)
    expect(times.length).toBe(28)
  })

  test('daySlots flags slots before the 24h lead and builds backend-shaped values', () => {
    const now = new Date('2026-06-22T10:00:00')        // earliest = 2026-06-23T10:00
    expect(daySlots('2026-06-22', now).every((s) => s.tooEarly)).toBe(true)  // whole day within lead
    const next = daySlots('2026-06-23', now)
    const at = (label: string) => next.find((s) => s.label === label)!
    expect(at('08:00').value).toBe('2026-06-23T08:00')
    expect(at('09:00').tooEarly).toBe(true)    // before 10:00
    expect(at('10:00').tooEarly).toBe(false)   // == earliest, allowed
    expect(at('10:30').tooEarly).toBe(false)
  })

  test('a far-future date has no too-early slots', () => {
    const now = new Date('2026-06-22T10:00:00')
    expect(daySlots('2026-06-25', now).every((s) => !s.tooEarly)).toBe(true)
  })

  test('earliestDateStr is 24h ahead', () => {
    expect(earliestDateStr(new Date('2026-06-22T10:00:00'))).toBe('2026-06-23')
  })

  test('reschedule lead relaxes the floor to a short notice (TD-137)', () => {
    const now = new Date('2026-06-22T10:00:00')
    // default 24h floor: every same-day slot is too early
    expect(daySlots('2026-06-22', now).every((s) => s.tooEarly)).toBe(true)
    // reschedule (2h) floor: same-day slots from now+2h (12:00) onward become selectable
    const re = daySlots('2026-06-22', now, RESCHEDULE_MIN_LEAD_HOURS)
    const at = (label: string) => re.find((s) => s.label === label)!
    expect(at('11:30').tooEarly).toBe(true)    // before now+2h
    expect(at('12:00').tooEarly).toBe(false)   // == now+2h, allowed
    expect(at('14:00').tooEarly).toBe(false)
  })

  test('earliestDateStr honours a custom lead', () => {
    const now = new Date('2026-06-22T10:00:00')
    expect(earliestDateStr(now, RESCHEDULE_MIN_LEAD_HOURS)).toBe('2026-06-22')  // 12:00 same day
    expect(earliestDateStr(now)).toBe('2026-06-23')                            // 24h default
  })

  test('isoToSlotValue converts a UTC timestamp to the MYT slot key', () => {
    // 01:30 UTC === 09:30 MYT (+8)
    expect(isoToSlotValue('2026-06-22T01:30:00Z')).toBe('2026-06-22T09:30')
    expect(isoToSlotValue('')).toBe('')
    expect(isoToSlotValue('not-a-date')).toBe('')
  })

  test('todayStr is a YYYY-MM-DD string', () => {
    expect(todayStr(new Date('2026-06-22T15:00:00'))).toBe('2026-06-22')
  })

  test('slotLabel12h renders 12-hour am/pm labels', () => {
    expect(slotLabel12h('08:00')).toBe('8:00am')
    expect(slotLabel12h('09:30')).toBe('9:30am')
    expect(slotLabel12h('12:00')).toBe('12:00pm')
    expect(slotLabel12h('14:00')).toBe('2:00pm')
    expect(slotLabel12h('21:30')).toBe('9:30pm')
  })

  // ── the rules are SERVED, not mirrored (Org Config Sprint D) ──
  test('the grid follows the rules the SERVER sent, not the platform constants', () => {
    const rules = slotRulesFrom({
      slot_window_start_min: 10 * 60, slot_window_end_min: 12 * 60,
      slot_step_min: 60, slot_min_lead_hours: 48,
    })
    expect(rules).toEqual({
      windowStartMin: 600, windowEndMin: 720, stepMin: 60, minLeadHours: 48,
    })
    expect(allSlotTimes(rules)).toEqual(['10:00', '11:00', '12:00'])
    const now = new Date('2026-06-22T10:00:00')
    const day = daySlots('2026-06-25', now, rules.minLeadHours, rules)
    expect(day.map((s) => s.label)).toEqual(['10:00', '11:00', '12:00'])
    expect(day[0].value).toBe('2026-06-25T10:00')
  })

  test('a payload with the fields missing falls back to the platform grid, per field', () => {
    // An older cached payload, or a build that served only some of them: whatever IS there is
    // used, and the rest follow the platform default — never a blank grid.
    expect(slotRulesFrom(undefined)).toEqual(DEFAULT_SLOT_RULES)
    expect(slotRulesFrom(null)).toEqual(DEFAULT_SLOT_RULES)
    expect(slotRulesFrom({})).toEqual(DEFAULT_SLOT_RULES)
    expect(slotRulesFrom({ slot_step_min: 15 })).toEqual({
      ...DEFAULT_SLOT_RULES, stepMin: 15,
    })
    // A nonsense step would loop forever in allSlotTimes — refused on its own.
    expect(slotRulesFrom({ slot_step_min: 0 }).stepMin).toBe(30)
    expect(allSlotTimes(slotRulesFrom({ slot_step_min: 0 })).length).toBe(28)
  })

  test('minuteLabel joins served minutes to the HH:MM the labels speak', () => {
    expect(minuteLabel(8 * 60)).toBe('08:00')
    expect(minuteLabel(21 * 60 + 30)).toBe('21:30')
    expect(slotLabel12h(minuteLabel(600))).toBe('10:00am')
  })

  test('monthCells pads leading blanks and lists every day', () => {
    // June 2026: the 1st is a Monday → one leading blank (Sunday).
    const cells = monthCells(2026, 5)
    expect(cells[0]).toBeNull()
    expect(cells[1]).toBe(1)
    expect(cells.filter((c) => c != null)).toHaveLength(30)
    expect(cellDateStr(2026, 5, 9)).toBe('2026-06-09')
  })
})

describe('the interview copy states no fixed window, step or length', () => {
  // ⚠ THE OTHER KIND OF MIRROR. Two sentences used to READ OUT the rules — the reviewer's
  // "Available times (8:00am-9:30pm, 30-min)" caption and the student's "about 30 minutes"
  // promise. Copy is invisible to a type-check and to every test that renders a component,
  // so it survived as a claim the product no longer guarantees the day the values became the
  // organisation's. These must interpolate; a rewrite that puts a number back fails here.
  type Leaf = Record<string, unknown>
  const dig = (obj: Leaf, path: string[]): unknown =>
    path.reduce<unknown>((o, part) => (o as Leaf | undefined)?.[part as keyof Leaf], obj)

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('%s', (_lang, messages) => {
    const caption = dig(messages as unknown as Leaf,
      ['admin', 'scholarship', 'interview', 'schedule', 'availableTimes']) as string
    for (const token of ['{from}', '{to}', '{step}']) expect(caption).toContain(token)
    expect(caption).not.toMatch(/\b30\b/)

    const intro = dig(messages as unknown as Leaf,
      ['scholarship', 'application', 'interview', 'pickIntro']) as string
    expect(intro).toContain('{minutes}')
    expect(intro).not.toMatch(/\b30\b/)
  })
})
