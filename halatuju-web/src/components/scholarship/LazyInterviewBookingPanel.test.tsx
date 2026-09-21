/**
 * @jest-environment jsdom
 *
 * The interview booking panel loads on demand (audit follow-up, 2026-09-21).
 *
 * Three facts, each of which a later "tidy-up" could quietly undo:
 *   1. the panel still ARRIVES through the lazy boundary, with its props intact (this file);
 *   2. a chunk that cannot be fetched says so IN PLACE and does not throw — see the sibling
 *      `LazyInterviewBookingPanel.failure.test.tsx`. It is its own file because the two cases
 *      need different hoisted mocks of the same module, and `jest.resetModules()` between them
 *      loads a second React that Testing Library does not share;
 *   3. the page does not go back to a STATIC import, which is the whole saving (306 → 304 kB on
 *      the one student route that sat on its first-load budget). Jest cannot measure kilobytes —
 *      `npm run bundle-budget` does, in the deploy gate — so this pins the import line instead.
 */
import { render, screen } from '@testing-library/react'
import { readWeb } from '@/test/sourceGuard'
import LazyInterviewBookingPanel from './LazyInterviewBookingPanel'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/components/scholarship/InterviewBookingPanel', () => ({
  __esModule: true,
  default: ({ applicationId, token }: { applicationId: number; token: string | null }) => (
    <div data-testid="booking-panel">{applicationId}:{token}</div>
  ),
}))

describe('the interview booking panel arrives on demand', () => {
  it('draws nothing while the chunk is in the air, then the panel with its props', async () => {
    const { container } = render(<LazyInterviewBookingPanel applicationId={42} token="tok" />)
    // Mid-flight: identical to the old first paint, where the panel returned null until its own
    // schedule fetch landed.
    expect(container.innerHTML).toBe('')
    expect((await screen.findByTestId('booking-panel')).textContent).toBe('42:tok')
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

describe('the saving is the import line', () => {
  it('the page imports the LAZY panel and never the real one', () => {
    const page = readWeb('src/app/scholarship/application/page.tsx',
      'the student application page — the route whose first-load budget this lazy boundary pays for')
    expect(page).toContain("from '@/components/scholarship/LazyInterviewBookingPanel'")
    expect(page).not.toMatch(/from\s+'@\/components\/scholarship\/InterviewBookingPanel'/)
  })

  it('the lazy module owns a LITERAL import() of the real panel — a variable specifier emits no chunk', () => {
    const lazy = readWeb('src/components/scholarship/LazyInterviewBookingPanel.tsx',
      'the lazy boundary itself')
    expect(lazy).toContain("import('@/components/scholarship/InterviewBookingPanel')")
    expect(lazy).not.toMatch(/from\s+'next\/dynamic'/)
  })
})
