/**
 * The read-only Course Data health dashboard: coverage, link failures, and a manual re-check.
 */
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'

// ---- Course Data dashboard (read-only) ----

export interface LinkFailure {
  url: string
  kind: string          // 'gone' | 'dns' | 'timeout' | 'conn' | 'badurl' | …
  detail: string        // HTTP code for 'gone'
  institutions: string[]
  refs: number          // how many catalogue rows use this URL
}

export interface CourseDataStatusEntry {
  last_run_at: string | null
  // counts (numbers) + the link-health 'failures' array; kept loose for forward-compat.
  summary: Record<string, number | string> & { failures?: LinkFailure[] }
  detail: string
}

export interface CourseDataCoverage {
  spm_total: number
  spm_by_source: Record<string, number>
  stpm_total: number
  stpm_active: number
  tvet_have: number
  uptvet_available: number | null
  uptvet_gap: number | null
  emasco_total: number
}

export interface CourseDataStatusResponse {
  statuses: Record<string, CourseDataStatusEntry | null>
  coverage: CourseDataCoverage
}

export async function getCourseDataStatus(options?: ApiOptions): Promise<CourseDataStatusResponse> {
  return adminFetch<CourseDataStatusResponse>('/api/v1/admin/course-data/', options)
}

/** Run the read-only health check (audit + link reachability) now; returns the refreshed status. */
export async function runCourseDataCheck(options?: ApiOptions): Promise<CourseDataStatusResponse> {
  return adminMutate<CourseDataStatusResponse>('/api/v1/admin/course-data/check/', 'POST', {}, options)
}

