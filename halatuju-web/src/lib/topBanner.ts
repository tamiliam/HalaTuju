/**
 * The console's top-banner slot: how a banner remembers that it was hidden (staff nudges, 2026-11-08).
 *
 * Brief `docs/plans/2026-11-08-staff-nudges.md`, decisions 4, 6 and 7. A banner under the top bar
 * (`components/admin/ShellBanners.tsx`) is hidden by its X for a while, PER BROWSER, keyed per account:
 *
 *   - `{ kind: 'days', days: 7 }` — the profile banner: hidden for N days, then it returns (if the
 *     server still says something is missing);
 *   - `{ kind: 'signIn', stamp }` — Phase B's overdue banner: hidden until the next sign-in. `stamp`
 *     names THIS sign-in (e.g. the session user's `last_sign_in_at`); a new sign-in brings a new stamp,
 *     and the old dismissal no longer matches.
 *
 * ⚠ NOT `lib/uiPrefs` (its header asks for a deliberate decision before reuse): a dismissal is not a
 * preference, and it has its own keys (`halatuju.banner.<name>.<account id>`).
 * ⚠ READ AFTER MOUNT ONLY. Storage read during render would give the server one answer and the browser
 * another; the caller reads in an effect. Every access is guarded (Safari private mode throws).
 * ⚠ A dismissal is a courtesy, never state anybody relies on: a wiped browser shows the banner again.
 */

export type DismissScope = { kind: 'days'; days: number } | { kind: 'signIn'; stamp: string }

const DAY_MS = 24 * 60 * 60 * 1000

/** The storage key for one banner and one account. */
export function bannerKey(name: string, accountId: number | string): string {
  return `halatuju.banner.${name}.${accountId}`
}

function read(key: string): string | null {
  if (typeof window === 'undefined') return null
  try { return window.localStorage.getItem(key) } catch { return null }
}

function write(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.setItem(key, value) } catch { /* storage unavailable: survivable */ }
}

/** Is this banner hidden right now? */
export function isDismissed(key: string, scope: DismissScope, now: number = Date.now()): boolean {
  const raw = read(key)
  if (!raw) return false
  if (scope.kind === 'signIn') return !!scope.stamp && raw === `signIn:${scope.stamp}`
  const at = Number(raw.startsWith('at:') ? raw.slice(3) : NaN)
  return Number.isFinite(at) && now >= at && now - at < scope.days * DAY_MS
}

/** The X: hide this banner for its scope. */
export function dismiss(key: string, scope: DismissScope, now: number = Date.now()): void {
  write(key, scope.kind === 'signIn' ? `signIn:${scope.stamp}` : `at:${now}`)
}
