/**
 * The apply form's "edit results" RETURN marker, the gift-code key, and the sessionStorage seam
 * they ride on.
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

/** Mark that onboarding should return to the apply form (the "edit my results" detour). */
export function setApplyReturn(storage?: StorageLike): void {
  const s = storage ?? safeSession()
  s?.setItem(APPLY_RETURN_KEY, '1')
}

/** THE APPLY DRAFT (Mobile M4, owner ruling: this tab only) — the half-filled form, kept so an iOS
 *  tab kill or the "edit my results" detour loses nothing. ONE key for both: the detour's old
 *  whole-form stash (`halatuju_apply_stash`, which held the IC and the typed signature and restored
 *  for whoever opened the form next) is gone. What it holds and every rule for reading it:
 *  `./applyDraft`. Wiped with every `halatuju_` tab key at sign-out and on any SIGNED_OUT. */
export const APPLY_STASH_KEY = 'halatuju_apply_draft'

/** The detour was ABANDONED (the dashboard, TD-057): drop the return marker, so a later ordinary
 *  onboarding does not route back to the form. The DRAFT stays on purpose (Mobile M4): it is bound to
 *  her user id and programme and expires in 24 h (`./applyDraft`), so it can no longer pre-fill the
 *  form for anyone else — and leaving the form for the dashboard must not throw her typing away. */
export function abandonApplyDetour(storage?: StorageLike): void {
  const s = storage ?? safeSession()
  s?.removeItem(APPLY_RETURN_KEY)
}

/** The gift (programme code) the apply page is open for — written on arrival from `?p=` or a pick
 *  in the chooser, cleared on a bare arrival and on submit. See `enterApplyPage` in scholarship.ts. */
export const APPLY_PROGRAMME_KEY = 'halatuju_apply_programme'
// (The way back to the form WITH that gift, `applyPagePath`, is its own leaf: ./applyPagePath.)
