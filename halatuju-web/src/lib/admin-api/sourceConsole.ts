/**
 * The source console — what a signed-in SOURCE user reads, and the one thing it writes (its
 * witness). Source sign-in S3 + S4, 2026-10-30; roadmap `docs/plans/2026-10-30-source-sign-in-roadmap.md`.
 *
 * ⚠ EVERY CALL HERE IS UNDER `admin/source/` AND NOTHING ELSE. The server answers these to a
 * source user only (a super is refused too — there is no impersonation), and refuses a source
 * user every staff endpoint. So a source screen must import from this module and never from the
 * staff modules beside it; `components/source/noStaffCalls.test.tsx` holds the pages to that.
 *
 * Shapes are the allowlists in `halatuju_api/apps/scholarship/source_console.py`, written out by
 * hand: nothing beyond these keys ever reaches a source (no NRIC, income, documents, scores,
 * verdicts, notes or money).
 *
 * `p` is a gift CODE, one of the source's own; absent, the server does not narrow.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

/** The folded stage a source sees — the student's own masked status on the partner emails'
 *  lines (`partner_comms.STAGE_LINES`). The ordered list and its labels live in the pure
 *  `lib/sourceConsole.ts` (a constant here would be emptied by every `jest.mock` of the barrel). */
export type SourceStage =
  | 'not_shortlisted' | 'shortlisted' | 'awaiting_review' | 'under_review' | 'awarded' | 'rejected'
  | 'closed'

export interface SourceGift { code: string; name: string }

/** The signing chain — dates only. `can_witness`: this contract waits for THIS source's witness
 *  (the server's one predicate, `source_console.can_witness`). */
export interface SourceContract {
  status: 'draft' | 'student_signed' | 'binds' | 'countersigned' | 'executed'
  student_signed_at: string | null
  guarantor_signed_at: string | null
  witness_signed_at: string | null
  foundation_signed_at: string | null
  witness_is_you: boolean
  can_witness: boolean
}

export interface SourceProfile {
  user: { name: string; email: string }
  source: {
    name: string; code: string; contact_person: string; contact_email: string; phone: string
    organisation: string
  }
}

export interface SourceOverview {
  programme: SourceGift | null
  counts: Record<SourceStage, number> & { total: number }
  scholars: number
  witness_waiting: { application_id: number; student_name: string }[]
  missing_items: { application_id: number; student_name: string; applied: string | null
                   last_activity: string | null }[]
}

export interface SourceApplicationRow {
  id: number
  student_name: string
  school: string
  state: string
  /** `spm` / `stpm` / `matric` / `asasi` / `diploma` / '' */
  level: string
  programme: SourceGift | null
  submitted_at: string | null
  stage: SourceStage
}

interface Paged { count: number; total_pages: number; page: number; page_size: number
                  next: string | null; previous: string | null }

export interface SourceApplicationList extends Paged { applications: SourceApplicationRow[] }

/** One application. A LISTED one (its student named this source) carries the profile basics; a
 *  case this source only WITNESSES (`witness_only`, another source's student) carries the
 *  contract task and nothing else. */
export type SourceApplication =
  | (SourceApplicationRow & {
      kind: 'listed'; phone: string; email: string; told_at: string | null
      missing_items: string[]; contract: SourceContract | null
    })
  | { id: number; kind: 'witness_only'; student_name: string; programme: SourceGift | null
      contract: SourceContract | null }

/** The full contract, to the witness source only. `pdf_url` is null unless asked for with
 *  `link` — a five-minute link, minted on a click. */
export interface SourceAgreement extends SourceContract {
  application_id: number
  student_name: string
  pdf_url: string | null
  pdf_expires_in: number
  rendered: false
}

export interface SourceScholarRow {
  id: number
  student_name: string
  programme: SourceGift | null
  institution: string
  course: string
  /** What the student sees: awarded / active / maintenance / closed. */
  status: string
  contract_stage: SourceContract['status'] | null
}

export interface SourceScholarList extends Paged { scholars: SourceScholarRow[] }

export interface SourceScholar extends SourceScholarRow {
  phone: string; email: string; contract: SourceContract | null
}

const query = (params: Record<string, string | number | undefined>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

const BASE = '/api/v1/admin/source'

export async function getSourceProfile(options?: ApiOptions) {
  return adminFetch<SourceProfile>(`${BASE}/profile/`, options)
}

/** Own name, and the source's name / contact person / contact email / phone. Anything else is
 *  400 `not_editable`. Answers with the GET payload. */
export async function updateSourceProfile(
  data: { user?: { name: string }; source?: Partial<Omit<SourceProfile['source'], 'code' | 'organisation'>> },
  options?: ApiOptions,
) {
  return adminMutate<SourceProfile>(`${BASE}/profile/`, 'PATCH', data, options)
}

export async function getSourceOverview(p?: string, options?: ApiOptions) {
  return adminFetch<SourceOverview>(`${BASE}/overview/${query({ p })}`, options)
}

export async function getSourceApplications(
  params: { p?: string; q?: string; stage?: string; page?: number; page_size?: number },
  options?: ApiOptions,
) {
  return adminFetch<SourceApplicationList>(`${BASE}/applications/${query(params)}`, options)
}

export async function getSourceApplication(id: number | string, options?: ApiOptions) {
  return adminFetch<SourceApplication>(`${BASE}/applications/${id}/`, options)
}

export async function getSourceAgreement(
  id: number | string, options?: ApiOptions & { link?: boolean },
) {
  return adminFetch<SourceAgreement>(
    `${BASE}/applications/${id}/agreement/${options?.link ? '?link=1' : ''}`, options)
}

/** Record this source's witness: the typed full name and the confirmation tick. */
export async function witnessAsSource(
  id: number | string, data: { witness_name: string; confirm: boolean }, options?: ApiOptions,
) {
  return adminMutate<SourceAgreement>(`${BASE}/applications/${id}/witness/`, 'POST', data, options)
}

export async function getSourceScholars(
  params: { p?: string; page?: number; page_size?: number }, options?: ApiOptions,
) {
  return adminFetch<SourceScholarList>(`${BASE}/scholars/${query(params)}`, options)
}

export async function getSourceScholar(id: number | string, options?: ApiOptions) {
  return adminFetch<SourceScholar>(`${BASE}/scholars/${id}/`, options)
}
