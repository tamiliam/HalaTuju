'use client'
// Student spending (sponsor spending S4) — the officer's view of what students bought, by SHOP,
// and the one correction that outranks every rung of the sorter.
//
// Access: super / org_admin / admin. ⚠ `finance` is DELIBERATELY ABSENT, unlike the neighbouring
// Payments page: `_b40_scope` promises a finance admin never sees student data beyond the Payments
// allowlist, and this screen carries names beside purchases. The backend refuses it too — this is
// not the fence, only the door.
//
// ⚠ THE ROW IS A SHOP, NOT A PAYMENT. You fix a shop once and every payment at it follows; a
// per-payment screen would ask the same question forty times for one stall.
//
// ⚠ THE CATEGORY CONTROL IS A NATIVE `<select>` AND MUST STAY ONE. `TableFrame` establishes two
// clipping contexts (rounded corners + the horizontal scroller), so a hand-rolled absolute
// dropdown inside a cell is sliced off at the table's edge — that really happened on the Intake
// years badge (2026-09-08) and the owner reported it as a panel that opens and cannot be seen. A
// native select's list is drawn by the browser outside the document, so it cannot be clipped.
// `page.test.tsx` pins this.

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { formatDate } from '@/lib/formatDate'
import {
  getSpendingOverview, setSpendingCategory, type SpendingOverview,
} from '@/lib/admin-api'

