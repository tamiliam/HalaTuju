/**
 * The offer itself: the award, the conditional bursary agreement, accepting or declining,
 * and the onboarding that follows.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'
import type { ScholarshipApplication } from './application'

// ── Phase E/F: student award + onboarding (F8b) ──────────────────────────
// The student's funded-studies offer. The sponsor's identity is never exposed
// (allowlist serializer): the student only ever sees the amount + deadline.

export interface StudentAward {
  id: number
  amount: string
  status: string
  offered_at: string
  accept_deadline: string
}

// ── Conditional Bursary Award Agreement (BURSARY_AGREEMENT_ENABLED, default OFF) ──
// The binding bursary CONTRACT a student + a parent/guardian surety sign when they
// accept an award. The DONOR is never a party and is never named (anonymity): none
// of these shapes carry a sponsor/donor field.

/** The not-yet-signed agreement the student is about to sign — frozen particulars +
 *  the server-rendered HTML body. Present in the award GET (alongside `offer`) only
 *  when the flag is on AND an offer/active award exists AND it's not yet signed. */
export interface BursaryPreview {
  award_amount: string | null
  payment_schedule: string
  institution_name: string
  course_name: string
  progress_standard: string
  foundation_signatory_name: string
  foundation_signatory_title: string
  rendered_html: string   // the full agreement body (server-rendered HTML; carries the DRAFT banner)
}

/** A signed (or part-signed) agreement: derived status + frozen particulars + the
 *  four signature timestamps + a time-limited signed PDF URL. No donor field. */
export interface BursaryAgreement {
  id: number
  status: string
  version: string
  locale: string
  award_amount: string | null
  payment_schedule: string
  institution_name: string
  course_name: string
  progress_standard: string
  foundation_signatory_name: string
  foundation_signatory_title: string
  student_signed_name: string
  student_signed_at: string | null
  guarantor_name: string
  guarantor_relationship: string
  guarantor_signed_at: string | null
  foundation_signed_at: string | null
  witness_signed_at: string | null
  agreement_sha256: string
  pdf_url: string | null
}

/** GET the student's current award offer (if any) + whether they're a minor
 *  (so the page knows to require a guardian to accept). When the bursary flag is
 *  on the payload also carries either `bursary_preview` (about to sign) or
 *  `bursary_agreement` (already signed) — never a donor field. */
export async function getStudentAward(
  options?: ApiOptions
): Promise<{
  offer: StudentAward | null
  finalising?: boolean
  is_minor: boolean
  bursary_preview?: BursaryPreview
  bursary_agreement?: BursaryAgreement
  // Gates the "View my award" panel — OFF while the accept/onboarding flow isn't exposed yet.
  acceptance_enabled?: boolean
}> {
  return apiRequest('/api/v1/scholarship/award/', options)
}

/** Accept or decline the award. A minor's guardian must accept (name + relationship + NRIC) —
 *  the same three facts the share-consent guardian gate asks for, enforced server-side. When the
 *  bursary flag is on, accepting also signs the contract in-session: an ADULT
 *  types their own signature (`student_signed_name` + optional `_nric`) AND a
 *  parent surety (`guarantor_*`); a MINOR's guardian IS the guarantor (the
 *  `guardian_*` fields). On error the API returns { error: code }; the code
 *  surfaces via err.code (apiRequest carries it). */
export async function respondToAward(
  payload: {
    action: 'accept' | 'decline'
    locale?: string
    granted_by?: 'self' | 'guardian'
    guardian_name?: string
    guardian_relationship?: string
    guardian_nric?: string
    // Bursary agreement (flag-gated) — adult student signs their own name + brings a surety.
    student_signed_name?: string
    student_signed_nric?: string
    guarantor_name?: string
    guarantor_nric?: string
    guarantor_relationship?: string
  },
  options?: ApiOptions
): Promise<StudentAward> {
  return apiRequest('/api/v1/scholarship/award/', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...options,
  })
}

/** GET the student's OWN signed bursary agreement (status + particulars + signed
 *  PDF URL). 404s when the feature is off or no agreement exists yet — callers
 *  treat that as "no agreement" and render nothing. */
export async function getBursaryAgreement(options?: ApiOptions): Promise<BursaryAgreement> {
  return apiRequest('/api/v1/scholarship/bursary-agreement/', options)
}

/** F8a: finish post-award onboarding — store the questionnaire answers and
 *  stamp onboarded_at. Returns the updated application. On error returns
 *  { error, code } (e.g. code 'not_awarded' when the award isn't accepted). */
export async function submitOnboarding(
  applicationId: number,
  answers: Record<string, unknown>,
  options?: ApiOptions
): Promise<ScholarshipApplication> {
  return apiRequest(`/api/v1/scholarship/applications/${applicationId}/onboarding-complete/`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
    ...options,
  })
}
