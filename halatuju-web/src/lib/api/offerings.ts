/**
 * WHERE EACH COURSE OF ONE PATHWAY IS TAUGHT — the scholarship "My Plans" pickers' catalogue
 * (`GET /api/v1/courses/offerings/?pathway=`, Scholarship My Plans redesign, 2026-10-30).
 *
 * UNFILTERED: every course of the pathway, Bumiputera-only and inactive ones included. The
 * student's results never reach this call; "Eligible only" narrows it in the browser, opt-in.
 * One pathway per call, kept for the visit — a picker downloads only the pathway it draws.
 */
import { apiRequest } from './client'

export interface OfferingInstitution {
  /** The grouping key (the institution id; a degree's unlinked university falls back to its name). */
  id: string
  /** The real `Institution` key — '' for a degree whose university the catalogue has not linked. */
  institution_id: string
  /** The catalogue spelling, which the offer-letter comparison reads. */
  name: string
  state: string
  course_ids: string[]
}

export interface OfferingCourse {
  course_id: string
  course_name: string
  field_key: string
  aliran: string | null   // PISMP only: the school type (sk / sjkc / sjkt / khas)
}

export interface PathwayOfferings {
  pathway: string
  institutions: OfferingInstitution[]
  courses: OfferingCourse[]
}

// ⚠ Made on first use, never at module level: a top-level `new Map()` is a side effect to the
// bundler, so every route that imports the `@/lib/api` barrel would carry this module — and the
// chunk split it causes put ~3 kB on every route (measured 2026-10-30).
let memo: Map<string, Promise<PathwayOfferings>> | undefined

export function getPathwayOfferings(pathway: string): Promise<PathwayOfferings> {
  memo ??= new Map()
  const hit = memo.get(pathway)
  if (hit) return hit
  const req = apiRequest<PathwayOfferings>(`/api/v1/courses/offerings/?pathway=${encodeURIComponent(pathway)}`)
  memo.set(pathway, req)
  req.catch(() => memo?.delete(pathway))   // a failed fetch may be asked again
  return req
}
