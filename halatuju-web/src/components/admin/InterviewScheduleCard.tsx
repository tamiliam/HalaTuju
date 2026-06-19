'use client'

import { useMemo, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatMyt } from '@/lib/interviewTime'
import {
  cellDateStr, daySlots, earliestDateStr, intlLocale, isoToSlotValue, monthCells, slotLabel12h,
} from '@/lib/interviewSlots'
import { proposeInterviewSlots, type InterviewSchedule } from '@/lib/admin-api'

const REQUIRED_PROPOSALS = 3
// Short weekday headers (Sun–Sat) localised via Intl; 2023-01-01 was a Sunday.
const WEEKDAY_SEEDS = Array.from({ length: 7 }, (_, i) => new Date(2023, 0, 1 + i))

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden>
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m2 0v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6m4 5v6m6-6v6" />
    </svg>
  )
}

/** Reviewer-facing "Propose interview times" card on the cockpit. The assigned reviewer
 *  offers EXACTLY 3 times (the student picks one + books, which generates the Meet link).
 *  Calendly-style month calendar + 12-hour time pills, 08:00–21:30 MYT on 30-min steps.
 *  Existing proposals pre-load so the menu can be revised; times the reviewer already holds
 *  for ANOTHER student are greyed out to avoid double-booking. Dark unless `schedule.enabled`. */
