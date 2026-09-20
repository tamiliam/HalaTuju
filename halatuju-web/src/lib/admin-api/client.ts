/**
 * The private fetch helpers every admin call in `@/lib/admin-api` goes through, and the
 * gift-scope query string they share.
 *
 * ⚠ PRIVATE TO THIS FOLDER — none of these is re-exported by the barrel, because `admin-api.ts`
 * never exported them. A test that reaches for `adminFetch` is reaching past the seam.
 *
 * ⚠ NOT the same helper as `api/client.ts`, and they must not be merged: `apiRequest` turns a
 * 403 `nric_required` into a window event and carries DRF field errors on a 400; `adminFetch`
 * does neither, because no admin screen has an NRIC gate. Both behaviours are deliberate.
 *
 * ⚠ FOUR SPANS of the old `admin-api.ts` (15-38, 1288-1314, 1595-1613, 3002-3012). The three
 * later helpers were each written beside the first call that needed them, 1,300 lines apart.
 */
import type { BursaryAgreement } from '@/lib/api'

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ApiOptions {
  token?: string
}

export async function adminFetch<T>(path: string, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  const res = await fetch(`${API_BASE}${path}`, { headers })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Admin API error: ${res.status}`)
  }

  return res.json()
}

export async function adminMutate<T>(path: string, method: string, body: unknown, options?: ApiOptions): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method, headers, body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Admin API error: ${res.status}`) as Error
      & { status?: number; code?: string; body?: Record<string, unknown> }
    err.status = res.status
    err.code = b.code || b.error || ''
    // Keep the whole error body: some codes carry a detail the UI needs to render a useful
    // message rather than restate a rule (e.g. 'too_early' → `earliest`, the first date a run
    // covering that month may be paid, computed by payments.earliest_payment_date).
    err.body = b
    throw err
  }
  // ⚠ A SUCCESSFUL DELETE ANSWERS 204 WITH NO BODY, and `res.json()` throws on an empty one — so
  // the call would have failed on the happy path only, which is the worst shape of bug: the write
  // lands, the caller sees an error, and a person presses again. Every existing caller returns a
  // body and is unaffected. Widened here rather than making one endpoint answer 200-with-a-body,
  // because the next DELETE would meet the same wall.
  if (res.status === 204) return undefined as T
  return res.json()
}

// A thin POST helper that carries the HTTP status on the thrown error so the
// cockpit card can surface a 403 (e.g. a non-referring-org admin trying to
// witness) gracefully, rather than as a generic failure.
export async function adminBursaryPost(path: string, body: unknown, options?: ApiOptions): Promise<BursaryAgreement> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (options?.token) headers['Authorization'] = `Bearer ${options.token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST', headers, body: body != null ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    const err = new Error(b.error || `Admin API error: ${res.status}`) as Error & { status?: number; code?: string }
    err.status = res.status
    err.code = b.error || b.code || ''
    throw err
  }
  return res.json()
}

/**
 * `?programme=<code>` for a Programme-scope call, or '' when the caller could not say.
 *
 * ⚠ AN EMPTY STRING IS A REAL ANSWER AND MUST STAY ONE. `programmeScope` resolves a single
 * gift itself and refuses to guess between several, so an absent code means the client
 * genuinely does not know — and the server answers with everything the organisation fence
 * already allowed rather than picking one. Never default this to "the first gift".
 */
export const giftQuery = (programme?: string) =>
  (programme ? `?programme=${encodeURIComponent(programme)}` : '')

