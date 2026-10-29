'use client'

/**
 * Invoices on Billing & usage (2026-09-14). Approved mockup: artifact c6edf138.
 *
 * TWO AUDIENCES, ONE COMPONENT, and the split is the server's, not ours:
 *  - super   — To issue (readiness per tenant) / Issued (every invoice, with Send, Record payment,
 *              Void) / Settings (who bills, who is billed).
 *  - org_admin — its own invoices, ONLY once sent, with the PDFs. The server never returns an
 *              unsent invoice to a tenant, so this component cannot show one by mistake.
 *
 * It loads its OWN data and holds its OWN error, like the costs section: a failure here must never
 * darken the usage half of the page, which an org_admin is entitled to read.
 */
import { useCallback, useEffect, useState } from 'react'
import InvoiceToIssue from '@/components/admin/InvoiceToIssue'
import TableFrame from '@/components/admin/TableFrame'
import {
  fetchBillingPdf, getInvoices, issueInvoice, recordInvoiceReceipt, sendInvoice, voidInvoice,
  type InvoiceProblem, type InvoiceRow, type InvoicesPayload,
} from '@/lib/admin-api'
import { formatMyr } from '@/lib/billingCosts'
import { formatMonth } from '@/lib/billingUsage'
import {
  canRecordPayment, canSend, canVoid, formatDay, orderedInvoices, statusChip, todayIso,
} from '@/lib/invoices'

type T = (k: string, vars?: Record<string, string>) => string
type Tab = 'toissue' | 'issued'

const INPUT = 'mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm text-ground-900'
const PRIMARY = 'rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50'
const SECONDARY = 'rounded-lg border bg-ground-0 px-2.5 py-1 text-xs text-ground-700 hover:bg-ground-50 disabled:opacity-50'

function errorText(e: unknown): string {
  const err = e as { body?: { message?: string; problems?: InvoiceProblem[] }; message?: string }
  if (err?.body?.problems?.length) return err.body.problems.map((p) => p.message).join(' ')
  return err?.body?.message || err?.message || String(e)
}

/** The browser cannot follow a plain link to a route that needs the auth header, so the PDF is
 *  fetched as a Blob and handed to the browser as a download. */
