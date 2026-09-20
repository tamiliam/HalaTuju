/**
 * The PLATFORM's own apply wording, in all three languages at once.
 *
 * ⚠ **SPLIT OUT OF `applyCopy.ts` BY CODE HEALTH H17, AND THE REASON IS A MEASUREMENT.** That
 * module holds two functions: `applyCard`, which is pure and takes the platform wording as an
 * argument, and `platformApplyCard`, which is the only thing in it that reads a message
 * catalogue. Because they shared a file, the three `@/messages/*.json` imports rode into
 * `/scholarship/apply` — a STUDENT-facing page that calls `applyCard` and never calls
 * `platformApplyCard` at all. With the rest of the sprint's saving in place that one page was
 * still 539 kB of first-load JS while every other route had fallen to about 260 kB.
 *
 * Nothing about the words or the rules changed. One pure function moved to a file of its own so
 * that the JSON it needs is paid for by the one screen that needs it.
 *
 * ⚠ **`ApplyCopyTab` MUST REACH THIS THROUGH `import()`**, not a static import, or the three
 * catalogues simply move from the apply page onto `/admin/programme`. `oneLocalePerVisitor.test.ts`
 * asserts both halves.
 */
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

/**
 * The PLATFORM's standard wording for one language, read straight from the message files.
 *
 * ⚠ IT READS THE MESSAGE FILES BY LOCALE, NOT THROUGH `t()`, and that is the point. `t()` answers
 * in the READER's language; the editor has to show what an applicant reading MALAY would get while
 * an administrator works in English. Same source either way — the message files are still the one
 * home for the platform default (`applyCopy.ts`'s docstring), and nothing here duplicates a string.
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
