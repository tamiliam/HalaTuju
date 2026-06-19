'use client'

import { Fragment } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { journeyStages, type JourneyStatus } from '@/lib/sponsorJourney'
import type { SponsorPoolCard } from '@/lib/api'

/**
 * My Giving — the sponsor's home, led by impact (R2): an impact-number strip, the
 * giving donut, the students you support with a journey tracker, and thank-you
 * messages. All figures come from the shared portal context (one fetch).
 */
export default function MyGivingPage() {
  const { t } = useT()
  const { account } = useSponsorAuth()
  const { wallet, impact, activity, community, gradMessages } = useSponsorPortal()

  const b = impact?.balance
  const committed = b ? parseFloat(b.committed) || 0 : 0
  const completed = b ? parseFloat(b.completed) || 0 : 0
  const available = b ? parseFloat(b.available) || 0 : 0
  const total = committed + completed + available
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0)
  const c1 = pct(committed)
  const c2 = c1 + pct(completed)
  const donut = total > 0
    ? `conic-gradient(#2563eb 0 ${c1}%, #22c55e ${c1}% ${c2}%, #e5e7eb ${c2}% 100%)`
    : '#e5e7eb'

  return (
    <div className="space-y-8">
      {/* Welcome + browse CTA */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">{t('sponsorPortal.myStudents.welcome')}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-2xl font-bold text-gray-900">{account?.name || ''}</span>
            <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">
              {t('sponsorPortal.myStudents.approvedPill')}
            </span>
          </div>
        </div>
        <Link href="/sponsor/students" className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 whitespace-nowrap">
          {t('sponsorPortal.nav.support')} →
        </Link>
      </div>

      {/* Impact numbers */}
      {impact && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat label={t('sponsorPortal.impact.totalGiven')} value={`RM ${impact.total_given}`}
            sub={t('sponsorPortal.impact.acrossStudents').replace('{n}', String(impact.students_supported))} />
          <Stat label={t('sponsorPortal.impact.supported')} value={String(impact.students_supported)}
            sub={`${impact.students_active} ${t('sponsorPortal.journey.studying').toLowerCase()} · ${impact.students_graduated} ${t('sponsorPortal.journey.graduated').toLowerCase()}`} />
          <Stat label={t('sponsorPortal.impact.semesters')} value={String(impact.semesters_completed)}
            sub={t('sponsorPortal.impact.semestersBy')} />
          <Stat label={t('sponsorPortal.impact.graduated')} value={impact.students_graduated > 0 ? `${impact.students_graduated} 🎉` : '0'}
            sub={t('sponsorPortal.impact.graduatedSub')} valueClass={impact.students_graduated > 0 ? 'text-green-600' : 'text-gray-900'} />
        </div>
      )}

      {/* Giving donut */}
      {impact && (
        <div className="rounded-2xl border bg-white p-5 sm:max-w-md">
          <h2 className="font-semibold text-gray-900">{t('sponsorPortal.impact.givingTitle')}</h2>
          <div className="flex items-center gap-5 mt-4">
            <div className="w-28 h-28 shrink-0 rounded-full grid place-items-center" style={{ background: donut }}>
              <div className="bg-white w-16 h-16 rounded-full grid place-items-center text-center">
                <span className="text-[11px] leading-tight text-gray-500">
                  {t('sponsorPortal.impact.available')}<br /><b className="text-gray-900 text-sm">RM {available.toLocaleString()}</b>
                </span>
              </div>
            </div>
            <ul className="text-sm space-y-2 flex-1">
              <LegendRow color="#2563eb" label={t('sponsorPortal.impact.committed')} amount={committed} />
              <LegendRow color="#22c55e" label={t('sponsorPortal.impact.completed')} amount={completed} />
              <LegendRow color="#e5e7eb" label={t('sponsorPortal.impact.available')} amount={available} />
            </ul>
          </div>
          <p className="text-[11px] text-gray-400 mt-3 leading-relaxed">{t('sponsorPortal.impact.balanceNote')}</p>
        </div>
      )}

      {/* Recent activity */}
      {activity.length > 0 && (
        <section className="rounded-2xl border bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">{t('sponsorPortal.activity.title')}</h2>
            <span className="text-xs text-gray-400">{t('sponsorPortal.activity.live')}</span>
          </div>
          <ul className="divide-y divide-gray-100 mt-1">
            {activity.slice(0, 8).map((e, i) => (
              <li key={i} className="py-3 flex items-start gap-3">
                <span className="mt-0.5 text-lg">{ACTIVITY_ICON[e.type] || '•'}</span>
                <div className="flex-1">
                  <p className="text-sm text-gray-800">{t(`sponsorPortal.activity.${e.type}`).replace('{ref}', e.ref)}</p>
                  <p className="text-xs text-gray-400">{new Date(e.at).toLocaleDateString()}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Students you support */}
      {wallet && wallet.sponsorships.length > 0 ? (
        <section>
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900">{t('sponsorPortal.myStudents.title')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.myStudents.subtitle')}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {wallet.sponsorships.map((sp) => {
              const st = sp.student
              const offered = sp.status === 'offered'
              return (
                <div key={sp.id} className={`rounded-2xl border p-4 ${offered ? 'bg-gray-50' : 'bg-white'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-semibold text-gray-900">{st.ref}</span>
                    {offered
                      ? <span className="text-xs rounded-full bg-gray-200 text-gray-600 px-2 py-0.5">⏳ {t('sponsorPortal.myStudents.awaiting')}</span>
                      : <ProgressBadge state={st.progress_state} t={t} />}
                  </div>
                  <p className="text-sm text-gray-800 mt-2">{st.field || '—'}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {st.state ? `${st.state} · ` : ''}RM {sp.amount}{st.programme_months ? ` / ${st.programme_months} ${t('sponsorPortal.myStudents.months')}` : ''}
                  </p>
                  {!offered && (
                    <JourneyTracker onboarded={sp.onboarded} state={st.progress_state} semesters={sp.semesters} t={t} />
                  )}
                </div>
              )
            })}
          </div>
        </section>
      ) : (
        <div className="rounded-2xl border border-dashed bg-white px-6 py-10 text-center">
          <p className="text-sm text-gray-500">{t('sponsorPortal.myStudents.none')}</p>
          <Link href="/sponsor/students" className="inline-block mt-3 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">
            {t('sponsorPortal.nav.support')} →
          </Link>
        </div>
      )}

      {/* Thank-you messages from students you supported — anonymous, linked to ref only */}
      {gradMessages.length > 0 && (
        <section>
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900">{t('sponsorPortal.graduationMessages.title')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.graduationMessages.subtitle')}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {gradMessages.map((m, i) => (
              <div key={i} className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
                <p className="text-sm text-gray-800">💬 “{m.text}”</p>
                <p className="text-xs text-gray-500 mt-3">{t('sponsorPortal.graduationMessages.attribution')} · {m.ref}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Community belonging strip */}
      {community && community.students_supported > 0 && (
        <div className="rounded-2xl bg-gradient-to-r from-blue-600 to-blue-700 text-white p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm opacity-90">{t('sponsorPortal.community.line1').replace('{n}', String(community.sponsors))}</p>
            <p className="text-lg font-semibold">{t('sponsorPortal.community.line2').replace('{n}', String(community.students_supported))}</p>
          </div>
          {community.students_waiting > 0 && (
            <Link href="/sponsor/students" className="px-4 py-2 bg-white/15 hover:bg-white/25 rounded-xl text-sm font-semibold whitespace-nowrap">
              {t('sponsorPortal.community.waiting').replace('{n}', String(community.students_waiting))} →
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

const ACTIVITY_ICON: Record<string, string> = {
  funded: '🤝', accepted: '✅', semester: '📘', graduated: '🎓', thank_you: '💬',
}

function Stat({ label, value, sub, valueClass = 'text-gray-900' }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <div className="bg-white rounded-2xl border p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold ${valueClass}`}>{value}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

function LegendRow({ color, label, amount }: { color: string; label: string; amount: number }) {
  return (
    <li className="flex items-center justify-between">
      <span className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />{label}</span>
      <b>RM {amount.toLocaleString()}</b>
    </li>
  )
}

const DOT: Record<JourneyStatus, string> = {
  done: 'bg-green-500',
  now: 'bg-blue-500 ring-4 ring-blue-100',
  todo: 'bg-gray-200',
}

/** The Matched → Onboarded → Studying → Graduated tracker (R2). */
function JourneyTracker({ onboarded, state, semesters, t }: {
  onboarded: boolean
  state: SponsorPoolCard['progress_state']
  semesters: number
  t: (k: string) => string
}) {
  const stages = journeyStages({ onboarded, progressState: state })
  return (
    <div className="mt-4">
      <div className="flex items-start text-center">
        {stages.map((s, i) => (
          <Fragment key={s.key}>
            {i > 0 && <div className={`flex-1 h-px mt-1 ${stages[i - 1].status === 'done' ? 'bg-green-200' : 'bg-gray-200'}`} />}
            <div className="flex flex-col items-center">
              <span className={`w-2.5 h-2.5 rounded-full ${DOT[s.status]}`} />
              <span className="text-[9px] text-gray-400 mt-1">{t(`sponsorPortal.journey.${s.key}`)}</span>
            </div>
          </Fragment>
        ))}
      </div>
      {semesters > 0 && (
        <p className="text-[10px] text-gray-400 mt-1.5">{t('sponsorPortal.journey.semesters').replace('{n}', String(semesters))}</p>
      )}
    </div>
  )
}

/** The coarse, non-identifying progress badge on a sponsored-student card. */
function ProgressBadge({ state, t }: { state: SponsorPoolCard['progress_state']; t: (k: string) => string }) {
  if (!state) return null
  const tone: Record<string, string> = {
    on_track: 'bg-green-100 text-green-700',
    semester_completed: 'bg-blue-100 text-blue-700',
    needs_attention: 'bg-amber-100 text-amber-700',
    graduated: 'bg-indigo-100 text-indigo-700',
  }
  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${tone[state] || 'bg-gray-100 text-gray-600'}`}>
      {t(`sponsorPortal.myStudents.progress.${state}`)}
    </span>
  )
}
