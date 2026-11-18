/**
 * @jest-environment jsdom
 *
 * LL2b: "Facts in doubt" — the QC's second look, inside the QC panel. The SERVER decides which facts
 * are in doubt (`second_look.in_doubt`); the panel lists them, remembers the QC's "Disagree" taps,
 * and sends only those taps as `fact_checks` on the decision (`{}` = agrees with the reviewer on
 * every one). With no fact in doubt — or old data with no `second_look` key — no block shows and
 * the request carries no `fact_checks` key at all, exactly as before. Made-up names only.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import type { SecondLook } from '@/lib/admin-api'
import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const K = 'admin.scholarship.qcDecision.secondLook'
const loaded = () => screen.findByText('Test Student 07')
const block = () => screen.queryByTestId('facts-in-doubt')

const TWO: SecondLook = {
  in_doubt: [
    // The AI was sure (green), the reviewer failed it and gave no reason: "Not given".
    { fact: 'identity', ai_status: 'verified', ai_green: true, reviewer: 'fail', reason: null,
      groups: ['ai_green_reviewer_fail'] },
    // The AI was in doubt, the reviewer failed it and still chose Recommend: no Reason row.
    { fact: 'income', ai_status: 'review', ai_green: false, reviewer: 'fail', reason: null,
      groups: ['failed_but_accepted'] },
  ],
  answers: null,
}

const asQc = (second_look?: SecondLook) => renderCockpit({
  role: 'qc', stage: 'awaiting_qc',
  build: { outcome: 'recommend', qc_refusal: null, ...(second_look ? { second_look } : {}) },
})

const disagree = (fact: string) => within(screen.getByTestId(`doubt-${fact}`)).getByRole('button')
const accept = () => fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' }))
const sent = (api: ReturnType<typeof asQc>['api']) => api.recordQcDecision.mock.calls[0][1]

describe('LL2b: the block on the QC panel', () => {
  it('lists each fact in doubt with the AI, the reviewer and the reason', async () => {
    asQc(TWO)
    await loaded()
    expect(within(block()!).getByText(`${K}.title`)).toBeTruthy()
    expect(within(block()!).getByText(`${K}.help`)).toBeTruthy()
    const identity = screen.getByTestId('doubt-identity')
    expect(within(identity).getByText('admin.scholarship.verdict.fact.identity')).toBeTruthy()
    expect(within(identity).getByText(`${K}.aiSaid`)).toBeTruthy()
    expect(within(identity).getByText('admin.scholarship.verdict.status.verified')).toBeTruthy()
    expect(within(identity).getByText(`${K}.reviewerSaid`)).toBeTruthy()
    expect(within(identity).getByText('admin.scholarship.recordVerdict.factFail')).toBeTruthy()
    expect(within(identity).getByText('admin.scholarship.recordVerdict.failReasonLabel')).toBeTruthy()
    expect(within(identity).getByText('admin.programmeOverview.aiPrediction.notGiven')).toBeTruthy()
    expect(within(identity).queryByText(new RegExp(`${K}.butDecision`))).toBeNull()
  })

  it('a reason given shows the LL2 label; a failed-but-recommended fact says so and has no Reason row', async () => {
    asQc({ ...TWO, in_doubt: [{ ...TWO.in_doubt[0], reason: 'read_wrong' }, TWO.in_doubt[1]] })
    await loaded()
    expect(within(screen.getByTestId('doubt-identity'))
      .getByText('admin.scholarship.recordVerdict.failReason.read_wrong')).toBeTruthy()
    const income = screen.getByTestId('doubt-income')
    expect(within(income).getByText(new RegExp(`${K}.butDecision`))).toBeTruthy()
    expect(within(income).queryByText('admin.scholarship.recordVerdict.failReasonLabel')).toBeNull()
    expect(within(income).getByText('admin.scholarship.verdict.status.review')).toBeTruthy()
  })

  it('a tap presses Disagree, hides the quiet line; a second tap undoes it', async () => {
    asQc(TWO)
    await loaded()
    const identity = screen.getByTestId('doubt-identity')
    expect(disagree('identity').getAttribute('aria-pressed')).toBe('false')
    expect(disagree('identity').textContent).toBe(`${K}.disagree`)
    expect(within(identity).getByText(`${K}.agree`)).toBeTruthy()
    fireEvent.click(disagree('identity'))
    expect(disagree('identity').getAttribute('aria-pressed')).toBe('true')
    expect(disagree('identity').textContent).toBe(`${K}.undo`)
    expect(within(identity).queryByText(`${K}.agree`)).toBeNull()
    expect(disagree('income').getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(disagree('identity'))
    expect(disagree('identity').getAttribute('aria-pressed')).toBe('false')
    expect(within(identity).getByText(`${K}.agree`)).toBeTruthy()
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
    renderCockpit({ role: 'qc', stage: 'awaiting_qc',
      build: { outcome: 'recommend', qc_refusal: 'self_review_qc_forbidden', second_look: TWO } })
    await loaded()
    expect(block()).toBeNull()
  })
})

describe('LL2b: what the decision sends', () => {
  it('Accept with no taps sends fact_checks {} (agrees with the reviewer on every fact)', async () => {
    const { api } = asQc(TWO)
    await loaded()
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api)).toEqual(expect.objectContaining({ decision: 'accept', fact_checks: {} }))
  })

  it('Accept after a tap sends only the tapped fact, as "disagreed"', async () => {
    const { api } = asQc(TWO)
    await loaded()
    fireEvent.click(disagree('income'))
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api).fact_checks).toEqual({ income: 'disagreed' })
  })

  it('a tap then undo sends nothing for that fact', async () => {
    const { api } = asQc(TWO)
    await loaded()
    fireEvent.click(disagree('identity'))
    fireEvent.click(disagree('identity'))
    accept()
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api).fact_checks).toEqual({})
  })

  it('Reopen carries the taps too', async () => {
    const { api } = asQc(TWO)
    await loaded()
    fireEvent.click(disagree('identity'))
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopen' }))
    expect(disagree('identity').getAttribute('aria-pressed')).toBe('true')   // still shown, still held
    fireEvent.change(screen.getByPlaceholderText('admin.scholarship.qcDecision.commentsPlaceholder'),
      { target: { value: 'The income letter is for the wrong year.' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopenConfirm' }))
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api)).toEqual(expect.objectContaining({ decision: 'reopen', fact_checks: { identity: 'disagreed' } }))
  })

  it('Reject carries the taps too', async () => {
    const { api } = asQc(TWO)
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopen' }))
    fireEvent.click(disagree('income'))
    fireEvent.click(screen.getByRole('switch'))
    fireEvent.change(screen.getByPlaceholderText('admin.scholarship.qcDecision.rejectPlaceholder'),
      { target: { value: 'Not eligible for this programme.' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.rejectConfirm' }))
    await waitFor(() => expect(api.recordQcDecision).toHaveBeenCalled())
    expect(sent(api)).toEqual(expect.objectContaining({ decision: 'reject', fact_checks: { income: 'disagreed' } }))
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
