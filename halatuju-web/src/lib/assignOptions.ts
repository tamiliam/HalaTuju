/**
 * The case list's assignment helpers, lifted out of `app/admin/scholarship/page.tsx` unchanged (Mobile M6a,
 * to keep the page under the 600-line standard). The phone rows and the desktop table both read them.
 */

/** The bucket badge's tone: A positive, B caution, anything else neutral. */
export const bucketBadge = (b: string) =>
  b === 'A' ? 'bg-positive-100 text-positive-700'
    : b === 'B' ? 'bg-caution-100 text-caution-700'
      : 'bg-ground-100 text-ground-500'

// ── Reviewer language matching (assignment dropdown) ───────────────────────────
// The "Prefers …" note shows only for a SPECIFIC preferred call language (en/ms/ta — 'mixed'/''
// show nothing). Its displayed name reuses the shared scholarship.apply.callLang.* keys so it
// reads "Prefers Tamil", never a bare code; the dropdown options show ✓/⚠ + the reviewer's name
// only — the language-code suffix was dropped (owner 2026-07-16).
export const SPECIFIC_CALL_LANGS = new Set(['en', 'ms', 'ta'])
export type Reviewer = { id: number; name: string; role: string; languages: string[]; assignable?: boolean }
/** Order reviewers for a student's preferred call language: when it's a specific language
 *  (en/ms/ta), reviewers who speak it come first and each carries a match flag; otherwise
 *  ('mixed'/unset) the list is unchanged and nothing is flagged. */
export function orderReviewersFor(reviewers: Reviewer[], lang: string): Array<{ rv: Reviewer; match: boolean; specific: boolean }> {
  const specific = lang === 'en' || lang === 'ms' || lang === 'ta'
  const out = reviewers.map((rv) => ({ rv, match: specific ? rv.languages.includes(lang) : true, specific }))
  if (specific) out.sort((a, b) => Number(b.match) - Number(a.match) || a.rv.name.localeCompare(b.rv.name))
  return out
}
