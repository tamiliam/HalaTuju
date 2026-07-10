'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { fundStudent, getSponsorPoolDetail, getSponsorWallet, type SponsorPoolDetail } from '@/lib/api'

// Backend fund error code → localised message key.
const FUND_ERR_KEY: Record<string, string> = {
  insufficient_balance: 'sponsorPortal.students.errInsufficient',
  not_fundable: 'sponsorPortal.students.errNotFundable',
}

/**
 * One anonymised student. Renders inside the portal shell (the layout supplies the
 * top bar + nav). The "Support" panel funds the student IN FULL for their award
 * amount from the sponsor's BrightPath balance → an 'offered' award (status 'awarded').
 */
export default function StudentDetailPage() {
  const { t } = useT()
  const { token } = useSponsorAuth()
  const { refreshPool, refreshWallet } = useSponsorPortal()
  const params = useParams()
  const id = Number(params?.id)

  const [detail, setDetail] = useState<SponsorPoolDetail | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [balance, setBalance] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [funding, setFunding] = useState(false)
  const [funded, setFunded] = useState(false)
  const [errCode, setErrCode] = useState<string | null>(null)

  useEffect(() => {
    if (!token || !id) return
    let cancelled = false
    getSponsorPoolDetail(id, { token })
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => { if (!cancelled) setUnavailable(true) })
    getSponsorWallet({ token })
      .then((w) => { if (!cancelled) setBalance(w.balance) })
      .catch(() => { /* balance is a hint; the fund call is the real gate */ })
    return () => { cancelled = true }
  }, [token, id])

  const doFund = async () => {
    if (!token) return
    setFunding(true)
    setErrCode(null)
    try {
      await fundStudent(id, { token })
      setFunded(true)
      setConfirming(false)
      // Reflect the committed amount in the displayed balance.
      getSponsorWallet({ token })
        .then((w) => setBalance(w.balance))
        .catch(() => { /* non-critical */ })
      // Refresh the shared portal data so the funded student drops off the "available
      // students" list and shows under "My students" as awaiting-acceptance — without the
      // sponsor having to hard-refresh (the reported stale-list bug, 2026-07).
      refreshPool()
      refreshWallet()
    } catch (e) {
      setErrCode((e as Error & { code?: string }).code || 'generic')
    } finally {
      setFunding(false)
    }
  }

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
              {detail.enrolment_verified && (
                <div className="mt-5 flex items-start gap-2 bg-green-50 border border-green-100 rounded-xl p-3 text-xs text-green-800">
                  🛡️ <span><b>{t('sponsorPortal.trust.verifiedBadge')}.</b> {t('sponsorPortal.trust.verifiedDetail')}</span>
                </div>
              )}
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
          <div className="bg-white rounded-2xl border p-6 h-fit space-y-3">
            {detail.award_amount && (
              <div>
                <p className="text-xs text-gray-500">{t('sponsorPool.fundingLabel')}</p>
                <p className="text-3xl font-bold text-gray-900">RM {detail.award_amount}</p>
                {detail.programme_months != null && (
                  <p className="text-xs text-gray-400">{detail.programme_months} {t('sponsorPool.months')}</p>
                )}
              </div>
            )}
            {balance !== null && (
              <p className="text-xs text-gray-500">
                {t('sponsorPortal.students.balanceLabel')}:{' '}
                <span className="font-semibold text-gray-800">RM {balance}</span>
              </p>
            )}

            {funded ? (
              <div className="rounded-lg bg-green-50 border border-green-100 px-3 py-2.5 text-xs text-green-800">
                ✅ {t('sponsorPortal.students.funded', { amount: detail.award_amount ?? '' })}
              </div>
            ) : confirming ? (
              <div className="space-y-2">
                <p className="text-xs text-gray-700">
                  {t('sponsorPortal.students.confirmBody', { amount: detail.award_amount ?? '' })}
                </p>
                <div className="flex gap-2">
                  <button
                    disabled={funding}
                    onClick={doFund}
                    className="flex-1 rounded-xl bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
                  >
                    {funding ? t('common.loading') : t('sponsorPortal.students.confirmAward')}
                  </button>
                  <button
                    disabled={funding}
                    onClick={() => { setConfirming(false); setErrCode(null) }}
                    className="rounded-xl border px-3 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-60"
                  >
                    {t('common.cancel')}
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => { setConfirming(true); setErrCode(null) }}
                className="w-full rounded-xl bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
              >
                {t('sponsorPortal.students.support')}
              </button>
            )}

            {errCode && (
              <p className="rounded-lg bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-700">
                {t(FUND_ERR_KEY[errCode] || 'sponsorPortal.students.errGeneric')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
