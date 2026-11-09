/**
 * A2.8a (TD-378): the API's verify_checklist now carries `verified_ic` (a digest string) and `relock`
 * (a QC's re-lock record) beside the verifier's boolean ticks. ts-jest type-checks this file, so the
 * served shape below compiles only while the admin type admits it.
 */
import type { AdminScholarshipDetail, VerifyChecklist } from '@/lib/admin-api/applications'

describe('verify_checklist type', () => {
  it('admits the ticks, the identity digest and a re-lock record', () => {
    const served: AdminScholarshipDetail['verify_checklist'] = {
      nric: true,
      name: false,
      verified_ic: 'a3f1digest',
      relock: { by: 'qc@example.org', at: '2026-11-09T10:00:00+08:00', checklist: { nric: true } },
    }
    const ticks: VerifyChecklist = {}
    expect(served.relock?.checklist).toEqual({ nric: true })
    expect(typeof served.verified_ic).toBe('string')
    expect(ticks).toEqual({})
  })
})
