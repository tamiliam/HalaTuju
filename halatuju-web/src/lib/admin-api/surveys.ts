/**
 * Programme → Surveys (student maintenance S9, 2026-11-02): an organisation's questions to its scholars,
 * the results, the CSV, and the scholar file's Surveys tab. Every rule is the server's
 * (`apps/scholarship/surveys.py`): who may make one, who sees it, the lock at the first answer, the
 * emails. The screens offer Delete / Close now / Remind only where the server's row says so.
 */
import { API_BASE, adminFetch, adminMutate, giftQuery } from './client'
import type { ApiOptions } from './client'

export type SurveyStatus = 'draft' | 'scheduled' | 'open' | 'closed'
export type SurveyAction = 'publish' | 'draft'
export type QuestionKind = 'one' | 'many' | 'rating' | 'yes_no' | 'short' | 'long'

export interface SurveyQuestionInput {
  kind: QuestionKind
  text: string
  hint: string
  required: boolean
  mentor_only: boolean
  /** The choices of a `one` / `many` question; `[]` otherwise. */
  options: string[]
}

export interface SurveyQuestionRow extends SurveyQuestionInput {
  id: number
}

export interface SurveyRow {
  id: number
  title: string
  intro: string
  /** The server's word, read from the dates. */
  status: SurveyStatus
  /** null = every scholar of the organisation. */
  programme: { code: string; name: string } | null
  opens_at: string
  closes_at: string
  questions: SurveyQuestionRow[]
  /** The scholars it is for today ("of M" in "N of M answered"). */
  audience_count: number
  answered_count: number
  email_on_open: boolean
  remind: boolean
  opened_emailed_at: string | null
  reminded_at: string | null
  author: { email: string; name: string; role: string }
  created_at: string
  /** At least one answer: the questions, the audience and the opening time are fixed. */
  locked: boolean
  can_delete: boolean
  can_close: boolean
}

export interface SurveyAudience {
  programme: string | null
  name: string
  count: number
}

export interface SurveyLimits {
  title: number
  intro: number
  question: number
  hint: number
  option: number
  options: number
  questions: number
}

export interface SurveysPayload {
  organisation: { code: string; name: string }
  surveys: SurveyRow[]
  counts: Record<SurveyStatus, number>
  audiences: SurveyAudience[]
  /** The organisation's "Survey" student email is switched on (Student communications). */
  email_switch_on: boolean
  limits: SurveyLimits
}

export interface SurveyInput {
  title: string
  intro: string
  programme: string | null
  /** ISO date-time; omitted = now. */
  opens_at?: string
  closes_at: string
  email_on_open: boolean
  remind: boolean
  questions: SurveyQuestionInput[]
  action?: SurveyAction
}

export interface SurveyWho {
  application_id: number
  name: string
}

/** A value as stored: an option's text, a list of them, 1-5, true/false, or the words written. */
export type AnswerValue = string | string[] | number | boolean

export interface SurveySummaryItem {
  question_id: number
  answered: number
  /** Choices, yes/no (option true/false) and ratings (option 1-5): each with who chose it. */
  options?: { option: string | number | boolean; count: number; who: SurveyWho[] }[]
  average?: number | null
  written?: (SurveyWho & { text: string })[]
}

export interface SurveyResults {
  survey: SurveyRow
  summary: SurveySummaryItem[]
  responses: (SurveyWho & { submitted_at: string; updated_at: string; answers: Record<string, AnswerValue> })[]
  not_answered: (SurveyWho & { reminded: boolean })[]
  can_remind: boolean
}

export interface ScholarSurveys {
  answered: {
    id: number
    title: string
    status: SurveyStatus
    submitted_at: string
    updated_at: string
    answers: { question_id: number; text: string; kind: QuestionKind; value: AnswerValue }[]
  }[]
  waiting: { id: number; title: string; closes_at: string }[]
}

const BASE = '/api/v1/admin/scholarship/surveys/'

export async function getSurveys(programme?: string, options?: ApiOptions) {
  return adminFetch<SurveysPayload>(`${BASE}${giftQuery(programme)}`, options)
}

/** Refusals arrive as `code` (+ `detail`: the question's place for a question error). */
export async function createSurvey(data: SurveyInput, programme?: string, options?: ApiOptions) {
  return adminMutate<SurveyRow>(`${BASE}${giftQuery(programme)}`, 'POST', data, options)
}

/** From the first answer: 409 `questions_locked` / `answered_locked` for the fixed parts. */
export async function updateSurvey(id: number, data: Partial<SurveyInput>, options?: ApiOptions) {
  return adminMutate<SurveyRow>(`${BASE}${id}/`, 'PATCH', data, options)
}

/** Only while nobody has answered (409 `close_instead`). */
export async function deleteSurvey(id: number, options?: ApiOptions) {
  return adminMutate<void>(`${BASE}${id}/`, 'DELETE', null, options)
}

export async function closeSurvey(id: number, options?: ApiOptions) {
  return adminMutate<SurveyRow>(`${BASE}${id}/close/`, 'POST', null, options)
}

export async function getSurveyResults(id: number, options?: ApiOptions) {
  return adminFetch<SurveyResults>(`${BASE}${id}/results/`, options)
}

/** The same reminder as the hourly job, now, to each scholar not yet reminded (never twice). */
export async function remindSurvey(id: number, options?: ApiOptions) {
  return adminMutate<Omit<SurveyResults, 'survey'> & { sent: number }>(`${BASE}${id}/remind/`, 'POST', null, options)
}

/** The CSV (auth header required), as text for a client-side download. */
export async function fetchSurveyCsv(id: number, options?: ApiOptions): Promise<string> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${BASE}${id}/csv/`, { headers })
  if (!res.ok) throw new Error(`CSV download failed: ${res.status}`)
  return res.text()
}

export async function getScholarSurveys(id: number, options?: ApiOptions) {
  return adminFetch<ScholarSurveys>(`/api/v1/admin/scholarship/scholars/${id}/surveys/`, options)
}
