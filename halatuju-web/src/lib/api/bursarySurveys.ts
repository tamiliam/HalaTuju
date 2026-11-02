// Her Surveys tab on My Bursary (student maintenance S9). Her OWN file only — the server 404s anything else.
// Imported by `components/bursary/BursarySurveys.tsx` only, so no other route carries it.
import { apiRequest } from './client'
import type { ApiOptions } from './client'

export type SurveyKind = 'one' | 'many' | 'rating' | 'yes_no' | 'short' | 'long'
export type SurveyAnswer = string | string[] | number | boolean

export interface SurveyQuestion {
  id: number
  kind: SurveyKind
  text: string
  hint: string
  required: boolean
  options: string[]
}

/** One survey as the server lets her see it (`surveys.student_payload`, an allowlist): her questions and
 *  her own answers — never who wrote it, who else it is for, a count, or anybody else's answer. */
export interface MySurvey {
  id: number
  title: string
  intro: string
  status: 'open' | 'closed'
  opens_at: string
  closes_at: string
  /** Open and her file in maintenance: she may send or change her answers. */
  can_answer: boolean
  answered_at: string | null
  updated_at: string | null
  questions: SurveyQuestion[]
  /** Her answers, by question id. */
  answers: Record<string, SurveyAnswer>
}

export interface MySurveys {
  organisation: string
  surveys: MySurvey[]
}

export async function getMySurveys(options?: ApiOptions): Promise<MySurveys> {
  return apiRequest('/api/v1/scholarship/bursary/surveys/', options)
}

/** Send (or change) her answers. Refusals: 409 `survey_closed`; 400 `required` / `bad_answer` /
 *  `answer_too_long` with the question's id in `detail`. */
export async function sendMyAnswers(id: number, answers: Record<string, SurveyAnswer>, options?: ApiOptions):
  Promise<{ survey: MySurvey | null; to_answer: number }> {
  return apiRequest(`/api/v1/scholarship/bursary/surveys/${id}/answers/`,
    { ...options, method: 'POST', body: JSON.stringify({ answers }) })
}
