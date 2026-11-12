/**
 * TD-349 DRIFT — the api's refusal is read from `reopen.py`, so a change to WHEN the server refuses
 * turns this file red instead of leaving a button that answers 400. The rule itself, by behaviour,
 * is `decisionReopenOffer.test.ts`.
 */
import { readApi } from '@/test/apiSource'

describe('drift — the api refuses a reopen on exactly these markers', () => {
  const src = readApi('apps/scholarship/reopen.py')
  const body = src.split('\ndef reopen_decision(')[1]?.split('\ndef ')[0] ?? ''

  test('reopen_decision was found', () => {
    expect(body.length).toBeGreaterThan(100)
  })
  test("it raises 'decline_pending' when either marker is set", () => {
    expect(body).toMatch(
      /if app\.decline_due_at or app\.pending_rejection_category:\s*\n\s*raise ReopenError\('decline_pending'\)/)
  })
  test('the refusal comes before the transaction (nothing is written first)', () => {
    expect(body.indexOf("raise ReopenError('decline_pending')"))
      .toBeLessThan(body.indexOf('transaction.atomic()'))
  })
})
