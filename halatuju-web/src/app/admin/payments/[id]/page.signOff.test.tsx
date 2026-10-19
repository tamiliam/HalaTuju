/**
 * @jest-environment jsdom
 *
 * The sign-off block after request #39 Sprint 2 (owner, 2026-10-19, option A): Admin prepares,
 * Finance APPROVES, and the organisation admin approves only when nobody else can.
 *
 * Pinned here: a name box is drawn ONLY for the step the server says this viewer may take now
 * (`your_step`, from the same `payments.next_step_for` the sign endpoint asks) — every other
 * unsigned step says it is waiting; the fallback notice appears only to the person approving under
 * it; and edit / cancel follow the served `can_prepare`, never a role read on the screen.
 */
import { render, screen, waitFor } from '@testing-library/react'
import PaymentRunPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'finance', owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: '3' }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const SIG = { name: 'Kulaly Maker', email: 'k@x.com', at: '2026-10-19T02:00:00Z' }

const run = (over: Partial<api.PaymentRunDetail> = {}): api.PaymentRunDetail => ({
  id: 3, reference: 'PR-2026-11-01', payment_date: '2026-11-01', period_month: '2026-11-01',
  status: 'admin_signed', note: '', drive_file_url: '', created_by: 'k@x.com', created_at: '',
  admin_signed: SIG, finance_signed: null, org_admin_signed: null,
  finance_check_required: false, check_step_required: false,
  your_step: null, approver_fallback: false, can_prepare: false,
  items: [], skipped: [], students: 0, total: '0',
  ...over,
} as api.PaymentRunDetail)

async function mount(r: api.PaymentRunDetail) {
  mockApi.getPaymentRun.mockResolvedValue(r)
  render(<PaymentRunPage />)
  await waitFor(() => expect(screen.getByText('admin.payments.signOff')).toBeTruthy())
}

beforeEach(() => jest.clearAllMocks())

describe('the approval box follows your_step', () => {
  it('offers Finance the approval when the server says it is their step', async () => {
    await mount(run({ your_step: 'approve' }))
    expect(screen.getByText('admin.payments.countersign')).toBeTruthy()
    expect(screen.queryByTestId('approver-fallback')).toBeNull()
    expect(screen.queryByText('admin.payments.cancelRun')).toBeNull()      // can_prepare: false
  })

  it('draws no name box for somebody whose step it is not, and says it is waiting', async () => {
    await mount(run({ your_step: null, can_prepare: true }))
    expect(screen.queryByText('admin.payments.countersign')).toBeNull()
    expect(screen.queryByText('admin.payments.sign')).toBeNull()
    expect(screen.getByText('admin.payments.awaitingStep')).toBeTruthy()
    expect(screen.getByText('admin.payments.cancelRun')).toBeTruthy()      // the org admin cancels
  })

  it('tells the organisation admin why they approve, only under the fallback', async () => {
    await mount(run({ your_step: 'approve', approver_fallback: true, can_prepare: true }))
    expect(screen.getByTestId('approver-fallback').textContent).toBe('admin.payments.approverFallback')
    expect(screen.getByText('admin.payments.countersign')).toBeTruthy()
  })

  it('offers the maker the first signature on a draft, and nothing further along', async () => {
    await mount(run({ status: 'draft', admin_signed: null, your_step: 'sign', can_prepare: true }))
    expect(screen.getByText('admin.payments.sign')).toBeTruthy()
    expect(screen.queryByText('admin.payments.countersign')).toBeNull()
    expect(screen.getByText('admin.payments.afterMaker')).toBeTruthy()
  })

  it('with the check armed, the approver waits for it and the checker gets the box', async () => {
    await mount(run({ check_step_required: true, finance_check_required: true, your_step: 'check' }))
    expect(screen.getByText('admin.payments.financeSign')).toBeTruthy()
    expect(screen.getByText('admin.payments.awaitingFinanceCheck')).toBeTruthy()
    expect(screen.queryByText('admin.payments.countersign')).toBeNull()
  })
})
