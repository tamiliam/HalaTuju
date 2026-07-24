import {
  incomeRequirements,
  relationshipDocFor,
  wizardComplete,
  workingMembers,
  salaryMemberBlocks,
  hasPatronymic,
  declaredAmount,
} from '@/lib/incomeWizard'

describe('declaredAmount — Phase 2A declared informal income', () => {
  it('reads a positive amount, else 0', () => {
    expect(declaredAmount({ father: 1500 }, 'father')).toBe(1500)
    expect(declaredAmount({ father: 0 }, 'father')).toBe(0)
    expect(declaredAmount({ mother: 1200 }, 'father')).toBe(0)
    expect(declaredAmount(null, 'father')).toBe(0)
    expect(declaredAmount(undefined, 'father')).toBe(0)
  })
})

describe('incomeRequirements — STR route + blank (mirror of income_engine)', () => {
  it('blank wizard → only the earner IC', () => {
    const r = incomeRequirements({})
    expect(r.compulsory).toEqual(['parent_ic'])
    expect(r.optional).toEqual([])
    expect(r.members).toEqual([])
  })

  it('STR route, father → earner IC + STR; bills/payslip optional', () => {
    const r = incomeRequirements({ income_route: 'str', income_earner: 'father' })
    expect(r.route).toBe('str')
    expect(r.compulsory).toEqual(['parent_ic', 'str'])
    expect(r.optional).toEqual(['water_bill', 'electricity_bill', 'salary_slip', 'epf'])
  })

  it('STR route, mother → birth certificate is compulsory', () => {
    expect(incomeRequirements({ income_route: 'str', income_earner: 'mother' }).compulsory).toEqual(
      ['parent_ic', 'birth_certificate', 'str'],
    )
  })

  it('STR route, guardian → guardianship letter is compulsory', () => {
    expect(incomeRequirements({ income_route: 'str', income_earner: 'guardian' }).compulsory).toEqual(
      ['parent_ic', 'guardianship_letter', 'str'],
    )
  })

  it('no doc is both compulsory and optional (STR)', () => {
    const r = incomeRequirements({ income_route: 'str', income_earner: 'mother' })
    expect(r.compulsory.filter((d) => r.optional.includes(d))).toEqual([])
  })
})

describe('salary route — multi-earner per-member blocks', () => {
  it('workingMembers orders + dedupes + drops garbage', () => {
    expect(workingMembers(['sister', 'father', 'father', 'guardian'])).toEqual(['father', 'guardian', 'sister'])
    expect(workingMembers(null)).toEqual([])
    // @ts-expect-error garbage member is filtered out
    expect(workingMembers(['nope', 'father'])).toEqual(['father'])
  })

  it('father block → IC compulsory; income (salary slip + EPF) optional — any one way (2026-07-25)', () => {
    const [block] = salaryMemberBlocks(['father'])
    expect(block.compulsory).toEqual([
      { docType: 'parent_ic', member: 'father' },
    ])
    expect(block.optional).toEqual([
      { docType: 'salary_slip', member: 'father' },
      { docType: 'epf', member: 'father' },
    ])
    expect(block.relDoc).toBe('')
  })

  it('mother block adds untagged birth certificate; guardian adds untagged letter', () => {
    expect(salaryMemberBlocks(['mother'])[0].compulsory).toEqual([
      { docType: 'parent_ic', member: 'mother' },
      { docType: 'birth_certificate', member: '' },
    ])
    expect(salaryMemberBlocks(['guardian'])[0].compulsory).toEqual([
      { docType: 'parent_ic', member: 'guardian' },
      { docType: 'guardianship_letter', member: '' },
    ])
  })

  it('sibling block → IC compulsory; income optional (relationship via shared patronymic)', () => {
    const [block] = salaryMemberBlocks(['brother'])
    expect(block.compulsory).toEqual([
      { docType: 'parent_ic', member: 'brother' },
    ])
    expect(block.optional).toEqual([
      { docType: 'salary_slip', member: 'brother' },
      { docType: 'epf', member: 'brother' },
    ])
    expect(block.relDoc).toBe('')
  })

  it('incomeRequirements salary → blocks in order + household bills optional', () => {
    const r = incomeRequirements({ income_route: 'salary', income_working_members: ['sister', 'father'] })
    expect(r.route).toBe('salary')
    expect(r.members.map((b) => b.member)).toEqual(['father', 'sister'])
    expect(r.compulsory).toEqual([])
    expect(r.optional).toEqual(['water_bill', 'electricity_bill'])
  })
})

