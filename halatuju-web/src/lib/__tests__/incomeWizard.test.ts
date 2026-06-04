import {
  incomeRequirements,
  relationshipDocFor,
  wizardComplete,
  workingMembers,
  salaryMemberBlocks,
} from '@/lib/incomeWizard'

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

  it('father block → IC tagged + optional payslip/EPF, no extra doc', () => {
    const [block] = salaryMemberBlocks(['father'])
    expect(block.compulsory).toEqual([{ docType: 'parent_ic', member: 'father' }])
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

  it('sibling block is IC only (relationship via shared patronymic)', () => {
    const [block] = salaryMemberBlocks(['brother'])
    expect(block.compulsory).toEqual([{ docType: 'parent_ic', member: 'brother' }])
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
