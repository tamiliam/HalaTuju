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
  'scholars',
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
 * May this person open a registry row? NAVKEYS (owner 2026-11-15: "there is admin, and there are permissions,
 * which determine what the admin views and edits"), in this order:
 *
 *  1. S7d: a row marked `staffMentors` admits a staff member who mentors now (`mentoring`, served).
 *  2. A row's `roles` admit WHO THE LOGIN IS — a KIND split or a PLATFORM row (`NavItem.roles`), never a
 *     permission: no row a staff login reaches by a key lists that staff role here.
 *  3. A row naming a `door` opens exactly when that server door opens: the served `page_keys` hold every key
 *     of `DOOR_KEYS[door]` (`pageDoors.opensDoor`). No `page_keys` (an older payload) opens nothing — since
 *     TD-623 every `GET admin/role/` serves them, so the role fallback is gone.
 *  4. A row naming `perms` admits whoever holds any of them (the server's `has_perm`, which a super passes and
 *     the lead tier answers for an organisation admin). No `permissions` opens nothing.
 *
 * Visibility only: every endpoint re-checks on the server.
 */
export function admitsRow(
  row: { roles?: readonly string[]; perms?: readonly StaffPermission[]; staffMentors?: boolean; door?: DoorName },
  role: string,
  permissions?: readonly string[] | null,
  mentoring?: boolean,
  pageKeys?: readonly string[] | null,
): boolean {
  if (row.staffMentors && mentoring === true) return true
  if (row.roles?.includes(role)) return true
  if (row.door) return opensDoor({ page_keys: pageKeys }, row.door) === true
  if (row.perms) return !!permissions && row.perms.some((k) => permissions.includes(k))
  return false
}
