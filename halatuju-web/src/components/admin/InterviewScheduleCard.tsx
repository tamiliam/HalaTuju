'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatMyt } from '@/lib/interviewTime'
import {
  proposeInterviewSlots,
  withdrawInterviewSlot,
  type InterviewSchedule,
} from '@/lib/admin-api'

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
  const { t } = useT()
  const [inputs, setInputs] = useState<string[]>([''])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!schedule?.enabled) return null

  const setInput = (i: number, v: string) =>
    setInputs((prev) => prev.map((x, j) => (j === i ? v : x)))
  const addInput = () => setInputs((prev) => (prev.length >= 3 ? prev : [...prev, '']))
  const removeInput = (i: number) => setInputs((prev) => prev.filter((_, j) => j !== i))

  const propose = async () => {
    const starts = inputs.map((s) => s.trim()).filter(Boolean)
    if (!starts.length) { setError(t('admin.scholarship.interview.schedule.needFuture')); return }
    setBusy(true); setError('')
    try {
      const next = await proposeInterviewSlots(appId, starts, { token })
      onChange(next)
      setInputs([''])
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

      {/* Propose new times */}
      <div className="mt-4 space-y-2">
        {inputs.map((v, i) => (
          <div key={i} className="flex items-center gap-2">
            <input type="datetime-local" value={v} onChange={(e) => setInput(i, e.target.value)}
              className="rounded-lg border border-gray-300 px-2 py-1 text-sm" />
            {inputs.length > 1 && (
              <button type="button" onClick={() => removeInput(i)}
                className="text-xs text-gray-400 hover:text-red-600">×</button>
            )}
          </div>
        ))}
        <div className="flex items-center gap-3">
          {inputs.length < 3 && (
            <button type="button" onClick={addInput}
              className="text-xs text-blue-600 hover:underline">
              + {t('admin.scholarship.interview.schedule.addTime')}
            </button>
          )}
          <button type="button" onClick={propose} disabled={busy}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            {t('admin.scholarship.interview.schedule.propose')}
          </button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </section>
  )
}
