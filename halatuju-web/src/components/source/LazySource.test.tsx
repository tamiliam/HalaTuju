/**
 * @jest-environment jsdom
 *
 * `lazySource` options (size-fix review, 2026-11-23): `quiet` draws nothing while loading;
 * a failed load says the admin words. The default still shows the loading line.
 */
import { render, screen } from '@testing-library/react'
import { lazySource } from './LazySource'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const Part = () => <p>part</p>

it('default: shows the loading line first, then the part', async () => {
  const L = lazySource(() => Promise.resolve(Part))
  render(<L />)
  expect(screen.getByText('common.loading')).toBeTruthy()
  expect(await screen.findByText('part')).toBeTruthy()
})

it('quiet: draws nothing while the chunk is in the air, then the part', async () => {
  const L = lazySource(() => Promise.resolve(Part), { quiet: true })
  const { container } = render(<L />)
  expect(container.textContent).toBe('')
  expect(screen.queryByText('common.loading')).toBeNull()
  expect(await screen.findByText('part')).toBeTruthy()
})

it('failure: says the admin words in place', async () => {
  const L = lazySource(() => Promise.reject(new Error('ChunkLoadError')), { quiet: true })
  render(<L />)
  expect((await screen.findByRole('alert')).textContent).toBe('admin.sourceConsole.loadFailed')
})
