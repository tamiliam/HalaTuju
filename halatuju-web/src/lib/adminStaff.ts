// World-split for the Administration panel staff tables (approved Stitch v2):
// PROGRAMME roles belong in an organisation's own staff table; `super` (platform
// owner) and `partner` (referral-organisation rep — an attribution concept, not
// programme staff) are PLATFORM-world rows and must never appear in the org table.
import type { AdminItem } from './admin-api'

export const PROGRAMME_STAFF_ROLES = ['reviewer', 'admin', 'qc', 'org_admin'] as const

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
