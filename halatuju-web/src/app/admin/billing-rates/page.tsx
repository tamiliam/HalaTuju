'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { getBillingRates, setBillingRate, type BillingRateRow } from '@/lib/admin-api'
import {
  rateGrid, formatMyr, formatPct, rateMonthOptions, RATE_MONTHS_BACK,
} from '@/lib/billingCosts'

/**
 * Billing rates — the platform-side numbers that turn cost and effort into a charge.
 *
 * Owner, 2026-09-11: *"we need to build the billing rate screen, where we could enter margins,
 * rates, markups, etc."* The endpoint for it shipped on 2026-07-27 and then sat unread for six
 * weeks; this is the page that was missing, and the nav's one legitimate reserved slot.
 *
 * ⚠ **SAVING NEVER EDITS A RATE. IT ADDS ONE.** Every save writes a new row dated from the month
 * you pick, and the old value stays exactly where it was. That is what stops a rate typed in
 * September silently re-pricing an August invoice that has already gone out. The page has to SAY
 * so, in words, above the form — the whole mechanism is invisible otherwise, and a screen that
 * looks like it overwrites will be used as if it does.
 *
 * ⚠ **An unset rate is drawn, not hidden.** `rateGrid` returns every (category, kind) pair
 * including the ones nobody has set, because the hourly rate being blank is the most important
 * thing this screen can tell anyone: until it exists, no development work can be billed at all.
 * A row that is not drawn says nothing. A row that says "not set" gets acted on.
 *
 * ⚠ **The date is a MONTH picker, not a date input.** A rate is only ever applied from the first
 * of a billed month (`platform_cost._month_start`), and a native date box follows the browser's
 * own locale — the same trap that made a time field untypeable and left Save asleep with no
 * error. A plain `<select>` of months has no locale and no silent empty state.
 */

// ⚠ `rateMonthOptions` lives in `@/lib/billingCosts`, not here. A Next.js page file may export
// nothing but `default` and the framework's own reserved names — exporting a helper alongside the
// component fails the production build, which is where this was caught.

