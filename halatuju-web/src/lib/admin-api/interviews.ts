/**
 * Interview scheduling from the OFFICER's side: proposing times, withdrawing one, the gap
 * suggester, and the Check-3 session itself.
 *
 * ⚠ `InterviewSchedule` is one half of a keep-in-sync pair with the student copy in
 * `api/interview.ts`.
 * drift-test: halatuju-web/src/lib/__tests__/webMirrorDrift.test.ts
 *
 * ⚠ THREE SPANS of the old `admin-api.ts` (1214-1251, 1372-1397, 1480-1512).
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { AdminInterviewSession, AdminScholarshipDetail } from './applications'

/** One proposed interview time. `start` is ISO (UTC); render in MYT on the client. */
export interface InterviewSlot {
  id: number
  start: string
  duration_min: number
  is_active: boolean
}

/** Interview booking state + the active proposed slots (shared admin/student shape). */
export interface InterviewSchedule {
  enabled: boolean
  status: '' | 'booked' | 'cancelled'
  start: string | null
  meeting_url: string
  meeting_provider: string
  booked_slot_id: number | null
  slots: InterviewSlot[]
  reschedule_cutoff_hours: number
  /** The organisation's booking grid, SERVED (Org Config Sprint D) — the picker must not
   *  hold its own copy. Optional so a payload cached from an older build still types; read
   *  them through `interviewSlots.slotRulesFrom`, which falls back per field.
   *  ⚠ The student shape in `api.ts` carries these too — same endpoint family, one seam. */
  slot_window_start_min?: number
  slot_window_end_min?: number
  slot_step_min?: number
  slot_min_lead_hours?: number
  interview_duration_min?: number
  /** Reviewer-facing only: start times (ISO) this reviewer already holds for OTHER
   *  students, so the propose grid can grey them out. Absent on the student payload. */
  reviewer_busy?: string[]
  /** The student said none of the proposed times work and asked for others. */
  alternatives_requested?: boolean
  alternatives_note?: string
  cancel_reason?: string
  /** The student's messages to their reviewer (the always-open channel), oldest first. */
  messages?: { text: string; created_at: string }[]
}

export async function getInterview(id: number, options?: ApiOptions) {
  return adminFetch<{ session: AdminInterviewSession | null; agenda: string[] }>(
    `/api/v1/admin/scholarship/applications/${id}/interview/`, options)
}

export async function saveInterview(
  id: number,
  payload: { findings: Record<string, { verdict: string; rationale: string }>; rubric: Record<string, number>; overall_note: string },
  options?: ApiOptions,
) {
  return adminMutate<AdminInterviewSession>(
    `/api/v1/admin/scholarship/applications/${id}/interview/`, 'POST', payload, options)
}

export async function submitInterview(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/interview/submit/`, 'POST', {}, options)
}

/** Reopen a SUBMITTED interview (un-submits → draft) so the reviewer can add a forgotten
 *  finding; reopens both the Interview Stage and Check 2. Only valid before a decision. */
export async function reopenInterview(id: number, options?: ApiOptions) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/interview/reopen/`, 'POST', {}, options)
}

// ── Interview scheduling (reviewer proposes times) ────────────────────────────
/** The assigned reviewer (or super) proposes interview times. `starts` are ISO
 *  strings. Returns the refreshed schedule (booking state + active slots). */
export async function proposeInterviewSlots(
  id: number, starts: string[], options?: ApiOptions & { reschedule?: boolean }) {
  const { reschedule, ...rest } = options || {}
  return adminMutate<InterviewSchedule>(
    `/api/v1/admin/scholarship/applications/${id}/interview-slots/`, 'POST',
    { slots: starts, ...(reschedule ? { reschedule: true } : {}) }, rest)
}

export async function getInterviewSlots(id: number, options?: ApiOptions) {
  return adminFetch<InterviewSchedule>(
    `/api/v1/admin/scholarship/applications/${id}/interview-slots/`, options)
}

/** Withdraw a single proposed (unbooked) slot. */
export async function withdrawInterviewSlot(id: number, slotId: number, options?: ApiOptions) {
  return adminMutate<InterviewSchedule>(
    `/api/v1/admin/scholarship/applications/${id}/interview-slots/${slotId}/`, 'DELETE', null, options)
}

/** Phase B: admin-on-demand Gemini interview gap-spotter. Returns the refreshed detail.
 *  ``append`` generates 3 MORE (without repeating) and appends; otherwise replaces. */
export async function suggestInterviewGaps(
  id: number, language?: string, options?: ApiOptions, append = false
) {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/suggest-gaps/`, 'POST',
    { ...(language ? { language } : {}), ...(append ? { append: true } : {}) }, options
  )
}

