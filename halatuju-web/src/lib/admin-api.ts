/**
 * Admin API client for partner organisations.
 *
 * All endpoints require Supabase auth and return 403 if the user
 * is not a partner admin.
 */

import type {
  AcademicCheck, PathwayCheck, IncomeIcCheck, IncomeProofCheck,
  StrCheck, UtilityCheck, BcCheck, GuardianshipCheck,
} from '@/lib/api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ApiOptions {
  token?: string
}

async function adminFetch<T>(path: string, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Admin API error: ${res.status}`)
  }

  return res.json()
}

// ── Types ────────────────────────────────────────────────────────────

export interface DashboardData {
  org_name: string
  org_code: string | null
  total_students: number
  completed_onboarding: number
  by_exam_type: Record<string, number>
  top_fields: Array<{ field: string; count: number }>
}

export interface StudentListItem {
  supabase_user_id: string
  name: string
  nric: string
  gender: string
  exam_type: string
  school: string
  contact_phone: string
  referral_source: string | null
  org_name: string | null
  created_at: string
}

export interface StudentListData {
  org_name: string
  count: number
  students: StudentListItem[]
}

export interface StudentDetailData {
  supabase_user_id: string
  name: string
  nric: string
  angka_giliran: string
  gender: string
  nationality: string
  contact_phone: string
  address: string
  postal_code: string
  city: string
  school: string
  household_income: number | null
  household_size: number | null
  colorblind: string
  disability: string
  exam_type: string
  grades: Record<string, string>
  stpm_grades: Record<string, string>
  stpm_cgpa: number | null
  muet_band: number | null
  student_signals: Record<string, unknown>
  preferred_state: string
  financial_pressure: string
  travel_willingness: string
  referral_source: string | null
  org_name: string | null
  created_at: string
  saved_courses: Array<{ course_id: string; name: string }>
}

// ── API functions ────────────────────────────────────────────────────

export async function getPartnerDashboard(options?: ApiOptions) {
  return adminFetch<DashboardData>('/api/v1/admin/dashboard/', options)
}

export async function getPartnerStudents(options?: ApiOptions) {
  return adminFetch<StudentListData>('/api/v1/admin/students/', options)
}

export async function getPartnerStudent(userId: string, options?: ApiOptions) {
  return adminFetch<StudentDetailData>(
    `/api/v1/admin/students/${userId}/`,
    options
  )
}

export function getExportUrl() {
  return `${API_BASE}/api/v1/admin/students/export/`
}

export async function deleteStudent(userId: string, options?: ApiOptions) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/students/${userId}/`, {
    method: 'DELETE',
    headers,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Delete failed: ${res.status}`)
  }

  return res.json()
}

// ── Admin management ────────────────────────────────────────────────

export interface AdminItem {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  is_active: boolean
  org_name: string | null
  created_at: string
}

export async function getAdmins(options?: ApiOptions) {
  return adminFetch<{ admins: AdminItem[] }>('/api/v1/admin/admins/', options)
}

export async function revokeAdmin(adminId: number, action: 'revoke' | 'restore', options?: ApiOptions) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/admins/${adminId}/revoke/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ action }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Action failed: ${res.status}`)
  }
  return res.json()
}

// ── Admin profile ───────────────────────────────────────────────────

export interface AdminProfile {
  id: number
  name: string
  email: string
  is_super_admin: boolean
  org_name: string | null
  org_contact_person: string | null
  org_phone: string | null
}

export async function getAdminProfile(options?: ApiOptions) {
  return adminFetch<AdminProfile>('/api/v1/admin/profile/', options)
}

export async function updateAdminProfile(
  data: { name?: string; org_contact_person?: string; org_phone?: string },
  options?: ApiOptions
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/profile/`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Update failed: ${res.status}`)
  }
  return res.json()
}

// ── Reviewer profile (F6) ───────────────────────────────────────────
// A reviewer's own credentials + contact details. Self-scoped endpoint
// (always the calling admin's own row). phone/address are private staff
// PII — reviewer + super only, never exposed to students/sponsors.

