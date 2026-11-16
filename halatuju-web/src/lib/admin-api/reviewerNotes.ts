/**
 * Request #55 (2026-11-07), two-way since request #73 (2026-11-16): "Org admin and reviewer notes" on the case
 * page. An organisation admin (or a platform super) and the ASSIGNED reviewer write; whoever may open the file
 * reads. A SEPARATE fetch, so the detail payload (pinned at 38 queries) is untouched. Append-only: there is no
 * edit and no delete. Reading the notes clears the caller's "New note" mark for the case (server-side).
 *
 * `can_add` and `viewer` are SERVED (the window, the side and the assignment are the server's) — the card never
 * derives them. Refusal codes: `writer_only`, `notes_closed`, `bad_body`, `empty_body`, `too_long`.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

/** The side a note was written on, and the side the caller reads from (`reader`: QC and the like, read-only). */
export type NoteSide = 'org_admin' | 'reviewer'
export type NoteViewer = NoteSide | 'reader'

export interface ReviewerNote {
  id: number
  body: string
  author_name: string
  author_role: NoteSide
  is_you: boolean
  created_at: string
}

export interface ReviewerNotes {
  notes: ReviewerNote[]
  viewer: NoteViewer
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

/** The bell line's numbers (#73): how many STUDENTS have a note from the other side the caller has not seen. */
/** The list row's #73 field (`AdminScholarshipListItem` extends this): the other side wrote a note THIS person
 * has not seen (the "New note" mark). */
export interface NewNoteListFields {
  new_note?: boolean
}

export interface NewNoteCount {
  from_reviewer: number
  from_org_admin: number
}

export async function getNewNoteCount(options?: ApiOptions) {
  return adminFetch<NewNoteCount>('/api/v1/admin/scholarship/staff-notifications/count/', options)
}
