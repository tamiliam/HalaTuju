/**
 * The apply form's "edit results" RETURN marker, and the sessionStorage seam it rides on.
 *
 * A LEAF on purpose (TD-057, 2026-10-01): the dashboard clears this marker on every visit, and
 * importing it through `@/lib/scholarship` cost `/dashboard` ~6 kB of first-load JS for one
 * `removeItem`. `scholarship.ts` re-exports all of it, so every existing import is unchanged.
 * See `scholarship.ts` ("My Results → onboarding round-trip") for how the marker is set and read.
 */

export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

/** sessionStorage if available (browser), else null (SSR / node tests without injection). */
export function safeSession(): StorageLike | null {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null
  } catch {
    return null
  }
}

export const APPLY_RETURN_KEY = 'halatuju_apply_return'

/** True when onboarding was entered from the apply form (should return to it). */
export function hasApplyReturn(storage?: StorageLike): boolean {
  const s = storage ?? safeSession()
  return !!s && s.getItem(APPLY_RETURN_KEY) === '1'
}

/** Clear the return marker — after routing back to the apply page, on an ordinary apply-page
 *  visit, and on a dashboard visit (the detour was abandoned — TD-057). */
export function clearApplyReturn(storage?: StorageLike): void {
  const s = storage ?? safeSession()
  s?.removeItem(APPLY_RETURN_KEY)
}
