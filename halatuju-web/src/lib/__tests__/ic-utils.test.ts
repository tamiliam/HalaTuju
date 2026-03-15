import { formatIc, maskIc, validateIc, stripDashes } from '../ic-utils'

describe('formatIc', () => {
  it('formats 12 digits with dashes', () => {
    expect(formatIc('031215011234')).toBe('031215-01-1234')
  })
  it('partial input: 6 digits', () => {
    expect(formatIc('031215')).toBe('031215')
  })
  it('partial input: 8 digits', () => {
    expect(formatIc('03121501')).toBe('031215-01')
  })
  it('strips non-digits', () => {
    expect(formatIc('031215-01-1234')).toBe('031215-01-1234')
  })
  it('truncates beyond 12 digits', () => {
    expect(formatIc('03121501123456')).toBe('031215-01-1234')
  })
})

describe('maskIc', () => {
  it('masks all but last 4 digits', () => {
    expect(maskIc('031215-01-1234')).toBe('****-**-1234')
  })
  it('returns original if too short', () => {
    expect(maskIc('031215')).toBe('031215')
  })
})

describe('stripDashes', () => {
  it('removes dashes', () => {
    expect(stripDashes('031215-01-1234')).toBe('031215011234')
  })
})

describe('validateIc', () => {
  it('accepts valid IC (born 2003, state 01)', () => {
    expect(validateIc('031215-01-1234')).toBeNull()
  })
  it('accepts valid IC (born 2008, state 14)', () => {
    expect(validateIc('080601-14-5678')).toBeNull()
  })
  it('rejects wrong length', () => {
    expect(validateIc('03121501')).toBe('IC number must be 12 digits')
  })
  it('rejects invalid month', () => {
    expect(validateIc('031315-01-1234')).toBe('Invalid date of birth in IC number')
  })
  it('rejects invalid day', () => {
    expect(validateIc('030230-01-1234')).toBe('Invalid date of birth in IC number')
  })
  it('rejects too young (born 2012 = age 14)', () => {
    expect(validateIc('120601-01-1234')).toBe('IC number must belong to a student aged 15\u201323')
  })
  it('rejects too old (born 2002 = age 24)', () => {
    expect(validateIc('020601-01-1234')).toBe('IC number must belong to a student aged 15\u201323')
  })
  it('rejects invalid state code', () => {
    expect(validateIc('031215-99-1234')).toBe('Invalid state code in IC number')
  })
  it('accepts foreign-born code 71', () => {
    expect(validateIc('050601-71-1234')).toBeNull()
  })
})
