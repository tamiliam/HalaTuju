/**
 * Cloudflare Turnstile — invisible, on-demand token fetch.
 *
 * Used to satisfy Supabase Auth's captcha protection (sponsor/admin password sign-in, sponsor
 * sign-up and password reset) and to gate the public contact form (via a Supabase Edge
 * Function). The site key is PUBLIC (`NEXT_PUBLIC_TURNSTILE_SITE_KEY`); the secret never
 * touches the browser.
 *
 * Design — invisible with a visible fallback:
 *   We render ONE explicit widget with `execution: 'execute'` + `appearance:
 *   'interaction-only'`, so nothing runs until we call `turnstile.execute()` and
 *   nothing is shown on a silent pass (no lingering Cloudflare "Success!" badge).
 *   For the vast majority (Managed mode) the challenge is non-interactive and the
 *   visitor sees nothing. Only genuinely suspicious traffic gets a visible,
 *   centred interaction modal — so a flagged real user can still pass, rather than
 *   being silently blocked. Tokens are single-use and ~300s-lived, so we reset and
 *   fetch a fresh one immediately before each auth/insert call.
 *
 * ⚠ CAPTCHA REPAIR (2026-11-19). The Supabase captcha switch is ON. Before this repair a fetch
 * that failed for ANY reason resolved to `undefined`, the callers then called Supabase with no
 * token, and the visitor saw Supabase's raw "captcha protection: request disallowed". Now:
 *   - `getTurnstileResult()` returns a TYPED outcome — `ok` (with the token), `off` (no site key:
 *     local dev), `blocked` (the Cloudflare script never loaded: ad blocker, firewall, network)
 *     or `failed` (the script loaded but the challenge errored or ran out of time, after a retry).
 *     The auth callers (`lib/captchaAuth.ts`) turn `blocked`/`failed` into a known error code and
 *     NEVER call Supabase without a token.
 *   - The silent budget is 15 s per attempt (was 8 s), and a failed attempt is retried once with
 *     reset + execute. Why 15 s: a Managed pass is ~1 s on a good line, but the challenge makes
 *     several round trips to challenges.cloudflare.com, and on a congested mobile connection
 *     (the students' and many sponsors' normal network) those trips alone ran past 8 s, which cut
 *     off real visitors. 15 s covers that without leaving a person staring at a frozen button for
 *     long. Worst-case waits for one password door (`lib/captchaAuth.ts`), Supabase's own time
 *     aside: SILENT 55 s = script 10 s + 2 x 15 s, plus 15 s for the single-attempt retry after a
 *     Supabase captcha refusal. VISIBLE 145 s = 10 s + 15 s + 120 s for the challenge, and 265 s
 *     only if Supabase then refuses that token AND Cloudflare asks the person to click again
 *     (120 s more) — a person mid-challenge is never cut off.
 *   - When the last attempt fails, the widget is reset (and kept hidden) before `failed` is
 *     returned, and a challenge that starts with no attempt in flight is cancelled, so no box
 *     can appear after the error is on screen.
 *   - The script load has its own 10 s budget. A firewall that silently DROPS the request (rather
 *     than refusing it) never fires `onerror`; without this the visitor would wait forever and we
 *     could not tell "blocked" apart from "failed".
 *   - Expiry: `refresh-expired: 'manual'` + `expired-callback` resets the widget when an unused
 *     token lapses, so a stale token is never handed out; and a token is never kept between
 *     calls — each fetch resets and executes afresh. A caller whose token Supabase still refuses
 *     (lapsed in flight, or a duplicate) asks for one fresh token and tries once more
 *     (`lib/captchaAuth.ts`).
 *
 * Graceful degradation:
 *   With no site key configured (local dev), the result is `off` and `getTurnstileToken()`
 *   resolves to `undefined`; callers proceed without a token, which only works while the
 *   Supabase dashboard captcha toggle is off.
 */

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
/** How long the Cloudflare script may take to arrive before we call it blocked. */
export const SCRIPT_LOAD_TIMEOUT_MS = 10000
/** Silent-path budget per attempt (see the header for why 15 s). */
export const SILENT_TIMEOUT_MS = 15000
/** Once Cloudflare shows a VISIBLE challenge, a human needs time to notice and click. */
export const INTERACTIVE_TIMEOUT_MS = 120000
/** One try plus one retry (reset + execute). */
export const MAX_ATTEMPTS = 2

