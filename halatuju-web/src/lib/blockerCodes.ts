/**
 * The SHAPE of a consent-gate blocker code, shared by the student's consent list
 * (`components/ScholarshipConsent.tsx`) and the officer's Blockers card (`lib/blockers.ts`).
 * A leaf with no i18n keys of its own, so a student route can import it without reaching the
 * admin slice (`messages/__tests__/sliceReach.test.ts`).
 */

// TD-403: codes whose suffix after the colon is a YEAR, not a member — `str_stale:2025` (an earlier
// year's STR). They render the `_year` variant with `{year}`, never a member label.
const YEAR_QUALIFIED = new Set(['str_stale'])

export function isYearQualified(code: string): boolean {
  return YEAR_QUALIFIED.has(code)
}
