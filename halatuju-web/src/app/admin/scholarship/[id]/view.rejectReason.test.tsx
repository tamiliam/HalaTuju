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
const qcPanel = () => screen.queryByText('admin.scholarship.qcDecision.title')

describe('TD-483: the QC panel follows the server rule', () => {
  it('a QC the server would refuse sees why, and no panel', async () => {
    renderCockpit({ role: 'qc', stage: 'awaiting_qc',
                    build: { outcome: 'recommend', qc_refusal: 'self_assigned_qc_forbidden' } })
    await loaded()
    expect(qcPanel()).toBeNull()
    expect(screen.getByTestId('qc-refusal').textContent)
      .toBe('admin.scholarship.qcDecision.refusal.self_assigned_qc_forbidden')
  })

  it('a QC the server clears sees the panel and no note', async () => {
    renderCockpit({ role: 'qc', stage: 'awaiting_qc',
                    build: { outcome: 'recommend', qc_refusal: null } })
    await loaded()
    expect(qcPanel()).toBeTruthy()
    expect(screen.queryByTestId('qc-refusal')).toBeNull()
  })

  it('a refusal on the click is shown in the cockpit language, for every code', async () => {
    const { api } = renderCockpit({ role: 'qc', stage: 'awaiting_qc',
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
    const { api, app } = renderCockpit({ role: 'super', stage: 'active' })
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
    renderCockpit({ role: 'super', stage: 'rejected',
                    build: { rejection_category: 'interview', rejection_comments: 'Never attended.',
                             rejected_by_unassigned: true } })
    await loaded()
    expect(screen.getByText('admin.scholarship.orgReject.recordTitle')).toBeTruthy()
    expect(screen.getByText('Never attended.')).toBeTruthy()
    expect(screen.getByText(/admin\.scholarship\.reject\.notAssigned/)).toBeTruthy()
  })

  it('the assignee\'s own decline carries no such note', async () => {
    renderCockpit({ role: 'super', stage: 'rejected',
                    build: { rejection_category: 'interview', rejection_comments: 'Never attended.',
                             rejected_by_unassigned: false } })
    await loaded()
    expect(screen.getByText('Never attended.')).toBeTruthy()
    expect(screen.queryByText(/admin\.scholarship\.reject\.notAssigned/)).toBeNull()
  })
})
