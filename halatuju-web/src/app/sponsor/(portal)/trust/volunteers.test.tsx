/**
 * @jest-environment jsdom
 *
 * Request #69 (2026-11-17, board 3): "Our volunteers" on the sponsor's Trust & Transparency page — the
 * headline as served (`senior_pct`), then the four levels as bars and "Based on {n}+ volunteers who have
 * told us." with the served band. Review round: when the server withholds the shares (a level holds
 * everyone or one person) the page shows the headline and the footnote, no bars. Below five answers the
 * server sends no figures and the section is off.
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

it('shows the served headline, the four bars and the banded count', () => {
  mockTrust = { ...BASE, volunteers: { count_at_least: 20, senior_pct: 39,
    shares: { c_level: 13, head: 26, manager: 30, individual: 31 } } }
  render(<TrustPage />)
  const section = screen.getByTestId('trust-volunteers')
  expect(section.querySelector('h2')?.textContent).toBe(`${V}.title`)
  expect(section.textContent).toContain(`${V}.headline(39)`)
  expect(section.textContent).toContain(`${V}.basedOn(20)`)
  for (const [k, n] of [['c_level', 13], ['head', 26], ['manager', 30], ['individual', 31]] as const) {
    const row = screen.getByTestId(`trust-volunteers-${k}`)
    expect(row.textContent).toContain(`${V}.level.${k}`)
    expect(row.textContent).toContain(`${n}%`)
    expect((row.querySelector('.bg-info-600') as HTMLElement).style.width).toBe(`${n}%`)
  }
})

it('shares withheld: the headline and the footnote, no bars', () => {
  mockTrust = { ...BASE, volunteers: { count_at_least: 5, senior_pct: 43, shares: null } }
  render(<TrustPage />)
  const section = screen.getByTestId('trust-volunteers')
  expect(section.textContent).toContain(`${V}.headline(43)`)
  expect(section.textContent).toContain(`${V}.basedOn(5)`)
  for (const k of ['c_level', 'head', 'manager', 'individual']) {
    expect(screen.queryByTestId(`trust-volunteers-${k}`)).toBeNull()
  }
  expect(section.querySelector('.bg-info-600')).toBeNull()
})

it('sits between Governance and Sources & uses', () => {
  mockTrust = { ...BASE, volunteers: { count_at_least: 5, senior_pct: 60,
    shares: { c_level: 20, head: 40, manager: 20, individual: 20 } } }
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
