'use client'

import '@/lib/messagesSponsor'   // TD-416: this page's sponsor* words (their own slice)
import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { fundStudent, getSponsorPoolDetail, getSponsorWallet, type SponsorPoolDetail } from '@/lib/api'
import { conceptFieldImageUrl } from '@/lib/fieldImage'
import { FundingBar } from '@/components/FundingBar'
import { rmWhole } from '@/lib/poolCard'
import { formatDate } from '@/lib/formatDate'
import Sheet from '@/components/Sheet'
import { useBottomBarInset } from '@/lib/bottomBarInset'
import { PHONE_BLEED, PHONE_SECTION_NO_GAP } from '@/lib/phoneSection'

// The sponsorship pays a flat RM200/month, so the funded duration = amount ÷ 200
// (RM1,000→5, RM2,000→10, RM3,000→15 months).
const PAY_RATE = 200
const payMonthsOf = (amount: string | null | undefined) => {
  const n = Number(amount)
  return Number.isFinite(n) && n > 0 ? Math.round(n / PAY_RATE) : 0
}

/** The route segment decoded, or '' when it is not valid percent-encoding (A4.6 review). */
function decodeSegment(segment: string): string {
  try { return decodeURIComponent(segment) } catch { return '' }
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
  const router = useRouter()
  // TD-074: the segment is the student's opaque ref (S-XXXXXX), never a raw id. A malformed escape
  // ('%E0') decodes to '' (the "not available" state), never a thrown render.
  const id = typeof params?.id === 'string' ? decodeSegment(params.id) : ''
  // An all-digit segment is a pre-TD-074 raw-id link (an email already sent): the student list, not
  // "not available". Nothing maps the id to a student; no detail is asked for.
  const legacyRawId = /^\d+$/.test(id)
  useEffect(() => {
    if (legacyRawId) router.replace('/sponsor/students')
  }, [legacyRawId, router])

  const [detail, setDetail] = useState<SponsorPoolDetail | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [balance, setBalance] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [funding, setFunding] = useState(false)
  const [funded, setFunded] = useState(false)
  const [errCode, setErrCode] = useState<string | null>(null)
  // ONE award request per tap burst (Mobile M5, owner): a second tap before React has re-rendered the
  // disabled button must not send a second request. State is too late for that; a ref is not.
  const inFlight = useRef(false)

  useEffect(() => {
    // A different student (the address changed in place): forget the last one FIRST, so nothing — above
    // all the confirm's amount — can show the previous student's figures while this one loads (M5 review).
    setDetail(null); setUnavailable(false); setFunded(false); setConfirming(false); setErrCode(null)
    if (!id) { setUnavailable(true); return }
    if (!token || legacyRawId) return
    let cancelled = false
    getSponsorPoolDetail(id, { token })
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => { if (!cancelled) setUnavailable(true) })
    getSponsorWallet({ token })
      .then((w) => { if (!cancelled) setBalance(w.balance) })
      .catch(() => { /* balance is a hint; the fund call is the real gate */ })
    return () => { cancelled = true }
  }, [token, id, legacyRawId])

  const doFund = async () => {
    if (!token || inFlight.current) return
    inFlight.current = true
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
      inFlight.current = false
      setFunding(false)
    }
  }

  const payMonths = payMonthsOf(detail?.award_amount)

  // The trust strip's core ticks — every pooled student has passed QC by construction.
  const CHECKS = ['checkIdentity', 'checkAcademic', 'checkPathway', 'checkFinancial'] as const

  // The fund action is offered while the student is still fundable and this tab has not funded them.
  const canFund = !!detail && !funded && !detail.funded
  const openConfirm = () => { setConfirming(true); setErrCode(null) }

  return (
    <div className="max-w-4xl">
      <Link href="/sponsor/students" className="inline-flex min-h-11 items-center text-sm text-primary-600 hover:underline">← {t('sponsorPool.back')}</Link>

      {unavailable ? (
        <p className="text-center text-ground-500 mt-12">{t('sponsorPool.notAvailable')}</p>
      ) : detail === null ? (
        <p className="text-center text-ground-500 mt-12">{t('common.loading')}</p>
      ) : (
        // Rule 15 (Mobile M5): full-width sections on a phone, the cards they were from md.
        <div className="md:mt-4 grid lg:grid-cols-3 md:gap-5">
          <div className="lg:col-span-2 md:space-y-4">
            {/* Header card: slim banner strip + title + chips. On a phone the banner runs edge to edge. */}
            <div className="border-b border-ground-100 md:overflow-hidden md:rounded-2xl md:border md:bg-ground-0">
              <div className="relative h-24 -mx-4 md:mx-0">
                {/* eslint-disable-next-line @next/next/no-img-element -- a small concept picture; a plain img keeps the card's fixed layout and adds no bundle weight */}
                <img src={conceptFieldImageUrl(detail.field_image_slug)} alt="" className="absolute inset-0 h-full w-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
                <span className="absolute bottom-2 left-4 rounded-md bg-ground-0/90 px-2.5 py-0.5 text-xs font-bold text-ground-900 shadow-sm">{detail.ref}</span>
              </div>
              <div className="py-4 md:p-6">
                {detail.academic && (
                  <span className="rounded-md bg-ground-100 px-2 py-0.5 text-xs font-medium text-ground-700">{detail.academic}</span>
                )}
                {/* The programme links to its public HalaTuju course page when it has one
                    (`course_href`, server-computed) — a new tab, so the sponsor doesn't lose the
                    student. Deliberately NOT on the browse card: that whole card is already a
                    <Link> to this page, and a nested anchor would be invalid HTML and would steal
                    the card's click. Falls back to plain text when there is no page. */}
                <h1 className="mt-2 text-xl font-bold text-ground-900 leading-snug">
                  {detail.course && detail.course_href ? (
                    <a href={detail.course_href} target="_blank" rel="noreferrer"
                       className="inline-block -my-2.5 py-2.5 hover:text-primary-600 hover:underline">{detail.course}</a>
                  ) : (detail.course || detail.field || detail.ref)}
                </h1>
                {detail.institution && <p className="text-sm text-ground-500 mt-0.5">{detail.institution}</p>}
              </div>
            </div>

            {/* Verification strip — our differentiator (a coloured callout at every width) */}
            <div className="border-b border-ground-100 py-4 md:border-0 md:py-0">
              <div className="rounded-2xl border border-positive-100 bg-positive-50/60 p-4 md:p-5">
                <p className="flex items-center gap-2 text-sm font-semibold text-positive-800">
                  🛡️ {t('sponsorPool.verifiedByBrightPath')}
                </p>
                <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
                  {CHECKS.map((c) => (
                    <li key={c} className="flex items-center gap-2 text-sm text-ground-700">
                      <span className="text-positive-700">✓</span> {t(`sponsorPool.${c}`)}
                    </li>
                  ))}
                  {detail.enrolment_verified && (
                    <li className="flex items-center gap-2 text-sm text-ground-700">
                      <span className="text-positive-700">✓</span> {t('sponsorPool.checkEnrolment')}
                    </li>
                  )}
                </ul>
                <p className="mt-3 text-xs text-positive-700/80">{t('sponsorPool.verifyCaption')}</p>
              </div>
            </div>

            {/* Narrative */}
            {detail.anon_profile && (
              <div className={PHONE_SECTION_NO_GAP}>
                <div className="text-sm text-ground-800 leading-relaxed [&_p]:mt-2 [&_p:first-child]:mt-0 md:p-1">
                  <ReactMarkdown>{detail.anon_profile}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar action card — a plain section on a phone, whose fund button is the sticky bar below */}
          <div className="py-4 h-fit space-y-5 md:rounded-2xl md:border md:bg-ground-0 md:p-6">
            {/* Support block */}
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ground-400">{t('sponsorPool.supportNeeded')}</p>
              {detail.award_amount && (
                <div>
                  <p className="text-3xl font-bold text-ground-900">RM{rmWhole(detail.award_amount)}</p>
                  {payMonths > 0 && (
                    <p className="text-xs text-ground-500">{t('sponsorPool.overMonths').replace('{months}', String(payMonths))}</p>
                  )}
                  <FundingBar funded={detail.funded_amount} award={detail.award_amount} className="mt-3" />
                </div>
              )}

              <div className="mt-5">
                {funded ? (
                  <div className="rounded-md bg-positive-50 border border-positive-100 px-3 py-2.5 text-xs text-positive-800">
                    ✅ {t('sponsorPortal.students.funded', { amount: rmWhole(detail.award_amount) })}
                  </div>
                ) : detail.funded ? (
                  // Funded by a sponsor within the grace window — read-only, no fund button (the
                  // fund action is gated server-side too; this just reflects it).
                  <div className="rounded-md bg-ground-50 border border-ground-200 px-3 py-2.5 text-xs font-medium text-ground-600">
                    ✓ {t('sponsorPool.fundedBody')}
                  </div>
                ) : (
                  // From md the button lives here; on a phone it is the sticky bar. Both open ONE confirm.
                  <button type="button" onClick={openConfirm}
                    className="hidden md:block w-full min-h-11 rounded-md bg-brand-fill px-3 py-2.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
                    {t('sponsorPool.fullyFund')}
                  </button>
                )}
              </div>

              {errCode && !confirming && (
                <p className="mt-2 rounded-md bg-critical-50 border border-critical-100 px-3 py-2 text-xs text-critical-700">
                  {t(FUND_ERR_KEY[errCode] || 'sponsorPortal.students.errGeneric')}
                </p>
              )}

              {/* On a phone the fund bar shows the balance (while the student is fundable). */}
              {balance !== null && (
                <p className={`mt-3 text-center text-xs text-ground-500 ${canFund ? 'hidden md:block' : ''}`}>
                  {t('sponsorPortal.students.balanceLabel')}: RM{rmWhole(balance)}
                </p>
              )}
            </div>

            {/* Facts — compact (smaller than the support block) */}
            <dl className="border-t pt-4 space-y-2 text-xs">
              {detail.school && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ground-500 shrink-0">{t('sponsorPool.secondarySchool')}</dt>
                  <dd className="text-right font-medium text-ground-900">{detail.school}</dd>
                </div>
              )}
              {detail.state && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ground-500">{t('sponsorPool.homeState')}</dt>
                  <dd className="text-right font-medium text-ground-900">{detail.state}</dd>
                </div>
              )}
              {detail.reporting_date && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ground-500">{t('sponsorPool.reportingDate')}</dt>
                  <dd className="text-right font-medium text-ground-900">{formatDate(detail.reporting_date)}</dd>
                </div>
              )}
              {detail.funding_categories.length > 0 && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-ground-500">{t('sponsorPool.coversLabel')}</dt>
                  <dd className="text-right font-medium text-ground-900">{detail.funding_categories.join(', ')}</dd>
                </div>
              )}
            </dl>

            {/* Privacy note — blue info box with an ⓘ icon (matches the design) */}
            <div className="flex items-start gap-2 rounded-lg bg-info-50 px-3 py-2.5 text-xs leading-relaxed text-info-800/80">
              <svg viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 h-4 w-4 shrink-0 text-info-600" aria-hidden>
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9 9a1 1 0 012 0v4a1 1 0 11-2 0V9zm1-4a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" />
              </svg>
              <span>{t('sponsorPool.privacyNote')}</span>
            </div>
          </div>
        </div>
      )}

      {/* Phones: the fund action as the page's own sticky bar — it replaces the tab bar (one bottom
          bar at a time, `data-page-bar`). Balance on the left, the action on the right. */}
      {canFund && <FundBar balance={balance} onFund={openConfirm} t={t} />}

      {/* ONE confirm for both widths (Mobile M5, owner): a Sheet that cannot be swiped or Escaped away
          (`dismissible={false}`) and cannot close while the award is being sent (`busy`). The amount it
          names is the server's `award_amount`, as before; nothing is computed here. */}
      {detail && (
        <Sheet open={confirming} onClose={() => { if (!funding) { setConfirming(false); setErrCode(null) } }}
          title={t('sponsorPool.fullyFund')} dismissible={false} busy={funding} role="alertdialog"
          testId="fund-confirm" className="font-sponsor"
          footer={(
            <>
              <button type="button" disabled={funding} onClick={() => { setConfirming(false); setErrCode(null) }}
                className="min-h-12 flex-1 rounded-lg border border-ground-300 px-4 py-2 text-sm font-semibold text-ground-700 hover:bg-ground-50 disabled:opacity-60">
                {t('common.cancel')}
              </button>
              <button type="button" disabled={funding} onClick={doFund} data-testid="fund-confirm-award"
                className="min-h-12 flex-[1.4] rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-60">
                {funding ? t('common.loading') : t('sponsorPortal.students.confirmAward')}
              </button>
            </>
          )}>
          <p className="text-sm text-ground-700">{t('sponsorPortal.students.confirmBody', { amount: rmWhole(detail.award_amount) })}</p>
          {balance !== null && (
            <p className="mt-3 text-sm text-ground-500">{t('sponsorPortal.students.balanceLabel')}: <b className="text-ground-900">RM{rmWhole(balance)}</b></p>
          )}
          {errCode && (
            <p className="mt-3 rounded-md bg-critical-50 border border-critical-100 px-3 py-2 text-sm text-critical-700" role="alert">
              {t(FUND_ERR_KEY[errCode] || 'sponsorPortal.students.errGeneric')}
            </p>
          )}
        </Sheet>
      )}
    </div>
  )
}

/** The phone's sticky fund bar (rule 6's sticky page bar; `data-page-bar` swaps the tabs out). */
function FundBar({ balance, onFund, t }: { balance: string | null; onFund: () => void; t: (k: string) => string }) {
  const bar = useRef<HTMLDivElement>(null)
  useBottomBarInset(bar)
  return (
    <div ref={bar} data-page-bar data-testid="fund-bar"
      className={`sticky bottom-0 z-10 mt-4 flex items-center gap-3 border-t border-ground-200 bg-ground-0 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.06)] md:hidden ${PHONE_BLEED}`}>
      <div className="min-w-0 flex-1">
        {balance !== null && (
          <p className="text-xs text-ground-500">{t('sponsorPortal.students.balanceLabel')}<b className="block text-sm text-ground-900">RM{rmWhole(balance)}</b></p>
        )}
      </div>
      <button type="button" onClick={onFund}
        className="min-h-12 flex-[1.6] rounded-lg bg-brand-fill px-4 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
        {t('sponsorPool.fullyFund')}
      </button>
    </div>
  )
}
