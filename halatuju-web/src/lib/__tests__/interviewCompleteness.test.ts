/**
 * TD-253 — the cockpit's interview-completeness rule, and THE DRIFT TEST named by the
 * `drift-test:` marker in `src/lib/interviewCompleteness.ts`.
 *
 * The api refuses an unanswered agenda item at submit and at Approve/Decline
 * (`apps/scholarship/interview_completeness.py`). If the cockpit's idea of "answered" drifts from
 * the api's, the buttons either wake for a case the server then refuses (a dead click with an
 * English error), or stay asleep on a case the server would accept (a reviewer stranded with no
 * way to say what is missing). So the verdict set is read out of the api module and compared.
 */
import {
  ANSWER_VERDICTS, BLANK, REVIEWER_STAGE, interviewGateApplies, isAnswered, missingAgendaItems,
} from '@/lib/interviewCompleteness'
import { readApi } from '@/test/apiSource'

const MODULE = 'apps/scholarship/interview_completeness.py'

describe('what counts as an answer (owner, 2026-09-18)', () => {
  it('a pressed verdict, with no words', () => {
    for (const verdict of ['resolved', 'still_unclear', 'new_concern']) {
      expect(isAnswered({ verdict, rationale: '' })).toBe(true)
    }
  })
  it('a short typed answer — "See conclusion" is legitimate', () => {
    expect(isAnswered({ verdict: '', rationale: 'See conclusion' })).toBe(true)
  })
  it('silence is not', () => {
    for (const f of [undefined, null, {}, { verdict: '', rationale: '' }, { verdict: '', rationale: '  ' }]) {
      expect(isAnswered(f)).toBe(false)
    }
  })
})

describe('missingAgendaItems', () => {
  const agenda = ['household_size_one', 'motivation:motivation_grit', 'gap_one']
  it('#32: an empty findings dict owes every item', () => {
    expect(missingAgendaItems(agenda, {})).toEqual(agenda)
    expect(missingAgendaItems(agenda, undefined)).toEqual(agenda)
  })
  it('names only what is left, in agenda order; a deleted item is not owed', () => {
    expect(missingAgendaItems(agenda, {
      household_size_one: { verdict: 'resolved', rationale: '' },
      gap_one: { verdict: 'deleted', rationale: '' },
    })).toEqual(['motivation:motivation_grit'])
  })
  it('a finding for something no longer on the agenda answers nothing', () => {
    expect(missingAgendaItems(['a'], { b: { verdict: 'resolved', rationale: '' } })).toEqual(['a'])
  })
  it('an empty agenda is complete', () => {
    expect(missingAgendaItems([], {})).toEqual([])
  })
})

describe('where the rule binds', () => {
  const at = (status: string, outcome: string | null, decisionReopened = false) =>
    interviewGateApplies({ status, recordedOutcome: outcome, decisionReopened })
  it("binds at the reviewer's stage before a decision, and on a reopened one at any status", () => {
    for (const s of ['shortlisted', 'profile_complete', 'interviewing']) expect(at(s, null)).toBe(true)
    expect(at('recommended', 'accept', true)).toBe(true)
    expect(at('rejected', 'decline', true)).toBe(true)
  })
  it('not over an Approve or a Decline already recorded', () => {
    expect(at('interviewing', 'accept')).toBe(false)
    expect(at('interviewing', 'decline')).toBe(false)
  })
  it('⚠ review F1: a hold or a blank is NOT a recorded decision', () => {
    expect(at('interviewing', 'hold')).toBe(true)
    expect(at('interviewing', '')).toBe(true)
  })
  it("review F4: not at QC's stage or after it, with no decision recorded", () => {
    for (const s of ['interviewed', 'recommended', 'awarded', 'active', 'rejected', 'expired']) {
      expect(at(s, null)).toBe(false)
    }
  })
})

/** Review F6 — the SAME table as `TestWhatCountsAsAnAnswer` in the api's
 *  `test_interview_completeness.py`; both sides must agree on every row. */
describe('invisible characters are silence on both sides', () => {
  const BLANKS = ['\ufeff', '\u200b', '\u200c', '\u200d', '\xa0', '\u3000', '\u2028', '\t\n',
    ' \ufeff\u200b ', '\x1c', '\x85']
  const ANSWERS = ['x', '\ufeffok', ' See conclusion\u200b']
  it('a blank made of them is not an answer', () => {
    for (const t of BLANKS) expect(isAnswered({ verdict: '', rationale: t })).toBe(false)
  })
  it('a visible character beside them is', () => {
    for (const t of ANSWERS) expect(isAnswered({ verdict: '', rationale: t })).toBe(true)
  })
})

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
