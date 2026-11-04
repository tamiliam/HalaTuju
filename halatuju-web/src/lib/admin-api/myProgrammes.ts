/**
 * The Programmes landing's one read (T5c P5, 2026-11-04): the caller's own programmes, with their counts.
 *
 * ⚠ A LEAF, NOT IN THE `admin-api` BARREL. The barrel rides in the first load of most console pages and the
 * bundle-budget median has ~0.1 kB of room; only `ProgrammesLanding` (its own lazy chunk) imports this.
 */
import { adminFetch } from './client'
import type { ApiOptions } from './client'

/**
 * T5c P5: one row of the Programmes landing (`my_programmes.py`), narrowed to the caller.
 * ⚠ A COUNT IS SHOWN ONLY WHEN SERVED: a missing key means "do not show", never zero. Admin-shaped callers get
 * the three gift counts; a reviewer gets `cases` (every case assigned to them, open or done); a mentor gets
 * `scholars` (current mentees). `opens` says where the card goes: the gift's Overview, or My students.
 */
export interface MyProgramme {
  id: number
  code: string
  name_en: string
  name_ms: string
  name_ta: string
  is_active: boolean
  lifecycle: 'active' | 'draft' | 'archived'
  archived: boolean
  opens: 'overview' | 'my_students'
  intake_years?: number
  applications?: number
  awarded?: number
  cases?: number
  scholars?: number
}

/** `every_gift`: the caller sees every programme of the org (admin-shaped), not only those with their work. */
export async function getMyProgrammes(options?: ApiOptions) {
  return adminFetch<{ every_gift: boolean; programmes: MyProgramme[] }>(
    '/api/v1/admin/scholarship/my-programmes/', options)
}
