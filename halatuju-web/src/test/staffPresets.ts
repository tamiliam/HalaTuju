/**
 * What `GET /admin/role/` serves as `permissions` for a role on its PRESET — read from the api's own
 * `apps/courses/staff_permissions.py`, never copied (request #39 Sprint 3).
 *
 * A test that fakes the signed-in officer must fake the payload the server really sends, and since
 * Sprint 1 that payload carries the RESOLVED permission list. Sprint 3 made the cockpit's QC / write
 * switches and three menu rows read it, so a fake without it would test a payload no server sends.
 * The web holds no copy of the presets on purpose (`lib/staffPermissions.ts`), so the harness reads
 * them where they live, as `staffPermissionsDrift.test.ts` does.
 */
import { pySeq, readApi } from './apiSource'
import SERVED from '../lib/__tests__/fixtures/t5cServedPayloads.json'

const SRC = readApi('apps/courses/staff_permissions.py')
const CATALOGUE = pySeq(SRC, 'CATALOGUE')
const LEAD_TIER = pySeq(SRC, 'LEAD_TIER')

/** `PRESETS = { 'role': (...), ... }`, as role -> keys. Throws if the dict changes shape. */
export const STAFF_PRESETS: Record<string, string[]> = (() => {
  const m = SRC.match(/^PRESETS = \{([\s\S]*?)^\}/m)
  if (!m) throw new Error('staffPresets: PRESETS is no longer a dict literal in staff_permissions.py')
  const out: Record<string, string[]> = {}
  for (const row of m[1].matchAll(/^\s+'([a-z_]+)':\s*\(([^)]*)\)/gm)) {
    out[row[1]] = [...row[2].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
  }
  if (Object.keys(out).length < 4) throw new Error('staffPresets: fewer than four presets read')
  return out
})()

/** The list the server resolves for `role` on its preset, in catalogue order (`resolve`). */
export function servedPermissions(role: string): string[] {
  const held = role === 'super' ? CATALOGUE
    : role === 'org_admin' ? LEAD_TIER
      : STAFF_PRESETS[role] ?? []
  return CATALOGUE.filter((k) => held.includes(k))
}

const V2_SRC = readApi('apps/courses/staff_permissions_v2.py')
/** `CATALOGUE_V2 = { 'page.level': (...), ... }`, its keys in order. Throws if the dict changes shape. */
const CATALOGUE_V2: string[] = (() => {
  const m = V2_SRC.match(/^CATALOGUE_V2 = \{([\s\S]*?)^\}/m)
  if (!m) throw new Error('staffPresets: CATALOGUE_V2 is no longer a dict literal in staff_permissions_v2.py')
  const out = [...m[1].matchAll(/^\s+'([a-z_]+\.[a-z_]+)':/gm)].map((x) => x[1])
  if (out.length < 20) throw new Error('staffPresets: fewer than twenty v2 keys read')
  return out
})()
const HATS = pySeq(V2_SRC, 'HATS')
/** S2 / M4a: `staff_permissions_v2.ORG_ADMIN_KEY`, and the v2 keys an organisation admin is no longer served. */
const ORG_ADMIN_KEY = 'organisation.admin'
const LEAD_MONEY_GONE = ['sponsors.check', 'payments.prepare', 'payments.check', 'payments.approve']

/**
 * M3c (list W): what `GET /admin/role/` serves as `page_keys` for a super or an organisation admin on the
 * full set — every v2 key, plus the hats (`review`, `qc`) their `permissions` hold (`staff_tables.page_keys`).
 *
 * TD-623 (owner 2026-11-15): the web reads ONLY these doors (no role fallback), so a fake officer must carry the
 * keys the server serves its role. For the other roles they are the server's own answers for a person on that
 * preset (`fixtures/t5cServedPayloads.json`, written by `test_team_tables_t5c_doors`): an admin, finance, qc or
 * reviewer gets its live keys; a mentor, partner or source login gets none (`[]`, as the server serves it).
 * An unknown role answers `undefined` (an older payload).
 */
export function servedPageKeys(role: string): string[] | undefined {
  if (role === 'super' || role === 'org_admin') {
    const held = servedPermissions(role)
    // S2 / M4a: both are served `organisation.admin`; an organisation admin is no longer served the four money keys
    // its role used to carry (they are the Payments switches and the super's Check now).
    const keys = role === 'super' ? CATALOGUE_V2 : CATALOGUE_V2.filter((k) => !LEAD_MONEY_GONE.includes(k))
    return [...keys, ...HATS.filter((h) => held.includes(h)), ORG_ADMIN_KEY]
  }
  const shape = (SERVED as Record<string, { role: string; page_keys: string[] } | undefined>)[role]
  return shape && shape.role === role ? [...shape.page_keys] : undefined
}

/** M3c: the signed-in officer as `GET /admin/role/` serves them on their preset (role, permissions, page_keys). */
export function servedViewer(role: string) {
  return { role, is_super_admin: role === 'super', permissions: servedPermissions(role), page_keys: servedPageKeys(role) }
}

/**
 * M3c: a role-only fixture (`{ role, is_super_admin? }`) with what the server serves added — the super's
 * keys when `is_super_admin`, else the role's. Fields the fixture sets itself win.
 */
export function withServedKeys<T extends { role: string; is_super_admin?: boolean }>(viewer: T) {
  const served = servedViewer(viewer.is_super_admin ? 'super' : viewer.role)
  return { permissions: served.permissions, page_keys: served.page_keys, ...viewer }
}

/**
 * TD-623: a role-only fixture with ONLY the served `page_keys` added (the super's when `is_super_admin`, else the
 * role's) — for a test that sets its own `permissions` (or none) and must not have them changed, now that every
 * in-page gate reads the served door. A `page_keys` the fixture sets itself wins.
 */
export function withServedPageKeys<T extends { role?: unknown; is_super_admin?: unknown }>(viewer: T) {
  const role = viewer.is_super_admin ? 'super' : typeof viewer.role === 'string' ? viewer.role : ''
  return { page_keys: servedPageKeys(role), ...viewer }
}
