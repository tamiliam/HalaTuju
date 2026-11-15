/**
 * The IC and name LOCKS, and the card flags (#67 scope 3 bundle fit, 2026-11-15) — the part of
 * `icEditor.ts` the /profile page itself reads (its padlocks and its "Please check" row). Split
 * out so the page's first load carries only these; everything the edit panel alone needs stays
 * in `icEditor.ts`, which only that lazily fetched panel imports. See `icEditor.ts` for why the
 * rule has a name and a test.
 */

/** Codes the API sends on `ic_flags`. The screen owns the wording; these are just the cases. */
export type IcFlag = 'nric_one_digit' | 'nric_differs' | 'name_incomplete' | 'name_differs'

const KNOWN_FLAGS: readonly IcFlag[] = [
  'nric_one_digit', 'nric_differs', 'name_incomplete', 'name_differs',
]

/**
 * May the student edit their IC number?
 *
 * ONLY the stored lock decides. Deliberately NOT `identity_verified`, which is broader (it also
 * greens for a matching-but-unlocked card) and is re-derived on every read, so keying on it
 * would both lock people the rule hasn't locked and unlock them again if they deleted the card.
 *
 * Undefined means the payload predates this field — treat as LOCKED. An old client showing an
 * editable box is the wrong way to be wrong: the save would be refused server-side anyway, and
 * offering an edit that cannot work is worse than offering none.
 */
export function canEditIc(profile: { nric_locked?: boolean } | null | undefined): boolean {
  if (!profile) return false
  return profile.nric_locked === false
}

/**
 * May the student edit their NAME? (#67 scope 3, 2026-11-14.)
 *
 * The name is held to the IC by the same stored lock as the number: once `name_locked` is true
 * the server takes only the card's own name. Undefined means the payload predates the field —
 * treat as EDITABLE, as the name always was (the server still refuses a locked change).
 */
export function canEditName(profile: { name_locked?: boolean } | null | undefined): boolean {
  return !profile?.name_locked
}

/** Only flags we have copy for — an unrecognised code must never render as a raw dotted key. */
export function icFlags(flags: string[] | undefined): IcFlag[] {
  if (!flags?.length) return []
  return flags.filter((f): f is IcFlag => (KNOWN_FLAGS as readonly string[]).includes(f))
}

/**
 * Is there anything to show the student about their card?
 *
 * True even when the record LOCKED — a shorter-than-the-card name locks and is still worth
 * aligning, and nothing else in the product will ever ask them to.
 */
export function hasIcFlags(flags: string[] | undefined): boolean {
  return icFlags(flags).length > 0
}