export interface ReviewerProfile {
  highest_qualification: string
  university: string
  graduation_year: number | null
  field_of_study: string
  phone: string
  address: string
}

export async function getReviewerProfile(options?: ApiOptions) {
  return adminFetch<ReviewerProfile>('/api/v1/admin/reviewer-profile/', options)
}

export async function updateReviewerProfile(
  data: Partial<ReviewerProfile>,
  options?: ApiOptions
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}/api/v1/admin/reviewer-profile/`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Update failed: ${res.status}`)
  }
  return res.json() as Promise<ReviewerProfile>
}

// ── Invite / Orgs ───────────────────────────────────────────────────

export interface OrgItem {
  id: number
  code: string
  name: string
  contact_person: string
  phone: string
}

export async function getOrgs(options?: ApiOptions) {
  return adminFetch<{ orgs: OrgItem[] }>('/api/v1/admin/orgs/', options)
}

export async function inviteAdmin(
  data: {
    email: string
    name: string
    org_id?: number
    new_org_name?: string
    new_org_code?: string
    contact_person?: string
    org_phone?: string
  },
  options?: ApiOptions
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/invite/`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Invite failed: ${res.status}`)
  }

  return res.json()
}

// ── Scholarship (B40 Assistance Programme) ──────────────────────────────

export interface AdminScholarshipListItem {
  id: number
  name: string
  profile_id: string | null
  cohort_code: string
  qualification: string
  spm_a_count: number | null
  stpm_pngk: number | null
  status: string
  bucket: string
  shortlist_reason: string
  submitted_at: string
  profile_completed_at: string | null
  assigned_to_id: number | null
  assigned_to_name: string | null
}

export interface AdminCompleteness {
  quiz_done: boolean
  details_done: boolean
  funding_done: boolean
  documents_done: boolean
  consent_done: boolean
  address_done: boolean
  guardian_docs_done: boolean
  family_done: boolean
  complete: boolean
}

export interface AdminInterviewSession {
  id: number
  status: 'draft' | 'submitted'
  findings: Record<string, { verdict: string; rationale: string }>
  rubric: Record<string, number>
  overall_note: string
  interviewer_name: string | null
  started_at: string | null
  submitted_at: string | null
  updated_at: string
}

export interface AdminSponsorProfile {
  draft_markdown: string
  edited_markdown: string
  current_markdown: string
  status: string
  model_used: string
  generated_at: string | null
  published_at: string | null
  updated_at: string
  // Phase D — the "v2" profile refined with interview findings (admin-facing for now).
  final_markdown: string
  final_model_used: string
  finalised_at: string | null
  // Phase E2 — the ANONYMOUS, sponsor-pool-facing profile (generate -> publish).
  anon_markdown: string
  anon_model_used: string
  anon_generated_at: string | null
  anon_published: boolean
  anon_published_at: string | null
}

