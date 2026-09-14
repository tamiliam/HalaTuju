/**
 * Tenant invoices and receipts (2026-09-14) — pure presentation helpers for /admin/billing.
 *
 * Node-testable, no React, no i18n objects: label KEYS only. Money arrives as STRINGS and a
 * string is truthy at '0.00', so every decision below goes through Number().
 */
import type { InvoiceProblem, InvoiceRow, InvoiceStatus } from '@/lib/admin-api'

/** The chip for a status: an i18n key and a semantic tone. Tone is separate from the accent. */
export function statusChip(status: InvoiceStatus): { key: string; className: string } {
  switch (status) {
    case 'paid':
      return { key: 'admin.billing.invoice.status.paid', className: 'bg-positive-100 text-positive-700' }
    case 'part_paid':
      return { key: 'admin.billing.invoice.status.part_paid', className: 'bg-caution-100 text-caution-700' }
    case 'sent':
      return { key: 'admin.billing.invoice.status.sent', className: 'bg-info-100 text-info-700' }
    case 'void':
      return { key: 'admin.billing.invoice.status.void', className: 'bg-ground-100 text-ground-500' }
    default:
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

/** Problems that send the reader to the Settings tab rather than anywhere else. */
export function needsSettings(problems: InvoiceProblem[]): boolean {
  return (problems || []).some((p) => p.code === 'issuer_incomplete' || p.code === 'bill_to_incomplete')
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
