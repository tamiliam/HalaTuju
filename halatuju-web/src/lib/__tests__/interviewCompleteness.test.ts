/**
 * TD-253 — the cockpit's interview-completeness rule, by behaviour. THE DRIFT TEST named by the
 * `drift-test:` marker in `src/lib/interviewCompleteness.ts` is `interviewCompletenessDrift.test.ts`.
 *
 * The api refuses an unanswered agenda item at submit and at Approve/Decline
 * (`apps/scholarship/interview_completeness.py`). If the cockpit's idea of "answered" drifts from
 * the api's, the buttons either wake for a case the server then refuses (a dead click with an
 * English error), or stay asleep on a case the server would accept (a reviewer stranded with no
 * way to say what is missing). The drift file reads the verdict set out of the api module.
 */
import {
  interviewGateApplies, isAnswered, missingAgendaItems,
} from '@/lib/interviewCompleteness'

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
