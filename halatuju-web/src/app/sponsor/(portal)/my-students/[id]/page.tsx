'use client'

import '@/lib/messagesSponsor'   // TD-416: this page's sponsor* words (their own slice)
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { getMyStudentDetail, type SponsorMyStudentDetail } from '@/lib/api'
import { conceptFieldImageUrl } from '@/lib/fieldImage'
import { portfolioBadgeTone, rmWhole } from '@/lib/poolCard'
import { PHONE_PILL } from '@/lib/phonePill'
import SpendingCard from '@/components/sponsor/SpendingCard'
import JourneyLine from '@/components/sponsor/JourneyLine'

/** Rule 15 (Mobile M5): a part of this page is a plain block under a hairline on a phone, and the box
 *  it always was inside the page's card from md. */
const PART = 'mt-5 border-t border-ground-100 pt-4 md:mt-6 md:border-t-0 md:pt-0'

/** The route segment decoded, or '' when it is not valid percent-encoding (A4.6 review). */
function decodeSegment(segment: string): string {
  try { return decodeURIComponent(segment) } catch { return '' }
}


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
  // TD-074: the segment is the student's opaque ref (S-XXXXXX), never a raw id. A malformed escape
  // ('%E0') decodes to '' (the "unavailable" state), never a thrown render.
  const id = typeof params?.id === 'string' ? decodeSegment(params.id) : ''

  const [detail, setDetail] = useState<SponsorMyStudentDetail | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    if (!id) { setUnavailable(true); return }
    if (!token) return
    let cancelled = false
    getMyStudentDetail(id, { token })
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => { if (!cancelled) setUnavailable(true) })
    return () => { cancelled = true }
  }, [token, id])

  const back = (
    <Link href="/sponsor" className="inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:underline">
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

  return (
    <div className="max-w-3xl mx-auto">
      {back}
      {/* One card from md; on a phone the page itself, the banner running edge to edge. */}
      <div className="md:mt-3 md:overflow-hidden md:rounded-2xl md:border md:bg-ground-0 md:shadow-sm">
        <div className="relative h-32 -mx-4 bg-gradient-to-br from-info-50 to-positive-50 md:mx-0">
          {st.field_image_slug && (
            // eslint-disable-next-line @next/next/no-img-element -- a small concept picture; a plain img keeps the card's fixed layout and adds no bundle weight
            <img src={conceptFieldImageUrl(st.field_image_slug)} alt="" className="w-full h-full object-cover" />
          )}
          <span className="absolute bottom-3 left-3 font-mono text-sm font-semibold bg-ground-0 border rounded-lg px-2.5 py-1">{st.ref}</span>
        </div>

        <div className="py-4 md:p-6">
          <h1 className="text-2xl font-bold text-ground-900 tracking-tight leading-snug">{st.course || st.field || '—'}</h1>
          {st.institution && (
            <p className="text-ground-500 mt-0.5">{st.institution}{st.state ? ` · ${st.state}` : ''}</p>
          )}

          <div className="mt-3 flex flex-wrap gap-2 items-center">
            {offered
              ? <span className={`rounded-full bg-ground-200 text-ground-600 px-3 py-1 text-xs font-semibold whitespace-nowrap ${PHONE_PILL}`}>⏳ {t('sponsorPortal.myStudents.awaiting')}</span>
              : status && (
                <span className={`rounded-full px-3 py-1 text-xs font-semibold whitespace-nowrap ${portfolioBadgeTone(status)} ${PHONE_PILL}`}>
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
            <JourneyLine onboarded={detail.onboarded} state={st.progress_state} semesters={detail.semesters}
              discontinued={discontinued} t={t} className="mt-5" />
          )}

          <div className={`${PART} md:rounded-xl md:bg-ground-50 md:border md:p-4`}>
            <p className="text-xs uppercase tracking-wide text-ground-400 font-semibold">{t('sponsorPortal.myStudents.detail.commitment')}</p>
            <p className="text-2xl font-bold text-ground-900 mt-1">RM {rmWhole(detail.amount)}</p>
            {st.supported_semesters ? (
              <p className="text-xs text-ground-500">{t('sponsorPortal.myStudents.detail.overSems').replace('{n}', String(st.supported_semesters))}</p>
            ) : null}
          </div>

          {detail.anon_profile && (
            <div className={PART}>
              <p className="text-xs uppercase tracking-wide text-ground-400 font-semibold mb-2">{t('sponsorPortal.myStudents.detail.profile')}</p>
              <div className="text-sm text-ground-700 leading-relaxed space-y-3 [&_h2]:font-semibold [&_h2]:text-ground-900 [&_h3]:font-semibold [&_ul]:list-disc [&_ul]:pl-5">
                <ReactMarkdown>{detail.anon_profile}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* The Vircle spending panel (S5) — this box was reserved for it since the page
              was built. ⚠ CATEGORIES AND TOTALS ONLY; never a shop, a date or a time.
              ⚠ `spending` is null when nothing has been imported yet, and then the panel is
              ABSENT rather than showing four zeroes — zeroes would claim the student has
              spent nothing, and the likelier truth is that no report has reached us. The
              placeholder that stood here said "coming soon", which stops being true the day
              this ships; it now says what is actually the case. */}
          {detail.spending ? (
            <SpendingCard spending={detail.spending} copy="sponsorPortal.myStudents.detail.spend"
              className={`${PART} md:rounded-xl md:border md:border-ground-200 md:bg-ground-0 md:p-5`} />
          ) : (
            <div className={`${PART} md:rounded-xl md:border md:border-dashed md:p-4`}>
              <p className="text-xs uppercase tracking-wide text-ground-400 font-semibold">
                {t('sponsorPortal.myStudents.detail.spending')}
              </p>
              <p className="text-xs text-ground-400 mt-2 max-w-md">
                {t('sponsorPortal.myStudents.detail.spend.none')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
