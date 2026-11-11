/**
 * Sprint M2a (owner rulings U1–U5, 2026-11-11): the Team page's addresses, in ONE place.
 *
 * Team lives at `/admin/organisation/team` (U1). Each GROUP has its own person page (U2):
 *   * `/team/admins/<id>` and `/team/reviewers/<id>` — by the person's staff id (`admin_id`);
 *   * `/team/mentors/<id>` — by their MENTOR record id (`mentor_id`), not the sign-in's.
 * Somebody in no group has no page and no link (U5): they are on the Staff tab only.
 *
 * ⚠ The old `/admin/organisation/reviewers/...` and `/admin/organisation/mentors` addresses are PERMANENT
 * redirects in `next.config.js` (pinned by `teamRedirects.test.ts`); nothing in the app links to them.
 */
export type TeamGroup = 'admins' | 'reviewers' | 'mentors'
export type TeamTab = 'staff' | TeamGroup

export const TEAM_PATH = '/admin/organisation/team'

/** The order a person's first page is chosen in (the Staff tab's link, the wrong-group replace). */
export const GROUP_ORDER: readonly TeamGroup[] = ['admins', 'reviewers', 'mentors']

export interface PersonIds {
  admin_id?: number | null
  mentor_id?: number | null
}

/** A Team tab's address. */
export function teamTabHref(tab: TeamTab): string {
  return `${TEAM_PATH}?tab=${tab}`
}

/** `group`'s page for this person, or null when they carry no id for it (a mentor chip with no `mentor_id`). */
export function groupPageHref(group: TeamGroup, ids: PersonIds): string | null {
  const id = group === 'mentors' ? ids.mentor_id : ids.admin_id
  return typeof id === 'number' && id > 0 ? `${TEAM_PATH}/${group}/${id}` : null
}

/** The first group page the person has, in the order Admins, Reviewers, Mentors; null in no group (U5). */
export function firstGroupPage(tables: readonly string[] | null | undefined, ids: PersonIds): string | null {
  for (const g of GROUP_ORDER) {
    if (!(tables ?? []).includes(g)) continue
    const href = groupPageHref(g, ids)
    if (href) return href
  }
  return null
}

/**
 * The wrong-group rule (M2a item 6): a group page opened for somebody NOT in that group (an old
 * `admins/<id>?table=reviewers` link, a reviewer-only person opened at `/team/admins/<id>`) is replaced by
 * the first group page they are in, keeping nothing of the query but `#permissions`; in no group, the
 * Staff tab (U5). Null = they belong here, stay.
 */
export function wrongGroupTarget(here: TeamGroup, person: PersonIds & { tables?: readonly string[] | null },
  hash: string): string | null {
  if ((person.tables ?? []).includes(here)) return null
  const first = firstGroupPage(person.tables, person)
  if (!first) return teamTabHref('staff')
  return hash === '#permissions' ? `${first}#permissions` : first
}

/**
 * The header chips' links (U4): each chip other than the page's own links to that group's page — unless
 * the person carries no id for it, or the VIEWER may not open that page (`may`), when it stays plain text.
 */
export function chipLinks(person: PersonIds & { tables?: readonly string[] | null }, here: TeamGroup,
  may: Readonly<Record<TeamGroup, boolean>>): Partial<Record<TeamGroup, string>> {
  const out: Partial<Record<TeamGroup, string>> = {}
  for (const g of GROUP_ORDER) {
    if (g === here || !may[g] || !(person.tables ?? []).includes(g)) continue
    const href = groupPageHref(g, person)
    if (href) out[g] = href
  }
  return out
}
