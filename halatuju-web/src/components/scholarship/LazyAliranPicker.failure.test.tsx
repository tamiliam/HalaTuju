/**
 * @jest-environment jsdom
 *
 * The PISMP school-type picker whose chunk cannot be fetched (apply gift clarity, 2026-10-05).
 * Said in place, with no half-drawn picker. Its own file: two hoisted mocks of one module cannot
 * share a file.
 */
import { render, screen } from '@testing-library/react'
import LazyAliranPicker from './LazyAliranPicker'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/AliranPicker', () => {
  throw new Error('ChunkLoadError: Loading chunk 6058 failed.')
})

it('says so in place, draws no picker, does not throw', async () => {
  render(<LazyAliranPicker alirans={['sk']} value="" onChange={() => {}} />)
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe('verifyEmail.networkError')   // an EXISTING string, no new copy
  expect(screen.queryByRole('radiogroup')).toBeNull()
})
