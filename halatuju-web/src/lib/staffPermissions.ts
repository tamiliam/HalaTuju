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
import { opensDoor, type DoorName } from './pageDoors'

export type { DoorName }

export const STAFF_PERMISSIONS = [
  'review',
  'see_all',
  'qc',
  'spending',
  'payments_prepare',
  'payments_check',
  'payments_approve',
  'award_withdraw_request',
  'award_withdraw_approve',
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
 *
 * S7d (2026-11-01): a row marked `staffMentors` also admits a STAFF member who mentors now
 * (`mentoring`, the served `/admin/role/` `mentoring`) — My students joins their own menu.
 *
 * Team tables T5c (P4): a row naming a `door` opens exactly when that server door opens — the served
 * `page_keys` hold every key of `DOOR_KEYS[door]` (`pageDoors.opensDoor`). With no `page_keys` (an older
 * payload, or a caller that passes none) the row's `roles` / `adminKeys` answer, exactly as before.
 */
export function admitsRow(
  row: { roles: readonly string[]; perms?: readonly StaffPermission[]; staffMentors?: boolean;
         adminKeys?: readonly StaffPermission[]; door?: DoorName },
  role: string,
  permissions?: readonly string[] | null,
  mentoring?: boolean,
  tables?: readonly string[] | null,
  pageKeys?: readonly string[] | null,
): boolean {
  if (row.staffMentors && mentoring === true) return true
  if (row.door) {
    const opens = opensDoor({ page_keys: pageKeys }, row.door)
    if (opens !== undefined) return opens
  }
  if (row.perms && permissions && (TEAM_ROLES as readonly string[]).includes(role)) {
    return row.perms.some((k) => permissions.includes(k))
  }
  if (row.roles.includes(role)) return true
  // Team tables T1: a person at the ADMINS table opens the row by an admin key they hold — the server's
  // `staff_tables.admits`, which is ALWAYS a union with the row's roles (nobody loses a row).
  if (row.adminKeys && tables?.includes(ADMINS_TABLE) && permissions) {
    const held = adminKeysHeld(permissions)
    return row.adminKeys.some((k) => held.includes(k))
  }
  return false
}

/** Team tables T1: the table names `/admin/role/` serves as `tables` (`staff_tables.TABLES`). */
export const ADMINS_TABLE = 'admins'
export const TABLE_NAMES = ['admins', 'reviewers', 'mentors'] as const

/** The admin keys a person holds, as the server reads them (`staff_tables.admin_keys`): `see_all` held
 *  beside `qc` is `qc`'s own dependency, never an admin hat. drift-test: teamTablesMatrix.test.ts */
export function adminKeysHeld(permissions: readonly string[]): string[] {
  const qc = permissions.includes('qc')
  return permissions.filter((k) => ADMIN_KEYS.includes(k as StaffPermission) && !(qc && k === 'see_all'))
}

/** The keys that seat a team member at the Admins table (`staff_tables.ADMIN_KEYS`). */
export const ADMIN_KEYS: readonly StaffPermission[] =
  ['see_all', 'spending', 'payments_prepare', 'payments_check', 'payments_approve',
    'award_withdraw_request', 'award_withdraw_approve', 'manage_team']

/** Team tables T1: the organisation pages an Admin READS (Organisation, Invitations, People, Sponsors) —
 *  any admin key opens them for a person at the Admins table (T1's `staff_tables.ORG_READ_KEYS`). Since
 *  T5c P4 those rows open by their `door`; this is the OLDER-payload rule (no `page_keys`), frozen as T1
 *  had it (the server's copy went in T5c P1). */
export const ORG_READ_KEYS: readonly StaffPermission[] = ADMIN_KEYS
