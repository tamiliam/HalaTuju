/**
 * NAVKEYS (2026-11-16) — THE ADMIN MENU FOLLOWS THE SERVED KEYS, AND NO STANDARD PRESET'S MENU MOVED.
 *
 * Owner 2026-11-15: "there is admin, and there are permissions, which determine what the admin views and edits."
 * Since TD-623 every `GET admin/role/` serves `page_keys`, so a menu row with a server door is answered by that
 * door alone (no role fallback), and a row the server gates by a key asks that key. Only two kinds of row are
 * still answered by who the login IS (`NavItem.roles`): a KIND split (a partner, source or mentor login sees a
 * different console) and a PLATFORM row (super only). See `docs/decisions.md` NAVKEYS.
 *
 * THE PIN: `fixtures/navkeysMenusBefore.json` was written by this file on main 31e738a14, BEFORE any NAVKEYS
 * change, with `env NAVKEYS_WRITE=1 npx jest navkeysPresetPin`. For each standard preset as the server serves it
 * (`servedViewer`: role, permissions, page_keys; `mentoring` and `tables` from the T5c payloads), it holds the
 * three menus, the landing and every registered route's guard (`mayOpen`). The test below proves the code
 * answers the same today. A row that moves for a standard preset is a declared move — there are none.
 */
import * as fs from 'fs'
import * as path from 'path'

import { NAV_ITEMS, NO_PROBES, defaultRoute, effectiveRole, visibleNav, type ProbeState } from '@/lib/navigation'
import { mayOpen } from '@/lib/pageGuard'
import { servedViewer } from '@/test/staffPresets'
import SERVED from './fixtures/t5cServedPayloads.json'

const BEFORE = path.join(__dirname, 'fixtures', 'navkeysMenusBefore.json')
const WRITE = !!process.env.NAVKEYS_WRITE

interface Payload {
  role: string
  is_super_admin?: boolean
  permissions?: string[]
  mentoring?: boolean
  tables?: string[]
  page_keys?: string[]
}
const T5C = SERVED as Record<string, Payload>

/** A standard preset as the server serves it; a `<role>_mentor` shape is that preset mentoring now. */
function preset(name: string): Payload {
  if (name === 'member') return { role: 'member', permissions: [], page_keys: [], mentoring: false, tables: [] }
  const role = name.replace(/_mentor$/, '')
  const shape = T5C[name]
  return { ...servedViewer(role), mentoring: shape?.mentoring ?? false, tables: shape?.tables ?? [] }
}

/** Every STANDARD preset (the brief's list), plus the three that mentor. */
const PRESETS = ['super', 'org_admin', 'admin', 'finance', 'reviewer', 'qc', 'mentor', 'partner', 'source_partner',
  'member', 'org_admin_mentor', 'admin_mentor', 'reviewer_mentor']

const LIVE: Record<'requests' | 'billing', ProbeState> = { requests: 'live', billing: 'live' }

function measure(p: Payload): Record<string, unknown> {
  const role = effectiveRole(p)
  // Built as a variable so the NavContext before and after NAVKEYS (with or without `tables`) accepts it.
  const ctx = { role, probes: LIVE, permissions: p.permissions, mentoring: p.mentoring, tables: p.tables,
    pageKeys: p.page_keys }
  const ids = (groups: ReturnType<typeof visibleNav>) =>
    groups.flatMap((g) => g.items.map((i) => `${i.id}:${i.state}`))
  const cells: Record<string, unknown> = {
    menu: ids(visibleNav(ctx)),
    menuNoGift: ids(visibleNav({ ...ctx, programmeChosen: false })),
    menuNothingProbed: ids(visibleNav({ ...ctx, probes: NO_PROBES })),
    landing: defaultRoute(p),
  }
  for (const item of NAV_ITEMS) {
    for (const href of [item.href, ...(item.match ?? [])]) cells[`open ${href}`] = mayOpen(href, p)
  }
  return cells
}

describe('NAVKEYS: every standard preset gets the same menu, routes and landing as before', () => {
  if (WRITE) {
    it('writes the BEFORE pin', () => {
      const out = Object.fromEntries(PRESETS.map((name) => [name, measure(preset(name))]))
      fs.writeFileSync(BEFORE, JSON.stringify(out, null, 1) + '\n')
    })
    return
  }
  const before = JSON.parse(fs.readFileSync(BEFORE, 'utf8')) as Record<string, Record<string, unknown>>

  it('pins every standard preset, and no other', () => {
    expect(Object.keys(before)).toEqual(PRESETS)
  })

  it.each(PRESETS)('%s: identical to before (no declared move)', (name) => {
    expect(measure(preset(name))).toEqual(before[name])
  })
})

/** The menu ids (every probe live, a gift chosen) and the route guard, for a hand-made payload. */
const menu = (p: Payload) => visibleNav({ role: effectiveRole(p), probes: LIVE, permissions: p.permissions,
  mentoring: p.mentoring, pageKeys: p.page_keys }).flatMap((g) => g.items.map((i) => i.id))
