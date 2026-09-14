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
import TableFrame from '@/components/admin/TableFrame'
import {
  fetchBillingPdf, getInvoiceSettings, getInvoices, issueInvoice, recordInvoiceReceipt,
  saveInvoiceIssuer, saveTenantBillingDetails, sendInvoice, voidInvoice,
  type InvoiceProblem, type InvoiceReadiness, type InvoiceRow, type InvoiceSettingsPayload,
  type InvoicesPayload, type TenantBillingDetails,
} from '@/lib/admin-api'
import { formatMyr } from '@/lib/billingCosts'
import { formatMonth } from '@/lib/billingUsage'
import {
  canRecordPayment, canSend, canVoid, formatDay, issueMode, needsSettings, orderedInvoices,
  orderedProblems, splitEmails, statusChip, todayIso,
} from '@/lib/invoices'

type T = (k: string, vars?: Record<string, string>) => string
type Tab = 'toissue' | 'issued' | 'settings'

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

function Chip({ status, t }: { status: InvoiceRow['status']; t: T }) {
  const c = statusChip(status)
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${c.className}`}>
      {t(c.key)}
    </span>
  )
}

// ── To issue ─────────────────────────────────────────────────────────────────────────────────

function ReadinessCard({ row, month, busy, t, onIssue, onGoSettings }: {
  row: InvoiceReadiness
  month: string
  busy: boolean
  t: T
  onIssue: (orgId: number, reason: string) => void
  onGoSettings: () => void
}) {
  const [reason, setReason] = useState('')
  // A month already invoiced is DONE, not "not ready": its other warnings were weighed when it was
  // issued, and re-listing them as blockers would read as an alarm about a settled decision.
  if (row.problems.some((p) => p.code === 'already_issued')) {
    return (
      <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl border bg-ground-0 p-4 shadow-sm"
        data-testid={`readiness-${row.organisation_id}`}>
        <p className="text-sm">
          <span className="font-semibold text-ground-900">{row.organisation}</span>
          <span className="text-ground-400"> · {formatMonth(month)}</span>
        </p>
        <span className="rounded-full bg-info-100 px-2 py-0.5 text-[11px] font-semibold text-info-700">
          {t('admin.billing.invoice.alreadyIssued')}
        </span>
      </div>
    )
  }
  const mode = issueMode(row.problems)
  const chip = mode === 'ready'
    ? { key: 'admin.billing.invoice.ready', cls: 'bg-positive-100 text-positive-700' }
    : mode === 'override'
      ? { key: 'admin.billing.invoice.needsReason', cls: 'bg-caution-100 text-caution-700' }
      : { key: 'admin.billing.invoice.notReady', cls: 'bg-critical-50 text-critical-700' }

  return (
    <div className="rounded-xl border bg-ground-0 p-4 shadow-sm" data-testid={`readiness-${row.organisation_id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm">
          <span className="font-semibold text-ground-900">{row.organisation}</span>
          <span className="text-ground-400"> · {formatMonth(month)}</span>
        </p>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${chip.cls}`}>{t(chip.key)}</span>
      </div>

      {row.problems.length > 0 && (
        <ul className="mt-3 space-y-2">
          {orderedProblems(row.problems).map((p) => (
            <li key={p.code} className="grid grid-cols-[5.5rem_1fr] items-baseline gap-2 text-sm">
              <span className={`w-fit rounded-full px-2 py-0.5 text-[11px] font-semibold ${p.overridable
                ? 'bg-caution-100 text-caution-700' : 'bg-critical-50 text-critical-700'}`}>
                {t(p.overridable ? 'admin.billing.invoice.warning' : 'admin.billing.invoice.mustFix')}
              </span>
              <span className="text-ground-700">{p.message}</span>
            </li>
          ))}
        </ul>
      )}
      {needsSettings(row.problems) && (
        <button type="button" className="mt-2 text-sm text-primary-600 underline" onClick={onGoSettings}>
          {t('admin.billing.invoice.fillSettings')}
        </button>
      )}

      {mode === 'override' && (
        <label className="mt-3 block">
          <span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.overrideReason')}</span>
          <textarea className={`${INPUT} min-h-[4rem]`} value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-label={t('admin.billing.invoice.overrideReason')} />
        </label>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {mode === 'ready' && (
          <button type="button" className={PRIMARY} disabled={busy}
            onClick={() => onIssue(row.organisation_id, '')}>
            {t('admin.billing.invoice.issue')}
          </button>
        )}
        {mode === 'override' && (
          <button type="button" className={PRIMARY} disabled={busy || reason.trim() === ''}
            onClick={() => onIssue(row.organisation_id, reason.trim())}>
            {t('admin.billing.invoice.issueAnyway')}
          </button>
        )}
        {mode === 'blocked' && (
          <>
            {/* Shown disabled rather than hidden: the reader should see there IS an action, and
                that the list above is what stands between them and it. */}
            <button type="button" className={PRIMARY} disabled>{t('admin.billing.invoice.issue')}</button>
            <span className="text-xs text-ground-400">{t('admin.billing.invoice.blockedHelp')}</span>
          </>
        )}
      </div>
    </div>
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
        <tbody className="tabular-nums">
          {inv.lines.map((ln) => (
            <tr key={ln.position} className="border-b">
              <td className="px-2 py-1.5 text-ground-900">{ln.description}</td>
              <td className="px-2 py-1.5 text-right text-ground-700">{ln.quantity ?? ''}</td>
              <td className="px-2 py-1.5 text-right text-ground-700">{ln.unit_amount_myr ? formatMyr(ln.unit_amount_myr) : ''}</td>
              <td className="px-2 py-1.5 text-right text-ground-900">{formatMyr(ln.amount_myr)}</td>
            </tr>
          ))}
          <tr><td colSpan={3} className="px-2 pt-2 text-right text-ground-500">{t('admin.billing.charge.subtotal')}</td>
            <td className="px-2 pt-2 text-right">{formatMyr(inv.subtotal_myr)}</td></tr>
          {Number(inv.discount_myr) > 0 && (
            <tr><td colSpan={3} className="px-2 text-right text-ground-500">
              {t('admin.billing.invoice.discountLine', { pct: String(Number(inv.discount_pct)) })}
              {inv.discount_reason && <span className="block text-[11px] text-ground-400">{inv.discount_reason}</span>}
            </td><td className="px-2 text-right">−{formatMyr(inv.discount_myr)}</td></tr>
          )}
          <tr className="font-semibold"><td colSpan={3} className="border-t border-ground-900 px-2 pt-1.5 text-right">{t('admin.billing.invoice.totalDue')}</td>
            <td className="border-t border-ground-900 px-2 pt-1.5 text-right">{formatMyr(inv.total_myr)}</td></tr>
          {Number(inv.amount_paid_myr) > 0 && (
            <>
              <tr><td colSpan={3} className="px-2 text-right text-ground-500">{t('admin.billing.invoice.paid')}</td>
                <td className="px-2 text-right">−{formatMyr(inv.amount_paid_myr)}</td></tr>
              <tr className="font-semibold"><td colSpan={3} className="px-2 text-right">{t('admin.billing.invoice.balance')}</td>
                <td className="px-2 text-right">{formatMyr(inv.balance_myr)}</td></tr>
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
              <Chip status={inv.status} t={t} />
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
        <td className="px-4 py-2"><Chip status={inv.status} t={t} /></td>
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

const ISSUER_FIELDS: Array<{ key: string; multiline?: boolean }> = [
  { key: 'legal_name' }, { key: 'registration_no' }, { key: 'address', multiline: true },
  { key: 'email' }, { key: 'phone' }, { key: 'bank_name' }, { key: 'bank_account_name' },
  { key: 'bank_account_no' }, { key: 'payment_terms_days' },
]

function SettingsPanel({ settings, busy, t, onSaveIssuer, onSaveTenant }: {
  settings: InvoiceSettingsPayload
  busy: boolean
  t: T
  onSaveIssuer: (values: Record<string, string>) => void
  onSaveTenant: (row: TenantBillingDetails, values: { bill_to_name: string; address: string; emails: string }) => void
}) {
  const [issuer, setIssuer] = useState<Record<string, string>>(() => Object.fromEntries(
    ISSUER_FIELDS.map((f) => [f.key, String((settings.issuer as unknown as Record<string, unknown>)[f.key] ?? '')])))

  return (
    <div className="grid items-start gap-4 lg:grid-cols-2">
      <div className="rounded-xl border bg-ground-0 p-4 shadow-sm" data-testid="issuer-form">
        <h3 className="text-sm font-semibold text-ground-900">{t('admin.billing.invoice.settings.issuerTitle')}</h3>
        <p className="mt-1 text-xs text-ground-500">{t('admin.billing.invoice.settings.issuerSub')}</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {ISSUER_FIELDS.map((f) => {
            const missing = settings.issuer.missing.includes(f.key)
            const cls = `${INPUT} ${missing ? 'border-critical-300' : ''}`
            return (
              <label key={f.key} className={`block ${f.multiline || f.key === 'legal_name' ? 'sm:col-span-2' : ''}`}>
                <span className="block text-[11px] text-ground-500">{t(`admin.billing.invoice.settings.field.${f.key}`)}</span>
                {f.multiline ? (
                  <textarea className={`${cls} min-h-[4rem]`} value={issuer[f.key]}
                    onChange={(e) => setIssuer((v) => ({ ...v, [f.key]: e.target.value }))} />
                ) : (
                  <input type="text" className={cls} value={issuer[f.key]}
                    inputMode={f.key === 'payment_terms_days' ? 'numeric' : undefined}
                    onChange={(e) => setIssuer((v) => ({ ...v, [f.key]: e.target.value }))} />
                )}
              </label>
            )
          })}
        </div>
        <button type="button" className={`${PRIMARY} mt-3`} disabled={busy} onClick={() => onSaveIssuer(issuer)}>
          {t('admin.billing.invoice.settings.save')}
        </button>
      </div>

      <div className="space-y-4">
        {settings.tenants.map((row) => (
          <TenantForm key={row.organisation_id} row={row} busy={busy} t={t} onSave={onSaveTenant} />
        ))}
      </div>
    </div>
  )
}

function TenantForm({ row, busy, t, onSave }: {
  row: TenantBillingDetails
  busy: boolean
  t: T
  onSave: (row: TenantBillingDetails, values: { bill_to_name: string; address: string; emails: string }) => void
}) {
  const [name, setName] = useState(row.bill_to_name)
  const [address, setAddress] = useState(row.address)
  const [emails, setEmails] = useState(row.emails.join(', '))
  const cls = (k: string) => `${INPUT} ${row.missing.includes(k) ? 'border-critical-300' : ''}`
  return (
    <div className="rounded-xl border bg-ground-0 p-4 shadow-sm" data-testid={`bill-to-${row.organisation_id}`}>
      <h3 className="text-sm font-semibold text-ground-900">
        {t('admin.billing.invoice.settings.billToTitle', { organisation: row.organisation })}
      </h3>
      <div className="mt-3 grid gap-2">
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.settings.field.bill_to_name')}</span>
          <input type="text" className={cls('bill_to_name')} value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.settings.field.address')}</span>
          <textarea className={`${cls('address')} min-h-[4rem]`} value={address} onChange={(e) => setAddress(e.target.value)} /></label>
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.settings.field.emails')}</span>
          <input type="text" className={cls('emails')} value={emails} onChange={(e) => setEmails(e.target.value)} /></label>
      </div>
      <button type="button" className={`${PRIMARY} mt-3`} disabled={busy}
        onClick={() => onSave(row, { bill_to_name: name, address, emails })}>
        {t('admin.billing.invoice.settings.save')}
      </button>
    </div>
  )
}

// ── The section ──────────────────────────────────────────────────────────────────────────────

export default function InvoicesSection({ token, isSuper, t }: { token: string; isSuper: boolean; t: T }) {
  const [data, setData] = useState<InvoicesPayload | null>(null)
  const [settings, setSettings] = useState<InvoiceSettingsPayload | null>(null)
  const [tab, setTab] = useState<Tab>('toissue')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!token) return
    getInvoices({ token })
      .then((d) => { setData(d); setError('') })
      .catch((e) => {
        // The dark 404 means billing is not live for this reader: render nothing, as the usage
        // half does. Anything else is a real failure and is said out loud.
        if (/404|not_found/.test(String(e))) setData(null)
        else setError(errorText(e))
      })
    if (isSuper) {
      getInvoiceSettings({ token }).then(setSettings).catch((e) => setError(errorText(e)))
    }
  }, [token, isSuper])

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
            {(['toissue', 'issued', 'settings'] as Tab[]).map((k) => (
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
            <div className="mt-4 space-y-3">
              <p className="text-sm text-ground-500">{t('admin.billing.invoice.superLead', {
                month: formatMonth(data.month || ''), day: String(data.issue_day ?? 15),
              })}</p>
              {(data.readiness || []).map((row) => (
                <ReadinessCard key={row.organisation_id} row={row} month={data.month || ''} busy={busy} t={t}
                  onGoSettings={() => setTab('settings')}
                  onIssue={(orgId, reason) => act(
                    issueInvoice({ organisation_id: orgId, period_month: data.month || '', override_reason: reason }, { token }),
                    () => setTab('issued'))} />
              ))}
            </div>
          )}

          {tab === 'issued' && (
            <div className="mt-4">
              <InvoiceTable invoices={invoices} isSuper busy={busy} t={t} token={token}
                onSend={(inv) => act(sendInvoice(inv.id, { token }))}
                onVoid={(inv, reason) => act(voidInvoice(inv.id, reason, { token }))}
                onReceipt={(inv, d) => act(recordInvoiceReceipt(inv.id, d, { token }))} />
            </div>
          )}

          {tab === 'settings' && settings && (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-ground-500">{t('admin.billing.invoice.settings.lead')}</p>
              <SettingsPanel settings={settings} busy={busy} t={t}
                onSaveIssuer={(v) => {
                  // A blank "days to pay" is left out rather than sent as 0, which would make every
                  // future invoice due on the day it is issued.
                  const { payment_terms_days: days, ...rest } = v
                  const body: Parameters<typeof saveInvoiceIssuer>[0] = { ...rest }
                  if (days.trim() !== '') body.payment_terms_days = Number(days)
                  act(saveInvoiceIssuer(body, { token }))
                }}
                onSaveTenant={(row, v) => act(saveTenantBillingDetails({
                  organisation_id: row.organisation_id, bill_to_name: v.bill_to_name.trim(),
                  address: v.address.trim(), emails: splitEmails(v.emails),
                }, { token }))} />
            </div>
          )}
        </>
      )}
    </section>
  )
}
