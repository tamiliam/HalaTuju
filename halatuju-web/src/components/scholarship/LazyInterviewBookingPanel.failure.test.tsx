/**
 * @jest-environment jsdom
 *
 * The chunk that cannot be fetched (audit follow-up, 2026-09-21).
 *
 * A student holding a tab open across a deploy asks for a chunk hash that no longer exists.
 * `next/dynamic` RE-THROWS that failure — its `loading` prop never sees it — which would put a
 * whole-page error where an interview booking panel should be. The lazy boundary owns its
 * `import()` so the failure is said in place and the rest of the page keeps working.
 *
 * Its own file: see the note at the top of `LazyInterviewBookingPanel.test.tsx`.
 */
import { render, screen } from '@testing-library/react'
import LazyInterviewBookingPanel from './LazyInterviewBookingPanel'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/scholarship/InterviewBookingPanel', () => {
  throw new Error('ChunkLoadError: Loading chunk 9046 failed.')
})

it('says so in place, draws no panel, and does not throw', async () => {
  const { container } = render(<LazyInterviewBookingPanel applicationId={42} token="tok" />)
  const alert = await screen.findByRole('alert')
  // An EXISTING string, on purpose: a failed chunk load is a network error, and a new sentence
  // would be new weight in every catalogue and new Tamil for the owner to check.
  expect(alert.textContent).toBe('verifyEmail.networkError')
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
})
