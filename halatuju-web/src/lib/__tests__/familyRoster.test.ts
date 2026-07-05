import { earningMembers, sameMemberSet, isValidPersonName } from '@/lib/familyRoster'

describe('isValidPersonName — guard a name field against numbers', () => {
  it('accepts real Malaysian names + connectors', () => {
    for (const n of ['JAYAKUMAR A/L ANNAMARI', 'THANGAM A/P RAMASAMY', 'Siti @ Aishah',
      "D'CRUZ", 'S. Kumar', 'Nur-Ain', '']) {
      expect(isValidPersonName(n)).toBe(true)
    }
  })
  it('rejects an IC / phone number typed into the name box', () => {
    for (const n of ['750819145383', '810122-10-5834', 'Kumar 123', '012-227 4556', '@#$']) {
      expect(isValidPersonName(n)).toBe(false)
    }
  })
})

describe('earningMembers — roster professions → income earners', () => {
  it('both parents working → father + mother (the #1 default for the salary wizard)', () => {
    expect(earningMembers({ father_occupation: 'technician', mother_occupation: 'teacher' }))
      .toEqual(['father', 'mother'])
  })

  it('drops non-earning professions (homemaker / unemployed / retired / deceased)', () => {
    expect(earningMembers({ father_occupation: 'technician', mother_occupation: 'homemaker' }))
      .toEqual(['father'])
    expect(earningMembers({ father_occupation: 'unemployed', mother_occupation: 'retired' }))
      .toEqual([])
  })

  it('includes earning pool members (guardian / brother / sister), de-duped + ordered', () => {
    expect(earningMembers({
      mother_occupation: 'trader',
      other_family_members: [{ role: 'guardian', occupation: 'driver' },
                             { role: 'brother', occupation: 'homemaker' }],
    })).toEqual(['mother', 'guardian'])   // brother is non-earning → excluded
  })
})

describe('sameMemberSet — order-independent equality (re-seed guard)', () => {
  it('equal regardless of order', () => {
    expect(sameMemberSet(['father', 'mother'], ['mother', 'father'])).toBe(true)
  })
  it('unequal when membership differs', () => {
    expect(sameMemberSet(['father'], ['father', 'mother'])).toBe(false)
    expect(sameMemberSet(['father'], ['mother'])).toBe(false)
  })
  it('two empties are equal', () => {
    expect(sameMemberSet([], [])).toBe(true)
  })
})
