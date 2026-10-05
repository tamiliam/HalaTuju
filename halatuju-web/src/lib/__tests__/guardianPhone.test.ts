/**
 * Request #26, review F4 + F5: the parent phone round-trips into a form the validator accepts, and
 * the screen accepts exactly what the server does (a Malaysian mobile).
 */
import { isValidMobile, toLocalPhone } from '@/lib/guardianPhone'

describe('toLocalPhone — a stored number pre-fills in a form the validator accepts (F4)', () => {
  it.each([
    ['+60123456789', '012-345 6789'],
    ['60123456789', '012-345 6789'],
    ['0123456789', '012-345 6789'],
    ['0060123456789', '012-345 6789'],
    ['+60 11-1234 5678', '011-1234 5678'],
  ])('%s → %s, and it is valid', (stored, shown) => {
    expect(toLocalPhone(stored)).toBe(shown)
    expect(isValidMobile(toLocalPhone(stored))).toBe(true)
  })

  it('the old pre-fill bug is gone: +60 never becomes "601-…"', () => {
    expect(toLocalPhone('+60123456789').startsWith('601')).toBe(false)
  })
})

describe('isValidMobile — the server rule, on the screen (F5)', () => {
  it.each(['012-345 6789', '011-1234 5678', '+60123456789', '60 12 345 6789'])('accepts %s', (n) => {
    expect(isValidMobile(n)).toBe(true)
  })
  it.each(['abc0123456789', '+44 20 7946 0958', '123456789', '03-1234 5678', '012-345 678',
    '011-123 4567', ''])('refuses %s', (n) => {
    expect(isValidMobile(n)).toBe(false)
  })
})
