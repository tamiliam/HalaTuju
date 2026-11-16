'use client'

/**
 * A SCHOLAR'S GRADUATION THANK-YOU, on the scholar file (sprint THANKS-SCHOLARS). OWNER RULING 2026-11-16:
 * "Thank yous are part of the scholar maintenance process." A student's thank-you reaches the sponsor only
 * after staff approve it, and that is scholar-file work: whoever may READ the file sees the card (the
 * server's file fence: `scholars` holders, a super, and a current student's mentor, read-only), and the
 * Approve / Reject controls are drawn ONLY when the server serves `may_decide` (serve, never derive: no key
 * or role is checked here). The server asks the same rule again on every decision.
 *
 * The newest message is the one to act on:
 *   • pending: the text the sponsor will see (starts as the student's words, editable), Approve, and Reject
 *     with an optional note. The server checks the edited text again; a text that still names the student
 *     comes back `scrubbed_leak` and is said plainly.
 *   • blocked: the automatic check found something that may name the student. Reject only, with the reason;
 *     the student edits and sends it again.
 *   • approved / rejected: read only.
 * Without `may_decide` every message is read only. Earlier versions (each send adds one) are listed read
 * only underneath. No messages: no card.
 */
import { useEffect, useState } from 'react'
import {
  getScholarThanks, reviewScholarThanks,
  type AdminGraduationMessage, type GraduationMessageStatus,
} from '@/lib/admin-api'
import { formatDateTime } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'

import { ReasonBox } from './ReasonBox'

type T = ReturnType<typeof useT>['t']
const K = 'admin.scholarship.graduationThanks'
/** The refusal codes the review call answers with; anything else gets the generic line. */
export const THANKS_ERRORS = ['scrubbed_leak', 'not_reviewable', 'empty_message', 'bad_action'] as const
/** The fields the automatic check can name (`pool.scan_anon_for_identifiers`). */
const FIELDS = ['name', 'school', 'city', 'nric', 'phone', 'email']
const TAP = 'max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center'

const TONE: Record<GraduationMessageStatus, string> = {
  pending: 'bg-caution-100 text-caution-900',
  blocked: 'bg-critical-50 text-critical-800',
  approved: 'bg-primary-50 text-primary-800',
  rejected: 'bg-ground-100 text-ground-700',
}

