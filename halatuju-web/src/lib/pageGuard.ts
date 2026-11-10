/**
 * Team tables T1 (2026-11-03): THE one question a page guard asks — "may this signed-in person open this
 * route?" — with EVERYTHING `/admin/role/` served (role, permissions, mentoring and the `tables` the
 * server seats them at). A guard that passed only the role could refuse a page the menu offers (a person
 * at the Admins table by an admin key); asking through here keeps the guard and the menu one rule.
 * Visibility only: the endpoint is the fence.
 */
import { canAccess, effectiveRole } from './navigation'
import { opensDoor, type DoorName } from './pageDoors'
import { admitsRow } from './staffPermissions'

type Served = { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null;
                mentoring?: boolean; tables?: readonly string[] | null; page_keys?: readonly string[] | null }

/** T5c P4: with the served `page_keys` too, so a row on a server door (`NavItem.door`) reads that door. */
export function mayOpen(href: string, role: Served | null | undefined): boolean {
  return canAccess(href, effectiveRole(role), role?.permissions, role?.mentoring, role?.tables, role?.page_keys)
}

/**
 * Sprint S1: may this person read EVERY scholar's file in their organisation (the server's
 * `scholars_scope` 'all': a super, or the `scholars` key)? The Scholars row's rule WITHOUT its mentor
 * admissions: a mentor (a login, or staff mentoring now) reads only their current students, so a link
 * to any other scholar's file is a dead end (404). A page that lists scholars it does not fence to the
 * viewer's mentees links a name to the file only when this says yes.
 */
export function readsAllScholars(role: Served | null | undefined): boolean {
  const r = effectiveRole(role)
  if (r === 'mentor' || r === 'source_partner') return false
  return canAccess('/admin/scholars', r, role?.permissions, false, role?.tables, role?.page_keys)
}

/**
 * Team tables T5c P4: an IN-PAGE gate on a server door (Announcements, Surveys, Development, the scholar
 * Mentoring / Surveys / Growth tabs, sponsor emails, Sources' invite) — `opensDoor` with the served
 * `page_keys`; an older payload (none) answers by the role list the page held before (`roles`).
 */
export function opensDoorOr(role: Served | null | undefined, door: DoorName, roles: readonly string[]): boolean {
  return opensDoor(role, door) ?? roles.includes(effectiveRole(role))
}

/**
 * Team tables T3 (2026-11-03): who sees Team → **Mentors** and a mentor's detail page — exactly who read the
 * old Mentors page (its registry row's roles): the server's `mentor_invite.may_read`, which is
 * `staff_tables.may_do_admin_work` (the union door `admin_work`, still answered by role label here via
 * `MENTORS_READ_ROLES`; no key yet). The Team
 * page itself is wider (finance and a key-seated admin read it), so the tab carries this rule of its own.
 * Visibility only: `GET admin/mentors/` and `GET admin/mentors/<id>/` are the fence.
 * ⚠ T5c: NOT on a door. The server keeps `mentor_invite.may_read` on the union door `admin_work` (TD-497, a
 * lead ruling is due), so this stays on its roles until that door moves.
 */
export const MENTORS_READ_ROLES = ['super', 'org_admin', 'admin'] as const

export function mayReadMentors(
  role: { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null;
          mentoring?: boolean; tables?: readonly string[] | null } | null | undefined,
): boolean {
  return admitsRow({ roles: MENTORS_READ_ROLES }, effectiveRole(role), role?.permissions, role?.mentoring,
    role?.tables)
}
