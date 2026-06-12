'use client'

/**
 * Student self-serve income route switch (post-submit Action Centre).
 *
 * A submitted student whose income route is wrong (e.g. they were told "Upload your
 * STR" but have no STR) can change it in place: pick STR (whose name) or the salary
 * route (who works), confirm, and the backend flips `income_route`, recomputes the
 * document tasks, and never re-blocks the submission. Mirrors the income wizard's
 * route question — see lib/incomeWizard.ts for the shared completeness rule.
 */

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { switchIncomeRoute } from '@/lib/api'

const EARNERS = ['father', 'mother', 'guardian'] as const          // STR route: one earner
const MEMBERS = ['father', 'mother', 'guardian', 'brother', 'sister'] as const  // salary route: many

export default function IncomeRouteSwitch({
  token,
  applicationId,
  onDone,
}: {
  token: string | null
  applicationId: number
  /** Refetch the Action Centre tasks after a successful switch. */
  onDone: () => void
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const [route, setRoute] = useState<'str' | 'salary' | ''>('')
  const [earner, setEarner] = useState('')
  const [members, setMembers] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Mirrors backend wizardComplete: STR needs an earner, salary needs ≥1 member.
  const valid = route === 'str' ? !!earner : route === 'salary' ? members.length > 0 : false

  const reset = () => { setOpen(false); setRoute(''); setEarner(''); setMembers([]); setError(null) }
  const toggleMember = (m: string) =>
    setMembers((s) => (s.includes(m) ? s.filter((x) => x !== m) : [...s, m]))

  const confirm = async () => {
    if (!token || !valid) return
    setBusy(true)
    setError(null)
    try {
      await switchIncomeRoute(
        applicationId,
        route === 'str'
          ? { income_route: 'str', income_earner: earner }
          : { income_route: 'salary', income_working_members: members },
        { token },
      )
      reset()
      onDone()
    } catch {
      setError(t('scholarship.incomeRouteSwitch.error'))
      setBusy(false)
    }
  }

  // Collapsed: a quiet secondary link beneath the income tasks.
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-sm font-medium text-primary-600 underline-offset-2 hover:underline"
      >
        {t('scholarship.incomeRouteSwitch.cta')}
      </button>
    )
  }

  const Chip = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
        active ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
      <p className="text-xs font-medium text-gray-400">{t('scholarship.actionCentre.fromAssistant')}</p>
      <h3 className="font-semibold text-gray-900">{t('scholarship.incomeRouteSwitch.title')}</h3>
      <p className="mt-1 text-sm text-gray-500">{t('scholarship.incomeRouteSwitch.help')}</p>

      {/* Route choice */}
      <div className="mt-4 space-y-2">
        {(['str', 'salary'] as const).map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setRoute(r)}
            className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left ${
              route === r ? 'border-primary-500 bg-primary-50 ring-1 ring-primary-500' : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <span
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 ${
                route === r ? 'border-primary-500' : 'border-gray-300'
              }`}
            >
              {route === r && <span className="h-2 w-2 rounded-full bg-primary-500" />}
            </span>
            <span className="text-sm font-medium text-gray-900">{t(`scholarship.incomeRouteSwitch.route.${r}`)}</span>
          </button>
        ))}
      </div>

      {/* STR → whose name */}
      {route === 'str' && (
        <div className="mt-4">
          <p className="text-sm font-medium text-gray-700">{t('scholarship.incomeRouteSwitch.earnerQ')}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {EARNERS.map((e) => (
              <Chip key={e} active={earner === e} label={t(`scholarship.incomeRouteSwitch.member.${e}`)} onClick={() => setEarner(e)} />
            ))}
          </div>
        </div>
      )}

      {/* Salary → who works */}
      {route === 'salary' && (
        <div className="mt-4">
          <p className="text-sm font-medium text-gray-700">{t('scholarship.incomeRouteSwitch.membersQ')}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {MEMBERS.map((m) => (
              <Chip key={m} active={members.includes(m)} label={t(`scholarship.incomeRouteSwitch.member.${m}`)} onClick={() => toggleMember(m)} />
            ))}
          </div>
        </div>
      )}

      <p className="mt-3 text-xs text-gray-400">{t('scholarship.incomeRouteSwitch.note')}</p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-4 flex gap-3">
        <button
          type="button"
          onClick={reset}
          disabled={busy}
          className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50"
        >
          {t('scholarship.incomeRouteSwitch.cancel')}
        </button>
        <button
          type="button"
          onClick={confirm}
          disabled={busy || !valid}
          className="flex-1 rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
        >
          {busy ? t('scholarship.incomeRouteSwitch.confirming') : t('scholarship.incomeRouteSwitch.confirm')}
        </button>
      </div>
    </div>
  )
}
