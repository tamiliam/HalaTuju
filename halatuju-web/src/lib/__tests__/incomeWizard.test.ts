import {
  incomeRequirements,
  relationshipDocFor,
  wizardComplete,
  workingMembers,
  salaryMemberBlocks,
  hasPatronymic,
  declaredAmount,
  strIcSlotMembers,
  strIcNamedMembers,
  type StrSlotDoc,
} from '@/lib/incomeWizard'
import { readApi } from '@/test/apiSource'

describe('strIcSlotMembers — TD-309, the IC that settles whose STR it is', () => {
  const str = (missing: string[], unreadable: string[] = [], uploaded_at = '2026-09-01T00:00:00Z'): StrSlotDoc =>
    ({ doc_type: 'str', household_member: 'father', uploaded_at, str_check: { ic_slots: { missing, unreadable } } })
  const ic = (m: string): StrSlotDoc => ({ doc_type: 'parent_ic', household_member: m, uploaded_at: '2026-09-01T00:00:00Z' })
  const STR_FATHER = { income_route: 'str' as const, income_earner: 'father' as const }
  const SALARY_FATHER = { income_route: 'salary' as const, income_working_members: ['father' as const] }

  it('offers the named members on both routes', () => {
    expect(strIcSlotMembers([str(['mother'])], STR_FATHER)).toEqual(['mother'])
    expect(strIcSlotMembers([str(['mother'])], SALARY_FATHER)).toEqual(['mother'])
  })

  it('never offers a second card to a member who already owns one (earner / ticked member)', () => {
    expect(strIcSlotMembers([str(['father', 'mother']), ic('father')], STR_FATHER)).toEqual(['mother'])
    expect(strIcSlotMembers([str(['father', 'mother']), ic('father')], SALARY_FATHER)).toEqual(['mother'])
    expect(strIcSlotMembers([str(['mother'])],
      { income_route: 'salary', income_working_members: ['father', 'mother'] })).toEqual([])
    expect(strIcSlotMembers([str(['mother'])], { income_route: 'str', income_earner: 'mother' })).toEqual([])
  })

  it('is missing ∪ unreadable, in MEMBER_ORDER', () => {
    expect(strIcSlotMembers([str(['sister', 'guardian'], ['mother'])], STR_FATHER))
      .toEqual(['mother', 'guardian', 'sister'])
  })

  it('keeps a member whose tagged IC is on file once the STR is settled (never hides an upload)', () => {
    expect(strIcSlotMembers([str([]), ic('father'), ic('mother')], STR_FATHER)).toEqual(['mother'])
    // an untagged legacy IC is nobody's extra card
    expect(strIcSlotMembers([str([]), ic('')], STR_FATHER)).toEqual([])
  })

  it('no STR, or a payload from before TD-309 without ic_slots → []', () => {
    expect(strIcSlotMembers([ic('mother')], STR_FATHER)).toEqual([])
    expect(strIcSlotMembers([{ doc_type: 'str', uploaded_at: '2026-09-01T00:00:00Z', str_check: {} }, ic('mother')],
      STR_FATHER)).toEqual([])
    expect(strIcSlotMembers([{ doc_type: 'str', str_check: null }], STR_FATHER)).toEqual([])
    expect(strIcSlotMembers([], STR_FATHER)).toEqual([])
  })

  it('review F1: strIcNamedMembers is who the SERVER names — not who is kept for a doc on file', () => {
    expect(strIcNamedMembers([str(['sister'], ['mother']), ic('guardian')])).toEqual(['mother', 'sister'])
    // settled STR + her IC on file: she still has a card, but the server no longer names her
    expect(strIcNamedMembers([str([]), ic('mother')])).toEqual([])
    expect(strIcSlotMembers([str([]), ic('mother')], STR_FATHER)).toEqual(['mother'])
    expect(strIcNamedMembers([ic('mother')])).toEqual([])
    const older = str(['guardian'], [], '2026-08-01T00:00:00Z')
    expect(strIcNamedMembers([str([], [], '2026-09-15T00:00:00Z'), older])).toEqual([])
  })

  it('DRIFT: "latest" is the api\'s — live rows, `uploaded_at` then `id` descending (document_snapshot)', () => {
    // The ordering above is a copy of the server's, so it is read from the server's source: if
    // `SNAPSHOT_ORDER` or `latest_doc` changes shape, this goes red and the copy must follow.
    const src = readApi('apps/scholarship/document_snapshot.py')
    expect(src).toMatch(/^SNAPSHOT_ORDER = \('-uploaded_at', '-id'\)$/m)
    expect(src).toMatch(/def latest_doc\([\s\S]*?return live_docs\(application, doc_type, member=member, members=members\)\.first\(\)/)
    expect(src).toMatch(/def _live\(rows\):\s*\n\s*return \[d for d in rows if getattr\(d, 'superseded_at', None\) is None\]/)
  })

  it('the LATEST STR wins over an older one with different slots, whatever the list order', () => {
    const older = str(['guardian'], [], '2026-08-01T00:00:00Z')
    const newer = str(['mother'], [], '2026-09-15T00:00:00Z')
    expect(strIcSlotMembers([older, newer], STR_FATHER)).toEqual(['mother'])
    expect(strIcSlotMembers([newer, older], STR_FATHER)).toEqual(['mother'])
  })

  it('TD-292: an exact `uploaded_at` tie goes to the greater id, whatever the list order', () => {
    const lower = { ...str(['guardian'], [], '2026-09-15T00:00:00Z'), id: 7 }
    const higher = { ...str(['mother'], [], '2026-09-15T00:00:00Z'), id: 8 }
    expect(strIcSlotMembers([lower, higher], STR_FATHER)).toEqual(['mother'])
    expect(strIcSlotMembers([higher, lower], STR_FATHER)).toEqual(['mother'])
  })
})

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
