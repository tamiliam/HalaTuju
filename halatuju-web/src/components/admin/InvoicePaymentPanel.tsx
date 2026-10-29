'use client'

/**
 * "We have paid this" — the tenant's side, and the owner's side of the same claim (2026-10-29).
 *
 * The owner read BrightPath's own billing page and said there was *"no way for the client to enter
 * anything to claim settlement"*. This panel is that way in, and the owner's queue for checking it.
 *
 * TWO AUDIENCES, ONE PANEL, the split decided by `isSuper`:
 *  - org_admin — a date and a bank reference, nothing else. No amount (the invoice states it) and
 *    no slip; both were asked about and ruled out on 2026-10-29.
 *  - super — the claim as the tenant wrote it, with the amount READ OFF THE BANK, then Confirm
 *    (which raises the receipt) or Not found (which needs a reason the tenant is shown).
 *
 * ⚠ **NOTHING HERE IS MONEY UNTIL THE OWNER CONFIRMS.** A declaration raises no receipt and moves
 * no balance. It lives in its own panel, away from Record payment, so the two are never mistaken
 * for one another on the screen either.
 *
 * It owns no data and no fetch: the parent hands it a row and three callbacks, like every other
 * part of the invoice detail.
 */
import { useState } from 'react'
import type { InvoicePaymentDeclarationRow, InvoiceRow } from '@/lib/admin-api'
import { formatMyr } from '@/lib/billingCosts'
import {
  canDeclarePayment, formatDay, lastRejectedDeclaration, openDeclaration, todayIso,
} from '@/lib/invoices'

type T = (k: string, vars?: Record<string, string>) => string

const INPUT = 'mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm text-ground-900'
const PRIMARY = 'rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50'
const SECONDARY = 'rounded-lg border bg-ground-0 px-2.5 py-1 text-xs text-ground-700 hover:bg-ground-50 disabled:opacity-50'

export interface InvoicePaymentPanelProps {
  inv: InvoiceRow
  isSuper: boolean
  busy: boolean
  t: T
  onDeclare: (inv: InvoiceRow, data: { paid_on: string; reference: string }) => void
  onConfirm: (inv: InvoiceRow, data: {
    declaration_id: number; amount_myr: string; received_on: string; reference: string
  }) => void
  onReject: (inv: InvoiceRow, data: { declaration_id: number; reason: string }) => void
}

/** The tenant's form: a date and a reference. */
function DeclareForm({ inv, busy, t, onDeclare }: {
  inv: InvoiceRow; busy: boolean; t: T
  onDeclare: InvoicePaymentPanelProps['onDeclare']
}) {
  const [paidOn, setPaidOn] = useState(todayIso())
  const [reference, setReference] = useState('')
  return (
    <div data-testid={`declare-${inv.id}`}>
      <h4 className="text-xs font-semibold text-ground-900">{t('admin.billing.invoice.declare.title')}</h4>
      <p className="mt-0.5 text-[11px] text-ground-500">{t('admin.billing.invoice.declare.help')}</p>
      <div className="mt-1 grid grid-cols-2 gap-2">
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.declare.paidOn')}</span>
          {/* ⚠ A plain text box, not type="date": a native picker follows the BROWSER's locale and
              can report no value at all until it is satisfied. Same rule as Record payment. */}
          <input type="text" inputMode="numeric" placeholder="YYYY-MM-DD" className={INPUT} value={paidOn}
            onChange={(e) => setPaidOn(e.target.value)} aria-label={t('admin.billing.invoice.declare.paidOn')} /></label>
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.declare.reference')}</span>
          <input type="text" className={INPUT} value={reference}
            onChange={(e) => setReference(e.target.value)} aria-label={t('admin.billing.invoice.declare.reference')} /></label>
      </div>
      <button type="button" className={`${PRIMARY} mt-2`}
        disabled={busy || reference.trim() === '' || paidOn.trim() === ''}
        onClick={() => onDeclare(inv, { paid_on: paidOn.trim(), reference: reference.trim() })}>
        {t('admin.billing.invoice.declare.submit')}
      </button>
    </div>
  )
}

