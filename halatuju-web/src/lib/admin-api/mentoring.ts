/**
 * A scholar's Mentoring tab (student maintenance S7b, 2026-11-01): the current mentor, the change and
 * the end, the meetings staff log. Every rule is the server's (`apps/scholarship/mentoring.py`): the
 * screen offers an action only where `can_act` says the endpoint would take it, and offers the
 * "Email the student" option only where `email_switch_on` says the organisation sends it.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

export type MeetingMode = 'in_person' | 'video' | 'phone'
export type LanguageCode = 'en' | 'ms' | 'ta'

export interface StaffRef { email: string; name: string; role: string }

interface MentorBits {
  mentor_id: number
  name: string
  email: string
  /** Staff always see the mentor's phone ('' when none). */
  phone: string
  area: string
  languages: LanguageCode[]
  other_language: string
  status: 'active' | 'invited' | 'inactive' | ''
}

export interface CurrentMentor extends MentorBits {
  id: number
  since: string
  assigned_by: StaffRef
  meetings: number
  last_meeting: string | null
  /** "You have a mentor" went to the student. */
  emailed: boolean
  /** Review fix: the mentor's login is, by now, the student's own — the tab says "end it". */
  is_the_student?: boolean
}

export interface PastMentor {
  id: number
  mentor_id: number
  name: string
  started_at: string
  ended_at: string
  /** STAFF ONLY: why it ended (typed by staff, or "Mentor deactivated" / "File closed"). */
  end_reason: string
  ended_by: StaffRef
  meetings: number
}

export interface MentoringMeeting {
  id: number
  met_on: string
  mode: MeetingMode
  minutes: number | null
  /** STAFF ONLY. */
  notes: string
  /** STAFF ONLY. */
  next_step: string
  mentor_name: string
  logged_by: StaffRef
  created_at: string
  /** S7c: the MENTOR logged it ("logged by <name> (mentor)"). */
  logged_by_mentor?: boolean
  /** S7c: the mentor raised a concern with this meeting. */
  concern?: boolean
  concern_handled_at?: string | null
  concern_handled_by?: StaffRef | null
}

export interface AssignableMentor {
  id: number
  name: string
  area: string
  languages: LanguageCode[]
  other_language: string
  status: 'active' | 'invited'
  scholars_now: number
}

export interface ScholarMentoring {
  current: CurrentMentor | null
  history: PastMentor[]
  meetings: MentoringMeeting[]
  asked_for_help: { university: boolean; scholarship: boolean; flagged: boolean }
  assignable: AssignableMentor[]
  can_act: boolean
  file_closed: boolean
  email_switch_on: boolean
  /** S7c: the concerns not yet handled ("Mentor concerned"), or null. */
  concern?: { count: number; raised_at: string } | null
  /** Only on an assign's answer: whether "You have a mentor" went. */
  emailed?: boolean | null
}

const base = (id: number) => `/api/v1/admin/scholarship/scholars/${id}/mentoring/`

export async function getScholarMentoring(id: number, options?: ApiOptions) {
  return adminFetch<ScholarMentoring>(base(id), options)
}

/** Assign or change. Refusals arrive as `code`: mentor_not_found, mentor_inactive, own_application,
 *  already_assigned, file_closed, conflict, too_long. */
export async function assignMentor(
  id: number, body: { mentor_id: number; reason: string; email_student: boolean }, options?: ApiOptions,
) {
  return adminMutate<ScholarMentoring>(`${base(id)}assign/`, 'POST', body, options)
}

/** S7c — "Mark as handled": every open concern on this file. Idempotent. Refusals: file_closed. */
export async function handleMentorConcern(id: number, options?: ApiOptions) {
  return adminMutate<ScholarMentoring>(`${base(id)}handle-concern/`, 'POST', {}, options)
}

export async function endMentoring(id: number, body: { reason: string }, options?: ApiOptions) {
  return adminMutate<ScholarMentoring>(`${base(id)}end/`, 'POST', body, options)
}

/** Log a meeting with the CURRENT mentor. Refusals: bad_date, future_date, before_assignment,
 *  bad_mode, bad_minutes, notes_required, too_long, no_mentor, file_closed. */
export async function logMentoringMeeting(
  id: number,
  body: { met_on: string; mode: MeetingMode; minutes: number | null; notes: string; next_step: string },
  options?: ApiOptions,
) {
  return adminMutate<ScholarMentoring>(`${base(id)}sessions/`, 'POST', body, options)
}
