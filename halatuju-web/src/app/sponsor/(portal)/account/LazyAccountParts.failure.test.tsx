/**
 * @jest-environment jsdom
 *
 * My Account's parts whose chunk cannot be fetched (size-fix review, 2026-11-23): said in place,
 * the page is not thrown away. Its own file because the module mocks below throw for the whole file.
 */
import { render, screen } from '@testing-library/react'
import { LazyInviteFriends, LazyGivingStatement } from './LazyAccountParts'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('./InviteFriends', () => { throw new Error('ChunkLoadError: Loading chunk 1 failed.') })
jest.mock('./GivingStatement', () => { throw new Error('ChunkLoadError: Loading chunk 2 failed.') })

it('each part says so in place and nothing throws', async () => {
  render(<><LazyInviteFriends /><LazyGivingStatement statement={{} as never} /></>)
  const alerts = await screen.findAllByRole('alert')
  expect(alerts).toHaveLength(2)
  for (const a of alerts) expect(a.textContent).toBe('sponsorPortal.partLoadFailed')
})
