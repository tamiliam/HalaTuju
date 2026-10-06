/**
 * @jest-environment jsdom
 *
 * The award and bursary-agreement panels load on demand (TD-352, 2026-10-06).
 *
 * Four facts a later "tidy-up" could quietly undo:
 *   1. a student with nothing to see never asks for the chunk;
 *   2. a student with an award offer (or a signed agreement) gets the panels, props intact, and
 *      they draw what the page used to draw;
 *   3. a chunk that cannot be fetched says so in place — the sibling `.failure.test.tsx`;
 *   4. the page does not go back to a STATIC import, which is the whole saving. Jest cannot
 *      measure kilobytes (`npm run bundle-budget` does), so this pins the import line instead.
 */
import { render, screen } from '@testing-library/react'
import type { BursaryAgreement, StudentAward } from '@/lib/api'
import { readWeb } from '@/test/sourceGuard'
import LazyApplicationAwardPanels, { showsAwardPanels } from './LazyApplicationAwardPanels'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}))

const OFFER = { status: 'offered' } as unknown as StudentAward
const ACCEPTED = { status: 'active' } as unknown as StudentAward
const SIGNED = { pdf_url: 'https://example.test/agreement.pdf' } as unknown as BursaryAgreement
const base = { award: null, acceptanceEnabled: false, bursary: null, status: 'recommended', onboardedAt: null }

describe('showsAwardPanels — the panels’ own two guards, asked before any fetch', () => {
  it.each([
    [{}, false],
    [{ award: OFFER }, false],                              // flag off: the award panel is hidden
    [{ award: OFFER, acceptanceEnabled: true }, true],
    [{ bursary: { pdf_url: '' } as unknown as BursaryAgreement }, false],
    [{ bursary: SIGNED }, true],
  ])('%j → %s', (over, want) => {
    expect(showsAwardPanels({ ...base, ...over })).toBe(want)
  })
})

describe('the panels arrive on demand', () => {
  it('draws nothing, and fetches nothing, for a student with no award', async () => {
    const { container } = render(<LazyApplicationAwardPanels {...base} />)
    await Promise.resolve()
    expect(container.innerHTML).toBe('')
  })

  it('an open offer → the accept panel, linking to the award page', async () => {
    render(<LazyApplicationAwardPanels {...base} award={OFFER} acceptanceEnabled />)
    expect(await screen.findByText('scholarship.application.awardPanel.title')).toBeTruthy()
    expect(screen.getByRole('link').getAttribute('href')).toBe('/scholarship/award')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('signed but not yet executed → the awaiting panel, and the agreement download', async () => {
    render(<LazyApplicationAwardPanels {...base} status="interviewed" award={ACCEPTED}
      acceptanceEnabled bursary={SIGNED} />)
    expect(await screen.findByText('scholarship.application.awardPanel.awaitingTitle')).toBeTruthy()
    expect(screen.getByText('scholarship.application.bursaryPanel.download').getAttribute('href'))
      .toBe(SIGNED.pdf_url)
  })

  it('accepted but not yet onboarded → the onboarding panel, linking to onboarding', async () => {
    render(<LazyApplicationAwardPanels {...base} status="active" award={ACCEPTED} acceptanceEnabled
      onboardedAt={null} />)
    expect(await screen.findByText('scholarship.application.awardPanel.onboardingBody')).toBeTruthy()
    expect(screen.getByRole('link').getAttribute('href')).toBe('/scholarship/onboarding')
    expect(screen.getByRole('link').textContent).toBe('scholarship.application.awardPanel.onboardingCta')
  })

  it('accepted and onboarded → the award panel goes', async () => {
    render(<LazyApplicationAwardPanels {...base} status="active" award={ACCEPTED} acceptanceEnabled
      onboardedAt="2026-10-01T00:00:00Z" bursary={SIGNED} />)
    expect(await screen.findByText('scholarship.application.bursaryPanel.title')).toBeTruthy()
    expect(screen.queryByText('scholarship.application.awardPanel.title')).toBeNull()
  })
})

describe('the saving is the import line', () => {
  it('the page imports the LAZY panels and never the real ones', () => {
    const page = readWeb('src/app/scholarship/application/page.tsx',
      'the student application page — the route whose first-load budget this lazy boundary pays for')
    expect(page).toContain("from '@/components/scholarship/LazyApplicationAwardPanels'")
    expect(page).not.toMatch(/from\s+'@\/components\/scholarship\/ApplicationAwardPanels'/)
  })

  it('the lazy module owns a LITERAL import() and takes only a type from the real one', () => {
    const lazy = readWeb('src/components/scholarship/LazyApplicationAwardPanels.tsx',
      'the lazy boundary itself')
    expect(lazy).toContain("import('./ApplicationAwardPanels')")
    expect(lazy).toMatch(/import type \{ AwardPanelsProps \} from '\.\/ApplicationAwardPanels'/)
    expect(lazy).not.toMatch(/^import (?!type)[^\n]*'\.\/ApplicationAwardPanels'/m)
    expect(lazy).not.toMatch(/from\s+'next\/dynamic'/)
  })
})
