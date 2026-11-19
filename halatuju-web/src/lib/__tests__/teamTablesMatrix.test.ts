/**
 * Team tables T1 — THE WEB HALF OF THE ACCESS MATRIX: every console route × every live person-shape.
 *
 * The backend half is `halatuju_api/apps/scholarship/tests/test_team_tables_matrix.py`; read its
 * docstring. Here each shape is the `/admin/role/` payload the server sends that person (the RESOLVED
 * `permissions`, `mentoring`, and since T1 `tables`), and the measured cells are what the console
 * decides from it: the menu (every probe live; and with no gift chosen), `canAccess` for every
 * registered route (the page guards), the landing (`defaultRoute`) and the Guide (chapters shown, the
 * sections of each, the chapter opened first).
 *
 * HOW THE BEFORE MATRIX WAS MADE: `fixtures/teamTablesAccessBefore.json` was written by this file on the
 * code BEFORE T1 (origin/main faacf681) with `T1_WRITE_MATRIX=1 npx jest teamTablesMatrix`, and committed
 * in the T1 commit. A moved cell must be a bug or a line in `EXPECTED_CHANGES`.
 *
 * NAVKEYS (2026-11-16): the menu and the route guards read the served `page_keys` ALONE for a row with a door
 * (no role or `tables` fallback), so each shape is measured WITH the keys the server serves it — its payload in
 * `fixtures/t5cServedPayloads.json`, by the same name (`reviewer_incomplete` is the reviewer's). With those keys
 * every cell answers what the older payload answered under the rules it replaced (T5c P4 proved the doors move
 * nothing), so the TD-623 gift-door move that this matrix carried for an older payload is gone.
 */
import * as fs from 'fs'
import * as path from 'path'

import {
  NAV_ITEMS, NO_PROBES, canAccess, defaultRoute, effectiveRole, visibleNav, type ProbeState,
} from '@/lib/navigation'
import { defaultChapterSlug, manualPerms, manualRole, visibleChapters } from '@/content/manual'
import * as pageGuard from '@/lib/pageGuard'
import { mayOpen, mayReadMentors } from '@/lib/pageGuard'
import SERVED from './fixtures/t5cServedPayloads.json'
import { t5cP5Moves } from '@/test/t5cP5Moves'
import { s1Moves, s1Served } from '@/test/s1Moves'
import { m2aMoves } from '@/test/m2aMoves'

const FIXTURE = path.join(__dirname, 'fixtures', 'teamTablesAccessBefore.json')
const MIXED_FIXTURE = path.join(__dirname, 'fixtures', 'teamTablesAccessMixedBefore.json')
const WRITE = !!process.env.T1_WRITE_MATRIX

const ALL = ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check',
  'payments_approve', 'award_withdraw_request', 'award_withdraw_approve', 'manage_team']
// A1.13b: the lead tier gained award_withdraw_approve (the API's LEAD_TIER); no cell moves for it.
const LEAD = ['see_all', 'qc', 'spending', 'award_withdraw_approve', 'manage_team']

interface Payload {
  role: string
  is_super_admin?: boolean
  permissions: string[]
  mentoring?: boolean
  tables: string[]
  reviewer_profile_complete?: boolean
}

