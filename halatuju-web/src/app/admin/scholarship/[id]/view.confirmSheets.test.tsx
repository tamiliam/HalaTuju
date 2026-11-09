/**
 * @jest-environment jsdom
 *
 * THE COCKPIT'S THREE QUESTIONS, ASKED IN THE SITE'S OWN DIALOG (audit A3.3, TD-480).
 *
 * Nudge, cancel a scheduled decline and hold a pending award each asked with `window.confirm`,
 * which a browser may suppress and a phone draws as its own box (mobile-standard.md rule 5). They
 * now ask in the shared Sheet, as an `alertdialog`, with the words they always had. The two that
 * touch a decision (cancel, hold) cannot be dismissed by a stray tap: only the buttons answer.
 *
 * The other half of TD-480 lives here too: the referral pill's full name was a hover-only `title`,
 * so a phone saw only the acronym. It is visible text now.
 */
import { act, fireEvent, screen, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const NAME = (k: string) => ({ name: `admin.scholarship.${k}` })
const NUDGE_ON = { applicable: true, sent_at: null, available: true, available_at: null }

describe('the questions are asked in a dialog, never in window.confirm', () => {
  let nativeConfirm: jest.SpyInstance
  beforeEach(() => { nativeConfirm = jest.spyOn(window, 'confirm').mockReturnValue(true) })
  afterEach(() => { nativeConfirm.mockRestore() })

  it('cancel a scheduled decline: asks, and Keep does nothing', async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'rejected' })
    await loaded()
    fireEvent.click(screen.getAllByRole('button', NAME('cooloff.cancelDecline'))[0])
    const dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText('admin.scholarship.cooloff.cancelConfirm')).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'common.cancel' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(api.cancelPendingDecline).not.toHaveBeenCalled()
    expect(nativeConfirm).not.toHaveBeenCalled()
  })

  it('cancel a scheduled decline: the confirm button runs it once', async () => {
    const { api, app } = renderCockpit({ role: 'super', stage: 'rejected' })
    api.cancelPendingDecline.mockResolvedValue(app)
    await loaded()
    fireEvent.click(screen.getAllByRole('button', NAME('cooloff.cancelDecline'))[0])
    const dialog = screen.getByRole('alertdialog')
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', NAME('cooloff.cancelDecline')))
    })
    expect(api.cancelPendingDecline).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(nativeConfirm).not.toHaveBeenCalled()
  })

  it('a money question cannot be dismissed with Escape or the backdrop', async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'rejected' })
    await loaded()
    fireEvent.click(screen.getAllByRole('button', NAME('cooloff.cancelDecline'))[0])
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(api.cancelPendingDecline).not.toHaveBeenCalled()
  })

  it('hold a pending award: asks first, then holds', async () => {
    const { api, app } = renderCockpit({
      role: 'super', stage: 'recommended', build: { award_due_at: '2026-12-01T00:00:00Z' } })
    api.holdPendingAward.mockResolvedValue(app)
    await loaded()
    fireEvent.click(screen.getByRole('button', NAME('cooloff.holdAward')))
    expect(api.holdPendingAward).not.toHaveBeenCalled()
    const dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText('admin.scholarship.cooloff.holdConfirm')).toBeTruthy()
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', NAME('cooloff.holdAward')))
    })
    expect(api.holdPendingAward).toHaveBeenCalledTimes(1)
    expect(nativeConfirm).not.toHaveBeenCalled()
  })

  it('the reminder to a student: asks first, Keep sends nothing, Send sends once', async () => {
    const { api, app } = renderCockpit({
      role: 'super', stage: 'shortlisted', build: { nudge: NUDGE_ON } })
    api.nudgeStudent.mockResolvedValue(app)
    await loaded()
    fireEvent.click(screen.getByRole('button', NAME('blockers.nudge.send')))
    let dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText('admin.scholarship.blockers.nudge.confirm')).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'common.cancel' }))
    expect(api.nudgeStudent).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', NAME('blockers.nudge.send')))
    dialog = screen.getByRole('alertdialog')
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', NAME('blockers.nudge.send')))
    })
    expect(api.nudgeStudent).toHaveBeenCalledTimes(1)
    expect(nativeConfirm).not.toHaveBeenCalled()
  })
})

describe('the referral pill names its source without a hover', () => {
  it('shows the full name as text (it was a hover-only title)', async () => {
    renderCockpit({
      role: 'super', stage: 'interviewing',
      build: { referral_source: 'smc', source: { id: 3, code: 'smc', name: 'Test Referring Organisation' } },
    })
    await loaded()
    expect(screen.getByText('SMC', { exact: false }).textContent).toContain('Test Referring Organisation')
  })
})
