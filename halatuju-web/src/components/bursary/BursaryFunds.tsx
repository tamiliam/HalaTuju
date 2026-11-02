'use client'

import SpendingCard from '@/components/sponsor/SpendingCard'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { formatMoney2dp as rm } from '@/lib/scholarship'
import type { BursaryFunds as FundsPayload } from '@/lib/api'
import { PHONE_SECTION_FLAT } from '@/lib/phoneSection'   // rule 15 (Mobile M4c)

/** The student's own words for the spending card — the `bursary` slice (loaded by the route's page,
 *  `app/scholarship/bursary/page.tsx`, rule D), never `sponsorPortal`. */
export const STUDENT_SPEND_COPY = 'bursaryTabs.spend'
/** Rule 15 (Mobile M4c): the spending card is a plain section on a phone and, from `md`, exactly the bordered
 *  card the sponsor portal draws (its default box). */
const SPEND_SECTION = 'border-b border-ground-100 py-4 md:mt-6 md:rounded-xl md:border md:border-ground-200 md:bg-ground-0 md:p-5'

/**
 * Her Funds tab on My Bursary (student maintenance S5b). Design of record: the MyBursary board's
 * "Your funds" card, expanded.
 *
 * ⚠ OWNER RULING (a), 2026-10-30: totals plus categories — THE SAME CARD HER SPONSOR SEES — and
 * nothing finer: no merchant, no transaction, no transaction date. The server sends exactly that
 * (`scholar_money.student_funds`); this screen formats strings and does no arithmetic.
 * ⚠ `spending: null` means no report has reached us yet — said in words, never four zeroes.
 */
export default function BursaryFunds({ funds }: { funds: FundsPayload }) {
  const { t } = useT()
  return (
    <div className="flex flex-col md:gap-4" data-testid="bursary-funds-tab">
      <section className={PHONE_SECTION_FLAT}>
        <h2 className="text-lg font-bold text-ground-900">{t('scholarship.bursary.funds.title')}</h2>
        <p className="mt-2 text-sm text-ground-600">
          <strong className="text-xl text-ground-900" data-testid="funds-received">RM{rm(funds.received)}</strong>{' '}
          {!funds.closed && funds.award_amount && t('scholarship.bursary.funds.of', { award: `RM${rm(funds.award_amount)}` })}
          {funds.closed && t('bursaryTabs.funds.receivedInAll')}
        </p>
        {funds.closed ? (
          <p className="mt-1 text-xs text-ground-500" data-testid="funds-ended">{t('bursaryTabs.funds.ended')}</p>
        ) : funds.award_amount && funds.remaining && (
          <p className="mt-1 text-xs text-ground-500" data-testid="funds-remaining">
            {t('bursaryTabs.funds.remaining', { amount: `RM${rm(funds.remaining)}` })}
          </p>
        )}
        <h3 className="mt-4 text-sm font-semibold text-ground-900">{t('bursaryTabs.funds.payments')}</h3>
        {funds.releases.length === 0 ? (
          <p className="mt-1 text-sm text-ground-500">{t('bursaryTabs.funds.noPayments')}</p>
        ) : (
          <ul className="mt-1 divide-y divide-ground-100 text-sm" data-testid="funds-releases">
            {funds.releases.map((r, i) => (
              <li key={i} className="flex justify-between py-2">
                <span className="text-ground-600">{r.released_on ? formatDate(r.released_on) : '—'}</span>
                <span className="tabular-nums font-medium text-ground-900">RM{rm(r.amount)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {funds.spending ? (
        <SpendingCard spending={funds.spending} copy={STUDENT_SPEND_COPY} className={SPEND_SECTION} />
      ) : (
        <p className={`${PHONE_SECTION_FLAT} text-sm text-ground-600`} data-testid="funds-no-spending">
          {t('bursaryTabs.funds.noSpending')}
        </p>
      )}
    </div>
  )
}
