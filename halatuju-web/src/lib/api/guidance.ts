/**
 * Where a student is pointed next: the interest quiz, the ranked course list, the report we
 * generate from it, and the admission outcomes they record elsewhere.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'
import type { EligibleCourse, Insights } from './courses'

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