describe('relationshipDocFor + wizardComplete', () => {
  it('maps member → relationship doc (siblings derive from patronymic)', () => {
    expect(relationshipDocFor('father')).toBe('')
    expect(relationshipDocFor('brother')).toBe('')
    expect(relationshipDocFor('sister')).toBe('')
    expect(relationshipDocFor('mother')).toBe('birth_certificate')
    expect(relationshipDocFor('guardian')).toBe('guardianship_letter')
  })

  it('wizardComplete — STR needs earner; salary needs ≥1 working member', () => {
    expect(wizardComplete({})).toBe(false)
    expect(wizardComplete({ income_route: 'str', income_earner: 'father' })).toBe(true)
    expect(wizardComplete({ income_route: 'str' })).toBe(false)
    expect(wizardComplete({ income_route: 'salary', income_working_members: [] })).toBe(false)
    expect(wizardComplete({ income_route: 'salary', income_working_members: ['brother'] })).toBe(true)
  })
})

describe('hasPatronymic — Malaysian parentage connectors', () => {
  it('detects A/L · A/P · S/O · D/O · bin · binti · @ (incl. spaced slash)', () => {
    expect(hasPatronymic('SHAARVESHWAAR A/L SARAWANAN')).toBe(true)
    expect(hasPatronymic('DIVASHINI A / P MURUGAN')).toBe(true)
    expect(hasPatronymic('AHMAD BIN ALI')).toBe(true)
    expect(hasPatronymic('SITI BINTI OSMAN')).toBe(true)
    expect(hasPatronymic('LEE WEI @ ALI')).toBe(true)
  })
  it('is false for a mononym (the #55 / DIVIYA case) and blanks', () => {
    expect(hasPatronymic('DIVIYA')).toBe(false)
    expect(hasPatronymic('')).toBe(false)
    expect(hasPatronymic(null)).toBe(false)
    expect(hasPatronymic('BINTANG')).toBe(false)   // not a bare "bin" token
  })
})

describe('mononym student → BC surfaced as optional father-link proof (#55)', () => {
  it('STR + father + no patronymic → birth_certificate becomes optional', () => {
    const withName = incomeRequirements(
      { income_route: 'str', income_earner: 'father' }, { studentHasPatronymic: false })
    expect(withName.optional).toContain('birth_certificate')
    // and it is NOT forced compulsory (never hard-blocks — soft proof)
    expect(withName.compulsory).not.toContain('birth_certificate')
  })
  it('STR + father WITH a patronymic → no BC offered (the normal case)', () => {
    expect(incomeRequirements(
      { income_route: 'str', income_earner: 'father' }, { studentHasPatronymic: true })
      .optional).not.toContain('birth_certificate')
    // default (unknown) also does not surface it
    expect(incomeRequirements({ income_route: 'str', income_earner: 'father' })
      .optional).not.toContain('birth_certificate')
  })
  it('mother earner already brings a BC → mononym flag does not double it', () => {
    const r = incomeRequirements(
      { income_route: 'str', income_earner: 'mother' }, { studentHasPatronymic: false })
    expect(r.compulsory).toContain('birth_certificate')
    expect(r.optional).not.toContain('birth_certificate')
  })
  it('salary + sibling + no patronymic → household BC optional; mother block not doubled', () => {
    expect(incomeRequirements(
      { income_route: 'salary', income_working_members: ['brother'] }, { studentHasPatronymic: false })
      .optional).toContain('birth_certificate')
    const withMother = incomeRequirements(
      { income_route: 'salary', income_working_members: ['mother', 'father'] }, { studentHasPatronymic: false })
    // mother's block already carries the BC → not added again household-level
    expect(withMother.optional).not.toContain('birth_certificate')
  })
})
