import {
  canRecordPayment, canSend, canVoid, formatDay, issueMode, needsSettings, orderedInvoices,
  orderedProblems, splitEmails, statusChip, todayIso,
} from '@/lib/invoices'
import type { InvoiceProblem, InvoiceRow } from '@/lib/admin-api'

function inv(over: Partial<InvoiceRow> = {}): InvoiceRow {
  return {
    id: 1, number: 'INV-2026-0001', organisation_id: 1, organisation: 'BrightPath',
    period_month: '2026-08', issued_on: '2026-09-15', due_on: '2026-10-15', status: 'issued',
    currency: 'MYR', subtotal_myr: '856.75', discount_pct: '0.00', discount_myr: '0.00',
    discount_reason: '', total_myr: '856.75', amount_paid_myr: '0.00', balance_myr: '856.75',
    sent_at: null, voided_at: null, void_reason: '', bill_to_name: 'BP', lines: [], receipts: [],
    ...over,
  }
}

const block: InvoiceProblem = { code: 'issuer_incomplete', message: 'x', overridable: false }
const warn: InvoiceProblem = { code: 'supplier_missing', message: 'y', overridable: true }

describe('issueMode', () => {
  it('is ready with no problems, override with only warnings, blocked with any blocker', () => {
    expect(issueMode([])).toBe('ready')
    expect(issueMode([warn])).toBe('override')
    expect(issueMode([warn, block])).toBe('blocked')
  })
  it('puts the blocker first so it is read before the warning', () => {
    expect(orderedProblems([warn, block]).map((p) => p.code)).toEqual(['issuer_incomplete', 'supplier_missing'])
  })
  it('sends the reader to Settings only for missing billing details', () => {
    expect(needsSettings([warn])).toBe(false)
    expect(needsSettings([block])).toBe(true)
    expect(needsSettings([{ code: 'bill_to_incomplete', message: '', overridable: false }])).toBe(true)
  })
})

describe('what each invoice offers', () => {
  it('offers no payment on a fully discounted month — the string "0.00" is truthy', () => {
    const zero = inv({ total_myr: '0.00', balance_myr: '0.00' })
    expect(canRecordPayment(zero)).toBe(false)
    expect(canRecordPayment(inv())).toBe(true)
  })
  it('offers no void once money has arrived, and nothing but a PDF on a void', () => {
    const paid = inv({ receipts: [{ id: 1, number: 'RCP-2026-0001', received_on: '2026-09-20',
      amount_myr: '10.00', method: 'bank_transfer', reference: 'x' }] })
    expect(canVoid(paid)).toBe(false)
    expect(canVoid(inv())).toBe(true)
    const v = inv({ status: 'void' })
    expect([canSend(v), canVoid(v), canRecordPayment(v)]).toEqual([false, false, false])
  })
  it('gives every status a chip key and a tone', () => {
    for (const s of ['issued', 'sent', 'part_paid', 'paid', 'void'] as const) {
      expect(statusChip(s).key).toBe(`admin.billing.invoice.status.${s}`)
      expect(statusChip(s).className).toMatch(/^bg-/)
    }
  })
  it('moves a voided invoice below the live ones without reordering the live ones', () => {
    const rows = [inv({ id: 1, status: 'void' }), inv({ id: 2 }), inv({ id: 3, status: 'paid' })]
    expect(orderedInvoices(rows).map((r) => r.id)).toEqual([2, 3, 1])
  })
})

describe('text helpers', () => {
  it('splits and de-duplicates billing emails on commas, semicolons and spaces', () => {
    expect(splitEmails('a@x.com, b@y.com;a@x.com  c@z.com')).toEqual(['a@x.com', 'b@y.com', 'c@z.com'])
    expect(splitEmails('')).toEqual([])
  })
  it('formats a date without passing it through a UTC Date', () => {
    expect(formatDay('2026-09-15')).toBe('15 Sep 2026')
    expect(formatDay('2026-01-01')).toBe('1 Jan 2026')
    expect(formatDay('nonsense')).toBe('nonsense')
  })
  it('builds today from local parts, so 00:30 local is not yesterday in UTC', () => {
    expect(todayIso(new Date(2026, 9, 15, 0, 30))).toBe('2026-10-15')
  })
})
