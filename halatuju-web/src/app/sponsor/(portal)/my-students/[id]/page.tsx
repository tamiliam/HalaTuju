'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { getMyStudentDetail, type SponsorMyStudentDetail } from '@/lib/api'
import { conceptFieldImageUrl } from '@/lib/fieldImage'
import { portfolioBadgeTone, rmWhole } from '@/lib/poolCard'
import { journeyStages } from '@/lib/sponsorJourney'


/**
 * A student the sponsor SUPPORTS — the portfolio detail page (reached by clicking a My-students
 * card). Framed as "the student you support": status, journey, the full anonymised profile, your
 * commitment, and a RESERVED spending panel (a later sprint). NO funding controls — this is not the
 * discovery page. Anonymity is inviolate: never a name/photo, only the reference + reviewed profile.
 */
export default function MyStudentDetailPage() {
  const { t } = useT()
  const { token } = useSponsorAuth()
  const params = useParams()
  const id = Number(params?.id)

  const [detail, setDetail] = useState<SponsorMyStudentDetail | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    if (!token || !id) return
    let cancelled = false
    getMyStudentDetail(id, { token })
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => { if (!cancelled) setUnavailable(true) })
    return () => { cancelled = true }
  }, [token, id])

  const back = (
    <Link href="/sponsor" className="text-sm font-medium text-info-600 hover:underline">
      ← {t('sponsorPortal.myStudents.detail.back')}
    </Link>
  )

  if (unavailable) {
    return (
      <div>
        {back}
        <p className="mt-6 text-sm text-ground-500">{t('sponsorPortal.myStudents.detail.unavailable')}</p>
      </div>
    )
  }
  if (!detail) return <div className="text-sm text-ground-400">{t('common.loading')}</div>

  const st = detail.student
  const offered = detail.status === 'offered'
  const status = st.portfolio_status
  const discontinued = status === 'discontinued'
  const stages = journeyStages({ onboarded: detail.onboarded, progressState: st.progress_state })

  return (
    <div className="max-w-3xl mx-auto">
      {back}
      <div className="mt-3 bg-ground-0 rounded-2xl border overflow-hidden shadow-sm">
        <div className="relative h-32 bg-gradient-to-br from-info-50 to-positive-50">
          {st.field_image_slug && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={conceptFieldImageUrl(st.field_image_slug)} alt="" className="w-full h-full object-cover" />
          )}
          <span className="absolute bottom-3 left-3 font-mono text-sm font-semibold bg-ground-0 border rounded-lg px-2.5 py-1">{st.ref}</span>
        </div>

        <div className="p-6">
          <h1 className="text-2xl font-bold text-ground-900 tracking-tight leading-snug">{st.course || st.field || '—'}</h1>
          {st.institution && (
            <p className="text-ground-500 mt-0.5">{st.institution}{st.state ? ` · ${st.state}` : ''}</p>
          )}

          <div className="mt-3 flex flex-wrap gap-2 items-center">
            {offered
              ? <span className="rounded-full bg-ground-200 text-ground-600 px-3 py-1 text-xs font-semibold whitespace-nowrap">⏳ {t('sponsorPortal.myStudents.awaiting')}</span>
              : status && (
                <span className={`rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap ${portfolioBadgeTone(status)}`}>
                  {t(`sponsorPortal.myStudents.status.${status}`)}
                </span>
              )}
            {st.academic && <span className="rounded-md bg-info-50 text-info-700 px-2.5 py-1 text-xs font-medium">{st.academic}</span>}
            {st.supported_semesters ? (
              <span className="rounded-md bg-info-50 text-info-700 px-2.5 py-1 text-xs font-medium">
                {t('sponsorPortal.myStudents.detail.supportedSems').replace('{n}', String(st.supported_semesters))}
              </span>
            ) : null}
          </div>

          <p className="mt-5 text-sm text-ground-600">
            {t('sponsorPortal.myStudents.detail.supportLine').replace('{amount}', rmWhole(detail.amount))}
          </p>

          {!offered && (
            <div className="mt-5 flex items-start">
              {stages.map((s, i) => {
                const withdrew = discontinued && s.key === 'studying'
                const dot = withdrew ? 'bg-critical-500'
                  : s.status === 'done' ? 'bg-positive-500'
                  : s.status === 'now' ? 'bg-info-500 ring-4 ring-info-100' : 'bg-ground-200'
                return (
                  <div key={s.key} className="flex-1 flex flex-col items-center text-center relative">
                    {i > 0 && <div className={`absolute top-1.5 -left-1/2 w-full h-px ${stages[i - 1].status === 'done' ? 'bg-positive-200' : 'bg-ground-200'}`} />}
                    <span className={`w-3 h-3 rounded-full z-10 ${dot}`} />
                    <span className={`text-[11px] mt-1.5 ${withdrew ? 'text-critical-600 font-semibold' : 'text-ground-400'}`}>
                      {t(withdrew ? 'sponsorPortal.journey.withdrew' : `sponsorPortal.journey.${s.key}`)}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          <div className="mt-6 rounded-xl bg-ground-50 border p-4">
            <p className="text-[11px] uppercase tracking-wide text-ground-400 font-semibold">{t('sponsorPortal.myStudents.detail.commitment')}</p>
            <p className="text-2xl font-bold text-ground-900 mt-1">RM {rmWhole(detail.amount)}</p>
            {st.supported_semesters ? (
              <p className="text-xs text-ground-500">{t('sponsorPortal.myStudents.detail.overSems').replace('{n}', String(st.supported_semesters))}</p>
            ) : null}
          </div>

          {detail.anon_profile && (
            <div className="mt-6">
              <p className="text-[11px] uppercase tracking-wide text-ground-400 font-semibold mb-2">{t('sponsorPortal.myStudents.detail.profile')}</p>
              <div className="text-sm text-ground-700 leading-relaxed space-y-3 [&_h2]:font-semibold [&_h2]:text-ground-900 [&_h3]:font-semibold [&_ul]:list-disc [&_ul]:pl-5">
                <ReactMarkdown>{detail.anon_profile}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Reserved for the Vircle spending panel (a later sprint). */}
          <div className="mt-6 rounded-xl border border-dashed p-4 relative">
            <span className="absolute top-3 right-3 text-[10px] uppercase tracking-wide bg-ground-100 text-ground-400 rounded-full px-2 py-0.5 font-semibold">
              {t('sponsorPortal.myStudents.detail.soon')}
            </span>
            <p className="text-[11px] uppercase tracking-wide text-ground-400 font-semibold">{t('sponsorPortal.myStudents.detail.spending')}</p>
            <p className="text-xs text-ground-400 mt-2 max-w-md">{t('sponsorPortal.myStudents.detail.spendingSoon')}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
