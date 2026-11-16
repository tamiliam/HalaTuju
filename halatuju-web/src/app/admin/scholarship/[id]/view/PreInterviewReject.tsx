'use client'

/**
 * Request #75 (analysis 172, 2026-11-16): REJECT BEFORE INTERVIEW, on the Reviewer card.
 *
 * Two pieces:
 *   • `PreInterviewOption` — at Awaiting review, the alternative to "Assign a reviewer": a
 *     three-step panel (idle -> form -> confirm). The door is SERVED: `app.pre_interview` is present
 *     only for a viewer holding the `qc` key (QC, org admins, super; never a reviewer) at Awaiting
 *     review, and it carries the reason list and the note's limit. With a reviewer on the case the
 *     button is not offered; a hint, worded by whether this viewer may assign, says to set the
 *     reviewer back to Unassigned first (or to ask someone who assigns reviewers). The server refuses
 *     both again (`has_reviewer`, `bad_status`), and on either the case is reloaded.
 *     Focus (#75 review): the select when the form opens, the confirm heading on "Are you sure?",
 *     the Reject button on Go back (or a refusal), and the start button on Cancel.
 *   • `PreInterviewRecord` — once made: the decline kind, the main reason, and the email: held
 *     ("This decline is scheduled to be sent on"; the header's cool-off banner carries "Cancel
 *     decline", the same cancel as every held decline) or sent ("Decline email sent on"). The note
 *     itself shows in the existing record card (`OrgRejectPanel`). Neither ever reaches the student.
 */
import { useEffect, useRef, useState } from 'react'
import { rejectBeforeInterview } from '@/lib/admin-api'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { PRE_INTERVIEW_CATEGORY } from '@/lib/applicationStatus'
import { formatDate } from '@/lib/formatDate'

import type { T } from './shared'

const P = 'admin.scholarship.preInterview'
const REFUSALS = ['bad_status', 'has_reviewer', 'reason_required', 'comments_required', 'comments_too_long']
/** The refusals that mean the page is stale: the case is reloaded. */
const STALE = ['bad_status', 'has_reviewer']
const BTN = 'max-md:min-h-11 max-md:inline-flex max-md:items-center max-md:justify-center'
type Focus = 'start' | 'select' | 'submit' | 'title'

