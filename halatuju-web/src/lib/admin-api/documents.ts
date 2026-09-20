/**
 * A student's uploaded document as the officer sees it — every per-document check the
 * reader returned — plus re-running vision, and the referees.
 */
import type {
  AcademicCheck, PathwayCheck, IncomeIcCheck, IncomeProofCheck,
  StrCheck, UtilityCheck, BcCheck, GuardianshipCheck, SupportDocCheck, SemesterCheck,
  SchoolLeavingCheck,
} from '@/lib/api'

import { API_BASE, adminMutate } from './client'
import type { ApiOptions } from './client'

export interface AdminApplicantDocument {
  id: number
  doc_type: string
  // Salary-route income docs: whose IC/salary slip/EPF this is (father/mother/…); '' otherwise.
  household_member?: string
  // Officer box placement: the stored tag, or (for a blank-tagged income doc) the member resolved
  // from the name on the doc against the family roster. '' for non-income / unresolvable. The
  // cockpit places a doc by `resolved_member || household_member`.
  resolved_member?: string
  original_filename: string
  content_type: string
  size: number
  verification_status: string
  download_url: string | null
  // S13: Vision OCR soft-signal fields (populated only for doc_type='ic')
  // Post-S14: vision_address surfaced for admin cross-check, no matcher.
  vision_nric: string
  vision_name: string
  vision_address: string
  vision_run_at: string | null
  vision_error: string
  vision_nric_verdict: '' | 'match' | 'mismatch' | 'unreadable'
  vision_name_verdict: '' | 'match' | 'partial' | 'mismatch' | 'unreadable'
  // Supporting-doc soft name/address presence checks (results slip, income, bills…)
  vision_name_match: '' | 'found' | 'not_found' | 'unreadable'
  vision_address_match: '' | 'found' | 'not_found' | 'unreadable'
  // Document-assist: Gemini-extracted fields for admin verification.
  // S2: results_slip carries `results: [{subject, grade}]` (subject+grade pairs).
  vision_fields?: {
    fields?: Record<string, string | string[] | Array<{ subject?: string; grade?: string }>>
    warnings?: string[]
    student_verdict?: string
    // How this doc's fields were read: 'deterministic' (label-anchored parser) vs 'ai'
    // (Gemini fallback) — surfaced to the officer as a capture-confidence badge.
    capture?: 'deterministic' | 'ai'
    error?: string
  }
  // Per-fact verification checks (the admin detail serializes documents via
  // ApplicantDocumentSerializer, so these arrive on the admin response too). Each is
  // null unless its doc_type matches. The cockpit renders them as coloured fact-labels.
  academic_check?: AcademicCheck | null
  pathway_check?: PathwayCheck | null
  income_ic_check?: IncomeIcCheck | null
  income_proof_check?: IncomeProofCheck | null
  str_check?: StrCheck | null
  utility_check?: UtilityCheck | null
  bc_check?: BcCheck | null
  guardianship_check?: GuardianshipCheck | null
  support_doc_check?: SupportDocCheck | null
  semester_check?: SemesterCheck | null
  school_leaving_check?: SchoolLeavingCheck | null
  // Genuineness fingerprint (soft, flag-gated) — for ic/parent_ic/str/results_slip/birth_certificate/
  // epf/offer_letter. Null when the check didn't run. The cockpit uses it to colour the doc chip.
  authenticity?: { status: 'genuine' | 'likely_genuine' | 'suspect' | `not_${string}`; reason: string; doc_seen?: string } | null
  // Phase 2 version history: when this doc was replaced by a re-upload (null/absent = the
  // live copy) + which doc superseded it. The admin serializer returns superseded rows so the
  // cockpit can show them under an "Old / Replaced" list; they are excluded from every fact group.
  superseded_at?: string | null
  superseded_by?: number | null
}

/** Admin re-runs Vision OCR on an existing IC document (soft signal, never a gate). */
export async function reRunVision(id: number, docId: number, options?: ApiOptions) {
  return adminMutate<AdminApplicantDocument>(
    `/api/v1/admin/scholarship/applications/${id}/documents/${docId}/re-run-vision/`,
    'POST', {}, options
  )
}

export interface AdminReferee {
  id: number; name: string; role: string; relationship: string; phone: string; email: string
}

/** Coordinator records a referee for the application at the verify-&-accept stage. */
export async function addReferee(
  id: number,
  payload: { name: string; role?: string; relationship?: string; phone?: string; email?: string },
  options?: ApiOptions
) {
  return adminMutate<AdminReferee>(
    `/api/v1/admin/scholarship/applications/${id}/referees/`, 'POST', payload, options
  )
}

/** Remove a referee from the application (204 No Content on success). */
export async function deleteReferee(id: number, refId: number, options?: ApiOptions): Promise<void> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(
    `${API_BASE}/api/v1/admin/scholarship/applications/${id}/referees/${refId}/`,
    { method: 'DELETE', headers }
  )
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    throw new Error(b.error || `Admin API error: ${res.status}`)
  }
}

