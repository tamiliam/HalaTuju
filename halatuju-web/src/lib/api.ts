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
  student_merit: number | null
  merit_label: string | null
  merit_color: string | null
}

export interface Course {
  course_id: string
  course: string
  level: string
  department: string
  field: string
  frontend_label: string
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

// API Functions
export async function checkEligibility(
  profile: StudentProfile,
  options?: ApiOptions
): Promise<{ eligible_courses: EligibleCourse[]; stats: Record<string, number>; insights: Insights }> {
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
): Promise<{ course: Course; institutions: Institution[]; career_occupations: MascoOccupation[] }> {
  return apiRequest(`/api/v1/courses/${courseId}/`, options)
}

export async function getInstitutions(options?: ApiOptions): Promise<{ institutions: Institution[] }> {
  return apiRequest('/api/v1/institutions/', options)
}

export async function getSavedCourses(options?: ApiOptions): Promise<{ saved_courses: Course[] }> {
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
  return apiRequest(`/api/v1/saved-courses/${courseId}/`, {
    method: 'DELETE',
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

// Quiz types
export interface QuizQuestion {
  id: string
  prompt: string
  options: { text: string; signals: Record<string, number> }[]
}

export interface QuizAnswer {
  question_id: string
  option_index: number
}

export interface QuizResult {
  student_signals: Record<string, Record<string, number>>
  signal_strength: Record<string, string>
}

// Ranked course extends EligibleCourse with fit data
export interface RankedCourse extends EligibleCourse {
  fit_score: number
  fit_reasons: string[]
  institution_id?: string
}

export interface RankingResult {
  top_5: RankedCourse[]
  rest: RankedCourse[]
  total_ranked: number
}

// Quiz API functions
export async function getQuizQuestions(
  lang: string = 'en',
  options?: ApiOptions
): Promise<{ questions: QuizQuestion[]; total: number; lang: string }> {
  return apiRequest(`/api/v1/quiz/questions/?lang=${lang}`, options)
}

export async function submitQuiz(
  answers: QuizAnswer[],
  lang: string = 'en',
  options?: ApiOptions
): Promise<QuizResult> {
  return apiRequest('/api/v1/quiz/submit/', {
    method: 'POST',
    body: JSON.stringify({ answers, lang }),
    ...options,
  })
}

export async function getRankedResults(
  eligibleCourses: EligibleCourse[],
  studentSignals: Record<string, Record<string, number>>,
  options?: ApiOptions
): Promise<RankingResult> {
  return apiRequest('/api/v1/ranking/', {
    method: 'POST',
    body: JSON.stringify({
      eligible_courses: eligibleCourses,
      student_signals: studentSignals,
    }),
    ...options,
  })
}

// Report types
export interface GenerateReportResponse {
  report_id: number
  markdown: string
  counsellor_name: string
  model_used: string
}

export interface ReportDetail {
  report_id: number
  title: string
  markdown: string
  summary: string
  model_used: string
  created_at: string
}

export interface ReportListItem {
  report_id: number
  title: string
  summary: string
  model_used: string
  created_at: string
}

// Report API functions
export async function generateReport(
  eligibleCourses: EligibleCourse[],
  insights: Insights,
  lang: string = 'bm',
  options?: ApiOptions
): Promise<GenerateReportResponse> {
  return apiRequest('/api/v1/reports/generate/', {
    method: 'POST',
    body: JSON.stringify({
      eligible_courses: eligibleCourses,
      insights,
      lang,
    }),
    ...options,
  })
}

export async function getReport(
  reportId: number,
  options?: ApiOptions
): Promise<ReportDetail> {
  return apiRequest(`/api/v1/reports/${reportId}/`, options)
}

export async function getReports(
  options?: ApiOptions
): Promise<{ reports: ReportListItem[]; count: number }> {
  return apiRequest('/api/v1/reports/', options)
}
