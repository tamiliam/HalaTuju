/**
 * @jest-environment jsdom
 *
 * LL sprint close (2026-11-19): the withdraw-award card loads as its own chunk, and only for a case
 * whose `withdrawal_request` carries a status or a step (the card's own render condition). Jest cannot
 * measure kilobytes (`npm run bundle-budget` does), so the import line is pinned too.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { readWeb } from '@/test/sourceGuard'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const REQUEST = {
  id: 7, status: 'pending' as const, your_step: null, requested_by_name: 'A Maker',
  requested_at: '2026-11-10T00:00:00Z', expires_at: '2026-11-24T00:00:00Z', explanation: 'Moved abroad',
}
const NONE = { id: null, status: null, your_step: null }

describe('the withdraw card arrives on demand', () => {
  it('a case WITH a withdraw request shows the card after the lazy load', async () => {
    renderCockpit({ role: 'admin', stage: 'awarded', build: { withdrawal_request: REQUEST } })
    await loaded()
    expect(await screen.findByTestId('withdrawal-outcome')).toBeTruthy()
  })

  it('a case WITHOUT one never mounts the wrapper (no loading line, no card)', async () => {
    renderCockpit({ role: 'admin', stage: 'awarded', build: { withdrawal_request: NONE } })
    await loaded()
    await Promise.resolve()
    expect(screen.queryByText('common.loading')).toBeNull()
    expect(screen.queryByTestId('withdrawal-outcome')).toBeNull()
    expect(screen.queryByTestId('withdrawal-pill')).toBeNull()
  })
})

describe('the saving is the import line', () => {
  it('the view imports the lazy wrapper and never the card', () => {
    const view = readWeb('src/app/admin/scholarship/[id]/view.tsx', 'the cockpit view whose first-load budget this pays for')
    expect(view).toContain("from './view/LazyWithdrawAwardCard'")
    expect(view).not.toMatch(/from\s+'\.\/view\/WithdrawAwardCard'/)
  })

  it('the wrapper owns a LITERAL import() of the card', () => {
    const lazy = readWeb('src/app/admin/scholarship/[id]/view/LazyWithdrawAwardCard.tsx', 'the lazy boundary itself')
    expect(lazy).toMatch(/import\('\.\/WithdrawAwardCard'\)/)
    expect(lazy).not.toMatch(/^import (?!type)[^\n]*'\.\/WithdrawAwardCard'/m)
  })
})
