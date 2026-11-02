/**
 * Team tables T1 (2026-11-03): THE one question a page guard asks — "may this signed-in person open this
 * route?" — with EVERYTHING `/admin/role/` served (role, permissions, mentoring and the `tables` the
 * server seats them at). A guard that passed only the role could refuse a page the menu offers (a person
 * at the Admins table by an admin key); asking through here keeps the guard and the menu one rule.
 * Visibility only: the endpoint is the fence.
 */
import { canAccess, effectiveRole } from './navigation'

export function mayOpen(
  href: string,
  role: { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null;
          mentoring?: boolean; tables?: readonly string[] | null } | null | undefined,
): boolean {
  return canAccess(href, effectiveRole(role), role?.permissions, role?.mentoring, role?.tables)
}
