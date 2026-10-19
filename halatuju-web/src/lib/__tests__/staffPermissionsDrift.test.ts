/**
 * THE DRIFT TEST for `STAFF_PERMISSIONS` in `staffPermissions.ts` — named by its `drift-test:` marker.
 * Request #39 Sprint 1.
 *
 * Read from the api's own source in BOTH directions (lessons.md, 2026-09-19: the reverse sweep is
 * derived from the api side): every key the server's `CATALOGUE` has is here, every key here is in
 * the server's, in the same order. Also pinned from the server: every preset and the lead tier name
 * only catalogue keys, so a key renamed on one side cannot leave a preset pointing at nothing.
 */
import { STAFF_PERMISSIONS, hasPerm } from '@/lib/staffPermissions'
import { pySeq, readApi } from '@/test/apiSource'

const SRC = readApi('apps/courses/staff_permissions.py')
const apiKeys = pySeq(SRC, 'CATALOGUE')
const leadTier = pySeq(SRC, 'LEAD_TIER')

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
