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
  coq_score?: number
  student_merit?: number
  student_signals?: Record<string, number>
  preferred_state?: string
  name?: string
  school?: string
  nric?: string
  address?: string
  phone?: string
  family_income?: string
  siblings?: number | null
}

export interface EligibleCourse {
  course_id: string
  course_name: string
  level: string
  field: string
  source_type: string
  pathway_type?: string
  merit_cutoff: number | null
  student_merit: number | null
  merit_label: string | null
  merit_color: string | null
  merit_display_student?: string
  merit_display_cutoff?: string
  pismp_languages?: string[]
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
  field: string
  source_type: string
  merit_cutoff: number | null
  institution_count: number
  institution_name: string
  institution_state: string
}

export interface SearchFilters {
  levels: string[]
  fields: string[]
  source_types: string[]
  states: string[]
}

export interface SearchParams {
  q?: string
  level?: string
  field?: string
  source_type?: string
  state?: string
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
  if (params.field) query.set('field', params.field)
  if (params.source_type) query.set('source_type', params.source_type)
  if (params.state) query.set('state', params.state)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const qs = query.toString()
  return apiRequest(`/api/v1/courses/search/${qs ? `?${qs}` : ''}`, options)
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
): Promise<{ course: Course; institutions: Institution[]; career_occupations: MascoOccupation[]; requirements: CourseRequirements | null; merit_cutoff?: number }> {
  return apiRequest(`/api/v1/courses/${courseId}/`, options)
}

export async function getInstitutions(options?: ApiOptions): Promise<{ institutions: Institution[] }> {
  return apiRequest('/api/v1/institutions/', options)
}

export interface SavedCourseWithStatus extends Course {
  interest_status: string
}

export async function getSavedCourses(options?: ApiOptions): Promise<{ saved_courses: SavedCourseWithStatus[] }> {
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
  options: { text: string; icon: string; signals: Record<string, number>; not_sure?: boolean }[]
  select_mode?: 'multi' | 'single'
  max_select?: number
  condition?: { requires: string; option_signal: string }
}

export interface QuizAnswer {
  question_id: string
  option_index?: number
  option_indices?: number[]
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

// Admission outcome types
export type OutcomeStatus = 'applied' | 'offered' | 'accepted' | 'rejected' | 'withdrawn'

export interface AdmissionOutcome {
  id: number
  course_id: string
  course_name: string
  institution_id: string | null
  institution_name: string | null
  status: OutcomeStatus
  intake_year: number | null
  intake_session: string
  notes: string
  applied_at: string | null
  outcome_at: string | null
  created_at: string
  updated_at: string
}

// Outcome API functions
export async function getOutcomes(
  options?: ApiOptions
): Promise<{ outcomes: AdmissionOutcome[]; count: number }> {
  return apiRequest('/api/v1/outcomes/', options)
}

export async function createOutcome(
  data: {
    course_id: string
    institution_id?: string
    status?: OutcomeStatus
    intake_year?: number
    intake_session?: string
    notes?: string
    applied_at?: string
  },
  options?: ApiOptions
): Promise<{ id: number; message: string }> {
  return apiRequest('/api/v1/outcomes/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}

export async function updateOutcome(
  outcomeId: number,
  data: Partial<{
    status: OutcomeStatus
    intake_year: number
    intake_session: string
    notes: string
    applied_at: string
    outcome_at: string
  }>,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest(`/api/v1/outcomes/${outcomeId}/`, {
    method: 'PUT',
    body: JSON.stringify(data),
    ...options,
  })
}

export async function deleteOutcome(
  outcomeId: number,
  options?: ApiOptions
): Promise<{ message: string }> {
  return apiRequest(`/api/v1/outcomes/${outcomeId}/`, {
    method: 'DELETE',
    ...options,
  })
}

// Profile sync (after first login — pushes localStorage data to backend)
export interface SyncProfileData {
  grades?: Record<string, string>
  gender?: string
  nationality?: string
  colorblind?: string
  disability?: string
  student_signals?: Record<string, Record<string, number>>
  preferred_state?: string
  name?: string
  school?: string
}

export async function syncProfile(
  data: SyncProfileData,
  options?: ApiOptions
): Promise<{ message: string; created: boolean }> {
  return apiRequest('/api/v1/profile/sync/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}

// STPM types
export interface StpmEligibleProgramme {
  program_id: string
  program_name: string
  university: string
  stream: string
  min_cgpa: number
  min_muet_band: number
  stpm_req_physics: boolean
  req_interview: boolean
  no_colorblind: boolean
}

export interface StpmEligibilityRequest {
  stpm_grades: Record<string, string>
  spm_grades: Record<string, string>
  cgpa: number
  muet_band: number
  gender?: string
  nationality?: string
  colorblind?: string
}

export interface StpmEligibilityResponse {
  eligible_programmes: StpmEligibleProgramme[]
  total_eligible: number
}

export async function checkStpmEligibility(
  data: StpmEligibilityRequest,
  options?: ApiOptions
): Promise<StpmEligibilityResponse> {
  return apiRequest('/api/v1/stpm/eligibility/check/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}

export interface StpmRankedProgramme extends StpmEligibleProgramme {
  fit_score: number
  fit_reasons: string[]
}

export interface StpmRankingRequest {
  eligible_programmes: StpmEligibleProgramme[]
  student_cgpa: number
  student_signals: Record<string, unknown>
}

export interface StpmRankingResponse {
  ranked_programmes: StpmRankedProgramme[]
  total: number
}

export async function rankStpmProgrammes(
  data: StpmRankingRequest,
  options?: ApiOptions
): Promise<StpmRankingResponse> {
  return apiRequest('/api/v1/stpm/ranking/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}

// STPM search + detail types
export interface StpmSearchParams {
  q?: string
  university?: string
  stream?: string
  limit?: number
  offset?: number
}

export interface StpmSearchFilters {
  universities: string[]
  streams: string[]
}

export interface StpmSearchResponse {
  programmes: StpmEligibleProgramme[]
  total_count: number
  filters: StpmSearchFilters
}

export interface StpmRequirements {
  min_cgpa: number
  min_muet_band: number
  stpm_min_subjects: number
  stpm_min_grade: string
  stpm_subjects: string[]
  stpm_subject_group: Record<string, unknown> | null
  spm_prerequisites: string[]
  spm_subject_group: Record<string, unknown> | null
  req_interview: boolean
  no_colorblind: boolean
  req_medical_fitness: boolean
  req_malaysian: boolean
  req_bumiputera: boolean
}

export interface StpmProgrammeDetail {
  program_id: string
  program_name: string
  university: string
  stream: string
  requirements: StpmRequirements
}

export async function searchStpmProgrammes(
  params: StpmSearchParams = {},
  options?: ApiOptions
): Promise<StpmSearchResponse> {
  const searchParams = new URLSearchParams()
  if (params.q) searchParams.set('q', params.q)
  if (params.university) searchParams.set('university', params.university)
  if (params.stream) searchParams.set('stream', params.stream)
  if (params.limit) searchParams.set('limit', String(params.limit))
  if (params.offset) searchParams.set('offset', String(params.offset))
  const qs = searchParams.toString()
  return apiRequest(`/api/v1/stpm/search/${qs ? `?${qs}` : ''}`, options)
}

export async function getStpmProgrammeDetail(
  programId: string,
  options?: ApiOptions
): Promise<StpmProgrammeDetail> {
  return apiRequest(`/api/v1/stpm/programmes/${programId}/`, options)
}
