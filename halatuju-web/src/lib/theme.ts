/**
 * Light / Dark / Auto — a PERSON's choice (Layer 1 F1).
 *
 * Owner, 2026-07-29: *"Dark or light is a personal choice. And there are those like light at day
 * time and dark in the evenings, auto set."* and *"Light/dark choice would be under the personal
 * account settings/profile."* So: the organisation owns the colours, the person owns the mode. An
 * `org_admin` never sets what mode a reviewer sits in.
 *
 * ⚠ THIS IS DELIBERATELY NOT IN `uiPrefs.ts`, WHOSE DOCSTRING SAYS SO IN SO MANY WORDS.
 * That module is for device-local preferences whose home is the device — a menu's width. The theme's
 * home is the ACCOUNT, so that someone who needs dark for accessibility has it on every machine they
 * sign in from. Local storage below is a CACHE of that account value, not its home, and the
 * distinction is the whole reason this file exists separately.
 *
 * ⚠ AND IT IS NOT THE RESERVED-KEY MISTAKE COMING BACK. `docs/lessons.md` records a `PREF_KEYS.theme`
 * that was deleted for silently asserting a theme is a device preference while that was exactly the
 * open question. The question is now answered — by the owner, on the record — and what is written
 * here follows the answer. The account WRITE PATH is not built yet (three identity models, four
 * settings surfaces); it is openly deferred, named below, and the flag keeps the control unreachable
 * until it lands. Deferred and named is not the same as guessed and hidden.
 *
 * ── Why local storage is read before the account ──
 * The account value arrives with the session, which is after first paint. Read it first and a dark
 * user watches a white page turn dark on every navigation. So the cache is read SYNCHRONOUSLY in a
 * blocking inline script before any paint (`ThemeScript`), and the account reconciles afterwards.
 * That ordering is not an optimisation; without it the feature is visibly broken on every page load.
 */

export const THEME_MODES = ['light', 'dark', 'auto'] as const
export type ThemeMode = typeof THEME_MODES[number]

/** What actually gets painted. `auto` is a mode, never a resolution. */
export type ResolvedTheme = 'light' | 'dark'

/** localStorage key. Namespaced like `uiPrefs`, but this module owns it. */
export const THEME_STORAGE_KEY = 'halatuju.theme'

/** Attribute on `<html>` that `globals.css` keys the reversed ramp off. */
export const THEME_ATTR = 'data-theme'

export const DEFAULT_MODE: ThemeMode = 'auto'

export function isThemeMode(v: unknown): v is ThemeMode {
  return typeof v === 'string' && (THEME_MODES as readonly string[]).includes(v)
}

/**
 * The mode a person chose → the theme to paint.
 *
 * `auto` follows the DEVICE rather than a clock of our own. macOS and Windows already offer a
 * light/dark schedule that flips at the user's local sunset, so following the device inherits a
 * schedule that is location-aware and already theirs. Our own would need a cutover hour and a
 * timezone, and would be wrong for anyone travelling or working nights.
 */
export function resolveTheme(mode: ThemeMode, prefersDark: boolean): ResolvedTheme {
  if (mode === 'light' || mode === 'dark') return mode
  return prefersDark ? 'dark' : 'light'
}

/** Does this device currently ask for dark? SSR-safe; false when there is nothing to ask. */
export function devicePrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

export function readStoredMode(): ThemeMode {
  if (typeof window === 'undefined') return DEFAULT_MODE
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeMode(raw) ? raw : DEFAULT_MODE
  } catch {
    // Safari in private mode throws on read, not only on write. A theme is never worth an exception.
    return DEFAULT_MODE
  }
}

export function writeStoredMode(mode: ThemeMode): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    /* see readStoredMode — storage may be unavailable, and that is survivable */
  }
}

/**
 * Paint a resolved theme.
 *
 * ⚠ THIS SETS ONE ATTRIBUTE AND NOTHING ELSE, AND THAT IS THE POINT. The repaint is a CSS variable
 * set swapping under the same DOM — no re-render, no re-mount, no re-fetch. `auto` follows the
 * device, so this can fire at sunset while a student is halfway through uploading documents or a
 * reviewer is part-way through a verdict. Anyone who loses a half-filled form to a sunset will not
 * report it as a theming bug. Never make this function do more.
 */
export function applyTheme(theme: ResolvedTheme): void {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute(THEME_ATTR, theme)
}

/**
 * Where the before-paint boot script lives: `public/theme-boot.js`, loaded render-blocking from
 * `<head>` in the root layout.
 *
 * It is a real static file rather than an inline string because injecting raw HTML is a habit worth
 * not having, even when the content is our own compile-time constant. A blocking head script cannot
 * import this module, so the key, the attribute and the default are spelled out in both places —
 * and `theme.test.ts` READS THAT FILE and asserts it agrees with the constants here. Duplication a
 * test refuses to let drift is the only acceptable kind.
 */
export const THEME_BOOT_SRC = '/theme-boot.js'

/**
 * Is the theme switch reachable by a person yet?
 *
 * Ships OFF. The token vocabulary lands one surface at a time (F1 → F6) and a reachable switch part
 * way through means a person can put half the product into a mode nothing has painted for. It flips
 * in F7, once every surface is converted — which is what makes the repaint ORDER a question of risk
 * rather than of user-visible breakage.
 */
export function themeSwitchEnabled(): boolean {
  return process.env.NEXT_PUBLIC_THEME_SWITCH === '1'
}
