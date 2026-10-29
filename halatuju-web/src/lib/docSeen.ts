/**
 * The plain words for a genuineness `doc_seen` code (M4b review nit, 2026-10-30).
 *
 * The api stores what a genuineness scorer recognised a page as — a family code such as
 * `matric_result_slip` or `stpm_online_results_page` — and the reviewer's interview question
 * ("… it looks like {seen}") used to print that code raw. Every code a scored document type can
 * store is listed here with a label in en / ms / ta (`admin.scholarship.docSeen.<code>`); a code not
 * listed reads as "another kind of document", so a raw code never reaches the reviewer. A value that
 * is not a code at all (free words from an older read) is shown as it is.
 *
 * The list is pinned to the api's own constants by `docSeen.test.ts` (a drift test).
 */
export const DOC_SEEN_CODES = [
  // results_doc families (SPM slip / certificate, birth certificate, EPF, STR)
  'results_slip', 'certificate', 'birth_certificate', 'epf', 'str_letter', 'str_dashboard', 'str_semakan',
  // stpm_doc (STPM S3) + its ruling-1A page
  'stpm_slip', 'stpm_certificate', 'stpm_online_results_page',
  // matric_poly_doc (M4 / M4b)
  'matric_transcript', 'poly_transcript', 'matric_result_slip', 'poly_result_slip', 'poly_portal_page',
  'matric_transcript_not_final', 'poly_transcript_not_final', 'matric_offer_letter',
] as const

const KNOWN = new Set<string>(DOC_SEEN_CODES)
const CODE_SHAPE = /^[a-z0-9_]+$/

type Translate = (key: string, params?: Record<string, string>) => string

export function docSeenLabel(t: Translate, seen: string | undefined | null): string {
  const s = (seen || '').trim()
  if (KNOWN.has(s)) return t(`admin.scholarship.docSeen.${s}`)
  if (!s || CODE_SHAPE.test(s)) return t('admin.scholarship.docSeen.other')
  return s
}

/** An anomaly's params as strings for its i18n copy, with a `seen` code put into plain words. */
export function anomalyParams(t: Translate, params: Record<string, unknown>): Record<string, string> {
  const p = Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]))
  return 'seen' in p ? { ...p, seen: docSeenLabel(t, p.seen) } : p
}
