/** The account-type self-check (owner, 2026-09-09): defaults follow Vircle's birth-year rule
 *  (served as `vircle_expected`); a disagreeing pick coaches with a direction-specific note
 *  and never blocks. See lib/vircleAccount.ts. */
import { accountWarningKey, expectedAccountType } from '../vircleAccount'

describe('expectedAccountType', () => {
  it('reads the served expectation', () => {
    expect(expectedAccountType('principal')).toBe('principal')
    expect(expectedAccountType('child')).toBe('child')
  })

  it('degrades to principal — the common case — on a missing or unknown value', () => {
    expect(expectedAccountType(undefined)).toBe('principal')
    expect(expectedAccountType(null)).toBe('principal')
    expect(expectedAccountType('')).toBe('principal')
    expect(expectedAccountType('supplementary')).toBe('principal')
  })
})

describe('accountWarningKey', () => {
  it('is silent when the pick agrees with the expectation', () => {
    expect(accountWarningKey('principal', 'principal')).toBeNull()
    expect(accountWarningKey('child', 'child')).toBeNull()
  })

  it('an adult picking Child gets the re-register note', () => {
    expect(accountWarningKey('child', 'principal'))
      .toBe('scholarship.actionCentre.vircle.warnChildAdult')
  })

  it('a minor picking Principal gets the parent-registers note', () => {
    expect(accountWarningKey('principal', 'child'))
      .toBe('scholarship.actionCentre.vircle.warnPrincipalMinor')
  })
})