/** The live shapes (2026-11-03), as `/admin/role/` serves them. A revoked person gets no payload. */
export const SHAPES: Record<string, Payload> = {
  super: { role: 'super', is_super_admin: true, permissions: ALL, tables: ['admins'] },
  org_admin: { role: 'org_admin', permissions: LEAD, tables: ['admins'] },
  org_admin_mentor: { role: 'org_admin', permissions: LEAD, mentoring: true, tables: ['admins', 'mentors'] },
  admin: { role: 'admin', permissions: ['see_all', 'spending', 'payments_prepare'], tables: ['admins'] },
  admin_see_all_spending: { role: 'admin', permissions: ['see_all', 'spending'], tables: ['admins'] },
  finance: { role: 'finance', permissions: ['payments_approve'], tables: ['admins'] },
  qc: { role: 'qc', permissions: ['see_all', 'qc'], tables: ['reviewers'] },
  reviewer: { role: 'reviewer', permissions: ['review'], tables: ['reviewers'] },
  reviewer_incomplete: { role: 'reviewer', permissions: ['review'], tables: ['reviewers'],
    reviewer_profile_complete: false },
  reviewer_admin_keys: { role: 'reviewer', permissions: ['review', 'see_all', 'spending'],
    tables: ['admins', 'reviewers'] },
  mentor: { role: 'mentor', permissions: [], mentoring: true, tables: ['mentors'] },
  partner: { role: 'partner', permissions: [], tables: [] },
  source_partner: { role: 'source_partner', permissions: [], tables: [] },
  // ── MIXED KEYS (T1 review, 2026-11-03): no live row; they pin the derivation where it could go wrong.
  // Their BEFORE rows are in their OWN fixture (`MIXED_FIXTURE`), measured on the pre-T1 navigation.ts and
  // staffPermissions.ts (faacf681), so the first fixture stays exactly as it was made.
  qc_spending: { role: 'qc', permissions: ['see_all', 'qc', 'spending'], tables: ['admins', 'reviewers'] },
  reviewer_payments_check: { role: 'reviewer', permissions: ['review', 'payments_check'],
    tables: ['admins', 'reviewers'] },
  finance_custom: { role: 'finance', permissions: ['review', 'payments_approve'], tables: ['admins', 'reviewers'] },
  reviewer_mentor: { role: 'reviewer', permissions: ['review'], mentoring: true, tables: ['reviewers', 'mentors'] },
  admin_mentor: { role: 'admin', permissions: ['see_all', 'spending', 'payments_prepare'], mentoring: true,
    tables: ['admins', 'mentors'] },
}

/** THE ONLY CELLS T1 MAY MOVE: {shape: {cell: [before, after]}}. Owner ruling 2026-11-03 (option B): the
 *  reviewer seated at the Admins table by keys gains the organisation READ rows (Organisation,
 *  Invitations, People, Sponsors) — the server's `staff_tables.may_read_org` — and NOTHING that writes.
 *  Her landing and her Guide do not move (she lands by her first hat, reviewer). */
const REVIEWER_MENU = ['programmeOverview:show', 'applications:show', 'scholars:show', 'spending:show',
  'profile:show', 'guide:show', 'faq:show']
const ORG_READ_ROWS = ['staff:show', 'reviewers:show', 'sponsors:show']
const ORG_READ_HREFS = ['/admin/organisation', '/admin/administration', '/admin/organisation/programmes',
  '/admin/organisation/staff', '/admin/invite', '/admin/organisation/reviewers', '/admin/sponsors']   // the fixture's keys; M2a renames Team's (`test/m2aMoves.ts`)
/** The shapes seated at Admins by KEYS, not role: each gains exactly the organisation READ rows (they lead
 *  the menu: the Organisation group comes before Programme) and nothing else. */
const KEY_SEATED = ['reviewer_admin_keys', 'qc_spending', 'reviewer_payments_check']
const MENUS = ['menu', 'menuNoGift', 'menuNothingProbed'] as const
function expectedChanges(before: Record<string, Record<string, unknown>>) {
  const out: Record<string, Record<string, [unknown, unknown]>> = {}
  for (const shape of KEY_SEATED) {
    const was = before[shape]
    out[shape] = {
      ...Object.fromEntries(MENUS.map((m) => [m, [was[m], [...ORG_READ_ROWS, ...(was[m] as string[])]]])),
      ...Object.fromEntries(ORG_READ_HREFS.map((href) => [`open ${href}`, [false, true]])),
    }
  }
  return out
}

/** NAVKEYS: the `page_keys` the server serves this shape (`t5cServedPayloads.json`, by name). */
const T5C = SERVED as Record<string, { page_keys: string[] }>
const servedKeys = (shape: string): string[] => [...T5C[shape === 'reviewer_incomplete' ? 'reviewer' : shape].page_keys]

/** `staff_tables.py`'s own tuple `name` (the server's rule, never a web copy). */
const STAFF_TABLES = fs.readFileSync(
  path.join(__dirname, '..', '..', '..', '..', 'halatuju_api', 'apps', 'courses', 'staff_tables.py'), 'utf8')
