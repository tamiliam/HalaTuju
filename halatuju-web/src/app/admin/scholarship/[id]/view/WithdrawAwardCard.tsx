'use client'

/**
 * A1.13 (TD-198 / CO-09, owner ruling D3 2026-11-08): WITHDRAW AN AWARD. Super admins only, on an
 * awarded case, with a required reason that stays internal (the student is told only that the
 * offer was withdrawn). The case returns to the pool and the unpaid award goes back to the
 * sponsor's balance. A case with a paid tranche (released or returned) is refused (TD-591), so the
 * card shows a note instead of the button. The reason prompt is the decision reopen's `ReasonBox`.
 */
import { useState } from 'react'
import { withdrawAward, type AdminScholarshipDetail } from '@/lib/admin-api'

import { ReasonBox } from './ReasonBox'
import type { T } from './shared'

/** The refusal codes the API answers with; anything else falls back to the generic message. */
const KNOWN_ERRORS = ['reason_required', 'reason_too_long', 'not_awarded', 'has_payments'] as const

/** Has money gone out on this case (a released or returned tranche)? Mirrors the API's rule. */
export function hasPaidTranche(app: AdminScholarshipDetail): boolean {
  return (app.disbursements ?? []).some((d) => d.status === 'released' || d.status === 'returned')
}

export function WithdrawAwardCard({
  app, t, isSuper, token, onWithdrawn,
}: {
  app: AdminScholarshipDetail
  t: T
  isSuper: boolean
  token: string | null | undefined
  onWithdrawn: (next: AdminScholarshipDetail) => void
}) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!isSuper || app.status !== 'awarded') return null
  const paid = hasPaidTranche(app)

  const confirm = async () => {
    if (!token || !reason.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const next = await withdrawAward(app.id, reason.trim(), { token })
      setOpen(false)
      setReason('')
      onWithdrawn(next)
    } catch (err) {
      const code = (err as { code?: string })?.code
      setError(KNOWN_ERRORS.includes(code as (typeof KNOWN_ERRORS)[number])
        ? t(`admin.scholarship.withdrawAward.error.${code}`)
        : t('admin.scholarship.withdrawAward.error.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section data-testid="withdraw-award"
      className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-ground-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-3">
      <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.withdrawAward.title')}</h2>
      <p className="text-xs text-ground-600">{t('admin.scholarship.withdrawAward.hint')}</p>
      {paid ? (
        <p className="text-xs text-caution-800">{t('admin.scholarship.withdrawAward.paidNote')}</p>
      ) : open ? (
        <ReasonBox
          title={t('admin.scholarship.withdrawAward.dialogTitle')}
          hint={t('admin.scholarship.withdrawAward.dialogHint')}
          placeholder={t('admin.scholarship.withdrawAward.placeholder')}
          confirmLabel={t('admin.scholarship.withdrawAward.confirm')}
          workingLabel={t('common.loading')} cancelLabel={t('common.cancel')}
          value={reason} onChange={setReason} onConfirm={confirm}
          onCancel={() => { setOpen(false); setReason(''); setError('') }}
          disabled={busy} working={busy} />
      ) : (
        <button onClick={() => setOpen(true)}
          className="px-3 py-1.5 border border-critical-200 rounded-lg text-sm text-critical-700 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
          {t('admin.scholarship.withdrawAward.action')}
        </button>
      )}
      {error && <p role="alert" className="text-xs text-critical-700">{error}</p>}
    </section>
  )
}