export interface AdminScholarshipDetail {
  id: number
  name: string
  school: string
  nric: string
  nric_verified: boolean
  mentoring_candidate: boolean
  verified_at: string | null
  verified_by: string
  verify_checklist: Record<string, boolean>
  profile_id: string | null
  // S13: typed-name signature captured at submit (used as a comparison against Vision-read IC name)
  declaration_name: string
  qualification: string
  spm_a_count: number | null
  merit_score: number | null
  stpm_pngk: number | null
  household_income: number | null
  household_size: number | null
  receives_str: boolean
  // Income wizard answers — drive the cockpit's route-aware income document panel.
  income_route?: string | null
  income_earner?: string | null
  income_working_members?: string[] | null
  receives_jkm: boolean
  intended_pathway: string
  intends_tertiary_2026: boolean
  aspirations: string
  plans: string
  fears: string
  justification: string
  // Profile-derived address (post-S14) — used by the admin Vision card to
  // cross-check what the student typed against the MyKad-read vision_address.
  address: string
  // Complete-profile view: contact + family + academic detail (profile-sourced)
  postal_code: string
  city: string
  preferred_state: string
  contact_phone: string
  contact_email: string
  notify_email: string
  verified_email: string
  preferred_call_language: string
  referral_source: string | null
  guardians: Array<{ name?: string; phone?: string; relationship?: string }>
  muet_band: number | null
  coq_score: number | null
  grades: Record<string, string>
  stpm_grades: Record<string, string>
  spm_prereq_grades: Record<string, string>
  // "Your story" narrative (S2) + support + declaration
  first_in_family: boolean
  parents_occupation: string
  siblings_studying_count: number | null
  // P2 (Check 2): the school/tertiary split — the family-burden breakdown
  siblings_in_school: number | null
  siblings_in_tertiary: number | null
  family_context: string
  daily_life: string
  consent_to_contact: boolean
  declared_at: string | null
  // My Plans + My Support intake (were exposed by the serializer; now typed)
  pathway_certainty: string
  chosen_pathway: string
  chosen_programme: Record<string, unknown> | null
  pre_u_track: string
  pre_u_institution: string
  uncertainty_reasons: string[]
  uncertainty_note: string
  pathways_considered: string[]
  top_choices: Array<{ rank: number; course_id: string; course_name: string; institution: string }>
  upu_status: string
  field_of_study: string
  other_scholarships: string[]
  other_scholarships_text: string
  help_university: string
  help_scholarship: string
  anything_else: string
  status: string
  bucket: string
  shortlist_reason: string
  // Rejection bucket: '' | 'merit' | 'need' | 'ineligible' | 'interview' | 'contractual'
  rejection_category: string
  rejected_at: string | null
  rejected_by: string
  submitted_at: string
  funding_need: { categories: string[]; funding_note: string; programme_months: number | null } | null
  // S16 Phase A: deterministic pre-interview flag list. {code, params}; the
  // frontend resolves human copy from its i18n bundle (no server-side copy).
  anomalies: AdminAnomaly[]
  // S1 verification verdict: the four-fact rollup the coordinator audits.
  verdict: AdminVerdictFact[]
  // Check 2 STEP 1: the deterministic submission review — the facts ledger (claims +
  // how well each is backed), fundable-profile gaps, and consistency flags. Pure rules.
  submission_review: AdminSubmissionReview
  // Check 2 STEP 2/3: the query SLA clock + assignment readiness.
  query_sla: AdminQuerySla
  // Check 2: per-pathway funding-need estimate (the gap after govt coverage) for award sizing.
  funding_estimate: AdminFundingEstimate
  // Phase B: Gemini-suggested interview gaps. Carry their OWN dynamic text
  // (unlike anomalies which i18n by code). Empty until the admin generates them.
  interview_gaps: Array<{ code: string; question: string; why: string }>
  interview_gaps_run_at: string | null
  documents: AdminApplicantDocument[]
  referees: AdminReferee[]
  consents: Array<{ id: number; consent_type: string; version: string; granted_by: string; guardian_name: string; is_active: boolean; granted_at: string }>
  sponsor_profile: AdminSponsorProfile | null
  // Phase C
  profile_completed_at: string | null
  completeness: AdminCompleteness
  interview_session: AdminInterviewSession | null
  assigned_to_id: number | null
  assigned_to_name: string | null
  info_request_note: string
  info_requested_at: string | null
  // Sprint 5 — Verification verdict cockpit fields
  ai_verdict_snapshot: AdminVerdictFact[]
  officer_verdict: {
    identity?: string
    academic?: string
    income?: string
    pathway?: string
    overall?: string
  }
  verdict_reason: string
  verdict_decided_by: string
  verdict_decided_at: string | null
  resolution_items: AdminResolutionItem[]
}

/** Admin-facing resolution item. Mirrors the student-facing ResolutionItem in
 *  src/lib/api.ts but kept separate — do not cross-import. */
