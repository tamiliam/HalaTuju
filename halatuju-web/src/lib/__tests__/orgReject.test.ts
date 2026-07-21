/**
 * The org-admin reject gate (owner 2026-07-21).
 *
 * This action is immediate and irreversible — no cool-off, no cancel window — so the card
 * must appear ONLY where the server will accept it. These cases pin the cockpit's offer-set
 * to `AdminOrgRejectView` (super/org_admin) x `services.ORG_REJECT_FROM` ('shortlisted').
 */
import { ORG_REJECT_FROM, canOrgReject } from '@/lib/officerCockpit'

const ALL_STATUSES = [
  'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed',
  'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn',
  'expired',
]

describe('canOrgReject — role', () => {
  it('allows an org_admin', () => {
    expect(canOrgReject({ isSuper: false, role: 'org_admin', status: 'shortlisted' })).toBe(true)
  })

  it('allows a super whatever their role string', () => {
    expect(canOrgReject({ isSuper: true, role: 'super', status: 'shortlisted' })).toBe(true)
    expect(canOrgReject({ isSuper: true, role: null, status: 'shortlisted' })).toBe(true)
  })

  it('refuses a qc and a reviewer — both of whom CAN use the ordinary /reject/ endpoint', () => {
    for (const role of ['qc', 'reviewer', 'admin', 'partner', '', null, undefined]) {
      expect(canOrgReject({ isSuper: false, role, status: 'shortlisted' })).toBe(false)
    }
  })
})

describe('canOrgReject — status', () => {
  it('allows only shortlisted, for every other stage refuses', () => {
    const allowed = ALL_STATUSES.filter(
      (status) => canOrgReject({ isSuper: false, role: 'org_admin', status })
    )
    expect(allowed).toEqual(['shortlisted'])
  })

  it('does not let a super bypass the status gate', () => {
    expect(canOrgReject({ isSuper: true, role: 'super', status: 'interviewed' })).toBe(false)
    expect(canOrgReject({ isSuper: true, role: 'super', status: 'rejected' })).toBe(false)
  })

  it('exposes the same set the API mirrors', () => {
    expect([...ORG_REJECT_FROM]).toEqual(['shortlisted'])
  })
})
