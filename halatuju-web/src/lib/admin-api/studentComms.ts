// Organisation → Settings → Student communications (student maintenance S4b): the organisation's
// wording for the emails a FUNDED student receives about her results, per kind and language.
// The server fences it to the caller's own organisation (`?org=` only for a super with several).
import { adminFetch, adminMutate, type ApiOptions } from './client'

export type StudentEmailKind = 'results_due' | 'results_overdue' | 'result_queried'
export type StudentEmailLanguage = 'en' | 'ms' | 'ta'

export interface StudentEmailTemplate {
  /** `${kind}.${language}` — the row's identity, and the `kind` the shared TemplateEditor keys on. */
  key: string
  kind: StudentEmailKind
  language: StudentEmailLanguage
  subject: string
  body: string
  /** True when the organisation has its own wording; false = the platform default. */
  customised: boolean
  placeholders: string[]
  updated_by_email: string
  updated_at: string | null
}

/** The headings the page reads, in order (`student_email_catalogue.GROUPS`). */
export type StudentEmailGroup = 'account' | 'applying' | 'interview' | 'award' | 'results' | 'closure'

/** One email a student receives (S6a) — every field decided by the server, the page only reads it. */
export interface StudentEmailRow {
  key: string
  group: StudentEmailGroup
  /** `en_ms_ta`: one email in her language; `en_ms`: English, or English with a Malay copy, in one email. */
  languages: 'en_ms_ta' | 'en_ms' | 'en'
  /** The organisation writes its own wording (the `templates` rows with this `kind`). */
  editable: boolean
  /** On the owner's safe list: the organisation may switch it off. */
  switchable: boolean
  /** This organisation's switch; always true for an email that is not switchable. */
  enabled: boolean
  /** Why it cannot be switched off (a reason code) — null when switchable. */
  lock: string | null
  platform_flag: string | null
  /** False when a platform flag holds it back whatever the switch says. */
  platform_on: boolean
  /** False when "last sent" cannot be read per organisation. */
  tracked: boolean
  last_sent_at: string | null
  /** Set when the email is worded and switched on another screen (`sources`). */
  managed_on: string | null
  /** The wording as sent, per language, tokens left in place ({} when written in code). */
  wording: Partial<Record<StudentEmailLanguage, { subject: string; body: string }>>
}

export interface StudentEmailsPayload {
  organisation: { code: string; name: string }
  /** The platform switch (`MAINTENANCE_REMINDERS_ENABLED`): false = nothing is sent yet. */
  enabled: boolean
  groups: StudentEmailGroup[]
  catalogue: StudentEmailRow[]
  templates: StudentEmailTemplate[]
}

const BASE = '/api/v1/admin/scholarship/organisation/student-emails/'
const q = (org?: string) => (org ? `?org=${encodeURIComponent(org)}` : '')

export async function getStudentEmails(org?: string, options?: ApiOptions): Promise<StudentEmailsPayload> {
  return adminFetch(`${BASE}${q(org)}`, options)
}

export async function saveStudentEmail(
  patch: { kind: string; language: string; subject?: string; body?: string; reset?: boolean },
  org?: string, options?: ApiOptions,
): Promise<StudentEmailsPayload> {
  return adminMutate(`${BASE}${q(org)}`, 'PUT', patch, options)
}

/** Switch one of the SAFE emails on or off for this organisation. A locked one is refused by the
 *  server (400 `not_switchable`); the page never decides that itself. */
export async function setStudentEmailSwitch(
  key: string, enabled: boolean, org?: string, options?: ApiOptions,
): Promise<StudentEmailsPayload> {
  return adminMutate(`${BASE}switch/${q(org)}`, 'POST', { key, enabled }, options)
}
