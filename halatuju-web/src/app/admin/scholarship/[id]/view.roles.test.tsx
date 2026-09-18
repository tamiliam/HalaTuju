/**
 * @jest-environment jsdom
 *
 * WHO SEES WHICH PANEL — the cockpit is one screen serving five kinds of officer, and the
 * difference between them is a permission, not a preference.
 *
 * Two controls carry real consequences and are asserted here:
 *
 *  * **The QC gate.** A second pair of eyes accepts or reopens a case awaiting QC. The gate is
 *    worth nothing if the person who recorded the verdict can also uphold it, so the panel is
 *    hidden from the reviewer who holds the case — including a `qc` or `org_admin` who happens
 *    to be that reviewer. The backend recorder guard refuses it too; this is the half a person
 *    can see.
 *  * **The org-admin reject.** Immediate and IRREVERSIBLE — no cool-off, so no Cancel banner to
 *    undo it. Its role gate is deliberately narrower than every other per-application write
 *    ("rejection is a super feature; the org admin is the super of the organisation"), and its
 *    stage gate is `ORG_REJECT_FROM` — one status. A card rendered outside either is not a
 *    cosmetic bug: it is a button that looks live and answers 400 or 403.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit, ASSIGNED_ADMIN_ID } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const qcPanel = () => screen.queryByText('admin.scholarship.qcDecision.title')
const rejectCard = () => screen.queryByRole('button', { name: 'admin.scholarship.orgReject.start' })

// ── The QC gate ──────────────────────────────────────────────────────────────────────────────
describe('the QC decision panel at AWAITING QC', () => {
  it.each(['super', 'qc', 'org_admin'] as const)('%s may act as the second pair of eyes',
    async (role) => {
      renderCockpit({ role, stage: 'awaiting_qc', build: { outcome: 'recommend' } })
      await loaded()
      expect(qcPanel()).toBeTruthy()
      expect(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' })).toBeTruthy()
      expect(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopen' })).toBeTruthy()
    })

  it.each(['reviewer', 'admin', 'finance', 'partner'] as const)('%s does not', async (role) => {
    renderCockpit({ role, stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(qcPanel()).toBeNull()
  })

  it('⚠ HIDES IT FROM THE QC WHO REVIEWED THE CASE — a gate of one is no gate', async () => {
    // Two-person control. Signed in as a `qc` whose own admin id IS the assignee's.
    renderCockpit({
      role: 'qc', adminId: ASSIGNED_ADMIN_ID,
      stage: 'awaiting_qc', build: { outcome: 'recommend' },
    })
    await loaded()
    expect(qcPanel()).toBeNull()
  })

  it('reads CONFIRM DECLINE, not Accept, when the verdict is a decline', async () => {
    // A decline at QC confirms a REJECTION, not a recommendation (owner 2026-07-19). The red
    // primary button is the whole difference between upholding a decline and awarding a bursary.
    renderCockpit({ role: 'qc', stage: 'awaiting_qc', build: { outcome: 'decline' } })
    await loaded()
    expect(screen.getByRole('button',
      { name: 'admin.scholarship.qcDecision.confirmDecline' })).toBeTruthy()
    expect(screen.queryByRole('button',
      { name: 'admin.scholarship.qcDecision.accept' })).toBeNull()
    // …and the secondary path is reopen-ONLY: offering "reject" again here is redundant.
    expect(screen.getByRole('button',
      { name: 'admin.scholarship.qcDecision.reopenOnly' })).toBeTruthy()
  })

  it('is not offered before the case reaches QC, nor after', async () => {
    for (const stage of ['interviewing', 'recommended'] as const) {
      const view = renderCockpit({ role: 'qc', stage })
      await loaded()
      expect(qcPanel()).toBeNull()
      view.unmount()
    }
  })

  it('accepting sends the QC decision, with no comment attached', async () => {
    const { api } = renderCockpit({ role: 'qc', stage: 'awaiting_qc',
                                    build: { outcome: 'recommend' } })
    await loaded()
    api.recordQcDecision.mockResolvedValue(buildApplicationDetail('recommended'))
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' }))
    expect(api.recordQcDecision).toHaveBeenCalledWith(
      7, { decision: 'accept', comments: undefined, override_reason: undefined },
      { token: 'test-token' })
    // The success state: the gate has closed behind them and the QC is now NAMED on the case.
    expect(await screen.findByText(/Test Quality Officer 02/)).toBeTruthy()
    expect(qcPanel()).toBeNull()
  })

  it('reopening refuses to send until the gaps are written down', async () => {
    // The comment is emailed to the reviewer and is the only thing telling her what to fix.
    const { api } = renderCockpit({ role: 'qc', stage: 'awaiting_qc',
                                    build: { outcome: 'recommend' } })
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.reopen' }))
    const confirm = screen.getByRole('button',
      { name: 'admin.scholarship.qcDecision.reopenConfirm' }) as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    fireEvent.click(confirm)
    expect(api.recordQcDecision).not.toHaveBeenCalled()

    fireEvent.change(
      screen.getByPlaceholderText('admin.scholarship.qcDecision.commentsPlaceholder'),
      { target: { value: 'The offer letter is not the final one.' } })
    api.recordQcDecision.mockResolvedValue(
      buildApplicationDetail('interviewing', { status: 'interviewing' }))
    fireEvent.click(screen.getByRole('button',
      { name: 'admin.scholarship.qcDecision.reopenConfirm' }))
    expect(api.recordQcDecision).toHaveBeenCalledWith(
      7, { decision: 'reopen', comments: 'The offer letter is not the final one.',
           override_reason: undefined },
      { token: 'test-token' })
    // The case has gone back to the reviewer, so the gate is no longer this officer's to hold.
    await waitFor(() => expect(qcPanel()).toBeNull())
  })
})

// ── The org-admin reject ─────────────────────────────────────────────────────────────────────
describe('rejecting a stuck applicant outright', () => {
  it.each(['org_admin', 'super'] as const)('%s is offered it at shortlisted', async (role) => {
    renderCockpit({ role, stage: 'shortlisted' })
    await loaded()
    expect(rejectCard()).toBeTruthy()
  })

  it.each(['reviewer', 'admin', 'qc', 'finance'] as const)('%s is not', async (role) => {
    renderCockpit({ role, stage: 'shortlisted' })
    await loaded()
    expect(rejectCard()).toBeNull()
  })

  it.each(['profile_complete', 'interviewing', 'recommended'] as const)(
    'is not offered at %s — ORG_REJECT_FROM is one status', async (stage) => {
      // KEEP IN SYNC with `services.ORG_REJECT_FROM`. Anywhere else the endpoint answers 400.
      renderCockpit({ role: 'org_admin', stage })
      await loaded()
      expect(rejectCard()).toBeNull()
    })

  it('⚠ TAKES THREE DELIBERATE STEPS, and the reason is mandatory at the second', async () => {
    // Unlike every other decline this one is IMMEDIATE and IRREVERSIBLE: there is no cool-off
    // and therefore no Cancel banner to undo it. The confirm step IS the safety net, so it is
    // in-page rather than a `window.confirm` the browser can suppress.
    const { api } = renderCockpit({ role: 'org_admin', stage: 'shortlisted' })
    await loaded()

    // 1 — idle → form
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.orgReject.start' }))
    const submit = () => screen.getByRole('button',
      { name: 'admin.scholarship.orgReject.submit' }) as HTMLButtonElement
    expect(submit().disabled).toBe(true)

    // 2 — the written reason. It is never emailed, so this screen is its whole audit surface.
    fireEvent.change(screen.getByLabelText('admin.scholarship.orgReject.whyLabel'),
                     { target: { value: 'No documents after four reminders.' } })
    expect(submit().disabled).toBe(false)
    fireEvent.click(submit())

    // 3 — the confirm step, which must SAY what is about to happen before it happens
    expect(screen.getByText('admin.scholarship.orgReject.confirmTitle')).toBeTruthy()
    expect(api.orgRejectApplication).not.toHaveBeenCalled()

    api.orgRejectApplication.mockResolvedValue(buildApplicationDetail('shortlisted', {
      status: 'rejected', rejection_category: 'incomplete',
      rejection_comments: 'No documents after four reminders.',
      rejected_by_name: 'Test Officer 04', rejected_at: '2026-06-01T09:00:00.000Z',
    }))
    fireEvent.click(screen.getByRole('button',
      { name: 'admin.scholarship.orgReject.confirmYes' }))
    expect(api.orgRejectApplication).toHaveBeenCalledWith(
      7, 'No documents after four reminders.', { token: 'test-token' })

    // …and the screen settles into the read-only record of what was just done.
    expect(await screen.findByText('admin.scholarship.orgReject.recordTitle')).toBeTruthy()
    expect(screen.getByText('No documents after four reminders.')).toBeTruthy()
  })

  it('backing out of the confirm step keeps the typed reason', async () => {
    // A transient failure or a second thought must not cost the officer their sentence.
    renderCockpit({ role: 'org_admin', stage: 'shortlisted' })
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.orgReject.start' }))
    fireEvent.change(screen.getByLabelText('admin.scholarship.orgReject.whyLabel'),
                     { target: { value: 'No documents after four reminders.' } })
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.orgReject.submit' }))
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.orgReject.back' }))
    expect((screen.getByLabelText('admin.scholarship.orgReject.whyLabel') as HTMLTextAreaElement)
      .value).toBe('No documents after four reminders.')
  })
})
