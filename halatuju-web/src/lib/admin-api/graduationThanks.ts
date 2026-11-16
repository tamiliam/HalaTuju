/**
 * Sprint THANKS (owner 2026-11-16): a student's graduation thank-you, read and moderated from the case page
 * by whoever holds the `review` key. The read is its OWN fetch (the detail payload, pinned at 38 queries,
 * is untouched); the server refuses both calls without the key.
 *
 * Refusal codes on the review call: `scrubbed_leak` (the edited text still names the student),
 * `not_reviewable` (already decided, or blocked and asked to approve), `empty_message`, `bad_action`.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

export type GraduationMessageStatus = 'pending' | 'blocked' | 'approved' | 'rejected'

export interface AdminGraduationMessage {
  id: number
  application: number
  ref: string
  status: GraduationMessageStatus
  raw_text: string
  scrubbed_text: string
  /** The identifying fields the automatic check found ('name', 'school', 'city', 'nric', 'phone', 'email'). */
  scan_result: string[]
  approved_by: string
  review_note: string
  created_at: string
  reviewed_at: string | null
}

export type GraduationReview =
  | { action: 'approve'; scrubbed_text: string }
  | { action: 'reject'; review_note: string }

export async function getCaseGraduationMessages(id: number, options?: ApiOptions) {
  return adminFetch<{ messages: AdminGraduationMessage[] }>(
    `/api/v1/admin/scholarship/applications/${id}/graduation-messages/`, options)
}

export async function reviewGraduationMessage(messageId: number, body: GraduationReview, options?: ApiOptions) {
  return adminMutate<AdminGraduationMessage>(
    `/api/v1/admin/graduation-messages/${messageId}/review/`, 'POST', body, options)
}
