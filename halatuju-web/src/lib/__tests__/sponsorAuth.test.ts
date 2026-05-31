import { checkPassword, SPONSOR_SOURCES } from '../sponsorAuth'

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
