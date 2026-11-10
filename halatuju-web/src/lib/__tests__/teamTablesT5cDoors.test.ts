/**
 * Team tables T5c P4 — THE WEB READS THE SERVER'S DOORS, AND NO MENU MOVED.
 *
 * Since P4a `GET admin/role/` serves `page_keys` (`staff_tables.page_keys`: the v2 keys the page doors ask).
 * P4 moves the menu rows and page guards of the P1/P2 doors onto `pageDoors.opensDoor`, which reads them
 * through a web copy of `staff_tables.DOOR_KEYS`. This file proves two things:
 *
 *  1. DRIFT: the web's `DOOR_KEYS` is the server's `DOOR_KEYS`, exactly (read from `staff_tables.py`).
 *  2. NOTHING MOVED: for every active shape of `test_team_tables_t5c_doors.py` (the access matrix's shapes +
 *     the T5c extras), the menu (three probe states), every registered route's guard (`mayOpen`), the
 *     landing, the Mentors tab and the converted in-page gates answer exactly what they answered BEFORE P4
 *     — once with the payload as the server serves it today (with `page_keys`), once as an older payload
 *     (without it, which keeps today's role rules).
 *
 * THE PAYLOADS (`fixtures/t5cServedPayloads.json`) are the server's own answers: `GET admin/role/` for each
 * active shape, built by `test_team_tables_t5c_doors.DoorParity.setUpTestData` on branch t5c (P4a ae27058d).
 * Inactive shapes get no payload (sign-in refuses them).
 *
 * HOW THE BEFORE MATRIX WAS MADE: `fixtures/t5cDoorsMenusBefore.json` was written by this file on P4a
 * (ae27058d, before any web change) with `T5C_WRITE_MATRIX=1 npx jest teamTablesT5cDoors`.
 */
import * as fs from 'fs'
import * as path from 'path'

import { NAV_ITEMS, NO_PROBES, defaultRoute, effectiveRole, visibleNav, type ProbeState } from '@/lib/navigation'
import { DOOR_KEYS, opensDoor, type DoorName } from '@/lib/pageDoors'
import { mayOpen, mayReadMentors, opensDoorOr } from '@/lib/pageGuard'
import { pyDictOfSeqs, readApi } from '@/test/apiSource'
import { t5cP5Moves } from '@/test/t5cP5Moves'
import { s1Moves, s1Served } from '@/test/s1Moves'

const PAYLOADS = path.join(__dirname, 'fixtures', 't5cServedPayloads.json')
const BEFORE = path.join(__dirname, 'fixtures', 't5cDoorsMenusBefore.json')
const WRITE = !!process.env.T5C_WRITE_MATRIX

interface Payload {
  role: string
  is_super_admin?: boolean
  permissions: string[]
  mentoring?: boolean
  tables: string[]
  page_keys: string[]
}
const SHAPES = JSON.parse(fs.readFileSync(PAYLOADS, 'utf8')) as Record<string, Payload>

/** The in-page gates of the converted doors: the rule each page held before P4 (its role list). */
const ADMIN_WORK_ROLES = ['super', 'org_admin', 'admin']
const LEAD_ROLES = ['super', 'org_admin']
const PAGE_GATES: Record<string, readonly string[]> = {
  'announcements': ADMIN_WORK_ROLES,      // AnnouncementsAdmin POSTER_ROLES
  'surveys': ADMIN_WORK_ROLES,            // SurveysAdmin / SurveyResults / scholar Surveys tab, MAKER_ROLES
  'development': ADMIN_WORK_ROLES,        // DevelopmentAdmin / ModuleProgressView / scholar Growth tab
  'mentoring': ADMIN_WORK_ROLES,          // scholars list + detail, MENTORING_ROLES
  'sponsor_emails': ADMIN_WORK_ROLES,     // sponsors page CAN_EDIT_EMAILS
  'sources': ADMIN_WORK_ROLES,            // sources page canManage (its row's roles)
  'invitations': LEAD_ROLES,              // sources page canInvite
}

const isPlatform = (id: string) => NAV_ITEMS.find((i) => i.id === id)?.scope === 'platform'

const LIVE: Record<'requests' | 'billing', ProbeState> = { requests: 'live', billing: 'live' }

type Gate = (p: Partial<Payload>, door: string, roles: readonly string[]) => boolean
const legacyGate: Gate = (p, _door, roles) => roles.includes(effectiveRole(p))

