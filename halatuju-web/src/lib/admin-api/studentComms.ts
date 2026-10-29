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

export interface StudentEmailsPayload {
  organisation: { code: string; name: string }
  /** The platform switch (`MAINTENANCE_REMINDERS_ENABLED`): false = nothing is sent yet. */
  enabled: boolean
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
