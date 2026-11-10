'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import type { AdminReviewerDetail } from '@/lib/admin-api'
import { hasNoHistory, outcomeSegments, turnaroundBand, type OutcomeKey } from '@/lib/reviewerDetail'

/**
 * Sprint T3: the REVIEWER parts of a person page (request #10's page, moved here whole). What they
 * carry (the figures, in the header card — M4), what became of what they decided (Outcomes), and every
 * decision of theirs that was reopened, each with the reason recorded at the time (Reopens).
 *
 * ⚠ The reopens block is the reason this page exists rather than a wider table. Seventeen of
 * BrightPath's sixty-five decisions carry a reopen and several were caused by OUR defects, not by
 * anybody's judgement. The number alone would be read as a competence score; the reason is what tells
 * the two apart, so the two never appear separately.
 */

/**
 * The colour of each outcome band — one home, so the bar and its legend cannot drift apart.
 *
 * ⚠ Amber and red are DIFFERENT on purpose. Amber is a rejection this reviewer made; red is one
 * somebody else made on a case they reviewed. Painting both the same accuses them of a decision
 * that was not theirs.
 */
const OUTCOME_BG: Record<OutcomeKey, string> = {
  recommended: 'bg-positive-500',
  declined: 'bg-caution-500',
  rejectedAfterReview: 'bg-critical-500',
  awaitingQc: 'bg-ground-400',
}

export function Block({ title, children, note, testId }: {
  title: string
  children: ReactNode
  note?: string
  testId?: string
}) {
  return (
    <section className="bg-ground-0 rounded-xl shadow-sm border overflow-hidden" data-testid={testId}>
      <div className="px-4 sm:px-5 py-3.5 border-b">
        <h2 className="text-[11.5px] font-semibold uppercase tracking-wider text-ground-600">{title}</h2>
      </div>
      {children}
      {note && <p className="px-4 sm:px-5 py-3 text-xs text-ground-500 max-w-3xl">{note}</p>}
    </section>
  )
}

/** One summary figure. Right-aligned so the numbers line up — from md; on a phone they are two by two
 *  and read from the left. */
function Figure({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="text-right max-md:min-w-0 max-md:text-left max-md:[overflow-wrap:anywhere]">
      <div className={`text-xl sm:text-2xl font-semibold tabular-nums leading-tight ${tone ?? 'text-ground-900'}`}>
        {value}
      </div>
      <div className="text-[10.5px] font-semibold uppercase tracking-wider text-ground-500 mt-0.5">{label}</div>
    </div>
  )
}

/** Mobile M8: four figures in one row ran 70 px past the card at 360. Below md they are two by two
 *  across the card; from md one row. Request #51: the list's two halves, not their sum. */
export function ReviewerFigures({ detail }: { detail: AdminReviewerDetail }) {
  const { t } = useT()
  const band = turnaroundBand(detail.turnaround_days)
  return (
    <div className="flex gap-6 md:gap-8 max-md:grid max-md:w-full max-md:grid-cols-2 max-md:gap-y-3"
      data-testid="reviewer-figures">
      <Figure label={t('admin.reviewers.colAwaiting')} value={String(detail.awaiting_review)} />
      <Figure label={t('admin.reviewers.colInterviewing')} value={String(detail.interviewing)} />
      <Figure label={t('admin.reviewers.colCompleted')} value={String(detail.completed)} />
      <Figure label={t('admin.reviewers.colTurnaround')} tone={band === 'waiting' ? 'text-caution-700' : undefined}
        value={band === 'unknown'
          ? t('admin.reviewers.noTurnaround')
          : t('admin.reviewers.days', { days: String(detail.turnaround_days) })} />
    </div>
  )
}

/** The bar is the shape; the counts beneath it are the fact. A percentage alone over single-digit
 *  caseloads would say "100%" about one decision. ⚠ The four bands PARTITION the decided cases (the
 *  server guarantees it), so the bar always reconciles with the Completed figure. */
export function ReviewerOutcomes({ detail }: { detail: AdminReviewerDetail }) {
  const { t } = useT()
  const segments = outcomeSegments(detail)
  return (
    <Block title={t('admin.reviewers.detail.outcomes')} testId="reviewer-outcomes"
      note={hasNoHistory(detail) ? t('admin.reviewers.detail.noHistory') : undefined}>
      {segments.length === 0 ? (
        <p className="px-4 sm:px-5 py-4 text-sm text-ground-500">{t('admin.reviewers.detail.noOutcomes')}</p>
      ) : (
        <div className="px-4 sm:px-5 py-4">
          <div className="flex h-2.5 rounded-full overflow-hidden bg-ground-100" aria-hidden>
            {segments.map((s) => <div key={s.key} style={{ width: `${s.pct}%` }} className={OUTCOME_BG[s.key]} />)}
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3.5 text-sm">
            {segments.map((s) => (
              <span key={s.key} className="text-ground-700">
                <span className={`inline-block w-2.5 h-2.5 rounded-sm mr-1.5 ${OUTCOME_BG[s.key]}`} />
                {t(`admin.reviewers.detail.${s.key}`)}{' '}
                <span className="font-semibold text-ground-900">{s.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </Block>
  )
}

export function ReviewerReopens({ detail }: { detail: AdminReviewerDetail }) {
  const { t } = useT()
  return (
    <Block title={t('admin.reviewers.detail.reopens')} note={t('admin.reviewers.detail.reopensNote')}
      testId="reviewer-reopens">
      {detail.reopens.length === 0 ? (
        <p className="px-4 sm:px-5 py-4 text-sm text-ground-500">{t('admin.reviewers.detail.noReopens')}</p>
      ) : (
        <ul className="divide-y divide-ground-100">
          {detail.reopens.map((r) => (
            <li key={r.id} className="px-4 sm:px-5 py-3.5">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <Link href={`/admin/scholarship/${r.application_id}`}
                  className="text-sm font-medium text-primary-600 hover:text-primary-800 max-md:inline-flex max-md:min-h-11 max-md:items-center">
                  {t('admin.reviewers.detail.application', { id: String(r.application_id) })}
                </Link>
                <span className="text-xs text-ground-500">
                  {t('admin.reviewers.detail.reopenedBy', { by: r.reopened_by || '—', date: formatDate(r.at) })}
                </span>
              </div>
              {/* The reason, always — never a bare count. */}
              <p className="text-sm text-ground-700 mt-1 whitespace-pre-wrap">{r.reason}</p>
            </li>
          ))}
        </ul>
      )}
    </Block>
  )
}
