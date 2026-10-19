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