async function downloadPdf(kind: 'invoice' | 'receipt', id: number, name: string, token: string) {
  const blob = await fetchBillingPdf(kind, id, { token })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function Chip({ status, t, isSuper, dueOn }: {
  status: InvoiceRow['status']; t: T; isSuper: boolean; dueOn?: string | null
}) {
  // The owner sees what they DID ("Sent"); the organisation sees what it OWES ("Unpaid", or
  // "Overdue" once the due date has passed). See `statusChip`.
  const c = statusChip(status, { forOwner: isSuper, today: todayIso(), dueOn })
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${c.className}`}>
      {t(c.key)}
    </span>
  )
}

// ── Issued ───────────────────────────────────────────────────────────────────────────────────

function InvoiceDetail({ inv, isSuper, busy, t, token, onSend, onVoid, onReceipt }: {
  inv: InvoiceRow
  isSuper: boolean
  busy: boolean
  t: T
  token: string
  onSend: (inv: InvoiceRow) => void
  onVoid: (inv: InvoiceRow, reason: string) => void
  onReceipt: (inv: InvoiceRow, data: { received_on: string; amount_myr: string; method: string; reference: string }) => void
}) {
  const [receivedOn, setReceivedOn] = useState(todayIso())
  const [amount, setAmount] = useState(inv.balance_myr)
  const [method, setMethod] = useState('bank_transfer')
  const [reference, setReference] = useState('')
  const [voidOpen, setVoidOpen] = useState(false)
  const [voidReason, setVoidReason] = useState('')
  const [confirmSend, setConfirmSend] = useState(false)

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]" data-testid={`detail-${inv.id}`}>
      <TableFrame bare minWidth={420} label={t('admin.billing.invoice.title')}>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-ground-500">
            <th className="px-2 py-1.5 text-left font-medium">{t('admin.billing.invoice.col.description')}</th>
            <th className="px-2 py-1.5 text-right font-medium">{t('admin.billing.invoice.col.hours')}</th>
            <th className="px-2 py-1.5 text-right font-medium">{t('admin.billing.invoice.col.rate')}</th>
            <th className="px-2 py-1.5 text-right font-medium">{t('admin.billing.invoice.col.amount')}</th>
          </tr>
        </thead>
        {/* `tabular-nums` on the figure cells only, not the body: it switches face to Plex
            (Lexend has no even digits), and the descriptions must stay in Lexend (TD-310). */}
        <tbody>
          {/* A sub-item is indented and prints NO amount, matching the PDF exactly: its parent
              carries the group's money, so showing RM0.00 here would read as something waived. */}
          {inv.lines.map((ln) => (
            <tr key={ln.position} className="border-b">
              <td className={ln.is_sub_item ? 'py-1.5 pl-6 pr-2 text-ground-600' : 'px-2 py-1.5 text-ground-900'}>{ln.description}</td>
              <td className="px-2 py-1.5 text-right tabular-nums text-ground-700">{ln.quantity ?? ''}</td>
              <td className="px-2 py-1.5 text-right tabular-nums text-ground-700">{ln.is_sub_item || !ln.unit_amount_myr ? '' : formatMyr(ln.unit_amount_myr)}</td>
              <td className="px-2 py-1.5 text-right tabular-nums text-ground-900">{ln.is_sub_item ? '' : formatMyr(ln.amount_myr)}</td>
            </tr>
          ))}
          <tr><td colSpan={3} className="px-2 pt-2 text-right text-ground-500">{t('admin.billing.charge.subtotal')}</td>
            <td className="px-2 pt-2 text-right tabular-nums">{formatMyr(inv.subtotal_myr)}</td></tr>
          {Number(inv.discount_myr) > 0 && (
            <tr><td colSpan={3} className="px-2 text-right text-ground-500">
              {t('admin.billing.invoice.discountLine', { pct: String(Number(inv.discount_pct)) })}
              {inv.discount_reason && <span className="block text-[11px] text-ground-400">{inv.discount_reason}</span>}
            </td><td className="px-2 text-right tabular-nums">−{formatMyr(inv.discount_myr)}</td></tr>
          )}
          <tr className="font-semibold"><td colSpan={3} className="border-t border-ground-900 px-2 pt-1.5 text-right">{t('admin.billing.invoice.totalDue')}</td>
            <td className="border-t border-ground-900 px-2 pt-1.5 text-right tabular-nums">{formatMyr(inv.total_myr)}</td></tr>
          {Number(inv.amount_paid_myr) > 0 && (
            <>
              <tr><td colSpan={3} className="px-2 text-right text-ground-500">{t('admin.billing.invoice.paid')}</td>
                <td className="px-2 text-right tabular-nums">−{formatMyr(inv.amount_paid_myr)}</td></tr>
              <tr className="font-semibold"><td colSpan={3} className="px-2 text-right">{t('admin.billing.invoice.balance')}</td>
                <td className="px-2 text-right tabular-nums">{formatMyr(inv.balance_myr)}</td></tr>
            </>
          )}
        </tbody>
      </table>
      </TableFrame>

      <div className="space-y-4 text-xs">
        {inv.status === 'void' && (
          <p className="text-ground-700">{t('admin.billing.invoice.voidedBecause', { reason: inv.void_reason })}</p>
        )}

        <div>
          <h4 className="text-xs font-semibold text-ground-900">{t('admin.billing.invoice.receipts')}</h4>
          {inv.receipts.length === 0 ? (
            <p className="mt-1 text-ground-400">{t('admin.billing.invoice.noReceipts')}</p>
          ) : (
            <ul className="mt-1 space-y-1">
              {inv.receipts.map((r) => (
                <li key={r.id} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-mono">{r.number}</span>
                  <span className="text-ground-500">{formatDay(r.received_on)} · {r.reference}</span>
                  <span className="tabular-nums font-semibold">{formatMyr(r.amount_myr)}</span>
                  <button type="button" className={SECONDARY}
                    onClick={() => downloadPdf('receipt', r.id, r.number, token)}>
                    {t('admin.billing.invoice.pdf')}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {isSuper && canRecordPayment(inv) && (
          <div>
            <h4 className="text-xs font-semibold text-ground-900">{t('admin.billing.invoice.recordPayment')}</h4>
            <div className="mt-1 grid grid-cols-2 gap-2">
              <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.receivedOn')}</span>
                {/* ⚠ A plain text box, not type="date": a native picker follows the BROWSER's
                    locale and can report no value at all until it is satisfied. */}
                <input type="text" inputMode="numeric" placeholder="YYYY-MM-DD" className={INPUT} value={receivedOn}
                  onChange={(e) => setReceivedOn(e.target.value)} aria-label={t('admin.billing.invoice.receivedOn')} /></label>
              <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.amount')}</span>
                <input type="text" inputMode="decimal" className={INPUT} value={amount}
                  onChange={(e) => setAmount(e.target.value)} aria-label={t('admin.billing.invoice.amount')} /></label>
              <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.method')}</span>
                <select className={INPUT} value={method} onChange={(e) => setMethod(e.target.value)}
                  aria-label={t('admin.billing.invoice.method')}>
                  <option value="bank_transfer">{t('admin.billing.invoice.methods.bank_transfer')}</option>
                  <option value="cheque">{t('admin.billing.invoice.methods.cheque')}</option>
                  <option value="other">{t('admin.billing.invoice.methods.other')}</option>
                </select></label>
              <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.reference')}</span>
                <input type="text" className={INPUT} value={reference}
                  onChange={(e) => setReference(e.target.value)} aria-label={t('admin.billing.invoice.reference')} /></label>
            </div>
            <button type="button" className={`${PRIMARY} mt-2`}
              disabled={busy || reference.trim() === '' || !(Number(amount) > 0)}
              onClick={() => onReceipt(inv, { received_on: receivedOn.trim(), amount_myr: amount.trim(), method, reference: reference.trim() })}>
              {t('admin.billing.invoice.recordAndReceipt')}
            </button>
          </div>
        )}

        {isSuper && canSend(inv) && (
          <div>
            {!confirmSend ? (
              <button type="button" className={SECONDARY} disabled={busy} onClick={() => setConfirmSend(true)}>
                {t(inv.sent_at ? 'admin.billing.invoice.sendAgain' : 'admin.billing.invoice.send')}
              </button>
            ) : (
              /* ⚠ A CONFIRM THAT NAMES THE INBOXES. This is the only moment a bill leaves the
                 building, and the owner's ruling is that a person decides it. */
              <div className="rounded-lg border bg-ground-50 p-2">
                <p className="text-ground-700">{t('admin.billing.invoice.confirmSend', {
                  to: (inv.bill_to_emails || []).join(', '),
                })}</p>
                <div className="mt-2 flex gap-2">
                  <button type="button" className={PRIMARY} disabled={busy}
                    onClick={() => { setConfirmSend(false); onSend(inv) }}>
                    {t('admin.billing.invoice.send')}
                  </button>
                  <button type="button" className={SECONDARY} onClick={() => setConfirmSend(false)}>
                    {t('admin.billing.invoice.cancel')}
                  </button>
                </div>
              </div>
            )}
            {inv.sent_at && (
              <p className="mt-1 text-ground-400">{t('admin.billing.invoice.sentLine', {
                date: formatDay(inv.sent_at), to: (inv.sent_to || []).join(', '), by: inv.sent_by_email || '',
              })}</p>
            )}
          </div>
        )}

        {isSuper && canVoid(inv) && (
          <div>
            <button type="button" className="text-xs text-critical-700 underline" onClick={() => setVoidOpen((v) => !v)}>
              {t('admin.billing.invoice.void')}
            </button>
            {voidOpen && (
              <div className="mt-1 flex flex-wrap items-end gap-2">
                <label className="block flex-1"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.voidReason')}</span>
                  <input type="text" className={INPUT} value={voidReason}
                    onChange={(e) => setVoidReason(e.target.value)} aria-label={t('admin.billing.invoice.voidReason')} /></label>
                <button type="button" className={PRIMARY} disabled={busy || voidReason.trim() === ''}
                  onClick={() => onVoid(inv, voidReason.trim())}>
                  {t('admin.billing.invoice.voidConfirm')}
                </button>
              </div>
            )}
          </div>
        )}

        {isSuper && inv.override_reason && (
          <p className="whitespace-pre-line text-ground-500">{t('admin.billing.invoice.overrideLine', { reason: inv.override_reason })}</p>
        )}
        {isSuper && inv.replaces_number && (
          <p className="text-ground-500">{t('admin.billing.invoice.replaces', { number: inv.replaces_number })}</p>
        )}
      </div>
    </div>
  )
}

function InvoiceTable({ invoices, isSuper, busy, t, token, onSend, onVoid, onReceipt }: {
  invoices: InvoiceRow[]
  isSuper: boolean
  busy: boolean
  t: T
  token: string
  onSend: (inv: InvoiceRow) => void
  onVoid: (inv: InvoiceRow, reason: string) => void
  onReceipt: (inv: InvoiceRow, data: { received_on: string; amount_myr: string; method: string; reference: string }) => void
}) {
  const [open, setOpen] = useState<number | null>(null)
  const cols = isSuper ? 8 : 7
  if (invoices.length === 0) {
    return (
      <p className="rounded-xl border bg-ground-0 p-6 text-center text-sm text-ground-500" data-testid="no-invoices">
        {t(isSuper ? 'admin.billing.invoice.noneSuper' : 'admin.billing.invoice.noneTenant')}
      </p>
    )
  }
  const rows = orderedInvoices(invoices)
  return (
    <>
    {/* ⚠ PHONE CARDS. An invoice is exactly what a finance officer checks on a phone, so this list
        gets the card layout rather than an exemption. Same rows, same open state as the table. */}
    <div className="space-y-3 md:hidden" data-testid="invoice-cards">
      {rows.map((inv) => {
        const isVoid = inv.status === 'void'
        return (
          <div key={inv.id} className="rounded-xl border bg-ground-0 p-4 shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <div>
                <button type="button" aria-expanded={open === inv.id}
                  onClick={() => setOpen((o) => (o === inv.id ? null : inv.id))}
                  className={`font-mono text-[13px] text-primary-600 ${isVoid ? 'line-through' : ''}`}>
                  {inv.number}
                </button>
                <p className="mt-0.5 text-xs text-ground-500">
                  {isSuper ? `${inv.organisation} · ` : ''}{formatMonth(inv.period_month)}
                </p>
              </div>
              <Chip status={inv.status} t={t} isSuper={isSuper} dueOn={inv.due_on} />
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
              <dt className="text-ground-500">{t('admin.billing.invoice.col.total')}</dt>
              <dd className="text-right tabular-nums text-ground-900">{formatMyr(inv.total_myr)}</dd>
              <dt className="text-ground-500">{t('admin.billing.invoice.balance')}</dt>
              <dd className="text-right tabular-nums text-ground-900">{isVoid ? '—' : formatMyr(inv.balance_myr)}</dd>
              <dt className="text-ground-500">{t('admin.billing.invoice.col.due')}</dt>
              <dd className="text-right text-ground-700">{formatDay(inv.due_on)}</dd>
            </dl>
            <button type="button" className={`${SECONDARY} mt-2`}
              onClick={() => downloadPdf('invoice', inv.id, inv.number, token)}>
              {t('admin.billing.invoice.pdf')}
            </button>
            {open === inv.id && (
              <div className="mt-3 border-t pt-3">
                <InvoiceDetail inv={inv} isSuper={isSuper} busy={busy} t={t} token={token}
                  onSend={onSend} onVoid={onVoid} onReceipt={onReceipt} />
              </div>
            )}
          </div>
        )
      })}
    </div>
    <TableFrame className="hidden md:block" minWidth={860} label={t('admin.billing.invoice.title')}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-ground-600">
            <th className="px-4 py-2 text-left font-medium">{t('admin.billing.invoice.col.number')}</th>
            {isSuper && <th className="px-4 py-2 text-left font-medium">{t('admin.billing.invoice.col.organisation')}</th>}
            <th className="px-4 py-2 text-left font-medium">{t('admin.billing.month')}</th>
            <th className="px-4 py-2 text-left font-medium">{t('admin.billing.invoice.col.issued')}</th>
            <th className="px-4 py-2 text-left font-medium">{t('admin.billing.invoice.col.due')}</th>
            <th className="px-4 py-2 text-right font-medium">{t('admin.billing.invoice.col.total')}</th>
            <th className="px-4 py-2 text-right font-medium">{t('admin.billing.invoice.balance')}</th>
            <th className="px-4 py-2 text-left font-medium">{t('admin.billing.invoice.col.status')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((inv) => (
            <InvoiceRowGroup key={inv.id} inv={inv} cols={cols} isOpen={open === inv.id}
              onToggle={() => setOpen((o) => (o === inv.id ? null : inv.id))}
              isSuper={isSuper} busy={busy} t={t} token={token}
              onSend={onSend} onVoid={onVoid} onReceipt={onReceipt} />
          ))}
        </tbody>
      </table>
    </TableFrame>
    </>
  )
}

function InvoiceRowGroup({ inv, cols, isOpen, onToggle, isSuper, busy, t, token, onSend, onVoid, onReceipt }: {
  inv: InvoiceRow
  cols: number
  isOpen: boolean
  onToggle: () => void
  isSuper: boolean
  busy: boolean
  t: T
  token: string
  onSend: (inv: InvoiceRow) => void
  onVoid: (inv: InvoiceRow, reason: string) => void
  onReceipt: (inv: InvoiceRow, data: { received_on: string; amount_myr: string; method: string; reference: string }) => void
}) {
  const isVoid = inv.status === 'void'
  return (
    <>
      <tr className={`border-b ${isVoid ? 'text-ground-400' : ''}`} data-testid={`invoice-${inv.id}`}>
        <td className="px-4 py-2">
          <button type="button" aria-expanded={isOpen} onClick={onToggle}
            className={`font-mono text-[13px] text-primary-600 ${isVoid ? 'line-through' : ''}`}>
            {inv.number}
          </button>
          <button type="button" className={`${SECONDARY} ml-2`}
            onClick={() => downloadPdf('invoice', inv.id, inv.number, token)}>
            {t('admin.billing.invoice.pdf')}
          </button>
        </td>
        {isSuper && <td className="px-4 py-2">{inv.organisation}</td>}
        <td className="px-4 py-2">{formatMonth(inv.period_month)}</td>
        <td className="px-4 py-2">{formatDay(inv.issued_on)}</td>
        <td className="px-4 py-2">{formatDay(inv.due_on)}</td>
        <td className="px-4 py-2 text-right tabular-nums">{formatMyr(inv.total_myr)}</td>
        <td className="px-4 py-2 text-right tabular-nums">{isVoid ? '—' : formatMyr(inv.balance_myr)}</td>
        <td className="px-4 py-2"><Chip status={inv.status} t={t} isSuper={isSuper} dueOn={inv.due_on} /></td>
      </tr>
      {isOpen && (
        <tr className="border-b bg-ground-50/60">
          <td colSpan={cols} className="px-4 py-3">
            <InvoiceDetail inv={inv} isSuper={isSuper} busy={busy} t={t} token={token}
              onSend={onSend} onVoid={onVoid} onReceipt={onReceipt} />
          </td>
        </tr>
      )}
    </>
  )
}

// ── Settings ─────────────────────────────────────────────────────────────────────────────────

// ── The section ──────────────────────────────────────────────────────────────────────────────

export default function InvoicesSection({ token, isSuper, t }: { token: string; isSuper: boolean; t: T }) {
  const [data, setData] = useState<InvoicesPayload | null>(null)
  const [tab, setTab] = useState<Tab>('toissue')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // Blank until a super picks one, and then the server is asked for THAT month. Blank is not a
  // default month held here: the cut-off belongs to the server (`invoicing.previous_month`), and a
  // second copy of it in the browser is a second answer that would eventually disagree.
  const [month, setMonth] = useState('')

  const load = useCallback(() => {
    if (!token) return
    getInvoices({ token, month: month || undefined })
      .then((d) => { setData(d); setError('') })
      .catch((e) => {
        // The dark 404 means billing is not live for this reader: render nothing, as the usage
        // half does. Anything else is a real failure and is said out loud.
        if (/404|not_found/.test(String(e))) setData(null)
        else setError(errorText(e))
      })
  }, [token, month])

  useEffect(() => { load() }, [load])

  const act = useCallback((p: Promise<unknown>, after?: () => void) => {
    setBusy(true)
    p.then(() => { setError(''); after?.(); load() })
      .catch((e) => { setError(errorText(e)); load() })
      .finally(() => setBusy(false))
  }, [load])

  if (!data) return error ? <p className="mt-6 text-sm text-critical-600" role="alert">{error}</p> : null

  const invoices = data.invoices || []

  return (
    <section className="mt-8" data-testid="invoices">
      <h2 className="text-lg font-semibold text-ground-900">{t('admin.billing.invoice.title')}</h2>
      {error && <p className="mt-2 text-sm text-critical-600" role="alert" data-testid="invoice-error">{error}</p>}

      {!isSuper ? (
        <div className="mt-3 space-y-3">
          <p className="text-sm text-ground-500">{t('admin.billing.invoice.tenantLead')}</p>
          <InvoiceTable invoices={invoices} isSuper={false} busy={busy} t={t} token={token}
            onSend={() => {}} onVoid={() => {}} onReceipt={() => {}} />
        </div>
      ) : (
        <>
          <div className="mt-3 flex gap-1 border-b" role="tablist" aria-label={t('admin.billing.invoice.title')}>
            {(['toissue', 'issued'] as Tab[]).map((k) => (
              <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${tab === k
                  ? 'border-primary-600 font-semibold text-ground-900' : 'border-transparent text-ground-500'}`}>
                {t(`admin.billing.invoice.tab.${k}`)}
                {k === 'issued' && invoices.length > 0 && (
                  <span className="ml-1 rounded-full border px-1.5 text-[11px] text-ground-500">{invoices.length}</span>
                )}
              </button>
            ))}
          </div>

          {tab === 'toissue' && (
            // ⚠ `key={data.month}` REMOUNTS the panel on every month change, which is what
            // re-defaults its issue-date box to the 15th of the month after the new choice.
            <InvoiceToIssue key={data.month || ''} data={data} busy={busy} t={t}
              onMonth={setMonth}
              onIssue={(orgId, period, reason, issuedOn) => act(
                issueInvoice({
                  organisation_id: orgId, period_month: period, override_reason: reason,
                  issued_on: issuedOn,
                }, { token }),
                () => setTab('issued'))} />
          )}

          {tab === 'issued' && (
            <div className="mt-4">
              <InvoiceTable invoices={invoices} isSuper busy={busy} t={t} token={token}
                onSend={(inv) => act(sendInvoice(inv.id, { token }))}
                onVoid={(inv, reason) => act(voidInvoice(inv.id, reason, { token }))}
                onReceipt={(inv, d) => act(recordInvoiceReceipt(inv.id, d, { token }))} />
            </div>
          )}

        </>
      )}
    </section>
  )
}
