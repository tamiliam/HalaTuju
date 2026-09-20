/**
 * Sponsor terms authoring (T2): the sections, the generated quiz, validation, publishing,
 * the .docx import and the preview.
 */
import { API_BASE, adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ── Sponsor terms (T2) ───────────────────────────────────────────────────────
// The versioned document a sponsor accepts. Authoring only — nothing here is sponsor-facing.

export interface SponsorTermsSection {
  order: number
  heading_en: string; heading_ms: string; heading_ta: string
  body_en: string; body_ms: string; body_ta: string
  is_quiz_candidate: boolean
  /** `{tag, plain, question, options[3], correct, why}` — the same shape the student quiz uses. */
  quiz_en: SponsorQuizPayload
  quiz_ms: SponsorQuizPayload
  quiz_ta: SponsorQuizPayload
  /** Blank = hand-written. Otherwise the model that drafted it. */
  quiz_generated_model: string
}

export interface SponsorQuizPayload {
  tag?: string
  plain?: string
  question?: string
  options?: string[]
  correct?: number
  why?: string
}

export interface SponsorTermsSummary {
  id: number
  version: string
  status: 'draft' | 'active' | 'archived'
  title_en: string
  /** Locales servable WHOLE — the table's Languages column. */
  languages_available: string[]
  section_count: number
  created_by_email: string
  published_by_email: string
  published_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface SponsorTermsDetail extends SponsorTermsSummary {
  title_ms: string; title_ta: string
  intro_en: string; intro_ms: string; intro_ta: string
  sections: SponsorTermsSection[]
  acceptance_count: number
}

export interface SponsorTermsRule { code: string; label: string }
export interface SponsorTermsValidation {
  ok: boolean
  errors: SponsorTermsRule[]
  warnings: SponsorTermsRule[]
}

export interface SponsorTermsListPayload {
  versions: SponsorTermsSummary[]
  active_version: string
  sponsor_count: number
}

const ST = '/api/v1/admin/scholarship/sponsor-terms'

export async function getSponsorTermsList(options?: ApiOptions): Promise<SponsorTermsListPayload> {
  return adminFetch(`${ST}/`, options)
}

export async function getSponsorTerms(id: number, options?: ApiOptions): Promise<SponsorTermsDetail> {
  return adminFetch(`${ST}/${id}/`, options)
}

export async function createSponsorTerms(
  body: { version: string; copy_from?: number },
  options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/`, 'POST', body, options)
}

export async function updateSponsorTermsIntro(
  id: number,
  patch: Partial<Pick<SponsorTermsDetail,
    'title_en' | 'title_ms' | 'title_ta' | 'intro_en' | 'intro_ms' | 'intro_ta'>>,
  options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/`, 'PATCH', patch, options)
}

export async function putSponsorTermsSections(
  id: number,
  sections: Array<Partial<SponsorTermsSection>>,
  options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/sections/`, 'PUT', { sections }, options)
}

export async function generateSponsorTermsQuiz(
  id: number, order: number, options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/sections/${order}/generate-quiz/`, 'POST', {}, options)
}

export async function validateSponsorTerms(
  id: number, options?: ApiOptions,
): Promise<SponsorTermsValidation> {
  return adminFetch(`${ST}/${id}/validate/`, options)
}

export async function publishSponsorTerms(
  id: number, options?: ApiOptions,
): Promise<SponsorTermsDetail> {
  return adminMutate(`${ST}/${id}/publish/`, 'POST', {}, options)
}

/**
 * Propose a flat section list from an author's .docx. PROPOSAL ONLY — nothing is saved, and the
 * upload is never retained. Sub-clauses fold into their parent's body (owner, 2026-07-28).
 */
export async function importSponsorTermsDocx(
  id: number, file: File, options?: ApiOptions,
): Promise<{
  title: string
  intro: string
  sections: Array<Pick<SponsorTermsSection, 'heading_en' | 'body_en' | 'is_quiz_candidate' | 'quiz_en'>>
}> {
  const headers: Record<string, string> = {}
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}${ST}/${id}/import-docx/`, {
    method: 'POST', headers, body: form,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Import failed: ${res.status}`) as Error & { code?: string }
    err.code = b.error || ''
    throw err
  }
  return res.json()
}

export async function previewSponsorTerms(
  id: number, locale: string, options?: ApiOptions,
): Promise<{
  document: {
    version: string; locale_used: string; title: string; intro: string
    sections: Array<{ order: number; heading: string; body: string; has_quiz: boolean }>
  }
  checkpoints: Array<SponsorQuizPayload & { order: number }>
}> {
  return adminFetch(`${ST}/${id}/preview/?locale=${encodeURIComponent(locale)}`, options)
}

