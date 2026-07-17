'use client'
// Payment run detail (P2) — eligibility table (editable in draft), greyed skipped list,
// two-stage maker→approver sign-off, and the completed state (Drive link + CSV download).
// Access: admin / org_admin / super. Entered from the Payments landing.

import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import {
  getPaymentRun, updatePaymentRunItem, signPaymentRun, cancelPaymentRun, fetchPaymentRunCsv,
  type PaymentRunDetail,
} from '@/lib/admin-api'
import { statusPill, monthLabel, monthLabelFull } from '@/lib/paymentStatus'
import Toggle from '@/components/Toggle'

// Amounts are whole ringgit with thousands grouping — "RM 2,200", never "RM 200.00"
// (a genuine .50 would still show). Hand-formatted so server and browser render identically.
const rm = (v: string | number) => {
  const n = Number(v)
  return Number.isFinite(n) ? String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',') : String(v)
}

type SortKey = 'name' | 'nric' | 'vircle_id' | 'paid_to_date'

const errText = (e: unknown, t: (k: string) => string) => {
  const code = (e as { code?: string })?.code
  const known = ['name_mismatch', 'same_signer', 'wrong_role', 'past_date', 'amount_over_cap',
                 'reason_required', 'not_draft', 'not_editable', 'bad_state', 'not_ready']
  return code && known.includes(code) ? t(`admin.payments.error.${code}`)
    : e instanceof Error ? e.message : t('admin.actionFailed')
}

