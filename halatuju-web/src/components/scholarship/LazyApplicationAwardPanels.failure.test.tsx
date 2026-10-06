/**
 * @jest-environment jsdom
 *
 * The chunk that cannot be fetched (TD-352, 2026-10-06). A student holding a tab open across a
 * deploy asks for a chunk hash that no longer exists; the lazy boundary says so in place and the
 * rest of the page keeps working. Its own file: see `LazyInterviewBookingPanel.test.tsx`.
 */
import { render, screen } from '@testing-library/react'
import type { StudentAward } from '@/lib/api'
import LazyApplicationAwardPanels from './LazyApplicationAwardPanels'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('./ApplicationAwardPanels', () => {
  throw new Error('ChunkLoadError: Loading chunk 9046 failed.')
})

it('says so in place, draws no panel, and does not throw', async () => {
  const { container } = render(
    <LazyApplicationAwardPanels award={{ status: 'offered' } as unknown as StudentAward}
      acceptanceEnabled bursary={null} status="recommended" onboardedAt={null} />)
  const alert = await screen.findByRole('alert')
  // An EXISTING string, on purpose: a new sentence would be new weight in every catalogue.
  expect(alert.textContent).toBe('verifyEmail.networkError')
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
})
