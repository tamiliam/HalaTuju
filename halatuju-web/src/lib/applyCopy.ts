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
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

/** The `scholarship.apply.*` block per language — the one home for the platform default. */
const MESSAGES: Record<Locale, Record<string, string>> = {
  en: (en as never)['scholarship']['apply'],
  ms: (ms as never)['scholarship']['apply'],
  ta: (ta as never)['scholarship']['apply'],
}

export interface ApplyCard {
  title: string
  intro: string
  criteria: string[]
  /** True when these are the GIFT's own words. Only tests and the tab care. */
  fromGift: boolean
}

export type ServedCopy = Partial<Record<Locale, ApplyCopyBlock>> | undefined | null

/**
 * The PLATFORM's standard wording for one language, read straight from the message files.
 *
 * ⚠ IT READS THE MESSAGE FILES BY LOCALE, NOT THROUGH `t()`, and that is the point. `t()` answers
 * in the READER's language; the editor has to show what an applicant reading MALAY would get while
 * an administrator works in English. Same source either way — the message files are still the one
 * home for the platform default (this module's docstring), and nothing here duplicates a string.
 *
 * ⚠ THE BULLETS ARE `criteria1..N`, read until one is missing. A hard-coded four would silently
 * drop a fifth the day somebody adds one.
 */
export function platformApplyCard(locale: Locale): {
  title: string; intro: string; criteria: string[]
} {
  const bundle = MESSAGES[locale] ?? MESSAGES.en
  const criteria: string[] = []
  for (let n = 1; ; n += 1) {
    const line = bundle[`criteria${n}`]
    if (!line) break
    criteria.push(line)
  }
  return { title: bundle.title ?? '', intro: bundle.intro ?? '', criteria }
}

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
