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
