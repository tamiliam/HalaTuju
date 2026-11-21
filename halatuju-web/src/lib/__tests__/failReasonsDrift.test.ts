/**
 * THE DRIFT TEST for `FAIL_REASON_CODES` in `failReasons.ts` (F3, I-11): the chips the reviewer taps
 * are the server's fixed list (`apps/scholarship/fail_reasons.py` `CODES`), in the same order, with
 * the same default. A code the server does not know is refused with a 400, so a drift here would
 * make every Fail with that chip unsaveable.
 */
import { DEFAULT_FAIL_REASON, FAIL_REASON_CODES, failedFacts, reasonsToSend, VERDICT_FACTS } from '@/lib/failReasons'
import { pySeq, readApi } from '@/test/apiSource'

const SRC = readApi('apps/scholarship/fail_reasons.py')

describe('fail reasons drift (F3)', () => {
  it('the chips are the server list, in its order', () => {
    expect([...FAIL_REASON_CODES]).toEqual(pySeq(SRC, 'CODES'))
  })

  it('the default is the server default (Other)', () => {
    expect(SRC).toMatch(/^DEFAULT = OTHER$/m)
    expect(SRC).toMatch(/^OTHER = 'other'$/m)
    expect(DEFAULT_FAIL_REASON).toBe('other')
  })

  it('the facts are the server facts', () => {
    expect([...VERDICT_FACTS]).toEqual(pySeq(readApi('apps/scholarship/audit.py'), 'FACTS'))
  })
})

describe('reasonsToSend (F3)', () => {
  const verdict = { identity: 'pass', academic: 'fail', pathway: '', income: 'fail' }
  it('sends one reason for every Fail, Other when none was chosen, none for a Pass', () => {
    expect(failedFacts(verdict)).toEqual(['academic', 'income'])
    expect(reasonsToSend(verdict, { identity: 'document_false', income: 'proof_missing' }))
      .toEqual({ academic: 'other', income: 'proof_missing' })
  })
  it('an unknown chip falls back to Other rather than being refused', () => {
    expect(reasonsToSend(verdict, { academic: 'engine_wrong' })).toEqual({ academic: 'other', income: 'other' })
  })
})
