/**
 * TD-349 — the Decision card never offers a super a Reopen the api refuses.
 *
 * The rule (`decisionReopenOffer`). The DRIFT half — the api's refusal read from `reopen.py` — is
 * `decisionReopenOfferDrift.test.ts`.
 */
import { decisionReopenOffer, isDeclinePending } from '@/lib/decisionReopenOffer'

const NOT_PENDING = { decline_due_at: null, pending_rejection_category: '' }

describe('isDeclinePending — either marker, as the api reads it', () => {
  test('neither marker → not pending', () => {
    expect(isDeclinePending(NOT_PENDING)).toBe(false)
  })
  test('the due date alone → pending', () => {
    expect(isDeclinePending({ ...NOT_PENDING, decline_due_at: '2026-10-07T09:00:00Z' })).toBe(true)
  })
  test('the category alone → pending', () => {
    expect(isDeclinePending({ ...NOT_PENDING, pending_rejection_category: 'interview' })).toBe(true)
  })
})

describe('decisionReopenOffer', () => {
  const cases: Array<[boolean, boolean, boolean, ReturnType<typeof decisionReopenOffer>]> = [
    // decisionLocked, isSuper, declinePending → offer
    [true, true, false, 'reopen'],
    [true, true, true, 'cancelPendingDecline'],   // the api would refuse the reopen
    [true, false, false, null],                    // reopen is super-only
    [true, false, true, null],                     // (the header banner still offers the cancel)
    [false, true, false, null],                    // nothing recorded / already reopened
    [false, true, true, null],
  ]
  test.each(cases)('locked=%s super=%s pending=%s → %s', (decisionLocked, isSuper, declinePending, want) => {
    expect(decisionReopenOffer({ decisionLocked, isSuper, declinePending })).toBe(want)
  })

  test('a pending decline never yields a Reopen, whoever asks', () => {
    for (const decisionLocked of [true, false]) {
      for (const isSuper of [true, false]) {
        expect(decisionReopenOffer({ decisionLocked, isSuper, declinePending: true })).not.toBe('reopen')
      }
    }
  })
})
