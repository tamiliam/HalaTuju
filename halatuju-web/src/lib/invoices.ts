/**
 * Tenant invoices and receipts (2026-09-14) — pure presentation helpers for /admin/billing.
 *
 * Node-testable, no React, no i18n objects: label KEYS only. Money arrives as STRINGS and a
 * string is truthy at '0.00', so every decision below goes through Number().
 */
import type { InvoiceProblem, InvoiceRow, InvoiceStatus } from '@/lib/admin-api'

/**
 * The chip for a status: an i18n key and a semantic tone. Tone is separate from the accent.
 *
 * ⚠ **THE WORD DEPENDS ON WHO IS READING IT.** The owner read the organisation's own invoice list
 * on 2026-10-29 and found it said "Sent" — true, and meaningless to the person it was sent TO, who
 * can see it in front of them. What a customer needs to know is whether they owe anything, so the
 * same `sent` row reads "Unpaid" on their side, and "Overdue" once the due date has passed.
 *
 * `today` and `dueOn` are passed in rather than read from the clock here: this module is pure, and
 * an overdue chip that depends on a hidden `new Date()` cannot be tested at a boundary. Omit them
 * and nothing is ever overdue, which is the safe direction — a customer wrongly told they are late
 * is a worse failure than one not told at all.
 */
export function statusChip(
  status: InvoiceStatus,
  opts: { forOwner?: boolean; today?: string; dueOn?: string | null } = {},
): { key: string; className: string } {
  const owner = opts.forOwner !== false      // default to the owner's wording, as before
  switch (status) {
    case 'paid':
      return { key: 'admin.billing.invoice.status.paid', className: 'bg-positive-100 text-positive-700' }
    case 'part_paid':
      return { key: 'admin.billing.invoice.status.part_paid', className: 'bg-caution-100 text-caution-700' }
    case 'payment_declared':
      // ⚠ TWO DIFFERENT SENTENCES, not one word dressed twice. The owner has something to DO
      // ("Check the bank"); the tenant has something to WAIT for ("Payment being checked"). A
      // shared "Declared" would leave the owner's queue invisible and the tenant unsure anyone
      // had noticed — which is the whole complaint this feature answers.
      return {
        key: owner
          ? 'admin.billing.invoice.status.toCheck'
          : 'admin.billing.invoice.status.beingChecked',
        className: 'bg-caution-100 text-caution-700',
      }
    case 'sent':
      if (owner) {
        return { key: 'admin.billing.invoice.status.sent', className: 'bg-info-100 text-info-700' }
      }
      // ⚠ STRING compare on two ISO dates, never `new Date()`: the same reason `todayIso` exists
      // in this file. A timezone shift must not make a customer's invoice turn red a day early.
      if (opts.today && opts.dueOn && opts.today > opts.dueOn) {
        return { key: 'admin.billing.invoice.status.overdue', className: 'bg-critical-100 text-critical-700' }
      }
      return { key: 'admin.billing.invoice.status.unpaid', className: 'bg-info-100 text-info-700' }
    case 'void':
      return {
        key: owner ? 'admin.billing.invoice.status.void' : 'admin.billing.invoice.status.cancelled',
        className: 'bg-ground-100 text-ground-500',
      }
    default:
      // `issued` is "Not sent", which the organisation never sees — an invoice reaches them only
      // once it has been sent. Left as the owner's word rather than invented for a case that
      // cannot occur.
      return { key: 'admin.billing.invoice.status.issued', className: 'bg-ground-100 text-ground-700' }
  }
}

/** Send is offered for anything not void. Re-sending a lost email is ordinary. */
export function canSend(inv: InvoiceRow): boolean {
  return inv.status !== 'void'
}

/** Money can be recorded while something is still owed on a live invoice. A fully discounted
 *  month owes nothing, so it offers no payment button — there is nothing to receive. */
export function canRecordPayment(inv: InvoiceRow): boolean {
  return inv.status !== 'void' && Number(inv.balance_myr) > 0
}

/** The tenant's open claim on this invoice, or undefined. The screen shows at most one. */
export function openDeclaration(inv: InvoiceRow) {
  return (inv.payment_declarations || []).find((d) => d.state === 'open')
}

/** The last claim the owner could not match, if it is the most recent thing that happened.
 *
 * ⚠ Only shown while nothing newer has replaced it: once the tenant declares again, or the money
 * is in, a stale "we could not find it" is worse than silence. */
