/**
 * ONE LOCALE PER VISITOR — the message catalogue loader. (Code health H17, 2026-09-20; sliced by
 * audience in TD-360 Sprint 1, 2026-10-21.)
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
 *  - **Malay and Tamil are `import()`ed** (in `lib/messageChunks.ts`, the network edge), which is
 *    what tells webpack to give each its own chunk. The specifiers are LITERAL on purpose: a computed
 *    `import('@/messages/' + locale + '.json')` makes webpack emit a context module holding
 *    *every* JSON in that folder, which is the bug this sprint is fixing, spelled differently.
 *  - **Loaded catalogues are cached for the life of the tab**, so switching back to a language is
 *    instant and a second `I18nProvider` (the design sandbox mounts its own) shares the fetch.
 *
 * ── TD-360: EACH LANGUAGE IS DELIVERED IN SLICES ────────────────────────────────────────────
 * `?slice=core` / `?slice=admin` are cut at BUILD time by `scripts/messages-slice-loader.js`:
 * `admin` is the `admin` namespace (the console's words, more than half of every file) and `core`
 * is every other namespace, so a namespace added tomorrow can never go missing from a route.
 *
 *  - This module statically imports English CORE only. The English admin slice is imported by
 *    `lib/messagesAdmin.ts`, which only the admin and sandbox layouts load; it merges itself into
 *    this same English object and marks `admin` REQUIRED.
 *  - `loadCatalogue(locale)` loads every REQUIRED slice of that locale (core, plus admin once an
 *    admin layout has loaded), in parallel, and merges them into ONE catalogue object per locale.
 *    `catalogueIfLoaded` answers only when every required slice is in.
 *  - A slice arriving later (the admin slice of a language already on screen) is merged into the
 *    SAME object and announced through `subscribeCatalogues`, so the provider re-renders.
 *
 * ⚠ **NOT ONE WORD OF ANY LANGUAGE CHANGES HERE, AND NO KEY LEAVES ANY FILE.** All three
 * catalogues keep all ~5,400 keys and the i18n parity guards read them straight off disk. This
 * module changes DELIVERY, not content.
 *
 * ⚠ **A FAILED LOAD MUST NOT STRAND THE READER.** Every in-flight record is cleared on rejection
 * so a retry is possible, and `I18nProvider` falls back to English rather than leaving the
 * switcher stuck — a wrong-language truth beats a screen that will not move (the same rule
 * `applyCopy.ts` states for the gift's own words).
 */
import type { Locale } from '@/lib/branding'

import enCore from '@/messages/en.json?slice=core'
import { fetchSlice, type SliceName } from '@/lib/messageChunks'

/** A parsed message file: nested objects of strings, addressed by dotted path. */
export type Catalogue = Record<string, unknown>

export type { SliceName }

/**
 * English, statically imported — the fallback, the server's render and the first client paint.
 *
 * ⚠ A FRESH OBJECT owned by this module (not the JSON module itself), because
 * `lib/messagesAdmin.ts` merges the admin slice INTO it and the identity must hold:
 * `contentLocale` is derived by `catalogue === FALLBACK_CATALOGUE`.
 *
 * ⚠ This module (English core) and `lib/messagesAdmin.ts` (English admin) are the only static
 * catalogue imports on any route's path — `lib/applyCopyPlatform.ts` is the one declared exemption,
 * and it is reached lazily. `oneLocalePerVisitor.test.ts` fails if another appears.
 */
export const FALLBACK_CATALOGUE: Catalogue = { ...enCore }

/** The slices every catalogue must hold before it is handed out. `admin` joins via `requireSlice`. */
const required = new Set<SliceName>(['core'])

/** One merged object per locale; English exists from the first line. */
const merged: Partial<Record<Locale, Catalogue>> = { en: FALLBACK_CATALOGUE }
const have: Record<Locale, Set<SliceName>> = { en: new Set(['core']), ms: new Set(), ta: new Set() }
const inFlight: Record<Locale, Partial<Record<SliceName, Promise<void>>>> = { en: {}, ms: {}, ta: {} }

