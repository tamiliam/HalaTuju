/**
 * @jest-environment jsdom
 *
 * The scholar file's Money tab (student maintenance S5a). Pinned:
 *  * the screen formats the server's strings and does no arithmetic of its own;
 *  * her last releases are listed as the server sends them;
 *  * the spending block is drawn ONLY when the payload carries it (the server leaves the key out for a
 *    viewer without the `spending` permission) — and it says which period it covers;
 *  * the Payments / Spending links are the ones the page hands in, nothing more.
 */
import { render, screen } from '@testing-library/react'
import ScholarMoney from './ScholarMoney'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const BASE: api.ScholarMoney = {
  award_amount: '2000.00', paid_to_date: '550.50', remaining: '1449.50',
  releases: [{ amount: '250.50', released_on: '2026-10-20', label: 'October', reference: 'RUN-9' },
    { amount: '300.00', released_on: '2026-09-20', label: '', reference: 'RUN-8' }],
}

beforeEach(() => jest.clearAllMocks())

it('shows the server figures and her last releases, with no spending block when the server sent none', async () => {
  mockApi.getScholarMoney.mockResolvedValue(BASE)
  render(<ScholarMoney id={7} token="tok" links={[]} />)
  expect((await screen.findByTestId('money-paid_to_date')).textContent).toBe('RM550.50')
  expect(screen.getByTestId('money-remaining').textContent).toBe('RM1,449.50')
  expect(screen.getByTestId('money-releases').textContent).toContain('October')
  expect(screen.queryByTestId('money-spending')).toBeNull()
  expect(screen.queryByRole('link')).toBeNull()
})

it('draws the spending block, its period and the links when they are there', async () => {
  mockApi.getScholarMoney.mockResolvedValue({ ...BASE, spending: {
    since: '2026-09-01', basis: 'term', spent: '42.00', as_at: '2026-10-28',
    categories: [{ code: 'food', label: 'Food', total: '30.00' }, { code: 'transport', label: 'Transport', total: '12.00' }],
  } })
  render(<ScholarMoney id={7} token="tok" links={[{ page: 'payments', href: '/admin/payments?programme=flag' },
    { page: 'spending', href: '/admin/spending?programme=flag' }]} />)
  const block = await screen.findByTestId('money-spending')
  expect(block.textContent).toContain('admin.scholars.moneyTab.since.term')
  expect(block.textContent).toContain('Food')
  expect(block.textContent).toContain('RM42.00')
  expect(screen.getByRole('link', { name: 'admin.scholars.money.openPayments' }).getAttribute('href'))
    .toBe('/admin/payments?programme=flag')
})

it('says so when the read fails', async () => {
  mockApi.getScholarMoney.mockRejectedValue(new Error('x'))
  render(<ScholarMoney id={7} token="tok" links={[]} />)
  expect(await screen.findByText('admin.scholars.moneyTab.loadFailed')).toBeTruthy()
})
