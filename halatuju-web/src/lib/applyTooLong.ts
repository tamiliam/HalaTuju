/**
 * The apply form's "which answer is too long" helpers. A leaf of their own so `/scholarship/apply`
 * fetches them only when a submit is refused for length (the error path), not in its first-load JS.
 */

// ── Save-error helpers (actionable validation messages) ──────────────────
// The Story/Funding label map is `STORY_FIELD_LABEL_KEYS` in `./nextSteps`; the same idea for
// the /apply form's typed fields (profile + application):
export const APPLY_FIELD_LABEL_KEYS: Record<string, string> = {
  name: 'scholarship.apply.field.name',
  school: 'scholarship.apply.field.school',
  pre_u_studied_at: 'scholarship.preU.label',
  contact_phone: 'scholarship.apply.field.phone',
  preferred_state: 'scholarship.apply.field.state',
  declaration_name: 'scholarship.apply.declaration.signLabel',
  other_scholarships_text: 'scholarship.apply.otherScholarshipsLabel',
  anything_else: 'scholarship.apply.anythingElseLabel',
  uncertainty_note: 'scholarship.apply.plan.uncertainNoteLabel',
}

/**
 * Walk a DRF 400 error body and return the first field key whose message is a
 * length-limit error (possibly nested, e.g. funding_need.funding_note), or null.
 * Lets the caller show "Your answer to "<question>" is too long" instead of a
 * generic "could not save".
 */
export function firstTooLongField(errors: unknown): string | null {
  if (!errors || typeof errors !== 'object') return null
  for (const [key, val] of Object.entries(errors as Record<string, unknown>)) {
    if (Array.isArray(val)) {
      if (val.some((m) => typeof m === 'string' && /no more than|too long|characters/i.test(m))) {
        return key
      }
    } else if (val && typeof val === 'object') {
      const nested = firstTooLongField(val)
      if (nested) return nested
    }
  }
  return null
}
