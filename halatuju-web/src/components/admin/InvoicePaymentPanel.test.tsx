/**
 * @jest-environment jsdom
 *
 * "We have paid this" (2026-10-29). Written from the harms, not the markup:
 *
 *  * the TENANT gets a date and a reference, and nothing that looks like recording money;
 *  * the OWNER never sees the tenant's figure offered as the amount — there is no tenant figure;
 *  * a claim is ACKNOWLEDGED to the tenant, because being unsure anyone noticed is the complaint
 *    this whole feature answers;
 *  * a rejection is shown WITH ITS REASON, and stops being shown once something newer replaces it;
 *  * neither side is offered the other's buttons.
 */
import { fireEvent, render, within } from '@testing-library/react'
import InvoicePaymentPanel from './InvoicePaymentPanel'
import type { InvoicePaymentDeclarationRow, InvoiceRow } from '@/lib/admin-api'

const t = (k: string, vars?: Record<string, string>) =>
  (vars ? `${k}:${Object.values(vars).join('|')}` : k)

function inv(over: Partial<InvoiceRow> = {}): InvoiceRow {
  return {
    id: 7, number: 'INV-2026-0003', organisation_id: 1, organisation: 'BrightPath',
    period_month: '2026-09', issued_on: '2026-10-15', due_on: '2026-11-14', status: 'sent',
    currency: 'MYR', subtotal_myr: '179.89', discount_pct: '0.00', discount_myr: '0.00',
    discount_reason: '', total_myr: '179.89', amount_paid_myr: '0.00', balance_myr: '179.89',
    sent_at: '2026-10-15T02:00:00Z', voided_at: null, void_reason: '', bill_to_name: 'BP',
    lines: [], receipts: [], payment_declarations: [],
    ...over,
  }
}

const open: InvoicePaymentDeclarationRow = {
  id: 3, paid_on: '2026-10-20', reference: 'MBB-77', declared_at: '2026-10-21T02:00:00Z',
  declared_by_email: 'oa@x.com', state: 'open', reject_reason: '', receipt_number: '',
}

function mount(over: Partial<InvoiceRow>, isSuper: boolean) {
  const onDeclare = jest.fn()
  const onConfirm = jest.fn()
  const onReject = jest.fn()
  const row = inv(over)
  const { container } = render(
    <InvoicePaymentPanel inv={row} isSuper={isSuper} busy={false} t={t}
      onDeclare={onDeclare} onConfirm={onConfirm} onReject={onReject} />)
  return { container, row, onDeclare, onConfirm, onReject }
}

describe('the tenant side', () => {
  it('takes the date DAY FIRST and sends the server the ISO date', () => {
    // ⚠ The customer writes it the Malaysian way (owner, 2026-10-29); the money code keeps the
    // one date format it has always parsed.
    const { container, row, onDeclare } = mount({}, false)
    const form = within(container).getByTestId('declare-7')
    fireEvent.change(within(form).getByLabelText('admin.billing.invoice.declare.paidOn'),
      { target: { value: '20-10-2026' } })
    fireEvent.change(within(form).getByLabelText('admin.billing.invoice.declare.reference'),
      { target: { value: ' MBB-77 ' } })
    fireEvent.click(within(form).getByText('admin.billing.invoice.declare.submit'))
    // ⚠ EXACTLY TWO FIELDS. No amount is collected, by the owner's choice: the invoice already
    // states it, and a tenant-typed figure would only invite a dispute.
    expect(onDeclare).toHaveBeenCalledWith(row, { paid_on: '2026-10-20', reference: 'MBB-77' })
  })

  it('says so, and sends nothing, when the date is not a real date', () => {
    const { container, onDeclare } = mount({}, false)
    const form = within(container).getByTestId('declare-7')
    fireEvent.change(within(form).getByLabelText('admin.billing.invoice.declare.reference'),
      { target: { value: 'MBB-77' } })
    fireEvent.change(within(form).getByLabelText('admin.billing.invoice.declare.paidOn'),
      { target: { value: '31-02-2026' } })
    expect(within(form).getByTestId('declare-baddate-7')).toBeTruthy()
    const button = within(form)
      .getByText('admin.billing.invoice.declare.submit') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(onDeclare).not.toHaveBeenCalled()
  })

  it('cannot be submitted without a bank reference', () => {
    const { container, onDeclare } = mount({}, false)
    const form = within(container).getByTestId('declare-7')
    const button = within(form)
      .getByText('admin.billing.invoice.declare.submit') as HTMLButtonElement
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(onDeclare).not.toHaveBeenCalled()
  })

  it('is told its claim arrived, and is not offered the form again', () => {
    const { container } = mount({ payment_declarations: [open], status: 'payment_declared' }, false)
    expect(within(container).getByTestId('declared-7').textContent)
      .toContain('admin.billing.invoice.declare.waiting')
    expect(within(container).queryByTestId('declare-7')).toBeNull()
  })

  it('is never offered the buttons that belong to the owner', () => {
    const { container } = mount({ payment_declarations: [open], status: 'payment_declared' }, false)
    expect(within(container).queryByTestId('check-7')).toBeNull()
    expect(within(container).queryByText('admin.billing.invoice.declare.confirm')).toBeNull()
  })

  it('is not offered the form on an invoice it cannot declare against', () => {
    for (const over of [{ sent_at: null }, { status: 'void' as const },
      { balance_myr: '0.00' }]) {
      const { container } = mount(over, false)
      expect(within(container).queryByTestId('declare-7')).toBeNull()
    }
  })
})

