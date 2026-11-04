'use client'

import '@/lib/messagesSponsor'   // TD-416: this page's sponsor* words (their own slice)
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import JourneyLine from '@/components/sponsor/JourneyLine'
import { PHONE_SECTION_NO_GAP } from '@/lib/phoneSection'
import { PHONE_PILL_SM } from '@/lib/phonePill'
import { formatRM } from '@/lib/sponsorTrust'
import { portfolioBadgeTone } from '@/lib/poolCard'
import type { SponsorPoolCard } from '@/lib/api'

/**
 * My Giving — the sponsor's home, led by impact (R2): an impact-number strip, the
 * giving donut, the students you support with a journey tracker, and thank-you
 * messages. All figures come from the shared portal context (one fetch).
 */
export default function MyGivingPage() {
  const { t } = useT()
  const { account } = useSponsorAuth()
  const { wallet, impact, activity, community, trust } = useSponsorPortal()

  const b = impact?.balance
  const committed = b ? parseFloat(b.committed) || 0 : 0
  const completed = b ? parseFloat(b.completed) || 0 : 0
  const available = b ? parseFloat(b.available) || 0 : 0
  const total = committed + completed + available
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0)
  const c1 = pct(committed)
  const c2 = c1 + pct(completed)
  // ⚠ COLOUR IN AN INLINE STYLE, WHICH NO TAILWIND CLASS SCAN CAN SEE. A conic-gradient cannot be
  // expressed as utilities, so these read the theme variables directly — the same values the
  // classes resolve to, so the donut inverts with everything else instead of staying a light-mode
  // island. Found in the Layer 1 F1 browser pass; the palette guard now scans for bare hex too.
  const tone = (name: string) => `rgb(var(--${name}))`
  const donut = total > 0
    ? `conic-gradient(${tone('info-600')} 0 ${c1}%, ${tone('positive-500')} ${c1}% ${c2}%, `
      + `${tone('ground-200')} ${c2}% 100%)`
    : tone('ground-200')

  return (
    // Rule 15 (Mobile M5): on a phone each block is a full-width SECTION on the 16 px gutter, divided by
    // a hairline; from md they are the cards they always were.
    <div className="md:space-y-8">
      {/* Welcome + browse CTA */}
      <section className="flex flex-wrap items-end justify-between gap-3 border-b border-ground-100 py-4 md:border-0 md:py-0">
        <div>
          <p className="text-xs uppercase tracking-wide text-ground-400">{t('sponsorPortal.myStudents.welcome')}</p>
          <div className="flex flex-wrap items-center gap-2 mt-0.5">
            <span className="text-2xl font-bold text-ground-900">{account?.name || ''}</span>
            <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-positive-100 text-positive-700">
              {t('sponsorPortal.myStudents.approvedPill')}
            </span>
          </div>
        </div>
        <Link href="/sponsor/students" className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover whitespace-nowrap md:w-auto">
          {t('sponsorPortal.nav.support')} →
        </Link>
      </section>

      {/* Assurance strip → Trust hub (R5). A coloured callout on a phone (rule 15's exception). */}
      {trust && (
        <section className="border-b border-ground-100 py-4 md:border-0 md:py-0">
          <Link href="/sponsor/trust" className="block rounded-xl bg-positive-50 p-4 transition-colors md:rounded-2xl md:border md:border-positive-100 md:bg-ground-0 md:p-5 md:hover:border-positive-200">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">🛡️</span>
                <div>
                  <p className="font-semibold text-ground-900">{t('sponsorPortal.trust.assured.title')}</p>
                  <p className="text-sm text-ground-500 max-w-2xl">{t('sponsorPortal.trust.assured.desc')}</p>
                  <p className="text-xs text-ground-400 mt-2">
                    {t('sponsorPortal.trust.assured.latest')
                      .replace('{fy}', trust.assurance.fy || '—')
                      .replace('{verified}', String(trust.assurance.students_verified ?? 0))
                      .replace('{disbursed}', formatRM(trust.assurance.disbursed || '0'))
                      .replace('{auditor}', trust.assurance.auditor || t('sponsorPortal.trust.auditorTbd'))}
                  </p>
                </div>
              </div>
              <span className="inline-flex min-h-11 items-center text-sm font-semibold text-positive-700 bg-positive-50 px-3 py-2 rounded-xl whitespace-nowrap shrink-0 max-md:whitespace-normal max-md:shrink">
                {t('sponsorPortal.trust.assured.cta')} →
              </span>
            </div>
          </Link>
        </section>
      )}

      {/* Impact numbers — four figures in a plain grid on a phone, four cards from md */}
      {impact && (
        <section className="grid grid-cols-2 gap-4 border-b border-ground-100 py-4 md:gap-3 md:border-0 md:py-0 lg:grid-cols-4">
          <Stat label={t('sponsorPortal.impact.totalGiven')} value={`RM ${impact.total_given}`}
            sub={t('sponsorPortal.impact.acrossStudents').replace('{n}', String(impact.students_supported))} />
          <Stat label={t('sponsorPortal.impact.supported')} value={String(impact.students_supported)}
            sub={`${impact.students_active} ${t('sponsorPortal.journey.studying').toLowerCase()} · ${impact.students_graduated} ${t('sponsorPortal.journey.graduated').toLowerCase()}`} />
          <Stat label={t('sponsorPortal.impact.semesters')} value={String(impact.semesters_completed)}
            sub={t('sponsorPortal.impact.semestersBy')} />
          <Stat label={t('sponsorPortal.impact.graduated')} value={impact.students_graduated > 0 ? `${impact.students_graduated} 🎉` : '0'}
            sub={t('sponsorPortal.impact.graduatedSub')} valueClass={impact.students_graduated > 0 ? 'text-positive-700' : 'text-ground-900'} />
        </section>
      )}

      {/* Giving donut */}
      {impact && (
        <section className={`${PHONE_SECTION_NO_GAP} md:max-w-md`}>
          <h2 className="font-semibold text-ground-900">{t('sponsorPortal.impact.givingTitle')}</h2>
          <div className="flex items-center gap-5 mt-4 max-md:gap-4">
            {/* Mobile M8: below md the ring is 128 px and its hole 88 px — the 64 px hole could not hold the Tamil
                "கிடைக்கிறது" or a four-figure sum (they spilled out of the circle). */}
            <div aria-hidden="true" className="w-28 h-28 shrink-0 rounded-full grid place-items-center max-md:w-32 max-md:h-32" style={{ background: donut }}>
              <div className="bg-ground-0 w-16 h-16 rounded-full grid place-items-center text-center max-md:w-[5.5rem] max-md:h-[5.5rem]">
                <span className="text-xs leading-tight text-ground-500">
                  {t('sponsorPortal.impact.available')}<br /><b className="text-ground-900 text-sm">RM {available.toLocaleString()}</b>
                </span>
              </div>
            </div>
            <ul className="text-sm space-y-2 flex-1">
              <LegendRow color={tone('info-600')} label={t('sponsorPortal.impact.committed')} amount={committed} />
              <LegendRow color={tone('positive-500')} label={t('sponsorPortal.impact.completed')} amount={completed} />
              <LegendRow color={tone('ground-200')} label={t('sponsorPortal.impact.available')} amount={available} />
            </ul>
          </div>
          <p className="text-xs text-ground-400 mt-3 leading-relaxed">{t('sponsorPortal.impact.balanceNote')}</p>
        </section>
      )}

      {/* Recent activity */}
      {activity.length > 0 && (
        <section className={PHONE_SECTION_NO_GAP}>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-ground-900">{t('sponsorPortal.activity.title')}</h2>
            <span className="text-xs text-ground-400">{t('sponsorPortal.activity.live')}</span>
          </div>
          <ul className="divide-y divide-ground-100 mt-1">
            {activity.slice(0, 8).map((e, i) => (
              <li key={i} className="py-3 flex items-start gap-3">
                <span className="mt-0.5 text-lg">{ACTIVITY_ICON[e.type] || '•'}</span>
                <div className="flex-1">
                  <p className="text-sm text-ground-800">{t(`sponsorPortal.activity.${e.type}`).replace('{ref}', e.ref)}</p>
                  <p className="text-xs text-ground-400">{formatDate(e.at)}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Students you support — rows on a phone, cards from md */}
      {wallet && wallet.sponsorships.length > 0 ? (
        <section className="border-b border-ground-100 py-4 md:border-0 md:py-0">
          <h2 className="text-xl sm:text-2xl font-bold text-ground-900">{t('sponsorPortal.myStudents.title')}</h2>
          <p className="text-sm text-ground-600 mt-1">{t('sponsorPortal.myStudents.subtitle')}</p>
          <div className="mt-2 max-md:divide-y max-md:divide-ground-100 md:mt-4 md:grid md:grid-cols-2 md:gap-4 lg:grid-cols-3" data-testid="my-students">
            {wallet.sponsorships.map((sp) => {
              const st = sp.student
              const offered = sp.status === 'offered'
              const discontinued = st.portfolio_status === 'discontinued'
              return (
                <Link key={sp.id} href={`/sponsor/my-students/${st.id}`}
                  className={`block py-3 transition-colors md:rounded-2xl md:border md:p-4 md:hover:border-info-300 ${offered ? 'md:bg-ground-50' : 'md:bg-ground-0'}`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-sm font-semibold text-ground-900">{st.ref}</span>
                    {offered
                      ? <span className={`text-xs rounded-full bg-ground-200 text-ground-600 px-2 py-0.5 whitespace-nowrap ${PHONE_PILL_SM}`}>⏳ {t('sponsorPortal.myStudents.awaiting')}</span>
                      : <PortfolioBadge status={st.portfolio_status} t={t} />}
                  </div>
                  {/* Full course + institution (was the bare field slug). */}
                  <p className="text-[15px] font-semibold text-ground-900 mt-2 leading-snug">{st.course || st.field || '—'}</p>
                  {st.institution && <p className="text-xs text-ground-500 mt-0.5">{st.institution}</p>}
                  {/* Key details — 12 px labels (were 10 px capitals), wrapping on a phone */}
                  <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 md:mt-3 md:grid md:grid-cols-2 md:gap-x-3 md:gap-y-1.5 md:border-t md:border-ground-100 md:pt-3">
                    {st.state && <Fact k={t('sponsorPortal.myStudents.fRegion')} v={st.state} />}
                    <Fact k={t('sponsorPortal.myStudents.fSupport')} v={`RM ${sp.amount}`} />
                    {st.academic && <Fact k={t('sponsorPortal.myStudents.fAcademic')} v={st.academic} />}
                    {st.supported_semesters ? (
                      <Fact k={t('sponsorPortal.myStudents.fSupports')}
                        v={t('sponsorPortal.myStudents.nSems').replace('{n}', String(st.supported_semesters))} />
                    ) : null}
                  </dl>
                  {!offered && (
                    <JourneyLine onboarded={sp.onboarded} state={st.progress_state} semesters={sp.semesters} discontinued={discontinued} t={t} />
                  )}
                </Link>
              )
            })}
          </div>
        </section>
      ) : (
        <section className="border-b border-ground-100 py-8 text-center md:rounded-2xl md:border md:border-dashed md:bg-ground-0 md:px-6 md:py-10">
          <p className="text-sm text-ground-500">{t('sponsorPortal.myStudents.none')}</p>
          <Link href="/sponsor/students" className="inline-flex min-h-11 items-center mt-3 rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
            {t('sponsorPortal.nav.support')} →
          </Link>
        </section>
      )}

      {/* Community belonging strip — a coloured callout, at every width */}
      {community && community.students_supported > 0 && (
        <section className="py-4 md:py-0">
          <div className="rounded-2xl bg-gradient-to-r from-info-600 to-info-700 text-white p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm opacity-90">{t('sponsorPortal.community.line1').replace('{n}', String(community.sponsors))}</p>
              <p className="text-lg font-semibold">{t('sponsorPortal.community.line2').replace('{n}', String(community.students_supported))}</p>
            </div>
            {community.students_waiting > 0 && (
              <Link href="/sponsor/students" className="inline-flex min-h-11 items-center px-4 py-2 bg-ground-0/15 hover:bg-ground-0/25 rounded-xl text-sm font-semibold">
                {t('sponsorPortal.community.waiting').replace('{n}', String(community.students_waiting))} →
              </Link>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

const ACTIVITY_ICON: Record<string, string> = {
  funded: '🤝', accepted: '✅', semester: '📘', graduated: '🎓', thank_you: '💬',
}

/** One impact figure: a plain figure on a phone, a card from md. */
function Stat({ label, value, sub, valueClass = 'text-ground-900' }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <div className="md:bg-ground-0 md:rounded-2xl md:border md:p-4">
      <p className="text-xs text-ground-500">{label}</p>
      <p className={`text-2xl font-bold ${valueClass}`}>{value}</p>
      {sub && <p className="text-xs text-ground-400 mt-1">{sub}</p>}
    </div>
  )
}

function LegendRow({ color, label, amount }: { color: string; label: string; amount: number }) {
  return (
    <li className="flex items-center justify-between max-md:gap-2">
      <span className="flex min-w-0 items-center gap-2 [overflow-wrap:anywhere]"><span className="w-2.5 h-2.5 shrink-0 rounded-full" style={{ background: color }} />{label}</span>
      <b className="shrink-0">RM {amount.toLocaleString()}</b>
    </li>
  )
}

/** A labelled key-detail on the sponsored-student row — 12 px label and value (rule 12). */
function Fact({ k, v }: { k: string; v: string }) {
  return (
    <div className="text-xs">
      <dt className="inline text-ground-500 md:block">{k}</dt>{' '}
      <dd className="inline font-semibold text-ground-800 md:block">{v}</dd>
    </div>
  )
}

/** The single sponsor-facing lifecycle badge on a sponsored-student card (post-acceptance). */
function PortfolioBadge({ status, t }: { status: SponsorPoolCard['portfolio_status']; t: (k: string) => string }) {
  if (!status) return null
  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded-full whitespace-nowrap ${portfolioBadgeTone(status)} ${PHONE_PILL_SM}`}>
      {t(`sponsorPortal.myStudents.status.${status}`)}
    </span>
  )
}