export interface AdminResolutionItem {
  id: number
  fact: string
  code: string
  params: Record<string, string | number | string[]>
  prompt: string
  kind: 'doc' | 'confirm' | 'explanation'
  doc_type: string
  status: string
  source: 'system' | 'officer'
  resolution_text: string
  created_at: string
  resolved_at: string | null
}

/** Verdict metrics summary returned by GET /verdict-metrics/. */
export interface VerdictMetrics {
  applications: number
  fact_decisions: number
  overrides: number
  override_rate: number
  per_fact: Record<string, { decided: number; overrides: number }>
}

async function adminMutate<T>(path: string, method: string, body: unknown, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method, headers, body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    throw new Error(b.error || `Admin API error: ${res.status}`)
  }
  return res.json()
}

export async function getScholarshipApplications(
  filters: { status?: string; bucket?: string; assigned?: string } = {},
  options?: ApiOptions
) {
  const q = new URLSearchParams()
  if (filters.status) q.set('status', filters.status)
  if (filters.bucket) q.set('bucket', filters.bucket)
  if (filters.assigned) q.set('assigned', filters.assigned)
  const qs = q.toString()
  return adminFetch<{ applications: AdminScholarshipListItem[]; total_count: number }>(
    `/api/v1/admin/scholarship/applications/${qs ? `?${qs}` : ''}`, options
  )
}

// ── Phase C: assignment, interview capture, request-more-docs ───────────────

/** Assign (or unassign with null) a reviewer to an application. */
export async function assignApplication(id: number, adminId: number | null, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/`, 'PATCH', { assigned_to: adminId }, options)
}

export async function getInterview(id: number, options?: ApiOptions) {
  return adminFetch<{ session: AdminInterviewSession | null; agenda: string[] }>(
    `/api/v1/admin/scholarship/applications/${id}/interview/`, options)
}

export async function saveInterview(
  id: number,
  payload: { findings: Record<string, { verdict: string; rationale: string }>; rubric: Record<string, number>; overall_note: string },
  options?: ApiOptions,
) {
  return adminMutate<AdminInterviewSession>(
    `/api/v1/admin/scholarship/applications/${id}/interview/`, 'POST', payload, options)
}

export async function submitInterview(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/interview/submit/`, 'POST', {}, options)
}

export async function requestMoreInfo(id: number, note: string, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/request-info/`, 'POST', { note }, options)
}

/** Active admins (for the assignment dropdown). Super admin only on the backend. */
export async function getAssignableAdmins(options?: ApiOptions) {
  return adminFetch<{ admins: Array<{ id: number; name: string; email: string; role: string }> }>(
    `/api/v1/admin/scholarship/assignable-admins/`, options)
}

export async function getScholarshipApplication(id: number, options?: ApiOptions) {
  return adminFetch<AdminScholarshipDetail>(`/api/v1/admin/scholarship/applications/${id}/`, options)
}

/** Generate the AI draft. `language` ('en'/'ms') sets the output language; defaults to the applicant's locale. */
export async function generateSponsorProfile(id: number, language?: string, options?: ApiOptions) {
  return adminMutate<AdminSponsorProfile>(
    `/api/v1/admin/scholarship/applications/${id}/generate-profile/`, 'POST',
    language ? { language } : {}, options
  )
}

/** Phase D: refine the draft profile with the submitted interview's findings (second Gemini pass). */
export async function finaliseSponsorProfile(id: number, language?: string, options?: ApiOptions) {
  return adminMutate<AdminSponsorProfile>(
    `/api/v1/admin/scholarship/applications/${id}/finalise-profile/`, 'POST',
    language ? { language } : {}, options
  )
}

/** Phase B: admin-on-demand Gemini interview gap-spotter. Returns the refreshed detail. */
export async function suggestInterviewGaps(id: number, language?: string, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/suggest-gaps/`, 'POST',
    language ? { language } : {}, options
  )
}