// Thousands grouping, hand-formatted so server and browser render identically (no locale drift).
// ⚠ The value arrives as a STRING and is never parsed to a Number and back — this is money.
const rm = (v: string) => {
  const [whole, cents = '00'] = String(v).split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`
}

/** The pill under "How we decided". Only `owner` — your own answer — carries the accent. */
function decidedPill(decidedBy: string) {
  return decidedBy === 'owner'
    ? 'bg-info-100 text-info-700'
    : 'bg-ground-100 text-ground-600'
}

export default function SpendingPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = canAccess('/admin/spending', effectiveRole(role))

  const [data, setData] = useState<SpendingOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState('')

  const load = useCallback(() => {
    if (!token || !allowed) { setLoading(false); return }
    getSpendingOverview({ token })
      .then(setData)
      .catch(() => setError(t('admin.spending.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed])

  useEffect(() => { load() }, [load])

  // ⚠ Re-read the whole overview after a correction rather than patching the row in place. One
  // change moves the shop's category, every payment at it, and all four figures at the top; a
  // local patch would leave the headline percentage disagreeing with the table under it.
  async function correct(merchant: string, category: string) {
    if (!token) return
    setSaving(merchant)
    setError('')
    try {
      await setSpendingCategory(merchant, category, { token })
      const fresh = await getSpendingOverview({ token })
      setData(fresh)
    } catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['unknown_merchant', 'unknown_category', 'merchant_required']
      setError(known.includes(code)
        ? t(`admin.spending.error.${code}`)
        : t('admin.spending.saveFailed'))
    } finally {
      setSaving('')
    }
  }

  if (role && !allowed) {
    return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const totals = data?.totals
  const categories = data?.categories ?? []

  return (
    <div>
      <h1 className="text-2xl font-semibold text-ground-900">{t('admin.spending.title')}</h1>
      <p className="mt-1 text-sm text-ground-600">{t('admin.spending.subtitle')}</p>

      {error && <p className="mt-4 text-sm text-critical-600" role="alert">{error}</p>}

      {/* ── the four figures. Every one COMPUTED by the server; none is an estimate. ── */}
      <dl className="mt-6 grid grid-cols-2 gap-6 border-b border-ground-200 pb-6 md:grid-cols-4"
        data-testid="spending-totals">
        {[
          ['spent', totals ? `RM${rm(totals.spent)}` : '—'],
          ['sorted', totals ? `${totals.placed_pct}%` : '—'],
          ['unsorted', totals ? `RM${rm(totals.unplaced)}` : '—'],
          ['toCheck', totals ? String(totals.merchants_to_check) : '—'],
        ].map(([key, value]) => (
          <div key={key}>
            <dt className="text-[11px] font-semibold uppercase tracking-wider text-ground-500">
              {t(`admin.spending.stat.${key}`)}
            </dt>
            <dd className="mt-1 text-xl font-medium tabular-nums text-ground-900">{value}</dd>
          </div>
        ))}
      </dl>

      {/* ── the shops, and the correction ── */}
      {/* ── PHONE: one card per shop (the console standard, owner 2026-09-08). A six-column table
          dragged sideways is safe but wrong-shaped for the screen people actually check things on.
          The SHOP and its category lead, because this list is scanned for what to correct.
          ⚠ The student table below stays table-only on purpose: four short numeric columns that
          already fit, the same reasoning the billing page's exemption records. ── */}
      <div className="mt-6 space-y-2.5 md:hidden" data-testid="merchant-cards">
        {(data?.merchants ?? []).map((m) => (
          <div key={m.merchant}
            className="rounded-xl border border-ground-200 bg-ground-0 p-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-semibold text-ground-900">{m.merchant}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${decidedPill(m.decided_by)}`}>
                {t(`admin.spending.by.${m.decided_by || 'none'}`)}
              </span>
            </div>
            <div className="mt-2">
              <select
                aria-label={`${t('admin.spending.col.countedAs')} — ${m.merchant}`}
                className="w-full rounded-md border border-ground-200 bg-ground-0 px-2 py-1.5 text-sm text-ground-700"
                value={m.category || 'unsorted'}
                disabled={saving === m.merchant}
                onChange={(e) => correct(m.merchant, e.target.value)}
              >
                {categories.map((c) => (
                  <option key={c.code} value={c.code}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ground-600">
              <span className="tabular-nums">RM{rm(m.total)}</span>
              <span>{t('admin.spending.col.visits')}{' '}
                <span className="tabular-nums">{m.visits}</span></span>
              {m.last_seen && <span>{formatDate(m.last_seen)}</span>}
            </div>
            {m.held_back > 0 && (
              <p className="mt-1 text-[11px] text-ground-500">
                {t('admin.spending.heldBack', { count: String(m.held_back) })}
              </p>
            )}
          </div>
        ))}
        {!loading && (data?.merchants ?? []).length === 0 && (
          <p className="py-6 text-center text-sm text-ground-400">{t('admin.spending.empty')}</p>
        )}
      </div>

      <TableFrame className="mt-6 hidden md:block" minWidth={760} label={t('admin.spending.title')}>
        <table className="w-full text-sm">
          <thead className="bg-ground-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
              <th className="px-4 py-3 font-semibold">{t('admin.spending.col.shop')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.spending.col.countedAs')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.spending.col.decidedBy')}</th>
              <th className="px-4 py-3 text-right font-semibold">{t('admin.spending.col.visits')}</th>
              <th className="px-4 py-3 text-right font-semibold">{t('admin.spending.col.total')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.spending.col.lastSeen')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ground-100">
            {(data?.merchants ?? []).map((m) => (
              <tr key={m.merchant} className="hover:bg-info-50/40">
                <td className="px-4 py-3 font-medium text-ground-900">
                  {m.merchant}
                  {m.held_back > 0 && (
                    <span className="mt-0.5 block text-[11px] font-normal text-ground-500">
                      {t('admin.spending.heldBack', { count: String(m.held_back) })}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {/* ⚠ NATIVE select — see the file header. Do not replace with a custom panel. */}
                  <select
                    aria-label={`${t('admin.spending.col.countedAs')} — ${m.merchant}`}
                    className="rounded-md border border-ground-200 bg-ground-0 px-2 py-1 text-sm text-ground-700"
                    value={m.category || 'unsorted'}
                    disabled={saving === m.merchant}
                    onChange={(e) => correct(m.merchant, e.target.value)}
                  >
                    {categories.map((c) => (
                      <option key={c.code} value={c.code}>{c.label}</option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${decidedPill(m.decided_by)}`}>
                    {t(`admin.spending.by.${m.decided_by || 'none'}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ground-700">{m.visits}</td>
                <td className="px-4 py-3 text-right font-medium tabular-nums text-ground-900">
                  RM{rm(m.total)}
                </td>
                <td className="px-4 py-3 text-ground-500">
                  {m.last_seen ? formatDate(m.last_seen) : '—'}
                </td>
              </tr>
            ))}
            {!loading && (data?.merchants ?? []).length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ground-400">
                {t('admin.spending.empty')}
              </td></tr>
            )}
          </tbody>
        </table>
      </TableFrame>

      <p className="mt-2 text-xs text-ground-500">{t('admin.spending.kept')}</p>

      {/* ── by student ── */}
      <h2 className="mt-10 text-lg font-semibold text-ground-900">
        {t('admin.spending.students.title')}
      </h2>
      <TableFrame className="mt-3" minWidth={560} label={t('admin.spending.students.title')}>
        <table className="w-full text-sm">
          <thead className="bg-ground-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
              <th className="px-4 py-3 font-semibold">{t('admin.spending.students.name')}</th>
              <th className="px-4 py-3 text-right font-semibold">{t('admin.spending.students.payments')}</th>
              <th className="px-4 py-3 text-right font-semibold">{t('admin.spending.students.spent')}</th>
              <th className="px-4 py-3 text-right font-semibold">{t('admin.spending.students.unsorted')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ground-100">
            {(data?.students ?? []).map((s) => (
              <tr key={s.application_id}>
                <td className="px-4 py-3 text-ground-900">{s.name}</td>
                <td className="px-4 py-3 text-right tabular-nums text-ground-700">{s.payments}</td>
                <td className="px-4 py-3 text-right tabular-nums text-ground-900">RM{rm(s.spent)}</td>
                <td className="px-4 py-3 text-right tabular-nums text-ground-500">RM{rm(s.unplaced)}</td>
              </tr>
            ))}
            {!loading && (data?.students ?? []).length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-ground-400">
                {t('admin.spending.students.empty')}
              </td></tr>
            )}
          </tbody>
        </table>
      </TableFrame>

      {/* ── what the model decided lately ── */}
      <h2 className="mt-10 text-lg font-semibold text-ground-900">
        {t('admin.spending.model.title')}
      </h2>
      <p className="mt-1 text-sm text-ground-600">{t('admin.spending.model.help')}</p>
      <ul className="mt-3 space-y-1.5" data-testid="model-decisions">
        {(data?.model_decisions ?? []).map((d) => (
          <li key={d.merchant} className="flex flex-wrap items-baseline gap-x-3 text-sm">
            <span className="font-medium text-ground-900">{d.merchant}</span>
            <span className="text-ground-600">
              {categories.find((c) => c.code === d.category)?.label ?? d.category}
            </span>
            {d.decided_at && (
              <span className="text-xs text-ground-400">{formatDate(d.decided_at.slice(0, 10))}</span>
            )}
          </li>
        ))}
        {!loading && (data?.model_decisions ?? []).length === 0 && (
          <li className="text-sm text-ground-400">{t('admin.spending.model.empty')}</li>
        )}
      </ul>

      {/* ── the two wallet gaps that ARE derivable. The third reaches staff by email. ── */}
      <h2 className="mt-10 text-lg font-semibold text-ground-900">
        {t('admin.spending.gaps.title')}
      </h2>
      <div className="mt-3 space-y-2 text-sm" data-testid="wallet-gaps">
        {(data?.wallet_gaps.students_without_wallet ?? []).length > 0 && (
          <p className="text-ground-700">
            {t('admin.spending.gaps.noWallet')}:{' '}
            <span className="tabular-nums">
              {(data?.wallet_gaps.students_without_wallet ?? []).join(', ')}
            </span>
          </p>
        )}
        {Object.keys(data?.wallet_gaps.shared_wallets ?? {}).length > 0 && (
          <p className="text-ground-700">
            {t('admin.spending.gaps.shared')}:{' '}
            <span className="tabular-nums">
              {Object.entries(data?.wallet_gaps.shared_wallets ?? {})
                .map(([wallet, ids]) => `${wallet} (${ids.join(', ')})`)
                .join(' · ')}
            </span>
          </p>
        )}
        {!loading
          && (data?.wallet_gaps.students_without_wallet ?? []).length === 0
          && Object.keys(data?.wallet_gaps.shared_wallets ?? {}).length === 0 && (
          <p className="text-ground-400">{t('admin.spending.gaps.none')}</p>
        )}
        <p className="text-xs text-ground-500">{t('admin.spending.gaps.note')}</p>
      </div>
    </div>
  )
}
