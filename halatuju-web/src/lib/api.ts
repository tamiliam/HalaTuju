/**
 * API client for HalaTuju Django backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ApiOptions {
  token?: string
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit & ApiOptions = {}
): Promise<T> {
  const { token, ...fetchOptions } = options

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(options.headers || {}),
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.message || `API error: ${response.status}`)
  }

  return response.json()
}

// Types
export interface StudentProfile {
  grades: Record<string, string>
  gender: 'male' | 'female'
  nationality: 'malaysian' | 'non_malaysian'
  colorblind?: boolean
  disability?: boolean
  student_signals?: Record<string, number>
  preferred_state?: string
}

export interface EligibleCourse {
  course_id: string
  course_name: string
  level: string
  field: string
  source_type: string
  merit_cutoff: number | null
}

export interface Course {
  course_id: string
  course: string
  level: string
  department: string
  field: string
  frontend_label: string
  description: string
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
}

// API Functions
export async function checkEligibility(
  profile: StudentProfile,
  options?: ApiOptions
): Promise<{ eligible_courses: EligibleCourse[]; stats: Record<string, number> }> {
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
): Promise<{ course: Course; institutions: Institution[] }> {
  return apiRequest(`/api/v1/courses/${courseId}/`, options)
}

export async function getInstitutions(options?: ApiOptions): Promise<{ institutions: Institution[] }> {
  return apiRequest('/api/v1/institutions/', options)
}

export async function getSavedCourses(options?: ApiOptions): Promise<{ saved_courses: string[] }> {
  return apiRequest('/api/v1/saved-courses/', options)
}

export async function saveCourse(
  courseId: string,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest('/api/v1/saved-courses/', {
    method: 'POST',
    body: JSON.stringify({ course_id: courseId }),
    ...options,
  })
}

export async function unsaveCourse(
  courseId: string,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest('/api/v1/saved-courses/', {
    method: 'DELETE',
    body: JSON.stringify({ course_id: courseId }),
    ...options,
  })
}

export async function getProfile(options?: ApiOptions): Promise<StudentProfile> {
  return apiRequest('/api/v1/profile/', options)
}

export async function updateProfile(
  profile: Partial<StudentProfile>,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest('/api/v1/profile/', {
    method: 'PUT',
    body: JSON.stringify(profile),
    ...options,
  })
}
