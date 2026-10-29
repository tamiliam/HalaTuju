/**
 * Student maintenance Sprint 2: the officer's Scholars list, maintenance file and activity log.
 *
 * ⚠ Who may read is the SERVER's (`views_admin/scholars.py` — the Applications rule: see_all reads the
 * organisation, a reviewer only their assigned scholars, finance never). Nothing here decides it.
 * ⚠ Money arrives as a STRING and stays one (the Payments rule) — format at the edge.
 * ⚠ `standing` is only 'no_result_yet' | 'has_result' until Sprint 4 derives the real one from the
 * organisation's settings; the screen must never judge a CGPA itself.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { MaintenanceSubstate } from './lifecycle'
export type ScholarStanding = 'no_result_yet' | 'has_result'

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
  standing: ScholarStanding
  mentor: null
  last_activity_at: string | null
}

export interface ScholarSummary {
  in_programme: number
  on_hold: number
  probation: number
  ready_to_close: number
  closed: number
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
  mentor: null
  letters: never[]
  last_activity_at: string | null
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

export async function addScholarActivity(
  id: number, entry: { kind: 'note' | 'call' | 'meeting'; body: string; internal: boolean },
  options?: ApiOptions,
) {
  return adminMutate<ScholarActivity>(`${BASE}${id}/activity/`, 'POST', entry, options)
}
