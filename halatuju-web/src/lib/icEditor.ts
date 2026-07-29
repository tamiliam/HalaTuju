/**
 * The IC field on /profile — the pure decisions (2026-07-29).
 *
 * Kept out of the component because the padlock has been WRONG since the field was built, and
 * wrong in a way review never caught: `disabled` was a bare attribute and the padlock icon had
 * no condition, so every student was told their IC was locked. On production that was 85 of 143
 * applicants, including accounts with no application at all. It is also why Cikgu Gopal's
 * "you can correct it on your Profile page" reads as nonsense — the page shows a padlock and a
 * greyed-out box.
 *
 * So the rule gets a name and a test rather than living inline as a JSX attribute.
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
 * Show the real number while editing, the masked one at rest.
 *
 * Not cosmetic: the field rendered `maskIc(nric)` into a disabled input, so simply enabling it
 * would have let the student edit `****-**-2022` and submit asterisks.
 */
export function icFieldValue(nric: string, masked: string, editing: boolean): string {
  if (!nric) return ''
  return editing ? nric : masked
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

/**
 * Which side, if any, the student can act on.
 *
 * `nric` flags are actionable only while unlocked. A NAME flag is always actionable, because the
 * name field has always been editable and is not covered by the lock.
 *
 * `neither` is a real answer, not a fallback: a locked record whose number disagrees is exactly
 * the orphaned-claim case, and the honest thing is to tell them to contact us rather than point
 * at a field they cannot change.
 */
export function icFixableSide(
  flags: string[] | undefined,
  canEdit: boolean,
): 'nric' | 'name' | 'both' | 'neither' {
  const fs = icFlags(flags)
  const nameFlag = fs.some((f) => f === 'name_incomplete' || f === 'name_differs')
  const nricFlag = fs.some((f) => f === 'nric_one_digit' || f === 'nric_differs')
  const nric = nricFlag && canEdit
  if (nric && nameFlag) return 'both'
  if (nric) return 'nric'
  if (nameFlag) return 'name'
  return 'neither'
}
