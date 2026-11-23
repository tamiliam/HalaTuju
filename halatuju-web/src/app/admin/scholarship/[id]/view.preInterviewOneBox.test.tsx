/**
 * @jest-environment jsdom
 *
 * REJECT BEFORE INTERVIEW USES THE ONE REVIEWER ASSESSMENT BOX (owner phone check, 23 Nov).
 *
 * The reject panel used to draw its own "four facts" Pass/Fail, a second copy of the Reviewer
 * Assessment box higher on the same page: taps in one never reached the other. Now there is ONE box.
 * These pin, on the REAL page:
 *   * only one set of Pass/Fail on the page, and the panel's plain red line follows the box
 *     (any fact unrated -> the line, Reject greyed; all four -> no line, Reject live);
 *   * "Yes, reject" sends exactly the box's state (a Fail with its chosen Why), and NEVER calls
 *     `recordVerdict` (no `verdict_decided_at`: a pre-interview reject stays out of F4 / LL5 scoring);
 *   * an assessment already on the case fills the box, and is what is sent;
 *   * after the reject, and after "Cancel decline", the box is reloaded from the server's reply, so
 *     taps from before never linger.
 * Dummy data only.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const P = 'admin.scholarship.preInterview'
const RV = 'admin.scholarship.recordVerdict'
const FACTS = ['identity', 'academic', 'pathway', 'income'] as const
const OFFER = { hold_hours: 24, reasons: ['not_b40'], note_max: 2000 }
const loaded = () => screen.findByText('Test Student 07')

/** The box's Pass for a fact (the only id the box gives), and the Fail beside it. */
const pass = (f: string) => document.getElementById(`rate-fact-${f}-pass`) as HTMLButtonElement
const fail = (f: string) => pass(f).nextElementSibling as HTMLButtonElement
const rated = (f: string) => /bg-(positive|critical)-fill/.test(pass(f).className + fail(f).className)
const line = () => screen.queryByTestId('pre-interview-facts-needed')
const submit = () => screen.getByRole('button', { name: `${P}.submit` }) as HTMLButtonElement

/** An org admin (holds `qc`, may write) at Awaiting review with no reviewer: the door is served. */
const atAwaitingReview = (build: Record<string, unknown> = {}) =>
  renderCockpit({ role: 'org_admin', writes: { can_write: true }, stage: 'profile_complete',
    build: { pre_interview: OFFER, ...build } as never })

/** The panel is its own lazy chunk: wait for its door before pressing it. */
const openPanel = async () => {
  fireEvent.click(await screen.findByRole('button', { name: `${P}.start` }))
  fireEvent.change(screen.getByLabelText(`${P}.whyLabel`, { exact: false }), { target: { value: 'not_b40' } })
  fireEvent.change(screen.getByLabelText(`${P}.detailsLabel`, { exact: false }), { target: { value: 'Dummy note' } })
}

