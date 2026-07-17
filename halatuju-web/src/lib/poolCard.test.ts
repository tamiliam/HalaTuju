import { daysUntil, countdown, inAmountBucket } from './poolCard'

const NOW = new Date(2026, 6, 17) // 17 Jul 2026 (local)

describe('daysUntil', () => {
  it('null for empty / unparseable', () => {
    expect(daysUntil(null, NOW)).toBeNull()
    expect(daysUntil(undefined, NOW)).toBeNull()
    expect(daysUntil('not-a-date', NOW)).toBeNull()
  })
  it('counts whole days to a future date', () => {
    expect(daysUntil('2026-07-20', NOW)).toBe(3)
    expect(daysUntil('2026-07-17', NOW)).toBe(0)
  })
  it('negative for a past date', () => {
    expect(daysUntil('2026-07-10', NOW)).toBe(-7)
  })
})

describe('countdown', () => {
  it('hidden (null) when no date or already past', () => {
    expect(countdown(null, NOW)).toBeNull()
    expect(countdown('2026-07-16', NOW)).toBeNull()
  })
  it('today / one / many', () => {
    expect(countdown('2026-07-17', NOW)).toEqual({ kind: 'today', days: 0 })
    expect(countdown('2026-07-18', NOW)).toEqual({ kind: 'one', days: 1 })
    expect(countdown('2026-09-01', NOW)).toEqual({ kind: 'many', days: 46 })
  })
})

describe('inAmountBucket', () => {
  it('empty bucket matches everything', () => {
    expect(inAmountBucket('3000', '')).toBe(true)
    expect(inAmountBucket(null, '')).toBe(true)
  })
  it('ranges', () => {
    expect(inAmountBucket('1500', 'lt2000')).toBe(true)
    expect(inAmountBucket('2000', 'lt2000')).toBe(false)
    expect(inAmountBucket('2000', '2000to3000')).toBe(true)
    expect(inAmountBucket('3000', '2000to3000')).toBe(true)
    expect(inAmountBucket('3001', '2000to3000')).toBe(false)
    expect(inAmountBucket('3500', 'gt3000')).toBe(true)
    expect(inAmountBucket('3000', 'gt3000')).toBe(false)
  })
  it('non-numeric never matches a real bucket', () => {
    expect(inAmountBucket(null, 'lt2000')).toBe(false)
  })
})
