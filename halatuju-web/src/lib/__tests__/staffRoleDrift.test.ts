/**
 * THE DRIFT TEST for `ROLE_PARTNER` in `staffRole.ts` — named by its `drift-test:` marker.
 *
 * The server's `staff_lifecycle.ROLE_PAIRS` decides which role switches exist (owner, 2026-10-09:
 * Admin ↔ Finance, Reviewer ↔ QC). The People page offers exactly the partner role from this map,
 * so a pair the server added and this map lacks is a switch nobody can reach, and one this map
 * has and the server refused is a button that always fails.
 */
import { ROLE_PARTNER, switchableTo } from '@/lib/staffRole'
import { readApi } from '@/test/apiSource'

const SRC = readApi('apps/scholarship/staff_lifecycle.py')

const backendPairs = (() => {
  const m = SRC.match(/^ROLE_PAIRS = \{([^}]*)\}/m)
  if (!m) throw new Error('drift test: ROLE_PAIRS is no longer a dict literal in staff_lifecycle.py')
  return Object.fromEntries([...m[1].matchAll(/'([a-z_]+)':\s*'([a-z_]+)'/g)].map((x) => [x[1], x[2]]))
})()

describe('ROLE_PARTNER vs staff_lifecycle.ROLE_PAIRS', () => {
  test('the parse found the four pairs (parse sanity)', () => {
    expect(Object.keys(backendPairs).length).toBe(4)
  })

  test('the two maps agree exactly', () => {
    expect({ ...ROLE_PARTNER }).toEqual(backendPairs)
  })

  test('no switch ever reaches or leaves an appointment role', () => {
    for (const role of ['org_admin', 'super', 'partner']) {
      expect(Object.keys(ROLE_PARTNER)).not.toContain(role)
      expect(Object.values(ROLE_PARTNER)).not.toContain(role)
    }
  })

  test('a revoked or super row offers no switch', () => {
    expect(switchableTo({ role: 'admin', is_active: false })).toBeNull()
    expect(switchableTo({ role: 'admin', is_active: true, is_super_admin: true })).toBeNull()
    expect(switchableTo({ role: 'org_admin', is_active: true })).toBeNull()
    expect(switchableTo({ role: 'qc', is_active: true })).toBe('reviewer')
  })
})
