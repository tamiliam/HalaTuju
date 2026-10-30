/**
 * @jest-environment jsdom
 *
 * Her Funds tab on My Bursary (student maintenance S5b). Pinned:
 *  * received, award and what is still to come come from the server's STRINGS;
 *  * her last payments are listed as sent;
 *  * the spending card speaks in HER words (`bursaryTabs.spend.*`) — never the sponsor
 *    portal's — and names every category by its code's translation (owner ruling (a));
 *  * no report yet is said in words, never four zeroes.
 */
import { render, screen } from '@testing-library/react'
import BursaryFunds from './BursaryFunds'
import type { BursaryFunds as FundsPayload } from '@/lib/api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))

const FUNDS: FundsPayload = {
  award_amount: '2000.00', received: '550.50', remaining: '1449.50',
  releases: [{ amount: '250.50', released_on: '2026-10-01' }, { amount: '300.00', released_on: '2026-09-01' }],
  spending: { promised: '2000.00', released: '550.50', spent: '120.00', left: '430.50', as_at: '2026-10-28',
    categories: [{ code: 'food', total: '80.00' }, { code: 'micro_stall', total: '40.00' }] },
}

it('shows her money and payments, and the spending card in her own words', () => {
  render(<BursaryFunds funds={FUNDS} />)
  expect(screen.getByTestId('funds-received').textContent).toBe('RM550.50')
  expect(screen.getByTestId('funds-remaining').textContent).toContain('RM1,449.50')
  expect(screen.getByTestId('funds-releases').textContent).toContain('RM250.50')
  const card = screen.getByTestId('spending-card')
  expect(card.textContent).toContain('bursaryTabs.spend.title')
  expect(card.textContent).toContain('bursaryTabs.spend.cat.micro_stall')
  expect(card.textContent).not.toContain('sponsorPortal')
})

it('says so when no spending report has reached us', () => {
  render(<BursaryFunds funds={{ ...FUNDS, spending: null }} />)
  expect(screen.getByTestId('funds-no-spending').textContent).toBe('bursaryTabs.funds.noSpending')
  expect(screen.queryByTestId('spending-card')).toBeNull()
})
