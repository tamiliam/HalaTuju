import { formatDate, relativeTime, RELATIVE_AS_DATE_DAYS } from '@/lib/formatDate'

describe('formatDate — British DD/MM/YYYY throughout the site', () => {
  it('formats a day-first date, zero-padded (this is the American-format bug fix)', () => {
    // 5 July 2026 — the case in the reported screenshot ("7/5/2026" was M/D/YYYY).
    expect(formatDate('2026-07-05T09:00:00Z')).toBe('05/07/2026')
  })

  it('pads single-digit days and months', () => {
    expect(formatDate('2026-03-09T12:00:00Z')).toBe('09/03/2026')
  })

  it('accepts a Date instance', () => {
    expect(formatDate(new Date(2026, 0, 1))).toBe('01/01/2026')
  })

  it('a date-only string is the LOCAL calendar day, never a day early west of Greenwich (S5b review L7)', () => {
    const before = process.env.TZ
    process.env.TZ = 'America/New_York'
    try {
      // The trap this pins: the engine reads '2026-10-01' as UTC midnight — 30 September in New York.
      const naive = new Date('2026-10-01')
      if (naive.getTimezoneOffset() > 0) expect(naive.getDate()).toBe(30)
      expect(formatDate('2026-10-01')).toBe('01/10/2026')
      expect(formatDate('2027-01-01')).toBe('01/01/2027')
    } finally {
      process.env.TZ = before
    }
  })

  it('returns empty string for null / undefined / empty / invalid input', () => {
    expect(formatDate(null)).toBe('')
    expect(formatDate(undefined)).toBe('')
    expect(formatDate('')).toBe('')
    expect(formatDate('not-a-date')).toBe('')
  })
})

describe('relativeTime — when a log row happened (sprint P1, P1-e)', () => {
  // 9 November 2026, 10:00 in Kuala Lumpur (02:00 UTC).
  const NOW = Date.parse('2026-11-09T02:00:00Z')
  const at = (iso: string) => relativeTime(iso, NOW)

  it('counts minutes, then hours, within the same Malaysian day', () => {
    expect(at('2026-11-09T01:59:30Z')).toEqual({ key: 'now' })
    expect(at('2026-11-09T01:59:00Z')).toEqual({ key: 'minute' })
    expect(at('2026-11-09T01:15:00Z')).toEqual({ key: 'minutes', n: 45 })
    expect(at('2026-11-09T01:00:00Z')).toEqual({ key: 'hour' })
    expect(at('2026-11-08T16:30:00Z')).toEqual({ key: 'hours', n: 9 })    // 00:30 KL the same day
  })

  it('"Yesterday" is the previous calendar day in Kuala Lumpur, not a 24-hour gap', () => {
    expect(at('2026-11-08T15:30:00Z')).toEqual({ key: 'yesterday' })      // 23:30 KL, 10.5 hours ago
    expect(at('2026-11-07T16:00:00Z')).toEqual({ key: 'yesterday' })      // 00:00 KL, 34 hours ago
    expect(at('2026-11-07T15:59:00Z')).toEqual({ key: 'days', n: 2 })
  })

  it('minutes win across midnight', () => {
    const justAfterMidnight = Date.parse('2026-11-08T16:10:00Z')          // 00:10 KL
    expect(relativeTime('2026-11-08T15:50:00Z', justAfterMidnight)).toEqual({ key: 'minutes', n: 20 })
  })

  it('counts days, then shows the date from 30 days back', () => {
    expect(at('2026-10-31T02:00:00Z')).toEqual({ key: 'days', n: 9 })
    expect(at('2026-10-11T02:00:00Z')).toEqual({ key: 'days', n: RELATIVE_AS_DATE_DAYS - 1 })
    const old = at('2026-10-10T02:00:00Z')
    expect(old?.key).toBe('on')
  })

  it('reads a time a little in the future as just now, and nonsense as null', () => {
    expect(at('2026-11-09T02:03:00Z')).toEqual({ key: 'now' })
    expect(at('not-a-date')).toBeNull()
  })
})
