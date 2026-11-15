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
 *
 * #67 scope 3 bundle fit (2026-11-15): the locks and the flag filter live in `icLock.ts` (the
 * page reads them) and the card-name comparison in `cardName.ts` (the apply form reads it). This
 * file keeps what only the lazily fetched edit panel needs, and re-exports the rest, so it is
 * still the one place to read the rules.
 */
import { sameLettersAsCard } from './cardName'
import { icFlags } from './icLock'

export { canEditIc, canEditName, hasIcFlags, icFlags, type IcFlag } from './icLock'
export { sameLettersAsCard }

/**
 * May a LOCKED student take the name on their card? (#67 scope 3 review.) The one name change a
 * locked record allows. Offered only when the server says it would take it (`takeable`, the
 * profile's `name_card_takeable`: their own card, exact number, cleanly read, genuine, and a name
 * that differs), so the button never leads to a 403 `name_locked`; and never once the name on
 * screen already is the card's.
 */
export function canTakeCardName(nameLocked: boolean, name: string, cardName: string, takeable: boolean): boolean {
  return nameLocked && takeable && !!cardName.trim() && !sameLettersAsCard(name, cardName)
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

/**
 * Which side, if any, the student can act on.
 *
 * `nric` flags are actionable only while unlocked. A NAME flag is actionable while the name is
 * editable — always, until #67 scope 3 (2026-11-14) put the name under the same lock — or, once
 * locked, while the student can take the card's own name (`canTakeCardNameField`, the "Use the
 * name on my IC" action). Otherwise a locked name goes to support, like a locked number.
 *
 * `neither` is a real answer, not a fallback: a locked record whose number disagrees is exactly
 * the orphaned-claim case, and the honest thing is to tell them to contact us rather than point
 * at a field they cannot change.
 */
export function icFixableSide(
  flags: string[] | undefined,
  canEdit: boolean,
  canEditNameField = true,
  canTakeCardNameField = false,
): 'nric' | 'name' | 'both' | 'neither' {
  const fs = icFlags(flags)
  const nameFlag = (canEditNameField || canTakeCardNameField) && fs.some((f) => f === 'name_incomplete' || f === 'name_differs')
  const nricFlag = fs.some((f) => f === 'nric_one_digit' || f === 'nric_differs')
  const nric = nricFlag && canEdit
  if (nric && nameFlag) return 'both'
  if (nric) return 'nric'
  if (nameFlag) return 'name'
  return 'neither'
}
