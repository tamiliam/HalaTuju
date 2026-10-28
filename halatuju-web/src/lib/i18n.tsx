'use client'

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from 'react'

import { KEY_LOCALE } from '@/lib/storage'
import { brandingParams, interpolateMessage } from '@/lib/branding'
import { useBranding } from '@/lib/branding-context'
import {
  FALLBACK_CATALOGUE,
  catalogueIfLoaded,
  catalogueVersion,
  loadCatalogue,
  sliceAbsent,
  subscribeCatalogues,
  type Catalogue,
} from '@/lib/messages'

export type Locale = 'en' | 'ms' | 'ta'

export const LOCALE_LABELS: Record<Locale, string> = {
  en: 'English',
  ms: 'Bahasa Melayu',
  ta: 'தமிழ்',
}

interface I18nContextValue {
  /** The language the reader has CHOSEN, and the one the switcher has committed to. */
  locale: Locale
  /**
   * The language of the WORDS on screen right now — `en` while `locale`'s catalogue is still in
   * the air, or after its chunk failed to arrive.
   *
   * ⚠ **`html lang` FOLLOWS THIS ONE, NEVER `locale`.** They differ for exactly as long as a
   * download takes, and in that window `lang="ta"` over English text tells a screen reader to
   * pronounce English in a Tamil voice. A returning Tamil reader met it on every single visit,
   * because the server cannot read `localStorage` and so the first paint is always English.
   */
  contentLocale: Locale
  /**
   * Ask for a language. Resolves once the words are on screen; REJECTS when the catalogue could
   * not be fetched, so the caller can put its control back and say so.
   *
   * ⚠ It rejects rather than committing a half-move. Until the 2026-09-21 audit a failed load
   * moved `locale` anyway and showed English words under a Tamil switcher, with nothing said.
   */
  setLocale: (locale: Locale) => Promise<void>
  t: (key: string, params?: Record<string, string>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const parts = path.split('.')
  let current: unknown = obj
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = (current as Record<string, unknown>)[part]
    } else {
      return path // Return the key as fallback
    }
  }
  return typeof current === 'string' ? current : path
}

/**
 * TD-360: the value of `key` in `catalogue`, or in ENGLISH when the key's whole top-level
 * NAMESPACE is absent from `catalogue` — which happens for exactly one reason: that slice of the
 * reader's language has not arrived yet (a Malay / Tamil staff member's first admin page in a tab,
 * accepted by the owner 2026-10-21). The words are right in a language, just briefly not theirs.
 *
 * ⚠ NEVER a fallback for a missing KEY. A namespace that is present but lacks the key returns the
 * key itself, exactly as before — the contract `tOr` and the key-echo guard are built on.
 * (TD-416: for a namespace split across slices — `scholarship` — "present" means the key's CHILD of
 * it is present; see `sliceAbsent` in `lib/messages.ts`.)
 */
function lookup(catalogue: Catalogue, key: string): string {
  // TD-416: `sliceAbsent` is the namespace test, plus one level down for a namespace split across
  // slices (`scholarship`: its menu words are in core, the rest in its own slice).
  if (catalogue !== FALLBACK_CATALOGUE && sliceAbsent(catalogue, key)) {
    return getNestedValue(FALLBACK_CATALOGUE, key)
  }
  return getNestedValue(catalogue, key)
}

/**
 * ⚠ **EVERY TOUCH OF `localStorage` IN THIS FILE GOES THROUGH THESE TWO FUNCTIONS, AND THAT IS
 * NOT TIDINESS.** Where a browser has site data blocked — Safari private mode, "block all
 * cookies", a locked-down school device — `localStorage` still EXISTS and throws `SecurityError`
 * the instant it is touched. The read happens as this module is EVALUATED (see the warm start
 * below), which is *before React exists*: an unguarded throw escapes the module body, the bundle
 * never finishes evaluating, and the reader is handed a BLANK DOCUMENT. Not an error screen, not
 * a broken switcher — nothing at all, on every page of the product.
 *
 * `theme.ts` has wrapped the identical call in try/catch since F1, with a comment saying exactly
 * this. i18n did not, and an audit found it on 2026-09-21. A blocked store must cost the MEMORY
 * of the choice and nothing else: such a reader gets English, and a switcher that works for the
 * life of the tab. `localeSwitch.test.tsx` blocks both calls and proves both halves.
 */
