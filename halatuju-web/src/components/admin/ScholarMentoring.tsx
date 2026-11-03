'use client'

import { PHONE_CARD_XL } from '@/lib/phoneSection'
import { useCallback, useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { dayFirstFromIso, isoFromDayFirst, todayIso } from '@/lib/invoices'
import Toggle from '@/components/Toggle'
import {
  assignMentor, endMentoring, getScholarMentoring, handleMentorConcern, logMentoringMeeting,
  type AssignableMentor, type MeetingMode, type ScholarMentoring as Payload, type StaffRef,
} from '@/lib/admin-api'

type T = (k: string, p?: Record<string, string>) => string

const K = 'admin.scholars.mentoring'
const MODES: MeetingMode[] = ['in_person', 'video', 'phone']
const REFUSALS = ['mentor_not_found', 'mentor_inactive', 'own_application', 'already_assigned', 'file_closed',
  'conflict', 'too_long', 'no_mentor', 'bad_date', 'future_date', 'before_assignment', 'bad_mode', 'bad_minutes',
  'notes_required']
const CARD = PHONE_CARD_XL   // Mobile M7a (rule 15): a section on a phone, this card from md
const FIELD = 'h-11 w-full rounded-lg border border-ground-300 px-3 text-base md:h-10 md:text-sm focus:border-info-500 focus:ring-2 focus:ring-info-500'
const PRIMARY = 'h-11 rounded-lg bg-brand-fill px-4 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50 md:h-10'
const SECONDARY = 'h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm text-ground-800 hover:bg-ground-50 disabled:opacity-50 md:h-10'
const codeOf = (e: unknown) => (e as { code?: string })?.code ?? ''

/** "EN · MS · TA · Mandarin" — the languages spoken conversationally or better (the server's list). */
export function languagesLine(codes: readonly string[], other: string): string {
  return [...codes.map((c) => c.toUpperCase()), ...(other ? [other] : [])].join(' · ')
}

function who(t: T, ref: StaffRef): string {
  return ref.name || ref.email || t(`${K}.someone`)
}

function optionText(t: T, m: AssignableMentor): string {
  if (m.status === 'invited') return t(`${K}.form.invitedOption`, { name: m.name })
  const parts = [m.area, languagesLine(m.languages, m.other_language),
    t(`${K}.form.scholarsNow`, { count: String(m.scholars_now) })].filter(Boolean)
  return `${m.name} — ${parts.join(' · ')}`
}

/** The help the scholar asked for, as one sentence ('' when none). */
export function helpLine(t: T, h: Payload['asked_for_help'] | undefined): string {
  if (!h) return ''
  const what = [h.university && t(`${K}.help.university`), h.scholarship && t(`${K}.help.scholarship`)]
    .filter(Boolean).join(t(`${K}.help.and`))
  if (what) return t(`${K}.help.asked`, { what })
  return h.flagged ? t(`${K}.help.flagged`) : ''
}

function AssignForm({ t, data, changing, busy, onSubmit, onCancel }: {
  t: T; data: Payload; changing: boolean; busy: boolean
  onSubmit: (b: { mentor_id: number; reason: string; email_student: boolean }) => void; onCancel: () => void
}) {
  const choices = data.assignable.filter((m) => m.id !== data.current?.mentor_id)
  const [mentorId, setMentorId] = useState<number | null>(choices[0]?.id ?? null)
  const [reason, setReason] = useState('')
  const [email, setEmail] = useState(true)
  return (
    <section aria-label={t(changing ? `${K}.form.changeTitle` : `${K}.form.assignTitle`)}
      className={`${CARD} flex max-w-3xl flex-col gap-3`} data-testid="mentoring-assign-form">
      <h2 className="text-base font-semibold text-ground-900">
        {t(changing ? `${K}.form.changeTitle` : `${K}.form.assignTitle`)}
      </h2>
      {choices.length === 0 ? <p className="text-sm text-ground-600">{t(`${K}.form.noneAvailable`)}</p> : (
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.form.mentor`)}
          <select className={FIELD} value={mentorId ?? ''} data-testid="mentoring-picker"
            onChange={(e) => setMentorId(Number(e.target.value))}>
            {choices.map((m) => <option key={m.id} value={m.id}>{optionText(t, m)}</option>)}
          </select>
        </label>
      )}
      {changing && (
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.form.reason`)}
          <input className={FIELD} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)}
            placeholder={t(`${K}.form.reasonPlaceholder`)} />
        </label>
      )}
      {/* The organisation's switch decides whether the option exists at all; the staff member's
          choice is the site Toggle (house rule), on by default. */}
      {data.email_switch_on && (
        <div className="flex items-center justify-between gap-3" data-testid="mentoring-email-option">
          <span className="text-sm text-ground-700">{t(`${K}.form.email`)}</span>
          <Toggle on={email} onChange={setEmail} label={t(`${K}.form.email`)} />
        </div>
      )}
      <p className="text-xs text-ground-600">
        {changing && data.current
          ? t(`${K}.form.changeNote`, { name: data.current.name })
          : t(`${K}.form.assignNote`)}
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={PRIMARY} disabled={busy || mentorId === null}
          onClick={() => mentorId !== null && onSubmit({ mentor_id: mentorId, reason: reason.trim(),
            email_student: data.email_switch_on && email })}>
          {t(`${K}.form.assign`)}
        </button>
        <button type="button" className={SECONDARY} onClick={onCancel}>{t(`${K}.cancel`)}</button>
      </div>
    </section>
  )
}

