/**
 * @jest-environment jsdom
 *
 * TD-343: when the intake request fails the apply form says so and offers a retry, instead of
 * showing no gift in silence; a retry that succeeds names the gift.
 */
import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { useApplyGift } from '@/lib/useApplyGift'
import ApplyingTo from '@/components/scholarship/ApplyingTo'

const mockIntake = jest.fn()
jest.mock('@/lib/api', () => ({ getScholarshipIntake: (...a: unknown[]) => mockIntake(...a) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const OPEN = { open: true, cohort_name: 'BrightPath 2026', programme_code: 'bp', choices: [], apply_copy: {}, sources: [] }
const router = { replace: jest.fn() }

beforeEach(() => { mockIntake.mockReset(); sessionStorage.clear() })

it('a failed intake sets failed (and settles); retry asks again and names the gift', async () => {
  mockIntake.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(OPEN)
  const { result } = renderHook(() => useApplyGift(router))
  await waitFor(() => expect(result.current.settled).toBe(true))
  expect(result.current.failed).toBe(true)
  expect(result.current.name).toBe('')
  act(() => result.current.retry())
  await waitFor(() => expect(result.current.name).toBe('BrightPath 2026'))
  expect(result.current.failed).toBe(false)
  expect(result.current.code).toBe('bp')
})

it('the form line says it could not check, and Try again calls retry', () => {
  const retry = jest.fn()
  render(<ApplyingTo name="" failed onRetry={retry} />)
  expect(screen.getByTestId('apply-gift-failed').textContent).toContain('scholarship.apply.giftCheckFailed')
  fireEvent.click(screen.getByTestId('apply-gift-retry'))
  expect(retry).toHaveBeenCalledTimes(1)
})

it('draws nothing when there is no name and no failure', () => {
  const { container } = render(<ApplyingTo name="" />)
  expect(container.innerHTML).toBe('')
})
