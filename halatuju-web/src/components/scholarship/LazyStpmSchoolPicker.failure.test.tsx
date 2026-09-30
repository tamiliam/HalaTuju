/**
 * @jest-environment jsdom
 *
 * The Form 6 centre list that cannot be fetched (TD-309 follow-up, 2026-09-30) — a student holding
 * the apply form open across a deploy asks for a chunk hash that no longer exists. The failure is
 * said in place, with no empty picker to search, and the rest of the form keeps working.
 * Its own file: two hoisted mocks of one module cannot share a file.
 */
import { render, screen } from '@testing-library/react'
import LazyStpmSchoolPicker from './LazyStpmSchoolPicker'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/data/stpm-schools', () => {
  throw new Error('ChunkLoadError: Loading chunk 3650 failed.')
})

it('says so in place, draws no picker, does not throw', async () => {
  const { container } = render(
    <LazyStpmSchoolPicker stream="sains" value="" onChange={() => {}} placeholder="pick" />)
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe('verifyEmail.networkError')   // an EXISTING string, no new copy
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
  expect(screen.queryByPlaceholderText('pick')).toBeNull()
})