const tuple = (name: string): string[] => {
  const m = STAFF_TABLES.match(new RegExp(`^${name} = \(([^)]*)\)`, 'm'))
  if (!m) throw new Error(`${name} not found in staff_tables.py`)
  return [...m[1].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
}
/** The server's `staff_tables.admin_keys`: `see_all` beside `qc` is `qc`'s own dependency, never an admin hat. */
const adminKeysHeld = (permissions: readonly string[]): string[] => {
  const keys = tuple('ADMIN_KEYS')
  return permissions.filter((k) => keys.includes(k) && !(permissions.includes('qc') && k === 'see_all'))
}

const isPlatform = (id: string) => NAV_ITEMS.find((i) => i.id === id)?.scope === 'platform'

const LIVE: Record<'requests' | 'billing', ProbeState> = { requests: 'live', billing: 'live' }

function measure(p: Payload, pageKeys: string[]): Record<string, unknown> {
  const role = effectiveRole(p)
  const ctx = { role, probes: LIVE, permissions: p.permissions, mentoring: p.mentoring, pageKeys }
  const ids = (groups: ReturnType<typeof visibleNav>) =>
    groups.flatMap((g) => g.items.map((i) => `${i.id}:${i.state}`))
  const cells: Record<string, unknown> = {
    menu: ids(visibleNav(ctx)),
    menuNoGift: ids(visibleNav({ ...ctx, programmeChosen: false })),
    menuNothingProbed: ids(visibleNav({ ...ctx, probes: NO_PROBES })),
    landing: defaultRoute(p, p.reviewer_profile_complete),
    guide: visibleChapters(manualRole(p), manualPerms(p)).map((c) =>
      `${c.slug}:${c.sections.map((s) => s.anchor).join(',')}`),
    guideFirst: defaultChapterSlug(manualRole(p)),
  }
  for (const item of NAV_ITEMS) {
    for (const href of [item.href, ...(item.match ?? [])]) {
      cells[`open ${href}`] = canAccess(href, role, p.permissions, p.mentoring, pageKeys)
    }
  }
  return cells
}

describe('Team tables T1: the console access matrix', () => {
  // Sprint S1: measured on the payload the server serves after S1 (`s1Served`; the WRITE path is unchanged in effect
  // for a fixture, which is never rewritten).
  // NAVKEYS: with the keys the server serves the shape (`servedKeys`).
  const measured = Object.fromEntries(Object.entries(SHAPES).map(([k, p]) =>
    [k, measure(s1Served(k, p), servedKeys(k))]))

  if (WRITE) {
    it('writes the BEFORE matrix', () => {
      fs.mkdirSync(path.dirname(FIXTURE), { recursive: true })
      fs.writeFileSync(FIXTURE, JSON.stringify(measured, null, 1) + '\n')
    })
    return
  }

  const first = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')) as Record<string, Record<string, unknown>>
  const mixed = JSON.parse(fs.readFileSync(MIXED_FIXTURE, 'utf8')) as Record<string, Record<string, unknown>>
  const before = { ...first, ...mixed }
  const EXPECTED_CHANGES = expectedChanges(before)

  it('the two fixtures never overlap, and the key-seated shapes are what the rule says', () => {
    expect(Object.keys(first).filter((k) => k in mixed)).toEqual([])
    // `staff_tables`: a TEAM role that is not itself an Admins label, holding an admin key (see_all
    // beside qc does not count) — and Rohini's original row moved exactly this way.
    const seated = Object.entries(SHAPES).filter(([, p]) =>
      ['reviewer', 'qc'].includes(p.role) && adminKeysHeld(p.permissions).length > 0).map(([k]) => k)
    expect(seated.sort()).toEqual([...KEY_SEATED].sort())
    expect(before.reviewer_admin_keys.menu).toEqual(REVIEWER_MENU)
  })

  it('covers every shape the fixture has, and no other', () => {
    expect(Object.keys(measured).sort()).toEqual(Object.keys(before).sort())
  })

  it.each(Object.keys(SHAPES))('%s: identical to before, except the declared changes', (shape) => {
    const expected = { ...before[shape] }
    for (const [cell, [was, now]] of Object.entries(EXPECTED_CHANGES[shape] ?? {})) {
      expect([cell, before[shape][cell]]).toEqual([cell, was])
      expected[cell] = now
    }
    // T5c P5's declared move (Programmes is a row and the landing again) — see `test/t5cP5Moves.ts`.
    // Sprint S1's declared move (the Scholars row asks `scholars`) — see `test/s1Moves.ts`.
    // Sprint M2a's declared move (Team's address is `/team`) — see `test/m2aMoves.ts`.
    // NAVKEYS: measured with the served `page_keys`, so the TD-623 older-payload gift-door move no longer applies.
    expect(measured[shape]).toEqual(m2aMoves(s1Moves(
      r55GuideMoves(t5cP5Moves(t3Moves(expected), effectiveRole(SHAPES[shape]), isPlatform)), shape)))
  })
})

/**
 * Team tables T3 (2026-11-03, owner ruling 6): THE ONLY CELLS T3 MOVES. The Mentors menu row goes (Mentors are
 * Team → Mentors), and `/admin/organisation/mentors` is now a redirect matched to the Team row, so opening it
 * answers what opening Team answers (it only sends the visitor to Team). Who sees the Mentors TAB is
 * `pageGuard.mayReadMentors` — exactly the old row's roles — pinned below. Nothing else moves.
 */
function t3Moves(cells: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...cells }
  for (const m of MENUS) out[m] = (cells[m] as string[]).filter((id) => !id.startsWith('mentors:'))
  out['open /admin/organisation/mentors'] = cells['open /admin/organisation/reviewers']
  for (const m of MENUS) out[m] = programmeSettingsLast(out[m] as string[])
  return out
}

