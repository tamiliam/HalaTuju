'use client'

import { useMemo, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatMyt } from '@/lib/interviewTime'
import {
  cellDateStr, daySlots, intlLocale, isoToSlotValue, monthCells, slotLabel12h, todayStr,
} from '@/lib/interviewSlots'
import {
  proposeInterviewSlots,
  withdrawInterviewSlot,
  type InterviewSchedule,
} from '@/lib/admin-api'

const MAX_PROPOSALS = 3
// Short weekday headers (Sun–Sat) localised via Intl; 2023-01-01 was a Sunday.
const WEEKDAY_SEEDS = Array.from({ length: 7 }, (_, i) => new Date(2023, 0, 1 + i))

/** Reviewer-facing "Propose interview times" card on the cockpit. The assigned
 *  reviewer offers 2–3 times; the student picks one (the student side books +
 *  generates the Meet link). Dark unless `schedule.enabled`. */
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
  const today = todayStr()
  const todayNow = new Date()
  const [view, setView] = useState({ y: todayNow.getFullYear(), m: todayNow.getMonth() })
  const [date, setDate] = useState(today)
  const [selected, setSelected] = useState<string[]>([])  // "YYYY-MM-DDThh:mm" values
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // Slot values already on the menu (proposed or booked) — shown as taken, not re-offerable.
  const taken = useMemo(
    () => new Set((schedule?.slots || []).map((s) => isoToSlotValue(s.start))),
    [schedule],
  )
  // Future slots for the selected day (past times dropped, like Calendly).
  const slots = useMemo(() => daySlots(date).filter((s) => !s.past), [date])
  // Days the reviewer has already picked a time on → a dot on the calendar.
  const pickedDays = useMemo(() => new Set(selected.map((v) => v.slice(0, 10))), [selected])

  if (!schedule?.enabled) return null

  const atCurrentMonth = view.y === todayNow.getFullYear() && view.m === todayNow.getMonth()
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
      if (prev.length >= MAX_PROPOSALS) return prev
      return [...prev, value]
    })

  const propose = async () => {
    if (!selected.length) { setError(t('admin.scholarship.interview.schedule.needFuture')); return }
    setBusy(true); setError('')
    try {
      const next = await proposeInterviewSlots(appId, [...selected].sort(), { token })
      onChange(next)
      setSelected([])
    } catch {
      setError(t('admin.scholarship.interview.schedule.error'))
    } finally { setBusy(false) }
  }

  const withdraw = async (slotId: number) => {
    setBusy(true); setError('')
    try { onChange(await withdrawInterviewSlot(appId, slotId, { token })) }
    catch { setError(t('admin.scholarship.interview.schedule.error')) }
    finally { setBusy(false) }
  }

  return (
    <section className="mt-6 rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="text-base font-semibold tracking-tight text-gray-900">
        {t('admin.scholarship.interview.schedule.title')}
      </h2>
      <p className="mt-1 text-xs text-gray-500">{t('admin.scholarship.interview.schedule.intro')}</p>

      {schedule.status === 'booked' && schedule.start && (
        <div className="mt-3 rounded-xl border border-green-200 bg-green-50/50 p-3 text-sm">
          <div className="font-medium text-gray-900">
            {t('admin.scholarship.interview.schedule.booked')}: {formatMyt(schedule.start)}
          </div>
          {schedule.meeting_url
            ? <a href={schedule.meeting_url} target="_blank" rel="noreferrer"
                 className="mt-1 inline-block text-blue-600 underline">
                {t('admin.scholarship.interview.schedule.meetLink')}
              </a>
            : <span className="mt-1 block text-xs text-gray-500">
                {t('admin.scholarship.interview.schedule.noLink')}
              </span>}
        </div>
      )}

      {schedule.status === 'cancelled' && (
        <p className="mt-3 text-sm text-amber-700">
          {t('admin.scholarship.interview.schedule.cancelledNote')}
        </p>
      )}

      {/* Active proposed (unbooked) slots */}
      <div className="mt-4">
        <div className="text-xs font-medium text-gray-700">
          {t('admin.scholarship.interview.schedule.proposed')}
        </div>
        {schedule.slots.length === 0
          ? <p className="mt-1 text-sm text-gray-400 italic">
              {t('admin.scholarship.interview.schedule.noneProposed')}
            </p>
          : <ul className="mt-2 space-y-1.5">
              {schedule.slots.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 text-sm">
                  <span className={s.id === schedule.booked_slot_id ? 'font-medium text-green-700' : 'text-gray-800'}>
                    {formatMyt(s.start)}
                    {s.id === schedule.booked_slot_id && ` ✓`}
                  </span>
                  {s.id !== schedule.booked_slot_id && (
                    <button type="button" onClick={() => withdraw(s.id)} disabled={busy}
                      className="text-xs text-gray-400 hover:text-red-600 disabled:opacity-50">
                      {t('admin.scholarship.interview.schedule.withdraw')}
                    </button>
                  )}
                </li>
              ))}
            </ul>}
      </div>

      {/* Propose new times — Calendly-style: month calendar (left) + time pills (right).
          Reviewer taps up to 3 times (across days); 08:00–21:30 MYT, 30-min. */}
      <div className="mt-4 grid gap-5 md:grid-cols-2">
        {/* Left: month calendar */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-900">{monthTitle}</span>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => shiftMonth(-1)} disabled={atCurrentMonth}
                aria-label="previous month"
                className="rounded-md px-2 py-0.5 text-gray-500 hover:bg-gray-100 disabled:opacity-30">‹</button>
              <button type="button" onClick={() => shiftMonth(1)} aria-label="next month"
                className="rounded-md px-2 py-0.5 text-gray-500 hover:bg-gray-100">›</button>
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
              const isPast = ds < today
              const isSel = ds === date
              const hasPick = pickedDays.has(ds)
              return (
                <button key={i} type="button" disabled={isPast}
                  onClick={() => setDate(ds)}
                  className={
                    'relative mx-auto flex h-9 w-9 items-center justify-center rounded-full text-sm transition ' +
                    (isSel
                      ? 'bg-blue-600 font-semibold text-white'
                      : isPast
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
                const isTaken = taken.has(s.value)
                const isSel = selected.includes(s.value)
                const atMax = selected.length >= MAX_PROPOSALS && !isSel
                return (
                  <button key={s.value} type="button" disabled={isTaken || atMax}
                    onClick={() => toggle(s.value)}
                    title={isTaken ? t('admin.scholarship.interview.schedule.slotTaken') : undefined}
                    className={
                      'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition ' +
                      (isSel
                        ? 'border-blue-600 bg-blue-600 text-white'
                        : isTaken
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

      {/* Selected summary (can span days) + submit */}
      <div className="mt-4 space-y-3 border-t border-gray-100 pt-4">
        {selected.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-700">
              {t('admin.scholarship.interview.schedule.selectedCount')
                .replace('{n}', String(selected.length)).replace('{max}', String(MAX_PROPOSALS))}
            </div>
            <ul className="mt-1.5 space-y-1">
              {[...selected].sort().map((v) => (
                <li key={v} className="flex items-center justify-between gap-3 text-sm text-gray-800">
                  <span>{formatMyt(v)}</span>
                  <button type="button" onClick={() => toggle(v)}
                    className="text-xs text-gray-400 hover:text-red-600">×</button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <button type="button" onClick={propose} disabled={busy || selected.length === 0}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {t('admin.scholarship.interview.schedule.propose')}
        </button>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </section>
  )
}
