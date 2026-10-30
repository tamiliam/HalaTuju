'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { rm } from '@/lib/programmeOverview'
import { getScholarMoney, type ScholarMoney as MoneyPayload } from '@/lib/admin-api'

const CARD = 'rounded-xl border border-ground-200 bg-ground-0 p-5'
const money = (v: string | null | undefined) => (v == null ? '—' : `RM${rm(v)}`)

/**
 * The scholar file's Money tab (student maintenance S5a). Design of record: the canvas file's Money
 * card — Award / Paid / Remaining, her last payments, spending this term by category, and the ways
 * into Payments and Spending.
 *
 * ⚠ NO ARITHMETIC HERE. Award, paid and remaining are the server's (`scholar_money`, THE Payments
 * rules), as strings; this screen formats them and nothing else, so it cannot disagree with the
 * Payments page, her My Bursary page or her sponsor's card.
 * ⚠ THE SPENDING BLOCK IS THE SERVER'S DECISION: it is absent from the payload unless the viewer
 * holds the `spending` permission, and this component draws it only when it is there.
 */
export default function ScholarMoney({ id, token, links }: {
  id: number
  token: string | null
  /** The pages this viewer may open, already carrying the file's gift. */
  links: { page: 'payments' | 'spending'; href: string }[]
}) {
  const { t } = useT()
  const [data, setData] = useState<MoneyPayload | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!token) return
    getScholarMoney(id, { token }).then(setData).catch(() => setFailed(true))
  }, [id, token])

  if (failed) return <p className="text-sm text-critical-600">{t('admin.scholars.moneyTab.loadFailed')}</p>
  if (!data) return <p className="text-sm text-ground-400">{t('common.loading')}</p>
  const spending = data.spending

  return (
    <div className="flex flex-col gap-4">
      <section className={CARD} aria-label={t('admin.scholars.card.money')}>
        <div className="grid grid-cols-3 gap-3 text-sm">
          {(['award_amount', 'paid_to_date', 'remaining'] as const).map((k) => (
            <div key={k}>
              <div className="text-ground-600">{t(`admin.scholars.money.${k}`)}</div>
              <div className="text-xl font-semibold tabular-nums text-ground-900" data-testid={`money-${k}`}>
                {money(data[k])}
              </div>
            </div>
          ))}
        </div>
        <h3 className="mt-5 text-sm font-semibold text-ground-900">{t('admin.scholars.moneyTab.releases')}</h3>
        {data.releases.length === 0 ? (
          <p className="mt-1 text-sm text-ground-500">{t('admin.scholars.money.noPayment')}</p>
        ) : (
          <ul className="mt-1 divide-y divide-ground-100 text-sm" data-testid="money-releases">
            {data.releases.map((r, i) => (
              <li key={i} className="flex items-center justify-between py-2">
                <span className="text-ground-700">
                  {r.released_on ? formatDate(r.released_on) : '—'}
                  {(r.label || r.reference) && <span className="ml-2 text-xs text-ground-500">{r.label || r.reference}</span>}
                </span>
                <span className="tabular-nums font-medium text-ground-900">{money(r.amount)}</span>
              </li>
            ))}
          </ul>
        )}
        {links.length > 0 && (
          <p className="mt-4 flex gap-4 text-sm">
            {links.map((l) => (
              <Link key={l.page} href={l.href} className="text-primary-600 hover:underline">
                {t(l.page === 'payments' ? 'admin.scholars.money.openPayments' : 'admin.scholars.money.openSpending')}
              </Link>
            ))}
          </p>
        )}
      </section>

      {spending && (
        <section className={CARD} aria-label={t('admin.scholars.moneyTab.spendingTitle')} data-testid="money-spending">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-sm font-semibold text-ground-900">{t('admin.scholars.moneyTab.spendingTitle')}</h3>
            <span className="text-xs text-ground-500">
              {spending.since
                ? t(`admin.scholars.moneyTab.since.${spending.basis}`, { date: formatDate(spending.since) })
                : t('admin.scholars.moneyTab.since.all')}
              {spending.as_at && ` · ${t('admin.scholars.moneyTab.asAt', { date: formatDate(spending.as_at) })}`}
            </span>
          </div>
          <p className="mt-2 text-xl font-semibold tabular-nums text-ground-900">{money(spending.spent)}</p>
          {spending.categories.length === 0 ? (
            <p className="mt-1 text-sm text-ground-500">{t('admin.scholars.moneyTab.noSpending')}</p>
          ) : (
            <ul className="mt-2 divide-y divide-ground-100 text-sm">
              {spending.categories.map((c) => (
                <li key={c.code} className="flex items-center justify-between py-1.5">
                  <span className="text-ground-700">{c.label}</span>
                  <span className="tabular-nums text-ground-900">{money(c.total)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