export type TurnstileResult =
  | { status: 'ok'; token: string }
  | { status: 'off' }
  | { status: 'blocked' }
  | { status: 'failed' }

interface TurnstileAPI {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string
  execute: (el: HTMLElement | string, opts?: Record<string, unknown>) => void
  reset: (el?: HTMLElement | string) => void
  remove: (el: HTMLElement | string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileAPI
  }
}

let scriptPromise: Promise<void> | null = null

// The script is requested once. A call that waits past SCRIPT_LOAD_TIMEOUT_MS gives up (blocked)
// but leaves the request in flight, so a slow script that arrives later serves the next call.
// A script that FAILS (onerror) is removed and forgotten, so the next call asks again.
function loadScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'))
  if (window.turnstile) return Promise.resolve()
  if (!scriptPromise) {
    const s = document.createElement('script')
    const p = new Promise<void>((resolve, reject) => {
      s.src = SCRIPT_SRC
      s.async = true
      s.defer = true
      s.onload = () => resolve()
      s.onerror = () => {
        if (scriptPromise === p) scriptPromise = null
        try { s.remove() } catch { /* already gone */ }
        reject(new Error('Turnstile script failed to load'))
      }
    })
    // A rejection nobody is waiting for any more (the caller timed out) must not surface.
    p.catch(() => undefined)
    scriptPromise = p
    // Appended only once `scriptPromise` is set, so an error that fires at once still clears it.
    document.head.appendChild(s)
  }
  const pending = scriptPromise
  return new Promise<void>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('Turnstile script load timed out')), SCRIPT_LOAD_TIMEOUT_MS)
    pending.then(
      () => { clearTimeout(t); resolve() },
      (e) => { clearTimeout(t); reject(e) },
    )
  })
}

// One singleton widget, reused across every token fetch. The container is fixed,
// centred and top-most, but kept HIDDEN until Cloudflare actually needs to show an
// interaction challenge — so a silent pass shows nothing, and a finished challenge
// (passed OR failed) never lingers on screen over the app.
let container: HTMLDivElement | null = null
let widgetId: string | null = null
type AttemptOutcome = { token: string; humanTimedOut?: undefined } | { token?: undefined; humanTimedOut: boolean }
let currentResolve: ((outcome: AttemptOutcome) => void) | null = null
let timer: ReturnType<typeof setTimeout> | null = null
// Serialise: Turnstile reuses one widget, so concurrent fetches would clobber
// each other's token. Chain them instead.
let queue: Promise<unknown> = Promise.resolve()

function show(): void { if (container) container.style.display = '' }
function hide(): void { if (container) container.style.display = 'none' }

// Resolve the in-flight attempt exactly once: clear any timer, HIDE the widget (so no
// box is ever left on screen), then hand the outcome back. A callback that arrives after
// the attempt settled (a late token after a timeout) finds no resolver and is dropped.
function settle(outcome: AttemptOutcome): void {
  if (timer) { clearTimeout(timer); timer = null }
  hide()
  const r = currentResolve
  currentResolve = null
  r?.(outcome)
}

