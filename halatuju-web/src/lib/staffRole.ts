/**
 * People → Change role (staff lifecycle, 2026-10-09): which role a person may be switched to.
 *
 * Owner's ruling: Admin ↔ Finance and Reviewer ↔ QC, never to or from org_admin, super or
 * partner. This map mirrors `ROLE_PAIRS` in `apps/scholarship/staff_lifecycle.py`, which is the
 * real gate — the screen only uses it to offer the ONE role the server would accept, never a menu
 * of roles it would refuse.
 * drift-test: halatuju-web/src/lib/__tests__/staffRoleDrift.test.ts
 */
export const ROLE_PARTNER: Readonly<Record<string, string>> = {
  admin: 'finance',
  finance: 'admin',
  reviewer: 'qc',
  qc: 'reviewer',
}

/** The role this person could be switched to, or null when the row offers no switch at all. */
export function switchableTo(p: { role: string; is_active: boolean; is_super_admin?: boolean }) {
  if (!p.is_active || p.is_super_admin) return null
  return ROLE_PARTNER[p.role] ?? null
}

/** A one-line "how much work" summary of a served `work` footprint, for the tooltip that says why
 *  a row has no Delete. The keys are the server's own (`staff_footprint.footprint`), shown as
 *  words rather than translated: it is a detail on hover, and nine more strings on every route
 *  would cost more than it is worth (TD-360). */
export function workSummary(work: Record<string, number> | undefined): string {
  return Object.entries(work ?? {})
    .map(([k, n]) => `${k.replace(/_/g, ' ')}: ${n}`).join(', ')
}