function readStoredLocale(): Locale | null {
  if (typeof window === 'undefined') return null
  try {
    const stored = window.localStorage.getItem(KEY_LOCALE)
    if (stored === 'en' || stored === 'ms' || stored === 'ta') return stored
  } catch {
    /* site data blocked — see above. English, and no memory of the choice. */
  }
  return null
}

function writeStoredLocale(locale: Locale): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(KEY_LOCALE, locale)
  } catch {
    /* see readStoredLocale — the choice still applies to this tab, it is just not remembered. */
  }
}

function getInitialLocale(): Locale {
  return readStoredLocale() ?? 'en'
}

/**
 * ⚠ **THE FETCH STARTS HERE, NOT IN AN EFFECT — and that is the whole of the anti-flash work.**
 *
 * A returning Tamil reader has always seen English first: the server cannot read `localStorage`,
 * so the HTML it sends is English, and the browser paints it before React has run at all. What
 * code health H17 could have ADDED is a second, longer wait — English on screen until an effect
 * fires after hydration and only then asks for `ta.json`.
 *
 * Kicking the load off as this module is evaluated removes that: the request leaves the moment
 * the bundle is parsed, in parallel with hydration, so by the time the provider's effect looks
 * the catalogue is usually already there. On every visit after the first the chunk is in the HTTP
 * cache and the swap is synchronous.
 *
 * Guarded on `window` so it is inert during SSR and in the `node` test environment. The rejection
 * is swallowed HERE only; `I18nProvider` handles a genuine failure where it can act on it.
 */
if (typeof window !== 'undefined') {
  loadCatalogue(getInitialLocale()).catch(() => { /* the provider decides what a failure means */ })
}

interface ActiveLocale {
  locale: Locale
  /** The words on screen. `FALLBACK_CATALOGUE` while `locale`'s own chunk is still in the air. */
  catalogue: Catalogue
}

