/**
 * Interview scheduling from the STUDENT's side: the slots offered, booking one, cancelling,
 * asking for alternatives, and the always-open message channel to the reviewer.
 *
 * ⚠ `InterviewSchedule` is one half of a keep-in-sync pair with the admin copy in
 * `admin-api/interviews.ts`.
 * drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts
 */
import { apiRequest } from './client'
import type { ApiOptions } from './client'

// ── Interview scheduling (student books a proposed slot) ──────────────────────
/** One interview time proposed by the reviewer. `start` is ISO (UTC). */
export interface InterviewSlot {
  id: number
  start: string
  duration_min: number
  is_active: boolean
}

/** The student's interview booking state + proposed slots. */
export interface InterviewMessage {
  text: string
  created_at: string
}

export interface InterviewSchedule {
  enabled: boolean
  status: '' | 'booked' | 'cancelled'
  start: string | null
  meeting_url: string
  meeting_provider: string
  booked_slot_id: number | null
  slots: InterviewSlot[]
  reschedule_cutoff_hours: number
  /** The organisation's booking grid, SERVED (Org Config Sprint D). The VALUES are the server's;
   *  only the SHAPE is written twice — the admin mirror is in `admin-api.ts`.
   *  drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts */
  slot_window_start_min?: number
  slot_window_end_min?: number
  slot_step_min?: number
  slot_min_lead_hours?: number
  interview_duration_min?: number
  alternatives_requested?: boolean
  alternatives_note?: string
  messages?: InterviewMessage[]
}

export async function getInterview(id: number, options?: ApiOptions): Promise<InterviewSchedule> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/interview/`, { ...options })
}

/** Book (or reschedule to) a proposed slot. */
export async function bookInterviewSlot(id: number, slotId: number, options?: ApiOptions): Promise<InterviewSchedule> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/interview/book/`, {
    method: 'POST', body: JSON.stringify({ slot_id: slotId }), ...options,
  })
}

/** Cancel the booked interview (subject to the reschedule cutoff). */
export async function cancelInterview(
  id: number, reason?: string, options?: ApiOptions
): Promise<InterviewSchedule> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/interview/cancel/`, {
    method: 'POST', body: JSON.stringify(reason ? { reason } : {}), ...options,
  })
}

/** Tell us none of the proposed times work (notifies the assigned reviewer). */
export async function requestInterviewAlternatives(
  id: number, note: string, options?: ApiOptions,
): Promise<InterviewSchedule> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/interview/request-alternatives/`, {
    method: 'POST', body: JSON.stringify({ note }), ...options,
  })
}

/** Message the assigned interviewer — the always-open channel (works in every state,
 *  even inside the reschedule cutoff, e.g. "I'm running late" before the call). */
export async function sendInterviewMessage(
  id: number, text: string, options?: ApiOptions,
): Promise<InterviewSchedule> {
  return apiRequest(`/api/v1/scholarship/applications/${id}/interview/message/`, {
    method: 'POST', body: JSON.stringify({ text }), ...options,
  })
}

