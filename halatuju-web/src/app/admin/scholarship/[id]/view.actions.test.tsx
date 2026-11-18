/**
 * @jest-environment jsdom
 *
 * THE COCKPIT'S WRITES — the controls an officer presses and what they send.
 *
 * Two of them, each for a stated reason:
 *
 *  * **The reporting date.** Not cosmetic: it sizes the bursary (a course begun before the cohort
 *    year is a continuing student with one year of funding left), gates payment eligibility and
 *    triggers the semester-result request. QC REFUSES to accept a case without one, so a case
 *    whose offer letter carries no readable date needs a human to type it — and only inside the
 *    reviewer's own window, because QC cannot fill it in place. #120 displayed a ticked reporting
 *    date on screen while the column driving the bursary was empty, so the box's own condition
 *    matters as much as the save.
 *  * **Assigning a reviewer and raising a query** — the two ordinary writes. Both are asserted
 *    from the click through to the arguments AND to the state the officer is left looking at; a
 *    call that lands while the screen says nothing is the shape of BrightPath #20.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit, OTHER_ADMIN_ID } from '@/test/renderCockpit'
import { buildApplicationDetail, buildDocument } from '@/test/adminApplicationDetail'
import { AdminScholarshipDetailView } from './view'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

/** The date box, addressed by the accessible name the heading gives it. */
const dateBox = () =>
  screen.queryByLabelText('admin.scholarship.reportingDateEntry.title') as HTMLInputElement | null

/** An offer letter that CARRIES a readable reporting date — then the value syncs itself and a
 *  manual box would only invite contradicting the document. */
const letterWithDate = (extra: Record<string, unknown> = {}) => [buildDocument('offer_letter', {
  pathway_check: {
    name: 'match', ic: 'match', candidate_name: 'Test Student 07',
    candidate_nric: '030303-14-0007', programme: 'Test Engineering Degree',
    institution: 'Test University', issuer: 'Test University', offer_date: '2026-05-01',
    intake: '2026', reporting_date: '2026-06-08', address: '',
  },
  ...extra,
})]

describe('the reporting-date box appears only where a human may settle it', () => {
  it('is offered while the reviewer holds the case', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing' })
    await loaded()
    expect(dateBox()).toBeTruthy()
  })

  it('is NOT offered once the letter carries a readable date', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
                    build: { documents: letterWithDate() } })
    await loaded()
    expect(dateBox()).toBeNull()
  })

  it('⚠ A SUPERSEDED OFFER DOES NOT COUNT — the box comes back', async () => {
    // The value shown has to come from the CURRENT offer, or the screen and the column driving
    // the bursary can disagree (#120). A replaced letter is history, not the pathway.
    renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
                    build: { documents: letterWithDate({ superseded_at: '2026-05-20T09:00:00.000Z' }) } })
    await loaded()
    expect(dateBox()).toBeTruthy()
  })

  it.each(['shortlisted', 'profile_complete', 'awaiting_qc', 'recommended'] as const)(
    'is not offered at %s', async (stage) => {
      const roads = stage === 'awaiting_qc'
      renderCockpit({ role: 'super', writes: true, stage,
                      build: { reporting_date: null,
                               ...(roads ? { outcome: 'recommend' as const } : {}) } })
      await loaded()
      expect(dateBox()).toBeNull()
    })

  it('comes back on a REOPENED case, wherever the reopen landed it', async () => {
    // A reopen lands in two different places (recommended → interviewed, interviewed →
    // interviewing), so it is checked explicitly rather than by status — otherwise a case
    // bounced back from Recommended would miss the box.
    renderCockpit({
      role: 'super', writes: true, stage: 'awaiting_qc',
      build: { outcome: 'recommend', reporting_date: null,
               decision_reopened_at: '2026-06-03T09:00:00.000Z' },
    })
    await loaded()
    expect(dateBox()).toBeTruthy()
  })

  it('refuses to save an empty date, then sends the one that was typed', async () => {
    const { api } = renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
                                    build: { reporting_date: null } })
    await loaded()
    const save = () => screen.getByRole('button',
      { name: 'admin.scholarship.reportingDateEntry.save' }) as HTMLButtonElement
    expect(save().disabled).toBe(true)

    fireEvent.change(dateBox() as HTMLInputElement, { target: { value: '2026-07-01' } })
    expect(save().disabled).toBe(false)

    api.setReportingDate.mockResolvedValue(
      buildApplicationDetail('interviewing', { reporting_date: '2026-07-01' }))
    fireEvent.click(save())
    expect(api.setReportingDate).toHaveBeenCalledWith(7, '2026-07-01', { token: 'test-token' })
    // The success state: the screen now states the date on file.
    expect(await screen.findByText('admin.scholarship.reportingDateEntry.current')).toBeTruthy()
  })

  it('a failed save says why and keeps the typed date (TD-165)', async () => {
    const { api } = renderCockpit({ role: 'super', writes: true, stage: 'interviewing',
                                    build: { reporting_date: null } })
    await loaded()
    fireEvent.change(dateBox() as HTMLInputElement, { target: { value: '2026-07-01' } })
    api.setReportingDate.mockRejectedValue(new Error('A reporting date cannot be in 2019.'))
    fireEvent.click(screen.getByRole('button', { name: 'admin.scholarship.reportingDateEntry.save' }))
    expect(await screen.findByText('A reporting date cannot be in 2019.')).toBeTruthy()
    expect((dateBox() as HTMLInputElement).value).toBe('2026-07-01')
    expect(screen.queryByText('admin.scholarship.reportingDateEntry.current')).toBeNull()
  })
})