function Pill({ status, t }: { status: GraduationMessageStatus; t: T }) {
  return (
    <span data-testid="thanks-pill"
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE[status]}`}>
      {t(`${K}.status.${status}`)}
    </span>
  )
}

function Quote({ heading, text }: { heading: string; text?: string }) {
  if (!text) return null
  return (
    <div>
      <p className="text-xs font-medium text-ground-700">{heading}</p>
      <blockquote className="mt-1 whitespace-pre-wrap break-words border-l-2 border-ground-300 pl-3 text-sm text-ground-800">
        {text}
      </blockquote>
    </div>
  )
}

/** "name, school" in words, from the check's field list. */
function fieldWords(fields: string[], t: T): string {
  return fields.map((f) => (FIELDS.includes(f) ? t(`${K}.field.${f}`) : f)).join(', ')
}

export default function ScholarThanks({ id, token }: { id: number; token: string | null }) {
  const { t } = useT()
  const [mayDecide, setMayDecide] = useState(false)
  const [messages, setMessages] = useState<AdminGraduationMessage[] | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [text, setText] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<'' | 'approve' | 'reject'>('')
  const [error, setError] = useState('')

  /** Bumped to read the messages again (a refusal saying someone else already decided). */
  const [reads, setReads] = useState(0)

  useEffect(() => {
    if (!token) return
    let live = true
    getScholarThanks(id, { token })
      .then((d) => {
        if (!live) return
        setMessages(d.messages); setMayDecide(d.may_decide === true); setLoadFailed(false)
        setText(d.messages[0]?.raw_text ?? '')
      })
      .catch(() => { if (live) setLoadFailed(true) })
    return () => { live = false }
  }, [id, token, reads])

  if (loadFailed && !messages) {
    return <p className="text-sm text-critical-600">{t(`${K}.loadError`)}</p>
  }
  if (!messages || messages.length === 0) return null
  const [msg, ...earlier] = messages

  const act = async (action: 'approve' | 'reject') => {
    if (!token || busy) return
    setBusy(action); setError('')
    try {
      const next = await reviewScholarThanks(id, msg.id, action === 'approve'
        ? { action, scrubbed_text: text }
        : { action, review_note: note }, { token })
      setMessages([next, ...earlier]); setRejecting(false); setNote('')
    } catch (e) {
      const code = (e as { code?: string }).code ?? ''
      setError((THANKS_ERRORS as readonly string[]).includes(code)
        ? t(`${K}.error.${code}`) : t(`${K}.error.generic`))
      if (code === 'not_reviewable') setReads((n) => n + 1)
    } finally {
      setBusy('')
    }
  }

  const rejectBox = rejecting && (
    <ReasonBox testId="thanks-reject-box" optional
      title={t(`${K}.rejectTitle`)} hint={t(`${K}.rejectHint`)} placeholder={t(`${K}.rejectPlaceholder`)}
      confirmLabel={t(`${K}.reject`)} workingLabel={t(`${K}.working`)} cancelLabel={t(`${K}.cancel`)}
      value={note} onChange={setNote} onConfirm={() => act('reject')}
      onCancel={() => { setRejecting(false); setNote('') }}
      disabled={busy !== ''} working={busy === 'reject'} />
  )
  const rejectButton = !rejecting && (
    <button type="button" onClick={() => { setRejecting(true); setError('') }} disabled={busy !== ''}
      className={`rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50 ${TAP}`}>
      {t(`${K}.reject`)}
    </button>
  )
  const decided = msg.status === 'approved' || msg.status === 'rejected'

  return (
    <section data-graduation-thanks
      className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-ground-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-3">
      <div className="space-y-1">
        <h2 className="text-base font-semibold tracking-tight text-ground-900">{t(`${K}.title`)}</h2>
        <p className="text-sm text-ground-600">{t(mayDecide ? `${K}.intro` : `${K}.introReadOnly`)}</p>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Pill status={msg.status} t={t} />
        <span className="text-xs text-ground-600">{t(`${K}.sent`, { date: formatDateTime(msg.created_at) })}</span>
      </div>

      <Quote heading={t(`${K}.studentWrote`)} text={msg.raw_text} />

      {msg.status === 'blocked' && (
        <div className="space-y-2">
          <p data-testid="thanks-blocked-reason" className="text-sm text-critical-700">
            {t(`${K}.blockedReason`, { fields: fieldWords(msg.scan_result ?? [], t) })}
          </p>
          <p className="text-xs text-ground-600">{t(`${K}.blockedHint`)}</p>
          {mayDecide && rejectButton}
          {mayDecide && rejectBox}
        </div>
      )}

      {msg.status === 'pending' && mayDecide && (
        <div className="space-y-2">
          <label htmlFor={`thanks-text-${msg.id}`} className="block text-sm font-medium text-ground-700">
            {t(`${K}.sponsorSees`)}
          </label>
          <textarea id={`thanks-text-${msg.id}`} rows={5} value={text}
            onChange={(e) => { setText(e.target.value); setError('') }}
            className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm leading-relaxed focus:border-info-500 focus:ring-2 focus:ring-info-500" />
          <p className="text-xs text-ground-600">{t(`${K}.editHint`)}</p>
          {!rejecting && (
            <div className="flex flex-col gap-2 sm:flex-row">
              <button type="button" onClick={() => act('approve')} disabled={busy !== '' || !text.trim()}
                className="min-h-11 rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {busy === 'approve' ? t(`${K}.working`) : t(`${K}.approve`)}
              </button>
              {rejectButton}
            </div>
          )}
          {rejectBox}
        </div>
      )}

      {decided && (
        <div className="space-y-2">
          {msg.status === 'approved' && <Quote heading={t(`${K}.sponsorSaw`)} text={msg.scrubbed_text} />}
          {msg.status === 'rejected' && <Quote heading={t(`${K}.noteHeading`)} text={msg.review_note} />}
          {msg.reviewed_at && (
            <p className="text-xs text-ground-600">
              {t(`${K}.decidedBy`, { name: msg.approved_by || t(`${K}.someone`), date: formatDateTime(msg.reviewed_at) })}
            </p>
          )}
        </div>
      )}

      {error && <p role="alert" className="text-sm text-critical-600">{error}</p>}

      {earlier.length > 0 && (
        <details className="rounded-xl border border-ground-200 bg-ground-50 px-3.5 py-2.5">
          <summary className={`cursor-pointer text-sm font-medium text-ground-700 ${TAP}`}>
            {t(`${K}.earlier`, { count: String(earlier.length) })}
          </summary>
          <ol className="mt-2 space-y-3">
            {earlier.map((m) => (
              <li key={m.id} className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Pill status={m.status} t={t} />
                  <span className="text-xs text-ground-600">{t(`${K}.sent`, { date: formatDateTime(m.created_at) })}</span>
                </div>
                <p className="whitespace-pre-wrap break-words text-sm text-ground-800">{m.raw_text}</p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
