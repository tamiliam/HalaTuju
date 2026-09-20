/**
 * The fetch helper every student-facing call in `@/lib/api` goes through.
 *
 * ⚠ PRIVATE TO THIS FOLDER — `apiRequest` and `ApiOptions` are not re-exported by the barrel,
 * because `api.ts` never exported them.
 *
 * ⚠ NOT the same helper as `admin-api/client.ts`, and they must not be merged: this one turns
 * a 403 `nric_required` into an `nric-required` window event and carries DRF field errors on
 * a 400; `adminFetch` does neither. Both behaviours are deliberate.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface ApiOptions {
  token?: string
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit & ApiOptions = {}
): Promise<T> {
  const { token, ...fetchOptions } = options

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(options.headers || {}),
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    if (response.status === 403 && error.code === 'nric_required') {
      window.dispatchEvent(new CustomEvent('nric-required'))
      throw new Error('NRIC verification required')
    }
    const err = new Error(error.message || `API error: ${response.status}`)
    // Carry the backend error code (e.g. 'doc_limit_reached') so callers can
    // map it to a localised message.
    ;(err as Error & { code?: string }).code = error.error || error.code || ''
    // Carry DRF field-level validation errors (400) — e.g.
    // { parents_occupation: ["Ensure this field has no more than 5000 characters."] }
    // so callers can tell the student WHICH answer to fix, not just "save failed".
    if (response.status === 400 && error && typeof error === 'object') {
      ;(err as Error & { fieldErrors?: unknown }).fieldErrors = error
    }
    throw err
  }

  return response.json()
}

