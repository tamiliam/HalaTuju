import { figureTotal, figurePercent, formatRM } from './sponsorTrust'

describe('figureTotal', () => {
  it('sums stringified amounts', () => {
    expect(figureTotal([{ label: 'a', amount: '312000' }, { label: 'b', amount: '40000' }])).toBe(352000)
  })
  it('treats non-numeric / empty as zero', () => {
    expect(figureTotal([{ label: 'a', amount: '' }, { label: 'b', amount: 'x' }])).toBe(0)
  })
  it('handles null/empty', () => {
    expect(figureTotal(null)).toBe(0)
    expect(figureTotal([])).toBe(0)
  })
})

describe('figurePercent', () => {
  it('computes a rounded share', () => {
    expect(figurePercent('284000', 352000)).toBe(81)
  })
  it('guards divide-by-zero', () => {
    expect(figurePercent('100', 0)).toBe(0)
  })
  it('clamps to 0–100', () => {
    expect(figurePercent('500', 100)).toBe(100)
    expect(figurePercent('-5', 100)).toBe(0)
  })
})

describe('formatRM', () => {
  it('formats with thousands separators', () => {
    expect(formatRM('312000')).toBe('RM 312,000')
  })
  it('falls back to RM 0 for non-numeric', () => {
    expect(formatRM('abc')).toBe('RM 0')
  })
})
