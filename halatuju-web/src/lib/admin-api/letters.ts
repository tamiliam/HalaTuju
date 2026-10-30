// Formal letters on a scholar's file, and an organisation's letter wording (student maintenance S6b).
// The server decides who may issue which kind, what a closed file may take, and the typed-name
// check; the page reads `can_issue` / `can_withdraw` and shows what the server refuses.
import { adminFetch, adminMutate, type ApiOptions } from './client'

export type LetterKind = 'general' | 'discipline' | 'suspension' | 'termination' | 'close_out'
export type LetterLanguage = 'en' | 'ms'
/** withdrawn | acknowledged | overdue | awaiting — the server's one judgement. */
export type LetterState = 'withdrawn' | 'acknowledged' | 'overdue' | 'awaiting'

export interface AdminLetter {
  id: number
  kind: LetterKind
  language: LetterLanguage
  subject: string
  body: string
  clause: string
  issued_at: string
  issued_by_name: string
  issued_by_role: string
  response_due_on: string
  emailed_at: string | null
  /** Masked: "a…@gmail.com". Empty until the notice email actually went. */
  emailed_to: string
  acknowledged_at: string | null
  withdrawn_at: string | null
  withdrawn_by_name: string
  withdrawn_reason: string
  state: LetterState
  has_pdf: boolean
}

export interface ScholarLetters {
  letters: AdminLetter[]
  can_issue: LetterKind[]
  can_withdraw: boolean
  /** A termination letter stands and the file is open: show "Close the file?". */
  prompt_close: boolean
  response_days: number
  student_name: string
  default_language: LetterLanguage
  file_closed: boolean
}

export interface LetterDraft {
  kind: LetterKind
  language: LetterLanguage
  clause: string
  note: string
}

export interface LetterPreview {
  subject: string
  body: string
  response_due_on: string
  email: { language: string; subject: string; body: string }
  needs_confirm: boolean
}

export interface LetterTemplateRow {
  key: string
  kind: LetterKind
  language: LetterLanguage
  subject: string
  body: string
  customised: boolean
  placeholders: string[]
  updated_by_email: string
  updated_at: string | null
}

export interface LetterTemplatesPayload {
  organisation: { code: string; name: string }
  templates: LetterTemplateRow[]
  response_days: number
}

const base = (id: number) => `/api/v1/admin/scholarship/scholars/${id}/letters/`

export async function getScholarLetters(id: number, options?: ApiOptions): Promise<ScholarLetters> {
  return adminFetch(base(id), options)
}

export async function previewLetter(id: number, draft: LetterDraft, options?: ApiOptions): Promise<LetterPreview> {
  return adminMutate(`${base(id)}preview/`, 'POST', draft, options)
}

export async function issueLetter(
  id: number, draft: LetterDraft & { confirm_name: string }, options?: ApiOptions,
): Promise<AdminLetter> {
  return adminMutate(base(id), 'POST', draft, options)
}

export async function withdrawLetter(id: number, letterId: number, reason: string, options?: ApiOptions): Promise<AdminLetter> {
  return adminMutate(`${base(id)}${letterId}/withdraw/`, 'POST', { reason }, options)
}

export async function resendLetter(id: number, letterId: number, options?: ApiOptions): Promise<AdminLetter> {
  return adminMutate(`${base(id)}${letterId}/resend/`, 'POST', {}, options)
}

/** A five-minute link, minted on the click only. */
export async function letterPdfLink(id: number, letterId: number, options?: ApiOptions): Promise<{ url: string }> {
  return adminFetch(`${base(id)}${letterId}/pdf/`, options)
}

const TEMPLATES = '/api/v1/admin/scholarship/organisation/letter-templates/'
const q = (org?: string) => (org ? `?org=${encodeURIComponent(org)}` : '')

export async function getLetterTemplates(org?: string, options?: ApiOptions): Promise<LetterTemplatesPayload> {
  return adminFetch(`${TEMPLATES}${q(org)}`, options)
}

export async function saveLetterTemplate(
  patch: { kind: string; language: string; subject?: string; body?: string; reset?: boolean },
  org?: string, options?: ApiOptions,
): Promise<LetterTemplatesPayload> {
  return adminMutate(`${TEMPLATES}${q(org)}`, 'PUT', patch, options)
}
