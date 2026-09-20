/**
 * The STPM / Form-6 arm: its own eligibility check, its own ranking, its own quiz, and its
 * own course search and detail read.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'
import type { MascoOccupation } from './courses'

// STPM types
export interface StpmEligibleCourse {
  course_id: string
  course_name: string
  university: string
  stream: string
  field: string // Legacy — use field_key instead
  field_key?: string
  min_cgpa: number
  min_muet_band: number
  stpm_req_physics: boolean
  req_interview: boolean
  no_colorblind: boolean
  merit_score: number | null
}

export interface StpmEligibilityRequest {
  stpm_grades: Record<string, string>
  spm_grades: Record<string, string>
  cgpa: number
  muet_band: number
  gender?: string
  nationality?: string
  colorblind?: boolean
}

export interface StpmEligibilityResponse {
  eligible_courses: StpmEligibleCourse[]
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

export interface StpmRankedCourse extends StpmEligibleCourse {
  fit_score: number
  fit_reasons: string[]
}

export interface StpmRankingRequest {
  eligible_courses: StpmEligibleCourse[]
  student_cgpa: number
  student_signals: Record<string, unknown>
  stpm_subjects?: string[]
}

export interface StpmResultFraming {
  mode: 'confirmatory' | 'guided' | 'discovery'
  heading: string
  subtitle: string
}

export interface StpmRankingResponse {
  ranked_courses: StpmRankedCourse[]
  total: number
  framing?: StpmResultFraming
}

export async function rankStpmCourses(
  data: StpmRankingRequest,
  options?: ApiOptions
): Promise<StpmRankingResponse> {
  return apiRequest('/api/v1/stpm/ranking/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}

// ── STPM Quiz types ──────────────────────────────────────────────────

export interface StpmQuizQuestion {
  id: string
  prompt: string
  options: { text: string; icon: string; signals: Record<string, number> }[]
}

export interface StpmQuizQuestionsResponse {
  branch: 'science' | 'arts' | 'mixed'
  riasec_seed: Record<string, number>
  primary_seed: string[]
  has_cross_stream: boolean
  questions: StpmQuizQuestion[]
  q3_variants: Record<string, StpmQuizQuestion>
  q5: StpmQuizQuestion
  trunk_remaining: StpmQuizQuestion[]
}

export interface StpmQuizResolveResponse {
  q3: StpmQuizQuestion | null
  q4: StpmQuizQuestion | null
}

export interface StpmQuizSubmitResponse {
  student_signals: Record<string, Record<string, number>>
  signal_strength: Record<string, string>
  branch: string
  riasec_seed: Record<string, number>
}

// ── STPM Quiz API functions ──────────────────────────────────────────

export async function getStpmQuizQuestions(
  subjects: string[],
  grades: Record<string, string>,
  lang: string = 'en',
  options?: ApiOptions
): Promise<StpmQuizQuestionsResponse> {
  const params = new URLSearchParams()
  params.set('subjects', subjects.join(','))
  params.set('grades', JSON.stringify(grades))
  params.set('lang', lang)
  return apiRequest(`/api/v1/stpm/quiz/questions/?${params.toString()}`, options)
}

export async function resolveStpmQuizQ3Q4(
  fieldSignal: string,
  branch: string,
  grades: Record<string, string>,
  lang: string = 'en',
  options?: ApiOptions
): Promise<StpmQuizResolveResponse> {
  return apiRequest('/api/v1/stpm/quiz/resolve/', {
    method: 'POST',
    body: JSON.stringify({
      field_signal: fieldSignal,
      branch,
      grades,
      lang,
    }),
    ...options,
  })
}

export async function submitStpmQuiz(
  answers: { question_id: string; option_index: number }[],
  subjects: string[],
  grades: Record<string, string>,
  lang: string = 'en',
  options?: ApiOptions
): Promise<StpmQuizSubmitResponse> {
  return apiRequest('/api/v1/stpm/quiz/submit/', {
    method: 'POST',
    body: JSON.stringify({ answers, subjects, grades, lang }),
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
  courses: StpmEligibleCourse[]
  total_count: number
  filters: StpmSearchFilters
}

export interface SubjectGroupDisplay {
  min_count: number
  min_grade: string
  subjects: string[]
  any_subject: boolean
  exclude: string[]
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
  stpm_subject_groups_display: SubjectGroupDisplay[]
  spm_subject_groups_display: SubjectGroupDisplay[]
  req_interview: boolean
  no_colorblind: boolean
  req_medical_fitness: boolean
  req_male: boolean
  req_female: boolean
  single: boolean
  no_disability: boolean
  req_malaysian: boolean
  req_bumiputera: boolean
}

export interface StpmInstitutionDetail {
  institution_id: string
  institution_name: string
  acronym: string
  type: string
  category: string
  state: string
  url: string
}

export interface StpmCourseDetail {
  course_id: string
  course_name: string
  university: string
  stream: string
  field: string // Legacy — use field_key instead
  field_key?: string
  category: string
  description: string
  headline: string
  merit_score: number | null
  mohe_url?: string
  requirements: StpmRequirements
  institution: StpmInstitutionDetail | null
  career_occupations: MascoOccupation[]
}

export async function searchStpmCourses(
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

export async function getStpmCourseDetail(
  courseId: string,
  options?: ApiOptions
): Promise<StpmCourseDetail> {
  return apiRequest(`/api/v1/stpm/courses/${courseId}/`, options)
}

