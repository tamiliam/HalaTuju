import {
  canRecordPayment, canSend, canVoid, defaultIssueDate, formatDay, issuableMonths,
  issueDateProblem, issueMode, orderedInvoices, settingsHref, shiftMonth,
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
  it('sends the reader to the page that can actually fix their problem', () => {
    // 2026-10-28: the two forms moved to the pages whose scope they match, so one link no longer
    // serves both. A supplier warning sends nobody anywhere.
    const billTo = { code: 'bill_to_incomplete', message: '', overridable: false }
    expect(settingsHref([warn])).toEqual([])
    expect(settingsHref([block])).toEqual([
      { code: 'issuer_incomplete', href: '/admin/billing-rates' }])
    expect(settingsHref([billTo])).toEqual([
      { code: 'bill_to_incomplete', href: '/admin/organisation/settings' }])
  })

  it('offers BOTH when both are blank, the issuer first', () => {
    // The first day in production is exactly this case: nothing is filled in anywhere, and the
    // issuer comes first because no invoice can be issued at all without it.
    const billTo = { code: 'bill_to_incomplete', message: '', overridable: false }
    expect(settingsHref([billTo, block]).map((d) => d.code))
      .toEqual(['issuer_incomplete', 'bill_to_incomplete'])
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

// ── Which month, and dated when (2026-10-28) ─────────────────────────────────────────────────
// The owner asked to bill July onwards, each invoice dated the 15th of the following month. Both
// halves were missing: the screen never asked for a month other than the server's default, and the
// issue date was always the day the button was pressed, so a July bill would carry November's due
// date. Every case below is a string compare; nothing here may build a `Date`.

describe('month arithmetic', () => {
  it('crosses a year boundary in both directions', () => {
    expect(shiftMonth('2026-12', 1)).toBe('2027-01')
    expect(shiftMonth('2026-01', -1)).toBe('2025-12')
    expect(shiftMonth('2026-07', 0)).toBe('2026-07')
  })
  it('refuses a month that is not a month, rather than printing one', () => {
    // '2026-00' is the trap `invoicing.MONTH_RE` exists for: index -1 reads as December.
    for (const bad of ['2026-00', '2026-13', '2026-7', 'nonsense', '', '2026']) {
      expect(shiftMonth(bad, 1)).toBe('')
    }
  })

  it('offers only months that have CLOSED, newest first', () => {
    const months = issuableMonths('2026-10-28', 4)
    expect(months).toEqual(['2026-09', '2026-08', '2026-07', '2026-06'])
    // ⚠ NEVER the current month. Its suppliers have not billed, which is the server's own
    // `month_not_closed` refusal; offering it would be a door that always fails.
    expect(months).not.toContain('2026-10')
  })
  it('walks back across the new year without inventing month zero', () => {
    // November 2026 stops the walk: its natural date is 15 December 2026, in a closed year.
    expect(issuableMonths('2027-02-15', 3)).toEqual(['2027-01', '2026-12'])
  })
})

describe('the issue date a month should carry', () => {
  it('prefills the 15th of the month AFTER the one being billed', () => {
    expect(defaultIssueDate('2026-07', '2026-10-28')).toBe('2026-08-15')
    expect(defaultIssueDate('2026-08', '2026-10-28')).toBe('2026-09-15')
    expect(defaultIssueDate('2026-12', '2027-03-01')).toBe('2027-01-15')
  })
  it('never prefills a future date, so a month closed early carries today', () => {
    // 1 October: September closed yesterday, but 15 October has not happened.
    expect(defaultIssueDate('2026-09', '2026-10-01')).toBe('2026-10-01')
  })

  it('accepts a date after the billed month ended and not after today', () => {
    expect(issueDateProblem('2026-07', '2026-08-15', '2026-10-28')).toBe('')
    expect(issueDateProblem('2026-07', '2026-08-01', '2026-10-28')).toBe('')
    expect(issueDateProblem('2026-07', '2026-10-28', '2026-10-28')).toBe('')
  })
  it('refuses a date inside the billed month, because a bill cannot predate what it bills', () => {
    expect(issueDateProblem('2026-07', '2026-07-31', '2026-10-28')).toBe('issueDateBeforeMonthEnd')
    expect(issueDateProblem('2026-07', '2026-07-01', '2026-10-28')).toBe('issueDateBeforeMonthEnd')
    expect(issueDateProblem('2026-07', '2026-06-30', '2026-10-28')).toBe('issueDateBeforeMonthEnd')
  })
  it('refuses tomorrow', () => {
    expect(issueDateProblem('2026-07', '2026-10-29', '2026-10-28')).toBe('issueDateFuture')
  })
  it('names a malformed date as malformed, not as out of range', () => {
    // Two different corrections, so two different messages — the same reason
    // `invoicing._receipt_amount` carries two sentences under one code.
    for (const bad of ['15/08/2026', '2026-8-15', '2026-08', '2026-13-01', '2026-08-32']) {
      expect(issueDateProblem('2026-07', bad, '2026-10-28')).toBe('badIssueDate')
    }
  })
  it('calls an EMPTY box a problem, which the server does not', () => {
    // ⚠ Deliberately stricter than the service. Blank means "today" there, which is right for
    // the monthly job and every ordinary Issue — but clearing this box would quietly produce the
    // exact failure the panel exists to stop: a July invoice dated 28 October, frozen, with a
    // November due date. Found by adversarial review, 2026-10-28.
    expect(issueDateProblem('2026-07', '', '2026-10-28')).toBe('issueDateRequired')
    expect(issueDateProblem('2026-07', '   ', '2026-10-28')).toBe('issueDateRequired')
  })

  it('refuses a date in a CLOSED YEAR, which would open a new run of numbers', () => {
    expect(issueDateProblem('2025-11', '2025-12-15', '2026-10-28')).toBe('issueDateLastYear')
    expect(issueDateProblem('2025-12', '2026-01-15', '2026-10-28')).toBe('')
  })
})

describe('the months offered never need a closed-year date', () => {
  it('stops at December of last year, the oldest month still datable in the open year', () => {
    // ⚠ A plain twelve-month window reached November 2025 and PREFILLED 15 December 2025 — a
    // date the server now refuses, so the reader would have been handed a prefilled error.
    const months = issuableMonths('2026-10-28', 12)
    expect(months[months.length - 1]).toBe('2025-12')
    expect(months).not.toContain('2025-11')
    for (const m of months) {
      expect(issueDateProblem(m, defaultIssueDate(m, '2026-10-28'), '2026-10-28')).toBe('')
    }
  })

  it('offers a full twelve months when the year has not been crossed', () => {
    expect(issuableMonths('2026-12-31', 12)).toEqual([
      '2026-11', '2026-10', '2026-09', '2026-08', '2026-07', '2026-06',
      '2026-05', '2026-04', '2026-03', '2026-02', '2026-01', '2025-12',
    ])
  })

  it('offers only December in early January, because nothing older can be dated yet', () => {
    expect(issuableMonths('2027-01-20', 12)).toEqual(['2026-12'])
  })
})
