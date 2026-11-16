/**
 * @jest-environment jsdom
 *
 * Request #55 (2026-11-07): the cockpit draws the notes card directly UNDER "Reviewer assigned" for the
 * org admin. Since request #73 (2026-11-16) it is "Org admin and reviewer notes" and the assigned reviewer
 * REPLIES in it (the served `viewer` picks the face).
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const P = 'admin.scholarship.reviewerNotes'
const NOTES = {
  notes: [{ id: 1, body: 'Please ask about the older brother.', author_name: 'Org Admin One',
    author_role: 'org_admin' as const, is_you: false, created_at: '2026-11-05T10:42:00+08:00' }],
  window_open: true, reason: null, max_length: 2000,
}

it('sits directly under Reviewer assigned, with the box, for the org admin', async () => {
  const { api } = renderCockpit({ role: 'org_admin', writes: true, stage: 'interviewing' })
  api.getReviewerNotes.mockResolvedValue({ ...NOTES, viewer: 'org_admin', can_add: true })
  const note = await screen.findByText('Please ask about the older brother.')
  const assigned = screen.getByText('admin.scholarship.assign.assignedTitle')
  const assignedCard = assigned.closest('div') as HTMLElement
  const notesCard = note.closest('[data-reviewer-notes]') as HTMLElement
  expect(assignedCard.nextElementSibling).toBe(notesCard)
  expect(screen.getByLabelText(`${P}.addLabel`)).toBeTruthy()
  expect(api.getReviewerNotes).toHaveBeenCalledWith(expect.any(Number), { token: 'test-token' })
})

it('the assigned reviewer reads the notes and gets the Reply box (#73)', async () => {
  const { api } = renderCockpit({ role: 'reviewer', writes: true, stage: 'interviewing' })
  api.getReviewerNotes.mockResolvedValue({ ...NOTES, viewer: 'reviewer', can_add: true })
  expect(await screen.findByText('Please ask about the older brother.')).toBeTruthy()
  expect(screen.getByText(`${P}.introReviewer`)).toBeTruthy()
  expect(screen.getByLabelText(`${P}.replyLabel`)).toBeTruthy()
  expect(screen.getByRole('button', { name: `${P}.sendReply` })).toBeTruthy()
  expect(screen.queryByLabelText(`${P}.addLabel`)).toBeNull()
})

it('QC reads the notes, with no box', async () => {
  const { api } = renderCockpit({ role: 'qc', stage: 'interviewing' })
  api.getReviewerNotes.mockResolvedValue({ ...NOTES, viewer: 'reader', can_add: false })
  expect(await screen.findByText('Please ask about the older brother.')).toBeTruthy()
  expect(screen.getByText(`${P}.introReader`)).toBeTruthy()
  expect(screen.queryByRole('textbox', { name: `${P}.addLabel` })).toBeNull()
})
