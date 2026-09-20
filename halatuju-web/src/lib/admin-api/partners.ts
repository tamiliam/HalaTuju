/**
 * The partner organisation's own screens: its dashboard, its student list and detail, the
 * CSV export, and deleting a student.
 */
import { API_BASE, adminFetch } from './client'
import type { ApiOptions } from './client'

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
  owning_org_name?: string | null
  created_at: string
}

export interface StudentListData {
  org_name: string
  is_super_admin: boolean
  count: number
  total_pages: number
  page: number
  page_size: number
  next: string | null
  previous: string | null
  students: StudentListItem[]
  /** Distinct referral_source values across the admin's visible set, for the Source filter. */
  source_options: string[]
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

export const DEFAULT_ADMIN_PAGE_SIZE = 25

export async function getPartnerStudents(
  params?: { page?: number; pageSize?: number; q?: string; exam?: string; source?: string },
  options?: ApiOptions,
) {
  const qs = new URLSearchParams()
  if (params?.page && params.page > 1) qs.set('page', String(params.page))
  if (params?.pageSize && params.pageSize !== DEFAULT_ADMIN_PAGE_SIZE) {
    qs.set('page_size', String(params.pageSize))
  }
  if (params?.q) qs.set('q', params.q)
  if (params?.exam) qs.set('exam', params.exam)
  if (params?.source) qs.set('source', params.source)
  const query = qs.toString()
  return adminFetch<StudentListData>(
    `/api/v1/admin/students/${query ? `?${query}` : ''}`,
    options,
  )
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

