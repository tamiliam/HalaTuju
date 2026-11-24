/**
 * @jest-environment jsdom
 *
 * Sprint A1.11a part 2.
 *
 *  * **TD-483.** The QC panel follows the SERVER's separation rule: the detail read carries
 *    `qc_refusal` (the code the QC door would refuse this viewer with), so a QC who was assigned
 *    before, interviewed, or did other review work sees a one-line note, not a panel that answers
 *    403. Every refusal code reaches the person in their language, not as the server's English.
 *  * **TD-227.** A decline at `/reject/` needs a reason (Cancel still does nothing; a blank one is
 *    refused before anything is sent), and the record shows the reason and, when the decliner was
 *    not the assigned reviewer, says so.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
/** Access S1: a QC writer, as the server serves her (`can_qc` is the QC door's own key). */
const QC_WRITER = { can_write: true, can_cancel_decline: true, can_tranche: true, can_qc: true }
const qcPanel = () => screen.queryByText('admin.scholarship.qcDecision.title')

describe('TD-483: the QC panel follows the server rule', () => {
  it('a QC the server would refuse sees why, and no panel', async () => {
    renderCockpit({ role: 'qc', writes: QC_WRITER, stage: 'awaiting_qc',
                    build: { outcome: 'recommend', qc_refusal: 'self_assigned_qc_forbidden' } })
    await loaded()
    expect(qcPanel()).toBeNull()
    expect(screen.getByTestId('qc-refusal').textContent)
      .toBe('admin.scholarship.qcDecision.refusal.self_assigned_qc_forbidden')
  })

  it('a QC the server clears sees the panel and no note', async () => {
    renderCockpit({ role: 'qc', writes: QC_WRITER, stage: 'awaiting_qc',
                    build: { outcome: 'recommend', qc_refusal: null } })
    await loaded()
    expect(qcPanel()).toBeTruthy()
    expect(screen.queryByTestId('qc-refusal')).toBeNull()
  })

  it('a refusal on the click is shown in the cockpit language, for every code', async () => {
    const { api } = renderCockpit({ role: 'qc', writes: QC_WRITER, stage: 'awaiting_qc',
                                    build: { outcome: 'recommend', qc_refusal: null } })
    await loaded()
    const refused = Object.assign(new Error('You interviewed this student.'),
                                  { status: 403, code: 'self_interview_qc_forbidden' })
    api.recordQcDecision.mockRejectedValue(refused)
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.qcDecision.accept' }))
    expect((await screen.findAllByText(
      'admin.scholarship.qcDecision.refusal.self_interview_qc_forbidden')).length).toBeGreaterThan(0)
  })
})

describe('TD-227: a decline needs a reason, and says who', () => {
  afterEach(() => { jest.restoreAllMocks() })

  it('Cancel sends nothing; a blank reason is refused; a reason is sent', async () => {
    const { api, app } = renderCockpit({ role: 'super', writes: true, stage: 'active' })
    await loaded()
    const decline = () => fireEvent.click(
      screen.getByRole('button', { name: 'admin.scholarship.reject.declineContractual' }))
    const prompt = jest.spyOn(window, 'prompt')

    prompt.mockReturnValueOnce(null)
    decline()
    expect(api.rejectApplication).not.toHaveBeenCalled()

    prompt.mockReturnValueOnce('   ')
    decline()
    expect((await screen.findAllByText('admin.scholarship.reject.reasonRequired')).length).toBeGreaterThan(0)
    expect(api.rejectApplication).not.toHaveBeenCalled()

    api.rejectApplication.mockResolvedValue({
      ...app, status: 'rejected', rejection_category: 'contractual',
      rejection_comments: 'Did not register at the college.', rejected_by_unassigned: true })
    prompt.mockReturnValueOnce('  Did not register at the college. ')
    decline()
    await waitFor(() => expect(api.rejectApplication).toHaveBeenCalledWith(
      7, 'contractual', 'Did not register at the college.', { token: 'test-token' }))
    expect(await screen.findByText('Did not register at the college.')).toBeTruthy()
  })

  it('the record of an interview decline shows the reason and that it was not the assignee', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'rejected',
                    build: { rejection_category: 'interview', rejection_comments: 'Never attended.',
                             rejected_by_unassigned: true } })
    await loaded()
    expect(screen.getByText('admin.scholarship.orgReject.recordTitle')).toBeTruthy()
    expect(screen.getByText('Never attended.')).toBeTruthy()
    expect(screen.getByText(/admin\.scholarship\.reject\.notAssigned/)).toBeTruthy()
  })

  it('the assignee\'s own decline carries no such note', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'rejected',
                    build: { rejection_category: 'interview', rejection_comments: 'Never attended.',
                             rejected_by_unassigned: false } })
    await loaded()
    expect(screen.getByText('Never attended.')).toBeTruthy()
    expect(screen.queryByText(/admin\.scholarship\.reject\.notAssigned/)).toBeNull()
  })
})

