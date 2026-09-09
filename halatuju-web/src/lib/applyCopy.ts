/**
 * Which words does the apply page show — the gift's own, or the platform's?
 *
 * ⚠ THE PLATFORM DEFAULT LIVES IN THE MESSAGE FILES, NOT HERE and not in Python. Putting the
 * seven `scholarship.apply.*` strings x 3 languages into the server as well is the
 * `_SUBJECT_BM` <-> `subjects.ts` drift trap, recorded three times in `lessons.md`. The server
 * answers WHICH GIFT; this answers whether that gift has anything to say.
 *
 * ⚠ ALL-OR-NOTHING, AND THE SERVER ALREADY GUARANTEES IT (`apply_copy.normalise`). A gift either
 * supplies title + intro + at least one bullet, or nothing. Per-FIELD mixing would render the
 * platform's "Apply for B40 Education Assistance" above Sabah's own criteria — one gift's
 * heading over another gift's terms, with nothing failing. Do not "improve" this into a
 * field-by-field merge.
 */
import type { ApplyCopyBlock } from './api'
import type { Locale } from './branding'

export interface ApplyCard {
  title: string
  intro: string
  criteria: string[]
  /** True when these are the GIFT's own words. Only tests and the tab care. */
  fromGift: boolean
}

export type ServedCopy = Partial<Record<Locale, ApplyCopyBlock>> | undefined | null

/**
 * `served` is the intake endpoint's `apply_copy`; `platform` is what `t()` resolved from the
 * message files for this reader.
 *
 * ⚠ ms/ta FALL BACK TO THE GIFT'S OWN ENGLISH, NEVER TO THE PLATFORM'S MALAY OR TAMIL. The
 * server folds that already; the arm here is the belt to its braces, and it is NOT the same
 * rule `branding.resolveLang` uses (that falls back per locale to the platform). Falling back to
 * the platform's *name* is harmless; falling back to the platform's *criteria* would tell a
 * Malay-reading Sabah applicant they must be B40 with five A's. A wrong-language truth beats a
 * right-language falsehood.
 */
export function applyCard(served: ServedCopy, locale: Locale, platform: {
  title: string
  intro: string
  criteria: string[]
}): ApplyCard {
  const block = served?.[locale] ?? served?.en
  const criteria = (block?.criteria ?? []).filter(c => (c || '').trim())
  if (block && block.title && block.intro && criteria.length) {
    return { title: block.title, intro: block.intro, criteria, fromGift: true }
  }
  return { ...platform, fromGift: false }
}
