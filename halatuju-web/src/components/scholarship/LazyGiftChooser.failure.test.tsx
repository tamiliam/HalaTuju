/**
 * @jest-environment jsdom
 *
 * The gift chooser's chunk that cannot be fetched (apply gift clarity, 2026-10-05) — a student
 * holding the apply page open across a deploy asks for a chunk hash that no longer exists. The
 * failure is said in place, with no half-drawn chooser. Its own file: two hoisted mocks of one
 * module cannot share a file. The success path is exercised by `apply/page.gift.test.tsx`.
 */
import { render, screen } from '@testing-library/react'
import LazyGiftChooser from './LazyGiftChooser'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('./GiftChooser', () => {
  throw new Error('ChunkLoadError: Loading chunk 4120 failed.')
})

it('says so in place, draws no chooser, does not throw', async () => {
  render(<LazyGiftChooser choices={[{ code: 'a', name: 'A' }, { code: 'b', name: 'B' }]} onPick={() => {}} />)
  const alert = await screen.findByRole('alert')
  expect(alert.textContent).toBe('verifyEmail.networkError')   // an EXISTING string, no new copy
  expect(screen.queryByText('scholarship.apply.chooseTitle')).toBeNull()
})