describe('assigning a reviewer', () => {
  /** The assign card, found by its own heading rather than by being the Nth combobox — the page
   *  has several, and "the first one" is how a test quietly moves to another control. */
  const assignPicker = (headingKey: string) => {
    const card = screen.getByText(`admin.scholarship.${headingKey}`).closest('div') as HTMLElement
    return within(card).getByRole('combobox') as HTMLSelectElement
  }

  it('sends the chosen reviewer, and the card then names them', async () => {
    const { api } = renderCockpit({ role: 'org_admin', writes: true, stage: 'profile_complete' })
    await loaded()
    const picker = assignPicker('assignTitle')
    expect(picker.value).toBe('')

    // A2.3: the assign reply is slim; the page reloads the case, and THAT names the reviewer.
    api.assignApplication.mockResolvedValue({
      id: 7, status: 'assigned', assigned_to_id: OTHER_ADMIN_ID,
      assigned_to_name: 'Test Reviewer 05', assigned_at: '2026-11-07T00:00:00Z',
    })
    api.getScholarshipApplication.mockResolvedValue(buildApplicationDetail('assigned', {
      assigned_to_id: OTHER_ADMIN_ID, assigned_to_name: 'Test Reviewer 05',
    }))
    fireEvent.change(picker, { target: { value: String(OTHER_ADMIN_ID) } })
    expect(api.assignApplication).toHaveBeenCalledWith(7, OTHER_ADMIN_ID, { token: 'test-token' })

    // The success state: the heading flips from "assign one" to "assigned", and the picker
    // shows who holds the case — a write nobody can see is the BrightPath #20 shape.
    expect(await screen.findByText('admin.scholarship.assign.assignedTitle')).toBeTruthy()
    expect(assignPicker('assign.assignedTitle').value).toBe(String(OTHER_ADMIN_ID))
  })

  it('a refusal says why (not_assignable too) and reloads the case (#75 re-check)', async () => {
    const { api } = renderCockpit({ role: 'org_admin', stage: 'profile_complete' })
    await loaded()
    const loads = api.getScholarshipApplication.mock.calls.length
    const NA = 'admin.scholarship.assign.error.not_assignable'
    expect(screen.queryAllByText(NA)).toHaveLength(0)
    api.assignApplication.mockRejectedValue(Object.assign(new Error('not_assignable'), { code: 'not_assignable' }))
    fireEvent.change(assignPicker('assignTitle'), { target: { value: String(OTHER_ADMIN_ID) } })
    await waitFor(() => expect(api.getScholarshipApplication.mock.calls.length).toBe(loads + 1))
    // The page's one error slot, drawn under the profile and in the decision card: the words, nothing else.
    expect(screen.getAllByText(NA).map((el) => [el.tagName, el.textContent])).toEqual([['P', NA], ['P', NA]])
    expect(screen.queryByText('admin.scholarship.assignError')).toBeNull()
  })

  it('an assign that lands but whose reload fails never says it could not assign (#75 re-check 2)', async () => {
    const { api } = renderCockpit({ role: 'org_admin', stage: 'profile_complete' })
    await loaded()
    const loads = api.getScholarshipApplication.mock.calls.length
    api.assignApplication.mockResolvedValue({
      id: 7, status: 'assigned', assigned_to_id: OTHER_ADMIN_ID,
      assigned_to_name: 'Test Reviewer 05', assigned_at: '2026-11-07T00:00:00Z',
    })
    api.getScholarshipApplication.mockRejectedValue(new Error('network'))
    fireEvent.change(assignPicker('assignTitle'), { target: { value: String(OTHER_ADMIN_ID) } })
    expect((await screen.findAllByText('admin.scholarship.assign.reloadAfterAssign')).length).toBeGreaterThan(0)
    expect(api.getScholarshipApplication.mock.calls.length).toBe(loads + 1)   // reloaded once, not twice
    expect(screen.queryByText('admin.scholarship.assignError')).toBeNull()
  })

  it('is not offered to a reviewer, who cannot hand their own case on', async () => {
    renderCockpit({ role: 'reviewer', writes: true, stage: 'profile_complete' })
    await loaded()
    expect(screen.queryByText('admin.scholarship.assignTitle')).toBeNull()
    expect(screen.queryByText('admin.scholarship.assign.assignedTitle')).toBeNull()
  })

  it('locks once the decision is recorded — a finished case keeps its reviewer', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(assignPicker('assign.assignedTitle').disabled).toBe(true)
    expect(screen.getByText('admin.scholarship.assign.lockedHint')).toBeTruthy()
  })
})

