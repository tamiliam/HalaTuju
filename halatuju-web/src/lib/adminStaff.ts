// World-split for the Administration panel staff tables (approved Stitch v2):
// PROGRAMME roles belong in an organisation's own staff table; `super` (platform
// owner) and `partner` (referral-organisation rep — an attribution concept, not
// programme staff) are PLATFORM-world rows and must never appear in the org table.
import type { AdminItem } from './admin-api'

export const PROGRAMME_STAFF_ROLES = ['reviewer', 'admin', 'qc', 'org_admin', 'finance'] as const

export function isProgrammeStaff(role: string): boolean {
  return (PROGRAMME_STAFF_ROLES as readonly string[]).includes(role)
}

export function programmeStaff(admins: AdminItem[]): AdminItem[] {
  return admins.filter((a) => isProgrammeStaff(a.role) && !a.is_super_admin)
}

// Platform-world lists: each platform icon card shows ITS OWN entries when opened
// (owner's model, 2026-07-15) — no general all-staff table at platform level.
export function referralPartners(admins: AdminItem[]): AdminItem[] {
  return admins.filter((a) => a.role === 'partner')
}

export function tenantAdmins(admins: AdminItem[]): AdminItem[] {
  return admins.filter((a) => a.role === 'org_admin' && !a.is_super_admin)
}

// ── the owner's two categories (2026-08-03) ──────────────────────────────────
// "There are two categories of people here: reviewers and admins. QC is a reviewer as well. And
// finance is also an admin. But their roles and permissions may differ." So the page groups by
// WHAT SOMEONE IS, and the differing permissions stay where they already live — this map is
// presentation, never a permission rule, and there is deliberately no server mirror of it.
export type StaffCategory = 'reviewers' | 'admins'

const CATEGORY: Record<string, StaffCategory> = {
  reviewer: 'reviewers',
  qc: 'reviewers',
  admin: 'admins',
  org_admin: 'admins',
  finance: 'admins',
}

/** Which of the two groups a role belongs to. Null only for a role outside the staff table. */
export function categoryOf(role: string): StaffCategory | null {
  return CATEGORY[role] ?? null
}

/** The staff rows, split into the owner's two categories, each keeping the incoming order. */
export function byCategory(admins: AdminItem[]): Record<StaffCategory, AdminItem[]> {
  const out: Record<StaffCategory, AdminItem[]> = { reviewers: [], admins: [] }
  for (const a of programmeStaff(admins)) {
    const c = categoryOf(a.role)
    if (c) out[c].push(a)
  }
  return out
}
