/**
 * @jest-environment jsdom
 *
 * The Invoices section (2026-09-14). Written from the harms, not the markup:
 *
 *  * a tenant gets NO issuing controls and NO settings — the server fences the data, and the screen
 *    must not offer a door the server would refuse;
 *  * nothing is sent without a confirm that NAMES the inboxes (owner: "you press send");
 *  * a warning can be issued past ONLY with a written reason, and a blocker not at all;
 *  * a fully discounted month's '0.00' is a truthy string, and must not offer a payment form;
 *  * a receipt cannot be recorded without a bank reference, and void is not offered once paid.
 */
import { fireEvent, render, waitFor, within } from '@testing-library/react'
import InvoicesSection from './InvoicesSection'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
// TableFrame reads the translator for its scroll hint.
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
const mockApi = api as jest.Mocked<typeof api>

const t = (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k)

function inv(over: Partial<api.InvoiceRow> = {}): api.InvoiceRow {
  return {
    id: 7, number: 'INV-2026-0003', organisation_id: 1, organisation: 'BrightPath',
    period_month: '2026-08', issued_on: '2026-09-15', due_on: '2026-10-15', status: 'issued',
    currency: 'MYR', subtotal_myr: '856.75', discount_pct: '0.00', discount_myr: '0.00',
    discount_reason: '', total_myr: '856.75', amount_paid_myr: '0.00', balance_myr: '856.75',
    sent_at: null, voided_at: null, void_reason: '', bill_to_name: 'BrightPath Bursary',
    lines: [{ position: 1, category: 'development', description: 'Payments module', quantity: '10.0',
      unit_amount_myr: '57.50', amount_myr: '575.00' }],
    receipts: [], bill_to_emails: ['finance@bp.example'], sent_to: [],
    ...over,
  }
}

const SETTINGS: api.InvoiceSettingsPayload = {
  issuer: { legal_name: '', registration_no: '', address: '', email: '', phone: '', bank_name: '',
    bank_account_name: '', bank_account_no: '', payment_terms_days: 30,
    missing: ['legal_name', 'address', 'bank_name', 'bank_account_name', 'bank_account_no'] },
  tenants: [{ organisation_id: 1, organisation: 'BrightPath', bill_to_name: 'BrightPath Bursary',
    address: '', emails: ['finance@bp.example'], missing: ['address'] }],
}

function superPayload(over: Partial<api.InvoicesPayload> = {}): api.InvoicesPayload {
  return { invoices: [], month: '2026-08', issue_day: 15, readiness: [], ...over }
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getInvoiceSettings.mockResolvedValue(SETTINGS)
  mockApi.issueInvoice.mockResolvedValue(inv())
  mockApi.sendInvoice.mockResolvedValue(inv({ status: 'sent' }))
  mockApi.recordInvoiceReceipt.mockResolvedValue(inv())
  mockApi.voidInvoice.mockResolvedValue(inv({ status: 'void' }))
})

describe('what a tenant is offered', () => {
  it('shows its invoices and nothing to issue, send, pay, void or configure', async () => {
    mockApi.getInvoices.mockResolvedValue({ invoices: [inv({ status: 'sent', sent_at: '2026-09-15T01:00:00Z' })] })
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => within(container).getAllByText('INV-2026-0003'))
    expect(within(container).queryByRole('tablist')).toBeNull()
    expect(mockApi.getInvoiceSettings).not.toHaveBeenCalled()

    fireEvent.click(within(container).getAllByText('INV-2026-0003')[0])
    await waitFor(() => within(container).getAllByTestId('detail-7'))
    for (const control of ['admin.billing.invoice.send', 'admin.billing.invoice.sendAgain',
      'admin.billing.invoice.recordPayment', 'admin.billing.invoice.void']) {
      expect(within(container).queryByText(control)).toBeNull()
    }
  })

  it('says plainly when nothing has been sent yet', async () => {
    mockApi.getInvoices.mockResolvedValue({ invoices: [] })
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => within(container).getByTestId('no-invoices'))
    expect(within(container).getByText('admin.billing.invoice.noneTenant')).not.toBeNull()
  })

  it('renders nothing at all while billing is dark for this reader', async () => {
    mockApi.getInvoices.mockRejectedValue(new Error('not_found'))
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => expect(mockApi.getInvoices).toHaveBeenCalled())
    expect(within(container).queryByTestId('invoices')).toBeNull()
    expect(within(container).queryByRole('alert')).toBeNull()
  })
})