let version = 0
const listeners = new Set<() => void>()

function announce(): void {
  version += 1
  listeners.forEach((l) => l())
}

/** Subscribe to "a slice arrived or became required". Returns the unsubscribe. */
export function subscribeCatalogues(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** A counter that moves on every announcement — the `useSyncExternalStore` snapshot. */
export function catalogueVersion(): number {
  return version
}

function complete(locale: Locale): boolean {
  for (const slice of required) if (!have[locale].has(slice)) return false
  return true
}

/**
 * The catalogue for `locale` if EVERY required slice of it is in memory, else `undefined`.
 * Never fetches.
 */
export function catalogueIfLoaded(locale: Locale): Catalogue | undefined {
  return complete(locale) ? merged[locale] : undefined
}

/** True once `locale`'s words are in memory. `en` is true from the first line of the bundle. */
export function isCatalogueLoaded(locale: Locale): boolean {
  return catalogueIfLoaded(locale) !== undefined
}

/** One slice of one locale, fetched once; merged into that locale's object on arrival. */
function loadSlice(locale: Locale, slice: SliceName): Promise<void> {
  if (have[locale].has(slice)) return Promise.resolve()
  const running = inFlight[locale][slice]
  if (running) return running
  if (locale === 'en') {
    // English slices are static imports; a missing one is a wiring fault, never a network one.
    return Promise.reject(new Error(`the English "${slice}" slice was never registered`))
  }

  const pending = fetchSlice(locale, slice)
    .then((mod) => {
      // webpack/ts-jest hand back a module namespace; the parsed object is its default export.
      const parsed = ((mod as { default?: Catalogue }).default ?? mod) as Catalogue
      merged[locale] = Object.assign(merged[locale] ?? {}, parsed)
      have[locale].add(slice)
      delete inFlight[locale][slice]
      announce()
    })
    .catch((err) => {
      // Clear the record so a later attempt can genuinely retry rather than re-await a dead promise.
      delete inFlight[locale][slice]
      throw err
    })

  inFlight[locale][slice] = pending
  return pending
}

/**
 * The catalogue for `locale`, fetching each missing required slice once if need be.
 *
 * Resolves immediately for a locale already complete (always the case for `en`), so a caller
 * never has to branch on which language it was handed. Rejects if ANY required slice fails.
 */
export function loadCatalogue(locale: Locale): Promise<Catalogue> {
  const ready = catalogueIfLoaded(locale)
  if (ready) return Promise.resolve(ready)
  return Promise.all([...required].map((slice) => loadSlice(locale, slice))).then(() => {
    // A slice may have become required while these were in the air; go round once more for it.
    return catalogueIfLoaded(locale) ?? loadCatalogue(locale)
  })
}

/**
 * Make `slice` REQUIRED and register its English words — called once, at module evaluation, by
 * the module that owns the slice (`lib/messagesAdmin.ts` for `admin`).
 *
 * English is merged INTO `FALLBACK_CATALOGUE` (identity kept). Nothing is FETCHED here: the
 * announcement re-runs `I18nProvider`'s effect, which asks `loadCatalogue` for the language ON
 * SCREEN only — so a tab that visited Malay and then Tamil downloads the Tamil admin slice, not
 * both (the first cut fetched every language in memory; the 2026-10-21 smoke caught the Malay one
 * travelling for nothing). A load already in the air (the stored-locale warm start in `i18n.tsx`)
 * picks the new slice up too: `loadCatalogue` goes round again until the catalogue is complete.
 */
export function requireSlice(slice: SliceName, english: Catalogue): void {
  if (!have.en.has(slice)) {
    Object.assign(FALLBACK_CATALOGUE, english)
    have.en.add(slice)
  }
  if (required.has(slice)) return
  required.add(slice)
  announce()
}
