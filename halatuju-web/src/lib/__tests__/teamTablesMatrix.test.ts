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
 */
import * as fs from 'fs'
import * as path from 'path'

import {
  NAV_ITEMS, NO_PROBES, canAccess, defaultRoute, effectiveRole, visibleNav, type ProbeState,
} from '@/lib/navigation'
import { defaultChapterSlug, manualPerms, manualRole, visibleChapters } from '@/content/manual'
import { ADMIN_KEYS, ORG_READ_KEYS, adminKeysHeld } from '@/lib/staffPermissions'
import { MENTORS_READ_ROLES, mayReadMentors } from '@/lib/pageGuard'
import { t5cP5Moves } from '@/test/t5cP5Moves'
import { s1Moves, s1Served } from '@/test/s1Moves'

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
  '/admin/organisation/staff', '/admin/invite', '/admin/organisation/reviewers', '/admin/sponsors']
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

/** `canAccess` with the served `tables` (T1's fifth argument; the code before T1 ignored it). */
const open = canAccess as (...args: unknown[]) => boolean

const isPlatform = (id: string) => NAV_ITEMS.find((i) => i.id === id)?.scope === 'platform'

const LIVE: Record<'requests' | 'billing', ProbeState> = { requests: 'live', billing: 'live' }

function measure(p: Payload): Record<string, unknown> {
  const role = effectiveRole(p)
  const ctx = { role, probes: LIVE, permissions: p.permissions, mentoring: p.mentoring, tables: p.tables }
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
      cells[`open ${href}`] = open(href, role, p.permissions, p.mentoring, p.tables)
    }
  }
  return cells
}

describe('Team tables T1: the console access matrix', () => {
  // Sprint S1: measured on the payload the server serves after S1 (`s1Served`; the WRITE path is unchanged in effect
  // for a fixture, which is never rewritten).
  const measured = Object.fromEntries(Object.entries(SHAPES).map(([k, p]) => [k, measure(s1Served(k, p))]))

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
    expect(measured[shape]).toEqual(s1Moves(
      r55GuideMoves(t5cP5Moves(t3Moves(expected), effectiveRole(SHAPES[shape]), isPlatform)), shape))
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
function r55GuideMoves(cells: Record<string, unknown>): Record<string, unknown> {
  const guide = (cells.guide as string[]).map((row) => {
    const [slug, list] = [row.slice(0, row.indexOf(':')), row.slice(row.indexOf(':') + 1)]
    let anchors = list ? list.split(',') : []
    for (const [chapter, after, added] of R55_SECTIONS) {
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

describe('Team tables T3: the Mentors tab keeps the old Mentors page\'s readers', () => {
  const first = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')) as Record<string, Record<string, unknown>>
  const mixed = JSON.parse(fs.readFileSync(MIXED_FIXTURE, 'utf8')) as Record<string, Record<string, unknown>>
  const before = { ...first, ...mixed }
  it.each(Object.keys(SHAPES))('%s: sees the Mentors tab exactly when it opened the old page', (shape) => {
    expect(mayReadMentors(SHAPES[shape])).toBe(before[shape]['open /admin/organisation/mentors'])
  })
})

describe('Team tables T1: the web reads the server rule, not a copy of its own', () => {
  const py = fs.readFileSync(
    path.join(__dirname, '..', '..', '..', '..', 'halatuju_api', 'apps', 'courses', 'staff_tables.py'), 'utf8')
  const tuple = (name: string): string[] => {
    const m = py.match(new RegExp(`^${name} = \(([^)]*)\)`, 'm'))
    if (!m) throw new Error(`${name} not found in staff_tables.py`)
    return [...m[1].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
  }

  // ⚠ T5c P1 removed the server's `ORG_READ_KEYS` / `ADMIN_WORK_KEYS` / `ADMIN_WORK_ROLES` (its doors read v2
  // keys). Since T5c P4 the web's `adminKeys` rows are the OLDER-payload rule (no `page_keys`), frozen as T1
  // had it: `ORG_READ_KEYS` = T1's ADMIN_KEYS (written out since S1 added `scholars`), no admin-work key, Mentors readers super / org_admin / admin. The
  // served-payload rule is `pageDoors.DOOR_KEYS`, held to the server by `teamTablesT5cDoors.test.ts`.
  it('ADMIN_KEYS and the see_all-beside-qc rule match staff_tables.py', () => {
    expect([...ADMIN_KEYS]).toEqual(tuple('ADMIN_KEYS'))
    expect(adminKeysHeld(['see_all', 'qc', 'review'])).toEqual([])
    expect(adminKeysHeld(['review', 'see_all', 'spending'])).toEqual(['see_all', 'spending'])
  })

  it('only the organisation READ rows widen to the Admins table, and no write row does', () => {
    // T1 (frozen): Sources, Mentors, Announcements, Surveys and Development stay on their roles.
    expect([...MENTORS_READ_ROLES]).toEqual(['super', 'org_admin', 'admin'])
    expect(NAV_ITEMS.filter((i) => i.adminKeys).map((i) => [i.id, i.adminKeys]))
      .toEqual(['staff', 'reviewers', 'sponsors'].map((id) => [id, ORG_READ_KEYS]))
    // Sprint S1: `scholars` seats a person at Admins, but the frozen older-payload rule is T1's list exactly.
    expect([...ORG_READ_KEYS]).toEqual(ADMIN_KEYS.filter((k) => k !== 'scholars'))
  })

  it('a row is never NARROWED by tables: absent, empty or foreign tables answer exactly as before', () => {
    for (const p of Object.values(SHAPES)) {
      const role = effectiveRole(p)
      for (const item of NAV_ITEMS) {
        const was = open(item.href, role, p.permissions, p.mentoring)
        if (was) expect(open(item.href, role, p.permissions, p.mentoring, [])).toBe(true)
      }
    }
  })
})