describe('one box: the reject panel reads the Reviewer Assessment box', () => {
  it('there is only ONE set of Pass/Fail on the page, with the reject panel open', async () => {
    atAwaitingReview()
    await loaded()
    await openPanel()
    expect(screen.getAllByRole('button', { name: `${RV}.factPass` })).toHaveLength(4)
    expect(screen.getAllByRole('button', { name: `${RV}.factFail` })).toHaveLength(4)
    expect(screen.queryByTestId('pre-interview-facts')).toBeNull()
    for (const f of FACTS) expect(pass(f)).toBeTruthy()
  })

  it('tap the four facts in the box: the red line goes and Reject is live; un-rate one: both come back', async () => {
    atAwaitingReview()
    await loaded()
    await openPanel()
    expect(line()?.textContent).toBe(`${P}.factsNeeded`)
    expect(submit().disabled).toBe(true)
    for (const f of FACTS.slice(0, 3)) fireEvent.click(pass(f))
    expect(line()).toBeTruthy()
    expect(submit().disabled).toBe(true)
    fireEvent.click(fail('income'))
    expect(line()).toBeNull()
    expect(submit().disabled).toBe(false)
    // Freely changeable until submission: tapping Pass again un-rates it.
    fireEvent.click(pass('identity'))
    expect(line()).toBeTruthy()
    expect(submit().disabled).toBe(true)
    // Changing a fact (Pass -> Fail) keeps all four rated.
    fireEvent.click(pass('identity'))
    fireEvent.click(fail('academic'))
    expect(line()).toBeNull()
    expect(submit().disabled).toBe(false)
  })

  it('"Yes, reject" sends exactly the box (a Fail with its chosen Why) and never records a verdict', async () => {
    const { api } = atAwaitingReview()
    await loaded()
    api.rejectBeforeInterview.mockResolvedValue(buildApplicationDetail('rejected', {
      rejection_category: 'pre_interview', rejection_reason: 'not_b40', pre_interview: undefined,
      verdict_decided_at: null,
    } as never))
    for (const f of ['identity', 'pathway']) fireEvent.click(pass(f))
    fireEvent.click(fail('academic'))
    fireEvent.click(fail('income'))
    const incomeRow = pass('income').closest('div.flex-wrap') as HTMLElement
    fireEvent.click(within(incomeRow).getByRole('button', { name: `${RV}.failReason.proof_missing` }))
    await openPanel()
    fireEvent.click(submit())
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` })) })
    await waitFor(() => expect(api.rejectBeforeInterview).toHaveBeenCalledTimes(1))
    expect(api.rejectBeforeInterview).toHaveBeenCalledWith(7, 'not_b40', 'Dummy note', {
      facts: { identity: 'pass', academic: 'fail', pathway: 'pass', income: 'fail' },
      fail_reasons: { academic: 'other', income: 'proof_missing' },
    }, { token: 'test-token' })
    expect(await screen.findByTestId('pre-interview-record')).toBeTruthy()
    expect(api.recordVerdict).not.toHaveBeenCalled()
  })

  it('an assessment already on the case fills the box and is sent; the box reloads from the reject reply', async () => {
    const recorded = { identity: 'pass', academic: 'pass', pathway: 'fail', income: 'pass', overall: 'decline',
      fail_reasons: { pathway: 'documents_differ' } }
    // Back at Awaiting review with an assessment on file: the box is open (stuck after a verdict), filled in.
    const { api } = atAwaitingReview({ officer_verdict: recorded, verdict_decided_at: '2026-11-20T09:00:00.000Z' })
    await loaded()
    for (const f of FACTS) expect(rated(f)).toBe(true)
    // The reply carries a different assessment: the box must show the server's, not the page's.
    api.rejectBeforeInterview.mockResolvedValue(buildApplicationDetail('rejected', {
      rejection_category: 'pre_interview', rejection_reason: 'not_b40', pre_interview: undefined,
      verdict_decided_at: '2026-11-20T09:00:00.000Z',
      officer_verdict: { identity: 'fail', academic: 'fail', pathway: 'fail', income: 'fail', overall: 'decline',
        fail_reasons: {} },
    } as never))
    await openPanel()
    expect(line()).toBeNull()
    fireEvent.click(submit())
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` })) })
    expect(api.rejectBeforeInterview).toHaveBeenCalledWith(7, 'not_b40', 'Dummy note', {
      facts: { identity: 'pass', academic: 'pass', pathway: 'fail', income: 'pass' },
      fail_reasons: { pathway: 'documents_differ' },
    }, { token: 'test-token' })
    // A rejected case with a recorded assessment shows the box locked (badges): all four are the reply's Fail.
    await waitFor(() => expect(pass('identity')).toBeNull())
    expect(screen.getAllByText(`${RV}.factFail`)).toHaveLength(4)
    expect(screen.queryByText(`${RV}.factPass`)).toBeNull()
    expect(api.recordVerdict).not.toHaveBeenCalled()
  })

  it('a stale refusal (a reviewer got there first) reloads the box from the server, not only the case', async () => {
    const { api } = atAwaitingReview()
    await loaded()
    for (const f of FACTS) fireEvent.click(pass(f))
    await openPanel()
    // Meanwhile a reviewer took the case and their assessment is on the server: Identity is a Fail there.
    api.getScholarshipApplication.mockResolvedValue(buildApplicationDetail('profile_complete', {
      pre_interview: OFFER, assigned_to_id: 5, verdict_decided_at: null,
      officer_verdict: { identity: 'fail', academic: 'pass', pathway: 'pass', income: 'pass',
        fail_reasons: { identity: 'other' } },
    } as never))
    api.rejectBeforeInterview.mockRejectedValue(Object.assign(new Error('x'), { code: 'has_reviewer' }))
    fireEvent.click(submit())
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` })) })
    await waitFor(() => expect(api.getScholarshipApplication).toHaveBeenCalledTimes(2))
    // The page's unsaved Pass on Identity is gone: the box shows the server's Fail.
    await waitFor(() => expect(fail('identity').className).toMatch(/bg-critical-fill/))
    expect(pass('identity').className).not.toMatch(/bg-positive-fill/)
    expect(api.recordVerdict).not.toHaveBeenCalled()
  })

  it('a viewer who may not write: the box cannot be tapped, the red line shows and Reject stays greyed', async () => {
    renderCockpit({ role: 'org_admin', writes: {}, stage: 'profile_complete', build: { pre_interview: OFFER } as never })
    await loaded()
    await openPanel()
    for (const f of FACTS) {
      expect(pass(f).disabled).toBe(true)
      expect(fail(f).disabled).toBe(true)
    }
    expect(line()?.className).toContain('text-critical-600')   // the RED line (owner), not amber
    expect(submit().disabled).toBe(true)
  })

  it('after "Cancel decline" the box is reloaded from the reply: the decliner\'s facts do not linger', async () => {
    const declined = { identity: 'pass', academic: 'fail', pathway: 'pass', income: 'pass', fail_reasons: { academic: 'other' } }
    const { api } = renderCockpit({ role: 'org_admin', writes: true, stage: 'rejected',
      build: { rejection_category: 'pre_interview', rejection_reason: 'not_b40', verdict_decided_at: null,
               officer_verdict: declined } as never })
    await loaded()
    expect(pass('identity')).toBeNull()                      // a closed case with no recorded verdict: no box
    // The cancel takes the assessment back: Awaiting review, no reviewer, an empty box.
    api.cancelPendingDecline.mockResolvedValue(buildApplicationDetail('profile_complete', {
      pre_interview: OFFER, officer_verdict: {}, verdict_decided_at: null } as never))
    fireEvent.click(screen.getAllByRole('button', { name: 'admin.scholarship.cooloff.cancelDecline' })[0])
    const dialog = screen.getByRole('alertdialog')
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'admin.scholarship.cooloff.cancelDecline' }))
    })
    await waitFor(() => expect(pass('identity')).toBeTruthy())
    for (const f of FACTS) expect(rated(f)).toBe(false)
    await openPanel()
    expect(line()).toBeTruthy()
    expect(submit().disabled).toBe(true)
    expect(api.recordVerdict).not.toHaveBeenCalled()
  })
})
