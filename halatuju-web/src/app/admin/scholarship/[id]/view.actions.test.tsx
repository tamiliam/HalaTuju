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
import { fireEvent, screen, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit, OTHER_ADMIN_ID } from '@/test/renderCockpit'
import { buildApplicationDetail, buildDocument } from '@/test/adminApplicationDetail'

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
    renderCockpit({ role: 'super', stage: 'interviewing' })
    await loaded()
    expect(dateBox()).toBeTruthy()
  })

  it('is NOT offered once the letter carries a readable date', async () => {
    renderCockpit({ role: 'super', stage: 'interviewing',
                    build: { documents: letterWithDate() } })
    await loaded()
    expect(dateBox()).toBeNull()
  })

  it('⚠ A SUPERSEDED OFFER DOES NOT COUNT — the box comes back', async () => {
    // The value shown has to come from the CURRENT offer, or the screen and the column driving
    // the bursary can disagree (#120). A replaced letter is history, not the pathway.
    renderCockpit({ role: 'super', stage: 'interviewing',
                    build: { documents: letterWithDate({ superseded_at: '2026-05-20T09:00:00.000Z' }) } })
    await loaded()
    expect(dateBox()).toBeTruthy()
  })

  it.each(['shortlisted', 'profile_complete', 'awaiting_qc', 'recommended'] as const)(
    'is not offered at %s', async (stage) => {
      const roads = stage === 'awaiting_qc'
      renderCockpit({ role: 'super', stage,
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
      role: 'super', stage: 'awaiting_qc',
      build: { outcome: 'recommend', reporting_date: null,
               decision_reopened_at: '2026-06-03T09:00:00.000Z' },
    })
    await loaded()
    expect(dateBox()).toBeTruthy()
  })

  it('refuses to save an empty date, then sends the one that was typed', async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'interviewing',
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
})

describe('assigning a reviewer', () => {
  /** The assign card, found by its own heading rather than by being the Nth combobox — the page
   *  has several, and "the first one" is how a test quietly moves to another control. */
  const assignPicker = (headingKey: string) => {
    const card = screen.getByText(`admin.scholarship.${headingKey}`).closest('div') as HTMLElement
    return within(card).getByRole('combobox') as HTMLSelectElement
  }

  it('sends the chosen reviewer, and the card then names them', async () => {
    const { api } = renderCockpit({ role: 'org_admin', stage: 'profile_complete' })
    await loaded()
    const picker = assignPicker('assignTitle')
    expect(picker.value).toBe('')

    api.assignApplication.mockResolvedValue(buildApplicationDetail('assigned', {
      assigned_to_id: OTHER_ADMIN_ID, assigned_to_name: 'Test Reviewer 05',
    }))
    fireEvent.change(picker, { target: { value: String(OTHER_ADMIN_ID) } })
    expect(api.assignApplication).toHaveBeenCalledWith(7, OTHER_ADMIN_ID, { token: 'test-token' })

    // The success state: the heading flips from "assign one" to "assigned", and the picker
    // shows who holds the case — a write nobody can see is the BrightPath #20 shape.
    expect(await screen.findByText('admin.scholarship.assign.assignedTitle')).toBeTruthy()
    expect(assignPicker('assign.assignedTitle').value).toBe(String(OTHER_ADMIN_ID))
  })

  it('is not offered to a reviewer, who cannot hand their own case on', async () => {
    renderCockpit({ role: 'reviewer', stage: 'profile_complete' })
    await loaded()
    expect(screen.queryByText('admin.scholarship.assignTitle')).toBeNull()
    expect(screen.queryByText('admin.scholarship.assign.assignedTitle')).toBeNull()
  })

  it('locks once the decision is recorded — a finished case keeps its reviewer', async () => {
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(assignPicker('assign.assignedTitle').disabled).toBe(true)
    expect(screen.getByText('admin.scholarship.assign.lockedHint')).toBeTruthy()
  })
})

describe('raising a query with the student', () => {
  it('sends what was written, and the question then appears in Outstanding', async () => {
    const { api } = renderCockpit({ role: 'super', stage: 'shortlisted' })
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
    renderCockpit({ role: 'super', stage: 'awaiting_qc', build: { outcome: 'recommend' } })
    await loaded()
    expect(screen.queryByRole('button',
      { name: 'admin.scholarship.raiseQuerySend' })).toBeNull()
    expect(screen.getByText('admin.scholarship.outstanding.locked')).toBeTruthy()
  })
})
