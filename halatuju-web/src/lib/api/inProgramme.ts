/**
 * A student already on the programme (F9b): semester results, the 18+ promotional consent,
 * and the graduation message relay.
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── F9b — in-programme student lifecycle (results, 18+ promo consent, graduation relay) ──

export interface SemesterResult {
  id: number
  semester: string
  cgpa: string | null
  graduated: boolean
  results_slip: number | null
  note: string
  created_at: string
}

/** F9a/b — the student's own in-programme semester results (latest first). */
export async function getSemesterResults(appId: number, options?: ApiOptions): Promise<{ results: SemesterResult[] }> {
  return apiRequest(`/api/v1/scholarship/applications/${appId}/semester-results/`, options)
}

/** Record one semester result. 400 `not_in_programme` (award not accepted) / `bad_cgpa`. */
export async function addSemesterResult(
  appId: number,
  body: { semester?: string; cgpa?: string | null; graduated?: boolean; results_slip?: number | null; note?: string },
  options?: ApiOptions,
): Promise<SemesterResult> {
  return apiRequest(`/api/v1/scholarship/applications/${appId}/semester-results/`, {
    ...options, method: 'POST', body: JSON.stringify(body),
  })
}

export interface PromotionalConsentState { granted: boolean; is_minor: boolean }

/** F9b — the separate 18+-only promotional_use consent. */
export async function getPromotionalConsent(appId: number, options?: ApiOptions): Promise<PromotionalConsentState> {
  return apiRequest(`/api/v1/scholarship/applications/${appId}/promotional-consent/`, options)
}

/** Grant (POST) or withdraw (DELETE) the promotional_use consent. Grant 400s
 *  `minor_not_allowed` server-side for an under-18 (no guardian path). */
export async function setPromotionalConsent(appId: number, grant: boolean, options?: ApiOptions): Promise<{ granted: boolean }> {
  return apiRequest(`/api/v1/scholarship/applications/${appId}/promotional-consent/`, {
    ...options, method: grant ? 'POST' : 'DELETE',
  })
}

export interface GraduationMessage {
  id: number
  status: 'pending' | 'blocked' | 'approved' | 'rejected'
  raw_text: string
  scrubbed_text: string
  scan_result: string[]   // identifying fields the scan flagged when blocked (e.g. ['name','city'])
  created_at: string
  reviewed_at: string | null
}

/** F9b — the student's own graduation thank-you submissions + their review status. */
export async function getGraduationMessages(appId: number, options?: ApiOptions): Promise<{ messages: GraduationMessage[] }> {
  return apiRequest(`/api/v1/scholarship/applications/${appId}/graduation-message/`, options)
}

/** Submit a thank-you. Returns 201 with the saved row — `status:'blocked'` +
 *  `scan_result` when it carries the student's own identifiers (edit + resend),
 *  else `status:'pending'` (awaiting staff approval). */
export async function submitGraduationMessage(appId: number, text: string, options?: ApiOptions): Promise<GraduationMessage> {
  return apiRequest(`/api/v1/scholarship/applications/${appId}/graduation-message/`, {
    ...options, method: 'POST', body: JSON.stringify({ text }),
  })
}

// F9b — the sponsor-facing relay: a staff-approved note from a funded student,
// linked ONLY to the anonymous ref (never identity, never a reply channel).
export interface GraduationRelayMessage { ref: string; text: string; approved_at: string }

/** The approved graduation notes from the students this sponsor funds. 404s while
 *  the pool flag is off (callers treat that as "not available yet"). */
export async function getSponsorGraduationMessages(options?: ApiOptions): Promise<{ messages: GraduationRelayMessage[] }> {
  return apiRequest('/api/v1/sponsor/graduation-messages/', options)
}

