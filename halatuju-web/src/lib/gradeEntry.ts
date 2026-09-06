/**
 * Rules for what the SPM grades page is allowed to SAVE.
 *
 * The page keeps three parallel things: which subjects sit in the four stream slots, which sit in
 * the elective slots, and the grades typed against them. A slot can name a subject with no grade
 * behind it — the student opened the dropdown and stopped, or (before 2026-09-02) the page itself
 * pre-filled four Science subjects nobody had chosen.
 *
 * Saving such a slot records a subject the student never sat. `prepare_merit_inputs` then scored
 * it at G inside the 30% stream band; that half is fixed at source now, but the record was wrong
 * on its own terms, and this is where it was written.
 */

/**
 * The subject ids from `ids` that carry a non-blank grade, in their original order.
 *
 * ⚠ This is deliberately stricter than `filter(Boolean)`, which only drops an EMPTY slot. Blank
 * ids are dropped too, and duplicates are left alone — the page's own dropdowns prevent those,
 * and silently collapsing them here would hide a bug rather than fix one.
 */
export function gradedOnly(ids: string[], grades: Record<string, string>): string[] {
  return ids.filter((id) => Boolean(id) && Boolean(grades[id]))
}
