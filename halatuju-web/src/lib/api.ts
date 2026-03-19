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
  postal_code?: string
  city?: string
  phone?: string
  email?: string
  family_income?: string
  siblings?: number | null
  angka_giliran?: string
  contact_email?: string
  contact_email_verified?: boolean
  contact_phone?: string
  contact_phone_verified?: boolean
}

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
}

export interface SearchFilters {
  levels: string[]
  fields: string[]
  source_types: string[]
  states: string[]
  qualifications: string[]
}

export interface SearchParams {
  q?: string
  level?: string
  field_key?: string
  source_type?: string
  state?: string
  qualification?: string
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

export async function claimNric(
  nric: string,
  confirm: boolean = false,
  options?: ApiOptions
): Promise<{ status: 'created' | 'exists' | 'claimed' | 'linked'; name?: string }> {
  return apiRequest('/api/v1/profile/claim-nric/', {
    method: 'POST',
    body: JSON.stringify({ nric, confirm }),
    ...options,
  })
}

export async function sendVerificationEmail(
  email: string,
  lang?: string,
  options?: ApiOptions
): Promise<{ status: string }> {
  return apiRequest('/api/v1/profile/verify-email/send/', {
    method: 'POST',
    body: JSON.stringify({ email, lang }),
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
  ranked: RankedCourse[]
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
  colorblind?: boolean
  disability?: boolean
  student_signals?: Record<string, Record<string, number>>
  preferred_state?: string
  name?: string
  school?: string
  nric?: string
  referral_source?: string
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

// ── Field Taxonomy types ──────────────────────────────────────────────

export interface FieldTaxonomyEntry {
  key: string
  name_en: string
  name_ms: string
  name_ta: string
  image_slug: string
  parent_key: string | null
  sort_order: number
  children: FieldTaxonomyEntry[]
}

export async function fetchFieldTaxonomy(
  options?: ApiOptions
): Promise<{ groups: FieldTaxonomyEntry[] }> {
  return apiRequest('/api/v1/fields/', options)
}

// ── Calculation types ──────────────────────────────────────────────────

export interface MeritResult {
  academic_merit: number
  final_merit: number
}

export interface CgpaResult {
  cgpa: number
  academic_cgpa: number
  merit_percent: number
}

export interface PathwayResult {
  pathway: 'matric' | 'stpm'
  trackId: string
  trackName: string
  trackNameMs: string
  trackNameTa: string
  eligible: boolean
  merit: number | null
  mataGred: number | null
  maxMataGred: number | null
  fitScore: number
  reason: string | null
}

// ── Calculation API functions (stateless, public) ──────────────────────

export async function calculateMerit(
  grades: Record<string, string>,
  coqScore: number,
  options?: ApiOptions
): Promise<MeritResult> {
  return apiRequest('/api/v1/calculate/merit/', {
    method: 'POST',
    body: JSON.stringify({ grades, coq_score: coqScore }),
    ...options,
  })
}

export async function calculateCgpa(
  stpmGrades: Record<string, string>,
  kokoScore: number = 0,
  options?: ApiOptions
): Promise<CgpaResult> {
  return apiRequest('/api/v1/calculate/cgpa/', {
    method: 'POST',
    body: JSON.stringify({ stpm_grades: stpmGrades, koko_score: kokoScore }),
    ...options,
  })
}

export async function calculatePathways(
  grades: Record<string, string>,
  coqScore: number,
  signals?: Record<string, Record<string, number>> | null,
  options?: ApiOptions
): Promise<{ pathways: PathwayResult[] }> {
  const raw = await apiRequest<{ pathways: Array<Record<string, unknown>> }>('/api/v1/calculate/pathways/', {
    method: 'POST',
    body: JSON.stringify({ grades, coq_score: coqScore, signals: signals || undefined }),
    ...options,
  })
  // Map snake_case backend keys to camelCase frontend keys
  const pathways: PathwayResult[] = raw.pathways.map(p => ({
    pathway: p.pathway as 'matric' | 'stpm',
    trackId: p.track_id as string,
    trackName: p.track_name as string,
    trackNameMs: p.track_name_ms as string,
    trackNameTa: p.track_name_ta as string,
    eligible: p.eligible as boolean,
    merit: (p.merit as number) ?? null,
    mataGred: (p.mata_gred as number) ?? null,
    maxMataGred: (p.max_mata_gred as number) ?? null,
    fitScore: (p.fit_score as number) ?? 0,
    reason: (p.reason as string) ?? null,
  }))
  return { pathways }
}
