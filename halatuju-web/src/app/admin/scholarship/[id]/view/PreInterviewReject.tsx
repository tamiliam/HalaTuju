'use client'

/**
 * Request #75 (analysis 172, 2026-11-16): REJECT BEFORE INTERVIEW, on the Reviewer card.
 *
 * Two pieces:
 *   • `PreInterviewOption` — at Awaiting review, the alternative to "Assign a reviewer": a
 *     three-step panel (idle -> form -> confirm). The door is SERVED: `app.pre_interview` is present
 *     only for a viewer holding the `qc` key (QC, org admins, super; never a reviewer) at Awaiting
 *     review, and it carries the reason list and the note's limit. With a reviewer on the case the
 *     button is not offered; a hint says to set the reviewer back to Unassigned first. The server
 *     refuses both again (`has_reviewer`, `bad_status`).
 *   • `PreInterviewRecord` — once made: the decline kind, the main reason, and the email: held
 *     ("This decline is scheduled to be sent on", "Cancel decline": the same cool-off and the same
 *     cancel as every held decline) or sent ("Decline email sent on"). The note itself shows in the
 *     existing record card (`OrgRejectPanel`). Neither ever reaches the student.
 */
import { useState } from 'react'
import { rejectBeforeInterview } from '@/lib/admin-api'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { PRE_INTERVIEW_CATEGORY } from '@/lib/applicationStatus'
import { formatDate } from '@/lib/formatDate'

import type { T } from './shared'

const P = 'admin.scholarship.preInterview'
const REFUSALS = ['bad_status', 'has_reviewer', 'reason_required', 'comments_required', 'comments_too_long']
const BTN = 'max-md:min-h-11 max-md:inline-flex max-md:items-center max-md:justify-center'

