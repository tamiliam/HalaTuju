/**
 * Team tables T5c (P4): the page DOORS, read from the v2 keys the server serves.
 *
 * Since T5c P4a `GET admin/role/` serves `page_keys` (`staff_tables.page_keys`: `effective_v2`, never null,
 * `[]` for an inactive row), and every server page door asks `opens_door(admin, '<door>')` with its keys in
 * `staff_tables.DOOR_KEYS`. `DOOR_KEYS` below is a COPY of that table, held equal to it by a drift test, so a
 * menu row or page guard on a door shows exactly when the server's door opens.
 * drift-test: halatuju-web/src/lib/__tests__/teamTablesT5cDoors.test.ts
 *
 * ⚠ AN OLDER PAYLOAD (no `page_keys`) answers `undefined`: the caller keeps the role rule it had before
 * (`opensDoor(role, door) ?? <old rule>`), exactly as `tables` arrived in T1. Visibility only: the endpoint
 * is the fence. A leaf: imports nothing.
 */

/** door -> the v2 keys it asks (every one held). Same as `staff_tables.DOOR_KEYS`, in the same order. */
export const DOOR_KEYS = {
  org_read: ['invitations.view', 'team.view', 'sponsors.view'],
  admin_work: ['team.view', 'sources.view', 'sources.edit', 'sponsors.view', 'sponsors.edit',
    'announcements.view', 'announcements.edit', 'surveys.view', 'surveys.edit',
    'development.view', 'development.edit', 'mentoring.view', 'mentoring.edit'],
  sponsors_read: ['sponsors.view'],
  team_read: ['invitations.view', 'team.view'],
  announcements: ['announcements.edit'],
  surveys: ['surveys.edit'],
  development: ['development.edit'],
  mentoring: ['mentoring.edit'],
  invitations: ['invitations.edit'],
  sponsor_terms: ['sponsors.edit'],
  sponsor_emails: ['sponsors.edit'],
  sources: ['sources.edit'],
  credits_read: ['sponsors.view'],
} as const satisfies Record<string, readonly string[]>

export type DoorName = keyof typeof DOOR_KEYS

/**
 * Does the signed-in person open `door` — hold EVERY key it asks, in the served `page_keys`? `undefined`
 * when the payload carries no `page_keys` (an older server): the caller then answers by its role rule.
 */
export function opensDoor(
  role: { page_keys?: readonly string[] | null } | null | undefined,
  door: DoorName,
): boolean | undefined {
  const held = role?.page_keys
  if (!Array.isArray(held)) return undefined
  return DOOR_KEYS[door].every((k) => held.includes(k))
}
