'use client'

import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import type { SponsorStatement } from '@/lib/api/sponsor'

/** The giving statement (two ledgers). Its own chunk: the account page fetches it only when there is one. */
export function GivingStatement({ statement }: { statement: SponsorStatement }) {
  const { t } = useT()
  return (
        <section className="border-b border-ground-100 py-4 md:border-0 md:py-0">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-ground-900">{t('sponsorPortal.statement.title')}</h2>
            <button onClick={() => window.print()} className="min-h-11 px-3 py-1.5 text-sm font-semibold text-primary-700 bg-primary-50 hover:bg-primary-100 rounded-xl">
              {t('sponsorPortal.statement.print')}
            </button>
          </div>
          <p className="text-sm text-ground-600 mt-1">{t('sponsorPortal.statement.intro')} <span className="text-ground-400">{t('sponsorPortal.statement.taxNote')}</span></p>
          <div className="mt-1 max-md:divide-y max-md:divide-ground-100 md:mt-3 md:grid md:grid-cols-2 md:gap-4">
            <div className="py-3 md:rounded-2xl md:border md:bg-ground-0 md:p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-ground-900">⬇ {t('sponsorPortal.statement.donations')}</h3>
                <span className="text-xs text-ground-400">RM {statement.total_in}</span>
              </div>
              {statement.donations.length > 0 ? (
                <ul className="text-sm divide-y divide-ground-100">
                  {statement.donations.map((d, i) => (
                    <li key={i} className="py-2 flex justify-between gap-2">
                      <span>{formatDate(d.at)}{d.reference ? <span className="text-ground-400"> · {d.reference}</span> : null}</span>
                      <b>RM {d.amount}</b>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-ground-400">—</p>}
              <p className="text-xs text-ground-400 mt-2">{t('sponsorPortal.statement.donationsNote')}</p>
            </div>
            <div className="py-3 md:rounded-2xl md:border md:bg-ground-0 md:p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-ground-900">⬆ {t('sponsorPortal.statement.gifts')}</h3>
                <span className="text-xs text-ground-400">RM {statement.total_out}</span>
              </div>
              {statement.gifts.length > 0 ? (
                <ul className="text-sm divide-y divide-ground-100">
                  {statement.gifts.map((g, i) => (
                    <li key={i} className="py-2 flex justify-between gap-2">
                      <span>{formatDate(g.at)} <span className="text-ground-400">· {g.ref}</span></span>
                      <b>RM {g.amount}</b>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-ground-400">—</p>}
              <p className="text-xs text-ground-400 mt-2">{t('sponsorPortal.statement.giftsNote')}</p>
            </div>
          </div>
        </section>
  )
}
