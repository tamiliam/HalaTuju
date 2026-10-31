/**
 * Organisation → Mentors (student maintenance S7a, 2026-10-31): the mentors an organisation invited,
 * inviting one, and the staff actions. The rules are the server's (`apps/scholarship/mentor_invite.py`);
 * the screen offers an action only where the row's `manageable` says the endpoint would take it.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

export type MentorStatus = 'active' | 'invited' | 'inactive'
export type MentorFluency = '' | 'conversational' | 'fluent'

export interface MentorRow {
  id: number
  name: string
  email: string
  /** The mentor's own phone (their Profile tells them the inviting organisation sees it); '' if none. */
  phone: string
  status: MentorStatus
  /** The area of mentoring, written by the mentor; '' until they fill in their profile. */
  area: string
  languages: { en: MentorFluency; ms: MentorFluency; ta: MentorFluency }
  /** The optional fourth language's name, only when spoken conversationally or better; else ''. */
  other_language: string
  invited_at: string | null
  signed_in: boolean
  last_seen_at: string | null
  deactivated_at: string | null
  /** May THIS caller act on the row (super, or the organisation admin of its own organisation). */
  manageable: boolean
}

export interface MentorsPayload {
  mentors: MentorRow[]
  counts: Record<MentorStatus, number>
  can_invite: boolean
}

export type MentorAction = 'resend' | 'revoke' | 'deactivate' | 'reactivate'

export async function getMentors(options?: ApiOptions) {
  return adminFetch<MentorsPayload>('/api/v1/admin/mentors/', options)
}

/** Invite a mentor (super or org_admin). Refusals arrive as `code`: `already_staff`, `bad_email`,
 *  `name_required`, `organisation_required`, `not_configured`, `create_failed`. */
export async function inviteMentor(data: { name: string; email: string }, options?: ApiOptions) {
  return adminMutate<{ id: number; mentor: MentorRow; emailed: boolean; message: string }>(
    '/api/v1/admin/invitations/', 'POST', { audience: 'mentor', ...data }, options)
}

/** Resend / Revoke (invited only), Deactivate, Reactivate. Answers the row and `emailed`. */
export async function mentorAction(id: number, action: MentorAction, options?: ApiOptions) {
  return adminMutate<MentorRow & { emailed: boolean | null }>(
    `/api/v1/admin/mentors/${id}/${action}/`, 'POST', {}, options)
}
