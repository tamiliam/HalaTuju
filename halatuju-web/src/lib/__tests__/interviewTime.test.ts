import { formatMyt, withinCutoff } from '@/lib/interviewTime'

describe('formatMyt', () => {
  it('renders a UTC ISO time in Malaysia time with the (MYT) tag', () => {
    // 2026-06-23 12:00 UTC == 20:00 MYT (UTC+8)
    const s = formatMyt('2026-06-23T12:00:00Z')
    expect(s).toContain('(MYT)')
    expect(s).toMatch(/8:00/)        // 20:00 → 8:00 PM
    expect(s).toMatch(/PM/i)
    expect(s).toContain('Jun')
    expect(s).toContain('2026')
  })

  it('returns empty for missing/invalid input', () => {
    expect(formatMyt('')).toBe('')
    expect(formatMyt(null)).toBe('')
    expect(formatMyt('not-a-date')).toBe('')
  })
})

describe('withinCutoff', () => {
  it('is true when the start is closer than the cutoff window', () => {
    const soon = new Date(Date.now() + 2 * 3600 * 1000).toISOString()  // 2h away
    expect(withinCutoff(soon, 12)).toBe(true)
  })

  it('is false when the start is further than the cutoff window', () => {
    const far = new Date(Date.now() + 48 * 3600 * 1000).toISOString()  // 48h away
    expect(withinCutoff(far, 12)).toBe(false)
  })

  it('is false for missing input', () => {
    expect(withinCutoff(null, 12)).toBe(false)
  })
})
