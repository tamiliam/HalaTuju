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
export type Reviewer = {
  id: number; name: string; role: string; languages: string[]; assignable?: boolean
  /** The gifts they cover; `[]` (or absent) = EVERY gift. */
  gifts?: ReadonlyArray<{ id: number }>
}
/** What the list's dropdown needs to know about the case (a row of the applications list). */
export type AssignRow = { assigned_to_id: number | null; gift_ids?: number[] }

/** Who the case list's dropdown offers for ONE case (T1-e, owner D7 2026-11-09): the current holder
 *  always (a case is never confiscated by a screen, and a `<select>` must show its own value), plus
 *  everyone the server serves as `assignable` for this caller (the Reviewers table, fenced to an org
 *  admin's own organisation: `may_assign_to`) who COVERS THIS CASE'S GIFT. The list HIDES another
 *  gift's reviewer, where the case page greys them (`officerCockpit.assignOptions`): a row of the
 *  list has no room for a reason. A payload without `assignable` falls back to the old rule (a super
 *  any, an org admin reviewers only), as the case page does.
 *
 *  ⚠ An EMPTY gift list on either side narrows nothing: a reviewer with `gifts` [] covers every
 *  gift, and a case whose gifts are unknown (`gift_ids` [] or absent) hides nobody — the server is
 *  the authority (`gift_mismatch`), and a narrowing we cannot evaluate falls open. */
export function listAssignees(reviewers: Reviewer[], row: AssignRow, isSuper: boolean): Reviewer[] {
  const caseGifts = row.gift_ids ?? []
  return reviewers.filter((rv) => {
    if (rv.id === row.assigned_to_id) return true
    if (!(rv.assignable ?? (isSuper || rv.role === 'reviewer'))) return false
    const gifts = rv.gifts ?? []
    return gifts.length === 0 || caseGifts.length === 0 || gifts.some((g) => caseGifts.includes(g.id))
  })
}
/** Order reviewers for a student's preferred call language: when it's a specific language
 *  (en/ms/ta), reviewers who speak it come first and each carries a match flag; otherwise
 *  ('mixed'/unset) the list is unchanged and nothing is flagged. */
export function orderReviewersFor(reviewers: Reviewer[], lang: string): Array<{ rv: Reviewer; match: boolean; specific: boolean }> {
  const specific = lang === 'en' || lang === 'ms' || lang === 'ta'
  const out = reviewers.map((rv) => ({ rv, match: specific ? rv.languages.includes(lang) : true, specific }))
  if (specific) out.sort((a, b) => Number(b.match) - Number(a.match) || a.rv.name.localeCompare(b.rv.name))
  return out
}
