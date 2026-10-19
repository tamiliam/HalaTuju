/**
 * Staff permissions (request #39) — the catalogue keys and the one question the console asks.
 *
 * ⚠ THE SERVER DECIDES WHO HOLDS WHAT. `GET /admin/role/` serves `permissions` already RESOLVED
 * (the preset of the person's role, a saved custom set, the organisation admin's fixed tier, every
 * key for a super, none for a referral partner). This file deliberately holds no copy of the presets
 * or of any rule about them; `hasPerm` only reads the served list. And it is visibility, never the
 * fence: every endpoint re-checks on the server.
 *
 * The KEYS are the server's vocabulary (`STAFF_PERMISSIONS` below is the same list as
 * `halatuju_api/apps/courses/staff_permissions.py` `CATALOGUE`), and a test holds them in step in
 * both directions — a key the screen names that the server lacks would never be held, and a key the
 * server adds that the screen lacks could never be shown.
 * drift-test: halatuju-web/src/lib/__tests__/staffPermissionsDrift.test.ts
 *
 * Sprint 1 serves and types them. Sprint 3: the Applications, Payments and Spending menu rows and
 * page guards (`admitsRow`, read by `navigation.ts`), and the cockpit's QC / write switches, read them.
 */

export const STAFF_PERMISSIONS = [
  'review',
  'see_all',
  'qc',
  'spending',
  'payments_prepare',
  'payments_check',
  'payments_approve',
  'manage_team',
] as const

export type StaffPermission = (typeof STAFF_PERMISSIONS)[number]

/** Whether the signed-in person holds `key`, read from what `/admin/role/` served. A payload from
 *  before request #39 (no `permissions`) holds nothing here; the server still answers for itself. */
export function hasPerm(
  role: { permissions?: readonly string[] | null } | null | undefined,
  key: StaffPermission,
): boolean {
  return !!role?.permissions?.includes(key)
}

/** The roles whose access is a permission SET — the server's `TEAM_ROLES`, held by the drift test.
 *  The organisation admin (a fixed lead tier), a super and a referral partner are not in it. */
export const TEAM_ROLES = ['admin', 'finance', 'qc', 'reviewer'] as const

/**
 * May this person open a registry row (request #39 Sprint 3)? A row naming `perms` admits a TEAM
 * MEMBER who holds any of them; everyone else — and a team member whose payload carries no
 * `permissions` (an old payload, or a caller that passes none) — is answered by the row's `roles`,
 * exactly as before. So a missing field never invents a block, and for every preset the two
 * answers are the same (the rows' `perms` are the keys those roles' presets hold).
 */
export function admitsRow(
  row: { roles: readonly string[]; perms?: readonly StaffPermission[] },
  role: string,
  permissions?: readonly string[] | null,
): boolean {
  if (row.perms && permissions && (TEAM_ROLES as readonly string[]).includes(role)) {
    return row.perms.some((k) => permissions.includes(k))
  }
  return row.roles.includes(role)
}
