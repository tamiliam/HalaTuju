/**
 * OAuth sign-in must START and FINISH on the same browser origin.
 *
 * PKCE stores a one-time code verifier under the initiating client's storage key, and browser
 * storage — localStorage, sessionStorage and cookies alike — is scoped to the ORIGIN. So
 * `http://localhost:3000` and `http://127.0.0.1:3000` are the same dev server but two different
 * vaults: begin at one, come back at the other, and the verifier is simply not there.
 *
 * ⚠ This is the cause of TD-182, reproduced on 2026-07-28, and it is worth stating plainly
 * because the failure message Supabase raises actively misdirects. It says *"For SSR frameworks
 * (Next.js, SvelteKit, etc.), use @supabase/ssr ... to store the code verifier in cookies"*, and
 * that would have changed nothing here: cookies are bound to the host too, so a cookie written on
 * `127.0.0.1` is equally invisible to `localhost`. Two earlier diagnoses on that ticket were also
 * confident and also wrong. Measure before you migrate a storage layer.
 *
 * Two functions, both pure and both storage-injectable so node-env jest can drive them:
 *  - `canonicalLoopbackUrl` removes the trap, by moving a sign-in off a loopback IP BEFORE it
 *    starts. Inert anywhere the hostname is not a loopback literal, which is everywhere in
 *    production.
 *  - `oauthOriginMismatch` recognises the trap after the fact, so the callback can say something
 *    true and actionable instead of pointing at the wrong remedy.
 */

/**
 * Loopback spellings that address the SAME local server as `localhost` while forming a DIFFERENT
 * browser origin. `[::1]` is how `URL.hostname` reports IPv6 loopback (brackets included); the
 * bare `::1` is accepted too so a caller passing a raw hostname is not silently missed.
 */
const LOOPBACK_ALIASES = ['127.0.0.1', '[::1]', '::1']

/** The spelling every console sign-in is normalised to. */
export const CANONICAL_LOOPBACK_HOST = 'localhost'

/** Where supabase-js keeps the PKCE verifier: `${storageKey}-code-verifier` (auth-js 2.95.3,
 *  `GoTrueClient.js`). Derived rather than re-spelled so the two cannot drift apart. */
export function verifierKeyFor(storageKey: string): string {
  return `${storageKey}-code-verifier`
}

export function isLoopbackAlias(hostname: string): boolean {
  return LOOPBACK_ALIASES.includes(hostname.toLowerCase())
}

/**
 * The same URL spelled with the canonical loopback host, or `null` when it is already canonical
 * (or is not a loopback address at all, which is the production case).
 *
 * Path, query, hash and port are preserved: the caller redirects to exactly where the person was
 * going, only at the address the rest of the flow will agree on. Returning `null` rather than the
 * unchanged URL is deliberate — it makes "nothing to do" impossible to confuse with "redirect
 * here", so a caller cannot loop.
 */
export function canonicalLoopbackUrl(href: string): string | null {
  let url: URL
  try {
    url = new URL(href)
  } catch {
    return null  // not a URL we can reason about; leave the caller alone
  }
  if (!isLoopbackAlias(url.hostname)) return null
  url.hostname = CANONICAL_LOOPBACK_HOST
  return url.toString()
}

type StorageLike = Pick<Storage, 'getItem'>

/**
 * Did this OAuth callback arrive carrying a `?code=` that THIS origin cannot possibly exchange?
 *
 * True only when both halves hold: there is a code to exchange, and no verifier under this
 * origin's storage. That pair is what distinguishes an origin mismatch from the other ways a
 * callback fails (no code at all, an expired code, a refused exchange) — each of which wants a
 * different sentence in front of the person.
 *
 * ⚠⚠ **TIMING IS PART OF THE CONTRACT: call this BEFORE anything can attempt an exchange —
 * before `getSession()`, and ideally before the supabase client is even constructed.**
 * `_exchangeCodeForSession` deletes the verifier once it has POSTed, whether the exchange
 * succeeded or failed (auth-js 2.95.3, `GoTrueClient.js:788`), and `detectSessionInUrl` — on by
 * default — runs that during client initialisation, which `getSession()` awaits. Ask afterwards
 * and an absent verifier means "never here OR just consumed", so every unrelated exchange failure
 * gets blamed on the origin. I shipped exactly that on 2026-07-28 and the owner hit it within the
 * hour: a wrong explanation delivered confidently, which is worse than the vague one it replaced.
 * The name says `AtEntry` so the requirement travels with the call site.
 */
export function oauthOriginMismatchAtEntry(
  search: string,
  storageKey: string,
  storage?: StorageLike | null,
): boolean {
  const hasCode = new URLSearchParams(search).has('code')
  if (!hasCode) return false
  const store = storage ?? safeLocal()
  if (!store) return false  // no storage to inspect — do not claim a cause we cannot see
  return store.getItem(verifierKeyFor(storageKey)) === null
}

/**
 * The one impure function here: move THIS page to the canonical loopback host, if it is not
 * already there. Returns true when a redirect was started, so a caller can hold its render.
 *
 * ⚠ Call this from a console LOGIN page, never from a callback. A sign-in that legitimately began
 * on `127.0.0.1` also returns to `127.0.0.1` and works perfectly — `redirectTo` is built from the
 * initiating origin. Bouncing such a callback would strand it away from the verifier it was about
 * to use, turning a healthy flow into the exact failure this module exists to prevent. Guarding
 * the entry point is enough: if sign-in can only ever start on `localhost`, it can only ever
 * finish there.
 *
 * `location.replace` rather than `assign` so the loopback spelling does not sit in history for the
 * back button to return to.
 */
export function enforceCanonicalOrigin(): boolean {
  if (typeof window === 'undefined') return false
  const target = canonicalLoopbackUrl(window.location.href)
  if (!target) return false
  window.location.replace(target)
  return true
}

/** localStorage when there is one (a browser, not blocked). Never throws. */
function safeLocal(): StorageLike | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null  // Safari private mode / storage disabled
  }
}
