import { incomeRequirements, relationshipDocFor, wizardComplete } from '@/lib/incomeWizard'

describe('incomeRequirements (mirror of income_engine.income_requirements)', () => {
  it('blank wizard → only the earner IC', () => {
    expect(incomeRequirements({})).toEqual({ compulsory: ['parent_ic'], optional: [] })
  })

  it('STR route, father → earner IC + STR; bills/payslip optional', () => {
    const r = incomeRequirements({ income_route: 'str', income_earner: 'father' })
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

  it('salary + payslip → salary slip + EPF compulsory, bills optional', () => {
    const r = incomeRequirements({ income_route: 'salary', income_earner: 'father', earner_work_status: 'payslip' })
    expect(r.compulsory).toEqual(['parent_ic', 'salary_slip', 'epf'])
    expect(r.optional).toEqual(['water_bill', 'electricity_bill'])
  })

  it('salary + not working → EPF only', () => {
    expect(incomeRequirements({ income_route: 'salary', income_earner: 'father', earner_work_status: 'not_working' }).compulsory)
      .toEqual(['parent_ic', 'epf'])
  })

  it('salary + informal → utility bills compulsory, EPF optional', () => {
    const r = incomeRequirements({ income_route: 'salary', income_earner: 'father', earner_work_status: 'informal' })
    expect(r.compulsory).toEqual(['parent_ic', 'water_bill', 'electricity_bill'])
    expect(r.optional).toContain('epf')
  })

  it('no doc is both compulsory and optional', () => {
    const r = incomeRequirements({ income_route: 'salary', income_earner: 'father', earner_work_status: 'payslip' })
    expect(r.compulsory.filter((d) => r.optional.includes(d))).toEqual([])
  })
})

describe('relationshipDocFor + wizardComplete', () => {
  it('maps earner → relationship doc', () => {
    expect(relationshipDocFor('father')).toBe('')
    expect(relationshipDocFor('mother')).toBe('birth_certificate')
    expect(relationshipDocFor('guardian')).toBe('guardianship_letter')
  })

  it('wizardComplete needs route + earner (+ work status on salary)', () => {
    expect(wizardComplete({})).toBe(false)
    expect(wizardComplete({ income_route: 'str', income_earner: 'father' })).toBe(true)
    expect(wizardComplete({ income_route: 'salary', income_earner: 'father' })).toBe(false)
    expect(wizardComplete({ income_route: 'salary', income_earner: 'father', earner_work_status: 'payslip' })).toBe(true)
  })
})