export default function InterviewScheduleCard({
  appId, token, schedule, onChange,
}: {
  appId: number
  token: string
  schedule: InterviewSchedule
  onChange: (s: InterviewSchedule) => void
}) {
  const { t, locale } = useT()
  const il = intlLocale(locale)
  const todayNow = new Date()
  // The earliest selectable day (now + 24h lead) — days before this are disabled.
  const earliest = earliestDateStr(todayNow)
  const earliestMonth = new Date(`${earliest}T00:00`)
  const [view, setView] = useState({ y: earliestMonth.getFullYear(), m: earliestMonth.getMonth() })
  const [date, setDate] = useState(earliest)
  // Pre-load the current (unbooked) proposed times so the reviewer revises, not rebuilds.
  const [selected, setSelected] = useState<string[]>(() =>
    (schedule?.slots || [])
      .filter((s) => s.id !== schedule.booked_slot_id)
      .map((s) => isoToSlotValue(s.start))
      .slice(0, REQUIRED_PROPOSALS))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // Reviewer RESCHEDULE: move an already-booked interview (release booking → student re-picks).
  const [rescheduling, setRescheduling] = useState(false)
  const [confirmingReschedule, setConfirmingReschedule] = useState(false)

  // The current (unbooked) proposed menu — shown read-only until the reviewer chooses to revise.
  const proposedSlots = useMemo(
    () => (schedule?.slots || [])
      .filter((s) => s.id !== schedule.booked_slot_id)
      .slice().sort((a, b) => a.start.localeCompare(b.start)),
    [schedule],
  )
  // Start in the picker only when nothing's proposed yet; otherwise show the locked view.
  const [editing, setEditing] = useState(proposedSlots.length === 0)

  // Times this reviewer already holds for OTHER students (proposed or booked) — blocked here.
  const reviewerBusy = useMemo(
    () => new Set((schedule?.reviewer_busy || []).map(isoToSlotValue)),
    [schedule],
  )
  // Future slots for the selected day (past times dropped, like Calendly).
  const slots = useMemo(() => daySlots(date).filter((s) => !s.tooEarly), [date])
  // Days the reviewer has picked a time on → a dot on the calendar.
  const pickedDays = useMemo(() => new Set(selected.map((v) => v.slice(0, 10))), [selected])

  if (!schedule?.enabled) return null

  const atCurrentMonth = view.y === earliestMonth.getFullYear() && view.m === earliestMonth.getMonth()
  const shiftMonth = (delta: number) =>
    setView((v) => {
      const d = new Date(v.y, v.m + delta, 1)
      return { y: d.getFullYear(), m: d.getMonth() }
    })
  const monthTitle = new Intl.DateTimeFormat(il, { month: 'long', year: 'numeric' })
    .format(new Date(view.y, view.m, 1))
  const dateHeading = new Intl.DateTimeFormat(il, { weekday: 'long', day: 'numeric', month: 'long' })
    .format(new Date(`${date}T00:00`))

  const toggle = (value: string) =>
    setSelected((prev) => {
      if (prev.includes(value)) return prev.filter((v) => v !== value)
      if (prev.length >= REQUIRED_PROPOSALS) return prev
      return [...prev, value]
    })

  const ready = selected.length === REQUIRED_PROPOSALS

  const propose = async () => {
    if (!ready) return
    setBusy(true); setError('')
    try {
      const next = await proposeInterviewSlots(appId, [...selected].sort(), { token, reschedule: rescheduling })
      onChange(next)
      setEditing(false)        // back to the locked "Proposed times" view
      setRescheduling(false)
    } catch {
      setError(t('admin.scholarship.interview.schedule.error'))
    } finally { setBusy(false) }
  }

  // Reviewer moves a booked interview: open the picker fresh (new times) in reschedule mode.
  const startReschedule = () => {
    setSelected([])
    setError('')
    setConfirmingReschedule(false)
    setRescheduling(true)
    setEditing(true)
  }

  const startEdit = () => {
    // Re-open the picker pre-loaded with the current menu, so it's a revise, not a rebuild.
    setSelected(proposedSlots.map((s) => isoToSlotValue(s.start)).slice(0, REQUIRED_PROPOSALS))
    setError('')
    setEditing(true)
  }
  const cancelEdit = () => {
    setSelected(proposedSlots.map((s) => isoToSlotValue(s.start)).slice(0, REQUIRED_PROPOSALS))
    setError('')
    setEditing(false)
    setRescheduling(false)   // back to the booked view if we were mid-reschedule
  }

  return (
    <section className="mt-6 rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="text-base font-semibold tracking-tight text-gray-900">
        {t('admin.scholarship.interview.schedule.title')}
      </h2>
      {/* The subheader is shown only while proposing, and adapts to first-time vs revising.
          In the locked/booked/cancelled states the in-card copy carries the message. */}
      {((schedule.status !== 'booked' && schedule.status !== 'cancelled') || rescheduling) && editing && (
        <p className="mt-1 text-xs text-gray-500">
          {t(rescheduling
            ? 'admin.scholarship.interview.schedule.rescheduleIntro'
            : proposedSlots.length > 0
              ? 'admin.scholarship.interview.schedule.introAlternatives'
              : 'admin.scholarship.interview.schedule.intro')}
        </p>
      )}

      {schedule.status === 'booked' && schedule.start && !rescheduling && (
        <div className="mt-3 rounded-xl border border-green-200 bg-green-50/50 p-3 text-sm">
          <div className="font-medium text-gray-900">
            {t('admin.scholarship.interview.schedule.booked')}: {formatMyt(schedule.start)}
          </div>
          {schedule.meeting_url
            ? <a href={schedule.meeting_url} target="_blank" rel="noreferrer"
                 className="mt-2 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                {t('admin.scholarship.interview.schedule.meetLink')}
              </a>
            : <span className="mt-1 block text-xs text-gray-500">
                {t('admin.scholarship.interview.schedule.noLink')}
              </span>}
          {/* Emergency reschedule: move the time (releases the booking, student re-picks). No
              reviewer self-cancel — an emergency reschedules; a true hand-off is an admin reassign. */}
          <div className="mt-3 border-t border-green-200/70 pt-2">
            {confirmingReschedule ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5">
                <p className="text-gray-800">{t('admin.scholarship.interview.schedule.rescheduleConfirm')}</p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <button type="button" onClick={startReschedule}
                    className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700">
                    {t('admin.scholarship.interview.schedule.rescheduleYes')}
                  </button>
                  <button type="button" onClick={() => setConfirmingReschedule(false)}
                    className="text-sm text-gray-600 hover:text-gray-800">
                    {t('admin.scholarship.interview.schedule.rescheduleKeep')}
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-right">
                <button type="button" onClick={() => setConfirmingReschedule(true)}
                  className="text-xs text-blue-600 hover:underline">
                  {t('admin.scholarship.interview.schedule.reschedule')}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {schedule.status === 'cancelled' && (
        <p className="mt-3 text-sm text-amber-700">
          {t('admin.scholarship.interview.schedule.cancelledNote')}
        </p>
      )}

      {/* Once proposed, the menu is LOCKED to a read-only view until the reviewer chooses to
          revise — "Propose alternative times" reopens the picker (also for a student who says
          none of the times work). Hidden once booked. */}
      {schedule.status !== 'booked' && !editing && (
        <div className="mt-4">
          {/* The student said none of these work — prompt the reviewer to propose alternatives. */}
          {schedule.alternatives_requested && (
            <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <div className="font-medium">{t('admin.scholarship.interview.schedule.altRequestedTitle')}</div>
              {schedule.alternatives_note && (
                <p className="mt-1 italic">“{schedule.alternatives_note}”</p>
              )}
              <p className="mt-1 text-xs">{t('admin.scholarship.interview.schedule.altRequestedHint')}</p>
            </div>
          )}
          <div className="text-sm font-semibold text-gray-900">
            {t('admin.scholarship.interview.schedule.proposedHeading')}
          </div>
          <p className="mt-0.5 text-xs text-gray-500">
            {t('admin.scholarship.interview.schedule.awaitingChoice')}
          </p>
          <ul className="mt-3 space-y-2">
            {proposedSlots.map((s) => (
              <li key={s.id}
                className="flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                {formatMyt(s.start)}
              </li>
            ))}
          </ul>
          <button type="button" onClick={startEdit}
            className="mt-4 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
            {t('admin.scholarship.interview.schedule.proposeAlternative')}
          </button>
        </div>
      )}

      {/* Picker (edit mode) — hidden once booked, except while rescheduling (moving the time). */}
      {(schedule.status !== 'booked' || rescheduling) && editing && (
        <>
          {/* Calendly-style: month calendar (left) + 12-hour time pills (right). */}
          <div className="mt-4 grid gap-5 md:grid-cols-2">
            {/* Left: month calendar */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">{monthTitle}</span>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => shiftMonth(-1)} disabled={atCurrentMonth}
                    aria-label="previous month"
                    className="rounded-md px-2.5 py-1 text-2xl leading-none text-gray-600 hover:bg-gray-100 disabled:opacity-30">‹</button>
                  <button type="button" onClick={() => shiftMonth(1)} aria-label="next month"
                    className="rounded-md px-2.5 py-1 text-2xl leading-none text-gray-600 hover:bg-gray-100">›</button>
                </div>
              </div>
              <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-medium uppercase text-gray-400">
                {WEEKDAY_SEEDS.map((d, i) => (
                  <div key={i}>{new Intl.DateTimeFormat(il, { weekday: 'short' }).format(d).slice(0, 3)}</div>
                ))}
              </div>
              <div className="mt-1 grid grid-cols-7 gap-1">
                {monthCells(view.y, view.m).map((day, i) => {
                  if (day == null) return <div key={i} />
                  const ds = cellDateStr(view.y, view.m, day)
                  const tooEarly = ds < earliest
                  const isSel = ds === date
                  const hasPick = pickedDays.has(ds)
                  return (
                    <button key={i} type="button" disabled={tooEarly}
                      onClick={() => setDate(ds)}
                      className={
                        'relative mx-auto flex h-9 w-9 items-center justify-center rounded-full text-sm transition ' +
                        (isSel
                          ? 'bg-blue-600 font-semibold text-white'
                          : tooEarly
                            ? 'text-gray-300'
                            : 'text-gray-800 hover:bg-blue-50')
                      }>
                      {day}
                      {hasPick && !isSel && (
                        <span className="absolute bottom-1 h-1 w-1 rounded-full bg-blue-500" />
                      )}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Right: time pills for the selected day */}
            <div className="md:border-l md:border-gray-100 md:pl-5">
              <div className="text-sm font-semibold text-gray-900">{dateHeading}</div>
              <p className="text-[11px] text-gray-400">
                {t('admin.scholarship.interview.schedule.availableTimes')}
              </p>
              {slots.length === 0 ? (
                <p className="mt-2 text-sm italic text-gray-400">
                  {t('admin.scholarship.interview.schedule.noneToday')}
                </p>
              ) : (
                <div className="mt-2 max-h-72 space-y-2 overflow-y-auto pr-1">
                  {slots.map((s) => {
                    const isBusy = reviewerBusy.has(s.value)
                    const isSel = selected.includes(s.value)
                    const atMax = selected.length >= REQUIRED_PROPOSALS && !isSel
                    return (
                      <button key={s.value} type="button" disabled={isBusy || atMax}
                        onClick={() => toggle(s.value)}
                        title={isBusy ? t('admin.scholarship.interview.schedule.busyOther') : undefined}
                        className={
                          'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition ' +
                          (isSel
                            ? 'border-blue-600 bg-blue-600 text-white'
                            : isBusy
                              ? 'border-gray-200 bg-gray-50 text-gray-400 line-through'
                              : atMax
                                ? 'border-gray-200 text-gray-300'
                                : 'border-gray-200 text-gray-800 hover:border-blue-500 hover:bg-blue-50')
                        }>
                        <span className={'h-1.5 w-1.5 rounded-full ' + (isSel ? 'bg-white' : 'bg-green-500')} />
                        {slotLabel12h(s.label)}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Selected summary (can span days) + submit. Exactly 3 required. */}
          <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
            <div className="text-xs font-medium text-gray-700">
              {t('admin.scholarship.interview.schedule.selectedCount')
                .replace('{n}', String(selected.length)).replace('{max}', String(REQUIRED_PROPOSALS))}
            </div>
            {selected.length > 0 && (
              <ul className="space-y-1">
                {[...selected].sort().map((v) => (
                  <li key={v} className="flex items-center justify-between gap-3 text-sm text-gray-800">
                    <span>{formatMyt(v)}</span>
                    <button type="button" onClick={() => toggle(v)}
                      aria-label={t('admin.scholarship.interview.schedule.removeSlot')}
                      className="text-gray-400 hover:text-red-600">
                      <TrashIcon />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex items-center gap-3">
              <button type="button" onClick={propose} disabled={busy || !ready}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                {t('admin.scholarship.interview.schedule.propose')}
              </button>
              {(proposedSlots.length > 0 || rescheduling) && (
                <button type="button" onClick={cancelEdit} disabled={busy}
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50">
                  {t('admin.scholarship.interview.schedule.cancelEdit')}
                </button>
              )}
              {!ready && (
                <span className="text-xs text-gray-500">
                  {t('admin.scholarship.interview.schedule.pickThree')}
                </span>
              )}
            </div>
            {error && <p className="text-xs text-red-600">{error}</p>}
          </div>
        </>
      )}
    </section>
  )
}
