'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import type { SponsorPoolCard } from '@/lib/api'

/**
 * My Giving — the sponsor's home. R1 preserves the existing balance + "students you
 * support" + thank-you messages. R2 enriches this with impact numbers, a giving donut
 * and per-student journeys.
 */
export default function MyGivingPage() {
  const { t } = useT()
  const { account } = useSponsorAuth()
  const { wallet, gradMessages } = useSponsorPortal()

  return (
    <div className="space-y-8">
      {/* Account + balance + browse CTA */}
      <div className="rounded-2xl border bg-white px-6 py-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-400">{t('sponsorPortal.myStudents.welcome')}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-lg font-bold text-gray-900">{account?.name || ''}</span>
            <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">
              {t('sponsorPortal.myStudents.approvedPill')}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {wallet && (
            <div className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-2.5 text-right">
              <p className="text-xs uppercase tracking-wide text-blue-500">{t('sponsorPortal.myStudents.balance')}</p>
              <p className="text-lg font-bold text-blue-800">RM {wallet.balance}</p>
            </div>
          )}
          <Link href="/sponsor/students" className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 whitespace-nowrap">
            {t('sponsorPortal.nav.support')} →
          </Link>
        </div>
      </div>

      {/* Students you support */}
      {wallet && wallet.sponsorships.length > 0 ? (
        <section>
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900">{t('sponsorPortal.myStudents.title')}</h2>
          <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.myStudents.subtitle')}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {wallet.sponsorships.map((sp) => {
              const st = sp.student
              const offered = sp.status === 'offered'
              return (
                <div key={sp.id} className={`rounded-xl border p-4 ${offered ? 'bg-gray-50' : 'bg-white'}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900">{st.ref}</span>
                    {st.state && <span className="text-xs text-gray-500">{st.state}</span>}
                  </div>
                  <p className="text-sm text-gray-800 mt-2">{st.field || '—'}</p>
                  {st.academic && <p className="text-xs text-gray-500 mt-1">{st.academic}</p>}
                  <p className="text-xs text-gray-500 mt-1">
                    RM {sp.amount}{st.programme_months ? ` · ${st.programme_months} ${t('sponsorPortal.myStudents.months')}` : ''}
                  </p>
                  <div className="mt-3">
                    {offered ? (
                      <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-200 text-gray-600">
                        ⏳ {t('sponsorPortal.myStudents.awaiting')}
                      </span>
                    ) : (
                      <ProgressBadge state={st.progress_state} t={t} />
                    )}
                  </div>
                  {st.funding_categories.length > 0 && (
                    <p className="text-xs text-gray-400 mt-3 pt-3 border-t">{st.funding_categories.join(' · ')}</p>
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
