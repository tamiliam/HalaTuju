/**
 * @jest-environment jsdom
 *
 * The cockpit reads the case once per (token, id) — audit A3.15.
 *
 * The load effect needs the CURRENT interview / verdict / post-award handlers and `t`, all of which
 * are new objects every render. It used to carry a lint suppression to avoid listing them; it now
 * reads them through a ref. Pinned: a re-render caused by typing in the page (which hands every
 * hook a fresh object) does not read the case, the reviewers list or the case summary again.
 */
import { fireEvent, screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

it('a re-render does not re-read the case', async () => {
  const { api } = renderCockpit({ role: 'super', stage: 'profile_complete',
                                  build: { officer_requests: 'open' } })
  await screen.findByText('Test Student 07')
  const reads = () => [
    api.getScholarshipApplication.mock.calls.length,
    api.getAssignableAdmins.mock.calls.length,
    api.getVerdictCaseSummary.mock.calls.length,
  ]
  const before = reads()
  expect(before[0]).toBe(1)
  // State changes in the page: every hook object is rebuilt on the render that follows.
  fireEvent.change(screen.getByPlaceholderText('admin.scholarship.raiseQueryPlaceholder'),
                   { target: { value: 'Whose bill is this?' } })
  fireEvent.change(screen.getByPlaceholderText('admin.scholarship.raiseQueryPlaceholder'),
                   { target: { value: 'Whose bill is this? Please say.' } })
  expect(reads()).toEqual(before)
})
