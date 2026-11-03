/**
 * Team tables T1 (2026-11-03): THE one question a page guard asks — "may this signed-in person open this
 * route?" — with EVERYTHING `/admin/role/` served (role, permissions, mentoring and the `tables` the
 * server seats them at). A guard that passed only the role could refuse a page the menu offers (a person
 * at the Admins table by an admin key); asking through here keeps the guard and the menu one rule.
 * Visibility only: the endpoint is the fence.
 */
import { canAccess, effectiveRole } from './navigation'
import { admitsRow } from './staffPermissions'

export function mayOpen(
  href: string,
  role: { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null;
          mentoring?: boolean; tables?: readonly string[] | null } | null | undefined,
): boolean {
  return canAccess(href, effectiveRole(role), role?.permissions, role?.mentoring, role?.tables)
}

/**
 * Team tables T3 (2026-11-03): who sees Team → **Mentors** and a mentor's detail page — exactly who read the
 * old Mentors page (its registry row's roles): the server's `mentor_invite.may_read`, which is
 * `staff_tables.may_do_admin_work` (roles `ADMIN_WORK_ROLES`, no key: `ADMIN_WORK_KEYS` is empty). The Team
 * page itself is wider (finance and a key-seated admin read it), so the tab carries this rule of its own.
 * Visibility only: `GET admin/mentors/` and `GET admin/mentors/<id>/` are the fence.
 */
export const MENTORS_READ_ROLES = ['super', 'org_admin', 'admin'] as const

export function mayReadMentors(
  role: { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null;
          mentoring?: boolean; tables?: readonly string[] | null } | null | undefined,
): boolean {
  return admitsRow({ roles: MENTORS_READ_ROLES }, effectiveRole(role), role?.permissions, role?.mentoring,
    role?.tables)
}
