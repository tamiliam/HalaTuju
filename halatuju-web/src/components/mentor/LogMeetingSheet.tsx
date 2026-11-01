'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { dayFirstFromIso, isoFromDayFirst, todayIso } from '@/lib/invoices'
import Sheet from '@/components/Sheet'
import Toggle from '@/components/Toggle'
import { logMyMeeting, type MeetingMode, type MyStudent } from '@/lib/admin-api'

const K = 'admin.myStudents.form'
const MODES: MeetingMode[] = ['video', 'in_person', 'phone']
/** The refusal codes 7b's Mentoring tab already words (`admin.scholars.mentoring.error.*`). */
const REFUSALS = ['bad_date', 'future_date', 'before_assignment', 'bad_mode', 'bad_minutes', 'notes_required',
  'too_long', 'file_closed']
const FIELD = 'h-11 w-full rounded-lg border border-ground-300 bg-ground-0 px-3 text-base text-ground-900 focus:border-info-500 focus:ring-2 focus:ring-info-500'

/**
 * "Log a meeting" for a MENTOR (student maintenance S7c; the approved MentorPhone board): the shared
 * Sheet — a bottom sheet on a phone, a centred dialog from `md`. Date, how (three pill buttons, 44 px),
 * minutes, notes (required), next step (optional) and the site Toggle "Tell the team I am worried
 * about this student". Every rule is the server's (`mentor_desk.log_own_session`, 7b's validation);
 * a saved meeting is never edited, so there is no edit form anywhere.
 */
export default function LogMeetingSheet({ open, studentId, studentName, organisation, token, onClose, onSaved }: {
  open: boolean
  studentId: number
  studentName: string
  organisation: string
  token: string | null
  onClose: () => void
  /** The student's page after the save — or null when the student is no longer theirs. */
  onSaved: (page: MyStudent | null, concern: boolean) => void
}) {
  const { t } = useT()
  const [day, setDay] = useState(dayFirstFromIso(todayIso()))
  const [mode, setMode] = useState<MeetingMode>('video')
  const [minutes, setMinutes] = useState('')
  const [notes, setNotes] = useState('')
  const [next, setNext] = useState('')
  const [worried, setWorried] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const iso = isoFromDayFirst(day)
  const mins = minutes.trim() === '' ? null : Number(minutes.trim())
  const minsOk = mins === null || (Number.isInteger(mins) && mins > 0 && mins <= 1440)
  const ready = iso !== '' && minsOk && notes.trim() !== ''

  async function save() {
    if (!token || !ready || busy) return
    setBusy(true); setError('')
    try {
      const page = await logMyMeeting(studentId, {
        met_on: iso, mode, minutes: mins, notes: notes.trim(), next_step: next.trim(), concern: worried,
      }, { token })
      setNotes(''); setNext(''); setMinutes(''); setWorried(false)
      onSaved(page && Array.isArray(page.meetings) ? page : null, worried)
    } catch (e) {
      const err = e as { status?: number; code?: string }
      if (err.status === 404) setError(t('admin.myStudents.notYours'))
      else setError(t(`admin.scholars.mentoring.error.${REFUSALS.includes(err.code ?? '') ? err.code : 'generic'}`))
    } finally { setBusy(false) }
  }

  return (
    <Sheet open={open} onClose={onClose} busy={busy} title={t('admin.myStudents.log')} description={studentName}
      testId="log-meeting-sheet"
      onSubmit={(e) => { e.preventDefault(); void save() }}
      footer={(
        <>
          <button type="button" onClick={onClose} disabled={busy}
            className="h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm text-ground-800 hover:bg-ground-50 disabled:opacity-50">
            {t('admin.scholars.mentoring.cancel')}
          </button>
          <button type="submit" disabled={busy || !ready} data-testid="log-meeting-save"
            className="h-11 rounded-lg bg-brand-fill px-5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {t('admin.scholars.mentoring.meetings.save')}
          </button>
        </>
      )}>
      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.date`)}
          {/* A plain day-first box, not type="date" (a native picker follows the browser's locale). */}
          <input className={FIELD} value={day} inputMode="numeric" placeholder="DD-MM-YYYY"
            onChange={(e) => setDay(e.target.value)} data-testid="log-meeting-date" />
        </label>
        {day.trim() !== '' && iso === '' && (
          <p className="text-xs text-critical-700">{t('admin.scholars.mentoring.error.bad_date')}</p>
        )}
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-sm font-medium text-ground-700">{t(`${K}.how`)}</legend>
          <div className="flex flex-wrap gap-2">
            {MODES.map((m) => (
              <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}
                data-testid={`log-meeting-mode-${m}`}
                className={`h-11 rounded-full border px-4 text-sm ${mode === m
                  ? 'border-info-500 bg-info-50 font-medium text-info-800'
                  : 'border-ground-300 bg-ground-0 text-ground-800 hover:bg-ground-50'}`}>
                {t(`admin.scholars.mentoring.mode.${m}`)}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.minutes`)}
          <input className={FIELD} value={minutes} inputMode="numeric" onChange={(e) => setMinutes(e.target.value)}
            data-testid="log-meeting-minutes" />
        </label>
        {!minsOk && <p className="text-xs text-critical-700">{t('admin.scholars.mentoring.error.bad_minutes')}</p>}
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.notes`, { org: organisation || t(`${K}.theTeam`) })}
          <textarea rows={4} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)}
            data-testid="log-meeting-notes"
            className="w-full rounded-lg border border-ground-300 bg-ground-0 p-3 text-base text-ground-900 focus:border-info-500 focus:ring-2 focus:ring-info-500" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.nextStep`)}
          <input className={FIELD} value={next} maxLength={500} onChange={(e) => setNext(e.target.value)} />
        </label>
        <div className="flex items-center justify-between gap-3" data-testid="log-meeting-worried">
          <span className="text-sm text-ground-800">{t(`${K}.worried`)}</span>
          <Toggle on={worried} onChange={setWorried} label={t(`${K}.worried`)} />
        </div>
        <p className="text-xs text-ground-600">{t(`${K}.noEdit`)}</p>
        {error && <p role="alert" className="text-sm text-critical-700">{error}</p>}
      </div>
    </Sheet>
  )
}
