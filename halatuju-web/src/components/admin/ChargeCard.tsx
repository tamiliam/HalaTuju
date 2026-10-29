'use client'

/** One tenant's bill for one month.
 *
 * Moved VERBATIM out of `src/app/admin/billing/page.tsx` on 2026-10-29 (moves only, plus the
 * corrections row this sprint adds): that page sits in the oversize ledger, and the standard asks
 * for a SPLIT rather than for prose to be trimmed until the number passes.
 *
 * ⚠ Every line is shown and THEN discounted. The owner's July rule — *"we do not bill anything for
 * July. 100% discount. But show the values."* — only works if the subtotal survives to the screen.
 * The month reads: subtotal -> discount -> corrections -> charged.
 */

import { useState } from 'react'
import type { BillingCharge } from '@/lib/admin-api'
import { formatHours, formatMyr, formatPct } from '@/lib/billingCosts'
import { formatMonth } from '@/lib/billingUsage'
import { ChargeCorrections } from '@/components/admin/ChargeCorrections'

/** One tenant's bill: every line shown, THEN the discount. The owner's July rule — shown in
 *  full, charged nothing — only works if the subtotal survives to the screen. */
export function ChargeCard({ charge, month, t, onDiscount, onCorrection, onRemoveCorrection, busy }: {
  charge: BillingCharge
  month: string
  t: (k: string, vars?: Record<string, string>) => string
  onDiscount: (orgId: number, pct: string, reason: string) => void
  onCorrection: (orgId: number, amountMyr: string, reason: string) => void
  onRemoveCorrection: (id: number) => void
  busy: boolean
}) {
  const [open, setOpen] = useState(false)
  const [pct, setPct] = useState('100')
  const [reason, setReason] = useState('')

  return (
    <div className="rounded-xl border bg-ground-0 p-4 shadow-sm"
      data-testid={`charge-${charge.organisation_id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ground-900">{charge.organisation}</h3>
        <span className="text-2xl font-semibold text-ground-900">{formatMyr(charge.charged_myr)}</span>
      </div>

      <dl className="mt-3 space-y-1 text-sm">
        {charge.lines.map((ln) => (
          <div key={ln.category} className="flex justify-between gap-4">
            <dt className="text-ground-600">
              {t(`admin.billing.charge.line.${ln.category}`)}
              {ln.hours ? (
                <>
                  <span className="text-ground-400">
                    {' · '}{t('admin.billing.charge.workedAt', {
                      hours: formatHours(ln.hours),
                      rate: formatMyr(ln.rate_myr),
                      margin: formatPct(ln.margin_pct),
                    })}
                  </span>
                  {/* ⚠ WHAT THE TOOLS COST US, beside what the hours are charged at. Shown,
                      never added — the hourly rate already recovers it, and adding it would
                      take the same ringgit twice. It exists so "is the rate enough?" is a
                      figure on a screen rather than a feeling. */}
                  {ln.tool_cost_myr && Number(ln.tool_cost_myr) > 0 && (
                    <span className="block text-[11px] text-ground-400">
                      {t('admin.billing.charge.toolCost', { cost: formatMyr(ln.tool_cost_myr) })}
                    </span>
                  )}
                </>
              ) : (
                /* ⚠ WHAT WE PAID, BESIDE WHAT WE CHARGE. A single marked-up figure hides the
                   markup, and the markup is the thing the reader is here to check. */
                <span className="text-ground-400">
                  {' · '}{t('admin.billing.charge.costPlus', {
                    cost: formatMyr(ln.cost_myr),
                    margin: formatPct(ln.margin_pct),
                  })}
                </span>
              )}
              {/* The tenant's share of a platform-wide cost, and the rule behind it. With one
                  tenant this reads 100% — which is exactly when it is worth writing down. */}
              {ln.share_pct && (
                <span className="block text-[11px] text-ground-400">
                  {t('admin.billing.charge.share', { pct: formatPct(ln.share_pct) })}
                  {ln.share_rule ? ` — ${ln.share_rule}` : ''}
                </span>
              )}
            </dt>
            <dd className="tabular-nums text-ground-900">{formatMyr(ln.amount_myr)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 border-t pt-1">
          <dt className="text-ground-600">{t('admin.billing.charge.subtotal')}</dt>
          <dd className="tabular-nums text-ground-900">{formatMyr(charge.subtotal_myr)}</dd>
        </div>
        {/* ⚠ The discount is its own LINE, never a quietly smaller total. A waiver you cannot see
            is indistinguishable from a bug that produced zero. */}
        {Number(charge.discount_pct) > 0 && (
          <div className="flex justify-between gap-4" data-testid="discount-line">
            <dt className="text-ground-600">
              {t('admin.billing.charge.discount', { pct: formatPct(charge.discount_pct) })}
              {charge.discount_reason && (
                <span className="block text-xs text-ground-400">{charge.discount_reason}</span>
              )}
            </dt>
            <dd className="tabular-nums text-ground-900">−{formatMyr(charge.discount_myr)}</dd>
          </div>
        )}
        {/* ⚠ AFTER the discount, and never folded into it: a discount is a percentage of THIS
            month's work, a correction a fixed sum putting an earlier bill right. Discounting one
            would shrink a refund we owe, and July's 100% discount would have erased it. */}
        <ChargeCorrections charge={charge} month={month} t={t} busy={busy}
          onRecord={onCorrection} onRemove={onRemoveCorrection} />
        <div className="flex justify-between gap-4 border-t pt-1 font-semibold">
          <dt className="text-ground-900">{t('admin.billing.charge.charged')}</dt>
          <dd className="tabular-nums text-ground-900">{formatMyr(charge.charged_myr)}</dd>
        </div>
      </dl>

      {/* ⚠ Every category we could NOT price, with its reason. Never rendered as RM0.00 —
          a line the reader can see is missing gets fixed; a zero gets believed. */}
      {charge.blocked.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid={`blocked-${charge.organisation_id}`}>
          {charge.blocked.map((b) => (
            <li key={b.category} className="rounded-lg bg-ground-50 px-3 py-2 text-xs text-ground-600">
              <span className="font-medium text-ground-700">
                {t(`admin.billing.charge.line.${b.category}`)}
              </span>
              {' — '}{b.reason}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3">
        <button type="button" className="text-xs text-ground-500 underline"
          onClick={() => setOpen((v) => !v)}>
          {t('admin.billing.charge.setDiscount', { month: formatMonth(month) })}
        </button>
        {open && (
          <div className="mt-2 grid gap-2 sm:grid-cols-[6rem_1fr_auto] sm:items-end">
            <label className="block">
              <span className="block text-[11px] text-ground-500">{t('admin.billing.charge.pct')}</span>
              <input type="number" min="0" max="100" step="0.01" inputMode="decimal"
                className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
                value={pct} onChange={(e) => setPct(e.target.value)}
                aria-label={t('admin.billing.charge.pct')} />
            </label>
            <label className="block">
              <span className="block text-[11px] text-ground-500">{t('admin.billing.charge.reason')}</span>
              <input type="text"
                className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
                value={reason} onChange={(e) => setReason(e.target.value)}
                aria-label={t('admin.billing.charge.reason')} />
            </label>
            <button type="button"
              /* The reason is required here as well as on the server, so the refusal is a
                 disabled button rather than a round-trip and an error message. */
              disabled={busy || reason.trim() === ''}
              /* The console's default disabled button, same as the rates screen's Save. */
              className="rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
              onClick={() => onDiscount(charge.organisation_id, pct.trim(), reason.trim())}>
              {t('admin.billing.charge.apply')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