describe('owner 2026-11-23: "Rejected" plus ONE served second chip', () => {
  const chips = () => screen.queryAllByTestId('rejection-chip').map((c) => c.textContent)

  it.each([
    ['merit', 'merit'], ['need', 'need'], ['state', 'state'], ['shortlisted', 'shortlisted'],
    ['before_interview', 'before_interview'], ['interview', 'interview'], ['qc', 'qc'],
    ['contractual', 'contractual'],
  ])('the served %s chip reads its label beside "Rejected"', async (code, label) => {
    renderCockpit({ role: 'super', stage: 'rejected', build: { rejection_category: 'interview', rejection_chip: code } })
    await loaded()
    expect(screen.getAllByText('admin.scholarship.statuses.rejected').length).toBeGreaterThan(0)
    expect(chips()).toEqual([`admin.scholarship.rejectionChip.${label}`])
    // the old category pill is gone: the chip replaces it, never beside it
    expect(screen.queryByText('admin.scholarship.reject.category.interview')).toBeNull()
  })

  it('qc and interview are told apart by the served chip, not the category', async () => {
    renderCockpit({ role: 'super', stage: 'rejected', build: { rejection_category: 'interview', rejection_chip: 'qc' } })
    await loaded()
    expect(chips()).toEqual(['admin.scholarship.rejectionChip.qc'])
  })

  it('another ineligible reason keeps the "Ineligible" label', async () => {
    renderCockpit({ role: 'super', stage: 'rejected', build: { rejection_category: 'ineligible', rejection_chip: 'ineligible' } })
    await loaded()
    expect(chips()).toEqual(['admin.scholarship.reject.category.ineligible'])
  })

  it('a blank chip shows no second chip', async () => {
    renderCockpit({ role: 'super', stage: 'rejected', build: { rejection_category: '', rejection_chip: '' } })
    await loaded()
    expect(chips()).toEqual([])
    expect(screen.getAllByText('admin.scholarship.statuses.rejected').length).toBeGreaterThan(0)
  })

  it('a reject before interview is "Rejected", never a status of its own', async () => {
    renderCockpit({ role: 'super', stage: 'rejected',
                    build: { rejection_category: 'pre_interview', rejection_reason: 'not_b40', rejection_chip: 'before_interview' } })
    await loaded()
    expect(screen.queryByText('admin.scholarship.statuses.rejected_before_interview')).toBeNull()
    expect(chips()).toEqual(['admin.scholarship.rejectionChip.before_interview'])
  })

  it('owner D: a case failing the state rule but not rejected keeps its status plus "state"', async () => {
    renderCockpit({ role: 'super', stage: 'submitted', build: { rejection_chip: 'state' } })
    await loaded()
    expect(screen.getAllByText('admin.scholarship.statuses.submitted').length).toBeGreaterThan(0)
    expect(chips()).toEqual(['admin.scholarship.rejectionChip.state'])
  })
})

describe('owner 2026-11-23: a case rejected before any review shows only its record', () => {
  const titles = () => Array.from(document.querySelectorAll('#record-verdict-panel h2')).map((h) => h.textContent)
  const HIDDEN = ['admin.scholarship.estimate.title', 'admin.scholarship.reviewerNotes.title']
  /** Everything else a review case carries, by heading text: it must be absent from the WHOLE page. */
  const ABSENT_TITLES = [
    ...HIDDEN, 'admin.scholarship.decision.title',
    'admin.scholarship.qcDecision.title', 'admin.scholarship.qcDecision.overrideTitle',
    'admin.scholarship.assignTitle', 'admin.scholarship.assign.assignedTitle',
    'admin.sources.witness.title',
    'admin.scholarship.recordVerdict.rateTitle']
  const ABSENT_IDS = ['decision-section', 'decision-missing', 'verdict-reason']
  const expectNoReviewCards = () => {
    for (const title of ABSENT_TITLES) expect(screen.queryByText(title)).toBeNull()
    for (const id of ABSENT_IDS) expect(document.getElementById(id)).toBeNull()
    expect(screen.queryByTestId('qc-refusal')).toBeNull()
  }
  const BOTH = { rejection_comments: 'Not a B40 household.', proposed_award_amount: '1200.00',
                 assigned_to_id: 3, assigned_to_name: 'Rev' }

  it('before interview: "Rejected before interview" on top, "Rejection reason" below, nothing else', async () => {
    renderCockpit({ role: 'super', stage: 'rejected',
                    build: { ...BOTH, rejection_category: 'pre_interview', rejection_reason: 'not_b40' } })
    await loaded()
    await screen.findByTestId('pre-interview-record')
    expect(titles()).toEqual(['admin.scholarship.preInterview.recordTitle', 'admin.scholarship.orgReject.recordTitle'])
    expectNoReviewCards()
  })

  it('by the org admin at Shortlisted: only "Rejection reason"', async () => {
    renderCockpit({ role: 'super', stage: 'rejected', build: { ...BOTH, rejection_category: 'incomplete' } })
    await loaded()
    expect(titles()).toEqual(['admin.scholarship.orgReject.recordTitle'])
    expectNoReviewCards()
  })

  // Owner 2026-11-24 (TD-716): a decline after interview hides the Estimated need card; the
  // notes card still shows.
  it('a decline after interview hides the estimate card but still shows the notes card', async () => {
    renderCockpit({ role: 'super', stage: 'rejected', build: { ...BOTH, rejection_category: 'interview' } })
    await loaded()
    expect(await screen.findByText('admin.scholarship.reviewerNotes.title')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.estimate.title')).toBeNull()
  })
})
