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
  it.each(['reviewer', 'admin', 'qc', 'org_admin', 'finance'])('includes programme role %s', (r) => {
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
      row({ id: 7, role: 'finance' }),
    ]
    expect(programmeStaff(list).map((a) => a.id)).toEqual([1, 2, 3, 4, 7])
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

// ── the owner's two categories (2026-08-03) ──────────────────────────────────
import { byCategory, categoryOf, PROGRAMME_STAFF_ROLES } from '../adminStaff'

describe('the two categories', () => {
  it('puts QC with the reviewers, because QC is a reviewer too', () => {
    expect(categoryOf('reviewer')).toBe('reviewers')
    expect(categoryOf('qc')).toBe('reviewers')
  })

  it('puts finance with the admins, because finance is an admin too', () => {
    expect(categoryOf('admin')).toBe('admins')
    expect(categoryOf('org_admin')).toBe('admins')
    expect(categoryOf('finance')).toBe('admins')
  })

  it('⚠ gives EVERY staff role a category, so a new role cannot fall out of both sections', () => {
    // Without this, adding a role means it silently appears on no table at all — the person exists,
    // has access, and is invisible to whoever is meant to be managing them.
    for (const role of PROGRAMME_STAFF_ROLES) {
      expect(categoryOf(role)).not.toBeNull()
    }
  })

  it('gives no category to a platform role, which never appears on this page', () => {
    // `partner` is the PLATFORM-level Referral Partner — a different relationship from the
    // organisation-level Source Partner. See docs/decisions.md, 2026-08-03.
    expect(categoryOf('partner')).toBeNull()
    expect(categoryOf('super')).toBeNull()
  })

  it('splits rows into the two groups and drops platform ones', () => {
    const row = (id: number, role: string) => ({
      id, name: `P${id}`, email: `p${id}@e.org`, is_super_admin: false, role,
      is_active: true, org_name: null, created_at: '2026-01-01T00:00:00Z',
    })
    const out = byCategory([
      row(1, 'reviewer'), row(2, 'finance'), row(3, 'qc'), row(4, 'partner'),
    ] as never)
    expect(out.reviewers.map((r) => r.id)).toEqual([1, 3])
    expect(out.admins.map((r) => r.id)).toEqual([2])
  })
})
