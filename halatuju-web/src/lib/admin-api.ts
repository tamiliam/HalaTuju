/**
 * Admin API client for partner organisations.
 *
 * All endpoints require Supabase auth and return 403 if the user
 * is not a partner admin.
 */

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
  submitted_at: string
  funding_need: { categories: string[]; funding_note: string; programme_months: number | null } | null
  // S16 Phase A: deterministic pre-interview flag list. {code, params}; the
  // frontend resolves human copy from its i18n bundle (no server-side copy).
  anomalies: AdminAnomaly[]
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

export interface AdminApplicantDocument {
  id: number
  doc_type: string
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