function RateCard({
  category, kind, current, history, t, onSave, saving,
}: {
  category: string
  kind: string
  current: BillingRateRow | null
  history: BillingRateRow[]
  t: (k: string, vars?: Record<string, string>) => string
  onSave: (category: string, kind: string, value: string, month: string, note: string) => void
  saving: boolean
}) {
  const months = useMemo(() => rateMonthOptions(new Date()), [])
  const thisMonth = months[RATE_MONTHS_BACK]
  const [value, setValue] = useState('')
  const [month, setMonth] = useState(thisMonth)
  const [note, setNote] = useState('')
  const [open, setOpen] = useState(false)

  const isMargin = kind === 'margin_pct'
  const shown = current
    ? (isMargin ? formatPct(current.value) : formatMyr(current.value))
    : null

  return (
    <div className="rounded-xl border bg-ground-0 p-4 shadow-sm" data-testid={`rate-${category}-${kind}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ground-900">
            {t(`admin.billingRates.category.${category}`)}
          </h2>
          <p className="text-xs text-ground-500">{t(`admin.billingRates.kind.${kind}`)}</p>
        </div>
        <div className="text-right">
          {shown ? (
            <>
              <p className="text-2xl font-semibold text-ground-900">{shown}</p>
              <p className="text-[11px] text-ground-400">
                {t('admin.billingRates.inForceSince', { date: current!.effective_from })}
              </p>
            </>
          ) : (
            /* ⚠ NOT a dash and NOT "RM0.00". A rate nobody has set makes the charge REFUSE to be
               computed, which is the whole design — so the screen says exactly that. */
            <p className="text-sm font-semibold text-caution-700" data-testid="rate-not-set">
              {t('admin.billingRates.notSet')}
            </p>
          )}
        </div>
      </div>

      {current?.note && <p className="mt-2 text-xs text-ground-500">{current.note}</p>}
      {current?.updated_by_email && (
        <p className="mt-0.5 text-[11px] text-ground-400">
          {t('admin.billingRates.setBy', { email: current.updated_by_email })}
        </p>
      )}
      {!current && (
        <p className="mt-2 text-xs text-caution-700">{t(`admin.billingRates.blocked.${category}`)}</p>
      )}

      <div className="mt-4 grid gap-2 sm:grid-cols-[7rem_10rem_1fr_auto] sm:items-end">
        <label className="block">
          <span className="block text-[11px] text-ground-500">
            {isMargin ? t('admin.billingRates.newMargin') : t('admin.billingRates.newRate')}
          </span>
          <input
            type="number" min="0" step="0.01" inputMode="decimal"
            className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-label={t(`admin.billingRates.category.${category}`) + ' ' + t(`admin.billingRates.kind.${kind}`)}
          />
        </label>
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.billingRates.from')}</span>
          <select
            className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            aria-label={t('admin.billingRates.from')}
          >
            {months.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="block text-[11px] text-ground-500">{t('admin.billingRates.why')}</span>
          <input
            type="text"
            className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            aria-label={t('admin.billingRates.why')}
          />
        </label>
        <button
          type="button"
          disabled={saving || value.trim() === ''}
          className="rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          onClick={() => onSave(category, kind, value.trim(), month, note.trim())}
        >
          {t('admin.billingRates.save')}
        </button>
      </div>

      {history.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            className="text-xs text-ground-500 underline"
            onClick={() => setOpen((v) => !v)}
          >
            {t('admin.billingRates.history', { n: String(history.length) })}
          </button>
          {open && (
            <ul className="mt-2 space-y-1" data-testid={`history-${category}-${kind}`}>
              {history.map((h) => (
                <li key={h.id} className="text-xs text-ground-500">
                  <span className="font-medium text-ground-700">
                    {isMargin ? formatPct(h.value) : formatMyr(h.value)}
                  </span>
                  {' · '}{t('admin.billingRates.inForceSince', { date: h.effective_from })}
                  {h.note ? ` · ${h.note}` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function AdminBillingRatesPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/billing-rates', effectiveRole(role))

  const [rows, setRows] = useState<BillingRateRow[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    getBillingRates({ token })
      .then((d) => { setRows(d.rates); setError('') })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => { load() }, [load])

  const save = useCallback((
    category: string, kind: string, value: string, month: string, note: string,
  ) => {
    if (!token) return
    setSaving(true)
    setError('')
    // A rate always takes effect on the FIRST of the chosen month, which is the only day
    // `rate_in_force` is ever asked about.
    setBillingRate({ category, kind, value, effective_from: `${month}-01`, note }, { token })
      // ⚠ Re-read rather than patch the row in place. A save ADDS a row, so the card's
      // "in force" value and its history both change — patching would leave one of them stale
      // with nothing failing.
      .then(() => load())
      .catch((e) => setError(String(e)))
      .finally(() => setSaving(false))
  }, [token, load])

  if (role && !mayView) {
    return <p className="text-critical-600 p-6">{t('apiErrors.superAdminRequired')}</p>
  }
  if (loading && rows === null) {
    return <p className="p-6 text-ground-500">{t('admin.billingRates.loading')}</p>
  }

  const grid = rateGrid(rows)

  return (
    <div>
      <h1 className="text-xl font-bold text-ground-900">{t('admin.billingRates.title')}</h1>
      <p className="mt-1 text-sm text-ground-500">{t('admin.billingRates.subtitle')}</p>

      {/* ⚠ The one sentence that makes the whole mechanism visible. Without it the page looks
          like it overwrites a number, and it will be used as if it does. */}
      <p className="mt-3 rounded-lg bg-info-50 px-3 py-2 text-xs text-info-800">
        {t('admin.billingRates.neverRetroactive')}
      </p>

      {error && <p className="mt-3 text-sm text-critical-600" role="alert">{error}</p>}

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {grid.map((r) => (
          <RateCard
            key={`${r.category}-${r.kind}`}
            category={r.category}
            kind={r.kind}
            current={r.current}
            history={r.history}
            t={t}
            onSave={save}
            saving={saving}
          />
        ))}
      </div>
    </div>
  )
}
