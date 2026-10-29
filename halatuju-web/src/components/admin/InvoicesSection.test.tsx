/**
 * @jest-environment jsdom
 *
 * The Invoices section (2026-09-14). Written from the harms, not the markup:
 *
 *  * a tenant gets NO issuing controls — the server fences the data, and the screen must not
 *    offer a door the server would refuse;
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
    discount_reason: '', corrections_myr: null, corrections: [], total_myr: '856.75', amount_paid_myr: '0.00', balance_myr: '856.75',
    sent_at: null, voided_at: null, void_reason: '', bill_to_name: 'BrightPath Bursary',
    lines: [{ position: 1, category: 'development', description: 'Payments module', quantity: '10.0',
      unit_amount_myr: '57.50', amount_myr: '575.00' }],
    receipts: [], payment_declarations: [], bill_to_emails: ['finance@bp.example'], sent_to: [],
    ...over,
  }
}

function superPayload(over: Partial<api.InvoicesPayload> = {}): api.InvoicesPayload {
  return { invoices: [], month: '2026-08', issue_day: 15, readiness: [], ...over }
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.issueInvoice.mockResolvedValue(inv())
  mockApi.sendInvoice.mockResolvedValue(inv({ status: 'sent' }))
  mockApi.recordInvoiceReceipt.mockResolvedValue(inv())
  mockApi.voidInvoice.mockResolvedValue(inv({ status: 'void' }))
})

describe('grouped development lines (owner, 2026-10-29)', () => {
  /** The screen must read like the PDF: a group line carrying the money, its requests indented
   *  under it carrying hours only, and a bug line showing hours at a rate of RM0.00. */
  const grouped = [
    { position: 1, category: 'infrastructure', description: 'Platform infrastructure, August 2026',
      quantity: null, unit_amount_myr: null, amount_myr: '163.89' },
    { position: 2, category: 'development', description: 'Feature requests, August 2026',
      quantity: '24.5', unit_amount_myr: '23.00', amount_myr: '563.50' },
    { position: 3, category: 'development', description: 'show year SPM was taken (REQ-12)',
      is_sub_item: true, quantity: '6.0', unit_amount_myr: null, amount_myr: '0.00' },
    { position: 4, category: 'development', description: 'Bug reports, August 2026',
      quantity: '2.5', unit_amount_myr: '0.00', amount_myr: '0.00' },
  ]

  async function openDetail() {
    mockApi.getInvoices.mockResolvedValue({ invoices: [inv({ lines: grouped })] })
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => within(container).getAllByText('INV-2026-0003'))
    fireEvent.click(within(container).getAllByText('INV-2026-0003')[0])
    await waitFor(() => within(container).getAllByTestId('detail-7'))
    return container
  }

  it('indents a sub-item and prints no money on it', async () => {
    const container = await openDetail()
    // ⚠ Matched on the WORDS, not the whole cell: the request number is now an anchor, so the
    // cell's text is split across nodes. The full sentence is still asserted below.
    const cell = within(container).getAllByText(/show year SPM was taken/)[0].closest('td')!
    expect(cell.className).toContain('pl-6')
    expect(cell.textContent).toBe('show year SPM was taken (REQ-12)')
    const cells = cell.closest('tr')!.querySelectorAll('td')
    expect(cells[1].textContent).toBe('6.0')        // its own hours
    expect(cells[2].textContent).toBe('')           // no rate
    expect(cells[3].textContent).toBe('')           // and no amount, so the column still adds up
  })

  it('links the request number, and only the number, to the request itself', async () => {
    // Owner, 2026-10-29: "Perhaps just the text within the brackets." The wording around it is
    // the super's own text and means nothing to a router.
    const container = await openDetail()
    const link = within(container).getAllByText('REQ-12')[0] as HTMLAnchorElement
    expect(link.tagName).toBe('A')
    expect(link.getAttribute('href')).toBe('/admin/requests/12')
  })

  it('leaves a line that names no request as plain text', async () => {
    const container = await openDetail()
    const cell = within(container).getAllByText(/Feature requests, August 2026/)[0].closest('td')!
    expect(cell.querySelector('a')).toBeNull()
  })

  it('keeps the rate and the amount on the group line above it', async () => {
    const container = await openDetail()
    const cells = within(container).getAllByText('Feature requests, August 2026')[0]
      .closest('tr')!.querySelectorAll('td')
    expect(cells[1].textContent).toBe('24.5')
    expect(cells[2].textContent).toContain('23.00')
    expect(cells[3].textContent).toContain('563.50')
  })

  it('shows a bug line with its hours and a rate of zero', async () => {
    const container = await openDetail()
    const cells = within(container).getAllByText('Bug reports, August 2026')[0]
      .closest('tr')!.querySelectorAll('td')
    expect(cells[1].textContent).toBe('2.5')
    expect(cells[2].textContent).toContain('0.00')
    expect(cells[3].textContent).toContain('0.00')
  })

  it('leaves an older invoice with no sub-items looking exactly as it did', async () => {
    mockApi.getInvoices.mockResolvedValue({ invoices: [inv()] })
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => within(container).getAllByText('INV-2026-0003'))
    fireEvent.click(within(container).getAllByText('INV-2026-0003')[0])
    await waitFor(() => within(container).getAllByTestId('detail-7'))
    const cell = within(container).getAllByText('Payments module')[0]
    expect(cell.className).not.toContain('pl-6')
    expect(cell.closest('tr')!.querySelectorAll('td')[3].textContent).toContain('575.00')
  })
})

