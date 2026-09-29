/**
 * @jest-environment jsdom
 *
 * TD-302 (2026-09-29) — where the crumb's "All gifts" may NOT appear. The two pages that offer it
 * (Applications, Overview) and the three list pages that must not (Payments, Spending,
 * Configuration) are pinned in their own `page.url.test.tsx`; this file holds the cases no list
 * page can reach: a DETAIL page that has pinned its record's gift, and a single-gift tenant.
 */
import { render, screen, waitFor } from '@testing-library/react'

import { usePinProgramme } from '@/lib/programmeScopeCore'
import { GiftScope, TWO_GIFTS, crumbSwitch, crumbText } from '@/test/giftScope'
import { crumbOffersAll, openAt, switchCrumbTo } from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

function OnARecord() {
  usePinProgramme({ code: 'bpb-sabah-2026', name: 'Sabah Bursary 2026' })
  return null
}

afterEach(() => openAt('/'))

describe('a pinned detail page: the crumb names the gift, with no switch and no "All gifts"', () => {
  it.each([
    ['an applicant', '/admin/scholarship/7'],
    ['a payment run', '/admin/payments/3'],
  ])('%s', async (_what, path) => {
    openAt(path)
    render(<GiftScope><OnARecord /></GiftScope>)
    await waitFor(() => expect(crumbText()).toContain('Sabah Bursary 2026'))
    expect(crumbSwitch()).toBeNull()
    expect(screen.queryByRole('menuitem', { name: 'admin.shell.allGifts' })).toBeNull()
  })
})

describe('a single-gift tenant: never offered — "no gift" resolves straight back to the only one', () => {
  it.each(['/admin/scholarship', '/admin/programme/overview'])('%s', (path) => {
    openAt(path)
    render(<GiftScope choices={[TWO_GIFTS[0]]} />)
    expect(crumbText()).toContain('Flagship Bursary')
    expect(crumbSwitch()).toBeNull()
  })
})

describe('the rule is the PAGE, not the scope: exact paths only', () => {
  it.each([
    ['/admin/scholarship', true],
    ['/admin/programme/overview', true],
    ['/admin/programme', false],
    ['/admin/payments', false],
    ['/admin/spending', false],
    ['/admin/scholarship/7', false],
  ])('%s offers it: %s', (path, offered) => {
    openAt(path)
    render(<GiftScope />)
    switchCrumbTo('Sabah Bursary 2026')
    expect(crumbOffersAll()).toBe(offered)
  })
})
