import { checkPassword, SPONSOR_SOURCES, formatMyMobile, isValidMyMobile } from '../sponsorAuth'

describe('checkPassword', () => {
  it('passes a compliant password', () => {
    const r = checkPassword('Abcdef12')
    expect(r).toEqual({ minLength: true, mixedCase: true, hasNumber: true, allPass: true })
  })

  it('fails when too short', () => {
    const r = checkPassword('Ab1')
    expect(r.minLength).toBe(false)
    expect(r.allPass).toBe(false)
  })

  it('fails without mixed case', () => {
    expect(checkPassword('abcdef12').mixedCase).toBe(false)
    expect(checkPassword('ABCDEF12').mixedCase).toBe(false)
  })

  it('fails without a number', () => {
    const r = checkPassword('Abcdefgh')
    expect(r.hasNumber).toBe(false)
    expect(r.allPass).toBe(false)
  })

  it('empty password fails every rule', () => {
    expect(checkPassword('')).toEqual({ minLength: false, mixedCase: false, hasNumber: false, allPass: false })
  })
})

describe('SPONSOR_SOURCES', () => {
  it('is a non-empty list of unique codes', () => {
    expect(SPONSOR_SOURCES.length).toBeGreaterThan(0)
    expect(new Set(SPONSOR_SOURCES).size).toBe(SPONSOR_SOURCES.length)
  })
})

describe('formatMyMobile', () => {
  it('formats a 9-digit local mobile as XX-XXX XXXX', () => {
    expect(formatMyMobile('123456789')).toBe('12-345 6789')
  })
  it('formats a 10-digit local mobile (11-prefix) as XX-XXXX XXXX', () => {
    expect(formatMyMobile('1112345678')).toBe('11-1234 5678')
  })
  it('drops a leading 0 and a pasted +60', () => {
    expect(formatMyMobile('0123456789')).toBe('12-345 6789')
    expect(formatMyMobile('+60 12-345 6789')).toBe('12-345 6789')
  })
})

describe('isValidMyMobile', () => {
  it('accepts valid local mobiles (with or without 0 / +60)', () => {
    expect(isValidMyMobile('12-345 6789')).toBe(true)
    expect(isValidMyMobile('0123456789')).toBe(true)
    expect(isValidMyMobile('+60 11-1234 5678')).toBe(true)
  })
  it('rejects too-short, too-long, or non-mobile numbers', () => {
    expect(isValidMyMobile('12-345')).toBe(false)        // too short
    expect(isValidMyMobile('3-7955 1234')).toBe(false)    // landline (starts 3)
    expect(isValidMyMobile('')).toBe(false)
  })
})
