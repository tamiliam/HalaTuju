'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'

import { KEY_LOCALE } from '@/lib/storage'
import { brandingParams, interpolateMessage } from '@/lib/branding'
import { useBranding } from '@/lib/branding-context'
import {
  FALLBACK_CATALOGUE,
  catalogueIfLoaded,
  loadCatalogue,
  type Catalogue,
} from '@/lib/messages'

export type Locale = 'en' | 'ms' | 'ta'

export const LOCALE_LABELS: Record<Locale, string> = {
  en: 'English',
  ms: 'Bahasa Melayu',
  ta: 'தமிழ்',
}

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
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

function getInitialLocale(): Locale {
  if (typeof window === 'undefined') return 'en'
  const stored = localStorage.getItem(KEY_LOCALE)
  if (stored === 'en' || stored === 'ms' || stored === 'ta') return stored
  return 'en'
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
  // Branding lives in the OUTER BrandingProvider (see providers.tsx). Its five AUTO_TOKENS are
  // auto-injected into every render, BENEATH the explicit call-site params (which always win).
  const branding = useBranding()

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
      (loaded) => { if (alive) setActive((cur) => (cur.locale === locale ? { locale, catalogue: loaded } : cur)) },
      () => { /* keep showing English; the words are right in a language, just not this one */ },
    )
    return () => { alive = false }
  }, [locale])

  const setLocale = useCallback((newLocale: Locale) => {
    const ready = catalogueIfLoaded(newLocale)
    if (ready) {
      setActive({ locale: newLocale, catalogue: ready })
    } else {
      loadCatalogue(newLocale).then(
        (loaded) => setActive({ locale: newLocale, catalogue: loaded }),
        // The chunk did not arrive. Move anyway: the reader's choice is stored, `html lang` and
        // the switcher follow, and `t` answers in English until a reload retries the fetch.
        () => setActive({ locale: newLocale, catalogue: FALLBACK_CATALOGUE }),
      )
    }
    localStorage.setItem(KEY_LOCALE, newLocale)
  }, [])

  const t = useCallback(
    (key: string, params?: Record<string, string>) => {
      const value = getNestedValue(catalogue, key)
      // Branding tokens first, explicit params override them. interpolateMessage has a
      // '{'-absent fast path, so a plain string is returned untouched (byte-identical to before).
      return interpolateMessage(value, { ...brandingParams(branding, locale), ...params })
    },
    [catalogue, locale, branding]
  )

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
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
