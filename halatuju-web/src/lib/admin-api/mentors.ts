/**
 * Organisation → Mentors (student maintenance S7a, 2026-10-31): the mentors an organisation invited,
 * inviting one, and the staff actions. The rules are the server's (`apps/scholarship/mentor_invite.py`);
 * the screen offers an action only where the row's `manageable` says the endpoint would take it.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { TeamPersonBlock, TeamTableName } from './admins'
import type { AdminReviewerGift, ReviewerGiftTag } from './reviewers'

export type MentorStatus = 'active' | 'invited' | 'inactive'
export type MentorFluency = '' | 'conversational' | 'fluent'

export interface MentorRow {
  id: number
  name: string
  email: string
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
  // ── Team tables T3 (the Team -> Mentors table; `GET admin/mentors/` and the detail only) ──
  /** The tables this person sits in (`staff_tables.tables`) — the "Also in" chips. */
  tables?: string[]
  /** The organisation admin ("Admin (lead)"). */
  lead?: boolean
  /** Meetings with this mentor whose date is in the last 90 days (today included). */
  meetings_90?: number
  /** The latest meeting's date (YYYY-MM-DD), or null. */
  last_meeting?: string | null
  /** Concerns raised and not marked handled, on files still in maintenance. Null for a caller without
   *  the Scholars list's read key (`scholars` since sprint S1; `see_all` before) — T3 review. */
  concerns_open?: number | null
  /** Sprint T2 (D6): a pure mentor with no assignment, session or concern may be deleted
   *  (`DELETE admin/mentors/<id>/`); false for a staff mentor, deleted from their staff table. */
  deletable?: boolean
  /** T2 review N2: nobody may ever delete this row here — draw no Delete. */
  delete_never?: boolean
  work?: Record<string, number>
  // ── Invitations I4 (2026-11-08): the gifts this mentor mentors in ──
  /** Their gifts, by code. EMPTY means every gift — including gifts started later (`every_gift`).
   *  Absent on an api from before I4: read as every gift. */
  gifts?: ReviewerGiftTag[]
  /** True when they have no gifts named: they may mentor a scholar of any gift. */
  every_gift?: boolean
}

export interface MentorsPayload {
  mentors: MentorRow[]
  counts: Record<MentorStatus, number>
  can_invite: boolean
  /** T3 review: may the caller see the scholar side (the `scholars` key, sprint S1)? False: no concerns, no detail scholars. */
  sees_scholars?: boolean
}

export type MentorAction = 'resend' | 'revoke' | 'deactivate' | 'reactivate' | 'stop' | 'resume'

export async function getMentors(options?: ApiOptions) {
  return adminFetch<MentorsPayload>('/api/v1/admin/mentors/', options)
}

/** Invite a mentor (super or org_admin). Refusals arrive as `code`: `already_staff`, `bad_email`,
 *  `name_required`, `organisation_required`, `not_configured`, `create_failed`; I4: `gift_required`
 *  (not a list) and `not_found` (a gift that is not this organisation's active one).
 *  `programme_ids`: the gifts they will mentor in; `[]` (or absent) = every gift. */
export async function inviteMentor(
  data: { name: string; email: string; programme_ids?: number[] }, options?: ApiOptions,
) {
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

/** Sprint T2 (D6): delete a PURE mentor outright — their sign-in, mentor record and invitations, in
 *  one transaction. Refusals arrive as `code`: `has_work` (409, with `work`), `staff_mentor` (400: a
 *  staff member is deleted from their staff table), `not_found`, `login_cleanup_failed`,
 *  `delete_failed`. */
export async function deleteMentor(id: number, options?: ApiOptions) {
  return adminMutate<{ message: string; login?: string }>(`/api/v1/admin/mentors/${id}/`, 'DELETE',
    undefined, options)
}

/** Team tables T3: one scholar on the mentor detail page — never a meeting note. */
export interface MentorScholarRow {
  application_id: number
  name: string
  since: string | null
  /** Set for a PAST scholar (the mentoring ended). */
  ended: string | null
  meetings: number
  last_meeting: string | null
  /** `standing.py`'s word; null when the student has no maintenance file (e.g. an award reverted). */
  standing: string | null
  has_file: boolean
  /** `open` (not handled, file live), `handled`, `closed` (raised on a file now closed), or null. */
  concern: 'open' | 'handled' | 'closed' | null
}

export interface MentorDetail {
  mentor: MentorRow
  mentoring_since: string | null
  /** T3 review: false for a caller without `scholars` (sprint S1) — then `figures` is null and both lists are empty. */
  sees_scholars: boolean
  figures: null | {
    scholars_now: number
    meetings_90: number
    /** Whole days, per scholar (between each meeting and that scholar's previous one); null = '-'. */
    average_gap_days: number | null
    concerns_raised: number
    concerns_open: number
    last_meeting: string | null
  }
  current: MentorScholarRow[]
  past: MentorScholarRow[]
  /** Sprint T3: the person page's header and Profile tab. */
  person?: TeamPersonBlock
  /** Sprint T3 (D8): the tables THIS viewer may add a mentor's own login to — the Add endpoint's own rule
   *  (`staff_tables_admin.addable_tables`). [] for a staff mentor and for a viewer who may not add. */
  may_add?: TeamTableName[]
  /** I4: the gifts this mentor may be given — every gift of THEIR organisation, ended ones marked.
   *  Absent on an older api: then the details box shows the gifts but offers no edit. */
  programmes?: AdminReviewerGift[]
}

/** Team tables T3: the mentor detail page (super, org_admin, admin; org-fenced — 404 otherwise). */
export async function getMentorDetail(id: number, options?: ApiOptions) {
  return adminFetch<MentorDetail>(`/api/v1/admin/mentors/${id}/`, options)
}

/** Invitations I4: set the WHOLE list of gifts a mentor mentors in (super; org_admin of their own
 *  organisation). `[]` = every gift. Refusals arrive as `code`: `mentor_has_scholars_outside` (409, with
 *  `count` — narrowing never ends a current mentoring), `gift_required`, `not_found`. */
export async function setMentorGifts(
  mentorId: number, programmeIds: number[], options?: ApiOptions,
): Promise<{ id: number; gifts: ReviewerGiftTag[]; every_gift: boolean }> {
  return adminMutate(`/api/v1/admin/mentors/${mentorId}/gifts/`, 'POST',
    { programme_ids: programmeIds }, options)
}