describe('a correction of an earlier month (owner, 2026-10-29)', () => {
  /** *"When we have overcharged or undercharged, this should be deducted or added (or written
   *  off) in the following month."* The sent invoice is never edited; the money travels forward
   *  as its own line, carrying the reason — so the tenant reads what we got wrong. */
  const open = async (over: Partial<api.InvoiceRow>) => {
    mockApi.getInvoices.mockResolvedValue({ invoices: [inv(over)] })
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => within(container).getAllByText('INV-2026-0003'))
    fireEvent.click(within(container).getAllByText('INV-2026-0003')[0])
    await waitFor(() => within(container).getAllByTestId('detail-7'))
    // ⚠ The FIRST detail panel, not the whole container: the section renders the row in more than
    // one place, so a container-wide match counts every correction twice.
    return within(container).getAllByTestId('detail-7')[0] as HTMLElement
  }

  it('prints a credit with a minus, its reason, and the invoice it puts right', async () => {
    const detail = await open({
      corrections_myr: '-126.50', total_myr: '730.25',
      corrections: [{ amount_myr: '-126.50', corrects_invoice: 'INV-2026-0001',
        reason: 'Requests 10 and 14: billed the plan, not the hours we reported' }],
    })
    const row = within(detail)
      .getByText('admin.billing.invoice.correctionCredit').closest('tr')!
    expect(row.textContent).toContain('INV-2026-0001')
    expect(row.textContent).toContain('Requests 10 and 14')
    // ⚠ The minus is drawn by the screen and the amount is UNSIGNED — never "−RM-126.50".
    expect(row.querySelectorAll('td')[1].textContent).toBe('−RM126.50')
  })

  it('prints an under-charge as a charge, with no minus', async () => {
    const detail = await open({
      corrections_myr: '40.00', total_myr: '896.75',
      corrections: [{ amount_myr: '40.00', corrects_invoice: '', reason: 'July: two hours missed' }],
    })
    const row = within(detail)
      .getByText('admin.billing.invoice.correctionCharge').closest('tr')!
    expect(row.querySelectorAll('td')[1].textContent).toBe('RM40.00')
  })

  it('keeps each correction on its own line rather than netting them', async () => {
    const detail = await open({
      corrections_myr: '-149.50', total_myr: '707.25',
      corrections: [
        { amount_myr: '-126.50', corrects_invoice: '', reason: 'request 10' },
        { amount_myr: '-23.00', corrects_invoice: '', reason: 'request 14' },
      ],
    })
    expect(within(detail).getAllByText('admin.billing.invoice.correctionCredit'))
      .toHaveLength(2)
  })

  it('a month with no correction prints no correction line at all', async () => {
    const detail = await open({})
    expect(within(detail).queryByText('admin.billing.invoice.correctionCredit')).toBeNull()
    expect(within(detail).queryByText('admin.billing.invoice.correctionCharge')).toBeNull()
  })
})

