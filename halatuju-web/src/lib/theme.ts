/**
 * Light / Dark / Auto — a PERSON's choice (Layer 1 F1).
 *
 * Owner, 2026-07-29: *"Dark or light is a personal choice. And there are those like light at day
 * time and dark in the evenings, auto set."* and *"Light/dark choice would be under the personal
 * account settings/profile."* So: the organisation owns the colours, the person owns the mode. An
 * `org_admin` never sets what mode a reviewer sits in.
 *
 * ⚠ THE CHOICE IS DEVICE-LOCAL. STORAGE IS ITS HOME, NOT A CACHE OF AN ACCOUNT VALUE.
 * Owner ruling, 2026-09-02, at F7d: **device-local, no account storage.** LANGUAGE is a larger
 * per-person choice and is already device-local, so making the theme *more* persistent than the
 * language would be backwards.
 *
 * ⚠ THIS FILE SAID THE OPPOSITE UNTIL F7d, and the paragraph it said it in was load-bearing —
 * F1b was scoped around it (four settings surfaces, three identity models, a migration) and is now
 * SUPERSEDED, not deferred. A docstring that outlives the decision it describes is a confident
 * falsehood, and this arc has now been bitten by that four times. Whichever sprint acts on a ruling
 * owns rewriting the case that was made against it.
 *
 * ⚠ IT IS STILL NOT `uiPrefs.ts`, and that separation survives the ruling on different grounds.
 * `docs/lessons.md` records a `PREF_KEYS.theme` deleted for silently ASSUMING a theme is a device
 * preference while that was the open question. The question is answered now, so the answer is not
 * the problem — but the theme is read by a blocking head script that cannot import a module, and
 * `uiPrefs` is a React-side store. The mechanism, not the taxonomy, is why this file is separate.
 *
 * ── Why a blocking script reads it, when there is no account to wait for ──
 * Even a device value read in React lands after first paint, so a dark person would watch a white
 * page turn dark on every navigation. `public/theme-boot.js` reads it SYNCHRONOUSLY in `<head>`.
 * That ordering is not an optimisation; without it the feature is visibly broken on every load.
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
 *
 * ⚠ IT IS UNCONDITIONAL SINCE F7d. There was a `themeSwitchEnabled()` flag here, and it gated the
 * SCRIPT rather than the control — deliberately, because F1 first shipped it gating only the
 * affordance, which left the script running with a default of `auto` and handed a dark product to
 * every device set to dark, across surfaces no sprint had painted. That flag is deleted, because
 * every surface is painted now and the switch is reachable. **A flag that gates only the affordance
 * gates nothing**, and that lesson outlives the flag itself.
 */
export const THEME_BOOT_SRC = '/theme-boot.js'
