/**
 * H8: which drawn sample document shows each document type (the "See a sample" link).
 *
 * ONE map, one place. The drawings are in `public/samples/` (made-up details, stamped SAMPLE / CONTOH).
 * A type with no entry has no sample and gets no link. `other` never has one.
 *   - A parent's IC looks like a student's IC, so `parent_ic` shows the MyKad sample.
 *   - Income proofs map one-to-one: salary_slip -> payslip, epf -> epf_statement, and so on.
 *   - `higher_results` has two drawings (STPM and Matriculation); `kind` picks, STPM when unknown.
 */
export const SAMPLE_FILE: Record<string, string> = {
  ic: 'mykad',
  parent_ic: 'mykad',
  results_slip: 'results_slip',
  higher_results: 'higher_results_stpm',
  semester_result: 'semester_result',
  photo: 'photo',
  offer_letter: 'offer_letter',
  school_leaving_cert: 'school_leaving_cert',
  statement_of_intent: 'statement_of_intent',
  reference_letter: 'reference_letter',
  guardianship_letter: 'guardianship_letter',
  birth_certificate: 'birth_certificate',
  salary_slip: 'payslip',
  epf: 'epf_statement',
  str: 'str',
  bank_statement: 'bank_statement',
  income_support_doc: 'income_support_doc',
  water_bill: 'water_bill',
  electricity_bill: 'electricity_bill',
}

/** The sample's base name for a document type, or null when there is none. */
export function sampleFor(docType: string, kind?: string | null): string | null {
  if (docType === 'higher_results' && kind === 'matric') return 'higher_results_matric'
  return SAMPLE_FILE[docType] ?? null
}

export function samplePath(name: string): string {
  return `/samples/${name}.svg`
}
