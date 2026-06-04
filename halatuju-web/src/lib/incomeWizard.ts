// Pure mirror of the backend income requirement engine
// (apps/scholarship/income_engine.income_requirements). Kept framework-free so it
// is unit-testable in node-env Jest and so the student's dynamic checklist matches
// exactly what the officer verdict will assemble. Keep the two in lockstep.

export type IncomeRoute = '' | 'str' | 'salary'
export type IncomeEarner = '' | 'father' | 'mother' | 'guardian'
export type EarnerWork = '' | 'payslip' | 'informal' | 'not_working'

export interface IncomeAnswers {
  income_route?: IncomeRoute | null
  income_earner?: IncomeEarner | null
  earner_work_status?: EarnerWork | null
}

// The extra document a given earner needs to prove the relationship
// ('' for a father — derived from the student's IC patronymic).
const RELATIONSHIP_DOC: Record<string, string> = {
  mother: 'birth_certificate',
  guardian: 'guardianship_letter',
}

export function relationshipDocFor(earner: string | null | undefined): string {
  return RELATIONSHIP_DOC[earner || ''] || ''
}

/** The documents the family needs, given the wizard answers.
 *  Always: the earner IC + the relationship proof; then the income evidence per
 *  route/work-status. Optional docs add credibility but never block. */
export function incomeRequirements(a: IncomeAnswers): { compulsory: string[]; optional: string[] } {
  const route = a.income_route || ''
  const earner = a.income_earner || ''
  const work = a.earner_work_status || ''

  const compulsory: string[] = ['parent_ic'] // the earner's IC — always
  const relDoc = relationshipDocFor(earner)
  if (relDoc) compulsory.push(relDoc) // mother → BC, guardian → letter; father → none

  let optional: string[] = []
  if (route === 'str') {
    compulsory.push('str')
    optional = ['water_bill', 'electricity_bill', 'salary_slip', 'epf']
  } else if (route === 'salary') {
    if (work === 'payslip') {
      compulsory.push('salary_slip', 'epf')
      optional = ['water_bill', 'electricity_bill']
    } else if (work === 'not_working') {
      compulsory.push('epf')
      optional = ['water_bill', 'electricity_bill']
    } else if (work === 'informal') {
      // No payslip/EPF to demand — the bills tie the earner to the household;
      // a person judges the rest (never blocked).
      compulsory.push('water_bill', 'electricity_bill')
      optional = ['epf']
    } else {
      optional = ['salary_slip', 'epf', 'water_bill', 'electricity_bill']
    }
  }

  const seen = new Set(compulsory)
  optional = optional.filter((d) => !seen.has(d)) // a doc is never both
  return { compulsory, optional }
}

/** The wizard is "answered enough" to show a meaningful checklist once the route
 *  and earner are chosen (and, on the salary route, the work status). */
export function wizardComplete(a: IncomeAnswers): boolean {
  if (!a.income_route || !a.income_earner) return false
  if (a.income_route === 'salary' && !a.earner_work_status) return false
  return true
}
