/**
 * Small, device-local interface preferences. One of them today: whether the rail stays open.
 *
 * These are PREFERENCES, never state anybody relies on being true: a wiped browser must be
 * indistinguishable from a new one, so every read falls back to a default rather than failing.
 *
 * The rail pin is deliberately not on the account — storing it server-side means an endpoint, a
 * column and a round trip before the first paint, to remember which way a menu sits.
 *
 * ⚠ That reasoning is about A MENU'S WIDTH, and does not generalise. Do not reach for this
 * module for the next preference by default: theming, density and anything a person would
 * expect to follow them between machines are their own decision, and "it was already here" is
 * not the argument that settles them.
 *
 * ⚠ SSR-safe by necessity. This runs inside a Next app router build, where the module is
 * evaluated on the server too and `window` does not exist. Every function guards for it, and
 * `read` is never called during render — see `usePref`.
 */

const NS = 'halatuju.ui.'

function read(key: string): string | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(NS + key)
  } catch {
    // Safari in private mode throws on access, not just on write. A preference is never worth
    // an exception in the shell.
    return null
  }
}

function write(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(NS + key, value)
  } catch {
    /* see read() — storage may be unavailable, and that is survivable */
  }
}

/** Read a preference constrained to a known set; anything else (or nothing) gives `fallback`. */
export function readPref<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  const raw = read(key)
  return (allowed as readonly string[]).includes(raw ?? '') ? (raw as T) : fallback
}

export function writePref(key: string, value: string): void {
  write(key, value)
}

export const PREF_KEYS = {
  /** 'pinned' | 'hover' — whether the rail stays open. */
  navPin: 'navPin',
} as const
