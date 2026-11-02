/**
 * A MENTOR's own students (student maintenance S7c, 2026-11-01): My students, one student, and the
 * meeting the mentor logs. Every rule is the server's (`apps/scholarship/mentor_desk.py`): only the
 * caller's CURRENT students are served (anyone else's answers 404), what is served is an allowlist,
 * and a meeting staff logged comes back as date + how only.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { MeetingMode } from './mentoring'
import type { ScholarStanding } from './scholars'
import type { WorkRow } from './development'

export interface HelpAsked { university: boolean; scholarship: boolean; flagged: boolean }

/** The LATEST accepted result only: CGPA and its term. */
export interface MyStudentResult { cgpa: string; semester: string }

export interface MyStudentCard {
  id: number
  name: string
  course: string
  institution: string
  email: string
  phone: string
  since: string
  meetings: number
  last_meeting: string | null
  latest_result: MyStudentResult | null
  standing: ScholarStanding | 'no_result_yet'
  asked_for_help: HelpAsked
}

export interface MyStudents {
  organisation: string
  students: MyStudentCard[]
}

/** A meeting THIS mentor logged comes in full; one staff logged is date + how only (`by_you` false). */
export interface MyMeeting {
  id: number
  met_on: string
  mode: MeetingMode
  by_you: boolean
  minutes?: number | null
  notes?: string
  next_step?: string
  concern?: boolean
}

export interface MyStudent {
  id: number
  name: string
  course: string
  institution: string
  email: string
  phone: string
  since: string
  asked_for_help: HelpAsked
  latest_result: MyStudentResult | null
  standing: ScholarStanding | 'no_result_yet'
  organisation: string
  meetings: MyMeeting[]
  /** S10: their development modules and work, read-only (a short link on an uploaded task). */
  modules?: WorkRow[]
}

export interface MyMeetingBody {
  met_on: string
  mode: MeetingMode
  minutes: number | null
  notes: string
  next_step: string
  concern: boolean
}

const BASE = '/api/v1/admin/mentor/students/'

export async function getMyStudents(options?: ApiOptions) {
  return adminFetch<MyStudents>(BASE, options)
}

/** 404 when this is not (or no longer) one of the caller's current students. */
export async function getMyStudent(id: number, options?: ApiOptions) {
  return adminFetch<MyStudent>(`${BASE}${id}/`, options)
}

/** Refusals as `code`: bad_date, future_date, before_assignment, bad_mode, bad_minutes, notes_required,
 *  too_long, file_closed; 404 when the student is no longer theirs. */
export async function logMyMeeting(id: number, body: MyMeetingBody, options?: ApiOptions) {
  return adminMutate<MyStudent>(`${BASE}${id}/sessions/`, 'POST', body, options)
}