export function PreInterviewOption({ app, t, token, busy, onDone }: {
  app: AdminScholarshipDetail
  t: T
  token: string | null | undefined
  busy: string
  onDone: (app: AdminScholarshipDetail) => void
}) {
  const [step, setStep] = useState<'idle' | 'form' | 'confirm'>('idle')
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const [working, setWorking] = useState(false)
  const offer = app.pre_interview
  if (!offer) return null
  if (app.assigned_to_id) {
    return <p className="text-xs text-ground-500" data-testid="pre-interview-unassign-first">{t(`${P}.unassignFirst`)}</p>
  }
  const max = offer.note_max
  const ready = !!reason && !!note.trim() && note.length <= max
  const close = () => { setStep('idle'); setReason(''); setNote(''); setErr('') }
  const submit = async () => {
    if (!token) return
    setWorking(true); setErr('')
    try {
      onDone(await rejectBeforeInterview(app.id, reason, note, { token }))
      close()
    } catch (e) {
      const code = (e as { code?: string }).code || ''
      setErr(t(`${P}.error.${REFUSALS.includes(code) ? code : 'generic'}`))
      setStep('form')
    } finally { setWorking(false) }
  }
  return (
    <div className="space-y-2 border-t border-ground-100 pt-3" data-testid="pre-interview">
      {step === 'idle' && (<>
        <p className="text-center text-xs text-ground-400">{t(`${P}.or`)}</p>
        <button type="button" onClick={() => setStep('form')} disabled={!!busy}
          className={`w-full rounded-lg border border-critical-300 px-3 py-2 text-sm font-medium text-critical-700 hover:bg-critical-50 disabled:opacity-50 ${BTN}`}>
          {t(`${P}.start`)}
        </button>
        <p className="text-xs text-ground-500">{t(`${P}.help`)}</p>
      </>)}

      {step === 'form' && (<>
        <h3 className="text-sm font-semibold text-ground-900">{t(`${P}.title`)}</h3>
        <label htmlFor="pre-interview-reason" className="block text-sm font-medium text-ground-700">
          {t(`${P}.reasonLabel`)}
        </label>
        <select id="pre-interview-reason" value={reason} onChange={(e) => setReason(e.target.value)}
          className={`w-full rounded-lg border px-3 py-2 text-sm ${BTN}`}>
          <option value="">{t(`${P}.reasonPlaceholder`)}</option>
          {offer.reasons.map((r) => <option key={r} value={r}>{t(`${P}.reasons.${r}`)}</option>)}
        </select>
        <label htmlFor="pre-interview-why" className="block text-sm font-medium text-ground-700">
          {t(`${P}.whyLabel`)}
        </label>
        <textarea id="pre-interview-why" rows={4} value={note} maxLength={max}
          onChange={(e) => setNote(e.target.value)}
          className="w-full rounded-lg border px-3 py-2 text-sm" />
        <div className="flex justify-between gap-2 text-xs text-ground-500">
          <span>{t(`${P}.whyHint`)}</span>
          <span className="shrink-0" data-testid="pre-interview-counter">
            {t(`${P}.counter`, { count: String(note.length), max: String(max) })}
          </span>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={close}
            className={`flex-1 rounded-lg border px-3 py-2 text-sm text-ground-600 hover:bg-ground-50 ${BTN}`}>
            {t(`${P}.cancel`)}
          </button>
          <button type="button" onClick={() => { setErr(''); setStep('confirm') }} disabled={!ready}
            className={`flex-1 rounded-lg bg-critical-fill px-3 py-2 text-sm font-medium text-critical-fill-ink hover:bg-critical-700 disabled:opacity-40 ${BTN}`}>
            {t(`${P}.submit`)}
          </button>
        </div>
      </>)}

      {step === 'confirm' && (<>
        <div className="rounded-lg border border-critical-300 bg-critical-50 p-3" data-testid="pre-interview-confirm">
          <p className="text-sm font-medium text-critical-800">{t(`${P}.confirmTitle`)}</p>
          <p className="mt-1 text-xs text-critical-700">
            {t(`${P}.confirmBody`, { name: app.name, reason: t(`${P}.reasons.${reason}`) })}
          </p>
          <p className="mt-1 text-xs text-critical-700">
            {t(`${P}.confirmEmail`, { date: formatDate(Date.now() + offer.hold_hours * 3_600_000) })}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => setStep('form')} disabled={working}
            className={`flex-1 rounded-lg border px-3 py-2 text-sm text-ground-600 hover:bg-ground-50 ${BTN}`}>
            {t(`${P}.back`)}
          </button>
          <button type="button" onClick={submit} disabled={working || !!busy}
            className={`flex-1 rounded-lg bg-critical-fill px-3 py-2 text-sm font-medium text-critical-fill-ink hover:bg-critical-700 disabled:opacity-50 ${BTN}`}>
            {working ? t(`${P}.running`) : t(`${P}.confirmYes`)}
          </button>
        </div>
      </>)}

      {err && <p className="text-sm text-critical-600" role="alert">{err}</p>}
    </div>
  )
}

export function PreInterviewRecord({ app, t, busy, doCancelDecline }: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  doCancelDecline: () => void
}) {
  if (app.status !== 'rejected' || app.rejection_category !== PRE_INTERVIEW_CATEGORY) return null
  const held = !!app.decline_due_at && !!app.pending_rejection_category
  return (
    <div className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-critical-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-2"
      data-testid="pre-interview-record">
      <h2 className="text-base font-semibold tracking-tight text-ground-900">{t(`${P}.recordTitle`)}</h2>
      {app.rejection_reason && (
        <p className="text-sm text-ground-700">
          {t(`${P}.recordReason`, { reason: t(`${P}.reasons.${app.rejection_reason}`) })}
        </p>
      )}
      {held ? (<>
        <p className="text-sm text-caution-800">
          {t('admin.scholarship.cooloff.declineScheduled')} <strong>{formatDate(app.decline_due_at)}</strong>.
        </p>
        <button type="button" onClick={doCancelDecline} disabled={busy === 'cooloff'}
          className={`w-full rounded-lg border border-caution-300 px-3 py-2 text-sm font-medium text-caution-800 hover:bg-caution-50 disabled:opacity-50 ${BTN}`}>
          {busy === 'cooloff' ? '…' : t('admin.scholarship.cooloff.cancelDecline')}
        </button>
      </>) : app.decline_email_sent_at ? (
        <p className="text-sm text-ground-600">{t(`${P}.sent`, { date: formatDate(app.decline_email_sent_at) })}</p>
      ) : null}
    </div>
  )
}
