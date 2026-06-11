import { earningMembers, sameMemberSet } from '@/lib/familyRoster'

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