/**
 * Request #55 (2026-11-07): THE ONLY CELLS IT MOVES are three new Guide SECTIONS ("Notes for the reviewer"), each
 * inserted after a named one in a chapter a shape already sees. No chapter, menu row, page or landing moves; a
 * shape that did not see the chapter sees no new section.
 */
const R55_SECTIONS: Array<[chapter: string, after: string, added: string]> = [
  ['role-reviewer', 'reviewer-working-a-case', 'reviewer-notes-from-admin'],
  ['role-qc', 'qc-review-all', 'qc-reviewer-notes'],
  ['role-org-admin', 'org-admin-assigning', 'org-admin-reviewer-notes'],
]
/**
 * A4.4 (TD-502 part, 2026-11-11): two more Guide SECTIONS in the reviewer chapter, on the two scheduling states,
 * inserted in order after "reviewer-scheduling". Same rule as #55: only a shape that already sees the reviewer
 * chapter sees them; no chapter, menu row, page or landing moves.
 */
const A44_SECTIONS: Array<[chapter: string, after: string, added: string]> = [
  ['role-reviewer', 'reviewer-scheduling', 'reviewer-scheduling-proposed'],
  ['role-reviewer', 'reviewer-scheduling-proposed', 'reviewer-scheduling-booked'],
]
/** Request #75 (2026-11-16): one more Guide SECTION in the org admin chapter, "Rejecting before interview", after
 *  "Notes for the reviewer". Same rule as #55. */
const R75_SECTIONS: Array<[chapter: string, after: string, added: string]> = [
  ['role-org-admin', 'org-admin-reviewer-notes', 'org-admin-reject-before-interview'],
]
/**
 * LL2b (2026-11-19): one more Guide SECTION in the QC chapter, "Facts in doubt" (`perm: 'qc'`), inserted after
 * "qc-accept-reopen" (itself `perm: 'qc'`). Same rule as #55: only a shape that already sees the QC power's
 * sections sees it; no chapter, menu row, page or landing moves.
 */
const LL2B_SECTIONS: Array<[chapter: string, after: string, added: string]> = [
  ['role-qc', 'qc-accept-reopen', 'qc-facts-in-doubt'],
]
function r55GuideMoves(cells: Record<string, unknown>): Record<string, unknown> {
  const guide = (cells.guide as string[]).map((row) => {
    const [slug, list] = [row.slice(0, row.indexOf(':')), row.slice(row.indexOf(':') + 1)]
    let anchors = list ? list.split(',') : []
    for (const [chapter, after, added] of [...R55_SECTIONS, ...A44_SECTIONS, ...R75_SECTIONS, ...LL2B_SECTIONS]) {
      const at = anchors.indexOf(after)
      if (slug === chapter && at >= 0) anchors = [...anchors.slice(0, at + 1), added, ...anchors.slice(at + 1)]
    }
    return `${slug}:${anchors.join(',')}`
  })
  return { ...cells, guide }
}