/** The owner's side of an open claim: the tenant's words, then Confirm or Not found. */
function CheckForm({ inv, declaration, busy, t, onConfirm, onReject }: {
  inv: InvoiceRow; declaration: InvoicePaymentDeclarationRow; busy: boolean; t: T
  onConfirm: InvoicePaymentPanelProps['onConfirm']
  onReject: InvoicePaymentPanelProps['onReject']
}) {
  // ⚠ The amount defaults to the BALANCE, not to anything the tenant said — they were never
  // asked. It is editable because the figure that counts is the one on the statement.
  const [amount, setAmount] = useState(inv.balance_myr)
  const [receivedOn, setReceivedOn] = useState(declaration.paid_on)
  const [reference, setReference] = useState(declaration.reference)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [reason, setReason] = useState('')
  return (
    <div data-testid={`check-${inv.id}`}>
      <h4 className="text-xs font-semibold text-ground-900">{t('admin.billing.invoice.declare.checkTitle')}</h4>
      <p className="mt-0.5 text-[11px] text-ground-500">
        {t('admin.billing.invoice.declare.checkHelp', {
          amount: formatMyr(inv.balance_myr),
          date: formatDay(declaration.paid_on),
          reference: declaration.reference,
        })}
      </p>
      <div className="mt-1 grid grid-cols-2 gap-2">
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.amount')}</span>
          <input type="text" inputMode="decimal" className={INPUT} value={amount}
            onChange={(e) => setAmount(e.target.value)} aria-label={t('admin.billing.invoice.amount')} /></label>
        <label className="block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.receivedOn')}</span>
          <input type="text" inputMode="numeric" placeholder="YYYY-MM-DD" className={INPUT} value={receivedOn}
            onChange={(e) => setReceivedOn(e.target.value)} aria-label={t('admin.billing.invoice.receivedOn')} /></label>
        <label className="col-span-2 block"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.reference')}</span>
          <input type="text" className={INPUT} value={reference}
            onChange={(e) => setReference(e.target.value)} aria-label={t('admin.billing.invoice.reference')} /></label>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button type="button" className={PRIMARY}
          disabled={busy || !(Number(amount) > 0) || reference.trim() === '' || receivedOn.trim() === ''}
          onClick={() => onConfirm(inv, {
            declaration_id: declaration.id, amount_myr: amount.trim(),
            received_on: receivedOn.trim(), reference: reference.trim(),
          })}>
          {t('admin.billing.invoice.declare.confirm')}
        </button>
        <button type="button" className="text-xs text-critical-700 underline"
          onClick={() => setRejectOpen((v) => !v)}>
          {t('admin.billing.invoice.declare.notFound')}
        </button>
      </div>
      {rejectOpen && (
        <div className="mt-1 flex flex-wrap items-end gap-2">
          <label className="block flex-1"><span className="block text-[11px] text-ground-500">{t('admin.billing.invoice.declare.reason')}</span>
            <input type="text" className={INPUT} value={reason}
              onChange={(e) => setReason(e.target.value)} aria-label={t('admin.billing.invoice.declare.reason')} /></label>
          <button type="button" className={SECONDARY} disabled={busy || reason.trim() === ''}
            onClick={() => onReject(inv, { declaration_id: declaration.id, reason: reason.trim() })}>
            {t('admin.billing.invoice.declare.notFoundConfirm')}
          </button>
        </div>
      )}
    </div>
  )
}

export default function InvoicePaymentPanel(props: InvoicePaymentPanelProps) {
  const { inv, isSuper, busy, t, onDeclare, onConfirm, onReject } = props
  const open = openDeclaration(inv)
  const rejected = lastRejectedDeclaration(inv)

  return (
    <div className="space-y-3">
      {/* The tenant is TOLD their claim arrived. Being unsure anyone noticed is the complaint
          this whole feature answers, so the acknowledgement is not optional. */}
      {open && !isSuper && (
        <p className="text-ground-700" data-testid={`declared-${inv.id}`}>
          {t('admin.billing.invoice.declare.waiting', {
            date: formatDay(open.paid_on), reference: open.reference,
          })}
        </p>
      )}
      {/* A rejection is shown to BOTH sides, with the reason. "Not found" with no reason leaves a
          customer guessing at their own bank. */}
      {rejected && (
        <p className="text-critical-700" data-testid={`rejected-${inv.id}`}>
          {t('admin.billing.invoice.declare.rejectedLine', {
            date: formatDay(rejected.paid_on), reason: rejected.reject_reason,
          })}
        </p>
      )}
      {open && isSuper && (
        <CheckForm inv={inv} declaration={open} busy={busy} t={t}
          onConfirm={onConfirm} onReject={onReject} />
      )}
      {!isSuper && canDeclarePayment(inv) && (
        <DeclareForm inv={inv} busy={busy} t={t} onDeclare={onDeclare} />
      )}
    </div>
  )
}