describe('issuing', () => {
  it('a blocker leaves nothing to press, and points to Settings', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath',
      problems: [{ code: 'issuer_incomplete', message: 'Your own billing details are incomplete.', overridable: false },
        { code: 'supplier_missing', message: 'twilio missing', overridable: true }] }] }))
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    const card = await waitFor(() => within(container).getByTestId('readiness-1'))
    const issue = within(card).getByText('admin.billing.invoice.issue') as HTMLButtonElement
    expect(issue.disabled).toBe(true)
    expect(within(card).queryByText('admin.billing.invoice.issueAnyway')).toBeNull()
    fireEvent.click(within(card).getByText('admin.billing.invoice.fillSettings'))
    await waitFor(() => within(container).getByTestId('issuer-form'))
  })

  it('a warning is issued past only with a written reason, and the reason is sent', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath',
      problems: [{ code: 'supplier_missing', message: 'twilio missing', overridable: true }] }] }))
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    const card = await waitFor(() => within(container).getByTestId('readiness-1'))
    const anyway = within(card).getByText('admin.billing.invoice.issueAnyway') as HTMLButtonElement
    expect(anyway.disabled).toBe(true)
    fireEvent.change(within(card).getByLabelText('admin.billing.invoice.overrideReason'),
      { target: { value: '  Twilio was cancelled.  ' } })
    expect(anyway.disabled).toBe(false)
    fireEvent.click(anyway)
    await waitFor(() => expect(mockApi.issueInvoice).toHaveBeenCalledWith(
      { organisation_id: 1, period_month: '2026-08', override_reason: 'Twilio was cancelled.' }, { token: 'tok' }))
  })

  it('a month already invoiced reads as issued, not as a list of alarms', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath',
      problems: [{ code: 'already_issued', message: 'already', overridable: false },
        { code: 'unbilled_hours', message: '27 hours', overridable: true }] }] }))
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    const card = await waitFor(() => within(container).getByTestId('readiness-1'))
    expect(within(card).getByText('admin.billing.invoice.alreadyIssued')).not.toBeNull()
    expect(within(card).queryByText('27 hours')).toBeNull()
    expect(within(card).queryByText('admin.billing.invoice.issue')).toBeNull()
  })
})

async function openIssued(row: api.InvoiceRow) {
  mockApi.getInvoices.mockResolvedValue(superPayload({ invoices: [row] }))
  const view = render(<InvoicesSection token="tok" isSuper t={t} />)
  await waitFor(() => within(view.container).getByRole('tablist'))
  fireEvent.click(within(view.container).getByText('admin.billing.invoice.tab.issued'))
  // Cards (phone) and table (desktop) both render in jsdom, which has no CSS; drive the first.
  fireEvent.click((await waitFor(() => within(view.container).getAllByText(row.number)))[0])
  const detail = (await waitFor(() => within(view.container).getAllByTestId(`detail-${row.id}`)))[0]
  return { ...view, detail }
}

describe('after issue', () => {
  it('Send names the inboxes and sends nothing until confirmed', async () => {
    const { detail } = await openIssued(inv())
    fireEvent.click(within(detail).getByText('admin.billing.invoice.send'))
    expect(mockApi.sendInvoice).not.toHaveBeenCalled()
    expect(within(detail).getByText('admin.billing.invoice.confirmSend:finance@bp.example')).not.toBeNull()
    fireEvent.click(within(detail).getByText('admin.billing.invoice.send'))
    await waitFor(() => expect(mockApi.sendInvoice).toHaveBeenCalledWith(7, { token: 'tok' }))
  })

  it('a fully discounted month offers no payment form — "0.00" is a truthy string', async () => {
    const { detail } = await openIssued(inv({ total_myr: '0.00', balance_myr: '0.00' }))
    expect(within(detail).queryByText('admin.billing.invoice.recordPayment')).toBeNull()
  })

  it('a receipt needs a bank reference before it can be recorded', async () => {
    const { detail } = await openIssued(inv())
    const record = within(detail).getByText('admin.billing.invoice.recordAndReceipt') as HTMLButtonElement
    expect(record.disabled).toBe(true)
    fireEvent.change(within(detail).getByLabelText('admin.billing.invoice.reference'), { target: { value: 'MBB-1' } })
    expect(record.disabled).toBe(false)
    fireEvent.click(record)
    await waitFor(() => expect(mockApi.recordInvoiceReceipt).toHaveBeenCalledWith(
      7, expect.objectContaining({ amount_myr: '856.75', reference: 'MBB-1', method: 'bank_transfer' }),
      { token: 'tok' }))
  })

  it('void is not offered once money has arrived, and needs a reason before it is', async () => {
    const paid = inv({ status: 'part_paid', amount_paid_myr: '100.00', balance_myr: '756.75',
      receipts: [{ id: 3, number: 'RCP-2026-0001', received_on: '2026-09-20', amount_myr: '100.00',
        method: 'bank_transfer', reference: 'x' }] })
    const first = await openIssued(paid)
    expect(within(first.detail).queryByText('admin.billing.invoice.void')).toBeNull()
    first.unmount()

    const { detail } = await openIssued(inv())
    fireEvent.click(within(detail).getByText('admin.billing.invoice.void'))
    const confirm = within(detail).getByText('admin.billing.invoice.voidConfirm') as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    fireEvent.change(within(detail).getByLabelText('admin.billing.invoice.voidReason'), { target: { value: 'Wrong month' } })
    fireEvent.click(confirm)
    await waitFor(() => expect(mockApi.voidInvoice).toHaveBeenCalledWith(7, 'Wrong month', { token: 'tok' }))
  })
})

describe('settings', () => {
  it('a blank days-to-pay is left out rather than sent as zero', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload())
    mockApi.saveInvoiceIssuer.mockResolvedValue(SETTINGS)
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    await waitFor(() => within(container).getByRole('tablist'))
    fireEvent.click(within(container).getByText('admin.billing.invoice.tab.settings'))
    const form = await waitFor(() => within(container).getByTestId('issuer-form'))
    const inputs = form.querySelectorAll('input')
    const days = inputs[inputs.length - 1] as HTMLInputElement
    fireEvent.change(days, { target: { value: '' } })
    fireEvent.click(within(form).getByText('admin.billing.invoice.settings.save'))
    await waitFor(() => expect(mockApi.saveInvoiceIssuer).toHaveBeenCalled())
    expect(mockApi.saveInvoiceIssuer.mock.calls[0][0]).not.toHaveProperty('payment_terms_days')
  })
})
