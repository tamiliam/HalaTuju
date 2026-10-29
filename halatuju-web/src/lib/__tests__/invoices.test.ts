import {
  canDeclarePayment, canRecordPayment, canSend, canVoid, defaultIssueDate, formatDay,
  issuableMonths, issueDateProblem, issueMode, lastRejectedDeclaration, openDeclaration,
  orderedInvoices, settingsHref, shiftMonth,
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
    payment_declarations: [],
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
    // `payment_declared` has no same-named key: both audiences get their own sentence, below.
    expect(statusChip('payment_declared').className).toMatch(/^bg-/)
  })

  describe('the word depends on who is reading it (owner, 2026-10-29)', () => {
    /** The owner opened the ORGANISATION's own invoice list and it said "Sent" — true, and
     *  meaningless to the person it was sent TO. What a customer needs is whether they owe. */
    const asOrg = { forOwner: false as const, today: '2026-10-29', dueOn: '2026-11-14' }

    it('reads Unpaid to the organisation and Sent to the owner', () => {
      expect(statusChip('sent', asOrg).key).toBe('admin.billing.invoice.status.unpaid')
      expect(statusChip('sent', { ...asOrg, forOwner: true }).key)
        .toBe('admin.billing.invoice.status.sent')
    })

    it('turns Overdue the day AFTER the due date, not on it', () => {
      // ⚠ The boundary is the whole point. An invoice due on the 14th is not late ON the 14th.
      expect(statusChip('sent', { ...asOrg, today: '2026-11-14' }).key)
        .toBe('admin.billing.invoice.status.unpaid')
      expect(statusChip('sent', { ...asOrg, today: '2026-11-15' }).key)
        .toBe('admin.billing.invoice.status.overdue')
    })

    it('never says Overdue when it cannot know', () => {
      // No date is the safe direction: telling a customer they are late when they are not is a
      // worse failure than not telling them at all.
      expect(statusChip('sent', { forOwner: false }).key)
        .toBe('admin.billing.invoice.status.unpaid')
      expect(statusChip('sent', { forOwner: false, today: '2026-12-01', dueOn: null }).key)
        .toBe('admin.billing.invoice.status.unpaid')
    })

    it('never says Overdue once the money has arrived', () => {
      const late = { ...asOrg, today: '2026-12-01' }
      expect(statusChip('paid', late).key).toBe('admin.billing.invoice.status.paid')
      expect(statusChip('part_paid', late).key).toBe('admin.billing.invoice.status.part_paid')
    })

    it('gives the owner a job and the organisation a wait when a payment is declared', () => {
      // ⚠ TWO DIFFERENT SENTENCES. The owner has something to DO; the tenant has something to
      // WAIT for. A shared word would leave the owner's queue invisible.
      expect(statusChip('payment_declared', asOrg).key)
        .toBe('admin.billing.invoice.status.beingChecked')
      expect(statusChip('payment_declared', { ...asOrg, forOwner: true }).key)
        .toBe('admin.billing.invoice.status.toCheck')
    })

    it('never says Overdue while a declared payment is being checked', () => {
      // The customer has done their part. Turning their row red while we check our own bank
      // would be blaming them for our queue.
      expect(statusChip('payment_declared', { ...asOrg, today: '2026-12-01' }).key)
        .toBe('admin.billing.invoice.status.beingChecked')
    })

    describe('nothing owed is never late (owner, 2026-10-29)', () => {
      /** The owner read BrightPath's own list: July 2026 is fully discounted — shown in full,
       *  charged nothing — and its row said OVERDUE, in red, beside a balance of RM0.00. */
      const longPast = { ...asOrg, today: '2026-12-01', dueOn: '2026-09-14' }

      it('says Nothing to pay instead of Overdue when the balance is zero', () => {
        expect(statusChip('sent', { ...longPast, balanceMyr: '0.00' }).key)
          .toBe('admin.billing.invoice.status.nothingToPay')
        expect(statusChip('sent', { ...longPast, balanceMyr: '0.00' }).className)
          .not.toMatch(/critical/)
      })

      it('does NOT say Paid, because no money arrived', () => {
        // `Invoice.status` is deliberate about this: a discounted month owes nothing, but
        // calling it paid would claim money changed hands.
        expect(statusChip('sent', { ...longPast, balanceMyr: '0.00' }).key)
          .not.toBe('admin.billing.invoice.status.paid')
      })

      it('still says Overdue when something really is owed', () => {
        expect(statusChip('sent', { ...longPast, balanceMyr: '790.86' }).key)
          .toBe('admin.billing.invoice.status.overdue')
      })

      it('says nothing of the sort when the balance was not passed', () => {
        // The safe direction: a customer who DOES owe must never be told otherwise.
        expect(statusChip('sent', longPast).key)
          .toBe('admin.billing.invoice.status.overdue')
      })

      it('leaves the owner reading Sent, as before', () => {
        expect(statusChip('sent', { ...longPast, forOwner: true, balanceMyr: '0.00' }).key)
          .toBe('admin.billing.invoice.status.sent')
      })
    })

    it('says Cancelled to the organisation where the owner reads Void', () => {
      expect(statusChip('void', asOrg).key).toBe('admin.billing.invoice.status.cancelled')
      expect(statusChip('void', { ...asOrg, forOwner: true }).key)
        .toBe('admin.billing.invoice.status.void')
    })

    it('defaults to the owner wording, so an un-updated caller is unchanged', () => {
      expect(statusChip('sent').key).toBe('admin.billing.invoice.status.sent')
    })
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

describe('payment declarations (2026-10-29)', () => {
  const open = {
    id: 3, paid_on: '2026-10-20', reference: 'MBB-77', declared_at: '2026-10-21T02:00:00Z',
    declared_by_email: 'oa@x.com', state: 'open' as const, reject_reason: '', receipt_number: '',
  }
  const rejected = { ...open, id: 2, state: 'rejected' as const, reject_reason: 'No credit.' }
  const confirmed = { ...open, id: 1, state: 'confirmed' as const, receipt_number: 'RCP-2026-0001' }
  const sent = { sent_at: '2026-10-15T02:00:00Z' }

  it('finds the one open claim and ignores the settled ones', () => {
    expect(openDeclaration(inv({ ...sent, payment_declarations: [open, rejected] }))?.id).toBe(3)
    expect(openDeclaration(inv({ ...sent, payment_declarations: [rejected, confirmed] })))
      .toBeUndefined()
    expect(openDeclaration(inv())).toBeUndefined()
  })

  it('offers the form on a sent invoice that still owes something', () => {
    expect(canDeclarePayment(inv(sent))).toBe(true)
  })

  it('does not offer the form where the server would refuse it', () => {
    // All four refusals the server raises: unsent, void, nothing owed, a claim already waiting.
    expect(canDeclarePayment(inv())).toBe(false)
    expect(canDeclarePayment(inv({ ...sent, status: 'void' }))).toBe(false)
    expect(canDeclarePayment(inv({ ...sent, balance_myr: '0.00' }))).toBe(false)
    expect(canDeclarePayment(inv({ ...sent, payment_declarations: [open] }))).toBe(false)
  })

  it('shows a rejection only while nothing newer has replaced it', () => {
    // ⚠ A stale "we could not find it" is worse than silence: it tells a customer who has since
    // declared again, or already paid, that they are still in trouble.
    expect(lastRejectedDeclaration(inv({ ...sent, payment_declarations: [rejected] }))?.id).toBe(2)
    expect(lastRejectedDeclaration(inv({ ...sent, payment_declarations: [open, rejected] })))
      .toBeUndefined()
    expect(lastRejectedDeclaration(inv({ ...sent, payment_declarations: [confirmed, rejected] })))
      .toBeUndefined()
    expect(lastRejectedDeclaration(inv())).toBeUndefined()
  })
})