function measure(p: Partial<Payload>, gate: Gate): Record<string, unknown> {
  const role = effectiveRole(p)
  // Built as a variable so an older NavContext (no `pageKeys`) still accepts it.
  const ctx = { role, probes: LIVE, permissions: p.permissions, mentoring: p.mentoring, tables: p.tables,
    pageKeys: p.page_keys }
  const ids = (groups: ReturnType<typeof visibleNav>) =>
    groups.flatMap((g) => g.items.map((i) => `${i.id}:${i.state}`))
  const cells: Record<string, unknown> = {
    menu: ids(visibleNav(ctx)),
    menuNoGift: ids(visibleNav({ ...ctx, programmeChosen: false })),
    menuNothingProbed: ids(visibleNav({ ...ctx, probes: NO_PROBES })),
    landing: defaultRoute(p),
    mentorsTab: mayReadMentors(p),
  }
  for (const item of NAV_ITEMS) {
    for (const href of [item.href, ...(item.match ?? [])]) cells[`open ${href}`] = mayOpen(href, p)
  }
  for (const [door, roles] of Object.entries(PAGE_GATES)) cells[`gate ${door}`] = gate(p, door, roles)
  return cells
}

describe('Team tables T5c P4: no menu, route or page gate moved', () => {
  if (WRITE) {
    it('writes the BEFORE matrix', () => {
      const out = Object.fromEntries(Object.entries(SHAPES).map(([k, p]) => [k, measure(p, legacyGate)]))
      fs.writeFileSync(BEFORE, JSON.stringify(out, null, 1) + '\n')
    })
    return
  }
  const before = JSON.parse(fs.readFileSync(BEFORE, 'utf8')) as Record<string, Record<string, unknown>>
  const doorGate: Gate = (p, door, roles) => opensDoorOr(p, door as DoorName, roles)

  it('covers every served shape, and no other', () => {
    expect(Object.keys(before).sort()).toEqual(Object.keys(SHAPES).sort())
    expect(Object.keys(SHAPES)).toHaveLength(27)     // the doors test's 32, less its 5 inactive rows
  })

  // T5c P5's declared move (Programmes is a row and the landing again) — see `test/t5cP5Moves.ts`.
  // Sprint S1's declared move and served payload (the Scholars row asks `scholars`) — see `test/s1Moves.ts`.
  const after = (shape: string) =>
    s1Moves(t5cP5Moves(before[shape], effectiveRole(SHAPES[shape]), isPlatform), shape)
  const served = (shape: string) => s1Served(shape, SHAPES[shape])

  it.each(Object.keys(SHAPES))('%s, served today (with page_keys): identical to before', (shape) => {
    expect(measure(served(shape), doorGate)).toEqual(after(shape))
  })

  it.each(Object.keys(SHAPES))('%s, an older payload (no page_keys): identical to before', (shape) => {
    const { page_keys: _dropped, ...older } = served(shape)
    expect(measure(older, doorGate)).toEqual(after(shape))
  })
})

describe('Team tables T5c P4: the doors are really read', () => {
  const finance = JSON.parse(fs.readFileSync(PAYLOADS, 'utf8')).finance as Payload

  it('a converted row and gate follow page_keys, not the role (proof the matrix above is not vacuous)', () => {
    // Finance on today's payload reads Sponsors and makes no survey. Swap the keys and both follow them.
    const swapped = { ...finance, page_keys: ['surveys.view', 'surveys.edit'] }
    expect(mayOpen('/admin/sponsors', finance)).toBe(true)
    expect(mayOpen('/admin/sponsors', swapped)).toBe(false)
    expect(mayOpen('/admin/programme/surveys', swapped)).toBe(true)
    expect(opensDoorOr(swapped, 'surveys', ADMIN_WORK_ROLES)).toBe(true)
    expect(opensDoorOr({ ...finance, page_keys: [] }, 'sponsors_read', ['finance'])).toBe(false)
  })

  it('opensDoor needs EVERY key of the door, and answers undefined with no page_keys', () => {
    expect(opensDoor({ page_keys: ['team.view'] }, 'team_read')).toBe(false)
    expect(opensDoor({ page_keys: ['team.view', 'invitations.view'] }, 'team_read')).toBe(true)
    expect(opensDoor({}, 'team_read')).toBeUndefined()
    expect(opensDoor(null, 'team_read')).toBeUndefined()
  })

  it('exactly the P1/P2 rows ride a door; everything else keeps its own rule', () => {
    expect(NAV_ITEMS.filter((i) => i.door).map((i) => [i.id, i.door])).toEqual([
      ['staff', 'team_read'], ['reviewers', 'team_read'],
      ['sources', 'sources'], ['sponsors', 'sponsors_read'],
      ['announcements', 'announcements'], ['surveys', 'surveys'], ['development', 'development'],
    ])
  })
})

describe('Team tables T5c P4: the web DOOR_KEYS is the server\'s', () => {
  const server = pyDictOfSeqs(readApi('apps/courses/staff_tables.py'), 'DOOR_KEYS')

  it('every door, every key, in the same order', () => {
    expect(Object.keys(server).length).toBeGreaterThanOrEqual(13)    // parse sanity: a reader that reads nothing
    expect(Object.fromEntries(Object.entries(DOOR_KEYS).map(([d, k]) => [d, [...k]]))).toEqual(server)
  })
})