describe('raising a query with the student', () => {
  it('sends what was written, and the question then appears in Outstanding', async () => {
    const { api } = renderCockpit({ role: 'super', writes: true, stage: 'shortlisted' })
    await loaded()
    const send = () => screen.getByRole('button',
      { name: 'admin.scholarship.raiseQuerySend' }) as HTMLButtonElement
    expect(send().disabled).toBe(true)

    fireEvent.change(screen.getByPlaceholderText('admin.scholarship.raiseQueryPlaceholder'),
                     { target: { value: 'Whose name is on the electricity bill?' } })
    expect(send().disabled).toBe(false)

    api.raiseResolutionItem.mockResolvedValue(buildApplicationDetail('shortlisted', {
      resolution_items: [{
        id: 901, fact: 'identity', code: 'officer_explanation', params: {},
        prompt: 'Whose name is on the electricity bill?', kind: 'explanation', doc_type: '',
        status: 'open', source: 'officer', resolution_text: '',
        created_at: '2026-06-01T09:00:00.000Z', resolved_at: null,
      }],
    }))
    fireEvent.click(send())
    expect(api.raiseResolutionItem).toHaveBeenCalledWith(
      7, { kind: 'explanation', prompt: 'Whose name is on the electricity bill?',
           fact: 'identity' },
      { token: 'test-token' })

    // The success state: the student-facing question the officer just wrote, on screen, and the
    // "nothing outstanding" line gone.
    expect(await screen.findByText('Whose name is on the electricity bill?')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.outstanding.empty')).toBeNull()
  })

  it('is closed once the interview is concluded, and says WHY', async () => {
    // The copy used to hard-code "the interview is concluded" on cases that never held one —
    // a terminal status locks querying too. `queryingLockReason` returns which it was.
    renderCockpit({ role: 'super', writes: true, stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(screen.queryByRole('button',
      { name: 'admin.scholarship.raiseQuerySend' })).toBeNull()
    expect(screen.getByText('admin.scholarship.outstanding.locked')).toBeTruthy()
  })
})

describe('reject before interview, refused because a colleague got there first (#75 re-check)', () => {
  it('a bad_status refusal stays in view after the reload takes the door away', async () => {
    const offer = { hold_hours: 24, reasons: ['not_b40'], note_max: 2000 }
    const { api, rerender } = renderCockpit({
      role: 'org_admin', stage: 'profile_complete', build: { pre_interview: offer } as never })
    await loaded()
    api.rejectBeforeInterview.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_status' }))
    api.getScholarshipApplication.mockResolvedValue(buildApplicationDetail('rejected', {
      rejection_category: 'pre_interview', rejection_reason: 'not_b40', pre_interview: undefined,
    } as never))
    const P = 'admin.scholarship.preInterview'
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fireEvent.change(screen.getByLabelText(`${P}.reasonLabel`), { target: { value: 'not_b40' } })
    fireEvent.change(screen.getByLabelText(`${P}.whyLabel`), { target: { value: 'Dummy note' } })
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    // The reload shows the colleague's decline, and the officer still reads why theirs was refused.
    expect(await screen.findByTestId('pre-interview-record')).toBeTruthy()
    expect(screen.queryByTestId('pre-interview')).toBeNull()
    expect(screen.getByTestId('pre-interview-refused').textContent).toBe(`${P}.error.bad_status`)
    // #75 re-check 2: the door went with the reload, so focus lands on the words that stayed.
    expect(document.activeElement).toBe(screen.getByTestId('pre-interview-refused'))

    // ⚠ prev/next changes the case WITHOUT a remount (TD-216): the next case never inherits it.
    api.getScholarshipApplication.mockResolvedValue(buildApplicationDetail('assigned', { id: 8 } as never))
    rerender(<AdminScholarshipDetailView applicationId={8} />)
    await waitFor(() => expect(api.getScholarshipApplication).toHaveBeenLastCalledWith(8, { token: 'test-token' }))
    expect(await screen.findByText('admin.scholarship.assign.assignedTitle')).toBeTruthy()
    expect(screen.queryByTestId('pre-interview-refused')).toBeNull()
  })
})

describe('a request still in flight when the officer presses Next (#75 re-check 3, TD-216 class)', () => {
  const P = 'admin.scholarship.preInterview'
  const offer = { hold_hours: 24, reasons: ['not_b40'], note_max: 2000 }
  const case8 = () => buildApplicationDetail('profile_complete', { id: 8, name: 'Test Student 08' } as never)
  /** Case 7 as a colleague left it: declined before interview, the door gone. */
  const case7Rejected = () => buildApplicationDetail('rejected', {
    rejection_category: 'pre_interview', rejection_reason: 'not_b40', pre_interview: undefined,
  } as never)

  /** Open case 7's reject, press "Yes, reject" with the reply held, then move to case 8. */
  const rejectThenNext = async () => {
    const view = renderCockpit({ role: 'org_admin', stage: 'profile_complete', build: { pre_interview: offer } as never })
    await loaded()
    const reply: { settle: (ok: boolean, v: unknown) => void } = { settle: () => {} }
    view.api.rejectBeforeInterview.mockReturnValue(new Promise((res, rej) => {
      reply.settle = (ok, v) => (ok ? res(v as never) : rej(v))
    }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fireEvent.change(screen.getByLabelText(`${P}.reasonLabel`), { target: { value: 'not_b40' } })
    fireEvent.change(screen.getByLabelText(`${P}.whyLabel`), { target: { value: 'Dummy note' } })
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    view.api.getScholarshipApplication.mockImplementation(async (id: number) => (id === 8 ? case8() : case7Rejected()))
    view.rerender(<AdminScholarshipDetailView applicationId={8} />)
    expect(await screen.findByText('Test Student 08')).toBeTruthy()
    return { ...view, reply }
  }
  /** Let a held reply land, and everything it sets off, inside `act`. */
  const land = (fn: () => void) => act(async () => { fn(); await new Promise((r) => setTimeout(r, 30)) })

  it('a reject refused after Next leaves case 8 on screen, with no refusal', async () => {
    const { api, reply } = await rejectThenNext()
    const loads = api.getScholarshipApplication.mock.calls.length
    await land(() => reply.settle(false, Object.assign(new Error('x'), { code: 'bad_status' })))
    // The stale refusal's reload reads the LIVE case, never the one the request was sent for.
    expect(api.getScholarshipApplication.mock.calls.length).toBe(loads + 1)
    expect(api.getScholarshipApplication).toHaveBeenLastCalledWith(8, { token: 'test-token' })
    expect(screen.getByText('Test Student 08')).toBeTruthy()
    expect(screen.queryByText('Test Student 07')).toBeNull()
    expect(screen.queryByTestId('pre-interview-record')).toBeNull()
    expect(screen.queryByTestId('pre-interview-refused')).toBeNull()
    expect(screen.queryByText(`${P}.error.bad_status`)).toBeNull()
  })

  it('a reject that succeeds after Next never puts case 7 on case 8', async () => {
    const { reply } = await rejectThenNext()
    await land(() => reply.settle(true, case7Rejected()))
    expect(screen.getByText('Test Student 08')).toBeTruthy()
    expect(screen.queryByText('Test Student 07')).toBeNull()
    expect(screen.queryByTestId('pre-interview-record')).toBeNull()
  })

  it('an assign still running when Next is pressed leaves case 8 untouched', async () => {
    const { api, rerender } = renderCockpit({ role: 'org_admin', stage: 'profile_complete' })
    await loaded()
    let refuse: (e: unknown) => void = () => {}
    api.assignApplication.mockReturnValue(new Promise((_, rej) => { refuse = rej }))
    const card = screen.getByText('admin.scholarship.assignTitle').closest('div') as HTMLElement
    fireEvent.change(within(card).getByRole('combobox'), { target: { value: String(OTHER_ADMIN_ID) } })
    api.getScholarshipApplication.mockImplementation(async (id: number) => (id === 8 ? case8()
      : buildApplicationDetail('assigned', { assigned_to_id: OTHER_ADMIN_ID, assigned_to_name: 'Test Reviewer 05' })))
    rerender(<AdminScholarshipDetailView applicationId={8} />)
    expect(await screen.findByText('Test Student 08')).toBeTruthy()
    await land(() => refuse(Object.assign(new Error('not_assignable'), { code: 'not_assignable' })))
    expect(api.getScholarshipApplication).toHaveBeenLastCalledWith(7, { token: 'test-token' })
    // Case 7's reload and its refusal both belong to case 7: case 8 keeps its own record and picker.
    expect(screen.getByText('Test Student 08')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.assign.assignedTitle')).toBeNull()
    expect(screen.getByText('admin.scholarship.assignTitle')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.assign.error.not_assignable')).toBeNull()
  })

  it('a refusal left standing never takes focus when a later reload moves the door away (L-a)', async () => {
    const { api } = renderCockpit({ role: 'org_admin', stage: 'profile_complete', build: { pre_interview: offer } as never })
    await loaded()
    api.rejectBeforeInterview.mockRejectedValue(Object.assign(new Error('x'), { code: 'boom' }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.start` }))
    fireEvent.change(screen.getByLabelText(`${P}.reasonLabel`), { target: { value: 'not_b40' } })
    fireEvent.change(screen.getByLabelText(`${P}.whyLabel`), { target: { value: 'Dummy note' } })
    fireEvent.click(screen.getByRole('button', { name: `${P}.submit` }))
    fireEvent.click(screen.getByRole('button', { name: `${P}.confirmYes` }))
    expect(await screen.findByText(`${P}.error.generic`)).toBeTruthy()   // the door stays; the words in it
    // Later, an assign's reload takes the door away: the old words may not steal focus.
    api.assignApplication.mockResolvedValue({ id: 7, status: 'assigned', assigned_to_id: OTHER_ADMIN_ID,
      assigned_to_name: 'Test Reviewer 05', assigned_at: '2026-11-07T00:00:00Z' })
    api.getScholarshipApplication.mockResolvedValue(buildApplicationDetail('assigned', {
      assigned_to_id: OTHER_ADMIN_ID, assigned_to_name: 'Test Reviewer 05', pre_interview: undefined } as never))
    const card = screen.getByText('admin.scholarship.assignTitle').closest('div') as HTMLElement
    fireEvent.change(within(card).getAllByRole('combobox')[0], { target: { value: String(OTHER_ADMIN_ID) } })
    expect(await screen.findByText('admin.scholarship.assign.assignedTitle')).toBeTruthy()
    // The words outlive the door (re-check), but focus stays where the officer left it.
    expect(document.activeElement).not.toBe(screen.getByTestId('pre-interview-refused'))
  })
})
