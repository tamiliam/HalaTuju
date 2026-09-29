/**
 * @jest-environment jsdom
 *
 * The post-award chunk that cannot be fetched (TD-306 follow-up, 2026-09-30).
 *
 * A funded student holding a tab open across a deploy asks for a chunk hash that no longer
 * exists. `next/dynamic` would RE-THROW that and put a whole-page error where one card should
 * be; the lazy boundary owns its `import()` so the failure is said in place, with no dead button,
 * and the rest of the Action Centre keeps working.
 *
 * Its own file: see the note at the top of `LazyPostAwardTask.test.tsx`.
 */
import { render, screen } from '@testing-library/react'
import LazyPostAwardTask from './LazyPostAwardTask'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/scholarship/PostAwardTasks', () => {
  throw new Error('ChunkLoadError: Loading chunk 6120 failed.')
})

it.each(['bank', 'vircle'] as const)('%s: says so in place, draws no card and no button, does not throw', async (kind) => {
  const props = { item: { id: 9 } as ResolutionItem, token: 'tok', onResolved: () => {} }
  const { container } = render(kind === 'bank'
    ? <LazyPostAwardTask kind="bank" {...props} />
    : <LazyPostAwardTask kind="vircle" contactPhone="0123456789" {...props} />)
  const alert = await screen.findByRole('alert')
  // An EXISTING string, on purpose (as LazyInterviewBookingPanel): a failed chunk load is a
  // network error, and a new sentence would be new weight in every catalogue and new Tamil.
  expect(alert.textContent).toBe('verifyEmail.networkError')
  expect(container.querySelectorAll('[role="alert"]')).toHaveLength(1)
  expect(screen.queryByRole('button')).toBeNull()
})
