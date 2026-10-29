/**
 * THE DRIFT TEST for `STAFF_PERMISSIONS` in `staffPermissions.ts` — named by its `drift-test:` marker.
 * Request #39 Sprint 1.
 *
 * Read from the api's own source in BOTH directions (lessons.md, 2026-09-19: the reverse sweep is
 * derived from the api side): every key the server's `CATALOGUE` has is here, every key here is in
 * the server's, in the same order. Also pinned from the server: every preset and the lead tier name
 * only catalogue keys, so a key renamed on one side cannot leave a preset pointing at nothing.
 */
import { STAFF_PERMISSIONS, TEAM_ROLES, admitsRow, hasPerm } from '@/lib/staffPermissions'
import { NAV_ITEMS, ROLE_NAMES, canAccess, defaultRoute } from '@/lib/navigation'
import { pySeq, readApi } from '@/test/apiSource'

const SRC = readApi('apps/courses/staff_permissions.py')
const apiKeys = pySeq(SRC, 'CATALOGUE')
const leadTier = pySeq(SRC, 'LEAD_TIER')
const teamRoles = pySeq(SRC, 'TEAM_ROLES')
const STAFF_PRESETS_FOR = (role: string): string[] =>
  presets[role] ?? (role === 'org_admin' ? leadTier : role === 'super' ? apiKeys : [])

/** The `PRESETS = { 'role': (...), ... }` dict, as role -> keys. */
const presets = (() => {
  const m = SRC.match(/^PRESETS = \{([\s\S]*?)^\}/m)
  if (!m) throw new Error('drift test: PRESETS is no longer a dict literal in staff_permissions.py')
  const out: Record<string, string[]> = {}
  for (const row of m[1].matchAll(/^\s+'([a-z_]+)':\s*\(([^)]*)\)/gm)) {
    out[row[1]] = [...row[2].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
  }
  return out
})()

describe('parse sanity — the server catalogue was really found', () => {
  test('eight keys, review first and manage_team last', () => {
    expect(apiKeys).toHaveLength(8)
    expect(apiKeys[0]).toBe('review')
    expect(apiKeys[7]).toBe('manage_team')
  })

  test('four team presets and a lead tier', () => {
    expect(Object.keys(presets).sort()).toEqual(['admin', 'finance', 'qc', 'reviewer'])
    expect(leadTier.length).toBeGreaterThan(2)
  })
})

describe('STAFF_PERMISSIONS vs staff_permissions.CATALOGUE', () => {
  test('every server key is on the web, in the same order', () => {
    expect([...STAFF_PERMISSIONS]).toEqual(apiKeys)
  })

  test('no web key the server does not have', () => {
    expect(STAFF_PERMISSIONS.filter((k) => !apiKeys.includes(k))).toEqual([])
  })

  test('every server preset and the lead tier name only catalogue keys', () => {
    for (const keys of [...Object.values(presets), leadTier]) {
      expect(keys.filter((k) => !(STAFF_PERMISSIONS as readonly string[]).includes(k))).toEqual([])
    }
  })
})

describe('hasPerm reads only what the server served', () => {
  test('a served key is held, an absent one is not', () => {
    const role = { permissions: ['review', 'spending'] }
    expect(hasPerm(role, 'spending')).toBe(true)
    expect(hasPerm(role, 'see_all')).toBe(false)
  })

  test('a payload from before #39, a null list and no role hold nothing', () => {
    expect(hasPerm({}, 'review')).toBe(false)
    expect(hasPerm({ permissions: null }, 'review')).toBe(false)
    expect(hasPerm(null, 'review')).toBe(false)
    expect(hasPerm(undefined, 'review')).toBe(false)
  })
})

describe('TEAM_ROLES vs staff_permissions.TEAM_ROLES (#39 S3)', () => {
  test('the same roles, both directions, and exactly the preset roles', () => {
    expect([...TEAM_ROLES].sort()).toEqual([...teamRoles].sort())
    expect([...TEAM_ROLES].sort()).toEqual(Object.keys(presets).sort())
  })
})

describe('admitsRow — the registry rows that read permissions (#39 S3)', () => {
  const permRows = NAV_ITEMS.filter((i) => i.perms)

  // Scholars (maintenance S2) carries Applications' keys exactly — the same server rule.
  test('exactly Applications, Scholars, Payments and Spending carry perms', () => {
    expect(permRows.map((i) => i.id).sort()).toEqual(['applications', 'payments', 'scholars', 'spending'])
  })

  /** THE PRESET GUARANTEE ON THE WEB: for every team role, a row's `perms` asked of the role's
   *  preset (read from the api) gives the row's `roles` answer. The org admin, super and partner
   *  are answered by `roles` whatever they hold. */
  test('every preset is admitted exactly as its role was', () => {
    for (const row of permRows) {
      for (const role of ROLE_NAMES) {
        const held = presets[role] ?? (role === 'org_admin' ? leadTier : role === 'super' ? apiKeys : [])
        expect({ row: row.id, role, admitted: admitsRow(row, role, held) })
          .toEqual({ row: row.id, role, admitted: row.roles.includes(role) })
      }
    }
  })

  test('a custom set moves a team member, and only by the served keys', () => {
    // Rohini: Reviewer + Spending opens Spending, keeps Applications, gets no Payments.
    const rohini = ['review', 'spending']
    expect(canAccess('/admin/spending', 'reviewer', rohini)).toBe(true)
    expect(canAccess('/admin/scholarship', 'reviewer', rohini)).toBe(true)
    expect(canAccess('/admin/payments', 'reviewer', rohini)).toBe(false)
    // Admin minus Spending; Finance + Review; Finance without Approve.
    expect(canAccess('/admin/spending', 'admin', ['see_all', 'payments_prepare'])).toBe(false)
    expect(canAccess('/admin/scholarship', 'finance', ['payments_approve', 'review'])).toBe(true)
    expect(canAccess('/admin/payments', 'finance', [])).toBe(false)
  })

  test('the lead tier and the platform are answered by role, and no payload means role', () => {
    expect(canAccess('/admin/payments', 'org_admin', leadTier)).toBe(true)   // no payments key: lead tier
    expect(canAccess('/admin/spending', 'partner', apiKeys)).toBe(false)
    expect(canAccess('/admin/spending', 'reviewer')).toBe(false)
    expect(canAccess('/admin/spending', 'reviewer', null)).toBe(false)
    expect(canAccess('/admin/spending', 'admin', undefined)).toBe(true)
  })
})

describe('the landing follows the served permissions, like the menu (#39 S3 review fix 3)', () => {
  const sets: Array<[string, string[]]> = [
    ['reviewer', ['review', 'spending']], ['reviewer', []], ['finance', ['payments_approve', 'review']],
    ['finance', []], ['admin', ['see_all', 'payments_prepare']], ['qc', ['see_all']],
  ]
  test.each(sets)('a %s holding %j lands somewhere that set may open', (role, permissions) => {
    const href = defaultRoute({ role, permissions })
    expect(canAccess(href, role as never, permissions)).toBe(true)
  })

  test('every preset, given the list the server serves it, lands where it always did', () => {
    for (const role of ROLE_NAMES) {
      expect(defaultRoute({ role, permissions: STAFF_PRESETS_FOR(role) })).toBe(defaultRoute({ role }))
    }
  })
})

