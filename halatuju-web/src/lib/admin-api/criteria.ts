// The intake's criteria tree, read and saved whole (criteria editor Sprint 3 API,
// halatuju_api apps/scholarship/views_admin/criteria_tree.py). Errors carry `.code`, `.status`
// and (from a save) `.body` - `problems` on bad_criteria, `intake_id` on rule_year_changed.
import { adminFetch, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { CriteriaTree } from '../criteriaTree'

export interface CriteriaPayload {
  intake: { id: number; code: string; name: string; year: number; is_open: boolean }
  /** False until the intake's tree is built on the server; `criteria` is then today's meaning of
   *  the old columns, shown but not saveable (`criteria_not_built`). */
  stored: boolean
  /** Null when the stored tree cannot be read (`rules_error`). */
  criteria: CriteriaTree | null
  rules_error: boolean
  beyond_columns: boolean
  changed?: boolean
  problems?: string[]
  /** A fingerprint of the stored tree. Every save sends it back; when the tree changed since this
   *  answer the save is a 409 `criteria_changed` (another admin saved first) - reload, never overwrite. */
  digest?: string
}

/** One intake year's tree (the Intake year tab). */
export async function getIntakeYearCriteria(id: number, options?: ApiOptions) {
  return adminFetch<CriteriaPayload>(`/api/v1/admin/scholarship/intake-years/${id}/criteria/`, options)
}

export async function saveIntakeYearCriteria(
  id: number, criteria: CriteriaTree, digest: string | undefined, options?: ApiOptions,
) {
  return adminMutate<CriteriaPayload>(
    `/api/v1/admin/scholarship/intake-years/${id}/criteria/`, 'PATCH', { criteria, digest }, options)
}

/** The gift's rule year's tree (the Rules tab): the open year, else the newest. 404
 *  `no_intake_year` when the gift has none. */
export async function getProgrammeCriteria(programmeId: number, options?: ApiOptions) {
  return adminFetch<CriteriaPayload>(`/api/v1/admin/scholarship/programmes/${programmeId}/criteria/`, options)
}

/** `intakeId` is the year the screen showed: a year opened since is a 409 `rule_year_changed`. */
export async function saveProgrammeCriteria(
  programmeId: number, intakeId: number, criteria: CriteriaTree, digest: string | undefined,
  options?: ApiOptions,
) {
  return adminMutate<CriteriaPayload>(
    `/api/v1/admin/scholarship/programmes/${programmeId}/criteria/`, 'PATCH',
    { criteria, intake_id: intakeId, digest }, options)
}