export async function saveSponsorProfile(
  id: number, payload: { edited_markdown: string; status?: string }, options?: ApiOptions
) {
  return adminMutate<AdminSponsorProfile>(
    `/api/v1/admin/scholarship/applications/${id}/profile/`, 'PUT', payload, options
  )
}

export async function publishSponsorProfile(id: number, options?: ApiOptions) {
  return adminMutate<AdminSponsorProfile>(
    `/api/v1/admin/scholarship/applications/${id}/publish/`, 'POST', {}, options
  )
}

/** Phase E2: generate the ANONYMOUS sponsor-pool profile (non-identifying inputs only). */
export async function generateAnonProfile(id: number, language?: string, options?: ApiOptions) {
  return adminMutate<AdminSponsorProfile>(
    `/api/v1/admin/scholarship/applications/${id}/anon-profile/generate/`, 'POST',
    language ? { language } : {}, options
  )
}

/** Phase E2: publish (or unpublish) the anonymous profile to the sponsor pool. */
export async function publishAnonProfile(id: number, publish: boolean, options?: ApiOptions) {
  return adminMutate<AdminSponsorProfile>(
    `/api/v1/admin/scholarship/applications/${id}/anon-profile/publish/`, 'POST', { publish }, options
  )
}

/** Post-shortlist admin rejection. category: 'interview' (reviewed, not selected — from
 * shortlisted onward) or 'contractual' (failed post-award steps — from accepted). Sends the
 * bucket's decline email. */
export async function rejectApplication(
  id: number, category: 'interview' | 'contractual', options?: ApiOptions
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/reject/`, 'POST', { category }, options
  )
}

/** Verify the checklist + accept: sets nric_verified (locks NRIC), advances → accepted. */
export async function verifyAcceptApplication(
  id: number, checklist: Record<string, boolean>, options?: ApiOptions
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/verify-accept/`, 'POST', { checklist }, options
  )
}

