/** The Vircle account-type self-check on the Action-Centre setup card (owner, 2026-09-09).
 *
 *  Vircle applies its 18+ rule by BIRTH YEAR, not birthday — 1 January is the transition, so a
 *  student born 31/12/2008 counts as 18 while one born 1/1/2009 does not. The server derives the
 *  EXPECTED account type from that rule (`vircle.can_register`) and serves it on the resolution
 *  item as `vircle_expected`. The dropdown defaults to the expectation; picking the other value
 *  shows a coaching note but NEVER blocks the confirm — the server accepts either, and a
 *  client-side wall the server does not hold would strand edge cases (an 18-year-old genuinely
 *  added as a child under a parent's account is legitimate).
 */

export type VircleAccountType = 'principal' | 'child'

/** The served expectation, degraded safely: anything but 'child' reads as 'principal' —
 *  the common case, and the safe default when the payload predates the field. */
export function expectedAccountType(served?: string | null): VircleAccountType {
  return served === 'child' ? 'child' : 'principal'
}

/** The i18n key of the coaching note for a selection that disagrees with the expectation,
 *  or null when they agree (no note). One key per direction — the advice differs:
 *  an adult on a Child account should re-register; a minor cannot register at all. */
export function accountWarningKey(
  selected: VircleAccountType, expected: VircleAccountType,
): string | null {
  if (selected === expected) return null
  return selected === 'child'
    ? 'scholarship.actionCentre.vircle.warnChildAdult'
    : 'scholarship.actionCentre.vircle.warnPrincipalMinor'
}
