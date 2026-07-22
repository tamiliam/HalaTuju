'use client'
// Payments landing (P2) — the run list, a "New payment run" date dialog, and the funding
// summary. Entered from the Administration panel's Payments card (no top-level nav entry); the
// layout keeps "Administration" active here.
// Access: admin / org_admin / finance / super. Finance may READ everything here but creates
// nothing — the "New payment run" control is hidden for it (the backend 403s it anyway).

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  getPaymentRuns, createPaymentRun, getFundingSummary,
  type PaymentRunSummary, type FundingSummary,
} from '@/lib/admin-api'
import { statusPill, monthLabel } from '@/lib/paymentStatus'

// Whole ringgit with thousands grouping, matching the run-detail table ("RM 2,200").
// Hand-formatted so server and browser render identically (no locale drift).
const rm = (v: string | number) => {
  const n = Number(v)
  return Number.isFinite(n) ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',') : String(v)
}

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function PaymentsLandingPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()
  const allowed = !!(role?.is_super_admin || role?.role === 'super'
    || role?.role === 'admin' || role?.role === 'org_admin' || role?.role === 'finance')
  const canCreate = allowed && role?.role !== 'finance'

  const [runs, setRuns] = useState<PaymentRunSummary[]>([])
  const [funding, setFunding] = useState<FundingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [payDate, setPayDate] = useState('')
  const [payMonth, setPayMonth] = useState('')   // 'YYYY-MM'; defaults to the pay date's month
  const [busy, setBusy] = useState(false)
  // A cancelled run is never deleted (the service has no delete — `payments.cancel` only flips
  // the status, so a superseded run stays on the record). It is still clutter on the list, so
  // hide it behind a toggle rather than dropping it: the row explains, e.g., why a re-created
  // run is referenced `PR-2026-07-26-02`. Client-side — the list is one run per month per org
  // and is fetched whole, so a query param would split filtering across two layers for nothing
  // (same call as the sponsor pool's status filter, decisions.md 2026-07-21).
  const [showCancelled, setShowCancelled] = useState(false)

  useEffect(() => {
    if (!token || !allowed) { setLoading(false); return }
    getPaymentRuns({ token })
      .then((d) => setRuns(d.runs))
      .catch(() => setError(t('admin.payments.loadFailed')))
      .finally(() => setLoading(false))
    // Best-effort: the funding summary is a supplementary section, so a failure here hides it
    // rather than breaking the runs list this page exists for.
    getFundingSummary({ token }).then(setFunding).catch(() => setFunding(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed])

  if (role && !allowed) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  const cancelledCount = runs.filter((r) => r.status === 'cancelled').length
  const visibleRuns = showCancelled ? runs : runs.filter((r) => r.status !== 'cancelled')

  const create = async () => {
    if (!token || !payDate) return
    setBusy(true); setError('')
    try {
      const run = await createPaymentRun(payDate, payMonth || payDate.slice(0, 7), { token })
      router.push(`/admin/payments/${run.id}`)
    } catch (e) {
      const code = (e as { code?: string })?.code
      // 'too_early' = advance pay before the 25th of the month preceding the covered month.
      // The backend sends the earliest valid date with the error (the rule lives only in
      // payments.earliest_payment_date), so we name it rather than restate the rule here.
      const earliest = String((e as { body?: { earliest?: string } })?.body?.earliest ?? '')
      setError(code === 'past_date' ? t('admin.payments.pastDate')
        : code === 'too_early' ? t('admin.payments.tooEarly', { date: earliest || '' })
        : code === 'no_org' ? t('admin.payments.noOrg')
        : (e instanceof Error ? e.message : t('admin.actionFailed')))
      setBusy(false)
    }
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  return (
    <div className="max-w-4xl font-plex">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('admin.payments.title')}</h1>
          <p className="mt-1 text-sm text-gray-500">{t('admin.payments.subtitle')}</p>
        </div>
        {canCreate && (
          <button onClick={() => { setPayDate(''); setPayMonth(''); setError(''); setDialogOpen(true) }}
            className="shrink-0 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700">
            + {t('admin.payments.newRun')}
          </button>
        )}
      </div>

      {error && <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-600">{error}</div>}

      <div className="mt-6 bg-white rounded-xl shadow-sm border overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-gray-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-gray-500">
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.reference')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.paymentDate')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.month')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.status')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.students')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.total')}</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {visibleRuns.map((r) => (
              <tr key={r.id} className="hover:bg-blue-50/40">
                <td className="px-4 py-3">
                  <Link href={`/admin/payments/${r.id}`} className="font-medium text-blue-600 hover:underline">{r.reference}</Link>
                </td>
                <td className="px-4 py-3 text-gray-600">{formatDate(r.payment_date)}</td>
                <td className="px-4 py-3 text-gray-600">{monthLabel(r.period_month)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusPill(r.status)}`}>
                    {t(`admin.payments.status.${r.status}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700 tabular-nums">{r.students}</td>
                <td className="px-4 py-3 text-gray-900 font-medium tabular-nums">RM {Number(r.total)}</td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/admin/payments/${r.id}`} className="text-gray-400 hover:text-blue-600">›</Link>
                </td>
              </tr>
            ))}
            {!loading && visibleRuns.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">{t('admin.payments.empty')}</td></tr>
            )}
            {loading && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">{t('common.loading')}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Only offered when there is something to reveal — no dead control on a clean list. */}
      {!loading && cancelledCount > 0 && (
        <button type="button" onClick={() => setShowCancelled((v) => !v)}
          className="mt-3 text-xs font-medium text-gray-500 hover:text-gray-700">
          {showCancelled
            ? t('admin.payments.hideCancelled')
            : t('admin.payments.showCancelled', { count: String(cancelledCount) })}
        </button>
      )}

      {/* Funding summary — the funding-side view of the same cohort the runs pay. Server-side
          allowlist (FundingSummaryRowSerializer); names are plain text, never links into an
          applicant page (finance has no B40 route, and a role-dependent link is worse than
          none for everyone). */}
      {funding && funding.rows.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-bold text-gray-900">{t('admin.payments.funding.title')}</h2>
          <p className="mt-1 text-sm text-gray-500">{t('admin.payments.funding.subtitle')}</p>
          <div className="mt-3 bg-white rounded-xl shadow-sm border overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead className="bg-gray-50 border-b">
                <tr className="text-left text-xs uppercase tracking-wider text-gray-500">
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.student')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.status')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.award')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.paid')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.remaining')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.wallet')}</th>
                  <th className="px-4 py-3 font-semibold">{t('admin.payments.funding.col.lastRun')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {funding.rows.map((r) => (
                  <tr key={r.application_id} className="hover:bg-blue-50/40">
                    <td className="px-4 py-3">
                      <span className="font-medium text-gray-900">{r.name || '—'}</span>
                      {r.ref && <span className="ml-2 text-xs text-gray-400">{r.ref}</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{r.status ? t(`admin.payments.funding.state.${r.status}`) : '—'}</td>
                    <td className="px-4 py-3 text-gray-700 tabular-nums">RM {rm(r.award_amount)}</td>
                    <td className="px-4 py-3 text-gray-700 tabular-nums">RM {rm(r.paid_to_date)}</td>
                    <td className="px-4 py-3 font-medium text-gray-900 tabular-nums">RM {rm(r.remaining)}</td>
                    <td className="px-4 py-3 text-gray-500 tabular-nums">{r.vircle_id || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">
                      {r.last_run ? `${r.last_run.reference} · ${formatDate(r.last_run.payment_date)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-primary-50 border-t border-primary-100 font-semibold text-gray-900">
                <tr>
                  <td className="px-4 py-3">{t('admin.payments.funding.totals', { count: String(funding.totals.students) })}</td>
                  <td className="px-4 py-3" />
                  <td className="px-4 py-3 tabular-nums">RM {rm(funding.totals.award_total)}</td>
                  <td className="px-4 py-3 tabular-nums">RM {rm(funding.totals.paid_total)}</td>
                  <td className="px-4 py-3 tabular-nums">RM {rm(funding.totals.remaining_total)}</td>
                  <td className="px-4 py-3" colSpan={2} />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setDialogOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900">{t('admin.payments.newRun')}</h2>
            <label className="mt-4 block text-sm font-medium text-gray-700">{t('admin.payments.paymentDate')}</label>
            <input type="date" min={todayISO()} value={payDate} onChange={(e) => setPayDate(e.target.value)} className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-gray-500">{t('admin.payments.pastDateHint')}</p>
            <label className="mt-4 block text-sm font-medium text-gray-700">{t('admin.payments.paymentMonth')}</label>
            <input type="month" value={payMonth || payDate.slice(0, 7)} onChange={(e) => setPayMonth(e.target.value)} className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-gray-500">{t('admin.payments.paymentMonthHint')}</p>
            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
            <div className="mt-5 flex items-center justify-end gap-3">
              <button onClick={() => setDialogOpen(false)} disabled={busy} className="text-sm font-medium text-gray-500 hover:text-gray-700">{t('common.cancel')}</button>
              <button onClick={create} disabled={busy || !payDate} className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                {busy ? t('common.loading') : t('admin.payments.createDraft')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
