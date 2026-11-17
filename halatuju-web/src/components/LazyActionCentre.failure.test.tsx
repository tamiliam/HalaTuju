/**
 * @jest-environment jsdom
 *
 * The Action Centre chunk that cannot be fetched (student-help bundle trim, 2026-11-17).
 *
 * A student holding a tab open across a deploy asks for a chunk hash that no longer exists. The
 * wrapper owns its `import()` so the failure is said in place, with no dead button, instead of a
 * whole-page error. Its own file because the module mock below throws for the whole file.
 */
import { render, screen } from '@testing-library/react'
import LazyActionCentre from './LazyActionCentre'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/ActionCentre', () => {
  throw new Error('ChunkLoadError: Loading chunk 6120 failed.')
})

it('says so in place, draws no button, does not throw', async () => {
  const { container } = render(<LazyActionCentre token="tok" />)
  const alert = await screen.findByRole('alert')
  // An EXISTING string, on purpose (as LazyPostAwardTask): no new words in any catalogue.
  expect(alert.textContent).toBe('verifyEmail.networkError')
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
  expect(screen.queryByRole('button')).toBeNull()
})
