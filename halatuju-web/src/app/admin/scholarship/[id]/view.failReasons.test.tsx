/**
 * @jest-environment jsdom
 *
 * LL2 / F3 (I-11): Pass / Fail on the four facts, and the one-tap Why on EVERY Fail. The reason is
 * about the student, never the AI. Asserted from what a reviewer can see and press:
 *  * the question and five chips show for every failed fact, whatever the engine showed;
 *  * Other is already chosen, so Save is never held back for a reason;
 *  * a chip puts its code in the `record-verdict` payload, and undoing Fail clears it;
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
const CODES = ['proof_missing', 'document_false', 'documents_differ', 'interview_differs', 'other']

/** Four pressed facts, a conclusion and an outcome. */
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

  it('a failed fact asks why, with the five answers in order and Other already chosen', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing' })
    await loaded()
    fireEvent.click(failButtons()[0])
    expect(screen.getByText(`${K}failWhy`)).toBeTruthy()
    expect(screen.getAllByRole('button').map((b) => b.textContent ?? '')
      .filter((x) => x.startsWith(`${K}failReason.`))).toEqual(CODES.map((c) => `${K}failReason.${c}`))
    expect(chip('other').getAttribute('aria-pressed')).toBe('true')
  })

  it('a fact the engine did NOT show green asks why too', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: { verdict: buildVerdict({ identity: 'gap' }) } })
    await loaded()
    fireEvent.click(failButtons()[0])
    expect(screen.getByText(`${K}failWhy`)).toBeTruthy()
  })

  it('undoing Fail removes the question and the chosen reason', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing' })
    await loaded()
    fireEvent.click(failButtons()[0])
    fireEvent.click(chip('document_false'))
    expect(chip('document_false').getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(failButtons()[0])        // undo
    noQuestion()
    fireEvent.click(failButtons()[0])        // fail again: back to Other
    expect(chip('document_false').getAttribute('aria-pressed')).toBe('false')
    expect(chip('other').getAttribute('aria-pressed')).toBe('true')
  })
})

describe('the payload carries one reason for every Fail', () => {
  const save = () => screen.getByRole('button', { name: `${K}saveDecline` }) as HTMLButtonElement
  const send = async (m: ReturnType<typeof renderCockpit>) => {
    m.api.recordVerdict.mockResolvedValue({ ...m.app, finalise_result: null } as never)
    m.api.submitDeclineApplication.mockResolvedValue(m.app as never)
    fireEvent.click(save())
    await waitFor(() => expect(m.api.recordVerdict).toHaveBeenCalled())
    return m.api.recordVerdict.mock.calls[0][1]
  }

  it('Save is not held back; the chosen code is sent', async () => {
    const m = renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: decided({ income: 'fail' }) })
    await loaded()
    expect(save().disabled).toBe(false)
    fireEvent.click(chip('interview_differs'))
    const payload = await send(m)
    expect(payload.fail_reasons).toEqual({ income: 'interview_differs' })
    expect(payload.officer_verdict.income).toBe('fail')
  })

  it('a Fail with no chip pressed is sent as Other, even when the engine was not green', async () => {
    const m = renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
      build: decided({ income: 'fail' }, { verdict: buildVerdict({ income: 'gap' }) }) })
    await loaded()
    expect((await send(m)).fail_reasons).toEqual({ income: 'other' })
  })

  it('sends no reasons when nothing failed', async () => {
    const m = renderCockpit({ role: 'super', writes: true, stage: 'interviewing', build: decided() })
    await loaded()
    expect((await send(m)).fail_reasons).toEqual({})
  })
})

describe('stored reasons', () => {
  it('load into the chips', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
      build: decided({ income: 'fail' }, { officer_verdict: {
        identity: 'pass', academic: 'pass', income: 'fail', pathway: 'pass', overall: 'decline',
        fail_reasons: { income: 'documents_differ' } } }) })
    await loaded()
    expect(chip('documents_differ').getAttribute('aria-pressed')).toBe('true')
    expect(chip('other').getAttribute('aria-pressed')).toBe('false')
  })

  it('the locked view shows the chosen reason beside the failed fact', async () => {
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'decline', officer_verdict: {
      identity: 'pass', academic: 'fail', income: 'pass', pathway: 'pass', overall: 'decline',
      fail_reasons: { academic: 'proof_missing' } } } })
    await loaded()
    expect(screen.getByText(new RegExp(`${K}failReason.proof_missing`))).toBeTruthy()
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
