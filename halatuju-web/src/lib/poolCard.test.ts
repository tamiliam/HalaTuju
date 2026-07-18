import { daysUntil, countdown, rmWhole, fundedFraction } from './poolCard'

describe('rmWhole', () => {
  it('drops decimals and groups thousands', () => {
    expect(rmWhole('2000.00')).toBe('2,000')
    expect(rmWhole('3000')).toBe('3,000')
    expect(rmWhole(500)).toBe('500')
    expect(rmWhole('12345.67')).toBe('12,346')
  })
  it('passes non-numeric through', () => {
    expect(rmWhole(null)).toBe('')
    expect(rmWhole('abc')).toBe('abc')
  })
})

describe('fundedFraction', () => {
  it('0 when unfunded (empty rail)', () => {
    expect(fundedFraction('0', '2000')).toBe(0)
    expect(fundedFraction(null, '2000')).toBe(0)
    expect(fundedFraction(undefined, 2000)).toBe(0)
  })
  it('partial and full', () => {
    expect(fundedFraction('500', '2000')).toBe(0.25)
    expect(fundedFraction('2000', '2000')).toBe(1)
  })
  it('0 for a missing/non-positive target', () => {
    expect(fundedFraction('500', null)).toBe(0)
    expect(fundedFraction('500', '0')).toBe(0)
  })
  it('clamps overshoot to 1', () => {
    expect(fundedFraction('3000', '2000')).toBe(1)
  })
})

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

