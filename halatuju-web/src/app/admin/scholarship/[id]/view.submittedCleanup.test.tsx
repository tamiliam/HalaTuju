/**
 * @jest-environment jsdom
 *
 * Owner 2026-11-19: the pre-submission cleanup also covers 'submitted' (the first status). Dead cards
 * (Rate AI Prediction, funding projection, "Assign a reviewer", the notes card) are hidden at
 * submitted and shortlisted; the cards that still work stay.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'

import { buildApplicationDetail } from '@/test/adminApplicationDetail'
import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

describe.each(['submitted', 'shortlisted'] as const)('at %s', (stage) => {
  it('hides the dead cards: rate, projection, assign a reviewer, notes', async () => {
    const { api } = renderCockpit({ role: 'org_admin', writes: true, stage })
    await loaded()
    expect(screen.queryByText('admin.scholarship.recordVerdict.rateTitle')).toBeNull()
    expect(screen.queryByText('admin.scholarship.estimate.title')).toBeNull()
    expect(screen.queryByText('admin.scholarship.assignTitle')).toBeNull()
    expect(document.querySelector('[data-reviewer-notes]')).toBeNull()
    expect(api.getReviewerNotes).not.toHaveBeenCalled()
  })
})

describe('F1 / I-6: Documents and AI Prediction boxes', () => {
  it('are hidden at submitted', async () => {
    renderCockpit({ role: 'org_admin', writes: true, stage: 'submitted' })
    await loaded()
    expect(screen.queryByText('admin.scholarship.verdict.title')).toBeNull()
    expect(screen.queryByText(/admin\.scholarship\.docsDrawer\.title/)).toBeNull()
  })

  it('stay at shortlisted', async () => {
    renderCockpit({ role: 'org_admin', writes: true, stage: 'shortlisted' })
    await loaded()
    expect(screen.getByText('admin.scholarship.verdict.title')).toBeTruthy()
    expect(screen.getByText(/admin\.scholarship\.docsDrawer\.title/)).toBeTruthy()
  })
})

describe('F1 / I-7: the student note, one rule at every stage', () => {
  it.each(['shortlisted', 'interviewing', 'recommended'] as const)('shows at %s when it has text', async (stage) => {
    renderCockpit({ role: 'org_admin', writes: true, stage, build: { uncertainty_note: 'Dummy note' } as never })
    await loaded()
    expect(screen.getByText('Dummy note')).toBeTruthy()
  })

  it('shows on an engine-rejected case, where the review panel is hidden', async () => {
    renderCockpit({
      role: 'org_admin', writes: true, stage: 'shortlisted',
      build: { status: 'rejected', rejection_category: 'merit', uncertainty_note: 'Dummy note' } as never,
    })
    await loaded()
    expect(screen.getByText('Dummy note')).toBeTruthy()
  })

  it('is hidden when empty', async () => {
    renderCockpit({
      role: 'org_admin', writes: true, stage: 'interviewing',
      build: { uncertainty_note: '', anything_else: '' } as never,
    })
    await loaded()
    expect(screen.queryByText('admin.scholarship.studentNote')).toBeNull()
    expect(screen.queryByText('Dummy note')).toBeNull()
  })
})

it('submitted keeps the Close the file card', async () => {
  renderCockpit({ role: 'org_admin', writes: { can_write: true, can_close_pre_award: true }, stage: 'submitted' })
  await loaded()
  expect(screen.getByText('admin.closure.title')).toBeTruthy()
})

const NOTES_OPEN = {
  notes: [], window_open: true, reason: null, max_length: 2000, viewer: 'org_admin' as const, can_add: true,
}
const INTERVIEW = 'admin.scholarship.interview.title'
const ESTIMATE = 'admin.scholarship.estimate.title'
const decision = () => document.getElementById('decision-section')
const hiddenWhileWaiting = () => {
  expect(screen.queryByText(INTERVIEW)).toBeNull()
  expect(screen.queryByText(ESTIMATE)).toBeNull()
  expect(decision()).toBeNull()
  expect(document.querySelector('[data-reviewer-notes]')).toBeNull()
}

describe('Awaiting review with no reviewer assigned (isWaitingForReviewer)', () => {
  it('hides Interview Stage, Estimated need, Recommendation and the notes; keeps the assign card', async () => {
    const { api } = renderCockpit({ role: 'org_admin', writes: true, stage: 'profile_complete' })
    api.getReviewerNotes.mockResolvedValue(NOTES_OPEN)
    await loaded()
    hiddenWhileWaiting()
    expect(api.getReviewerNotes).not.toHaveBeenCalled()
    expect(screen.getByText('admin.scholarship.assignTitle')).toBeTruthy()
  })

  it('a reviewer assigned: all four show', async () => {
    const { api } = renderCockpit({ role: 'org_admin', writes: true, stage: 'assigned' })
    api.getReviewerNotes.mockResolvedValue(NOTES_OPEN)
    await loaded()
    expect(screen.getByText(INTERVIEW)).toBeTruthy()
    expect(decision()).toBeTruthy()
    await waitFor(() => expect(document.querySelector('[data-reviewer-notes]')).toBeTruthy())
  })

  it('a reopened decision shows them even with nobody assigned', async () => {
    const { api } = renderCockpit({
      role: 'org_admin', writes: true, stage: 'profile_complete',
      build: { decision_reopened_at: '2026-11-18T00:00:00Z' } as never,
    })
    api.getReviewerNotes.mockResolvedValue(NOTES_OPEN)
    await loaded()
    expect(screen.getByText(INTERVIEW)).toBeTruthy()
    expect(decision()).toBeTruthy()
  })

  it('they APPEAR right after a successful assign, on the same page, with no reload', async () => {
    const { api } = renderCockpit({ role: 'org_admin', writes: true, stage: 'profile_complete' })
    api.getReviewerNotes.mockResolvedValue(NOTES_OPEN)
    await loaded()
    hiddenWhileWaiting()
    api.assignApplication.mockResolvedValue({
      id: 7, status: 'assigned', assigned_to_id: 42, assigned_to_name: 'Test Reviewer 05', assigned_at: '2026-11-07T00:00:00Z',
    })
    api.getScholarshipApplication.mockResolvedValue(buildApplicationDetail('assigned', {
      assigned_to_id: 42, assigned_to_name: 'Test Reviewer 05',
    }))
    const card = screen.getByText('admin.scholarship.assignTitle').closest('div') as HTMLElement
    fireEvent.change(within(card).getByRole('combobox'), { target: { value: '42' } })
    expect(await screen.findByText(INTERVIEW)).toBeTruthy()
    expect(decision()).toBeTruthy()
    await waitFor(() => expect(document.querySelector('[data-reviewer-notes]')).toBeTruthy())
  })
})

describe('Check 2 - Outstanding box', () => {
  it.each(['submitted', 'shortlisted'] as const)('is hidden at %s with no items', async (stage) => {
    renderCockpit({ role: 'super', writes: true, stage })
    await loaded()
    expect(screen.queryByText('admin.scholarship.raiseQuerySend')).toBeNull()
    expect(screen.queryByRole('button', { name: 'admin.scholarship.raiseQuerySend' })).toBeNull()
  })

  it('is still there at profile_complete', async () => {
    renderCockpit({ role: 'super', writes: true, stage: 'profile_complete' })
    await loaded()
    expect(screen.getByRole('button', { name: 'admin.scholarship.raiseQuerySend' })).toBeTruthy()
  })
})
