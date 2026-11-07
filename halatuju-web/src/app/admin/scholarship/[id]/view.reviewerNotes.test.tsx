/**
 * @jest-environment jsdom
 *
 * Request #55 (2026-11-07): the cockpit draws "Notes for the reviewer" directly UNDER "Reviewer
 * assigned" for the org admin, and the assigned reviewer reads the same notes (no box).
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const P = 'admin.scholarship.reviewerNotes'
const NOTES = {
  notes: [{ id: 1, body: 'Please ask about the older brother.', author_name: 'Org Admin One',
    created_at: '2026-11-05T10:42:00+08:00' }],
  window_open: true, max_length: 2000,
}

it('sits directly under Reviewer assigned, with the box, for the org admin', async () => {
  const { api } = renderCockpit({ role: 'org_admin', stage: 'interviewing' })
  api.getReviewerNotes.mockResolvedValue({ ...NOTES, can_add: true })
  const note = await screen.findByText('Please ask about the older brother.')
  const assigned = screen.getByText('admin.scholarship.assign.assignedTitle')
  const assignedCard = assigned.closest('div') as HTMLElement
  const notesCard = note.closest('[data-reviewer-notes]') as HTMLElement
  expect(assignedCard.nextElementSibling).toBe(notesCard)
  expect(screen.getByLabelText(`${P}.addLabel`)).toBeTruthy()
  expect(api.getReviewerNotes).toHaveBeenCalledWith(expect.any(Number), { token: 'test-token' })
})

it('the assigned reviewer reads the notes, with no box', async () => {
  const { api } = renderCockpit({ role: 'reviewer', stage: 'interviewing' })
  api.getReviewerNotes.mockResolvedValue({ ...NOTES, can_add: false })
  expect(await screen.findByText('Please ask about the older brother.')).toBeTruthy()
  expect(screen.getByText(`${P}.introReader`)).toBeTruthy()
  expect(screen.queryByLabelText(`${P}.addLabel`)).toBeNull()
})
