'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatMyt, withinCutoff } from '@/lib/interviewTime'
import {
  getInterview, bookInterviewSlot, cancelInterview, requestInterviewAlternatives,
  type InterviewSchedule,
} from '@/lib/api'

/** Student-facing "Your interview" panel: pick one of the reviewer's proposed
 *  times, then see the confirmed time + Google Meet link, with self-service
 *  reschedule/cancel up to a cutoff. Hidden until the reviewer proposes times
 *  (and entirely dark unless the feature flag is on). */
export default function InterviewBookingPanel({
  applicationId, token,
}: { applicationId: number; token: string | null }) {
  const { t } = useT()
  const [sched, setSched] = useState<InterviewSchedule | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [rescheduling, setRescheduling] = useState(false)
  const [confirmingCancel, setConfirmingCancel] = useState(false)
  const [requesting, setRequesting] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let active = true
    getInterview(applicationId, { token })
      .then((s) => { if (active) setSched(s) })
      .catch(() => {})
    return () => { active = false }
  }, [applicationId, token])

  if (!sched || !sched.enabled || !token) return null
  // Nothing to show until the reviewer proposes times (and not booked/cancelled).
  if (sched.status !== 'booked' && sched.status !== 'cancelled' && sched.slots.length === 0) return null

  const book = async (slotId: number) => {
    setBusy(true); setError('')
    try {
      setSched(await bookInterviewSlot(applicationId, slotId, { token }))
      setRescheduling(false); setPicked(null)
    } catch (e) {
      setError((e as Error & { code?: string }).code === 'too_late'
        ? t('scholarship.application.interview.tooLateNote')
        : t('scholarship.application.interview.error'))
    } finally { setBusy(false) }
  }

  const cancel = async () => {
    setBusy(true); setError('')
    try { setSched(await cancelInterview(applicationId, { token })) }
    catch (e) {
      setError((e as Error & { code?: string }).code === 'too_late'
        ? t('scholarship.application.interview.tooLateNote')
        : t('scholarship.application.interview.error'))
    } finally { setBusy(false) }
  }

  const requestAlt = async () => {
    setBusy(true); setError('')
    try {
      setSched(await requestInterviewAlternatives(applicationId, note, { token }))
      setRequesting(false); setNote('')
    } catch { setError(t('scholarship.application.interview.error')) }
    finally { setBusy(false) }
  }

  const cutoffH = sched.reschedule_cutoff_hours
  const locked = sched.status === 'booked' && withinCutoff(sched.start, cutoffH)

  return (
    <section className="mb-6 rounded-2xl border border-blue-200 bg-blue-50/40 p-5">
      <h2 className="text-lg font-semibold text-gray-900">{t('scholarship.application.interview.title')}</h2>

      {sched.status === 'booked' ? (
        <div className="mt-2">
          <p className="text-sm text-gray-700">{t('scholarship.application.interview.booked')}:</p>
          <p className="mt-1 text-base font-semibold text-gray-900">{formatMyt(sched.start)}</p>
          {sched.meeting_url
            ? <a href={sched.meeting_url} target="_blank" rel="noreferrer"
                 className="mt-3 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                {t('scholarship.application.interview.joinMeet')}
              </a>
            : <p className="mt-2 text-xs text-gray-500">{t('scholarship.application.interview.noLinkYet')}</p>}
          <p className="mt-3 text-xs text-gray-500">{t('scholarship.application.interview.parentsNote')}</p>

          {locked ? (
            <p className="mt-3 text-xs text-amber-700">{t('scholarship.application.interview.tooLateNote')}</p>
          ) : confirmingCancel ? (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50/60 p-3">
              <p className="text-sm text-gray-800">{t('scholarship.application.interview.cancelConfirm')}</p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <button type="button" onClick={cancel} disabled={busy}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                  {t('scholarship.application.interview.cancelYes')}
                </button>
                <button type="button" onClick={() => setConfirmingCancel(false)} disabled={busy}
                  className="text-sm text-gray-600 hover:text-gray-800">
                  {t('scholarship.application.interview.cancelKeep')}
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {sched.slots.filter((s) => s.id !== sched.booked_slot_id).length > 0 && (
                <button type="button" onClick={() => setRescheduling((v) => !v)}
                  className="text-sm text-blue-600 hover:underline">
                  {t('scholarship.application.interview.reschedule')}
                </button>
              )}
              <button type="button" onClick={() => setConfirmingCancel(true)} disabled={busy}
                className="text-sm text-gray-500 hover:text-red-600 disabled:opacity-50">
                {t('scholarship.application.interview.cancelInterview')}
              </button>
            </div>
          )}

          {rescheduling && (
            <ul className="mt-3 space-y-2">
              {sched.slots.filter((s) => s.id !== sched.booked_slot_id).map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => book(s.id)} disabled={busy}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-left text-sm hover:border-blue-400 disabled:opacity-50">
                    {formatMyt(s.start)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : sched.status === 'cancelled' ? (
        <p className="mt-2 text-sm text-amber-700">{t('scholarship.application.interview.cancelledNote')}</p>
      ) : (
        <div className="mt-2">
          <p className="text-sm text-gray-700">{t('scholarship.application.interview.pickIntro')}</p>
          <ul className="mt-3 space-y-2">
            {sched.slots.map((s) => (
              <li key={s.id}>
                <label className="flex items-center gap-3 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm hover:border-blue-400">
                  <input type="radio" name="slot" checked={picked === s.id}
                    onChange={() => setPicked(s.id)} className="accent-blue-600" />
                  <span>{formatMyt(s.start)}</span>
                </label>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-gray-500">{t('scholarship.application.interview.parentsNote')}</p>
          <button type="button" disabled={busy || picked == null}
            onClick={() => picked != null ? book(picked) : setError(t('scholarship.application.interview.selectFirst'))}
            className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {t('scholarship.application.interview.book')}
          </button>

          {/* "None of these work" — request other times (notifies the interviewer). */}
          {sched.alternatives_requested ? (
            <p className="mt-4 rounded-lg bg-white/70 px-3 py-2 text-xs text-gray-600">
              {t('scholarship.application.interview.altRequested')}
            </p>
          ) : requesting ? (
            <div className="mt-4 space-y-2">
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000}
                placeholder={t('scholarship.application.interview.altNotePlaceholder')}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
              <div className="flex items-center gap-3">
                <button type="button" onClick={requestAlt} disabled={busy}
                  className="rounded-lg bg-gray-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-900 disabled:opacity-50">
                  {t('scholarship.application.interview.altSubmit')}
                </button>
                <button type="button" onClick={() => { setRequesting(false); setNote('') }}
                  className="text-sm text-gray-500 hover:text-gray-700">
                  {t('scholarship.application.interview.altCancel')}
                </button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={() => setRequesting(true)}
              className="mt-4 block text-sm text-blue-600 hover:underline">
              {t('scholarship.application.interview.altAsk')}
            </button>
          )}
        </div>
      )}

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </section>
  )
}
