/**
 * Team tables T1 (2026-11-03): THE one question a page guard asks — "may this signed-in person open this
 * route?" — with EVERYTHING `/admin/role/` served (role, permissions, mentoring and the `tables` the
 * server seats them at). A guard that passed only the role could refuse a page the menu offers (a person
 * at the Admins table by an admin key); asking through here keeps the guard and the menu one rule.
 * Visibility only: the endpoint is the fence.
 */
import { canAccess, effectiveRole } from './navigation'
import { opensDoor, type DoorName } from './pageDoors'

type Served = { role?: string; is_super_admin?: boolean; permissions?: readonly string[] | null;
                mentoring?: boolean; tables?: readonly string[] | null; page_keys?: readonly string[] | null }

/** T5c P4: with the served `page_keys` too, so a row on a server door (`NavItem.door`) reads that door.
 *  NAVKEYS: `tables` is no longer read — a key seats nobody at a row; the door and the keys decide. */
export function mayOpen(href: string, role: Served | null | undefined): boolean {
  return canAccess(href, effectiveRole(role), role?.permissions, role?.mentoring, role?.page_keys)
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
  return canAccess('/admin/scholars', r, role?.permissions, false, role?.page_keys)
}

/**
 * Sprint M3c (list W): an IN-PAGE gate on a server door with NO role fallback — `opensDoor` with the
 * served `page_keys`, and `false` when they are missing. Every `GET admin/role/` serves `page_keys` (T5c
 * P4a), so the role is never read. Visibility only: the endpoint is the fence.
 * TD-623 (2026-11-15): THE one in-page door gate. `opensDoorOr` (a door, or the page's old role list for a
 * payload without `page_keys`) is gone with its role lists; the role is a label, the keys decide.
 */
export function holdsDoor(role: Served | null | undefined, door: DoorName): boolean {
  return opensDoor(role, door) === true
}

/**
 * Team tables T3 (2026-11-03): who sees Team → **Mentors** and a mentor's detail page. Sprint M2b (D11): the
 * server's `mentor_invite.may_read` asks the door `mentors_read` (`mentoring.view`, A1.10a), so this reads
 * the served `page_keys`. TD-623: no role fallback (`MENTORS_READ_ROLES` is gone); a payload without
 * `page_keys` opens nothing. Visibility only: `GET admin/mentors/` and `GET admin/mentors/<id>/` are the fence.
 */
export function mayReadMentors(role: Served | null | undefined): boolean {
  return holdsDoor(role, 'mentors_read')
}
