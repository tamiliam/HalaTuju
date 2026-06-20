'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { figureTotal, figurePercent, formatRM } from '@/lib/sponsorTrust'

/**
 * Trust & Transparency hub (R5) — the load-bearing trust layer. Four sections:
 * Who we are · Governance · Sources & uses of funds · Independent assurance. The
 * editable DATA comes from the shared context's `trust` (DB-backed, no deploy to
 * update); the chrome + placeholders are trilingual i18n. Honest placeholders show
 * while the organisation is being formalised — nothing here is fabricated.
 */
export default function TrustPage() {
  const { t } = useT()
  const { trust } = useSponsorPortal()

  if (!trust) {
    return (
      <div className="max-w-3xl">
        <Link href="/sponsor" className="text-sm text-blue-600 hover:underline">← {t('sponsorPortal.trust.back')}</Link>
        <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
      </div>
    )
  }

  const a = trust.assurance
  const sourcesTotal = figureTotal(trust.sources)
  const usesTotal = figureTotal(trust.uses)
  const comingSoon = (
    <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">{t('sponsorPortal.trust.comingSoon')}</span>
  )

  return (
    <div className="max-w-4xl">
      <Link href="/sponsor" className="text-sm text-blue-600 hover:underline">← {t('sponsorPortal.trust.back')}</Link>
      <h1 className="text-2xl font-bold text-gray-900 mt-3">{t('sponsorPortal.trust.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 max-w-2xl">{t('sponsorPortal.trust.intro')}</p>

      <div className="grid lg:grid-cols-2 gap-4 mt-6">
        {/* Who we are */}
        <section className="bg-white rounded-2xl border p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">{t('sponsorPortal.trust.whoWeAre.title')}</h2>
            {!trust.legal_entity && comingSoon}
          </div>
          <p className="text-sm text-gray-500 mt-2">{t('sponsorPortal.trust.whoWeAre.body')}</p>
          <ul className="text-sm text-gray-400 mt-3 space-y-1">
            <li>• {t('sponsorPortal.trust.whoWeAre.legalLabel')} — {trust.legal_entity
              ? <span className="text-gray-700">{trust.legal_entity}</span>
              : <i>{t('sponsorPortal.trust.toBePublished')}</i>}</li>
            <li>• {t('sponsorPortal.trust.whoWeAre.storyLabel')} — <i>{t('sponsorPortal.trust.toBePublished')}</i></li>
            <li>• {t('sponsorPortal.trust.whoWeAre.contactLabel')} — {trust.contact_email}</li>
          </ul>
        </section>

        {/* Governance */}
        <section className="bg-white rounded-2xl border p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">{t('sponsorPortal.trust.governance.title')}</h2>
            {trust.trustees.length === 0 && comingSoon}
          </div>
          <p className="text-sm text-gray-500 mt-2">{t('sponsorPortal.trust.governance.body')}</p>
          {trust.trustees.length > 0 ? (
            <ul className="mt-3 space-y-2">
              {trust.trustees.map((tr, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium text-gray-900">{tr.name}</span>
                  {tr.role && <span className="text-gray-500"> — {tr.role}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 mt-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="bg-gray-50 rounded-xl p-3 text-center">
                    <div className="w-10 h-10 rounded-full bg-gray-200 mx-auto" />
                    <p className="text-[11px] text-gray-400 mt-2">{t('sponsorPortal.trust.governance.trusteeLabel')}</p>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-gray-400 mt-2">{t('sponsorPortal.trust.governance.tbd')}</p>
            </>
          )}
        </section>
      </div>

      {/* Sources & uses of funds */}
      <section className="bg-white rounded-2xl border p-5 mt-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">{t('sponsorPortal.trust.sourcesUses.title')}</h2>
          {trust.figures_are_illustrative && (
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">{t('sponsorPortal.trust.illustrative')}</span>
          )}
        </div>
        <p className="text-sm text-gray-500 mt-1">{t('sponsorPortal.trust.sourcesUses.body')}</p>
        <div className="grid md:grid-cols-2 gap-6 mt-4">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{t('sponsorPortal.trust.sourcesUses.sourcesHead')}</p>
            <FigureBars figures={trust.sources} total={sourcesTotal} tone="blue" />
            <p className="text-sm font-semibold text-gray-900 mt-3 flex justify-between">
              <span>{t('sponsorPortal.trust.sourcesUses.totalIn')}</span><span>{formatRM(sourcesTotal)}</span>
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{t('sponsorPortal.trust.sourcesUses.usesHead')}</p>
            <FigureBars figures={trust.uses} total={usesTotal} tone="green" />
            <p className="text-sm font-semibold text-gray-900 mt-3 flex justify-between">
              <span>{t('sponsorPortal.trust.sourcesUses.totalOut')}</span><span>{formatRM(usesTotal)}</span>
            </p>
          </div>
        </div>
      </section>

      {/* Independent assurance */}
      <section className="bg-white rounded-2xl border border-green-100 p-5 mt-4">
        <div className="flex items-start gap-3">
          <span className="text-2xl">🛡️</span>
          <div className="flex-1">
            <h2 className="font-semibold text-gray-900">{t('sponsorPortal.trust.assurance.title')}</h2>
            <p className="text-sm text-gray-500 mt-1 max-w-2xl">{t('sponsorPortal.trust.assurance.body')}</p>
            <div className="grid grid-cols-3 gap-2 mt-3 text-center">
              <AssureStat value={String(a.students_verified ?? 0)} label={t('sponsorPortal.trust.assurance.verified')} />
              <AssureStat value={formatRM(a.disbursed || '0')} label={t('sponsorPortal.trust.assurance.disbursed')} />
              <AssureStat value={a.fy || '—'} label={t('sponsorPortal.trust.assurance.latestReport')} />
            </div>
            <p className="text-xs text-gray-400 mt-2">
              {t('sponsorPortal.trust.assurance.auditedBy').replace('{auditor}', a.auditor || t('sponsorPortal.trust.auditorTbd'))}
              {a.report_url ? (
                <> · <a href={a.report_url} target="_blank" rel="noopener noreferrer" className="text-green-700 underline">{t('sponsorPortal.trust.assurance.downloadReport')}</a></>
              ) : null}
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

function FigureBars({ figures, total, tone }: {
  figures: { label: string; amount: string }[]
  total: number
  tone: 'blue' | 'green'
}) {
  const track = tone === 'blue' ? 'bg-blue-100' : 'bg-green-100'
  const fill = tone === 'blue' ? 'bg-blue-600' : 'bg-green-500'
  if (figures.length === 0) return <p className="text-sm text-gray-400">—</p>
  return (
    <div className="space-y-2 text-sm">
      {figures.map((f, i) => (
        <div key={i}>
          <div className="flex justify-between"><span>{f.label}</span><b>{formatRM(f.amount)}</b></div>
          <div className={`h-2 ${track} rounded-full mt-1`}>
            <div className={`h-2 ${fill} rounded-full`} style={{ width: `${figurePercent(f.amount, total)}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function AssureStat({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-green-50 rounded-xl p-3">
      <p className="text-lg font-bold text-green-700">{value}</p>
      <p className="text-[11px] text-gray-500">{label}</p>
    </div>
  )
}
