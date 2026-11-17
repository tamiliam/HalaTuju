/**
 * @jest-environment jsdom
 *
 * Request #69 (2026-11-17, board 3): "Our volunteers" on the sponsor's Trust & Transparency page — the
 * headline adds the two top shares as served, then the four levels as bars and "Based on the {n}
 * volunteers who have told us." Below five answers the server sends no figures and the section is off.
 */
import { render, screen } from '@testing-library/react'
import TrustPage from './page'
import type { SponsorTrust } from '@/lib/api/sponsor'

jest.mock('@/lib/messagesSponsor', () => ({}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string | number>) => (v ? `${k}(${Object.values(v).join('|')})` : k) }),
}))
jest.mock('next/link', () => ({ __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }))
let mockTrust: SponsorTrust | null = null
jest.mock('@/lib/sponsor-portal-context', () => ({ useSponsorPortal: () => ({ trust: mockTrust }) }))

const BASE = {
  legal_entity: 'Sample Foundation Berhad', contact_email: 'hello@sample.invalid', trustees: [],
  sources: [], uses: [], assurance: {}, figures_are_illustrative: false,
  community: {} as SponsorTrust['community'],
} as SponsorTrust
const V = 'sponsorPortal.trust.volunteers'

it('shows the headline (top two shares added), the four bars and how many told us', () => {
  mockTrust = { ...BASE, volunteers: { count: 23, shares: { c_level: 13, head: 26, manager: 30, individual: 31 } } }
  render(<TrustPage />)
  const section = screen.getByTestId('trust-volunteers')
  expect(section.querySelector('h2')?.textContent).toBe(`${V}.title`)
  expect(section.textContent).toContain(`${V}.headline(39)`)
  expect(section.textContent).toContain(`${V}.basedOn(23)`)
  for (const [k, n] of [['c_level', 13], ['head', 26], ['manager', 30], ['individual', 31]] as const) {
    const row = screen.getByTestId(`trust-volunteers-${k}`)
    expect(row.textContent).toContain(`${V}.level.${k}`)
    expect(row.textContent).toContain(`${n}%`)
    expect((row.querySelector('.bg-info-600') as HTMLElement).style.width).toBe(`${n}%`)
  }
})

it('sits between Governance and Sources & uses', () => {
  mockTrust = { ...BASE, volunteers: { count: 5, shares: { c_level: 20, head: 40, manager: 20, individual: 20 } } }
  render(<TrustPage />)
  const titles = Array.from(document.querySelectorAll('h2')).map((h) => h.textContent)
  const at = titles.indexOf(`${V}.title`)
  expect(titles[at - 1]).toBe('sponsorPortal.trust.governance.title')
  expect(titles[at + 1]).toBe('sponsorPortal.trust.sourcesUses.title')
})

it('no figures from the server, no section', () => {
  for (const volunteers of [null, undefined]) {
    mockTrust = { ...BASE, volunteers }
    const { unmount } = render(<TrustPage />)
    expect(screen.queryByTestId('trust-volunteers')).toBeNull()
    unmount()
  }
})
