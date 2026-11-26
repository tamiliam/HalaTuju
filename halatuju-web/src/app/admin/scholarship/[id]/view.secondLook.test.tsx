/**
 * @jest-environment jsdom
 *
 * LL2b: "Facts in doubt" — the QC's second look, inside the QC panel. The SERVER decides which facts
 * are in doubt (`second_look.in_doubt`); the panel lists them, shows the AI's band word, and lets the QC
 * answer each fact Pass ("disagreed") or Fail ("agreed"); nothing is chosen at the start, a second tap
 * clears, and an untouched fact is absent from `fact_checks`. With no fact answered, or no fact in
 * doubt, or old data with no `second_look` key, the request carries no `fact_checks` key at all,
 * exactly as before. Made-up names only.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import type { SecondLook } from '@/lib/admin-api'
import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'
import { QcPanel } from './view/QcPanel'
import type { T } from './view/shared'

installCockpitConsoleGuard()

const K = 'admin.scholarship.qcDecision.secondLook'
const loaded = () => screen.findByText('Test Student 07')
const block = () => screen.queryByTestId('facts-in-doubt')

const TWO: SecondLook = {
  in_doubt: [
    // The AI was sure (green), the reviewer failed it and gave no reason.
    { fact: 'identity', ai_status: 'verified', ai_green: true, reviewer: 'fail', reason: null,
      groups: ['ai_green_reviewer_fail'] },
    // The AI was in doubt, the reviewer failed it and still chose Recommend.
    { fact: 'income', ai_status: 'review', ai_green: false, reviewer: 'fail', reason: null,
      groups: ['failed_but_accepted'] },
  ],
  answers: null,
}

const asQc = (second_look?: SecondLook, ai_fact_bands: Record<string, string> = { identity: 'certain', income: 'unsure' }) =>
  renderCockpit({
    role: 'qc', stage: 'awaiting_qc', writes: { can_qc: true },   // S1: the QC panel draws from the served flag
    build: { outcome: 'recommend', qc_refusal: null, ai_fact_bands, ...(second_look ? { second_look } : {}) },
  })

const PASS = 'admin.scholarship.recordVerdict.factPass'
const FAILK = 'admin.scholarship.recordVerdict.factFail'
const APPROVE = 'admin.scholarship.recordVerdict.approve'
const DECLINE = 'admin.scholarship.recordVerdict.decline'
const choice = (fact: string, which: 'Pass' | 'Fail') =>
  within(screen.getByTestId(`doubt-${fact}`)).getByTestId(`doubt-${fact}-fact${which}`)
const pass = (fact: string) => fireEvent.click(choice(fact, 'Pass'))
const fail = (fact: string) => fireEvent.click(choice(fact, 'Fail'))
const pressed = (fact: string, which: 'Pass' | 'Fail') => choice(fact, which).getAttribute('aria-pressed')
const accept = () => fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' }))
const sent = (api: ReturnType<typeof asQc>['api']) => api.recordQcDecision.mock.calls[0][1]

describe('LL2b: the block on the QC panel', () => {
  it('lists each fact in doubt: AI said, Reviewer, Decision, Your verdict, in that order', async () => {
    asQc(TWO)
    await loaded()
    expect(within(block()!).getByText(`${K}.title`)).toBeTruthy()
    expect(within(block()!).getByText(`${K}.help`)).toBeTruthy()
    const identity = screen.getByTestId('doubt-identity')
    expect(within(identity).getByText('admin.scholarship.verdict.fact.identity')).toBeTruthy()
    expect(within(identity).getByText('admin.scholarship.verdict.band.certain')).toBeTruthy()
    const labels = Array.from(identity.querySelectorAll('dt')).map((d) => d.textContent)
    expect(labels).toEqual([`${K}.aiSaid`, `${K}.reviewer`, `${K}.decision`, `${K}.yourVerdict`])
    expect(within(identity).queryByText(`${K}.reviewerSaid`)).toBeNull()
    expect(within(identity).queryByText('admin.scholarship.recordVerdict.failReasonLabel')).toBeNull()
    expect(within(identity).queryByText(new RegExp(`${K}.butDecision`))).toBeNull()
    expect(within(identity).queryByText(/but the decision is/)).toBeNull()
  })

  it('the Reviewer row: no reason prints only Fail, no brackets', async () => {
    asQc(TWO)
    await loaded()
    const row = screen.getByTestId('doubt-identity').querySelectorAll('dd')[1]
    expect(row.textContent).toBe(FAILK)
    expect(row.textContent).not.toContain('(')
  })

  it('the Reviewer row: a reason prints Fail (reason)', async () => {
    asQc({ ...TWO, in_doubt: [{ ...TWO.in_doubt[0], reason: 'interview_differs' }, TWO.in_doubt[1]] })
    await loaded()
    const row = screen.getByTestId('doubt-identity').querySelectorAll('dd')[1]
    expect(row.textContent).toBe(`${FAILK} (admin.scholarship.recordVerdict.failReason.interview_differs)`)
  })

  it('the Decision row says Recommend for an accept, on every fact', async () => {
    asQc(TWO)
    await loaded()
    for (const fact of ['identity', 'income']) {
      expect(within(screen.getByTestId(`doubt-${fact}`)).getByText(`${K}.decision`)).toBeTruthy()
      expect(within(screen.getByTestId(`doubt-${fact}`)).getByText(APPROVE)).toBeTruthy()
    }
  })

  it('a declined case still draws the box, and the Decision row says Decline', async () => {
    renderCockpit({
      role: 'qc', stage: 'awaiting_qc', writes: { can_qc: true },
      build: { outcome: 'decline', qc_refusal: null, ai_fact_bands: { identity: 'certain', income: 'unsure' },
        second_look: TWO },
    })
    await loaded()
    expect(block()).toBeTruthy()
    expect(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.confirmDecline' })).toBeTruthy()
    for (const fact of ['identity', 'income']) {
      expect(within(screen.getByTestId(`doubt-${fact}`)).getByText(DECLINE)).toBeTruthy()
      expect(within(screen.getByTestId(`doubt-${fact}`)).queryByText(APPROVE)).toBeNull()
    }
  })

  it('any other overall value: no Decision row', async () => {
    renderCockpit({
      role: 'qc', stage: 'awaiting_qc', writes: { can_qc: true },
      build: { outcome: 'recommend', qc_refusal: null, second_look: TWO,
        officer_verdict: { identity: 'fail', income: 'fail', overall: 'pending' } },
    })
    await loaded()
    expect(block()).toBeTruthy()
    const identity = screen.getByTestId('doubt-identity')
    expect(within(identity).queryByText(`${K}.decision`)).toBeNull()
    expect(within(identity).queryByText(APPROVE)).toBeNull()
    expect(within(identity).queryByText(DECLINE)).toBeNull()
  })

  it('the AI line is the served band word, never the raw status', async () => {
    // status `recommend` with the served band `unsure`: the card says Unsure, so the box must too.
    asQc({ ...TWO, in_doubt: [{ ...TWO.in_doubt[0], ai_status: 'recommend', ai_green: false }, TWO.in_doubt[1]] },
      { identity: 'unsure', income: 'ruleNotMet' })
    await loaded()
    const identity = screen.getByTestId('doubt-identity')
    expect(within(identity).getByText('admin.scholarship.verdict.band.unsure')).toBeTruthy()
    expect(within(identity).queryByText(/verdict\.status\./)).toBeNull()
    expect(within(screen.getByTestId('doubt-income')).getByText('admin.scholarship.verdict.band.ruleNotMet')).toBeTruthy()
  })

  it('a missing band falls back as the card does: unverifiable for a gap, else unsure', async () => {
    asQc({ ...TWO, in_doubt: [{ ...TWO.in_doubt[0], ai_status: 'gap' }, { ...TWO.in_doubt[1], ai_status: 'verified' }] },
      {})
    await loaded()
    expect(within(screen.getByTestId('doubt-identity')).getByText('admin.scholarship.verdict.band.unverifiable')).toBeTruthy()
    expect(within(screen.getByTestId('doubt-income')).getByText('admin.scholarship.verdict.band.unsure')).toBeTruthy()
  })

  it('nothing is selected at the start: two buttons, no old toggle or quiet line', async () => {
    asQc(TWO)
    await loaded()
    const identity = screen.getByTestId('doubt-identity')
    expect(within(identity).getByText(`${K}.yourVerdict`)).toBeTruthy()
    expect(within(identity).getAllByRole('button')).toHaveLength(2)
    expect(choice('identity', 'Pass').textContent).toBe(PASS)
    expect(choice('identity', 'Fail').textContent).toBe(FAILK)
    expect(pressed('identity', 'Pass')).toBe('false')
    expect(pressed('identity', 'Fail')).toBe('false')
    expect(within(identity).queryByText(`${K}.disagree`)).toBeNull()
    expect(within(identity).queryByText(`${K}.agree`)).toBeNull()
  })

  it('a tap selects; the other button moves it; a tap on the selected one clears it', async () => {
    asQc(TWO)
    await loaded()
    pass('identity')
    expect(pressed('identity', 'Pass')).toBe('true')
    expect(pressed('identity', 'Fail')).toBe('false')
    expect(pressed('income', 'Pass')).toBe('false')
    fail('identity')
    expect(pressed('identity', 'Pass')).toBe('false')
    expect(pressed('identity', 'Fail')).toBe('true')
    fail('identity')
    expect(pressed('identity', 'Pass')).toBe('false')
    expect(pressed('identity', 'Fail')).toBe('false')
  })

  it('no fact in doubt, or old data with no key: no block', async () => {
    asQc({ in_doubt: [], answers: null })
    await loaded()
    expect(block()).toBeNull()
  })

  it('never on the reviewer cockpit, and never for a QC the server refuses', async () => {
    const { unmount } = renderCockpit({ role: 'reviewer', stage: 'awaiting_qc',
      build: { outcome: 'recommend', second_look: TWO } })
    await loaded()
    expect(block()).toBeNull()
    unmount()
    renderCockpit({ role: 'qc', stage: 'awaiting_qc', writes: { can_qc: true },
      build: { outcome: 'recommend', qc_refusal: 'self_review_qc_forbidden', second_look: TWO } })
    await loaded()
    expect(block()).toBeNull()
  })
})

describe('LL2b: what the decision sends', () => {
  it('Accept with nothing answered sends no fact_checks key at all', async () => {
    const { api } = asQc(TWO)
    await loaded()
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect('fact_checks' in sent(api)).toBe(false)
  })

  it('Pass is sent as "disagreed" and an untouched fact is absent', async () => {
    const { api } = asQc(TWO)
    await loaded()
    pass('income')
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api).fact_checks).toEqual({ income: 'disagreed' })
  })

  it('Fail is sent as "agreed"', async () => {
    const { api } = asQc(TWO)
    await loaded()
    fail('identity')
    pass('income')
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api).fact_checks).toEqual({ identity: 'agreed', income: 'disagreed' })
  })

  it('an answer then a second tap clears it: no answer at all, no key', async () => {
    const { api } = asQc(TWO)
    await loaded()
    pass('identity')
    pass('identity')
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect('fact_checks' in sent(api)).toBe(false)
  })

  it('Reopen carries the answers too', async () => {
    const { api } = asQc(TWO)
    await loaded()
    pass('identity')
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopen' }))
    expect(pressed('identity', 'Pass')).toBe('true')   // still shown, still held
    fireEvent.change(screen.getByPlaceholderText('admin.scholarship.qcDecision.commentsPlaceholder'),
      { target: { value: 'The income letter is for the wrong year.' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopenConfirm' }))
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api)).toEqual(expect.objectContaining({ decision: 'reopen',
      fact_checks: { identity: 'disagreed' } }))
  })

  it('Reject carries the answers too', async () => {
    const { api } = asQc(TWO)
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopen' }))
    pass('income')
    fireEvent.click(screen.getByRole('switch'))
    fireEvent.change(screen.getByPlaceholderText('admin.scholarship.qcDecision.rejectPlaceholder'),
      { target: { value: 'Not eligible for this programme.' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.rejectConfirm' }))
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api)).toEqual(expect.objectContaining({ decision: 'reject',
      fact_checks: { income: 'disagreed' } }))
  })

  it('taps do not carry from one application to the next', () => {
    const first = buildApplicationDetail('awaiting_qc', { outcome: 'recommend', qc_refusal: null, second_look: TWO })
    const next = { ...first, id: first.id + 1 }   // same verdict time: only the case differs
    const doQcDecision = jest.fn()
    const props = {
      t: ((k: string) => k) as unknown as T, busy: '', canQc: true, doQcDecision,
      qcReopenOpen: false, setQcReopenOpen: jest.fn(), qcComments: '', setQcComments: jest.fn(),
      qcRejectMode: false, setQcRejectMode: jest.fn(), qcOverrideOpen: false, setQcOverrideOpen: jest.fn(),
      qcOverrideReason: '', setQcOverrideReason: jest.fn(),
    }
    const { rerender } = render(<QcPanel app={first} {...props} />)
    pass('identity')
    expect(pressed('identity', 'Pass')).toBe('true')
    rerender(<QcPanel app={next} {...props} />)
    expect(pressed('identity', 'Pass')).toBe('false')
    accept()
    expect(doQcDecision).toHaveBeenCalledWith('accept', undefined, undefined)
  })

  it('no block shown: the request carries no fact_checks key at all', async () => {
    const { api } = asQc()
    await loaded()
    expect(block()).toBeNull()
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect('fact_checks' in sent(api)).toBe(false)
  })

  it('a 400 bad_fact_checks shows the panel\'s normal error, not the server\'s words', async () => {
    const { api } = asQc(TWO)
    await loaded()
    api.recordQcDecision.mockRejectedValue(Object.assign(new Error('bad fact_checks'),
      { status: 400, code: 'bad_fact_checks' }))
    accept()
    expect((await screen.findAllByText('admin.scholarship.qcDecision.error')).length).toBeGreaterThan(0)
    expect(screen.queryByText('bad fact_checks')).toBeNull()
  })
})
