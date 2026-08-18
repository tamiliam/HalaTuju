/**
 * Answers the app's API calls from fixtures, so the real components mount without a backend.
 *
 * WHY REPLACE `fetch` RATHER THAN THE API MODULE. Every call in `src/lib/api.ts` funnels through
 * one `apiRequest()` that does `fetch(API_URL + endpoint)`. Stubbing at the network edge means the
 * components run their REAL data path — the same `listDocuments()`, the same loading states, the
 * same error handling. Stubbing `@/lib/api` instead would mean the sandbox exercises a different
 * code path from production, which is precisely the drift a sandbox is supposed to rule out.
 *
 * Anything unmatched resolves to a 404 rather than throwing. A sandbox that white-screens because
 * one unmapped endpoint rejected is useless to a designer, and an unmapped call is a gap in the
 * fixtures, not an emergency — it is logged so it can be added.
 */
import {
  sandboxApplication,
  sandboxConsent,
  sandboxDocuments,
} from './fixtures/scholarship'

type Handler = () => unknown

/**
 * Endpoint path → payload. Keys are matched by `endsWith` against the URL's PATHNAME, never the
 * full URL, so a stub cannot be defeated by the API base changing between environments.
 */
const ROUTES: Record<string, Handler> = {
  '/api/v1/scholarship/documents/': () => ({ documents: sandboxDocuments }),
  '/api/v1/scholarship/consent/': () => sandboxConsent,
  '/api/v1/scholarship/applications/': () => ({
    total_count: 1,
    applications: [sandboxApplication],
  }),
  '/api/v1/scholarship/intake/': () => ({ open: true, cohort_name: sandboxApplication.cohort_name }),
}

/**
 * Per-surface answers, layered OVER `ROUTES` for the surface currently mounted.
 *
 * One surface needs a DIFFERENT answer from the same endpoint: the apply form redirects away the
 * moment `/scholarship/applications/` returns one, because a returning applicant has nothing to
 * fill in. The Documents surface needs that same endpoint to return one. Both are correct; they
 * are different screens.
 *
 * Set during the surface page's RENDER, before its children mount and fetch — the same timing
 * `installStubFetch` itself relies on. Replaced wholesale on every surface change so one screen's
 * fixtures can never leak into the next.
 */
let overrides: Record<string, Handler> = {}

export function setSurfaceRoutes(routes?: Record<string, Handler>): void {
  overrides = routes ?? {}
}

function payloadFor(pathname: string): unknown | undefined {
  const table = { ...ROUTES, ...overrides }
  const key = Object.keys(table).find((route) => pathname.endsWith(route))
  return key ? table[key]() : undefined
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

let installed = false

/**
 * Install once, before any component mounts. Idempotent — React 18 StrictMode double-invokes
 * effects in development, and a second install would wrap the stub around itself.
 */
export function installStubFetch(): void {
  if (installed || typeof window === 'undefined') return
  installed = true

  const realFetch = window.fetch.bind(window)

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url

    let pathname: string
    try {
      pathname = new URL(url, window.location.origin).pathname
    } catch {
      return realFetch(input as RequestInfo, init)
    }

    // Next.js's own machinery (RSC payloads, HMR) must reach the real network or the page dies.
    if (!pathname.startsWith('/api/')) return realFetch(input as RequestInfo, init)

    const body = payloadFor(pathname)
    if (body === undefined) {
      // eslint-disable-next-line no-console
      console.warn(`[sandbox] no fixture for ${init?.method ?? 'GET'} ${pathname}`)
      return jsonResponse({ error: 'No sandbox fixture for this endpoint.' }, 404)
    }

    // A write is accepted and discarded. The sandbox renders; it does not persist. Returning the
    // unchanged fixture keeps a component's optimistic path working without inventing state that
    // would then disagree with the next read.
    return jsonResponse(body)
  }
}
