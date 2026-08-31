/**
 * The role badge palette — ONE copy, for the whole console (Layer 1 F4, 2026-09-01).
 *
 * ── WHY THIS FILE EXISTS ──
 * Three files declared this mapping independently: `components/admin/StaffAdmin.tsx`,
 * `app/admin/organisation/reviewers/page.tsx` and `app/admin/guide/page.tsx` — the last with the
 * comment *"Reuse the Administration panel's role-badge palette so a role reads the same colour
 * everywhere."* A comment is not a mechanism. F4's codemod converted one copy's `amber` to
 * `caution` and left another's alone, and the three silently stopped agreeing: the same role would
 * have rendered one colour in Administration and another in the Manual, which a reader would
 * reasonably blame on the data rather than on us.
 *
 * ── WHY THESE ARE CATEGORY SWATCHES, NOT TONES ──
 * A role is a KIND of person, not a state. Converting by colour family would have made `org_admin`
 * (amber) a warning and `finance` (emerald) a success — assertions nobody meant. The
 * `category-N` family exists for exactly this: colours whose only job is to differ from each other.
 *
 * ⛔ Seven roles, seven DIFFERENT numbers. The unknown-role fallback is GROUND on purpose —
 * "no role we recognise" is not a category, and giving it a swatch would make an error look
 * like a valid eighth kind of person.
 */
export const ROLE_BADGE: Record<string, string> = {
  super: 'bg-category-1-surface text-category-1-ink',
  org_admin: 'bg-category-3-surface text-category-3-ink',
  admin: 'bg-category-8-surface text-category-8-ink',
  qc: 'bg-category-5-surface text-category-5-ink',
  finance: 'bg-category-2-surface text-category-2-ink',
  partner: 'bg-category-6-surface text-category-6-ink',
  reviewer: 'bg-category-7-surface text-category-7-ink',
}

/** The badge classes for a role, or the neutral ground for anything unrecognised. */
export function roleBadgeClass(role: string): string {
  return ROLE_BADGE[role] ?? 'bg-ground-100 text-ground-600'
}
