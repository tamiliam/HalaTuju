/**
 * @jest-environment jsdom
 *
 * LL2: Pass / Fail on the four facts, and the one-tap reason when a reviewer FAILS a fact the engine
 * showed green. Asserted from what a reviewer can see and press:
 *  * the question and five chips show ONLY for engine green + reviewer Fail;
 *  * a chip puts its code in the `record-verdict` payload, and undoing Fail clears it;
 *  * Save is held back until the reason is picked (the web holds it back; the server never does);
 *  * stored reasons load, and the locked view shows the chosen reason;
 *  * Approve with a failed fact shows a soft warning and does NOT disable Save.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildVerdict } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const K = 'admin.scholarship.recordVerdict.'
const failButtons = () => screen.getAllByRole('button', { name: `${K}factFail` })
const chip = (code: string) => screen.getByRole('button', { name: `${K}failReason.${code}` })
const noQuestion = () => expect(screen.queryByText(`${K}failWhy`)).toBeNull()

/** Four pressed facts, a conclusion and an outcome: only the reason (or nothing) can hold Save. */
const decided = (over: Record<string, string> = {}, extra = {}) => ({
  officer_verdict: { identity: 'pass', academic: 'pass', income: 'pass', pathway: 'pass', overall: 'decline', ...over },
  verdict_reason: 'The evidence supports it.',
  ...extra,
})

describe('the reason question and chips', () => {
  it('shows nothing until a fact is failed', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing' })
    await loaded()
    noQuestion()
    expect(screen.queryByRole('button', { name: `${K}failReason.other` })).toBeNull()
  })

  it('a green fact that is failed asks why, with the five answers in order', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing' })
    await loaded()
    fireEvent.click(failButtons()[0])
    expect(screen.getByText(`${K}failWhy`)).toBeTruthy()
    const names = ['engine_wrong', 'read_wrong', 'new_information', 'programme_rule', 'other']
    names.forEach((c) => expect(chip(c)).toBeTruthy())
    expect(screen.getAllByRole('button').map((b) => b.textContent ?? '')
      .filter((x) => x.startsWith(`${K}failReason.`))).toEqual(names.map((c) => `${K}failReason.${c}`))
  })

  it('a fact the engine did NOT show green takes no reason when failed', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: { verdict: buildVerdict({ identity: 'gap' }) } })
    await loaded()
    fireEvent.click(failButtons()[0])
    noQuestion()
  })

  it('undoing Fail removes the question and the chosen reason', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing' })
    await loaded()
    fireEvent.click(failButtons()[0])
    fireEvent.click(chip('read_wrong'))
    expect(chip('read_wrong').getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(failButtons()[0])        // undo
    noQuestion()
    fireEvent.click(failButtons()[0])        // fail again: the reason must not have survived
    expect(chip('read_wrong').getAttribute('aria-pressed')).toBe('false')
  })
})

describe('Save is held back without a reason, and the payload carries it', () => {
  it('holds Save back, says why, then sends the code once picked', async () => {
    const m = renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: decided({ income: 'fail' }) })
    await loaded()
    const save = () => screen.getByRole('button', { name: `${K}saveDecline` }) as HTMLButtonElement
    expect(save().disabled).toBe(true)
    expect(screen.getByText(`${K}pickReason`)).toBeTruthy()
    fireEvent.click(chip('new_information'))
    expect(save().disabled).toBe(false)
    expect(screen.queryByText(`${K}pickReason`)).toBeNull()
    m.api.recordVerdict.mockResolvedValue({ ...m.app, finalise_result: null } as never)
    m.api.submitDeclineApplication.mockResolvedValue(m.app as never)
    fireEvent.click(save())
    await waitFor(() => expect(m.api.recordVerdict).toHaveBeenCalled())
    const payload = m.api.recordVerdict.mock.calls[0][1]
    expect(payload.fail_reasons).toEqual({ income: 'new_information' })
    expect(payload.officer_verdict.income).toBe('fail')
  })

  it('sends no reasons when nothing green was failed', async () => {
    const m = renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
      build: decided({ income: 'fail' }, { verdict: buildVerdict({ income: 'gap' }) }) })
    await loaded()
    m.api.recordVerdict.mockResolvedValue({ ...m.app, finalise_result: null } as never)
    m.api.submitDeclineApplication.mockResolvedValue(m.app as never)
    fireEvent.click(screen.getByRole('button', { name: `${K}saveDecline` }))
    await waitFor(() => expect(m.api.recordVerdict).toHaveBeenCalled())
    expect(m.api.recordVerdict.mock.calls[0][1].fail_reasons).toEqual({})
  })
})

describe('stored reasons', () => {
  it('load into the chips (a missing key reads as empty)', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
      build: decided({ income: 'fail' }, { officer_verdict: {
        identity: 'pass', academic: 'pass', income: 'fail', pathway: 'pass', overall: 'decline',
        fail_reasons: { income: 'programme_rule' } } }) })
    await loaded()
    expect(chip('programme_rule').getAttribute('aria-pressed')).toBe('true')
    expect(chip('other').getAttribute('aria-pressed')).toBe('false')
  })

  it('the locked view shows the chosen reason beside the failed fact', async () => {
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'decline', officer_verdict: {
      identity: 'pass', academic: 'fail', income: 'pass', pathway: 'pass', overall: 'decline',
      fail_reasons: { academic: 'new_information' } } } })
    await loaded()
    expect(screen.getByText(new RegExp(`${K}failReason.new_information`))).toBeTruthy()
    expect(screen.queryByText(`${K}failWhy`)).toBeNull()
  })

  it('the locked view of an old row (no key) shows no reason line', async () => {
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'decline' } })
    await loaded()
    expect(screen.queryByText(new RegExp(`${K}failReasonLabel`))).toBeNull()
  })
})

describe('the soft warning', () => {
  const approved = (over: Record<string, string>) => decided({ overall: 'accept', ...over },
    { verdict: buildVerdict({ academic: 'gap' }) })

  it('shows on Approve with a failed fact, and Save stays pressable', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: approved({ academic: 'fail' }) })
    await loaded()
    expect(screen.getByText(`${K}failedAcceptWarn`)).toBeTruthy()
    const save = screen.getByRole('button', { name: `${K}save` }) as HTMLButtonElement
    expect(save.disabled).toBe(false)
  })

  it('does not show when nothing failed, or when the outcome is Decline', async () => {
    const a = renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: approved({}) })
    await loaded()
    expect(screen.queryByText(`${K}failedAcceptWarn`)).toBeNull()
    a.unmount()
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
      build: { ...approved({ academic: 'fail' }), officer_verdict: {
        identity: 'pass', academic: 'fail', income: 'pass', pathway: 'pass', overall: 'decline' } } })
    await loaded()
    expect(screen.queryByText(`${K}failedAcceptWarn`)).toBeNull()
  })
})
