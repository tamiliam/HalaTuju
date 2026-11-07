/**
 * Request #55 (2026-11-07): "Notes for the reviewer" on the case page. An organisation admin (or a
 * platform super) writes; whoever may open the file reads. A SEPARATE fetch, so the detail payload
 * (pinned at 38 queries) is untouched. Append-only: there is no edit and no delete.
 *
 * `can_add` is SERVED (the window AND the writer's role, both the server's) — the card never derives
 * it. Refusal codes: `writer_only`, `notes_closed`, `empty_body`, `too_long`.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

export interface ReviewerNote {
  id: number
  body: string
  author_name: string
  created_at: string
}

export interface ReviewerNotes {
  notes: ReviewerNote[]
  window_open: boolean
  can_add: boolean
  max_length: number
}

export async function getReviewerNotes(id: number, options?: ApiOptions) {
  return adminFetch<ReviewerNotes>(`/api/v1/admin/scholarship/applications/${id}/reviewer-notes/`, options)
}

export async function addReviewerNote(id: number, body: string, options?: ApiOptions) {
  return adminMutate<ReviewerNotes>(
    `/api/v1/admin/scholarship/applications/${id}/reviewer-notes/`, 'POST', { body }, options)
}
