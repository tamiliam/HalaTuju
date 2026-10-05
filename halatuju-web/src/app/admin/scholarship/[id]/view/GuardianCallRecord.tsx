'use client'

/**
 * "Record call" beside the parent/guardian phone (request #26, the owner's consent framing of
 * 2026-10-05): reasonable, RECORDED steps that the parent is on board — not fraud prevention.
 *
 * Super + org_admin only (the caller decides who sees it; `AdminGuardianCallView` refuses everyone
 * else, with the correction's organisation fence). The outcome is chosen explicitly. For
 * "Parent's number corrected" the number typed here IS stored as the parent phone in the same
 * action, so the number on file is exactly the number recorded as called; every other outcome is
 * about the number already on file. "Could not reach" asks no consent — nobody was spoken to.
 *
 * At MODULE scope deliberately (lessons.md): declared inside a page body it would remount on every
 * render and steal focus mid-typing.
 */
import { useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { recordGuardianCall, type GuardianCallOutcome } from '@/lib/admin-api'
import { isValidMobile, toLocalPhone } from '@/lib/guardianPhone'
import { GUARDIAN_REFUSAL } from './GuardianCorrect'
import type { T } from './shared'

const OUTCOMES: GuardianCallOutcome[] = [
  'shared_confirmed', 'parent_number_confirmed', 'parent_number_corrected', 'could_not_reach',
]

export function GuardianCallRecord({ appId, phone, t, onDone }: {
  appId: number
  phone: string
  t: T
  onDone?: () => void | Promise<void>
}) {
  const { token } = useAdminAuth()
  const [open, setOpen] = useState(false)
  const [outcome, setOutcome] = useState<GuardianCallOutcome | ''>('')
  const [consent, setConsent] = useState(false)
  const [number, setNumber] = useState('')
  const [parentName, setParentName] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const corrected = outcome === 'parent_number_corrected'
  const reached = outcome !== '' && outcome !== 'could_not_reach'
  const ready = outcome !== '' && (!corrected || isValidMobile(number))

  const begin = () => {
    setOutcome(''); setConsent(false); setNumber(''); setParentName(''); setNote(''); setError('')
    setOpen(true)
  }
  const save = async () => {
    if (!token || !outcome) return
    setBusy(true); setError('')
    try {
      await recordGuardianCall(appId, {
        outcome, consent: reached ? consent : null, number: corrected ? toLocalPhone(number) : '',
        parent_name: parentName.trim(), note: note.trim(),
      }, { token })
      setOpen(false)
      await onDone?.()
    } catch (e) {
      setError(t(GUARDIAN_REFUSAL[(e as Error & { code?: string }).code || ''] || 'errors.somethingWentWrong'))
    } finally { setBusy(false) }
  }

  if (!open) {
    return (
      <button type="button" onClick={begin} className="ml-2 text-xs font-medium text-primary-600 hover:underline">
        {t('admin.scholarship.guardianRecordCall')}
      </button>
    )
  }
  const field = 'w-full rounded-md border border-ground-300 px-2 py-1.5 text-sm'
  return (
    <div role="dialog" aria-label={t('admin.scholarship.guardianRecordCall')} className="mt-2 space-y-2 rounded-lg border border-ground-200 bg-ground-50 p-3">
      <select aria-label={t('admin.scholarship.guardianRecordCall')} value={outcome} onChange={e => setOutcome(e.target.value as GuardianCallOutcome | '')} className={field}>
        <option value="">—</option>
        {OUTCOMES.map(o => <option key={o} value={o}>{t(`admin.scholarship.guardianCallOutcome.${o}`)}</option>)}
      </select>
      {corrected
        ? <input aria-label={t('scholarship.apply.field.parentPhone')} value={number} onChange={e => setNumber(toLocalPhone(e.target.value))} inputMode="tel" placeholder="012-345 6789" className={field} />
        : <p className="text-xs text-ground-500">{t('scholarship.apply.field.parentPhone')}: {phone ? toLocalPhone(phone) : '—'}</p>}
      {corrected && number.trim() !== '' && !isValidMobile(number) && <p className="text-xs text-critical-600">{t('scholarship.apply.error.phone')}</p>}
      {reached && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
          {t('admin.scholarship.guardianCallConsent')}
        </label>
      )}
      <input aria-label={t('scholarship.apply.field.parentName')} placeholder={t('scholarship.apply.field.parentName')} value={parentName} onChange={e => setParentName(e.target.value)} maxLength={255} className={field} />
      <textarea aria-label={t('admin.requests.detail.quoteNote')} placeholder={t('admin.requests.detail.quoteNote')} value={note} onChange={e => setNote(e.target.value)} maxLength={2000} rows={2} className={field} />
      {error && <p role="alert" className="text-xs text-critical-600">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={() => setOpen(false)} className="rounded-md border border-ground-300 px-3 py-1.5 text-xs font-medium text-ground-700">
          {t('common.cancel')}
        </button>
        <button type="button" onClick={save} disabled={busy || !ready} className="rounded-md bg-brand-fill px-3 py-1.5 text-xs font-medium text-brand-fill-ink disabled:opacity-50">
          {busy ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  )
}
