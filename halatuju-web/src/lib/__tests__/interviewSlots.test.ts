import {
  allSlotTimes, cellDateStr, daySlots, earliestDateStr, isoToSlotValue, monthCells, slotLabel12h,
  todayStr,
} from '../interviewSlots'

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

  test('monthCells pads leading blanks and lists every day', () => {
    // June 2026: the 1st is a Monday → one leading blank (Sunday).
    const cells = monthCells(2026, 5)
    expect(cells[0]).toBeNull()
    expect(cells[1]).toBe(1)
    expect(cells.filter((c) => c != null)).toHaveLength(30)
    expect(cellDateStr(2026, 5, 9)).toBe('2026-06-09')
  })
})
