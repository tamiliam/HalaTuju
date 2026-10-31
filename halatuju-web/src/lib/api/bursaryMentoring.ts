// The student's mentor on My Bursary (student maintenance S7b). The student's OWN file only — the server 404s anything
// else. Imported by `components/bursary/BursaryMentoring.tsx` only, so no other route carries it.
import { apiRequest } from './client'
import type { ApiOptions } from './client'

export type MeetingMode = 'in_person' | 'video' | 'phone'

/** The CURRENT mentor, as the server allows the student to see them (`mentoring.student_payload`, an
 *  allowlist): no photo, no notes, no history. `phone` is '' unless the mentor shares it. */
export interface BursaryMentor {
  name: string
  area: string
  /** The en / ms / ta codes the mentor speaks conversationally or better. */
  languages: ('en' | 'ms' | 'ta')[]
  /** A fourth language's name, only when spoken conversationally or better; else ''. */
  other_language: string
  about: string
  email: string
  phone: string
  /** The day the mentor was assigned (YYYY-MM-DD). */
  since: string
}

export interface BursaryMentoring {
  mentor: BursaryMentor | null
  /** The student's meetings with this mentor: the date and how, nothing else. */
  meetings: { met_on: string; mode: MeetingMode }[]
}

export async function getBursaryMentoring(options?: ApiOptions): Promise<BursaryMentoring> {
  return apiRequest('/api/v1/scholarship/bursary/mentoring/', options)
}
