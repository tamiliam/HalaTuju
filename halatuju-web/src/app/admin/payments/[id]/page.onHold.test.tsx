/**
 * @jest-environment jsdom
 *
 * Student maintenance S1 (adversarial review L3): on hold stops money, so the run says WHO is on
 * hold (a chip, from the served `on_hold`), and a refused approval (`on_hold_in_run`) says how many
 * — the count the server sends — and what to do. `t` echoes its key and its params.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import PaymentRunPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k),
    locale: 'en',
  }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin', owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: '3' }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const SIG = { name: 'Kulaly Maker', email: 'k@x.com', at: '2026-10-19T02:00:00Z' }
const ITEM = {
  id: 9, application_id: 41, name: 'Student A', nric: '000101-14-0001', vircle_id: '8000400170001',
  activated: true, award_amount: '2000.00', paid_to_date: '0.00', amount: '200.00',
  credit_applied: '0.00', included: true, exclude_reason: '',
}

const run = (over: Partial<api.PaymentRunDetail> = {}): api.PaymentRunDetail => ({
  id: 3, reference: 'PR-2026-11-01', payment_date: '2026-11-01', period_month: '2026-11-01',
  status: 'admin_signed', note: '', drive_file_url: '', created_by: 'k@x.com', created_at: '',
  admin_signed: SIG, finance_signed: null, org_admin_signed: null,
  finance_check_required: false, check_step_required: false,
  your_step: 'approve', approver_fallback: false, can_prepare: true,
  items: [{ ...ITEM, on_hold: true }], skipped: [], students: 1, total: '200.00',
  ...over,
} as api.PaymentRunDetail)

beforeEach(() => jest.clearAllMocks())

it('shows an on-hold chip on a held student, and none on the others', async () => {
  mockApi.getPaymentRun.mockResolvedValue(run())
  render(<PaymentRunPage />)
  await waitFor(() => expect(screen.getByTestId('on-hold-chip')).toBeTruthy())
})

it('a refused approval says how many students are on hold', async () => {
  mockApi.getPaymentRun.mockResolvedValue(run())
  const refusal = Object.assign(new Error('on_hold_in_run'), {
    status: 400, code: 'on_hold_in_run', body: { code: 'on_hold_in_run', count: 2 } })
  mockApi.signPaymentRun.mockRejectedValue(refusal)
  render(<PaymentRunPage />)
  const box = await screen.findByPlaceholderText('admin.payments.fullName')
  fireEvent.change(box, { target: { value: 'Approver One' } })
  fireEvent.click(screen.getByText('admin.payments.countersign'))
  expect(await screen.findByText('admin.payments.error.on_hold_in_run|{"count":"2"}')).toBeTruthy()
})

it('a student not on hold carries no chip', async () => {
  mockApi.getPaymentRun.mockResolvedValue(run({ items: [{ ...ITEM, on_hold: false }] }))
  render(<PaymentRunPage />)
  await waitFor(() => expect(screen.getByText('admin.payments.signOff')).toBeTruthy())
  expect(screen.queryByTestId('on-hold-chip')).toBeNull()
})
