// Pure mirror of the backend income requirement engine
// (apps/scholarship/income_engine). Kept framework-free so it is unit-testable in
// node-env Jest and so the student's dynamic checklist matches exactly what the
// officer verdict will assemble. Keep the two in lockstep.
//
// Two shapes under one wizard, split by Q1 (STR document?):
//   - STR route    → a single earner (father/mother/guardian) + STR doc.
//   - SALARY route → MULTIPLE working members, each with their own IC + payslip +
//                    EPF (tagged by household member). Siblings prove the
//                    relationship via the SAME father's-name patronymic as the
//                    student, so they need no extra document.

export type IncomeRoute = '' | 'str' | 'salary'
export type IncomeEarner = '' | 'father' | 'mother' | 'guardian'
export type EarnerWork = '' | 'payslip' | 'informal' | 'not_working' // legacy (STR route unaffected)
export type WorkingMember = 'father' | 'mother' | 'guardian' | 'brother' | 'sister'

export interface IncomeAnswers {
  income_route?: IncomeRoute | null
  income_earner?: IncomeEarner | null // STR route only
  income_working_members?: WorkingMember[] | null // salary route
}

/** One required/optional document for a member block: the doc type + the member it
 *  is tagged to ('' for the untagged single docs — birth cert / guardianship letter). */
export interface MemberDoc {
  docType: string
  member: string
}

export interface MemberBlock {
  member: WorkingMember
  compulsory: MemberDoc[]
  optional: MemberDoc[]
  relDoc: string
}

export interface IncomeReqs {
  route: IncomeRoute
  members: MemberBlock[] // salary route only
  compulsory: string[] // STR route flat list (salary route: empty)
  optional: string[] // household-level (utility bills)
}

// The extra document a given member needs to prove the relationship
// ('' for father/brother/sister — derived from the shared student-IC patronymic).
const RELATIONSHIP_DOC: Record<string, string> = {
  mother: 'birth_certificate',
  guardian: 'guardianship_letter',
}

export function relationshipDocFor(member: string | null | undefined): string {
  return RELATIONSHIP_DOC[member || ''] || ''
}

const MEMBER_ORDER: WorkingMember[] = ['father', 'mother', 'guardian', 'brother', 'sister']

/** The ticked salary-route members, de-duped and in display order. Tolerant of a
 *  blank/garbage value. */
export function workingMembers(members: WorkingMember[] | null | undefined): WorkingMember[] {
  const chosen = new Set((members || []).filter((m) => MEMBER_ORDER.includes(m as WorkingMember)))
  return MEMBER_ORDER.filter((m) => chosen.has(m))
}

/** Per-member document plan for the salary route. Income-evidence docs (parent_ic /
 *  salary_slip / epf) are TAGGED to the member; the relationship doc (birth cert /
 *  guardianship letter) is a single household doc, untagged. */
export function salaryMemberBlocks(members: WorkingMember[] | null | undefined): MemberBlock[] {
  const chosen = new Set(workingMembers(members))
  const blocks: MemberBlock[] = []
  for (const m of MEMBER_ORDER) {
    if (!chosen.has(m)) continue
    // Compulsory order (mirrors income_engine.salary_member_blocks): IC → salary slip
    // → relationship doc. The salary slip is COMPULSORY (gate v2); EPF does not substitute.
    const compulsory: MemberDoc[] = [
      { docType: 'parent_ic', member: m },
      { docType: 'salary_slip', member: m },
    ]
    const relDoc = relationshipDocFor(m)
    if (relDoc) compulsory.push({ docType: relDoc, member: '' }) // birth cert / letter — single, untagged
    const optional: MemberDoc[] = [{ docType: 'epf', member: m }]
    blocks.push({ member: m, compulsory, optional, relDoc })
  }
  return blocks
}

/** The documents the family needs, given the wizard answers. The STR route keeps the
 *  single-earner shape; the salary route is driven by income_working_members. */
export function incomeRequirements(a: IncomeAnswers): IncomeReqs {
  const route = a.income_route || ''

  if (route === 'salary') {
    return {
      route: 'salary',
      members: salaryMemberBlocks(a.income_working_members),
      compulsory: [],
      optional: ['water_bill', 'electricity_bill'],
    }
  }

  const earner = a.income_earner || ''
  const compulsory: string[] = ['parent_ic'] // the earner's IC — always
  const relDoc = relationshipDocFor(earner)
  if (relDoc) compulsory.push(relDoc) // mother → BC, guardian → letter; father → none

  let optional: string[] = []
  if (route === 'str') {
    compulsory.push('str')
    optional = ['water_bill', 'electricity_bill', 'salary_slip', 'epf']
  }
  const seen = new Set(compulsory)
  optional = optional.filter((d) => !seen.has(d)) // a doc is never both
  return { route, members: [], compulsory, optional }
}

/** The wizard is "answered enough" to show a meaningful checklist once the route is
 *  chosen and — STR: an earner is picked; salary: at least one working member ticked. */
export function wizardComplete(a: IncomeAnswers): boolean {
  if (!a.income_route) return false
  if (a.income_route === 'salary') return workingMembers(a.income_working_members).length > 0
  return !!a.income_earner
}
