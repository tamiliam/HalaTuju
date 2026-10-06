/**
 * @jest-environment jsdom
 *
 * The income-route switch loads on demand (TD-352, 2026-10-06): it arrives through the lazy
 * boundary with its props intact, and the Action Centre does not go back to a STATIC import
 * (the saving; `npm run bundle-budget` measures it, jest cannot). The failed-chunk case is the
 * sibling `.failure.test.tsx`.
 */
import { render, screen } from '@testing-library/react'
import { readWeb } from '@/test/sourceGuard'
import LazyIncomeRouteSwitch from './LazyIncomeRouteSwitch'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/IncomeRouteSwitch', () => ({
  __esModule: true,
  default: ({ applicationId, token }: { applicationId: number; token: string | null }) => (
    <div data-testid="route-switch">{applicationId}:{token}</div>
  ),
}))

it('draws nothing while the chunk is in the air, then the switch with its props', async () => {
  const onDone = jest.fn()
  const { container } = render(<LazyIncomeRouteSwitch token="tok" applicationId={42} onDone={onDone} />)
  expect(container.innerHTML).toBe('')
  expect((await screen.findByTestId('route-switch')).textContent).toBe('42:tok')
  expect(screen.queryByRole('alert')).toBeNull()
})

it('the Action Centre imports the LAZY switch and never the real one', () => {
  const centre = readWeb('src/components/ActionCentre.tsx',
    'the Action Centre — drawn on /scholarship/application, whose first-load budget this pays for')
  expect(centre).toContain("from '@/components/LazyIncomeRouteSwitch'")
  expect(centre).not.toMatch(/from\s+'@\/components\/IncomeRouteSwitch'/)
  const lazy = readWeb('src/components/LazyIncomeRouteSwitch.tsx', 'the lazy boundary itself')
  expect(lazy).toContain("import('./IncomeRouteSwitch')")
  expect(lazy).not.toMatch(/from\s+'next\/dynamic'/)
})
