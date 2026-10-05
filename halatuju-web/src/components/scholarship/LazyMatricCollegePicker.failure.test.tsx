/**
 * @jest-environment jsdom
 *
 * The matriculation college list that cannot be fetched (apply gift clarity, 2026-10-05) — a
 * student holding the apply form open across a deploy asks for a chunk hash that no longer exists.
 * Said in place, with no empty picker to search. Its own file: two hoisted mocks of one module
 * cannot share a file.
 */
import { render, screen } from '@testing-library/react'
import LazyMatricCollegePicker from './LazyMatricCollegePicker'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/data/matric-colleges', () => {
  throw new Error('ChunkLoadError: Loading chunk 6634 failed.')
})

it('says so in place, draws no picker, does not throw', async () => {
  render(<LazyMatricCollegePicker track="sains" value="" onChange={() => {}} placeholder="pick" />)
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe('verifyEmail.networkError')   // an EXISTING string, no new copy
  expect(screen.queryByPlaceholderText('pick')).toBeNull()
})
