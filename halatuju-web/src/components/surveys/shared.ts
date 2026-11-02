/**
 * What the Surveys pages share (student maintenance S9), kept apart so the Results page's chunk does not
 * carry the list and its form.
 */
import type { SurveyRow } from '@/lib/admin-api'

/** The roles the server lets in (`surveys.may_make`); the screens refuse the rest and call nothing. */
export const MAKER_ROLES = ['super', 'org_admin', 'admin']
const K = 'admin.surveys'

type T = (k: string, vars?: Record<string, string>) => string

export function audienceLabel(t: T, row: Pick<SurveyRow, 'programme' | 'audience_count'>): string {
  const count = String(row.audience_count)
  return row.programme ? t(`${K}.forGift`, { name: row.programme.name, count }) : t(`${K}.forAll`, { count })
}

/** A page link that keeps the chosen gift (`?programme=`). */
export function giftHref(path: string, programme?: string): string {
  return programme ? `${path}?programme=${encodeURIComponent(programme)}` : path
}
