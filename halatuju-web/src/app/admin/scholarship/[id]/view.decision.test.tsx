/**
 * @jest-environment jsdom
 *
 * THE DECISION PANEL, RENDERED — the half of the cockpit BrightPath #21 and #24 both came out of.
 *
 * ⚠ THIS FILE REPLACES `src/lib/__tests__/approveLockoutGuard.test.ts`, which read this page's
 * SOURCE TEXT because "the officer cockpit has no test harness". It now has one. Two of that
 * guard's assertions are worth remembering, because they are why a text guard is not evidence:
 * one of them asserted that a key appears SOMEWHERE in the file — which it always did, including
 * with the fault re-injected — and another cried wolf on a CRLF line wrap. Everything below is
 * asserted from what a reviewer can SEE and PRESS.
 *
 * The two incidents, in one sentence each:
 *
 *  * **#21 — the half-completed Approve.** One press does two things: `record-verdict` saves the
 *    verdict, then `verify-accept` submits the case. Saving the verdict is what makes the panel
 *    read-only, so when the second half does not run the reviewer is left looking at a locked
 *    panel with no button she can press. Application 144 sat like that for six days. So: while
 *    the case is STUCK, the controls must STAY LIVE — `decisionLocked` exempts a stuck case.
 *  * **#24 — one sentence serving two outcomes.** `verified_at` is never written on the DECLINE
 *    road, so a rule that reads only the stamp calls every declined case stuck, the banner told
 *    the reviewer her verdict was not submitted, and the Save button offered to generate a final
 *    profile a decline does not produce. The wording must follow the RECORDED OUTCOME.
 */
import { fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

/** The case has arrived — the first paint is the loading line, the payload comes by promise. */
const loaded = () => screen.findByText('Test Student 07')

const button = (key: string) =>
  screen.getByRole('button', { name: `admin.scholarship.${key}` }) as HTMLButtonElement
const noButton = (key: string) =>
  screen.queryByRole('button', { name: `admin.scholarship.${key}` })

// ── Request #24: the decline road has its own words ──────────────────────────────────────────
describe('a verdict saved but not yet submitted says which verdict it was', () => {
  it('a DECLINE recorded at interviewing gets the decline banner and the decline Save label',
     async () => {
    // `record-verdict` moves no status, so the case is still `interviewing` with the decline
    // written on it. Before #24 this read "your recommendation has not been submitted" and
    // offered "Save & generate final profile" — both describing the opposite decision.
    renderCockpit({ role: 'super', stage: 'verdict_recorded', build: { outcome: 'decline' } })
    await loaded()
    expect(screen.getByText('admin.scholarship.recordVerdict.savedNotSubmittedDecline')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.recordVerdict.savedNotSubmitted')).toBeNull()
    expect(button('recordVerdict.saveDecline')).toBeTruthy()
    expect(noButton('recordVerdict.save')).toBeNull()
  })

  it('a RECOMMEND recorded at interviewing gets the recommend banner and the plain Save label',
     async () => {
    // The mirror case, asserted so the test above cannot pass by the page simply saying
    // "decline" everywhere.
    renderCockpit({ role: 'super', stage: 'verdict_recorded', build: { outcome: 'recommend' } })
    await loaded()
    expect(screen.getByText('admin.scholarship.recordVerdict.savedNotSubmitted')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.recordVerdict.savedNotSubmittedDecline')).toBeNull()
    expect(button('recordVerdict.save')).toBeTruthy()
    expect(noButton('recordVerdict.saveDecline')).toBeNull()
  })

  it('⚠ A DECLINE AWAITING QC IS NOT STUCK — no banner, no live buttons', async () => {
    // THE DEFECT ITSELF. `submit-decline` leaves the case at `interviewed` and stamps NOTHING
    // else — no `verified_at` — so a stuck-check that reads only the stamp calls this stuck for
    // ever and invites the reviewer to press Approve, which would replace her decline with a
    // recommendation. The panel here is the FROZEN record, not a form.
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'decline' } })
    await loaded()
    expect(screen.queryByText('admin.scholarship.recordVerdict.savedNotSubmittedDecline')).toBeNull()
    expect(screen.queryByText('admin.scholarship.recordVerdict.savedNotSubmitted')).toBeNull()
    expect(noButton('recordVerdict.approve')).toBeNull()
    expect(noButton('recordVerdict.saveDecline')).toBeNull()
  })

  it('a RECOMMEND awaiting QC is not stuck either — verify-accept left its stamp', async () => {
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(screen.queryByText('admin.scholarship.recordVerdict.savedNotSubmitted')).toBeNull()
    expect(noButton('recordVerdict.approve')).toBeNull()
  })
})

