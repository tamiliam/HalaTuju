/**
 * TD-253 DRIFT — the cockpit's idea of "answered" is the api's (`interview_completeness.py`). If it
 * drifts, the buttons wake for a case the server refuses, or sleep on one it would accept. The
 * verdict set, blank class and reviewer stage are read out of the api module and compared. The
 * rule's behaviour is `interviewCompleteness.test.ts`.
 */
import { ANSWER_VERDICTS, BLANK, REVIEWER_STAGE } from '@/lib/interviewCompleteness'
import { readApi } from '@/test/apiSource'

const MODULE = 'apps/scholarship/interview_completeness.py'

describe('DRIFT: the api reads blanks and the reviewer stage the same way', () => {
  const src = readApi(MODULE)
  it('the blank character class is the same source, character for character (F6)', () => {
    const m = src.match(/_BLANK = re\.compile\(r'([^']*)'\)/)
    if (!m) throw new Error(`drift test: no _BLANK = re.compile(r'...') in ${MODULE} — follow it.`)
    expect(m[1].length).toBeGreaterThan(20)
    expect(BLANK.source).toBe(m[1])
  })
  it('the reviewer-stage statuses are the same set (F4)', () => {
    const m = src.match(/_REVIEWER_STAGE = \(([^)]*)\)/)
    if (!m) throw new Error(`drift test: no _REVIEWER_STAGE = (...) in ${MODULE} — follow it.`)
    const api = (m[1].match(/'([a-z_]+)'/g) ?? []).map((x) => x.slice(1, -1))
    expect(api.length).toBeGreaterThanOrEqual(3)
    expect([...api].sort()).toEqual([...REVIEWER_STAGE].sort())
  })
})

describe('DRIFT: the api counts the same verdicts as answers', () => {
  const src = readApi(MODULE)
  const m = src.match(/_ANSWER_VERDICTS\s*=\s*frozenset\(\{([^}]*)\}\)/)
  it('the api set is where this test expects it', () => {
    if (!m) {
      throw new Error(`drift test: no _ANSWER_VERDICTS = frozenset({...}) in ${MODULE}. The rule `
        + 'has moved — follow it, never delete the assertion.')
    }
  })
  it('and the two sets are identical', () => {
    const api = new Set(((m?.[1] ?? '').match(/'([a-z_]+)'/g) ?? []).map((s) => s.slice(1, -1)))
    expect(api.size).toBeGreaterThanOrEqual(3)
    expect([...api].sort()).toEqual([...ANSWER_VERDICTS].sort())
  })
})
