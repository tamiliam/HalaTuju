/**
 * Sprint THANKS-SCHOLARS (owner 2026-11-16, "Thank yous are part of the scholar maintenance process"): a
 * student's graduation thank-you is read and decided on the SCHOLAR FILE, under the file's own rules. The
 * read serves `may_decide` (the server's decide rule, never derived here): true for a `scholars` holder who
 * may change the file, false for a mentor (read-only; `approved_by` is then a name, never an email). The
 * server refuses both calls to everyone else, a reviewer included.
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

export interface ScholarThanks {
  messages: AdminGraduationMessage[]
  /** The server's decide rule for THIS viewer on THIS file. The card draws the buttons only when true. */
  may_decide: boolean
}

export async function getScholarThanks(id: number, options?: ApiOptions) {
  return adminFetch<ScholarThanks>(`/api/v1/admin/scholarship/scholars/${id}/graduation-messages/`, options)
}

export async function reviewScholarThanks(id: number, messageId: number, body: GraduationReview,
  options?: ApiOptions) {
  return adminMutate<AdminGraduationMessage>(
    `/api/v1/admin/scholarship/scholars/${id}/graduation-messages/${messageId}/review/`, 'POST', body, options)
}
