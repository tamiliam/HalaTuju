import {
  checkPassword, SPONSOR_SOURCES, formatMyMobile, isValidMyMobile,
  formatIntlPhone, isValidIntlPhone, toStoredPhone, parseStoredPhone,
} from '../sponsorAuth'
import { COUNTRIES, countryByIso, countryByDial, flagOf, DEFAULT_COUNTRY_ISO } from '../countries'

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

describe('international phone (country-selectable)', () => {
  it('formatIntlPhone strips non-digits, a leading 0, and caps length', () => {
    expect(formatIntlPhone('(415) 555-0123')).toBe('4155550123')
    expect(formatIntlPhone('012 345 6789')).toBe('123456789')       // leading 0 dropped
    expect(formatIntlPhone('1234567890123456789')).toHaveLength(14) // capped
  })
  it('isValidIntlPhone accepts 4–14 digits, rejects outside', () => {
    expect(isValidIntlPhone('4155550123')).toBe(true)   // US
    expect(isValidIntlPhone('7911123456')).toBe(true)   // UK
    expect(isValidIntlPhone('123')).toBe(false)         // too short
    expect(isValidIntlPhone('')).toBe(false)
  })
  it('toStoredPhone composes "+<dial> <national>"', () => {
    expect(toStoredPhone('44', '7911123456')).toBe('+44 7911123456')
    expect(toStoredPhone('65', '9123 4567')).toBe('+65 91234567')
  })
  it('parseStoredPhone round-trips the dial code back to a country', () => {
    expect(parseStoredPhone('+44 7911123456')).toEqual({ iso: 'GB', local: '7911123456' })
    expect(parseStoredPhone('+65 91234567')).toEqual({ iso: 'SG', local: '91234567' })
    expect(parseStoredPhone('+60 123456789')).toEqual({ iso: 'MY', local: '123456789' })
  })
  it('parseStoredPhone treats a bare/legacy number as Malaysian', () => {
    expect(parseStoredPhone('012-345 6789')).toEqual({ iso: 'MY', local: '123456789' })
    expect(parseStoredPhone('')).toEqual({ iso: 'MY', local: '' })
  })
})

describe('countries data', () => {
  it('has Malaysia as the default and first entry', () => {
    expect(DEFAULT_COUNTRY_ISO).toBe('MY')
    expect(COUNTRIES[0].iso2).toBe('MY')
  })
  it('every entry has a unique ISO2 and digit-only dial code', () => {
    expect(new Set(COUNTRIES.map((c) => c.iso2)).size).toBe(COUNTRIES.length)
    COUNTRIES.forEach((c) => expect(c.dial).toMatch(/^[0-9]{1,4}$/))
  })
  it('countryByIso / countryByDial resolve correctly', () => {
    expect(countryByIso('sg')?.name).toBe('Singapore')
    expect(countryByDial('60123456789')?.iso2).toBe('MY')
    expect(countryByDial('971501234567')?.iso2).toBe('AE')  // longest-prefix wins over +9?
  })
  it('flagOf derives a two-char regional-indicator flag', () => {
    expect(flagOf('MY')).toBe('🇲🇾')
    expect(flagOf('??')).toBe('🏳️')
  })
})
