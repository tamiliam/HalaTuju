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
  phone: string
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
  phone: string
  address: string
  postal_code: string
  city: string
  school: string
  family_income: string
  siblings: number | null
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
  qualification: string
  spm_a_count: number | null
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
  status: string
  bucket: string
  shortlist_reason: string
  submitted_at: string
  funding_need: { categories: string[]; funding_note: string; programme_months: number | null } | null
  documents: Array<{ id: number; doc_type: string; original_filename: string; size: number; verification_status: string; download_url: string | null }>
  referees: AdminReferee[]
  consents: Array<{ id: number; consent_type: string; version: string; granted_by: string; guardian_name: string; is_active: boolean; granted_at: string }>
  sponsor_profile: AdminSponsorProfile | null
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
  filters: { status?: string; bucket?: string } = {},
  options?: ApiOptions
) {
  const q = new URLSearchParams()
  if (filters.status) q.set('status', filters.status)
  if (filters.bucket) q.set('bucket', filters.bucket)
  const qs = q.toString()
  return adminFetch<{ applications: AdminScholarshipListItem[]; total_count: number }>(
    `/api/v1/admin/scholarship/applications/${qs ? `?${qs}` : ''}`, options
  )
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