export function lastRejectedDeclaration(inv: InvoiceRow) {
  const list = inv.payment_declarations || []
  if (list.length === 0 || openDeclaration(inv)) return undefined
  return list[0].state === 'rejected' ? list[0] : undefined
}

/** Can the TENANT say it has paid? Only its own sent invoice, with something still owed and no
 *  claim already waiting. The server refuses all four cases; the form follows the same rule so it
 *  is never offered only to fail. */
export function canDeclarePayment(inv: InvoiceRow): boolean {
  return inv.status !== 'void' && inv.sent_at !== null
    && Number(inv.balance_myr) > 0 && !openDeclaration(inv)
}

/** Void is refused server-side once money has arrived; the button follows the same rule so it is
 *  never offered only to fail. */
export function canVoid(inv: InvoiceRow): boolean {
  return inv.status !== 'void' && inv.receipts.length === 0
}

/**
 * What the Issue control may do for a set of readiness problems.
 *  - 'ready'    — no problems: a plain Issue.
 *  - 'override' — only overridable warnings: Issue anyway, with a written reason.
 *  - 'blocked'  — at least one problem no reason can fix: nothing to press.
 */
export function issueMode(problems: InvoiceProblem[]): 'ready' | 'override' | 'blocked' {
  const list = problems || []
  if (list.length === 0) return 'ready'
  return list.some((p) => !p.overridable) ? 'blocked' : 'override'
}

/** Blocking problems first, so the thing that must be fixed is read before the thing that may be
 *  overridden. Stable within each group. */
export function orderedProblems(problems: InvoiceProblem[]): InvoiceProblem[] {
  const list = problems || []
  return [...list.filter((p) => !p.overridable), ...list.filter((p) => p.overridable)]
}

/** Where to send a reader whose invoice is blocked on a blank form.
 *
 * ⚠ TWO DESTINATIONS SINCE 2026-10-28, and that is the point. The two forms used to share one tab,
 * so one link served both. They now live on the pages whose SCOPE they match — who is billing is
 * platform-wide, who is billed belongs to the organisation — and a single "Settings" link would
 * send half the readers to a page that cannot fix their problem.
 *
 * Order follows `orderedProblems`: a blocker before a warning, and the issuer before the bill-to
 * because nothing at all can be issued without it. */
export function settingsHref(
  problems: InvoiceProblem[], organisationCode?: string,
): Array<{ code: string; href: string }> {
  const codes = new Set((problems || []).map((p) => p.code))
  const out: Array<{ code: string; href: string }> = []
  if (codes.has('issuer_incomplete')) {
    out.push({ code: 'issuer_incomplete', href: '/admin/billing-rates' })
  }
  if (codes.has('bill_to_incomplete')) {
    // ⚠ NAME THE ORGANISATION. A super reading "BrightPath is blocked" must land on BrightPath,
    // not on a "which organisation?" picker — the card already answered that question.
    const q = organisationCode ? `?organisation=${encodeURIComponent(organisationCode)}` : ''
    out.push({ code: 'bill_to_incomplete', href: `/admin/organisation/settings${q}` })
  }
  return out
}

/** "a@x.com, b@y.com; c@z.com" → a clean, de-duplicated list. */
export function splitEmails(text: string): string[] {
  const out: string[] = []
  for (const part of (text || '').split(/[,;\s]+/)) {
    const e = part.trim()
    if (e && !out.includes(e)) out.push(e)
  }
  return out
}

/** Invoices split for the screen: live ones first by month (newest), then voided ones. The server
 *  already orders by month; this only moves voids down so a withdrawn bill never sits on top. */
export function orderedInvoices(invoices: InvoiceRow[]): InvoiceRow[] {
  const list = invoices || []
  return [...list.filter((i) => i.status !== 'void'), ...list.filter((i) => i.status === 'void')]
}

const DAY_RE = /^(\d{4})-(\d{2})-(\d{2})/
const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** 'YYYY-MM-DD' → '15 Sep 2026'. Parsed by hand: `new Date('2026-09-15')` is UTC midnight, which a
 *  browser west of Greenwich renders as the 14th. A malformed value is returned unchanged. */
export function formatDay(iso: string | null | undefined): string {
  const m = (iso || '').match(DAY_RE)
  if (!m) return iso || ''
  const idx = parseInt(m[2], 10) - 1
  if (idx < 0 || idx > 11) return iso || ''
  return `${parseInt(m[3], 10)} ${SHORT_MONTHS[idx]} ${m[1]}`
}

