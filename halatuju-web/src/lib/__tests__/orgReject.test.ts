/**
 * The org-admin reject gate (owner 2026-07-21).
 *
 * This action is immediate and irreversible — no cool-off, no cancel window — so the card
 * must appear ONLY where the server will accept it. These cases pin the cockpit's offer-set
 * to `AdminOrgRejectView` (the `decide` door, `students.approve`) x `services.ORG_REJECT_FROM` ('shortlisted').
 *
 * TD-623 (owner 2026-11-15): the card follows the SERVED keys only. The role is a label, so a payload
 * without the key never offers it, whatever the role says. The keys below are what `GET /admin/role/`
 * serves each preset (`fixtures/t5cServedPayloads.json`, the server's own answers).
 */
import { ORG_REJECT_FROM, canOrgReject } from '@/lib/officerCockpit'
import SERVED from './fixtures/t5cServedPayloads.json'

const ALL_STATUSES = [
  'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed',
  'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn',
  'expired',
]

const keysOf = (shape: string): string[] =>
  (SERVED as unknown as Record<string, { page_keys: string[] }>)[shape].page_keys

describe('canOrgReject — keys', () => {
  it('allows an org_admin on its served keys', () => {
    expect(canOrgReject({ status: 'shortlisted', pageKeys: keysOf('org_admin') })).toBe(true)
  })

  it('allows a super on its served keys', () => {
    expect(canOrgReject({ status: 'shortlisted', pageKeys: keysOf('super') })).toBe(true)
  })

  it('refuses a qc, a reviewer, an admin and a partner — both of the first two CAN use the ordinary /reject/ endpoint', () => {
    for (const shape of ['qc', 'reviewer', 'admin', 'finance', 'partner', 'mentor', 'source_partner']) {
      expect(canOrgReject({ status: 'shortlisted', pageKeys: keysOf(shape) })).toBe(false)
    }
  })

  it('refuses a payload with no keys at all (TD-623: no role fallback)', () => {
    for (const pageKeys of [undefined, null, []]) {
      expect(canOrgReject({ status: 'shortlisted', pageKeys })).toBe(false)
    }
  })
})

describe('canOrgReject — status', () => {
  it('allows only shortlisted, for every other stage refuses', () => {
    const allowed = ALL_STATUSES.filter(
      (status) => canOrgReject({ status, pageKeys: keysOf('org_admin') })
    )
    expect(allowed).toEqual(['shortlisted'])
  })

  it('does not let a super bypass the status gate', () => {
    expect(canOrgReject({ status: 'interviewed', pageKeys: keysOf('super') })).toBe(false)
    expect(canOrgReject({ status: 'rejected', pageKeys: keysOf('super') })).toBe(false)
  })

  it('exposes the same set the API mirrors', () => {
    expect([...ORG_REJECT_FROM]).toEqual(['shortlisted'])
  })
})