/** Toggle the coordinator-facing mentoring-candidate flag. */
export async function setMentoringCandidate(id: number, value: boolean, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/`, 'PATCH', { mentoring_candidate: value }, options
  )
}

/** S16 Phase A: deterministic pre-interview flag (anomaly engine). The `code`
 *  resolves to two i18n keys: `scholarship.admin.anomaly.{code}.fact` (the
 *  observed inconsistency, with `params` interpolated) and `.question` (the
 *  suggested interview question). */
export interface AdminAnomaly {
  code: string
  params: Record<string, string | number>
}

/** S1 verification verdict. One of four facts the coordinator AUDITS (does not
 *  assemble). Each evidence/unresolved item's `code` resolves to
 *  `admin.scholarship.verdict.item.{code}` in i18n (params interpolate).
 *  status: verified (green, AI asserts) · review (amber, confirm) ·
 *  recommend (blue, a human places the verdict) · gap (red, action needed). */
export interface AdminVerdictItem {
  // string[] supports the income reason codes' `members` list (e.g. ['father','brother']).
  code: string
  params: Record<string, string | number | string[]>
}
export interface AdminVerdictFact {
  fact: 'identity' | 'academic' | 'income' | 'pathway'
  status: 'verified' | 'review' | 'recommend' | 'gap'
  evidence: AdminVerdictItem[]
  unresolved: AdminVerdictItem[]
}

/** Check 2 STEP 1 — the deterministic submission review. */
export interface AdminLedgerRow {
  claim: string
  value: string
  source: string
  // verified (assert as fact) · reported (self-reported / under review) ·
  // student_words (their voice) · unverified (omit or hedge).
  verification: 'verified' | 'reported' | 'student_words' | 'unverified'
}
export interface AdminSubmissionReview {
  ledger: AdminLedgerRow[]
  completeness: Array<{ code: string }>
  consistency: AdminAnomaly[]
}

/** Check 2 — per-pathway funding-need estimate (RM [low, high]). */
export interface AdminFundingEstimate {
  pathway: string            // 'matrik' | 'asasi' | 'stpm' | 'poly_diploma' | 'pismp' | 'degree' | 'unknown'
  known: boolean             // false for an unknown pathway → no estimate, fall back to self-report
  review: boolean            // estimate too variable to trust without an officer (e.g. degree)
  monthly: Record<string, [number, number]>
  monthly_total: [number, number]
  one_off: Record<string, [number, number]>
  one_off_total: [number, number]
  programme_months: number | null
  total: [number, number]    // monthly_total × months (or 12) + one_off_total
  covered: string[]          // what government already covers
}

/** Check 2 STEP 2/3 — the query SLA clock for the cockpit. */
export interface AdminQuerySla {
  deadline: string | null
  lapsed: boolean
  open_count: number
  days_left: number | null
  ready_for_assignment: boolean
  // true when the app is proceeding to assignment WITH clarify queries still open
  // (the SLA lapsed) — the 'ready-with-open-queries' reviewer flag.
  proceeding_with_open_queries: boolean
}

export interface AdminApplicantDocument {
  id: number
  doc_type: string
  // Salary-route income docs: whose IC/salary slip/EPF this is (father/mother/…); '' otherwise.
  household_member?: string
  original_filename: string
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

// ── Sprint 5: Officer verdict + caveats ─────────────────────────────────────

export interface RecordVerdictPayload {
  officer_verdict: {
    identity?: string
    academic?: string
    income?: string
    pathway?: string
    overall?: string
  }
  reason?: string
  finalise?: boolean
  language?: string
}

export interface RecordVerdictResult extends AdminScholarshipDetail {
  finalise_result: { ok: boolean; code?: string } | null
}

/** Record the coordinator's verdict. May also trigger a final-profile
 *  generation when `finalise: true` is passed. */
export async function recordVerdict(
  id: number,
  payload: RecordVerdictPayload,
  options?: ApiOptions,
): Promise<RecordVerdictResult> {
  return adminMutate<RecordVerdictResult>(
    `/api/v1/admin/scholarship/applications/${id}/record-verdict/`,
    'POST',
    payload,
    options,
  )
}

/** Aggregate override-rate metrics for the verdict engine.
 *  `cohort` is optional; omit to get the cross-cohort totals. */
export async function getVerdictMetrics(
  options?: ApiOptions,
  cohort?: string,
): Promise<VerdictMetrics> {
  const qs = cohort ? `?cohort=${encodeURIComponent(cohort)}` : ''
  return adminFetch<VerdictMetrics>(
    `/api/v1/admin/scholarship/verdict-metrics/${qs}`,
    options,
  )
}

/** Coordinator raises a new resolution item (free-text or doc request) for the
 *  student's Action Centre. */
export async function raiseResolutionItem(
  id: number,
  payload: { kind: 'doc' | 'confirm' | 'explanation'; prompt: string; doc_type?: string; fact?: string },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/resolution-items/`,
    'POST',
    payload,
    options,
  )
}

/** Waive or resolve a resolution item on behalf of the coordinator. */
export async function actionResolutionItem(
  itemId: number,
  action: 'waive' | 'resolve',
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/resolution-items/${itemId}/${action}/`,
    'POST',
    {},
    options,
  )
}

// ── Phase E: sponsor account vetting ──
export interface AdminSponsor {
  id: number
  name: string
  email: string
  phone: string
  source: string
  organisation: string
  note: string
  status: 'pending' | 'approved' | 'rejected' | 'suspended'
  reviewed_at: string | null
  reviewed_by: string
  created_at: string
}

export async function listSponsors(status?: string, options?: ApiOptions): Promise<{ sponsors: AdminSponsor[] }> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return adminFetch(`/api/v1/admin/sponsors/${q}`, options)
}

export async function reviewSponsor(
  id: number, action: 'approve' | 'reject' | 'suspend', options?: ApiOptions
): Promise<AdminSponsor> {
  return adminMutate(`/api/v1/admin/sponsors/${id}/review/`, 'POST', { action }, options)
}
