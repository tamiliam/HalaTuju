'use client'

/** Corrections of an EARLIER month, carried onto this month's bill (owner, 2026-10-29).
 *
 * *"When we have overcharged or undercharged, this should be deducted or added (or written off) in
 * the following month."* An invoice already sent is never edited — that is what a void is for, and
 * a void is a heavy, visible act. A billing MISTAKE is lighter and more common, so it travels
 * forward as its own line.
 *
 * ⚠ **EACH CORRECTION KEEPS ITS OWN WORDS.** The reason is printed on the tenant's invoice, so a
 * netted figure would put a number on a customer's bill that nobody can explain. That is why this
 * renders a row per correction rather than one total.
 *
 * ⚠ It lives in its own file because `src/app/admin/billing/page.tsx` sits in the oversize ledger.
 */

import { useState } from 'react'
import type { BillingCharge } from '@/lib/admin-api'
import { formatMyr } from '@/lib/billingCosts'
import { splitSignedMoney } from '@/lib/invoices'

type T = (k: string, vars?: Record<string, string>) => string

/** Why this correction cannot be recorded — an i18n key suffix — or '' when it can.
 *
 * ⚠ The SERVER decides; this puts the message beside the box. ZERO IS REFUSED on both sides: a
 * correction of nothing is not a decision, and it would print a line on a customer's invoice
 * saying we got something wrong by RM0.00.
 */
export function correctionProblem(amount: string, reason: string): string {
  const text = (amount || '').trim()
  if (text === '') return 'amountRequired'
  if (!/^-?\d+(\.\d{1,2})?$/.test(text)) return 'badAmount'
  if (Number(text) === 0) return 'badAmount'
  if ((reason || '').trim() === '') return 'reasonRequired'
  return ''
}

export function ChargeCorrections({ charge, month, t, busy, onRecord, onRemove }: {
  charge: BillingCharge
  /** The month that CARRIES the correction — not the month that was wrong. */
  month: string
  t: T
  busy: boolean
  onRecord: (organisationId: number, amountMyr: string, reason: string) => void
  onRemove: (id: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')

  const corrections = charge.corrections || []
  const problem = correctionProblem(amount, reason)

  return (
    <>
      {corrections.map((c) => {
        const { negative, magnitude } = splitSignedMoney(c.amount_myr)
        return (
          <div key={c.id} className="flex justify-between gap-4"
            data-testid={`correction-${c.id}`}>
            <dt className="text-ground-600">
              {t(negative ? 'admin.billing.charge.correctionCredit'
                : 'admin.billing.charge.correctionCharge')}
              <span className="block text-xs text-ground-400">
                {c.corrects_invoice ? `${c.corrects_invoice} — ${c.reason}` : c.reason}
              </span>
              {/* ⚠ Removal is offered only until the month is invoiced; after that the server
                  refuses, because the figures are frozen onto the document. The button stays on
                  screen and the refusal is read from the server rather than guessed here. */}
              <button type="button" disabled={busy} onClick={() => onRemove(c.id)}
                className="mt-0.5 text-[11px] text-ground-500 underline disabled:opacity-40">
                {t('admin.billing.charge.correctionRemove')}
              </button>
            </dt>
            <dd className="tabular-nums text-ground-900">
              {negative ? '−' : ''}{formatMyr(magnitude)}
            </dd>
          </div>
        )
      })}
      <div className="mt-1" data-testid={`correction-form-${charge.organisation_id}`}>
        <button type="button" className="text-xs text-ground-500 underline"
          onClick={() => setOpen((v) => !v)}>
          {t('admin.billing.charge.addCorrection')}
        </button>
        {open && (
          <div className="mt-2 grid gap-2 sm:grid-cols-[8rem_1fr_auto] sm:items-end">
            <label className="block">
              <span className="block text-[11px] text-ground-500">
                {t('admin.billing.charge.correctionAmount')}
              </span>
              {/* ⚠ A TEXT box, not type="number": a native numeric input follows the browser
                  locale, and a comma decimal would reach the server as something it refuses. */}
              <input type="text" inputMode="decimal"
                className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
                value={amount} onChange={(e) => setAmount(e.target.value)}
                aria-label={t('admin.billing.charge.correctionAmount')} />
            </label>
            <label className="block">
              <span className="block text-[11px] text-ground-500">
                {t('admin.billing.charge.correctionReason')}
              </span>
              <input type="text"
                className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
                value={reason} onChange={(e) => setReason(e.target.value)}
                aria-label={t('admin.billing.charge.correctionReason')} />
            </label>
            <button type="button" disabled={busy || problem !== ''}
              className="rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
              onClick={() => {
                onRecord(charge.organisation_id, amount.trim(), reason.trim())
                setAmount(''); setReason(''); setOpen(false)
              }}>
              {t('admin.billing.charge.apply')}
            </button>
            {/* The one rule a reader cannot guess from the boxes: a minus means WE owe them. */}
            <p className="text-[11px] text-ground-400 sm:col-span-3">
              {t('admin.billing.charge.correctionHelp', { month })}
            </p>
            {problem && (
              <p className="text-[11px] text-critical-600 sm:col-span-3">
                {t(`admin.billing.charge.correctionError.${problem}`)}
              </p>
            )}
          </div>
        )}
      </div>
    </>
  )
}