export function PreInterviewOption({ app, t, token, busy, canAssign, onDone, onStale }: {
  app: AdminScholarshipDetail
  t: T
  token: string | null | undefined
  busy: string
  /** May this viewer set the reviewer? Words the "unassign first" hint. */
  canAssign: boolean
  onDone: (app: AdminScholarshipDetail) => void
  /** Reload the case (a `bad_status` or `has_reviewer` refusal: the page was stale). */
  onStale: () => Promise<void> | void
}) {
  const [step, setStep] = useState<'idle' | 'form' | 'confirm'>('idle')
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [err, setErr] = useState('')
  const [working, setWorking] = useState(false)
  const startRef = useRef<HTMLButtonElement>(null)
  const selectRef = useRef<HTMLSelectElement>(null)
  const submitRef = useRef<HTMLButtonElement>(null)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const focusNext = useRef<Focus | null>(null)
  const go = (next: typeof step, focus: Focus) => { focusNext.current = focus; setStep(next) }
  useEffect(() => {
    const target = focusNext.current
    focusNext.current = null
    const el = target === 'start' ? startRef.current : target === 'select' ? selectRef.current
      : target === 'submit' ? submitRef.current : target === 'title' ? titleRef.current : null
    el?.focus()
  }, [step])
  const offer = app.pre_interview
  // A refusal that reloaded the case away from this door still says what happened.
  if (!offer) return err ? <p className="text-sm text-critical-600" role="alert">{err}</p> : null
  if (app.assigned_to_id) {
    return (<>
      <p className="text-xs text-ground-500" data-testid="pre-interview-unassign-first">
        {t(`${P}.${canAssign ? 'unassignFirst' : 'unassignAsk'}`)}
      </p>
      {err && <p className="text-sm text-critical-600" role="alert">{err}</p>}
    </>)
  }
  const max = offer.note_max
  const ready = !!reason && !!note.trim() && note.length <= max
  const close = () => { setReason(''); setNote(''); setErr(''); go('idle', 'start') }
  const submit = async () => {
    if (!token) return
    setWorking(true); setErr('')
    try {
      const next = await rejectBeforeInterview(app.id, reason, note, { token })
      setReason(''); setNote(''); setStep('idle')
      onDone(next)
    } catch (e) {
      const code = (e as { code?: string }).code || ''
      setErr(t(`${P}.error.${REFUSALS.includes(code) ? code : 'generic'}`))
      go('form', 'submit')
      if (STALE.includes(code)) {
        try { await onStale() } catch { /* the refusal already says what happened */ }
      }
    } finally { setWorking(false) }
  }
  const hasHold = offer.hold_hours > 0
  return (
    <div className="space-y-2 border-t border-ground-100 pt-3" data-testid="pre-interview">
      {step === 'idle' && (<>
        <p className="text-center text-xs text-ground-400">{t(`${P}.or`)}</p>
        <button type="button" ref={startRef} onClick={() => go('form', 'select')} disabled={!!busy}
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
        <select id="pre-interview-reason" ref={selectRef} value={reason} onChange={(e) => setReason(e.target.value)}
          className={`w-full rounded-lg border px-3 py-2 text-sm ${BTN}`}>
          <option value="">{t(`${P}.reasonPlaceholder`)}</option>
          {offer.reasons.map((r) => <option key={r} value={r}>{t(`${P}.reasons.${r}`)}</option>)}
        </select>
        <label htmlFor="pre-interview-why" className="block text-sm font-medium text-ground-700">
          {t(`${P}.whyLabel`)}
        </label>
        <textarea id="pre-interview-why" rows={4} value={note} maxLength={max}
          aria-describedby="pre-interview-why-hint pre-interview-why-count"
          onChange={(e) => setNote(e.target.value)}
          className="w-full rounded-lg border px-3 py-2 text-sm" />
        <div className="flex justify-between gap-2 text-xs text-ground-500">
          <span id="pre-interview-why-hint">{t(`${P}.whyHint`)}</span>
          <span id="pre-interview-why-count" className="shrink-0" data-testid="pre-interview-counter">
            {t(`${P}.counter`, { count: String(note.length), max: String(max) })}
          </span>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={close}
            className={`flex-1 rounded-lg border px-3 py-2 text-sm text-ground-600 hover:bg-ground-50 ${BTN}`}>
            {t(`${P}.cancel`)}
          </button>
          <button type="button" ref={submitRef} onClick={() => { setErr(''); go('confirm', 'title') }} disabled={!ready}
            className={`flex-1 rounded-lg bg-critical-fill px-3 py-2 text-sm font-medium text-critical-fill-ink hover:bg-critical-700 disabled:opacity-40 ${BTN}`}>
            {t(`${P}.submit`)}
          </button>
        </div>
      </>)}

      {step === 'confirm' && (
        <div role="alertdialog" aria-labelledby="pre-interview-confirm-title"
          aria-describedby="pre-interview-confirm-body pre-interview-confirm-email" className="space-y-2">
          <div className="rounded-lg border border-critical-300 bg-critical-50 p-3" data-testid="pre-interview-confirm">
            <h3 id="pre-interview-confirm-title" ref={titleRef} tabIndex={-1}
              className="text-sm font-medium text-critical-800 focus:outline-none">{t(`${P}.confirmTitle`)}</h3>
            <p id="pre-interview-confirm-body" className="mt-1 text-xs text-critical-700">
              {t(`${P}.confirmBody`, { name: app.name, reason: t(`${P}.reasons.${reason}`) })}
            </p>
            <p id="pre-interview-confirm-email" className="mt-1 text-xs text-critical-700">
              {hasHold
                ? t(`${P}.confirmEmail`, { date: formatDate(Date.now() + offer.hold_hours * 3_600_000) })
                : t(`${P}.confirmEmailNow`)}
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => go('form', 'submit')} disabled={working}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm text-ground-600 hover:bg-ground-50 ${BTN}`}>
              {t(`${P}.back`)}
            </button>
            <button type="button" onClick={submit} disabled={working || !!busy}
              className={`flex-1 rounded-lg bg-critical-fill px-3 py-2 text-sm font-medium text-critical-fill-ink hover:bg-critical-700 disabled:opacity-50 ${BTN}`}>
              {working ? t(`${P}.running`) : t(`${P}.confirmYes`)}
            </button>
          </div>
        </div>
      )}

      {err && <p className="text-sm text-critical-600" role="alert">{err}</p>}
    </div>
  )
}

export function PreInterviewRecord({ app, t }: {
  app: AdminScholarshipDetail
  t: T
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
      {held ? (
        <p className="text-sm text-caution-800">
          {t('admin.scholarship.cooloff.declineScheduled')} <strong>{formatDate(app.decline_due_at)}</strong>.
        </p>
      ) : app.decline_email_sent_at ? (
        <p className="text-sm text-ground-600">{t(`${P}.sent`, { date: formatDate(app.decline_email_sent_at) })}</p>
      ) : null}
    </div>
  )
}