/** Owner 2026-11-03 (small change): the gift's Configuration row became "Programme Settings", the LAST row of the
 *  Programme group (after Contract templates). The same rows, one moved; nobody gains or loses a row. */
function programmeSettingsLast(ids: string[]): string[] {
  const row = ids.find((id) => id.startsWith('programmeConfig'))
  if (!row) return ids
  const rest = ids.filter((id) => id !== row)
  const after = rest.findIndex((id) => id.startsWith('contracts'))
  return after < 0 ? ids : [...rest.slice(0, after + 1), row, ...rest.slice(after + 1)]
}

/**
 * TD-623 (owner 2026-11-15, "permissions determine what the admin views and edits"): THE ONE CELL TD-623 MOVES
 * here. These shapes are OLDER payloads (no `page_keys`); the Mentors tab used to answer them by the role list
 * super / org_admin / admin. That role fallback is gone, so an older payload sees no Mentors tab, whatever its
 * role. Who sees it on the payload the server serves is the `mentors_read` door, pinned shape by shape in
 * `teamTablesT5cDoors.test.ts` (mentorsTab).
 */
describe('Team tables T3 / TD-623: the Mentors tab on an older payload', () => {
  const first = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')) as Record<string, Record<string, unknown>>
  const mixed = JSON.parse(fs.readFileSync(MIXED_FIXTURE, 'utf8')) as Record<string, Record<string, unknown>>
  const before = { ...first, ...mixed }
  it('the old page had readers, so the cell really moves (the fixture is not blank)', () => {
    expect(Object.keys(SHAPES).filter((shape) => before[shape]['open /admin/organisation/mentors']).length)
      .toBeGreaterThan(0)
  })
  it.each(Object.keys(SHAPES))('%s: an older payload sees no Mentors tab (no role fallback)', (shape) => {
    expect(mayReadMentors(SHAPES[shape])).toBe(false)
  })
})

describe('NAVKEYS: no row is opened by a table seat, or by a role, any more', () => {
  // T1 widened Invitations, Team and Sponsors to the Admins table by an admin key (`adminKeys`, the older-payload
  // rule since T5c P4). NAVKEYS removed it with the role fallback: those rows read their door alone.
  it('no row carries adminKeys, and the web keeps no copy of the Admins-table keys', () => {
    expect(NAV_ITEMS.filter((i) => 'adminKeys' in i).map((i) => i.id)).toEqual([])
    expect(tuple('ADMIN_KEYS').length).toBeGreaterThanOrEqual(8)   // parse sanity for the seated-shape rule above
  })

  it('tables are never read: the same answer with any tables, or none', () => {
    for (const [shape, p] of Object.entries(SHAPES)) {
      const served = { ...s1Served(shape, p), page_keys: servedKeys(shape) }
      for (const item of NAV_ITEMS) {
        const was = mayOpen(item.href, served)
        expect([shape, item.id, mayOpen(item.href, { ...served, tables: [] })]).toEqual([shape, item.id, was])
        expect([shape, item.id, mayOpen(item.href, { ...served, tables: ['admins', 'reviewers', 'mentors'] })])
          .toEqual([shape, item.id, was])
      }
    }
  })

  it('a team shape with no page_keys opens no row that has a door (the role fallback is gone)', () => {
    for (const [shape, p] of Object.entries(SHAPES)) {
      // A door row that also lists the role (Programmes, the landing — NAVKEYS review) still admits that role.
      for (const item of NAV_ITEMS.filter((i) => i.door && !i.roles?.includes(effectiveRole(p) as never))) {
        expect([shape, item.id, mayOpen(item.href, s1Served(shape, p))]).toEqual([shape, item.id, false])
      }
    }
    expect('MENTORS_READ_ROLES' in pageGuard).toBe(false)
  })
})