const without = (keys: string[] | undefined, drop: string[]) => (keys ?? []).filter((k) => !drop.includes(k))

describe('NAVKEYS: a key granted by hand opens its row; a key unticked shuts it', () => {
  const admin = preset('admin')
  const lead = preset('org_admin')

  it.each([
    ['billing.view', 'billing', '/admin/billing'],
    ['contracts.view', 'contracts', '/admin/contracts'],
    ['programmes.edit', 'programmeConfig', '/admin/programme'],
    ['requests.view', 'requests', '/admin/requests'],
    ['settings.edit', 'orgSettings', '/admin/organisation/settings'],
  ])('an admin granted %s gets %s, and its page opens', (key, id, href) => {
    expect(menu(admin)).not.toContain(id)
    expect(mayOpen(href, admin)).toBe(false)
    const granted = { ...admin, page_keys: [...(admin.page_keys ?? []), key] }
    expect(menu(granted)).toContain(id)
    expect(mayOpen(href, granted)).toBe(true)
  })

  it('an admin with team.view unticked loses Invitations and Team, and nothing else', () => {
    const shut = { ...admin, page_keys: without(admin.page_keys, ['team.view']) }
    expect(menu(admin).filter((id) => !menu(shut).includes(id))).toEqual(['staff', 'reviewers'])
    expect(mayOpen('/admin/organisation/team', shut)).toBe(false)
  })

  it.each([
    [['see_all', 'qc', 'review'], 'applications', '/admin/scholarship'],
    [['scholars'], 'scholars', '/admin/scholars'],
    [['spending'], 'spending', '/admin/spending'],
  ])('an organisation admin with %j unticked loses %s (the key the server asks)', (drop, id, href) => {
    expect(menu(lead)).toContain(id)
    const shut = { ...lead, permissions: without(lead.permissions, drop) }
    expect(menu(lead).filter((row) => !menu(shut).includes(row))).toEqual([id])
    expect(mayOpen(href, shut)).toBe(false)
  })

  it('an organisation admin with billing.view unticked loses Billing', () => {
    const shut = { ...lead, page_keys: without(lead.page_keys, ['billing.view']) }
    expect(menu(lead).filter((id) => !menu(shut).includes(id))).toEqual(['billing'])
    expect(mayOpen('/admin/billing', shut)).toBe(false)
  })

  it('⚠ M4: an organisation admin keeps Payments with no payment key (the lead tier, LEAD_MONEY_UNTIL_M4)', () => {
    expect(lead.permissions?.some((k) => k.startsWith('payments_'))).toBe(false)
    expect(menu(lead)).toContain('payments')
    // …and a team member is answered by the keys alone: an admin without payments_prepare loses it.
    expect(menu({ ...admin, permissions: without(admin.permissions, ['payments_prepare']) })).not.toContain('payments')
  })

  it('no page_keys opens no row with a door; no permissions opens no row on a key; the KIND rows stay', () => {
    for (const name of ['super', 'org_admin', 'admin', 'finance']) {
      const p = preset(name)
      const noDoors = menu({ ...p, page_keys: undefined })
      // A row that ALSO lists the role (Programmes, the landing) stays by its role.
      expect(NAV_ITEMS.filter((i) => i.door && !i.roles?.includes(p.role as never) && noDoors.includes(i.id))
        .map((i) => i.id)).toEqual([])
      const noKeys = menu({ ...p, permissions: undefined })
      expect(['applications', 'scholars', 'spending'].filter((id) => noKeys.includes(id))).toEqual([])
      expect(noKeys).toContain('programmes')
    }
    // A source login reads its own Applications and Scholars by its KIND, with no key at all.
    expect(menu(preset('source_partner'))).toEqual(['programmeOverview', 'applications', 'scholars', 'profile'])
  })
})

describe('NAVKEYS review: the Programmes row is no dead end for a key holder', () => {
  const menu = (p: Payload) => visibleNav({ role: effectiveRole(p), probes: LIVE, permissions: p.permissions,
    mentoring: p.mentoring, pageKeys: p.page_keys }).flatMap((g) => g.items.map((i) => i.id))

  it('a login outside the role list given programmes.edit gets the Programmes row, the only way into a gift', () => {
    // The server lets no `member` hold a key today (`effective_v2` reads TEAM_ROLES), so this is the web half:
    // the row asks the same door the Programme pages ask, and never strands a holder on the Programme door.
    const member = preset('member')
    expect(menu(member)).not.toContain('programmes')
    const given = { ...member, page_keys: ['programmes.view', 'programmes.edit'] }
    expect(menu(given)).toContain('programmes')
    expect(mayOpen('/admin/organisation/programmes', given)).toBe(true)
  })
})