describe('the owner side', () => {
  it('defaults the amount to the BALANCE, never to anything the tenant said', () => {
    // ⚠ There is no tenant figure to default to, and that is the design. The date and the
    // reference ARE seeded from the claim, because re-typing a reference invites a typo.
    const { container } = mount({ payment_declarations: [open], status: 'payment_declared' }, true)
    const form = within(container).getByTestId('check-7')
    const value = (label: string) =>
      (within(form).getByLabelText(label) as HTMLInputElement).value
    expect(value('admin.billing.invoice.amount')).toBe('179.89')
    expect(value('admin.billing.invoice.receivedOn')).toBe('2026-10-20')
    expect(value('admin.billing.invoice.reference')).toBe('MBB-77')
  })

  it('confirms with the figures on the screen, corrections included', () => {
    const { container, row, onConfirm } = mount(
      { payment_declarations: [open], status: 'payment_declared' }, true)
    const form = within(container).getByTestId('check-7')
    fireEvent.change(within(form).getByLabelText('admin.billing.invoice.reference'),
      { target: { value: 'MBB-REAL-99' } })
    fireEvent.click(within(form).getByText('admin.billing.invoice.declare.confirm'))
    expect(onConfirm).toHaveBeenCalledWith(row, {
      declaration_id: 3, amount_myr: '179.89', received_on: '2026-10-20',
      reference: 'MBB-REAL-99',
    })
  })

  it('cannot say "not found" without a reason the tenant will be shown', () => {
    const { container, onReject } = mount(
      { payment_declarations: [open], status: 'payment_declared' }, true)
    const form = within(container).getByTestId('check-7')
    fireEvent.click(within(form).getByText('admin.billing.invoice.declare.notFound'))
    const confirm = within(form)
      .getByText('admin.billing.invoice.declare.notFoundConfirm') as HTMLButtonElement
    expect(confirm.disabled).toBe(true)
    fireEvent.change(within(form).getByLabelText('admin.billing.invoice.declare.reason'),
      { target: { value: 'No credit that week.' } })
    fireEvent.click(confirm)
    expect(onReject).toHaveBeenCalledWith(expect.anything(),
      { declaration_id: 3, reason: 'No credit that week.' })
  })

  it('is shown nothing at all until a tenant declares something', () => {
    const { container } = mount({}, true)
    expect(within(container).queryByTestId('check-7')).toBeNull()
    expect(within(container).queryByTestId('declare-7')).toBeNull()
  })
})

describe('a rejected claim', () => {
  const rejected: InvoicePaymentDeclarationRow = {
    ...open, id: 2, state: 'rejected', reject_reason: 'No credit on the 20th.',
  }

  it('is shown to both sides, with the reason', () => {
    for (const isSuper of [true, false]) {
      const { container } = mount({ payment_declarations: [rejected] }, isSuper)
      expect(within(container).getByTestId('rejected-7').textContent)
        .toContain('No credit on the 20th.')
    }
  })

  it('stops being shown once the tenant declares again', () => {
    // A stale "we could not find it" tells a customer who has already fixed it that they are
    // still in trouble.
    const { container } = mount({ payment_declarations: [open, rejected] }, false)
    expect(within(container).queryByTestId('rejected-7')).toBeNull()
  })

  it('lets the tenant try again', () => {
    const { container } = mount({ payment_declarations: [rejected] }, false)
    expect(within(container).getByTestId('declare-7')).toBeTruthy()
  })
})
