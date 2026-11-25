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
  test('eleven keys, review first and manage_team last (sprint S1 added scholars)', () => {
    expect(apiKeys).toHaveLength(11)
    expect(apiKeys[0]).toBe('review')
    expect(apiKeys[10]).toBe('manage_team')
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

  // Scholars (maintenance S2) carried Applications' keys until sprint S1; now its own key, `scholars`.
  // S2 / M4a: Payments left for its door (`payments_read`, `payments.view`).
  test('exactly Applications, Scholars and Spending carry perms', () => {
    expect(permRows.map((i) => i.id).sort()).toEqual(['applications', 'scholars', 'spending'])
  })

  /** THE PRESET GUARANTEE ON THE WEB: for every role, a row's `perms` asked of the role's preset (read from the
   *  api; the lead tier for an org admin, every key for a super) gives the answer the row's ROLE LIST gave
   *  before NAVKEYS. NAVKEYS (2026-11-16) took those lists off the rows (a key row keeps only its KIND logins),
   *  so the old answer is typed out here, on purpose. (Payments left for its door in S2 / M4a.) */
  const BEFORE_NAVKEYS: Record<string, readonly string[]> = {
    applications: ['super', 'org_admin', 'admin', 'qc', 'reviewer', 'source_partner'],
    scholars: ['super', 'org_admin', 'admin', 'source_partner', 'mentor'],
    spending: ['super', 'org_admin', 'admin'],
  }
  test('every preset is admitted exactly as its role was', () => {
    for (const row of permRows) {
      for (const role of ROLE_NAMES) {
        const held = presets[role] ?? (role === 'org_admin' ? leadTier : role === 'super' ? apiKeys : [])
        expect({ row: row.id, role, admitted: admitsRow(row, role, held) })
          .toEqual({ row: row.id, role, admitted: BEFORE_NAVKEYS[row.id].includes(role) })
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

  test('sprint S1: Scholars opens by its own key, Applications by its own, whatever the label', () => {
    // reviewer, QC and an Applications-only admin: no Scholars
    expect(canAccess('/admin/scholars', 'reviewer', ['review'])).toBe(false)
    expect(canAccess('/admin/scholars', 'qc', ['see_all', 'qc'])).toBe(false)
    expect(canAccess('/admin/scholars', 'admin', ['see_all'])).toBe(false)
    // Scholars alone: Scholars, not Applications
    expect(canAccess('/admin/scholars', 'admin', ['scholars'])).toBe(true)
    expect(canAccess('/admin/scholarship', 'admin', ['scholars'])).toBe(false)
    // the union shape (S1-e): label reviewer, keys review + see_all + scholars — both rows
    const both = ['review', 'see_all', 'scholars']
    expect(canAccess('/admin/scholars', 'reviewer', both)).toBe(true)
    expect(canAccess('/admin/scholarship', 'reviewer', both)).toBe(true)
    // the presets that hold it, and a source (its own screen) keep the row
    expect(canAccess('/admin/scholars', 'admin', STAFF_PRESETS_FOR('admin'))).toBe(true)
    expect(canAccess('/admin/scholars', 'org_admin', leadTier)).toBe(true)
    expect(canAccess('/admin/scholars', 'super', apiKeys)).toBe(true)
    expect(canAccess('/admin/scholars', 'source_partner', [])).toBe(true)
    // a mentor login never opens Applications
    expect(canAccess('/admin/scholarship', 'mentor', [])).toBe(false)
  })

  test('payments opens by its door, never by the role (S2 / M4a, TD-620); the keys decide, and no payload opens nothing', () => {
    expect(canAccess('/admin/payments', 'org_admin', leadTier)).toBe(false)               // a role string alone
    expect(canAccess('/admin/payments', 'org_admin', leadTier, false, ['payments.view'])).toBe(true)
    expect(canAccess('/admin/payments', 'finance', ['payments_check'], false, [])).toBe(false)
    // NAVKEYS: a partner is served no keys (`resolve` → ()), so it opens no key row; the KEYS decide, not its role.
    expect(canAccess('/admin/spending', 'partner', [])).toBe(false)
    expect(canAccess('/admin/spending', 'reviewer')).toBe(false)
    expect(canAccess('/admin/spending', 'reviewer', null)).toBe(false)
    expect(canAccess('/admin/spending', 'admin', undefined)).toBe(false)   // NAVKEYS: no role fallback
    expect(canAccess('/admin/spending', 'org_admin', leadTier.filter((k) => k !== 'spending'))).toBe(false)
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

