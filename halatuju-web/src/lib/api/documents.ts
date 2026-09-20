/**
 * Uploading a document, every per-document check the reader returns for it, the document
 * help coach, referees, and the consent record.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Documents / referee / consent (Sprint 5b) ───────────────────────────

export interface ApplicantDocument {
  id: number
  doc_type: string
  // Salary-route income docs: whose IC/payslip/EPF this is ('' for everything else).
  household_member: '' | 'father' | 'mother' | 'guardian' | 'brother' | 'sister'
  original_filename: string
  content_type: string
  size: number
  verification_status: string
  uploaded_at: string
  download_url: string | null
  // S13: Vision OCR soft-signal fields (populated only for doc_type='ic')
  vision_nric: string
  vision_name: string
  vision_address: string  // extracted IC address — a soft data point (often outdated), not a check
  vision_run_at: string | null
  vision_error: string
  // Server-computed match verdicts (empty when Vision hasn't run)
  vision_nric_verdict: '' | 'match' | 'mismatch' | 'unreadable'
  vision_name_verdict: '' | 'match' | 'partial' | 'mismatch' | 'unreadable'
  // Genuineness fingerprint (verification-assurance): null unless the check ran. Canonical outcome
  // (the backend serializer folds any legacy value): 'genuine' (pass) / 'suspect' (incomplete/cropped/
  // fabricated) / 'not_<type>' (not recognisably that document — e.g. not_ic, not_str, not_results).
  authenticity?: { status: 'genuine' | 'suspect' | `not_${string}`; reason: string; doc_seen?: string } | null
  // Supporting-doc soft checks: does the student's/parent's name appear, and
  // (utility bills only) the home address? '' = not run / N/A. Soft, never blocks.
  vision_name_match: '' | 'found' | 'not_found' | 'unreadable'
  vision_address_match: '' | 'found' | 'not_found' | 'unreadable'
  // Document-assist: Gemini-extracted fields + a soft student-facing verdict.
  // {} when not run. student_verdict: ok/name_mismatch/address_mismatch/wrong_doc/
  // unreadable/review_manually. Soft, never blocks.
  vision_fields?: {
    fields?: Record<string, string | string[]>
    warnings?: string[]
    student_verdict?: '' | 'ok' | 'name_mismatch' | 'address_mismatch' | 'wrong_doc' | 'unreadable' | 'review_manually'
    error?: string
  }
  // Check-1 Academic: the three clinical checks for a results slip (name / subjects /
  // results), server-computed against the student's own profile. null for other types.
  academic_check?: AcademicCheck | null
  // Check-1 Pathway: the offer-letter facts (name + IC checks + data points). null
  // unless doc_type=offer_letter.
  pathway_check?: PathwayCheck | null
  // Check-1 Income: an earner IC's OCR'd values + the RELATIONSHIP verdict (does this
  // person link to the student's family). null unless doc_type=parent_ic.
  income_ic_check?: IncomeIcCheck | null
  // Check-1 Income: a member-tagged salary slip / EPF cross-checked against that member's
  // IC (name + IC number) + the income data points. null unless salary_slip/epf w/ member.
  income_proof_check?: IncomeProofCheck | null
  // Check-1 Income: the STR document — recipient vs the earner IC + currency. null unless str.
  str_check?: StrCheck | null
  // Check-1 Income: a utility bill — address (vs home) + monthly bill + unpaid balance.
  utility_check?: UtilityCheck | null
  // Check-1 Income: relationship proof checklists. null unless the matching doc type.
  bc_check?: BcCheck | null
  guardianship_check?: GuardianshipCheck | null
}

// The three AMBER buckets are the corroboration rules in `income_engine._combine_relationship`,
// and this type had drifted behind them: `check` / `check_near` (the name agrees, the NRIC does
// not — a misread digit off a security-printed JPN document) and, from BrightPath #19,
// `check_name` (the NRIC matches EXACTLY, the name is spelt differently — a transliteration, not
// a different person). All three render partial, never green and never red.
// `check_one` (#23): only ONE of the two cells was present at all, so half the row was
// checked. Amber — never green off a single piece of evidence, never red either.
type RelStatus = 'match' | 'mismatch' | 'no_ref' | 'check' | 'check_near' | 'check_name' | 'check_one'

export interface BcCheck {
  child_name: string
  child_status: RelStatus     // vs the student (you)
  mother_name: string
  mother_nric: string
  mother_status: RelStatus    // vs the mother's IC
  father_name: string
  father_status: RelStatus    // vs your IC patronymic
  bc_number: string
  // #23: the document is on file and is the right KIND, but nothing at all could be read off
  // it. The three statuses above are all `no_ref` in that case, which renders as three greys —
  // indistinguishable from a certificate that checked out. The surface draws one amber instead.
  unreadable?: boolean
}

export interface GuardianshipCheck {
  guardian_name: string
  guardian_nric: string
  guardian_status: RelStatus  // vs the guardian's IC
  ward_name: string
  ward_status: RelStatus      // vs the student (you)
  doc_kind: string
  unreadable?: boolean        // #23 — nothing read ≠ nothing wrong
}

// V1: the declared-income supporting doc — whether it READ as real evidence (officer chip).
// It names the EARNER, not the student, so there is no student name-match; the read is the signal.
export interface SupportDocCheck {
  name: string
  amount: string
  issuer: string
  kind: string
  read_status: 'read' | 'unread'
}

export interface StrCheck {
  name: string
  nric: string
  status: string
  year: string
  member: string
  // Household-level (owner 2026-07-07): 'match' iff the recipient's name/nric hits ANY
  // parent/guardian's IC (each field independently — see _str_recipient_household_match).
  name_status: 'match' | 'mismatch' | 'no_ref'
  nric_status: 'match' | 'mismatch' | 'no_ref'
  // 'current' = approved (Lulus/Diluluskan/Layak) AND a current year; 'stale' = older year;
  // 'rejected' = a clear negative status; 'unconfirmed' = no approval shown (e.g. a SALINAN
  // application record) or approval we can't tie to a current year — not proof on its own.
  // 'wrong_type' = the file is not an STR document at all; 'unreadable' = we could not read it.
  // The backend has always emitted both (verdict_engine.py) and officerCockpit.ts handles both;
  // only this union lagged, which the type check found on 2026-09-18 (TD-221).
  current_status: 'current' | 'stale' | 'rejected' | 'unconfirmed' | 'unknown' | 'wrong_type' | 'unreadable'
  ic_present: boolean
}

export interface IncomeIcCheck {
  nric: string
  name: string
  address: string
  member: string
  // RELATIONSHIP to the student (patronymic / birth cert / letter):
  // 'match' | 'mismatch' | 'unknown' (no patronymic / no member) | 'pending' (not read)
  name_status: 'match' | 'mismatch' | 'unknown' | 'pending'
  readable: boolean
  // Cross-check against the cluster's income proof (the reason the IC is uploaded): does this
  // IC's holder match the STR / salary slip? 'match' | 'mismatch' | 'no_ref' (no proof yet).
  proof_kind?: 'str' | 'salary_slip' | 'epf' | ''
  proof_name_status?: 'match' | 'mismatch' | 'no_ref'
  proof_nric_status?: 'match' | 'mismatch' | 'no_ref'
  // IC-NUMBER chain: the earner was confirmed by the BC's printed parent IC number matching the
  // income proof's number — so the earner is verified even when this card is the wrong family
  // member's. `wrong_card` = the chain held BUT the card here disagrees with the proof (a soft
  // caveat: "looks like a different family member's IC; we verified the earner another way").
  chain_verified?: boolean
  wrong_card?: boolean
  // The CLUSTER coach verdict for this member (relationship + coherence across their IC +
  // income proofs); '' when the cluster is consistent. Drives the single per-member coach.
  cluster_status?: string
}

export interface IncomeProofCheck {
  name: string
  nric: string
  // Data points shown on the card. Salary: amount + period. EPF: monthlyContribution +
  // totalAccumulated + year (so the lifetime balance is never read as monthly income).
  points: { key: string; value: string }[]
  member: string
  // vs the member's IC: 'match' | 'mismatch' | 'no_ref' (that member's IC not uploaded / not read)
  name_status: 'match' | 'mismatch' | 'no_ref'
  nric_status: 'match' | 'mismatch' | 'no_ref'
  ic_present: boolean
}

export interface UtilityCheck {
  name: string
  address: string
  monthly_bill: string
  unpaid_balance: string
  // vs the home address: 'found' | 'not_found' | 'unreadable' | '' (not run)
  address_status: string
  // bill date vs the review date, a 3-tier traffic light: 'current' (≤3 months) |
  // 'ageing' (3–6 months) | 'stale' (>6 months) | 'unknown' (no readable date)
  current_status: 'current' | 'ageing' | 'stale' | 'unknown'
  // the bill's point-in-time as a standardised 'MMM YYYY' (e.g. 'May 2026'), '' when undated
  bill_month: string
  // combined household per-capita B40 proxy (both bills): 'reasonable' (the normal case) |
  // 'high' (> RM60/head, officer signal) | 'partial' (only one bill) | 'unknown' (no data)
  reasonable_status: 'reasonable' | 'high' | 'partial' | 'unknown'
  // which bills informed the reasonable verdict
  reasonable_detail: 'both' | 'water_only' | 'electricity_only' | ''
  // 'arrears' when unpaid balance exceeds the current charge (hardship signal); '' = hide
  outstanding_status: 'arrears' | ''
  // 'unrelated' = bill in a name that is neither the student nor any uploaded parent IC
  name_note: 'unrelated' | ''
}

export type SlipCheckStatus = 'match' | 'partial' | 'mismatch' | 'unreadable' | 'uncertain' | 'pending'

export interface AcademicCheck {
  name: SlipCheckStatus
  subjects: SlipCheckStatus
  results: SlipCheckStatus
  candidate_name: string
  exam: string
  exam_year: string
  exam_year_status?: '' | 'current' | 'off'   // vs cohort year−1: current→green, off→amber
  missing: string[]
  mismatched: { subject: string; typed: string; slip: string }[]
  uncertain: { subject: string; typed: string; slip: string; band: string }[]
  slip_count: number
}

export interface SemesterCheck {
  name: string
  nric: string
  cgpa: string
  name_status: 'match' | 'partial' | 'mismatch' | 'no_ref'
  nric_status: 'match' | 'mismatch' | 'no_ref'
}

export interface SchoolLeavingCheck {
  school: string
  school_status: 'match' | 'partial' | 'mismatch' | 'no_ref'
  name: string
  name_status: 'match' | 'partial' | 'mismatch' | 'no_ref'
  nric: string
  nric_status: 'match' | 'mismatch' | 'no_ref'
  kelakuan: string
  kelakuan_status: 'good' | 'concern' | 'bad' | 'unknown'
  activities: string
}

export interface PathwayCheck {
  name: SlipCheckStatus
  ic: SlipCheckStatus
  candidate_name: string
  candidate_nric: string
  programme: string
  institution: string
  issuer: string
  offer_date: string
  intake: string
  reporting_date?: string                 // report/registration date = course start
  reporting_official?: boolean            // validated official registration summons (the bonus)
  intake_year?: string                    // parsed course-start year
  intake_year_status?: '' | 'current' | 'off'   // vs cohort year: current→green, off→amber
  address: string
  // Offer-vs-declared reconciliation (Check-1 pathway): does the offer match the
  // college/programme the student declared at apply time?
  pathway?: 'match' | 'mismatch' | 'unknown'
  // The institution dimension on its own — drives the cockpit's Pre-U Institution verified tick.
  institution_status?: 'match' | 'clash' | 'unknown'
  // The offer institution vs the SHOWN chosen_programme.institution — drives the TERTIARY
  // (poly / UA diploma / asasi / PISMP) Institution tick, where pre_u_institution is blank.
  chosen_institution_status?: 'match' | 'clash' | 'unknown'
  declared_programme?: string
  declared_institution?: string
  // The course-switch note: set on the LIVE offer when it replaced a genuinely different prior
  // offer (any→any). Null when there was no switch. Surfaced even after the student confirms.
  switched_from?: { programme: string; institution: string } | null
}

export interface Referee {
  id: number
  name: string
  role: string
  relationship: string
  phone: string
  email: string
}

export interface ConsentStatus {
  is_minor: boolean
  consent_version: string
  consents: {
    id: number
    consent_type: string
    version: string
    granted_by: string
    guardian_name: string
    guardian_relationship: string
    guardian_nric: string
    is_active: boolean
    granted_at: string
  }[]
  // S19 — student context for parent-voice consent text interpolation.
  student_name: string
  student_nric: string
  student_gender: '' | 'male' | 'female'   // '' when NRIC unparseable; FE falls back to neutral pronoun
  // S19 — parent_ic Vision OCR values for the FE's live name+NRIC mismatch check.
  // Empty strings when parent_ic not uploaded yet or OCR hasn't run.
  parent_ic_vision_nric: string
  parent_ic_vision_name: string
  // Every unmet precondition for giving consent (empty = ready). Consent is the
  // final step: profile complete + required documents uploaded + the uploaded IC
  // readable and matching the student's name/NRIC. The FE renders these as a
  // checklist and keeps the consent button disabled until the list is empty.
  blockers: string[]
}

export async function signUploadDocument(
  docType: string,
  options?: ApiOptions
): Promise<{ upload_url: string; storage_path: string; doc_type: string }> {
  return apiRequest('/api/v1/scholarship/documents/sign-upload/', {
    method: 'POST',
    body: JSON.stringify({ doc_type: docType }),
    ...options,
  })
}

/** Direct PUT of the file bytes to the signed Supabase Storage URL (not our API). */
export async function uploadFileToSignedUrl(uploadUrl: string, file: File): Promise<void> {
  const resp = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': file.type || 'application/octet-stream', 'x-upsert': 'true' },
  })
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`)
}

export async function recordDocument(
  payload: { doc_type: string; storage_path: string; household_member?: string; request_code?: string; original_filename?: string; content_type?: string; size?: number },
  options?: ApiOptions
): Promise<ApplicantDocument & { match_verdict?: 'ok' | 'mismatch' | 'unreadable' | 'pending' | 'insufficient' }> {
  return apiRequest('/api/v1/scholarship/documents/', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...options,
  })
}

/** The organisation's upload limits, SERVED with the document list (Org Config Sprint E).
 *  Optional so a payload cached from an older build still types — read them through
 *  `documentLimits.limitsFrom`, which falls back per field. */
export interface DocumentLimits {
  max_doc_size_mb?: number
  max_docs_per_application?: number
  max_other_docs?: number
}

export async function listDocuments(
  options?: ApiOptions,
): Promise<{ documents: ApplicantDocument[]; limits?: DocumentLimits }> {
  return apiRequest('/api/v1/scholarship/documents/', options)
}

export async function deleteDocument(id: number, options?: ApiOptions): Promise<{ status: string }> {
  return apiRequest(`/api/v1/scholarship/documents/${id}/`, { method: 'DELETE', ...options })
}

// "Cikgu Gopal" document-help coach. `source`: 'ai' = warm Gemini message;
// 'fallback' = AI off/throttled → show pre-written i18n copy keyed by `verdict`;
// 'none' = nothing to help with (good/unchecked doc). Soft, never blocks.
export interface GradeDiff {
  subject: string
  typed: string
  slip: string
}

export interface DocumentHelp {
  message: string
  source: 'ai' | 'fallback' | 'none'
  verdict?: string
  model_used?: string
  /** For a slip grade mismatch: the exact subject(s) that differ, so the coach can name them. */
  grade_diffs?: GradeDiff[]
}

export async function getDocumentHelp(
  id: number,
  lang?: string,
  options?: ApiOptions
): Promise<DocumentHelp> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : ''
  return apiRequest(`/api/v1/scholarship/documents/${id}/help/${q}`, options)
}

// The single per-earner income-cluster coach (one Gopal for the whole cluster: the earner's
// IC + STR / payslip + relationship doc). Same shape as the per-document helper.
export async function getIncomeHelp(
  member: string,
  lang?: string,
  options?: ApiOptions
): Promise<DocumentHelp> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : ''
  return apiRequest(`/api/v1/scholarship/income/${encodeURIComponent(member)}/help/${q}`, options)
}

export async function listReferees(options?: ApiOptions): Promise<{ referees: Referee[] }> {
  return apiRequest('/api/v1/scholarship/referees/', options)
}

export async function addReferee(payload: Partial<Referee>, options?: ApiOptions): Promise<Referee> {
  return apiRequest('/api/v1/scholarship/referees/', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...options,
  })
}

export async function getConsentStatus(options?: ApiOptions): Promise<ConsentStatus> {
  return apiRequest('/api/v1/scholarship/consent/', options)
}

export async function recordConsent(
  payload: {
    consent_type?: string; locale?: string; granted_by?: string;
    guardian_name?: string; guardian_relationship?: string;
    // S19 — typed NRIC; validated against parent_ic Vision OCR at the view layer.
    guardian_nric?: string;
  },
  options?: ApiOptions
): Promise<unknown> {
  return apiRequest('/api/v1/scholarship/consent/', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...options,
  })
}

