import { formatDate } from '@/lib/formatDate'

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
