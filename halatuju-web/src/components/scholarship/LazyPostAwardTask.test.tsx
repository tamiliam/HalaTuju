/**
 * @jest-environment jsdom
 *
 * The Action Centre's post-award cards load on demand (TD-306 follow-up, 2026-09-30).
 *
 * Three facts, each of which a later "tidy-up" could quietly undo:
 *   1. each card still ARRIVES through the lazy boundary, with its props intact (this file);
 *   2. a chunk that cannot be fetched says so IN PLACE and does not throw — see the sibling
 *      `LazyPostAwardTask.failure.test.tsx` (its own file for the reason given in
 *      `LazyInterviewBookingPanel.test.tsx`: two hoisted mocks of one module);
 *   3. ActionCentre does not go back to a STATIC import, which is the whole saving
 *      (275,447 -> 272,750 gz bytes on `/scholarship/application`, the route the deploy gate
 *      refused at 276 kB). Jest cannot measure kilobytes — `npm run bundle-budget` does, in the
 *      deploy gate — so this pins the import lines instead.
 */
import { render, screen } from '@testing-library/react'
import { readWeb } from '@/test/sourceGuard'
import LazyPostAwardTask from './LazyPostAwardTask'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/scholarship/PostAwardTasks', () => ({
  __esModule: true,
  BankDetailsTask: ({ item, token }: { item: ResolutionItem; token: string | null }) => (
    <div data-testid="bank-task">{item.id}:{token}</div>
  ),
  VircleTask: ({ item, token, contactPhone }: {
    item: ResolutionItem; token: string | null; contactPhone: string
  }) => (
    <div data-testid="vircle-task">{item.id}:{token}:{contactPhone}</div>
  ),
}))

const ITEM = { id: 9 } as ResolutionItem

describe('the post-award cards arrive on demand', () => {
  it('bank: draws nothing while the chunk is in the air, then the card with its props', async () => {
    const { container } = render(
      <LazyPostAwardTask kind="bank" item={ITEM} token="tok" onResolved={() => {}} />)
    // Mid-flight: nothing, and in particular no button a student could press into a void.
    expect(container.innerHTML).toBe('')
    expect((await screen.findByTestId('bank-task')).textContent).toBe('9:tok')
    expect(screen.queryByTestId('vircle-task')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('vircle: draws nothing while the chunk is in the air, then the card with its props', async () => {
    const { container } = render(
      <LazyPostAwardTask kind="vircle" item={ITEM} token="tok" contactPhone="0123456789"
        onResolved={() => {}} />)
    expect(container.innerHTML).toBe('')
    expect((await screen.findByTestId('vircle-task')).textContent).toBe('9:tok:0123456789')
    expect(screen.queryByTestId('bank-task')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('the saving is the import line', () => {
  it('ActionCentre reaches the cards only through the LAZY boundary', () => {
    const centre = readWeb('src/components/ActionCentre.tsx',
      'the Action Centre — first-load JS of /scholarship/application, which this boundary pays for')
    expect(centre).toContain("from '@/components/scholarship/LazyPostAwardTask'")
    expect(centre).not.toMatch(/from\s+'@\/components\/scholarship\/PostAwardTasks'/)
    expect(centre).not.toMatch(/function\s+(BankDetailsTask|VircleTask)\b/)
    expect(centre).not.toMatch(/from\s+'@\/lib\/(sponsorAuth|vircleAccount)'/)
  })

  it('the lazy module owns a LITERAL import() of the cards — a variable specifier emits no chunk', () => {
    const lazy = readWeb('src/components/scholarship/LazyPostAwardTask.tsx',
      'the lazy boundary itself')
    expect(lazy).toContain("import('@/components/scholarship/PostAwardTasks')")
    expect(lazy).not.toMatch(/from\s+'next\/dynamic'/)
    expect(lazy).not.toMatch(/from\s+'@\/components\/scholarship\/PostAwardTasks'/)
  })
})
