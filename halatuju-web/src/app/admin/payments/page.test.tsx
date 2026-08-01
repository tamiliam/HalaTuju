/**
 * @jest-environment jsdom
 *
 * The funding summary's "Last paid" column (BrightPath request #5, 2026-08-01).
 *
 * It used to read `PR-2026-07-26-01 · 26/07/2026` — the payment run's reference and the date it
 * was paid, joined by a dot. The column is headed with a question about WHEN, and the reference
 * answered a different one while earning very little (it is not clickable), so the requester asked
 * for the date alone. What this pins is the pair that is easy to regress together: the date must
 * still be there, and the reference must not creep back beside it.
 */
import { render, screen } from '@testing-library/react'
import PaymentsLandingPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', is_super_admin: true } }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const FUNDING = {
  rows: [
    {
      application_id: 1, name: 'RASEKA A/P MURUGESE', ref: 'B40-0119', status: 'active',
      award_amount: '3000', paid_to_date: '1000', remaining: '2000', vircle_id: '1234567890123',
      last_run: { reference: 'PR-2026-07-26-01', payment_date: '2026-07-26' },
      programme: 'B40',
    },
    {
      application_id: 2, name: 'NEVER PAID', ref: 'B40-0200', status: 'active',
      award_amount: '3000', paid_to_date: '0', remaining: '3000', vircle_id: '',
      last_run: null, programme: 'B40',
    },
  ],
  totals: { students: 2, award_total: '6000', paid_total: '1000', remaining_total: '5000' },
} as unknown as api.FundingSummary

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getPaymentRuns.mockResolvedValue({ runs: [] } as unknown as Awaited<ReturnType<typeof api.getPaymentRuns>>)
  mockApi.getFundingSummary.mockResolvedValue(FUNDING)
})

describe('the Last paid column', () => {
  it('shows the date on its own', async () => {
    render(<PaymentsLandingPage />)
    expect(await screen.findByText('26/07/2026')).toBeTruthy()
  })

  it('no longer shows the payment run reference beside it', async () => {
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    // Neither joined to the date nor standing alone in that cell.
    expect(screen.queryByText(/PR-2026-07-26-01/)).toBeNull()
  })

  it('still says nothing at all for a student who has never been paid', async () => {
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})
