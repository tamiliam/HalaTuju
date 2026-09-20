/**
 * The contract module (S4): org-owned versioned bursary templates — clauses, schedule, quiz,
 * vetting, validation, submit, revert, deploy, and the HTML/PDF previews.
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Contract module (S4) — org-owned versioned bursary templates ───────────────
export type ContractStatus = 'draft' | 'pending_deployment' | 'active' | 'archived'

export interface ContractQuizPayload {
  tag?: string; plain?: string; question?: string
  options?: string[]; correct?: number; why?: string
}

export interface ContractClauseData {
  order: number
  level: number   // 0 clause, 1 sub-clause, 2 sub-sub-clause (numbers computed from the level run)
  heading_en: string; heading_ms: string; heading_ta: string
  body_en: string; body_ms: string; body_ta: string
  is_quiz_candidate: boolean
  quiz_en: ContractQuizPayload; quiz_ms: ContractQuizPayload; quiz_ta: ContractQuizPayload
  quiz_generated_model: string
}

export interface ContractScheduleRowData {
  pathway: string; variant: string
  label_en: string; label_ms: string; label_ta: string
  monthly_amount: string; start_month: number
  paid_offsets: number[]; sort_order: number
  months: number; total: string
}

export interface ContractTemplateSummary {
  id: number; organisation: string; version: string; status: ContractStatus
  languages_available: string[]
  vetted_by_name: string; vetted_on: string | null
  deployed_by_at: string | null; created_at: string; updated_at: string
}

export interface ContractTemplateDetail extends ContractTemplateSummary {
  title_en: string; title_ms: string; title_ta: string
  preamble_en: string; preamble_ms: string; preamble_ta: string
  progress_standard_en: string; progress_standard_ms: string; progress_standard_ta: string
  counterparty_name: string; counterparty_title: string; counterparty_nric: string
  counterparty_address: string
  counterparty_notify_emails: string[]
  parent_role: 'co_signer_all' | 'minor_only'
  parent_pin_required: boolean
  witness_policy: 'none' | 'optional' | 'required'
  vetting_attested_by_email: string; vetting_attested_at: string | null
  created_by_email: string; submitted_by_email: string; submitted_by_at: string | null
  deployed_by_email: string; archived_at: string | null
  clauses: ContractClauseData[]
  schedule: ContractScheduleRowData[]
}

export interface ContractValidation {
  ok: boolean
  errors: Array<{ code: string; label: string }>
  warnings: Array<{ code: string; label: string }>
}

const CT = '/api/v1/admin/scholarship/contract-templates'

export async function getContractTemplates(organisation?: string, options?: ApiOptions) {
  const q = organisation ? `?organisation=${encodeURIComponent(organisation)}` : ''
  return adminFetch<{ templates: ContractTemplateSummary[] }>(`${CT}/${q}`, options)
}
export async function createContractTemplate(
  body: { version: string; organisation?: string; copy_from?: number }, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/`, 'POST', body, options)
}
export async function getContractTemplate(id: number, options?: ApiOptions) {
  return adminFetch<ContractTemplateDetail>(`${CT}/${id}/`, options)
}
export async function updateContractConfig(id: number, patch: Record<string, unknown>, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/`, 'PATCH', patch, options)
}
export async function putContractClauses(
  id: number, clauses: Array<Partial<ContractClauseData>>, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/clauses/`, 'PUT', { clauses }, options)
}
export async function putContractSchedule(
  id: number, rows: Array<Partial<ContractScheduleRowData>>, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/schedule/`, 'PUT', { rows }, options)
}
export async function generateContractQuiz(id: number, order: number, options?: ApiOptions) {
  return adminMutate<ContractClauseData>(`${CT}/${id}/clauses/${order}/generate-quiz/`, 'POST', {}, options)
}
export async function recordContractVetting(
  id: number, body: { vetted_by_name: string; vetted_on: string }, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/vetting/`, 'POST', body, options)
}
export async function getContractValidation(id: number, options?: ApiOptions) {
  return adminFetch<ContractValidation>(`${CT}/${id}/validate/`, options)
}
export async function submitContractTemplate(id: number, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/submit/`, 'POST', {}, options)
}
export async function revertContractTemplate(id: number, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/revert/`, 'POST', {}, options)
}
export async function deployContractTemplate(id: number, options?: ApiOptions) {
  return adminMutate<ContractTemplateDetail>(`${CT}/${id}/deploy/`, 'POST', {}, options)
}
export async function getContractQuizPreview(id: number, locale: string, options?: ApiOptions) {
  return adminFetch<{ template_version: string; locale_used: string; checkpoints: ContractQuizPayload[] }>(
    `${CT}/${id}/quiz-preview/?locale=${encodeURIComponent(locale)}`, options)
}
/** The rendered preview HTML (for an iframe srcDoc). Auth header required. */
export async function fetchContractPreviewHtml(id: number, locale: string, options?: ApiOptions): Promise<string> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${CT}/${id}/preview/?locale=${encodeURIComponent(locale)}`, { headers })
  if (!res.ok) throw new Error(`Preview failed: ${res.status}`)
  return res.text()
}
/** Import a .docx → a PROPOSED [{heading, body, level}] clause list (nothing saved; file not retained). */
export async function importContractDocx(
  id: number, file: File, options?: ApiOptions): Promise<{
    clauses: Array<{ heading: string; body: string; level: number }>
    title: string; preamble: string
    counterparty?: { name?: string; nric?: string; address?: string }
  }> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}${CT}/${id}/import-docx/`, { method: 'POST', headers, body: form })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Import failed: ${res.status}`) as Error & { status?: number; code?: string }
    err.status = res.status
    err.code = b.code || b.error || ''
    throw err
  }
  return res.json()
}

/** The rendered preview PDF as a Blob (auth header required) — for a client-side open.
 *  Uses ?output=pdf, NOT ?format=pdf — `format` is DRF's reserved content-negotiation
 *  param and `?format=pdf` 404s before the view runs (TD-163). */
export async function fetchContractPreviewPdf(id: number, locale: string, options?: ApiOptions): Promise<Blob> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${CT}/${id}/preview/?locale=${encodeURIComponent(locale)}&output=pdf`, { headers })
  if (!res.ok) throw new Error(`Preview PDF failed: ${res.status}`)
  return res.blob()
}

