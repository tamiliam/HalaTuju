/**
 * Read-only peek at THE APPLY DRAFT (`./applyDraft`) for the onboarding pages visited DURING the "edit
 * my results" detour: her in-progress school and state beat the profile's older ones. Same checks as
 * `readApplyDraft` (format, 24 h, her user id), but it deletes nothing.
 *
 * Its own leaf (Mobile M4) only so /scholarship/apply — which never peeks — does not carry it: that
 * route had no bytes to spare.
 */
import { parse, strip, type DraftForm } from './applyDraft'

export function peekApplyDraft(uid?: string | null): DraftForm | null {
  const e = parse()
  // No user id yet (sign-in still loading) is NOT a match (review F2): someone else's draft must never
  // pre-fill this person's onboarding while the session settles.
  return e && uid && e.uid === uid ? strip(e.form) : null
}
