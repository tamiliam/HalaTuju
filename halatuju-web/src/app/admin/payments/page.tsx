'use client'
// Payments landing (P2) — the run list + a "New payment run" date dialog. Entered from the
// Administration panel's Payments card (no top-level nav entry); the layout keeps
// "Administration" active here. Access: admin / org_admin / super.

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { getPaymentRuns, createPaymentRun, type PaymentRunSummary } from '@/lib/admin-api'
import { statusPill } from '@/lib/paymentStatus'

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function PaymentsLandingPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()
  const allowed = !!(role?.is_super_admin || role?.role === 'super'
    || role?.role === 'admin' || role?.role === 'org_admin')

  const [runs, setRuns] = useState<PaymentRunSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [payDate, setPayDate] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!token || !allowed) { setLoading(false); return }
    getPaymentRuns({ token })
      .then((d) => setRuns(d.runs))
      .catch(() => setError(t('admin.payments.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, allowed])

  if (role && !allowed) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  const create = async () => {
    if (!token || !payDate) return
    setBusy(true); setError('')
    try {
      const run = await createPaymentRun(payDate, { token })
      router.push(`/admin/payments/${run.id}`)
    } catch (e) {
      const code = (e as { code?: string })?.code
      setError(code === 'past_date' ? t('admin.payments.pastDate')
        : code === 'no_org' ? t('admin.payments.noOrg')
        : (e instanceof Error ? e.message : t('admin.actionFailed')))
      setBusy(false)
    }
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  return (
    <div className="max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('admin.payments.title')}</h1>
          <p className="mt-1 text-sm text-gray-500">{t('admin.payments.subtitle')}</p>
        </div>
        <button onClick={() => { setPayDate(''); setError(''); setDialogOpen(true) }}
          className="shrink-0 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700">
          + {t('admin.payments.newRun')}
        </button>
      </div>

      {error && <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-600">{error}</div>}

      <div className="mt-6 bg-white rounded-xl shadow-sm border overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-gray-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-gray-500">
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.reference')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.paymentDate')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.status')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.students')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.total')}</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((r) => (
              <tr key={r.id} className="hover:bg-blue-50/40">
                <td className="px-4 py-3">
                  <Link href={`/admin/payments/${r.id}`} className="font-medium text-blue-600 hover:underline">{r.reference}</Link>
                </td>
                <td className="px-4 py-3 text-gray-600">{formatDate(r.payment_date)}</td>
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
            {!loading && runs.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">{t('admin.payments.empty')}</td></tr>
            )}
            {loading && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">{t('common.loading')}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setDialogOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900">{t('admin.payments.newRun')}</h2>
            <label className="mt-4 block text-sm font-medium text-gray-700">{t('admin.payments.paymentDate')}</label>
            <input type="date" min={todayISO()} value={payDate} onChange={(e) => setPayDate(e.target.value)} className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-gray-500">{t('admin.payments.pastDateHint')}</p>
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