/** Today in the viewer's own calendar as 'YYYY-MM-DD' — the default "received on" date. Built
 *  from local parts, never `toISOString()`, which is the UTC date. */
export function todayIso(now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`
}

// ── Which month, and dated when (2026-10-28) ─────────────────────────────────────────────────
// The owner asked to bill from July onwards, each invoice dated the 15th of the following month.
// Neither was possible from this screen: it only ever asked the server for the DEFAULT month (the
// one just closed), and the issue date was always the day the button was pressed.
//
// ⚠ Every comparison below is a plain string compare on ISO dates, which sorts correctly by
// construction. No `new Date(...)` anywhere: '2026-08-15' parses as UTC midnight, so a browser
// west of Greenwich reads it as the 14th — the bug `formatDay` above already exists to avoid.

const MONTH_ONLY_RE = /^(\d{4})-(0[1-9]|1[0-2])$/

/** 'YYYY-MM' shifted by whole months. '' for anything that is not a real calendar month. */
export function shiftMonth(month: string, delta: number): string {
  const m = (month || '').match(MONTH_ONLY_RE)
  if (!m) return ''
  const index = parseInt(m[1], 10) * 12 + (parseInt(m[2], 10) - 1) + delta
  if (index < 0) return ''
  return `${String(Math.floor(index / 12)).padStart(4, '0')}-${String((index % 12) + 1).padStart(2, '0')}`
}

/** The months a super may pick, newest first: every month that has CLOSED, back `count` of them.
 *
 * Two months are never offered:
 *   - the CURRENT one — its suppliers have not billed, which is the server's `month_not_closed`
 *     refusal and the reason the whole cut-off exists;
 *   - anything whose natural issue date (the 15th of the month after it) falls in a PREVIOUS
 *     calendar year. ⚠ Adversarial review, 2026-10-28: a twelve-month window reached November
 *     2025, prefilled 15 December 2025, and the server would then have minted `INV-2025-0001` —
 *     reopening a closed, filed run of numbers. The server refuses that date now; offering the
 *     month anyway would just hand the reader a prefilled error. So the list stops at December of
 *     last year, which is the oldest month that can still be dated inside the open year. */
export function issuableMonths(today: string, count = 12): string[] {
  const thisMonth = (today || '').slice(0, 7)
  const year = (today || '').slice(0, 4)
  const out: string[] = []
  for (let i = 1; i <= Math.max(count, 1); i += 1) {
    const m = shiftMonth(thisMonth, -i)
    if (!m) continue
    if (shiftMonth(m, 1).slice(0, 4) < year) break
    out.push(m)
  }
  return out
}

/** The date an invoice for `month` SHOULD carry: the 15th of the month after it — the owner's
 *  cut-off, the day the monthly job would have sent it. Capped at today, because an invoice
 *  cannot be dated in the future, so a month closed early carries today instead. */
export function defaultIssueDate(month: string, today: string): string {
  const next = shiftMonth(month, 1)
  if (!next) return today
  const due = `${next}-15`
  return due > today ? today : due
}

/** Why this issue date cannot be used — an i18n key suffix, or '' when it can.
 *
 * The SERVER decides (`invoicing.issue_date_for`); this mostly saves a round trip and puts the
 * message beside the box. Its bounds are the server's:
 *   - never after today;
 *   - never in a previous calendar year — the printed year opens that year's run of numbers;
 *   - never inside the billed month or earlier — a bill cannot predate the thing it bills. On ISO
 *     strings that is simply `issuedOn`'s own month being at or before `month`.
 *
 * ⚠ ONE RULE IS STRICTER HERE THAN ON THE SERVER, DELIBERATELY: a BLANK box is a problem. The
 * service reads blank as "today", which is right for the monthly job and for every ordinary
 * Issue — but this panel exists to set a date on purpose, and adversarial review (2026-10-28)
 * found that clearing the box silently produced the exact failure the panel was built to stop: a
 * July invoice dated 28 October with a November due date, frozen, remedied only by a void. */
export function issueDateProblem(month: string, issuedOn: string, today: string): string {
  const value = (issuedOn || '').trim()
  if (value === '') return 'issueDateRequired'
  if (!/^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(value)) return 'badIssueDate'
  if (value > today) return 'issueDateFuture'
  if (value.slice(0, 4) < today.slice(0, 4)) return 'issueDateLastYear'
  if (!MONTH_ONLY_RE.test(month || '')) return ''
  if (value.slice(0, 7) <= month) return 'issueDateBeforeMonthEnd'
  return ''
}