function EndForm({ t, name, busy, onSubmit, onCancel }: {
  t: T; name: string; busy: boolean; onSubmit: (reason: string) => void; onCancel: () => void
}) {
  const [reason, setReason] = useState('')
  return (
    <section aria-label={t(`${K}.end.title`)} className={`${CARD} flex max-w-3xl flex-col gap-3`}
      data-testid="mentoring-end-form">
      <h2 className="text-base font-semibold text-ground-900">{t(`${K}.end.title`)}</h2>
      <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
        {t(`${K}.form.reason`)}
        <input className={FIELD} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
      </label>
      <p className="text-xs text-ground-600">{t(`${K}.end.note`, { name })}</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={PRIMARY} disabled={busy} onClick={() => onSubmit(reason.trim())}>
          {t(`${K}.end.confirm`)}
        </button>
        <button type="button" className={SECONDARY} onClick={onCancel}>{t(`${K}.cancel`)}</button>
      </div>
    </section>
  )
}

function MeetingForm({ t, busy, onSubmit, onCancel }: {
  t: T; busy: boolean
  onSubmit: (b: { met_on: string; mode: MeetingMode; minutes: number | null; notes: string; next_step: string }) => void
  onCancel: () => void
}) {
  const [day, setDay] = useState(dayFirstFromIso(todayIso()))
  const [mode, setMode] = useState<MeetingMode>('in_person')
  const [minutes, setMinutes] = useState('')
  const [notes, setNotes] = useState('')
  const [next, setNext] = useState('')
  const iso = isoFromDayFirst(day)
  const mins = minutes.trim() === '' ? null : Number(minutes.trim())
  const minsOk = mins === null || (Number.isInteger(mins) && mins > 0)
  return (
    <form aria-label={t(`${K}.meetings.log`)} data-testid="mentoring-meeting-form"
      className="flex flex-col gap-3 border-b border-ground-200 bg-ground-50 px-5 py-4"
      onSubmit={(e) => { e.preventDefault(); if (iso && minsOk && notes.trim()) onSubmit({ met_on: iso, mode, minutes: mins, notes: notes.trim(), next_step: next.trim() }) }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.meetings.date`)}
          {/* A plain day-first box, not type="date" (a native picker follows the browser's locale). */}
          <input className={FIELD} value={day} inputMode="numeric" placeholder="DD-MM-YYYY"
            onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.meetings.how`)}
          <select className={FIELD} value={mode} onChange={(e) => setMode(e.target.value as MeetingMode)}>
            {MODES.map((m) => <option key={m} value={m}>{t(`${K}.mode.${m}`)}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
          {t(`${K}.meetings.minutes`)}
          <input className={FIELD} value={minutes} inputMode="numeric" onChange={(e) => setMinutes(e.target.value)} />
        </label>
      </div>
      {day.trim() !== '' && iso === '' && <p className="text-xs text-critical-700">{t(`${K}.error.bad_date`)}</p>}
      <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
        {t(`${K}.meetings.notes`)}
        <textarea rows={3} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)}
          className="w-full rounded-lg border border-ground-300 p-3 text-base md:text-sm focus:border-info-500 focus:ring-2 focus:ring-info-500" />
      </label>
      <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">
        {t(`${K}.meetings.nextStep`)}
        <input className={FIELD} value={next} maxLength={500} onChange={(e) => setNext(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2">
        <button type="submit" className={PRIMARY} disabled={busy || iso === '' || !minsOk || !notes.trim()}>
          {t(`${K}.meetings.save`)}
        </button>
        <button type="button" className={SECONDARY} onClick={onCancel}>{t(`${K}.cancel`)}</button>
      </div>
    </form>
  )
}

/**
 * A scholar's Mentoring tab (student maintenance S7b; the owner-approved MentoringTab board).
 *
 * ⚠ EVERY RULE IS THE SERVER'S (`apps/scholarship/mentoring.py`). One mentor at a time: Change ends the
 * current one (it stays below, with its staff-only reason) and starts the new. "Email the student" is
 * offered only when the organisation sends "You have a mentor" (`email_switch_on`), and the system never
 * emails a mentor. Notes, next steps and reasons are STAFF ONLY — the student's own tab never shows them.
 * `can_act` false (a closed file) reads the same, with no buttons.
 * S7c: a meeting the MENTOR logged reads "logged by <name> (mentor)"; a concern they raised shows a
 * "Mentor concerned" chip on that meeting and at the top, where "Mark as handled" clears every open one.
 */
export default function ScholarMentoring({ id, token }: { id: number; token: string | null }) {
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)
  const [mode, setMode] = useState<'view' | 'assign' | 'end' | 'meeting'>('view')
  const [busy, setBusy] = useState(false)
  const [banner, setBanner] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(() => {
    if (!token) return
    getScholarMentoring(id, { token }).then((d) => { setData(d); setFailed(false) }).catch(() => setFailed(true))
  }, [id, token])
  useEffect(() => { load() }, [load])

  async function run(work: () => Promise<Payload>, done: (d: Payload) => string) {
    setBusy(true); setBanner(null)
    try {
      const d = await work()
      setData(d); setMode('view'); setBanner({ ok: true, text: done(d) })
    } catch (e) {
      const code = codeOf(e)
      setBanner({ ok: false, text: t(`${K}.error.${REFUSALS.includes(code) ? code : 'generic'}`) })
    } finally { setBusy(false) }
  }

  if (failed) return <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadFailed`)}</p>
  if (!data) return <p className="text-sm text-ground-500">{t('common.loading')}</p>
  const cur = data.current
  const help = helpLine(t, data.asked_for_help)
  const past = data.history

  return (
    <div className="flex flex-col gap-5" data-testid="scholar-mentoring">
      {banner && (
        <p role={banner.ok ? 'status' : 'alert'} className={`rounded-lg border p-3 text-sm ${banner.ok
          ? 'border-positive-200 bg-positive-50 text-positive-800' : 'border-caution-200 bg-caution-50 text-caution-900'}`}>
          {banner.text}
        </p>
      )}
      {data.file_closed && <p className="text-sm text-ground-600" data-testid="mentoring-read-only">{t(`${K}.readOnly`)}</p>}

      {data.concern && (
        <section role="status" data-testid="mentoring-concern"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-critical-200 bg-critical-50 p-4">
          <div className="flex min-w-0 flex-col gap-1">
            <ConcernChip t={t} />
            <span className="text-sm text-ground-800">
              {t(`${K}.concern.open`, { count: String(data.concern.count), date: formatDate(data.concern.raised_at) })}
            </span>
          </div>
          {data.can_act && token && (
            <button type="button" className={SECONDARY} disabled={busy} data-testid="mentoring-handle-concern"
              onClick={() => run(() => handleMentorConcern(id, { token }), () => t(`${K}.done.handled`))}>
              {t(`${K}.concern.handle`)}
            </button>
          )}
        </section>
      )}

      {cur ? (
        <section aria-label={t(`${K}.current.label`)} data-testid="mentoring-current"
          className={`${CARD} flex flex-wrap justify-between gap-4`}>
          <div className="flex min-w-0 flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-ground-600">{t(`${K}.current.label`)}</span>
            <strong className="break-words text-lg text-ground-900">{cur.name || '—'}</strong>
            <span className="text-sm text-ground-700">
              {[cur.area || t(`${K}.notFilled`), languagesLine(cur.languages, cur.other_language)
                && t(`${K}.current.speaks`, { languages: languagesLine(cur.languages, cur.other_language) })]
                .filter(Boolean).join(' · ')}
            </span>
            <span className="break-words text-sm text-ground-600">{[cur.email, cur.phone].filter(Boolean).join(' · ')}</span>
            <span className="text-sm text-ground-600">
              {[t(`${K}.current.since`, { date: formatDate(cur.since) }),
                t(`${K}.current.assignedBy`, { name: who(t, cur.assigned_by) }),
                t(`${K}.current.meetings`, { count: String(cur.meetings) }),
                cur.last_meeting ? t(`${K}.current.last`, { date: formatDate(cur.last_meeting) }) : '']
                .filter(Boolean).join(' · ')}
            </span>
            {cur.emailed && (
              <span className="text-sm text-positive-700" data-testid="mentoring-emailed">
                {t(`${K}.current.emailed`, { date: formatDate(cur.since) })}
              </span>
            )}
            {cur.status === 'invited' && <span className="text-xs text-caution-700">{t(`${K}.current.invited`)}</span>}
            {cur.is_the_student && (
              <span role="alert" className="text-sm font-medium text-critical-700" data-testid="mentoring-is-student">
                {t(`${K}.current.isStudent`)}
              </span>
            )}
            <span className="text-xs text-ground-600">{t(`${K}.current.fromProfile`)}</span>
          </div>
          {data.can_act && mode === 'view' && (
            <div className="flex flex-wrap items-start gap-2">
              <button type="button" className={SECONDARY} onClick={() => { setMode('assign'); setBanner(null) }}>
                {t(`${K}.change`)}
              </button>
              <button type="button" className={SECONDARY} onClick={() => { setMode('end'); setBanner(null) }}>
                {t(`${K}.end.open`)}
              </button>
            </div>
          )}
        </section>
      ) : (
        <section data-testid="mentoring-none"
          className="flex flex-wrap items-center justify-between gap-3 py-4 md:rounded-xl md:border md:border-dashed md:border-ground-300 md:bg-ground-0 md:p-5">
          <div className="flex flex-col gap-1">
            <strong className="text-base text-ground-900">{t(`${K}.none.title`)}</strong>
            {help && <span className="text-sm text-ground-600">{help}</span>}
          </div>
          {data.can_act && mode === 'view' && (
            <button type="button" className={PRIMARY} onClick={() => { setMode('assign'); setBanner(null) }}>
              {t(`${K}.none.assign`)}
            </button>
          )}
        </section>
      )}

      {mode === 'assign' && token && (
        <AssignForm t={t} data={data} changing={!!cur} busy={busy} onCancel={() => setMode('view')}
          onSubmit={(b) => run(() => assignMentor(id, b, { token }),
            (d) => t(d.emailed ? `${K}.done.assignedEmailed` : `${K}.done.assigned`, { name: d.current?.name ?? '' }))} />
      )}
      {mode === 'end' && cur && token && (
        <EndForm t={t} name={cur.name} busy={busy} onCancel={() => setMode('view')}
          onSubmit={(reason) => run(() => endMentoring(id, { reason }, { token }),
            () => t(`${K}.done.ended`, { name: cur.name }))} />
      )}

      <section aria-label={t(`${K}.meetings.title`)} className="flex flex-col md:rounded-xl md:border md:border-ground-200 md:bg-ground-0"
        data-testid="mentoring-meetings">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ground-200 px-5 py-4 max-md:px-0">
          <h2 className="text-base font-semibold text-ground-900">{t(`${K}.meetings.title`)}</h2>
          {data.can_act && cur && mode === 'view' && (
            <button type="button" className={PRIMARY} onClick={() => { setMode('meeting'); setBanner(null) }}>
              {t(`${K}.meetings.log`)}
            </button>
          )}
        </div>
        {mode === 'meeting' && token && (
          <MeetingForm t={t} busy={busy} onCancel={() => setMode('view')}
            onSubmit={(b) => run(() => logMentoringMeeting(id, b, { token }), () => t(`${K}.done.logged`))} />
        )}
        {data.meetings.length === 0 && (
          <p className="px-5 py-4 max-md:px-0 text-sm text-ground-600">{t(`${K}.meetings.none`)}</p>
        )}
        {data.meetings.map((m) => (
          <article key={m.id} className="flex flex-col gap-1 border-b border-ground-100 px-5 py-4 last:border-b-0 max-md:px-0"
            data-testid={`mentoring-meeting-${m.id}`}>
            <strong className="text-sm text-ground-900">
              {[formatDate(m.met_on), t(`${K}.mode.${m.mode}`),
                m.minutes ? t(`${K}.meetings.minutesShort`, { count: String(m.minutes) }) : ''].filter(Boolean).join(' · ')}
            </strong>
            <span className="text-xs text-ground-600">
              {m.logged_by_mentor
                ? t(`${K}.meetings.withByMentor`, { mentor: m.mentor_name || '—' })
                : t(`${K}.meetings.withBy`, { mentor: m.mentor_name || '—', name: who(t, m.logged_by) })}
            </span>
            {m.concern && (
              <span className="flex flex-wrap items-center gap-2 text-xs text-ground-600" data-testid={`mentoring-meeting-concern-${m.id}`}>
                {m.concern_handled_at
                  ? t(`${K}.concern.handled`, { name: m.concern_handled_by ? who(t, m.concern_handled_by) : t(`${K}.someone`),
                    date: formatDate(m.concern_handled_at) })
                  : <ConcernChip t={t} />}
              </span>
            )}
            <p className="whitespace-pre-line break-words text-sm text-ground-700">{m.notes}</p>
            {m.next_step && (
              <p className="break-words text-sm text-ground-700">{t(`${K}.meetings.nextStepLine`, { step: m.next_step })}</p>
            )}
          </article>
        ))}
        {past.map((p) => (
          <p key={p.id} className="border-t border-ground-100 px-5 py-3 max-md:px-0 text-sm text-ground-600" data-testid={`mentoring-past-${p.id}`}>
            {t(`${K}.history.line`, { name: p.name || '—', from: formatDate(p.started_at), to: formatDate(p.ended_at),
              count: String(p.meetings) })}
            {p.end_reason && ` ${t(`${K}.history.reason`, { reason: p.end_reason })}`}
          </p>
        ))}
      </section>
    </div>
  )
}

/** S7c: the mentor is worried about this scholar (not yet handled by staff). */
function ConcernChip({ t }: { t: T }) {
  return (
    <span className="self-start whitespace-nowrap rounded-full bg-critical-50 px-2 py-0.5 text-xs font-medium text-critical-700"
      data-testid="mentor-concerned-chip">
      {t('admin.scholars.mentorConcerned')}
    </span>
  )
}