function ensureWidget(api: TurnstileAPI): void {
  if (widgetId && container) return
  container = document.createElement('div')
  container.style.position = 'fixed'
  container.style.top = '50%'
  container.style.left = '50%'
  container.style.transform = 'translate(-50%, -50%)'
  container.style.zIndex = '2147483647'
  container.style.display = 'none' // revealed only while an interaction challenge is actually up
  document.body.appendChild(container)
  widgetId = api.render(container, {
    sitekey: SITE_KEY,
    execution: 'execute', // run only when execute() is called
    appearance: 'interaction-only', // show nothing on a silent pass; only appear if interaction is required
    retry: 'never', // WE retry (reset + execute, MAX_ATTEMPTS), so the budget stays ours
    'refresh-expired': 'manual', // an expired token is never silently re-fetched behind our back
    callback: (token: string) => settle({ token }),
    'error-callback': () => settle({ humanTimedOut: false }),
    'timeout-callback': () => settle({ humanTimedOut: true }),
    // A token that lapsed unused (~300 s) is cleared so it can never be handed out.
    'expired-callback': () => {
      try { if (widgetId) api.reset(widgetId) } catch { /* the next fetch resets anyway */ }
    },
    // Cloudflare is about to show a VISIBLE challenge that needs a human. Reveal the
    // widget and swap the silent budget for a generous human one.
    'before-interactive-callback': () => {
      // No attempt in flight (it already failed and the visitor has the error): a late challenge
      // must never pop up over the page. Cancel it and stay hidden.
      if (!currentResolve) {
        try { if (widgetId) api.reset(widgetId) } catch { /* nothing more to stop */ }
        return
      }
      show()
      if (timer) { clearTimeout(timer); timer = null }
      timer = setTimeout(() => settle({ humanTimedOut: true }), INTERACTIVE_TIMEOUT_MS)
    },
  })
}

function attempt(api: TurnstileAPI, action?: string): Promise<AttemptOutcome> {
  return new Promise<AttemptOutcome>((resolve) => {
    currentResolve = resolve
    // Silent-path budget. If an interaction challenge appears,
    // before-interactive-callback REPLACES this with the longer human budget.
    timer = setTimeout(() => settle({ humanTimedOut: false }), SILENT_TIMEOUT_MS)
    try {
      api.reset(widgetId!) // clear any prior single-use or expired token
      api.execute(container!, action ? { action } : undefined)
    } catch {
      settle({ humanTimedOut: false })
    }
  })
}

/** Options for one fetch. `maxAttempts` caps the attempts below `MAX_ATTEMPTS` (never above):
 *  the retry after a Supabase captcha refusal asks for 1, so it adds one attempt, not a round. */
export interface TurnstileFetchOptions { maxAttempts?: number }

async function fetchResult(action?: string, opts?: TurnstileFetchOptions): Promise<TurnstileResult> {
  if (!SITE_KEY) return { status: 'off' }
  if (typeof window === 'undefined') return { status: 'failed' }
  try {
    await loadScript()
  } catch {
    return { status: 'blocked' }
  }
  const api = window.turnstile
  if (!api) return { status: 'blocked' }
  try {
    ensureWidget(api)
  } catch {
    return { status: 'failed' }
  }
  if (!widgetId || !container) return { status: 'failed' }
  const attempts = Math.max(1, Math.min(MAX_ATTEMPTS, opts?.maxAttempts ?? MAX_ATTEMPTS))
  for (let i = 0; i < attempts; i++) {
    const outcome = await attempt(api, action)
    if (outcome.token) return { status: 'ok', token: outcome.token }
    // A person who was shown a visible challenge and let it run out has had their chance;
    // a second two-minute wait would only look like a frozen page.
    if (outcome.humanTimedOut) break
  }
  // Out of attempts. Stop whatever challenge Cloudflare may still be running, so a late
  // challenge box cannot appear AFTER the visitor has been shown the error.
  try { api.reset(widgetId) } catch { /* nothing more to stop */ }
  hide()
  return { status: 'failed' }
}

/**
 * Fetch a fresh, single-use Turnstile token, with a typed outcome (see `TurnstileResult`).
 * Never rejects. `action` is an optional label for analytics.
 */
export function getTurnstileResult(action?: string, opts?: TurnstileFetchOptions): Promise<TurnstileResult> {
  // Serialise against the shared singleton widget.
  const next = queue.then(() => fetchResult(action, opts)).catch((): TurnstileResult => ({ status: 'failed' }))
  queue = next
  return next
}

/**
 * The token alone, or `undefined` when there is none. Kept for the contact form, which hands
 * the decision to its Edge Function; the auth callers use `getTurnstileResult()`.
 */
export async function getTurnstileToken(action?: string): Promise<string | undefined> {
  const r = await getTurnstileResult(action)
  return r.status === 'ok' ? r.token : undefined
}

/** True when a Turnstile site key is configured (captcha wiring is active). */
export function isTurnstileConfigured(): boolean {
  return !!SITE_KEY
}
