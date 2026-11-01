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
  /** S7b: how many scholars this mentor has now (open assignments). */
  scholars_now?: number
  /** S7d: the STAFF role of a staff member who also mentors ("Staff · <role>"); null for a mentor
   *  login. Only Stop mentoring / Mentor again act on such a row; their sign-in is People's. */
  staff_role?: string | null
}

export interface MentorsPayload {
  mentors: MentorRow[]
  counts: Record<MentorStatus, number>
  can_invite: boolean
}

export type MentorAction = 'resend' | 'revoke' | 'deactivate' | 'reactivate' | 'stop' | 'resume'

export async function getMentors(options?: ApiOptions) {
  return adminFetch<MentorsPayload>('/api/v1/admin/mentors/', options)
}

/** Invite a mentor (super or org_admin). Refusals arrive as `code`: `already_staff`, `bad_email`,
 *  `name_required`, `organisation_required`, `not_configured`, `create_failed`. */
export async function inviteMentor(data: { name: string; email: string }, options?: ApiOptions) {
  return adminMutate<{ id: number; mentor: MentorRow; emailed: boolean; message: string }>(
    '/api/v1/admin/invitations/', 'POST', { audience: 'mentor', ...data }, options)
}

/** Resend / Revoke (invited only), Deactivate, Reactivate; S7d — for a STAFF mentor only — Stop
 *  (`stop`, "Stop mentoring") and Mentor again (`resume`). Answers the row and `emailed`. */
/** S7d: a staff member the "Add a staff member as mentor" sheet may offer. */
export interface StaffCandidate {
  id: number
  name: string
  email: string
  role: string
  organisation: string
}

/** S7d: the eligible staff (super / org_admin; org_admin, admin, reviewer, qc of the organisation, not
 *  mentors yet). */
export async function getStaffMentorCandidates(options?: ApiOptions) {
  return adminFetch<{ staff: StaffCandidate[] }>('/api/v1/admin/mentors/staff/', options)
}

/** S7d: add a staff member as a mentor — no email. Refusals arrive as `code`: `not_eligible`,
 *  `already_mentor`, `not_found`. */
export async function addStaffMentor(adminId: number, options?: ApiOptions) {
  return adminMutate<MentorRow>('/api/v1/admin/mentors/staff/', 'POST', { admin_id: adminId }, options)
}

export async function mentorAction(id: number, action: MentorAction, options?: ApiOptions) {
  return adminMutate<MentorRow & { emailed: boolean | null }>(
    `/api/v1/admin/mentors/${id}/${action}/`, 'POST', {}, options)
}
