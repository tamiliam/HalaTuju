/**
 * THE FOUR LAZY MESSAGE CHUNKS — TD-360 Sprint 1 (2026-10-21).
 *
 * Malay and Tamil, each in three slices (`core`, `admin`, `documents`), cut at build time by
 * `scripts/messages-slice-loader.js`. `lib/messages.ts` is the only caller; this module exists so
 * the network edge is ONE function a test can stand in for (`localeSlices.test.tsx` owns the clock
 * through it while the real registry in `messages.ts` does the work).
 *
 * ⚠ FOUR LITERAL SPECIFIERS, NEVER A COMPUTED ONE. `import('@/messages/' + locale + '.json')`
 * makes webpack emit a context module holding every JSON in the folder — the H17 bug spelled
 * differently. `oneLocalePerVisitor.test.ts` checks all four are here, literal.
 */
import type { Locale } from '@/lib/branding'

export type SliceName = 'core' | 'admin' | 'documents'

/** Fetch one slice of Malay or Tamil. Resolves to the module (the catalogue is its default). */
export function fetchSlice(locale: Exclude<Locale, 'en'>, slice: SliceName): Promise<unknown> {
  if (locale === 'ms') {
    if (slice === 'documents') return import('@/messages/ms.json?slice=documents')
    return slice === 'core'
      ? import('@/messages/ms.json?slice=core')
      : import('@/messages/ms.json?slice=admin')
  }
  if (slice === 'documents') return import('@/messages/ta.json?slice=documents')
  return slice === 'core'
    ? import('@/messages/ta.json?slice=core')
    : import('@/messages/ta.json?slice=admin')
}
