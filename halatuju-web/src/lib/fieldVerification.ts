import { documentFacts } from './officerCockpit'
import type { AdminApplicantDocument, AdminScholarshipDetail } from './admin-api'

/**
 * Field-level "verified" ticks for the officer cockpit (owner 2026-07-15). Purely a DISPLAY
 * projection of the document-matching the engines already do: a field is "verified" only when its
 * typed value MATCHES an uploaded, machine-read document — the same green truth the Documents
 * drawer chips show (`documentFacts`). We deliberately reuse that helper so the tick can never
 * disagree with the chip. No backend / no MODEL_VERSION involvement — read-only, additive.
 *
 * Rules are CONSERVATIVE: a tick shows only on the engine's strongest "clean match" (`verified`)
 * state. Partial / mismatch / no-document → no tick (absence = "not corroborated"; the drawer's red
 * chips own the mismatches, so we never paint a competing failure here).
 */
export type VerifiableField =
  | 'name'
  | 'nric'
  | 'school'
  | 'grades'
  | 'chosenProgramme'
  | 'reportingDate'
  | 'address'
  | 'parentName'
  | 'householdIncome'
  | 'str'

export interface FieldVerification {
  /** i18n suffix under admin.scholarship.verified.source.* — names the document it matched. */
  source: string
}

/** A document is "live" (not a superseded re-upload). The admin drawer keeps old copies visible. */
function isLive(doc: AdminApplicantDocument): boolean {
  return !doc.superseded_at
}

/** True when the document's own distilled facts (drawer chips) mark `factKey` as a clean match. */
function factVerified(doc: AdminApplicantDocument, factKey: string): boolean {
  return documentFacts(doc).some((f) => f.key === factKey && f.status === 'verified')
}

/**
 * Map each requested profile field → its verification (or undefined). A field is present in the map
 * ONLY when a live document of the right type reports its relevant fact as a clean match.
 */
export function fieldVerifications(
  app: Pick<AdminScholarshipDetail, 'documents'>,
): Partial<Record<VerifiableField, FieldVerification>> {
  const docs = (app.documents || []).filter(isLive)
  const out: Partial<Record<VerifiableField, FieldVerification>> = {}

  const set = (field: VerifiableField, docType: string, factKey: string, source: string): boolean => {
    if (docs.some((d) => d.doc_type === docType && factVerified(d, factKey))) {
      out[field] = { source }
      return true
    }
    return false
  }

  // Identity — the MyKad is the authority (deterministic Vision read).
  set('name', 'ic', 'name', 'mykad')
  set('nric', 'ic', 'ic_no', 'mykad')

  // Academic.
  set('school', 'school_leaving_cert', 'school', 'schoolLeavingCert')
  set('grades', 'results_slip', 'results', 'resultsSlip')

  // Pathway — the offer letter establishes the chosen programme; the reporting date is trusted only
  // when it comes from a VALIDATED official registration summons (the reporting-bonus gate).
  set('chosenProgramme', 'offer_letter', 'pathway', 'offerLetter')
  if (docs.some((d) => d.doc_type === 'offer_letter' && d.pathway_check?.reporting_official)) {
    out.reportingDate = { source: 'offerLetter' }
  }

  // Address — a utility bill whose address matches the home address.
  set('address', 'water_bill', 'address', 'utilityBill') ||
    set('address', 'electricity_bill', 'address', 'utilityBill')

  // Family / income (conservative — see the note above).
  //  · Parent name: the parent's IC is on file and legibly read.
  set('parentName', 'parent_ic', 'name', 'parentIc')
  //  · Household income: a real income figure was read off a payslip or EPF statement.
  if (
    docs.some((d) => d.doc_type === 'salary_slip' && factVerified(d, 'amount')) ||
    docs.some((d) => d.doc_type === 'epf' && factVerified(d, 'contribution'))
  ) {
    out.householdIncome = { source: 'incomeProof' }
  }
  //  · STR: only when the proof is BOTH approved (Lulus) AND current (dated).
  if (docs.some((d) => d.doc_type === 'str' && factVerified(d, 'status') && factVerified(d, 'current'))) {
    out.str = { source: 'strDoc' }
  }

  return out
}