export default function PaymentRunDetailPage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = !!(role?.is_super_admin || role?.role === 'super'
    || role?.role === 'admin' || role?.role === 'org_admin')

  const [run, setRun] = useState<PaymentRunDetail | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [makerName, setMakerName] = useState('')
  const [approverName, setApproverName] = useState('')
  const [signError, setSignError] = useState('')   // shown inside the sign-off card, beside the action
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' } | null>(null)

  const load = useCallback(() => {
    if (!token) return
    getPaymentRun(id, { token }).then(setRun).catch(() => setError(t('admin.payments.loadFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])
  useEffect(() => { if (allowed) load() }, [allowed, load])

  if (role && !allowed) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>
  if (!run) return <p className="text-gray-400">{t('common.loading')}</p>

  const isDraft = run.status === 'draft'
  const isCompleted = run.status === 'completed'

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s?.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))
  const sortedItems = (() => {
    if (!sort) return run.items
    const dir = sort.dir === 'asc' ? 1 : -1
    return [...run.items].sort((a, b) => {
      if (sort.key === 'paid_to_date') return (Number(a.paid_to_date) - Number(b.paid_to_date)) * dir
      return String(a[sort.key] || '').localeCompare(String(b[sort.key] || '')) * dir
    })
  })()
  const sortArrow = (key: SortKey) => (sort?.key === key ? (sort.dir === 'asc' ? ' ↑' : ' ↓') : '')
  const SortTh = ({ k, label }: { k: SortKey; label: string }) => (
    <th className="px-4 py-3 font-semibold">
      <button type="button" onClick={() => toggleSort(k)} className="inline-flex items-center uppercase tracking-wider hover:text-gray-700">
        {label}<span className="text-gray-400">{sortArrow(k)}</span>
      </button>
    </th>
  )

  const patchItem = async (itemId: number, patch: { included?: boolean; exclude_reason?: string; amount?: string }) => {
    if (!token) return
    setError('')
    try { setRun(await updatePaymentRunItem(id, itemId, patch, { token })) }
    catch (e) { setError(errText(e, t)) }
  }

  const sign = async (typed: string) => {
    if (!token || !typed.trim()) return
    setBusy('sign'); setSignError('')
    try { setRun(await signPaymentRun(id, typed.trim(), { token })); setMakerName(''); setApproverName('') }
    catch (e) { setSignError(errText(e, t)) } finally { setBusy('') }
  }

  const doCancel = async () => {
    if (!token) return
    setBusy('cancel'); setSignError('')
    try { setRun(await cancelPaymentRun(id, { token })) }
    catch (e) { setSignError(errText(e, t)) } finally { setBusy('') }
  }

  const downloadCsv = async () => {
    if (!token) return
    try {
      const text = await fetchPaymentRunCsv(id, { token })
      const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
      const a = document.createElement('a')
      a.href = url; a.download = `${run.reference}.csv`; a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setError(errText(e, t)) }
  }

  const appHref = (appId: number) => `/admin/scholarship/${appId}`
  const inputCls = 'px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

  return (
    <div className="max-w-5xl">
      <nav className="text-xs text-gray-400">
        <a href="/admin/payments" className="hover:underline">{t('admin.payments.title')}</a>
        <span className="mx-1">/</span><span className="text-gray-600">{run.reference}</span>
      </nav>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">{run.reference}</h1>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusPill(run.status)}`}>{t(`admin.payments.status.${run.status}`)}</span>
        </div>
        {/* Two-segment stat card (Stitch design): STUDENTS | TOTAL AMOUNT */}
        <div className="flex rounded-xl border bg-white shadow-sm divide-x">
          <div className="px-5 py-2 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{t('admin.payments.studentsHeading')}</p>
            <p className="text-xl font-bold text-gray-900 tabular-nums leading-tight">{run.students}</p>
          </div>
          <div className="px-5 py-2 text-center">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{t('admin.payments.totalAmountHeading')}</p>
            <p className="text-xl font-bold text-primary-500 tabular-nums leading-tight">RM {rm(run.total)}</p>
          </div>
        </div>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        {t('admin.payments.col.paymentDate')}: {formatDate(run.payment_date)}
        {run.period_month && <> · {t('admin.payments.col.month')}: <span className="font-medium text-gray-700">{monthLabel(run.period_month)}</span></>}
      </p>

      {error && <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-600">{error}</div>}

      {/* Students table */}
      <div className="mt-5 bg-white rounded-xl shadow border overflow-x-auto">
        <table className="w-full text-sm min-w-[840px]">
          <thead className="bg-gray-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-gray-500">
              <SortTh k="name" label={t('admin.payments.col.name')} />
              <SortTh k="nric" label={t('admin.payments.col.nric')} />
              <SortTh k="vircle_id" label={t('admin.payments.col.vircleId')} />
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.awardApproved')}</th>
              <SortTh k="paid_to_date" label={t('admin.payments.col.paidToDate')} />
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.amountToPay')}</th>
              <th className="px-4 py-3 font-semibold">{t('admin.payments.col.include')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sortedItems.map((it) => (
              <tr key={it.id} className={it.included ? 'hover:bg-primary-50/40' : 'bg-gray-50/60 text-gray-400'}>
                <td className="px-4 py-3.5">
                  <a href={appHref(it.application_id)} target="_blank" rel="noopener noreferrer" className="font-medium text-blue-600 hover:underline">{it.name || '—'} ↗</a>
                </td>
                <td className="px-4 py-3.5">{it.nric || '—'}</td>
                <td className="px-4 py-3.5">
                  <div className="tabular-nums">{it.vircle_id || '—'}</div>
                </td>
                <td className="px-4 py-3.5 tabular-nums">RM {rm(it.award_amount)}</td>
                <td className="px-4 py-3.5 tabular-nums">RM {rm(it.paid_to_date)}</td>
                <td className="px-4 py-3.5">
                  {isDraft && it.included ? (
                    <input defaultValue={rm(it.amount)} onBlur={(e) => { if (e.target.value !== rm(it.amount)) patchItem(it.id, { amount: e.target.value }) }}
                      className="w-24 rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm tabular-nums focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                  ) : (
                    <span className="tabular-nums">RM {rm(it.amount)}</span>
                  )}
                  {Number(it.credit_applied) > 0 && (
                    <p className="mt-0.5 text-[11px] italic text-primary-500">{t('admin.payments.creditApplied', { amount: rm(it.credit_applied) })}</p>
                  )}
                </td>
                <td className="px-4 py-3.5">
                  {isDraft ? (
                    <div className="space-y-1.5">
                      <Toggle on={it.included} label={t('admin.payments.col.include')}
                        onChange={(v) => patchItem(it.id, v ? { included: true } : { included: false, exclude_reason: it.exclude_reason || t('admin.payments.defaultReason') })} />
                      {!it.included && (
                        <input defaultValue={it.exclude_reason} placeholder={t('admin.payments.reasonPlaceholder')}
                          onBlur={(e) => { if (e.target.value !== it.exclude_reason) patchItem(it.id, { included: false, exclude_reason: e.target.value }) }}
                          className={`block w-40 ${inputCls}`} />
                      )}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <Toggle on={it.included} disabled label={t('admin.payments.col.include')} onChange={() => {}} />
                      {!it.included && <p className="text-xs">{it.exclude_reason || '—'}</p>}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-primary-50 border-t border-primary-100">
            <tr>
              <td colSpan={7} className="px-4 py-4">
                <div className="flex items-center justify-end gap-4">
                  <span className="text-sm font-medium text-gray-600">{t('admin.payments.totalToPay')}</span>
                  <span className="text-2xl font-bold text-gray-900 tabular-nums">RM {rm(run.total)}</span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Skipped this run */}
      {run.skipped.length > 0 && (
        <div className="mt-4 rounded-xl border bg-white p-4">
          <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-500">🚫 {t('admin.payments.skippedTitle')}</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {run.skipped.map((s) => (
              <div key={s.application_id} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500">
                <span className="font-medium text-gray-600">{s.name || '—'}</span>
                <span className="mx-1">—</span>
                {s.reasons.map((r) => t(`admin.payments.reason.${r}`)).join(', ')}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sign-off */}
      {!isCompleted && run.status !== 'cancelled' && (
        <div className="mt-4 rounded-xl border bg-white p-5">
          <h2 className="text-base font-semibold text-gray-900">{t('admin.payments.signOff')}</h2>
          <p className="mt-2 rounded-lg border border-blue-100 bg-blue-50/60 p-3 text-sm text-gray-700 italic">
            {t('admin.payments.declaration', { month: monthLabelFull(run.period_month), email: run.vircle_email || '—' })}
          </p>
          {signError && <div className="mt-3 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-600">{signError}</div>}
          <div className="mt-3 grid gap-6 sm:grid-cols-2">
            <div>
              <p className="text-sm font-semibold text-gray-900">1 · {t('admin.payments.makerStep')}</p>
              {run.admin_signed ? (
                <p className="mt-1 text-sm text-green-700">✓ {run.admin_signed.name}</p>
              ) : (<>
                <p className="mt-1 text-xs text-gray-500">{t('admin.payments.typedNameHint')}</p>
                <div className="mt-2 flex gap-2">
                  <input value={makerName} onChange={(e) => setMakerName(e.target.value)} className={`flex-1 ${inputCls}`} placeholder={t('admin.payments.fullName')} />
                  <button onClick={() => sign(makerName)} disabled={!!busy || !makerName.trim()} className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">{t('admin.payments.sign')}</button>
                </div>
              </>)}
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">2 · {t('admin.payments.approverStep')}</p>
              {run.status === 'draft' ? (
                <p className="mt-1 text-xs text-gray-400">{t('admin.payments.afterMaker')}</p>
              ) : (<>
                <p className="mt-1 text-xs text-gray-500">{t('admin.payments.typedNameHint')}</p>
                <div className="mt-2 flex gap-2">
                  <input value={approverName} onChange={(e) => setApproverName(e.target.value)} className={`flex-1 ${inputCls}`} placeholder={t('admin.payments.fullName')} />
                  <button onClick={() => sign(approverName)} disabled={!!busy || !approverName.trim()} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">{t('admin.payments.countersign')}</button>
                </div>
              </>)}
            </div>
          </div>
          <p className="mt-3 text-xs text-gray-500">{t('admin.payments.signNote')}</p>
          <button onClick={doCancel} disabled={!!busy} className="mt-3 text-xs font-medium text-red-600 hover:text-red-800 disabled:opacity-50">{t('admin.payments.cancelRun')}</button>
        </div>
      )}

      {/* Completed */}
      {isCompleted && (
        <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-5">
          <p className="font-semibold text-green-800">✓ {t('admin.payments.completedBanner')}</p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 text-sm text-gray-700">
            {run.admin_signed && <div><p className="text-xs uppercase tracking-wide text-gray-500">{t('admin.payments.makerStep')}</p><p className="font-medium">{run.admin_signed.name}</p><p className="text-xs text-gray-500">{formatDate(run.admin_signed.at)}</p></div>}
            {run.org_admin_signed && <div><p className="text-xs uppercase tracking-wide text-gray-500">{t('admin.payments.approverStep')}</p><p className="font-medium">{run.org_admin_signed.name}</p><p className="text-xs text-gray-500">{formatDate(run.org_admin_signed.at)}</p></div>}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-4">
            {run.drive_file_url && <a href={run.drive_file_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-blue-600 hover:underline">{t('admin.payments.openInDrive')}</a>}
            <button onClick={downloadCsv} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">{t('admin.payments.downloadCsv')}</button>
          </div>
        </div>
      )}
    </div>
  )
}
