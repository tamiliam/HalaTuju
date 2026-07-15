// Regression for the Administration panel world-split: the org-section staff table
// must never show the platform super admin or referral partners (they surfaced there
// when the shipped panel rendered the raw all-staff list — owner caught it 2026-07-15).
import { isProgrammeStaff, programmeStaff, referralPartners, tenantAdmins } from '../adminStaff'
import type { AdminItem } from '../admin-api'

const row = (over: Partial<AdminItem>): AdminItem => ({
  id: 1, name: 'X', email: 'x@example.com', role: 'reviewer',
  is_super_admin: false, is_active: true, org_name: null, created_at: '2026-07-15',
  ...over,
} as AdminItem)

describe('isProgrammeStaff', () => {
  it.each(['reviewer', 'admin', 'qc', 'org_admin'])('includes programme role %s', (r) => {
    expect(isProgrammeStaff(r)).toBe(true)
  })
  it.each(['super', 'partner', ''])('excludes platform-world role %s', (r) => {
    expect(isProgrammeStaff(r)).toBe(false)
  })
})

describe('programmeStaff', () => {
  it('drops super and partner rows, keeps programme rows', () => {
    const list = [
      row({ id: 1, role: 'reviewer' }),
      row({ id: 2, role: 'qc' }),
      row({ id: 3, role: 'org_admin' }),
      row({ id: 4, role: 'admin' }),
      row({ id: 5, role: 'partner' }),
      row({ id: 6, role: 'super' }),
    ]
    expect(programmeStaff(list).map((a) => a.id)).toEqual([1, 2, 3, 4])
  })

  it('drops a legacy-flag super even if its role string is not "super"', () => {
    const list = [row({ id: 7, role: 'admin', is_super_admin: true })]
    expect(programmeStaff(list)).toEqual([])
  })
})

describe('platform panel lists (per-panel worlds, no all-staff table)', () => {
  const list = [
    row({ id: 1, role: 'reviewer' }),
    row({ id: 2, role: 'partner' }),
    row({ id: 3, role: 'partner' }),
    row({ id: 4, role: 'org_admin' }),
    row({ id: 5, role: 'super' }),
    row({ id: 6, role: 'qc' }),
  ]
  it('referralPartners returns partner rows only', () => {
    expect(referralPartners(list).map((a) => a.id)).toEqual([2, 3])
  })
  it('tenantAdmins returns org_admin rows only (never supers)', () => {
    expect(tenantAdmins(list).map((a) => a.id)).toEqual([4])
    expect(tenantAdmins([row({ id: 8, role: 'org_admin', is_super_admin: true })])).toEqual([])
  })
})