export function I18nProvider({ children }: { children: ReactNode }) {
  // ⚠ ONE piece of state, not two. The locale and the words that go with it have to change in the
  // SAME commit, or a render exists in which `locale` says Tamil and `catalogue` is still English
  // — which is precisely the flash of the wrong language this sprint exists to avoid.
  const [active, setActive] = useState<ActiveLocale>(() => {
    const locale = getInitialLocale()
    return { locale, catalogue: catalogueIfLoaded(locale) ?? FALLBACK_CATALOGUE }
  })
  const { locale, catalogue } = active
  // DERIVED, never stored: the only catalogue that is not its own locale's is the English
  // fallback, and it is a singleton, so identity answers the question exactly. Storing it would
  // be a fourth place for the same fact to be set — and three of them already have to agree.
  const contentLocale: Locale = catalogue === FALLBACK_CATALOGUE ? 'en' : locale
  /**
   * ⚠ **THE MONOTONIC REQUEST TOKEN — WHY A SWITCH NEEDS ONE AT ALL.** Two quick choices are two
   * fetches, and a network is free to answer them in either order. With no token, the slower
   * answer simply overwrote the faster one whenever the reader's FIRST choice happened to arrive
   * second: `localStorage` said Malay, the switcher said Tamil, `html lang` said Tamil and the
   * heading was Tamil — one reader, four surfaces, three answers. Reproduced in a browser on
   * 2026-09-21. Only the latest request may commit; every older one returns having done nothing.
   */
  const request = useRef(0)
  // Branding lives in the OUTER BrandingProvider (see providers.tsx). Its five AUTO_TOKENS are
  // auto-injected into every render, BENEATH the explicit call-site params (which always win).
  const branding = useBranding()
  /**
   * TD-360: moves whenever a message SLICE arrives or becomes required (the admin layout's words).
   * A slice that lands for the language already on screen is merged into the same catalogue
   * object, so identity cannot tell `t` it changed — this counter does. It also re-runs the effect
   * below, which is how a required-but-missing slice gets fetched for the locale on screen.
   */
  const sliceVersion = useSyncExternalStore(subscribeCatalogues, catalogueVersion, catalogueVersion)

  // The stored locale's catalogue, for a reader who arrives already set to Malay or Tamil. A
  // no-op for English and for anything already in memory. `setActive` is guarded on the locale
  // still being the one asked for, so a switch made mid-flight is never overwritten by the
  // arrival of the language the reader has just left.
  useEffect(() => {
    // ⚠ NOT a bare `if (loaded) return`. The module-level warm start can finish in the gap between
    // the state initialiser and this effect, and a bare early return would then leave the reader
    // on English for ever with the right catalogue sitting in memory beside them.
    const ready = catalogueIfLoaded(locale)
    if (ready) {
      setActive((cur) => (cur.locale === locale && cur.catalogue !== ready
        ? { locale, catalogue: ready } : cur))
      return
    }
    let alive = true
    loadCatalogue(locale).then(
      (loaded) => { if (alive) setActive((cur) => (cur.locale === locale
        ? { locale, catalogue: loaded } : cur)) },
      () => { /* keep showing English; the words are right in a language, just not this one */ },
    )
    return () => { alive = false }
  }, [locale, sliceVersion])

  // ⚠ THIS EFFECT NO LONGER RUNS AFTER A SWITCH, AND THAT IS THE SECOND HALF OF THE ONE-FETCH
  // RULE. `setLocale` commits `locale` only once the catalogue is in memory, so by the time
  // `[locale]` changes `catalogueIfLoaded` answers immediately and nothing is fetched. It used to
  // commit the failure too, which re-ran this effect against a chunk that had just 404'd — two
  // requests per switch for a tab held open across a deploy, both of them silent.

  /**
   * ⚠ **NOTHING IS COMMITTED AND NOTHING IS STORED UNTIL THE WORDS ARE IN HAND.** The locale, the
   * catalogue, `localStorage` and `html lang` therefore cannot disagree, which is the whole of the
   * 2026-09-21 audit's findings A, D and E in one sentence.
   *
   * Before: `localStorage` was written the moment the reader picked, and a failed chunk committed
   * `{ newLocale, English }` anyway — so a tab held open across a deploy showed a Tamil switcher
   * over English words, said nothing, remembered the choice, and asked for the dead chunk twice.
   * A stored choice that cannot be honoured is worse than none: it repeats on every reload.
   */
  const setLocale = useCallback((newLocale: Locale): Promise<void> => {
    const token = ++request.current
    const ready = catalogueIfLoaded(newLocale)
    if (ready) {
      // Already in memory (always so for English, and for any language visited this tab) — one
      // synchronous commit, no fetch, nothing for the control to wait on.
      setActive({ locale: newLocale, catalogue: ready })
      writeStoredLocale(newLocale)
      return Promise.resolve()
    }
    return loadCatalogue(newLocale).then(
      (loaded) => {
        if (token !== request.current) return   // a newer choice owns the screen; stand down
        setActive({ locale: newLocale, catalogue: loaded })
        writeStoredLocale(newLocale)
      },
      (err: unknown) => {
        // A SUPERSEDED failure is silent on purpose: the reader has already moved on, and a
        // message about a language they left would be noise they cannot act on.
        if (token !== request.current) return
        throw err
      },
    )
  }, [])

  // TD-360: the words AND the slice version as one value, so a slice merged into the SAME
  // catalogue object still gives consumers a new `t` (identity alone cannot see that change).
  const words = useMemo(() => ({ catalogue, sliceVersion }), [catalogue, sliceVersion])

  const t = useCallback(
    (key: string, params?: Record<string, string>) => {
      const value = lookup(words.catalogue, key)
      // Branding tokens first, explicit params override them. interpolateMessage has a
      // '{'-absent fast path, so a plain string is returned untouched (byte-identical to before).
      return interpolateMessage(value, { ...brandingParams(branding, locale), ...params })
    },
    [words, locale, branding]
  )

  return (
    <I18nContext.Provider value={{ locale, contentLocale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useT() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useT must be used within I18nProvider')
  return ctx
}

/**
 * `t(key)`, or `fallback` when the key resolves to nothing.
 *
 * ⚠ **THE IDIOM THIS EXISTS TO KILL IS `t(key) || 'English fallback'`.** `t` returns THE KEY
 * ITSELF when it cannot resolve one (see `getNestedValue`), and a key is a non-empty string, so
 * `||` never fires and the student reads a raw dotted path. Four keys shipped exactly that way
 * on the sign-in gate and nobody saw them for months (TD-259). The test that keeps the idiom out
 * is `src/lib/__tests__/codeStandards.test.ts`, "no key-echo fallback".
 *
 * Use it only where a key may legitimately be absent — a value the SERVER chose, say. Where the
 * key is known to exist, write a plain `t(key)`; the i18n ledger guards that.
 */
export function tOr(
  t: (key: string, params?: Record<string, string>) => string,
  key: string,
  fallback: string,
  params?: Record<string, string>,
): string {
  const value = t(key, params)
  return value === key ? fallback : value
}
