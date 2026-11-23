/**
 * @jest-environment jsdom
 *
 * The Trust sections whose chunk cannot be fetched (size-fix review, 2026-11-23): said in place, the
 * page is not thrown away. Its own file because the module mock below throws for the whole file.
 */
import { render, screen } from '@testing-library/react'
import { LazyTrustView } from './LazyTrustView'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('./TrustView', () => { throw new Error('ChunkLoadError: Loading chunk 3 failed.') })

it('says so in place and does not throw', async () => {
  render(<LazyTrustView trust={{} as never} />)
  expect((await screen.findByRole('alert')).textContent).toBe('sponsorPortal.partLoadFailed')
})