// ── #21: the lock-out that stranded application 144 ──────────────────────────────────────────
describe('a half-completed Approve leaves the reviewer a button she can press', () => {
  it('⚠ STUCK AFTER A VERDICT: Recommend is on screen AND ENABLED', async () => {
    // The whole of BrightPath #21. `verdict_decided_at` is set and `verified_at` is not, so the
    // submit never ran; locking the panel on the first stamp is what left application 144 with
    // no exit but a super-only Reopen recorded against a reviewer who did nothing wrong.
    renderCockpit({ role: 'super', stage: 'verdict_recorded', build: { outcome: 'recommend' } })
    await loaded()
    expect(button('recordVerdict.approve').disabled).toBe(false)
    expect(button('recordVerdict.save').disabled).toBe(false)
  })

  it('the assigned reviewer herself can press it — not only a super', async () => {
    // She is the person who has to finish it, and Reopen is super-only. `canWrite` admits the
    // ASSIGNED reviewer, which is why the fixture's `assigned_to_id` is her own admin id.
    renderCockpit({ role: 'reviewer', stage: 'verdict_recorded', build: { outcome: 'recommend' } })
    await loaded()
    expect(button('recordVerdict.approve').disabled).toBe(false)
  })

  it('NOT stuck and nothing recorded: the controls are there but asleep', async () => {
    // The ordinary mid-review case — an interview held, no verdict pressed, no conclusion
    // written. Approve must be visible (so the reviewer knows where she is going) and refused
    // (so she cannot skip the four facts). Without this the test above would also pass on a
    // page that simply never disables anything.
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    expect(button('recordVerdict.approve').disabled).toBe(true)
    expect(button('recordVerdict.decline').disabled).toBe(true)
    expect(button('recordVerdict.save').disabled).toBe(true)
  })

  it('NOT stuck and the decision recorded: the panel is read-only, with no controls at all',
     async () => {
    // The third state, and the one the lock exists FOR: once the case really has moved to QC
    // the verdict is frozen. A super may still Reopen it; nobody may edit it in place.
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(noButton('recordVerdict.approve')).toBeNull()
    expect(noButton('recordVerdict.decline')).toBeNull()
    expect(button('recordVerdict.reopen')).toBeTruthy()
  })

  it('a reopened decision unlocks the panel again', async () => {
    // A super reopen re-opens the WHOLE case for revision, for the assigned reviewer too.
    renderCockpit({
      role: 'reviewer', stage: 'awaiting_qc',
      build: { outcome: 'recommend', decision_reopened_at: '2026-06-03T09:00:00.000Z',
               decision_reopen_reason: 'The offer letter was superseded.' },
    })
    await loaded()
    expect(screen.getByText('admin.scholarship.recordVerdict.reopenedBanner')).toBeTruthy()
    expect(button('recordVerdict.approve').disabled).toBe(false)
  })
})

// ── The in-flight attribution line ───────────────────────────────────────────────────────────
describe('the reviewer line names what she actually decided', () => {
  it('reads "declined by" on the decline road', async () => {
    // Owner, on the live screen, 2026-09-18: a DECLINED case awaiting QC read "Interviewed and
    // recommended by". Same family as the banner above — one sentence serving two outcomes.
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'decline' } })
    await loaded()
    const line = screen.getByText(/admin\.scholarship\.interviewed/)
    expect(line.textContent).toContain('admin.scholarship.interviewedDeclinedBy')
    expect(line.textContent).not.toContain('admin.scholarship.interviewedRecommendedBy')
    // …and it names the reviewer and the date, which is the point of the line.
    expect(line.textContent).toContain('Test Reviewer 01')
    expect(line.textContent).toContain('01/06/2026')
  })

  it('reads "recommended by" on the recommend road', async () => {
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    const line = screen.getByText(/admin\.scholarship\.interviewed/)
    expect(line.textContent).toContain('admin.scholarship.interviewedRecommendedBy')
    expect(line.textContent).not.toContain('admin.scholarship.interviewedDeclinedBy')
  })
})

// ── Reopen asks why ──────────────────────────────────────────────────────────────────────────
describe('reopening a recorded decision', () => {
  it('demands a written reason before it will run', async () => {
    // A reopen asserts a reviewer error and is counted against her, so the reason is not
    // optional. Asserted through the button's own state, not through the handler.
    const { api } = renderCockpit({
      role: 'super', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    fireEvent.click(button('recordVerdict.reopen'))
    expect(button('recordVerdict.reopenConfirm').disabled).toBe(true)
    fireEvent.change(
      screen.getByPlaceholderText('admin.scholarship.recordVerdict.reopenPlaceholder'),
      { target: { value: 'The offer letter was superseded.' } })
    expect(button('recordVerdict.reopenConfirm').disabled).toBe(false)
    expect(api.reopenDecision).not.toHaveBeenCalled()
  })
})
