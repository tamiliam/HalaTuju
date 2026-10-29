/**
 * Student maintenance Sprint 2: the officer's Scholars list, maintenance file and activity log.
 *
 * ⚠ Who may read is the SERVER's (`views_admin/scholars.py` — the Applications rule: see_all reads the
 * organisation, a reviewer only their assigned scholars, finance never). Nothing here decides it.
 * ⚠ Money arrives as a STRING and stays one (the Payments rule) — format at the edge.
 * ⚠ `standing` is the SERVER's (S4a `standing.py`: the latest ACCEPTED result against the
 * organisation's thresholds); the screen must never judge a CGPA itself.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { ClosureReason, MaintenanceSubstate } from './lifecycle'
/** S4a: `standing.py`, from the latest ACCEPTED result and the organisation's thresholds. */
export type ScholarStanding = 'performing' | 'underperforming' | 'failing' | 'not_submitted' | 'awaiting_review'
  | 'no_result_yet'

export interface ScholarResult { cgpa: string | null; semester: string; at: string }
export interface ScholarGift { code: string; name: string }

export interface ScholarRow {
  id: number
  name: string
  gift: ScholarGift | null
  course: string
  institution: string
  status: string
  maintenance_substate: MaintenanceSubstate
  is_on_hold: boolean
  latest_result: ScholarResult | null
  /** A result is waiting for an officer's review. */
  pending_review?: boolean
  standing: ScholarStanding
  /** S4b: her earliest open result term's due date (a past date = late), or null. */
  next_due?: string | null
  mentor: null
  last_activity_at: string | null
}

export interface ScholarSummary {
  in_programme: number
  on_hold: number
  probation: number
  ready_to_close: number
  closed: number
  /** S4a: in maintenance with a latest accepted CGPA under the organisation's minimum. */
  below_minimum: number
  /** S4b: an open result term past its due date and the organisation's grace. */
  results_overdue: number
}

export interface ScholarList {
  summary: ScholarSummary
  count: number
  page: number
  page_size: number
  results: ScholarRow[]
}

export interface ScholarListQuery {
  programme?: string
  closed?: boolean
  substate?: MaintenanceSubstate | ''
  search?: string
  sort?: string
  /** S4a: 'below_minimum' narrows to the Underperforming filter. */
  standing?: 'below_minimum' | 'results_overdue' | ''
  page?: number
  page_size?: number
}

export interface ScholarFile extends Omit<ScholarRow, 'mentor' | 'last_activity_at'> {
  in_maintenance: boolean
  has_file: boolean
  closure_reason: string
  awarded_at: string | null
  vircle_activated_at: string | null
  closed_at: string | null
  money: {
    award_amount: string | null
    paid_to_date: string
    remaining: string | null
    last_payment: { amount: string; at: string } | null
  }
  contract: { exists: boolean; status: string | null }
  /** S4a: the organisation's thresholds the standing was judged by. */
  thresholds?: { minimum: string; failing: string }
  /** S4b: when her next result is due (null: no open term). */
  next_due?: string | null
  mentor: null
  letters: never[]
  last_activity_at: string | null
  /** Maintenance S3: what the header may OFFER this officer (the server judges every request again). */
  controls?: ScholarControls
}

export interface ScholarControls {
  /** S4a: may accept or query a result (a write on the case, while she is in maintenance). */
  can_review_results?: boolean
  /** May write this case and the case takes a sub-state. */
  can_set_substate: boolean
  /** May move it to or from `on_hold` (payments rights — S1 M1). */
  can_hold: boolean
  /** The closure reasons for this status; empty when a close would be refused or is not theirs. */
  close_reasons: ClosureReason[]
  /** 'sponsorship_open' for an awarded case still holding the sponsor's offer (TD-366); '' otherwise. */
  close_refusal: '' | 'sponsorship_open'
}

export type ActivityKind = 'note' | 'call' | 'meeting' | 'email' | 'system'
export interface ScholarActivity {
  id: number
  kind: ActivityKind
  /** A system event code ('' for a manual entry). */
  event: string
  body: string
  meta: Record<string, unknown>
  actor_email: string
  /** Staff-only. Nothing in this log is ever shown to a student today. */
  internal: boolean
  created_at: string
}
export interface ScholarActivityPage {
  count: number
  page: number
  page_size: number
  results: ScholarActivity[]
}

const BASE = '/api/v1/admin/scholarship/scholars/'

export function scholarsQuery(q: ScholarListQuery): string {
  const p = new URLSearchParams()
  if (q.programme) p.set('programme', q.programme)
  if (q.closed) p.set('closed', '1')
  if (q.substate) p.set('substate', q.substate)
  if (q.search?.trim()) p.set('search', q.search.trim())
  if (q.sort) p.set('sort', q.sort)
  if (q.standing) p.set('standing', q.standing)
  if (q.page) p.set('page', String(q.page))
  if (q.page_size) p.set('page_size', String(q.page_size))
  const s = p.toString()
  return s ? `?${s}` : ''
}

export async function getScholars(q: ScholarListQuery, options?: ApiOptions) {
  return adminFetch<ScholarList>(`${BASE}${scholarsQuery(q)}`, options)
}

export async function getScholarFile(id: number, options?: ApiOptions) {
  return adminFetch<ScholarFile>(`${BASE}${id}/`, options)
}

export async function getScholarActivity(id: number, options?: ApiOptions) {
  return adminFetch<ScholarActivityPage>(`${BASE}${id}/activity/`, options)
}

/** S4a — one result on the officer's Results tab: the student's figures, the review, the slip. */
export interface ScholarResultRow {
  id: number
  semester: string
  cgpa: string | null
  graduated: boolean
  note: string
  created_at: string
  review_status: 'pending' | 'accepted' | 'queried'
  review_note: string
  reviewed_by: string
  reviewed_at: string | null
  slip: { url: string | null; filename: string; content_type: string } | null
}

export async function getScholarResults(id: number, options?: ApiOptions) {
  return adminFetch<{ results: ScholarResultRow[] }>(`${BASE}${id}/results/`, options)
}

export async function reviewScholarResult(
  id: number, resultId: number, review: { decision: 'accepted' | 'queried'; note: string },
  options?: ApiOptions,
) {
  return adminMutate<ScholarResultRow>(`${BASE}${id}/results/${resultId}/review/`, 'POST', review, options)
}

export async function addScholarActivity(
  id: number, entry: { kind: 'note' | 'call' | 'meeting'; body: string; internal: boolean },
  options?: ApiOptions,
) {
  return adminMutate<ScholarActivity>(`${BASE}${id}/activity/`, 'POST', entry, options)
}
