/**
 * @jest-environment jsdom
 *
 * Configuration — the URL carries the gift (TD-296, 2026-09-28).
 *
 * The page already read `?tab=` once on mount; `?programme=` now rides beside it. The two must not
 * disturb each other: a gift card's "open settings" and the create flow land here with both, and a
 * switch in the crumb rewrites the gift while keeping the tab. The tabs themselves are stubbed —
 * what they do with a gift is theirs, and unchanged (their inline question stays, by decision).
 */
import { render, screen, waitFor } from '@testing-library/react'

import AdminProgrammeConfigPage from './page'
import { GiftScope, TWO_GIFTS, scopeChosen } from '@/test/giftScope'
import { address, openAt, switchCrumbTo, urlRouter } from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/components/admin/IntakeYearTab', () => function YearTab() { return <div>year-tab</div> })
jest.mock('@/components/admin/ProgrammeRulesTab', () => function RulesTab() { return <div>rules-tab</div> })
jest.mock('@/components/admin/ProgrammeConfigTab', () => function ConfigTab() { return <div>config-tab</div> })
jest.mock('@/components/admin/ApplyCopyTab', () => function CopyTab() { return <div>copy-tab</div> })

const SABAH = 'bpb-sabah-2026'

beforeEach(() => { jest.clearAllMocks(); openAt('/admin/programme') })

it('opens on the named tab AND in the named gift', async () => {
  openAt(`/admin/programme?tab=rules&programme=${SABAH}`)
  render(<GiftScope><AdminProgrammeConfigPage /></GiftScope>)
  await waitFor(() => expect(scopeChosen()).toBe(SABAH))
  expect(screen.getByTestId('tab-rules').getAttribute('aria-selected')).toBe('true')
  expect(urlRouter.replace).not.toHaveBeenCalled()
})

it('a switch in the crumb rewrites the gift and keeps the tab — in place', async () => {
  openAt(`/admin/programme?tab=rules&programme=${SABAH}`)
  render(<GiftScope><AdminProgrammeConfigPage /></GiftScope>)
  await waitFor(() => expect(scopeChosen()).toBe(SABAH))
  switchCrumbTo('Flagship Bursary')
  await waitFor(() => expect(address()).toBe('/admin/programme?tab=rules&programme=brightpath-flagship'))
  expect(urlRouter.push).not.toHaveBeenCalled()
})

it('an unknown gift selects nothing — the tabs ask, as they always have', async () => {
  openAt('/admin/programme?programme=not-a-gift')
  render(<GiftScope choices={[TWO_GIFTS[0]]}><AdminProgrammeConfigPage /></GiftScope>)
  await waitFor(() => expect(scopeChosen()).toBe('(none)'))
})
