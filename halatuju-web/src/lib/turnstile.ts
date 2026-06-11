/**
 * Cloudflare Turnstile — invisible, on-demand token fetch.
 *
 * Used to satisfy Supabase Auth's captcha protection (student anonymous sign-in,
 * sponsor/admin password sign-in, sign-up and password reset) and to gate the
 * public contact form (via a Supabase Edge Function). The site key is PUBLIC
 * (`NEXT_PUBLIC_TURNSTILE_SITE_KEY`); the secret never touches the browser.
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
 * Graceful degradation:
 *   With no site key configured (local dev, or before the Cloudflare widget is
 *   wired), `getTurnstileToken()` resolves to `undefined`. Callers still work, and
 *   Supabase only *enforces* the token once the dashboard captcha toggle is on —
 *   which lets us ship and deploy this wiring safely BEFORE flipping that switch.
 */

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
const TOKEN_TIMEOUT_MS = 8000 // never hang an auth flow on the captcha

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

function loadScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'))
  if (window.turnstile) return Promise.resolve()
  if (scriptPromise) return scriptPromise
  scriptPromise = new Promise<void>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = SCRIPT_SRC
    s.async = true
    s.defer = true
    s.onload = () => resolve()
    s.onerror = () => {
      scriptPromise = null
      reject(new Error('Turnstile script failed to load'))
    }
    document.head.appendChild(s)
  })
  return scriptPromise
}

// One singleton widget, reused across every token fetch. The container is fixed
// and centred (NOT off-screen) so that, on the rare occasion Turnstile must show
// an interaction challenge, the visitor can actually see and solve it.
let container: HTMLDivElement | null = null
let widgetId: string | null = null
let currentResolve: ((token: string | undefined) => void) | null = null
// Serialise: Turnstile reuses one widget, so concurrent fetches would clobber
// each other's token. Chain them instead.
let queue: Promise<string | undefined> = Promise.resolve(undefined)

function ensureWidget(api: TurnstileAPI): void {
  if (widgetId && container) return
  container = document.createElement('div')
  container.style.position = 'fixed'
  container.style.top = '50%'
  container.style.left = '50%'
  container.style.transform = 'translate(-50%, -50%)'
  container.style.zIndex = '2147483647'
  document.body.appendChild(container)
  widgetId = api.render(container, {
    sitekey: SITE_KEY,
    execution: 'execute', // run only when execute() is called
    appearance: 'interaction-only', // show nothing on a silent pass; only appear if interaction is required
    retry: 'never', // we handle failure by resolving undefined, no auto-retry loop
    callback: (token: string) => {
      const r = currentResolve
      currentResolve = null
      r?.(token)
    },
    'error-callback': () => {
      const r = currentResolve
      currentResolve = null
      r?.(undefined)
    },
    'timeout-callback': () => {
      const r = currentResolve
      currentResolve = null
      r?.(undefined)
    },
  })
}

async function fetchToken(action?: string): Promise<string | undefined> {
  if (!SITE_KEY || typeof window === 'undefined') return undefined
  try {
    await loadScript()
    const api = window.turnstile
    if (!api) return undefined
    ensureWidget(api)
    if (!widgetId || !container) return undefined
    return await new Promise<string | undefined>((resolve) => {
      currentResolve = resolve
      const timer = setTimeout(() => {
        if (currentResolve === resolve) {
          currentResolve = null
          resolve(undefined)
        }
      }, TOKEN_TIMEOUT_MS)
      const done = (t: string | undefined) => {
        clearTimeout(timer)
        resolve(t)
      }
      // Wrap resolve so the timer is always cleared.
      currentResolve = done
      try {
        api.reset(widgetId!) // clear any prior single-use token
        api.execute(container!, action ? { action } : undefined)
      } catch {
        if (currentResolve === done) {
          currentResolve = null
          done(undefined)
        }
      }
    })
  } catch {
    return undefined
  }
}

/**
 * Fetch a fresh, single-use Turnstile token without (normally) showing anything.
 * Resolves to `undefined` when Turnstile is unconfigured or can't produce a token,
 * so callers degrade gracefully. `action` is an optional label for analytics.
 */
export function getTurnstileToken(action?: string): Promise<string | undefined> {
  // Serialise against the shared singleton widget.
  const next = queue.then(() => fetchToken(action))
  // Keep the queue alive even if a fetch rejects (it shouldn't, but be safe).
  queue = next.catch(() => undefined)
  return next
}

/** True when a Turnstile site key is configured (captcha wiring is active). */
export function isTurnstileConfigured(): boolean {
  return !!SITE_KEY
}
