'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { fundStudent, getSponsorPoolDetail, getSponsorWallet, type SponsorPoolDetail } from '@/lib/api'
import { fieldImageUrl } from '@/lib/fieldImage'
import { rmWhole } from '@/lib/poolCard'
import { formatDate } from '@/lib/formatDate'

// The sponsorship pays a flat RM200/month, so the funded duration = amount ÷ 200
// (RM1,000→5, RM2,000→10, RM3,000→15 months).
const PAY_RATE = 200
const payMonthsOf = (amount: string | null | undefined) => {
  const n = Number(amount)
  return Number.isFinite(n) && n > 0 ? Math.round(n / PAY_RATE) : 0
}

// Backend fund error code → localised message key.
const FUND_ERR_KEY: Record<string, string> = {
  insufficient_balance: 'sponsorPortal.students.errInsufficient',
  not_fundable: 'sponsorPortal.students.errNotFundable',
}

/**
 * One anonymised student (image-led, IA: one home per fact). Header (artwork + title +
 * chips) → verification strip (our differentiator) → narrative → sidebar action card.
 * No fact renders twice; there is no facts table. Funding commits the award IN FULL from
 * the sponsor's BrightPath balance.
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
      getSponsorWallet({ token }).then((w) => setBalance(w.balance)).catch(() => {})
      // Refresh shared portal data so the funded student drops off the available list.
      refreshPool()
      refreshWallet()
    } catch (e) {
      setErrCode((e as Error & { code?: string }).code || 'generic')
    } finally {
      setFunding(false)
    }
  }

  const payMonths = payMonthsOf(detail?.award_amount)

  // The trust strip's core ticks — every pooled student has passed QC by construction.
  const CHECKS = ['checkIdentity', 'checkAcademic', 'checkPathway', 'checkFinancial'] as const

  return (
    <div className="max-w-4xl">
      <Link href="/sponsor/students" className="text-sm text-blue-600 hover:underline">← {t('sponsorPool.back')}</Link>

      {unavailable ? (
        <p className="text-center text-gray-500 mt-12">{t('sponsorPool.notAvailable')}</p>
      ) : detail === null ? (
        <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
      ) : (
        <div className="mt-4 grid lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-4">
            {/* Header card: slim banner strip + title + chips */}
            <div className="overflow-hidden rounded-2xl border bg-white">
              <div className="relative h-24">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={fieldImageUrl(detail.field_image_slug)} alt="" className="absolute inset-0 h-full w-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
                <span className="absolute bottom-2 left-4 rounded-md bg-white/90 px-2.5 py-0.5 text-xs font-bold text-gray-900 shadow-sm">{detail.ref}</span>
              </div>
              <div className="p-6">
                {detail.academic && (
                  <span className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-700">{detail.academic}</span>
                )}
                <h1 className="mt-2 text-xl font-bold text-gray-900 leading-snug">{detail.course || detail.field || detail.ref}</h1>
                {detail.institution && <p className="text-sm text-gray-500 mt-0.5">{detail.institution}</p>}
              </div>
            </div>

            {/* Verification strip — our differentiator */}
            <div className="rounded-2xl border border-green-100 bg-green-50/60 p-5">
              <p className="flex items-center gap-2 text-sm font-semibold text-green-800">
                🛡️ {t('sponsorPool.verifiedByBrightPath')}
              </p>
              <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
                {CHECKS.map((c) => (
                  <li key={c} className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="text-green-600">✓</span> {t(`sponsorPool.${c}`)}
                  </li>
                ))}
                {detail.enrolment_verified && (
                  <li className="flex items-center gap-2 text-sm text-gray-700">
                    <span className="text-green-600">✓</span> {t('sponsorPool.checkEnrolment')}
                  </li>
                )}
              </ul>
              <p className="mt-3 text-xs text-green-700/80">{t('sponsorPool.verifyCaption')}</p>
            </div>

            {/* Narrative */}
            {detail.anon_profile && (
              <div className="bg-white rounded-2xl border p-6">
                <div className="text-sm text-gray-800 leading-relaxed [&_p]:mt-2 [&_p:first-child]:mt-0">
                  <ReactMarkdown>{detail.anon_profile}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar action card */}
          <div className="bg-white rounded-2xl border p-6 h-fit space-y-5">
            {/* Support block */}
            <div>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{t('sponsorPool.supportNeeded')}</p>
              {detail.award_amount && (
                <div>
                  <p className="text-3xl font-bold text-gray-900">RM{rmWhole(detail.award_amount)}</p>
                  {payMonths > 0 && (
                    <p className="text-xs text-gray-500">{t('sponsorPool.overMonths').replace('{months}', String(payMonths))}</p>
                  )}
                </div>
              )}

              <div className="mt-5">
                {funded ? (
                  <div className="rounded-md bg-green-50 border border-green-100 px-3 py-2.5 text-xs text-green-800">
                    ✅ {t('sponsorPortal.students.funded', { amount: rmWhole(detail.award_amount) })}
                  </div>
                ) : confirming ? (
                  <div className="space-y-2">
                    <p className="text-xs text-gray-700">{t('sponsorPortal.students.confirmBody', { amount: rmWhole(detail.award_amount) })}</p>
                    <div className="flex gap-2">
                      <button disabled={funding} onClick={doFund}
                        className="flex-1 rounded-md bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60">
                        {funding ? t('common.loading') : t('sponsorPortal.students.confirmAward')}
                      </button>
                      <button disabled={funding} onClick={() => { setConfirming(false); setErrCode(null) }}
                        className="rounded-md border px-3 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-60">
                        {t('common.cancel')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => { setConfirming(true); setErrCode(null) }}
                    className="w-full rounded-md bg-blue-600 px-3 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">
                    {t('sponsorPool.fullyFund')}
                  </button>
                )}
              </div>

              {errCode && (
                <p className="mt-2 rounded-md bg-red-50 border border-red-100 px-3 py-2 text-xs text-red-700">
                  {t(FUND_ERR_KEY[errCode] || 'sponsorPortal.students.errGeneric')}
                </p>
              )}

              {balance !== null && (
                <p className="mt-3 text-center text-xs text-gray-500">
                  {t('sponsorPortal.students.balanceLabel')}: RM{rmWhole(balance)}
                </p>
              )}
            </div>

            {/* Facts — compact (smaller than the support block) */}
            <dl className="border-t pt-4 space-y-2 text-xs">
              {detail.school && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500 shrink-0">{t('sponsorPool.secondarySchool')}</dt>
                  <dd className="text-right font-medium text-gray-900">{detail.school}</dd>
                </div>
              )}
              {detail.state && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">{t('sponsorPool.homeState')}</dt>
                  <dd className="text-right font-medium text-gray-900">{detail.state}</dd>
                </div>
              )}
              {detail.reporting_date && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">{t('sponsorPool.reportingDate')}</dt>
                  <dd className="text-right font-medium text-gray-900">{formatDate(detail.reporting_date)}</dd>
                </div>
              )}
              {detail.funding_categories.length > 0 && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">{t('sponsorPool.coversLabel')}</dt>
                  <dd className="text-right font-medium text-gray-900">{detail.funding_categories.join(', ')}</dd>
                </div>
              )}
            </dl>

            {/* Privacy note — blue info box with an ⓘ icon (matches the design) */}
            <div className="flex items-start gap-2 rounded-lg bg-blue-50 px-3 py-2.5 text-xs leading-relaxed text-blue-800/80">
              <svg viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" aria-hidden>
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9 9a1 1 0 012 0v4a1 1 0 11-2 0V9zm1-4a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" />
              </svg>
              <span>{t('sponsorPool.privacyNote')}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
