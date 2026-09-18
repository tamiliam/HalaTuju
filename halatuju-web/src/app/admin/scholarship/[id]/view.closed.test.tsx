/**
 * @jest-environment jsdom
 *
 * THE OTHER END OF THE LIFECYCLE — a case that is off the review track for good.
 *
 * On 2026-08-18, 44 production records were found rendering a LIVE cockpit on a file nobody can
 * act on: a "Suggest interview questions" button (a billable Gemini call) on cases that never
 * held an interview, an editable justification and an Approve that would have stamped a verdict
 * and an award amount onto a rejected application, and a Check-2 box asserting "Nothing
 * outstanding — all student tasks are clear" on 43 records where nothing was ever asked.
 *
 * ⚠ THE RULE IS NOT "HIDE EVERYTHING ON A CLOSED CASE" — it is *hide a dead control, keep a
 * record*. A closed case that HOLDS an interview keeps the interview box; one that holds a
 * recorded verdict keeps the decision card, because that is the audit trail and it must survive.
 * Both halves are asserted below, because a test for only the first half would pass on a page
 * that deleted the evidence.
 *
 * ⚠ `closed` IS NOT A CLOSED CASE. `CASE_CLOSED_STATES` is `rejected` / `withdrawn` / `expired`
 * and deliberately excludes `closed`, which is the SUCCESSFUL end of a funded lifecycle — every
 * closed case carries a recorded verdict and keeps its decision record through that arm instead.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

/** The panel headings, which are the honest signal for "is this whole card on the page". */
const DECISION = 'admin.scholarship.decision.title'
const INTERVIEW = 'admin.scholarship.interview.title'

describe('an expired case — nothing was ever decided, so there is nothing to decide', () => {
  it('hides the decision and interview cards', async () => {
    // `expired` branches off `shortlisted`: the student never completed, the reminders lapsed and
    // the daily sweep closed the file. No verdict, no reviewer, no interview — so both cards are
    // pure dead control.
    renderCockpit({ role: 'super', stage: 'expired' })
    await loaded()
    expect(screen.queryByText(DECISION)).toBeNull()
    expect(screen.queryByText(INTERVIEW)).toBeNull()
  })

  it('offers no live control anywhere in the review panel', async () => {
    renderCockpit({ role: 'super', stage: 'expired' })
    await loaded()
    for (const key of ['recordVerdict.approve', 'recordVerdict.decline', 'recordVerdict.save',
                       'gaps.suggest', 'interview.submit']) {
      expect(screen.queryByRole('button', { name: `admin.scholarship.${key}` })).toBeNull()
    }
  })

  it('says nothing about the student having no outstanding tasks', async () => {
    // "Nothing outstanding — all student tasks are clear" reads as an achievement. On 43 of the
    // 44 records nothing was outstanding because nothing was ever asked, and one of them was
    // rejected over the college named on their offer letter.
    renderCockpit({ role: 'super', stage: 'expired' })
    await loaded()
    expect(screen.queryByText('admin.scholarship.outstanding.empty')).toBeNull()
  })

  it('but KEEPS a record that exists — a Check 2 box with items in it stays', async () => {
    // The mirror half. Hiding a record is a different mistake from hiding a dead control.
    renderCockpit({
      role: 'super', stage: 'expired',
      build: { resolution_items: [{
        id: 900, fact: 'identity', code: 'ic_missing', params: {},
        prompt: 'Please upload your own IC.', kind: 'doc', doc_type: 'ic', status: 'open',
        source: 'officer', resolution_text: '', created_at: '2026-05-01T09:00:00.000Z',
        resolved_at: null,
      }] },
    })
    await loaded()
    expect(screen.getByText('admin.scholarship.outstanding.title')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.outstanding.empty')).toBeNull()
  })
})

describe('a rejected case with no verdict — the org-admin reject', () => {
  /** An org-admin rejected a stuck `shortlisted` applicant: immediate, irreversible, and with a
   *  written reason that is never emailed, so this screen is its whole audit surface. */
  const orgRejected = {
    status: 'rejected', rejection_category: 'incomplete',
    rejection_comments: 'No documents were supplied after four reminders.',
    rejected_by: 'orgadmin@example.test', rejected_by_name: 'Test Organisation Admin 06',
    rejected_at: '2026-06-01T09:00:00.000Z',
    officer_verdict: {}, verdict_reason: '', verdict_decided_at: null, verdict_decided_by: '',
    verdict_decided_by_name: '', interview_session: null, reporting_date: null,
  }

  it('hides the decision and interview cards', async () => {
    renderCockpit({ role: 'super', stage: 'shortlisted', build: orgRejected })
    await loaded()
    expect(screen.queryByText(DECISION)).toBeNull()
    expect(screen.queryByText(INTERVIEW)).toBeNull()
  })

  it('shows the read-only record instead: the reason, who, and when', async () => {
    renderCockpit({ role: 'super', stage: 'shortlisted', build: orgRejected })
    await loaded()
    expect(screen.getByText('admin.scholarship.orgReject.recordTitle')).toBeTruthy()
    expect(screen.getByText('No documents were supplied after four reminders.')).toBeTruthy()
    // The name and the date on ONE line: the header carries a submitted date too, so a
    // page-wide date query would pass on the wrong element.
    expect(screen.getByText(/Test Organisation Admin 06/).textContent).toContain('01/06/2026')
  })

  it('offers no way to reject it a second time', async () => {
    // `ORG_REJECT_FROM` is `shortlisted` only; a card rendered outside it is a button that 400s.
    renderCockpit({ role: 'org_admin', stage: 'shortlisted', build: orgRejected })
    await loaded()
    expect(screen.queryByRole('button', { name: 'admin.scholarship.orgReject.start' })).toBeNull()
  })
})

describe('a rejected case WITH a verdict — the trail is the audit record and survives', () => {
  it('keeps the decision card and names BOTH people in order', async () => {
    // ⚠ A decline is a TWO-PERSON decision exactly like a recommend: the reviewer records it,
    // a QC upholds it. Rendering only "Declined by {rejected_by}" credited the whole decision to
    // the QC and erased the reviewer who interviewed the student (#56, owner 2026-07-25).
    renderCockpit({ role: 'super', stage: 'rejected' })
    await loaded()
    expect(screen.getByText(DECISION)).toBeTruthy()
    const trail = screen.getAllByText(/admin\.scholarship\.(interviewedDeclinedBy|recordVerdict\.declineAcceptedBy)/)
    expect(trail).toHaveLength(2)
    expect(trail[0].textContent).toContain('admin.scholarship.interviewedDeclinedBy')
    expect(trail[0].textContent).toContain('Test Reviewer 01')
    expect(trail[1].textContent).toContain('admin.scholarship.recordVerdict.declineAcceptedBy')
    expect(trail[1].textContent).toContain('Test Quality Officer 02')
  })

  it('shows the frozen justification, and no box to edit it in', async () => {
    renderCockpit({ role: 'super', stage: 'rejected' })
    await loaded()
    expect(screen.getByText('The evidence supports the conclusion recorded here.')).toBeTruthy()
    expect(screen.queryByPlaceholderText(
      'admin.scholarship.recordVerdict.reasonPlaceholder')).toBeNull()
    expect(screen.queryByRole('button',
      { name: 'admin.scholarship.recordVerdict.approve' })).toBeNull()
  })

  it('keeps the interview box, because the interview really happened', async () => {
    renderCockpit({ role: 'super', stage: 'rejected' })
    await loaded()
    expect(screen.getByText(INTERVIEW)).toBeTruthy()
  })
})
