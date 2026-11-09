/**
 * The console's top-banner slot: how a banner remembers that it was hidden (staff nudges, 2026-11-08).
 *
 * Brief `docs/plans/2026-11-08-staff-nudges.md`, decisions 4, 6 and 7. A banner under the top bar
 * (`components/admin/ShellBanners.tsx`) is hidden by its X for a while, PER BROWSER, keyed per account:
 *
 *   - `{ kind: 'days', days: 7 }` — the profile banner: hidden for N days, then it returns (if the
 *     server still says something is missing);
 *   - `{ kind: 'signIn', stamp }` — Phase B's overdue banner: hidden until the next sign-in. Kept TWO ways
 *     (review of sprint B, 2026-11-09): a per-tab mark in `sessionStorage`, which holds for this browser
 *     session whatever happens elsewhere and is cleared by `clearSignInDismissals` on sign-out
 *     (`adminSignOut`); and `stamp` in `localStorage` (the session user's `last_sign_in_at`), so a new tab of
 *     the SAME sign-in stays quiet. `last_sign_in_at` is per ACCOUNT, so a sign-in on another device moves
 *     it — the tab mark is what keeps the X steady in this tab; a new tab after that shows it again, which
 *     is the safe direction for a bill that is still late.
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
  return `${PREFIX}${name}.${accountId}`
}

function read(key: string): string | null {
  if (typeof window === 'undefined') return null
  try { return window.localStorage.getItem(key) } catch { return null }
}

function write(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try { window.localStorage.setItem(key, value) } catch { /* storage unavailable: survivable */ }
}

function readTab(key: string): string | null {
  if (typeof window === 'undefined') return null
  try { return window.sessionStorage.getItem(key) } catch { return null }
}

function writeTab(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try { window.sessionStorage.setItem(key, value) } catch { /* storage unavailable: survivable */ }
}

const PREFIX = 'halatuju.banner.'
const TAB_MARK = 'signIn'

/** Is this banner hidden right now? */
export function isDismissed(key: string, scope: DismissScope, now: number = Date.now()): boolean {
  if (scope.kind === 'signIn') {
    if (readTab(key) === TAB_MARK) return true
    return !!scope.stamp && read(key) === `signIn:${scope.stamp}`
  }
  const raw = read(key)
  if (!raw) return false
  const at = Number(raw.startsWith('at:') ? raw.slice(3) : NaN)
  return Number.isFinite(at) && now >= at && now - at < scope.days * DAY_MS
}

/** The X: hide this banner for its scope. */
export function dismiss(key: string, scope: DismissScope, now: number = Date.now()): void {
  if (scope.kind === 'signIn') {
    writeTab(key, TAB_MARK)
    if (scope.stamp) write(key, `signIn:${scope.stamp}`)
    return
  }
  write(key, `at:${now}`)
}

/** Sign-out: this tab's "until the next sign-in" marks go, so signing in again here shows them again. */
export function clearSignInDismissals(): void {
  if (typeof window === 'undefined') return
  try {
    const store = window.sessionStorage
    const keys: string[] = []
    for (let i = 0; i < store.length; i++) {
      const k = store.key(i)
      if (k && k.startsWith(PREFIX)) keys.push(k)
    }
    keys.forEach((k) => store.removeItem(k))
  } catch { /* storage unavailable: survivable */ }
}
