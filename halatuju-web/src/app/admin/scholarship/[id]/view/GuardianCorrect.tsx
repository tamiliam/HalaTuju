'use client'

/**
 * "Correct" beside the parent/guardian phone on the applicant summary (request #26, owner ruling R3).
 *
 * A super or org_admin may correct the contact of the student behind this application AT ANY
 * TIME — including while the student is locked out of it because bursary signing is possible —
 * and the server records every real change with the admin's email. The CALLER decides who sees
 * the button (`ApplicantCards`' `canCorrectGuardian`, from the cockpit's own role reading); the
 * server gate (`AdminGuardianContactView`) is what actually refuses everyone else.
 *
 * At MODULE scope deliberately (lessons.md): a component declared inside a page body is a new type
 * on every render, remounts, and steals focus mid-typing.
 */
import { useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { correctGuardianContact } from '@/lib/admin-api'
import { isValidMobile, toLocalPhone } from '@/lib/guardianPhone'
import type { T } from './shared'

/** Review F6: the server's refusal codes, in words. Reuses the apply form's phone sentence. */
const REFUSAL: Record<string, string> = {
  guardian_phone_invalid: 'scholarship.apply.error.phone',
  guardian_phone_is_students: 'admin.scholarship.guardianPhoneIsStudents',
  guardian_contact_locked: 'admin.scholarship.guardianLocked',
}

export function GuardianCorrect({ appId, name, phone, t, onDone }: {
  appId: number
  name: string
  phone: string
  t: T
  onDone?: () => void | Promise<void>
}) {
  const { token } = useAdminAuth()
  const [open, setOpen] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [draftPhone, setDraftPhone] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const begin = () => {
    setDraftName(name); setDraftPhone(toLocalPhone(phone)); setError(''); setOpen(true)
  }
  const save = async () => {
    if (!token) return
    setBusy(true); setError('')
    try {
      await correctGuardianContact(appId, { name: draftName.trim(), phone: toLocalPhone(draftPhone) }, { token })
      setOpen(false)
      await onDone?.()
    } catch (e) {
      setError(t(REFUSAL[(e as Error & { code?: string }).code || ''] || 'errors.somethingWentWrong'))
    } finally { setBusy(false) }
  }

  if (!open) {
    return (
      <button type="button" onClick={begin} className="ml-2 text-xs font-medium text-primary-600 hover:underline">
        {t('admin.scholarship.guardianCorrect')}
      </button>
    )
  }
  const field = 'w-full rounded-md border border-ground-300 px-2 py-1.5 text-sm'
  return (
    <div role="dialog" aria-label={t('admin.scholarship.guardianCorrect')} className="mt-2 space-y-2 rounded-lg border border-ground-200 bg-ground-50 p-3">
      <input aria-label={t('scholarship.apply.field.parentName')} value={draftName} onChange={e => setDraftName(e.target.value)} maxLength={255} className={field} />
      <input aria-label={t('scholarship.apply.field.parentPhone')} value={draftPhone} onChange={e => setDraftPhone(toLocalPhone(e.target.value))} inputMode="tel" className={field} />
      {draftPhone.trim() !== '' && !isValidMobile(draftPhone) && <p className="text-xs text-critical-600">{t('scholarship.apply.error.phone')}</p>}
      {error && <p role="alert" className="text-xs text-critical-600">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={() => setOpen(false)} className="rounded-md border border-ground-300 px-3 py-1.5 text-xs font-medium text-ground-700">
          {t('common.cancel')}
        </button>
        <button type="button" onClick={save} disabled={busy || !draftName.trim() || !isValidMobile(draftPhone)} className="rounded-md bg-brand-fill px-3 py-1.5 text-xs font-medium text-brand-fill-ink disabled:opacity-50">
          {busy ? '...' : t('common.save')}
        </button>
      </div>
    </div>
  )
}
