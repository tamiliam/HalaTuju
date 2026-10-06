/**
 * @jest-environment jsdom
 *
 * The chunk that cannot be fetched (TD-352, 2026-10-06): said in place, nothing thrown. Its own
 * file: see `scholarship/LazyInterviewBookingPanel.test.tsx`.
 */
import { render, screen } from '@testing-library/react'
import LazyIncomeRouteSwitch from './LazyIncomeRouteSwitch'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('./IncomeRouteSwitch', () => {
  throw new Error('ChunkLoadError: Loading chunk 9046 failed.')
})

it('says so in place, draws no switch, and does not throw', async () => {
  const { container } = render(<LazyIncomeRouteSwitch token="tok" applicationId={42} onDone={jest.fn()} />)
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe('verifyEmail.networkError')
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
})
