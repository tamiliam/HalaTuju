/**
 * The course catalogue: search, eligibility, institutions, and a student's saved list.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'
import type { StudentProfile } from './profile'

export interface EligibleCourse {
  course_id: string
  course_name: string
  level: string
  field: string // Legacy — use field_key instead
  field_key?: string
  source_type: string
  pathway_type?: string
  qualification?: 'SPM' | 'STPM'
  merit_cutoff: number | null
  student_merit: number | null
  merit_label: string | null
  merit_color: string | null
  merit_display_student?: string
  merit_display_cutoff?: string
  institution_name?: string
  institution_count?: number
  institution_state?: string
  pismp_languages?: string[]
  aliran?: string // PISMP only — school type (sk/sjkc/sjkt/khas) for the Aliran→Bidang picker
}

export interface Course {
  course_id: string
  course: string
  level: string
  department: string
  field: string // Legacy — use field_key instead
  field_key?: string
  headline: string
  headline_en: string
  description: string
  description_en: string
  wbl: boolean
  semesters: number
}

export interface Institution {
  institution_id: string
  institution_name: string
  acronym: string
  type: string
  category: string
  state: string
  url?: string
  // Per-offering details (from CourseInstitution)
  hyperlink?: string
  tuition_fee_semester?: string
  hostel_fee_semester?: string
  registration_fee?: string
  monthly_allowance?: number | null
  practical_allowance?: number | null
  free_hostel?: boolean
  free_meals?: boolean
}

export interface MascoOccupation {
  masco_code: string
  job_title: string
  emasco_url: string
}

export interface CourseRequirements {
  source_type: string
  general: { key: string; label: string; value?: number }[]
  special: { key: string; label: string }[]
  complex_requirements: { or_groups?: { count: number; grade: string; subjects: string[] }[] } | null
  subject_group_req: { min_grade: string; min_count: number; subjects: string[] }[] | null
  merit_cutoff: number | null
  remarks: string
  pismp_languages?: string[]
}

// Insights from eligibility analysis
export interface InsightsStreamItem {
  source_type: string
  label: string
  count: number
}

export interface InsightsFieldItem {
  field: string
  count: number
}

export interface InsightsLevelItem {
  level: string
  count: number
}

export interface Insights {
  stream_breakdown: InsightsStreamItem[]
  top_fields: InsightsFieldItem[]
  level_distribution: InsightsLevelItem[]
  merit_summary: { high: number; fair: number; low: number; no_data: number }
  summary_text: string
}

// Search/browse types
export interface SearchCourse {
  course_id: string
  course_name: string
  level: string
  field: string // Legacy — use field_key instead
  field_key?: string
  source_type: string
  pathway_type?: string
  merit_cutoff: number | null
  institution_count: number
  institution_name: string
  institution_state: string
  qualification: 'SPM' | 'STPM'
  aliran?: string | null // PISMP school type (sk|sjkc|sjkt|khas); null for non-PISMP
  is_elektif?: boolean // PISMP elektif (minor) variant rather than a bidang (major)
}

export interface AliranOption {
  value: string
  label: string
}

export interface SearchFilters {
  levels: string[]
  fields: string[]
  source_types: string[]
  states: string[]
  qualifications: string[]
  alirans?: AliranOption[]
}

export interface SearchParams {
  q?: string
  level?: string
  field_key?: string
  source_type?: string
  state?: string
  qualification?: string
  aliran?: string
  limit?: number
  offset?: number
}

export async function searchCourses(
  params: SearchParams = {},
  options?: ApiOptions
): Promise<{ courses: SearchCourse[]; total_count: number; filters: SearchFilters }> {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.level) query.set('level', params.level)
  if (params.field_key) query.set('field_key', params.field_key)
  if (params.source_type) query.set('source_type', params.source_type)
  if (params.state) query.set('state', params.state)
  if (params.qualification) query.set('qualification', params.qualification)
  if (params.aliran) query.set('aliran', params.aliran)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiRequest(`/api/v1/courses/search/${qs ? `?${qs}` : ''}`, options)
}

// API Functions
export async function checkEligibility(
  profile: StudentProfile,
  options?: ApiOptions
): Promise<{ eligible_courses: EligibleCourse[]; stats: Record<string, number>; pathway_stats: Record<string, number>; insights: Insights }> {
  return apiRequest('/api/v1/eligibility/check/', {
    method: 'POST',
    body: JSON.stringify(profile),
    ...options,
  })
}

export async function getCourses(options?: ApiOptions): Promise<{ courses: Course[] }> {
  return apiRequest('/api/v1/courses/', options)
}

export async function getCourse(
  courseId: string,
  options?: ApiOptions
): Promise<{ course: Course; institutions: Institution[]; career_occupations: MascoOccupation[]; requirements: CourseRequirements | null; merit_cutoff?: number; merit_type?: string }> {
  return apiRequest(`/api/v1/courses/${courseId}/`, options)
}

export async function getInstitutions(options?: ApiOptions): Promise<{ institutions: Institution[] }> {
  return apiRequest('/api/v1/institutions/', options)
}

export interface SavedCourseWithStatus extends Course {
  interest_status: string
  course_type: 'spm' | 'stpm'
  institution_name?: string
}

export async function getSavedCourses(options?: ApiOptions & { qualification?: 'SPM' | 'STPM' }): Promise<{ saved_courses: SavedCourseWithStatus[] }> {
  const qualification = options?.qualification
  const url = qualification
    ? `/api/v1/saved-courses/?qualification=${qualification}`
    : '/api/v1/saved-courses/'
  return apiRequest(url, options)
}

export async function saveCourse(
  courseId: string,
  options?: ApiOptions & { courseType?: 'spm' | 'stpm' }
): Promise<{ message: string }> {
  const body: Record<string, string> = { course_id: courseId }
  if (options?.courseType) body.course_type = options.courseType
  return apiRequest('/api/v1/saved-courses/', {
    method: 'POST',
    body: JSON.stringify(body),
    ...options,
  })
}

export async function unsaveCourse(
  courseId: string,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest(`/api/v1/saved-courses/${courseId}/`, {
    method: 'DELETE',
    ...options,
  })
}

export async function updateSavedCourseStatus(
  courseId: string,
  interestStatus: string,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest(`/api/v1/saved-courses/${courseId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ interest_status: interestStatus }),
    ...options,
  })
}

