/**
 * @jest-environment jsdom
 *
 * Sprint THANKS (owner 2026-11-16): the case page draws the graduation thank-you card for whoever holds the
 * `review` key (read from the served `page_keys`), and for nobody else. The role is only a label.
 */
import { screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { servedPageKeys } from '@/test/staffPresets'
import type { AdminGraduationMessage } from '@/lib/admin-api'

installCockpitConsoleGuard()

const MESSAGE: AdminGraduationMessage = {
  id: 5, application: 7, ref: 'HT-ABC123', status: 'pending', raw_text: 'Thank you for everything.',
  scrubbed_text: '', scan_result: [], approved_by: '', review_note: '',
  created_at: '2026-11-15T09:00:00+08:00', reviewed_at: null,
}

it('a review key holder sees the card with the waiting thank-you', async () => {
  expect(servedPageKeys('reviewer')).toContain('review')
  const { api, app } = renderCockpit({ role: 'reviewer', stage: 'awarded' })
  api.getCaseGraduationMessages.mockResolvedValue({ messages: [MESSAGE] })
  expect(await screen.findByText('admin.scholarship.graduationThanks.title')).toBeTruthy()
  expect(screen.getByRole('blockquote').textContent).toContain('Thank you for everything.')
  expect(api.getCaseGraduationMessages).toHaveBeenCalledWith(app.id, { token: 'test-token' })
})

it.each(['admin', 'org_admin', 'finance'] as const)('%s without the review key sees no card and asks for nothing', async (role) => {
  expect(servedPageKeys(role) ?? []).not.toContain('review')
  const { api } = renderCockpit({ role, stage: 'awarded' })
  api.getCaseGraduationMessages.mockResolvedValue({ messages: [MESSAGE] })
  await waitFor(() => expect(api.getScholarshipApplication).toHaveBeenCalled())
  await screen.findAllByText(/./)
  expect(api.getCaseGraduationMessages).not.toHaveBeenCalled()
  expect(screen.queryByText('admin.scholarship.graduationThanks.title')).toBeNull()
})
