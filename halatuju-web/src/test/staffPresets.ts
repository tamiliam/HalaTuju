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

/**
 * M3c (list W): what `GET /admin/role/` serves as `page_keys` for a super or an organisation admin on the
 * full set — every v2 key, plus the hats (`review`, `qc`) their `permissions` hold (`staff_tables.page_keys`).
 * The web now reads these doors instead of the role. Any other role answers `undefined` (an older payload):
 * none of them holds an organisation admin's key on its preset.
 */
export function servedPageKeys(role: string): string[] | undefined {
  if (role !== 'super' && role !== 'org_admin') return undefined
  const held = servedPermissions(role)
  return [...CATALOGUE_V2, ...HATS.filter((h) => held.includes(h))]
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
