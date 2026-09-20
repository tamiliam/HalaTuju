/**
 * ONE LOCALE PER VISITOR — the message catalogue loader. (Code health H17, 2026-09-20.)
 *
 * ⚠ **THIS MODULE EXISTS SO THAT `import ta from '@/messages/ta.json'` APPEARS EXACTLY ONCE IN
 * THE APP, INSIDE AN `import()`.** The three catalogues are 1.53 MB of raw JSON (en 372 kB,
 * ms 393 kB, ta 851 kB) and every one of them used to ship to every visitor on every route,
 * because `i18n.tsx` imported all three statically. An English reader downloaded a megabyte of
 * Malay and Tamil to render a page of English.
 *
 * The rule now:
 *
 *  - **English is STATIC.** It is the language the server renders (`getInitialLocale` cannot read
 *    `localStorage` on the server, so SSR has always been English), it is what the first client
 *    paint shows, and it is what `t()` resolves against while another catalogue is still in the
 *    air. Making it lazy too would buy one more round trip and a genuinely blank first paint.
 *  - **Malay and Tamil are `import()`ed**, which is what tells webpack to give each its own chunk.
 *    The two specifiers below are LITERAL on purpose: a computed
 *    `import('@/messages/' + locale + '.json')` makes webpack emit a context module holding
 *    *every* JSON in that folder, which is the bug this sprint is fixing, spelled differently.
 *  - **Loaded catalogues are cached for the life of the tab**, so switching back to a language is
 *    instant and a second `I18nProvider` (the design sandbox mounts its own) shares the fetch.
 *
 * ⚠ **NOT ONE WORD OF ANY LANGUAGE CHANGES HERE, AND NO KEY LEAVES ANY FILE.** All three
 * catalogues keep all ~5,388 keys and the i18n parity guards read them straight off disk. This
 * module changes DELIVERY, not content.
 *
 * ⚠ **A FAILED LOAD MUST NOT STRAND THE READER.** `loadCatalogue` clears its in-flight record on
 * rejection so a retry is possible, and `I18nProvider` falls back to English rather than leaving
 * the switcher stuck — a wrong-language truth beats a screen that will not move (the same rule
 * `applyCopy.ts` states for the gift's own words).
 */
import type { Locale } from '@/lib/branding'

import en from '@/messages/en.json'

/** A parsed message file: nested objects of strings, addressed by dotted path. */
export type Catalogue = Record<string, unknown>

/**
 * English, statically imported — the fallback, the server's render and the first client paint.
 *
 * ⚠ This is the ONE static catalogue import in the application. `oneLocalePerVisitor.test.ts`
 * fails if a second one appears anywhere in production source.
 */
export const FALLBACK_CATALOGUE = en as Catalogue

const loaded: Partial<Record<Locale, Catalogue>> = { en: FALLBACK_CATALOGUE }
const inFlight: Partial<Record<Locale, Promise<Catalogue>>> = {}

/** The catalogue for `locale` if it is already in memory, else `undefined`. Never fetches. */
export function catalogueIfLoaded(locale: Locale): Catalogue | undefined {
  return loaded[locale]
}

/** True once `locale`'s words are in memory. `en` is true from the first line of the bundle. */
export function isCatalogueLoaded(locale: Locale): boolean {
  return loaded[locale] !== undefined
}

/**
 * The catalogue for `locale`, fetching its chunk once if need be.
 *
 * Resolves immediately for a locale already in memory (always the case for `en`), so a caller
 * never has to branch on which language it was handed.
 */
export function loadCatalogue(locale: Locale): Promise<Catalogue> {
  const already = loaded[locale]
  if (already) return Promise.resolve(already)

  const running = inFlight[locale]
  if (running) return running

  // ⚠ Two literal specifiers, never one computed string — see the header.
  const chunk = locale === 'ms'
    ? import('@/messages/ms.json')
    : import('@/messages/ta.json')

  const pending = chunk
    .then((mod) => {
      // webpack/ts-jest hand back a module namespace; the parsed object is its default export.
      const parsed = ((mod as { default?: Catalogue }).default ?? mod) as Catalogue
      loaded[locale] = parsed
      delete inFlight[locale]
      return parsed
    })
    .catch((err) => {
      // Clear the record so a later attempt can genuinely retry rather than re-await a dead promise.
      delete inFlight[locale]
      throw err
    })

  inFlight[locale] = pending
  return pending
}
