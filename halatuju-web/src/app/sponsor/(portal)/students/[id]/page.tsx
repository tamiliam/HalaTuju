'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { getSponsorPoolDetail, type SponsorPoolDetail } from '@/lib/api'

/**
 * One anonymised student. Renders inside the portal shell (the layout supplies the
 * top bar + nav). The "Support this student" affordance is present; the actual fund
 * flow is confirmed with the owner as a fast follow (TD-101 — fund not yet wired).
 */
export default function StudentDetailPage() {
  const { t } = useT()
  const { token } = useSponsorAuth()
  const params = useParams()
  const id = Number(params?.id)

  const [detail, setDetail] = useState<SponsorPoolDetail | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [showFundNote, setShowFundNote] = useState(false)

  useEffect(() => {
    if (!token || !id) return
    let cancelled = false
    getSponsorPoolDetail(id, { token })
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => { if (!cancelled) setUnavailable(true) })
    return () => { cancelled = true }
  }, [token, id])

  return (
    <div className="max-w-3xl">
      <Link href="/sponsor/students" className="text-sm text-blue-600 hover:underline">← {t('sponsorPool.back')}</Link>

      {unavailable ? (
        <p className="text-center text-gray-500 mt-12">{t('sponsorPool.notAvailable')}</p>
      ) : detail === null ? (
        <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
      ) : (
        <div className="mt-4 grid lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white rounded-2xl border p-6">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-gray-900">{detail.ref}</h1>
                {detail.state && <span className="text-sm text-gray-500">{detail.state}</span>}
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                {detail.field && (
                  <div><dt className="text-gray-500">{t('sponsorPool.fieldLabel')}</dt><dd className="text-gray-900">{detail.field}</dd></div>
                )}
                {detail.academic && (
                  <div><dt className="text-gray-500">{t('sponsorPool.academicLabel')}</dt><dd className="text-gray-900">{detail.academic}</dd></div>
                )}
                {detail.funding_categories.length > 0 && (
                  <div><dt className="text-gray-500">{t('sponsorPool.fundingLabel')}</dt><dd className="text-gray-900">{detail.funding_categories.join(' · ')}</dd></div>
                )}
                {detail.programme_months != null && (
                  <div><dt className="text-gray-500">{t('sponsorPool.durationLabel')}</dt><dd className="text-gray-900">{detail.programme_months} {t('sponsorPool.months')}</dd></div>
                )}
              </dl>
            </div>

            {detail.anon_profile && (
              <div className="bg-white rounded-2xl border p-6">
                <div className="text-sm text-gray-800 leading-relaxed [&_h1]:text-base [&_h1]:font-bold [&_h2]:font-semibold [&_h2]:mt-3 [&_p]:mt-2 [&_ul]:list-disc [&_ul]:pl-5">
                  <ReactMarkdown>{detail.anon_profile}</ReactMarkdown>
                </div>
              </div>
            )}

            <div className="rounded-lg bg-blue-50 border border-blue-100 px-4 py-2.5 text-xs text-blue-800">
              {t('sponsorPool.anonymityNote')}
            </div>
          </div>

          {/* Support panel */}
          <div className="bg-white rounded-2xl border p-6 h-fit">
            {detail.award_amount && (
              <>
                <p className="text-xs text-gray-500">{t('sponsorPool.fundingLabel')}</p>
                <p className="text-3xl font-bold text-gray-900">RM {detail.award_amount}</p>
                {detail.programme_months != null && (
                  <p className="text-xs text-gray-400 mb-4">{detail.programme_months} {t('sponsorPool.months')}</p>
                )}
              </>
            )}
            <button
              onClick={() => setShowFundNote(true)}
              className="w-full rounded-xl bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
            >
              {t('sponsorPortal.students.support')}
            </button>
            {showFundNote && (
              <p className="mt-3 rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-800">
                {t('sponsorPortal.students.fundingSoon')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