describe('what a tenant is offered', () => {
  it('shows its invoices and nothing to issue, send, pay, void or configure', async () => {
    mockApi.getInvoices.mockResolvedValue({ invoices: [inv({ status: 'sent', sent_at: '2026-09-15T01:00:00Z' })] })
    const { container } = render(<InvoicesSection token="tok" isSuper={false} t={t} />)
    await waitFor(() => within(container).getAllByText('INV-2026-0003'))
    expect(within(container).queryByRole('tablist')).toBeNull()

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
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath', organisation_code: 'brightpath',
      problems: [{ code: 'issuer_incomplete', message: 'Your own billing details are incomplete.', overridable: false },
        { code: 'supplier_missing', message: 'twilio missing', overridable: true }] }] }))
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    const card = await waitFor(() => within(container).getByTestId('readiness-1'))
    const issue = within(card).getByText('admin.billing.invoice.issue') as HTMLButtonElement
    expect(issue.disabled).toBe(true)
    expect(within(card).queryByText('admin.billing.invoice.issueAnyway')).toBeNull()
    // ⚠ The fix now lives on ANOTHER PAGE, and which page depends on which detail is blank.
    // A single "Settings" link would send half the readers somewhere that cannot help them.
    const link = within(card).getByText('admin.billing.invoice.fix.issuer_incomplete')
    expect(link.closest('a')?.getAttribute('href')).toBe('/admin/billing-rates')
    expect(within(card).queryByText('admin.billing.invoice.fix.bill_to_incomplete')).toBeNull()
  })

  it('points at the organisation when it is THEIR details that are blank', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath', organisation_code: 'brightpath',
      problems: [{ code: 'bill_to_incomplete', message: 'Billing details for BrightPath are incomplete.', overridable: false }] }] }))
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    const card = await waitFor(() => within(container).getByTestId('readiness-1'))
    const link = within(card).getByText('admin.billing.invoice.fix.bill_to_incomplete')
    // ⚠ The link NAMES the organisation the card is about, so the super lands on BrightPath
    // rather than on a picker re-asking what the card just said.
    expect(link.closest('a')?.getAttribute('href'))
      .toBe('/admin/organisation/settings?organisation=brightpath')
  })

  it('a warning is issued past only with a written reason, and the reason is sent', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath', organisation_code: 'brightpath',
      problems: [{ code: 'supplier_missing', message: 'twilio missing', overridable: true }] }] }))
    const { container } = render(<InvoicesSection token="tok" isSuper t={t} />)
    const card = await waitFor(() => within(container).getByTestId('readiness-1'))
    const anyway = within(card).getByText('admin.billing.invoice.issueAnyway') as HTMLButtonElement
    expect(anyway.disabled).toBe(true)
    fireEvent.change(within(card).getByLabelText('admin.billing.invoice.overrideReason'),
      { target: { value: '  Twilio was cancelled.  ' } })
    expect(anyway.disabled).toBe(false)
    fireEvent.click(anyway)
    // `issued_on` rides along on every issue: the prefilled 15th of the month after the billed
    // one, which for August is 15 September. The server would use today if it were blank, and
    // "today" on a back-issued month is the wrong date — see InvoiceToIssue.test.tsx.
    await waitFor(() => expect(mockApi.issueInvoice).toHaveBeenCalledWith(
      {
        organisation_id: 1, period_month: '2026-08', override_reason: 'Twilio was cancelled.',
        issued_on: '2026-09-15',
      }, { token: 'tok' }))
  })

  it('a month already invoiced reads as issued, not as a list of alarms', async () => {
    mockApi.getInvoices.mockResolvedValue(superPayload({ readiness: [{ organisation_id: 1, organisation: 'BrightPath', organisation_code: 'brightpath',
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

  it('says whether the receipt reached the customer, either way', async () => {
    // ⚠ NEVER BLANK. A receipt that did not arrive looks identical to one that did unless the
    // screen says so, and the customer is not going to tell us.
    const receipt = { id: 3, number: 'RCP-2026-0001', received_on: '2026-09-20',
      amount_myr: '100.00', method: 'bank_transfer', reference: 'x' }
    const paid = { status: 'part_paid' as const, amount_paid_myr: '100.00', balance_myr: '756.75' }

    const sent = await openIssued(inv({ ...paid,
      receipts: [{ ...receipt, emailed_at: '2026-09-21T02:00:00Z' }] }))
    expect(within(sent.detail).getByText(/receiptEmailed/).textContent)
      .toContain('21 Sep 2026')
    sent.unmount()

    const { detail } = await openIssued(inv({ ...paid,
      receipts: [{ ...receipt, emailed_at: null }] }))
    expect(within(detail).getByText('admin.billing.invoice.receiptNotEmailed')).toBeTruthy()
  })

  it('treats a receipt from before the column existed as not emailed', async () => {
    // Every receipt raised before 2026-10-29 has no `emailed_at` at all, and none of them were.
    const { detail } = await openIssued(inv({
      status: 'part_paid', amount_paid_myr: '100.00', balance_myr: '756.75',
      receipts: [{ id: 3, number: 'RCP-2026-0001', received_on: '2026-09-20',
        amount_myr: '100.00', method: 'bank_transfer', reference: 'x' }] }))
    expect(within(detail).getByText('admin.billing.invoice.receiptNotEmailed')).toBeTruthy()
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
