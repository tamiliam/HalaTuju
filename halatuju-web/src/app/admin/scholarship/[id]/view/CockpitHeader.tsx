'use client'

/**
 * THE CASE HEADER — who this applicant is, where the case stands, and the two cool-off banners
 * that let an admin cancel a scheduled decline or hold a pending award before the student sees
 * anything.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import Link from 'next/link'
import VerifiedTick from '@/components/VerifiedTick'
import { formatNric, referralAcronym } from '@/lib/scholarship'
import { statusLabelKey, statusTone, displayStatus } from '@/lib/applicationStatus'
import { headerTimeline } from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T, Vtip } from './shared'

export function CockpitHeader({
  app, t, vtip, busy, canWrite, prevId, nextId, doCancelDecline, doHoldAward,
}: {
  app: AdminScholarshipDetail
  t: T
  vtip: Vtip
  busy: string
  canWrite: boolean
  prevId: number | null
  nextId: number | null
  doCancelDecline: () => void
  doHoldAward: () => void
}) {
  return (<>

      {/* Header — applicant identity, status, and key facts at a glance */}
      <header className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <Link href="/admin/scholarship" className="text-xs text-ground-400 hover:text-ground-600">‹ {t('admin.scholarship.back')}</Link>
          {(prevId != null || nextId != null) && (
            <div className="flex items-center gap-1 text-xs">
              {prevId != null ? (
                <Link href={`/admin/scholarship/${prevId}`} className="rounded px-2 py-1 font-medium text-ground-600 hover:bg-ground-100">‹ {t('admin.scholarship.prev')}</Link>
              ) : (
                <span className="rounded px-2 py-1 text-ground-300">‹ {t('admin.scholarship.prev')}</span>
              )}
              {nextId != null ? (
                <Link href={`/admin/scholarship/${nextId}`} className="rounded px-2 py-1 font-medium text-ground-600 hover:bg-ground-100">{t('admin.scholarship.next')} ›</Link>
              ) : (
                <span className="rounded px-2 py-1 text-ground-300">{t('admin.scholarship.next')} ›</span>
              )}
            </div>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-xl font-bold tracking-tight text-ground-900 sm:text-2xl">{app.name || '—'}{vtip('name') && <VerifiedTick label={vtip('name')!} />}</h1>
          {/* Status pill — a super-reopened decision shows "Reopened" (overrides accepted/rejected). */}
          {(() => {
            const s = displayStatus(app)
            return (
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusTone(s)}`}>
                {t(statusLabelKey(s))}
              </span>
            )
          })()}
          {/* Primary action button — scrolls to the Record Verdict panel. Not shown once
              'interviewed' (awaiting QC): the verdict is submitted, panel is read-only. */}
          {canWrite && ['shortlisted', 'profile_complete', 'interviewing'].includes(app.status) && (
            <button
              onClick={() => document.getElementById('record-verdict-panel')?.scrollIntoView({ behavior: 'smooth' })}
              className="ml-auto rounded-lg bg-brand-fill px-3 py-1.5 text-xs font-semibold text-brand-fill-ink shadow-sm hover:bg-brand-fill-hover"
            >
              {t('admin.scholarship.recordVerdict.title')}
            </button>
          )}
          {app.status === 'rejected' && app.rejection_category && (
            <span className="rounded-full bg-critical-100 px-2.5 py-0.5 text-xs font-semibold text-critical-700">
              {t(`admin.scholarship.reject.category.${app.rejection_category}`)}
            </span>
          )}
          {app.bucket && (
            <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-caution-100 px-1.5 text-xs font-bold text-caution-700">{app.bucket}</span>
          )}
          {app.qualification && (
            <span className="rounded-full border border-ground-200 px-2 py-0.5 text-xs font-medium text-ground-500">{app.qualification.toUpperCase()}</span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ground-500">
          <span>NRIC <span className="font-mono text-ground-700">{formatNric(app.nric || '') || '—'}</span>{vtip('nric') && <VerifiedTick label={vtip('nric')!} />}</span>
          {referralAcronym(app.referral_source) && (
            <span
              title={app.referral_source ? t(`scholarship.apply.org.${app.referral_source}`) : ''}
              className="rounded-full border border-ground-200 px-2 py-0.5 font-medium text-ground-600"
            >
              {referralAcronym(app.referral_source)}
            </span>
          )}
          {(() => {
            // Post-recommendation, the header shows a lifecycle timeline (Submitted·Recommended·
            // Awarded, then Awarded·Active·Maintenance). Earlier states keep the original
            // Submitted·Applied·Assigned line (Assigned carries the reviewer, not a date).
            const timeline = headerTimeline(app)
            if (timeline) {
              return timeline.map((step) => (
                <span key={step.labelKey}>
                  {t(`admin.scholarship.statuses.${step.labelKey}`)}{' '}
                  <span className="text-ground-700">{step.at ? formatDate(step.at) : '—'}</span>
                </span>
              ))
            }
            return (
              <>
                {app.submitted_at && (
                  <span>{t('admin.scholarship.submitted')} {formatDate(app.submitted_at)}</span>
                )}
                {app.profile_completed_at && (
                  <span>{t('admin.scholarship.applied')} {formatDate(app.profile_completed_at)}</span>
                )}
                <span>{t('admin.scholarship.assigned')} <span className="text-ground-700">{app.assigned_to_name || '—'}</span></span>
              </>
            )
          })()}
        </div>
      </header>

      {/* Cool-off (#13/#14): a decision recorded but held silently — the student sees nothing
          until the reveal date, so it can be cancelled/held in the window. Admin-only. */}
      {app.decline_due_at && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3">
          <p className="text-sm text-caution-800">
            ⏳ {t('admin.scholarship.cooloff.declineScheduled')}{' '}
            <strong>{formatDate(app.decline_due_at)}</strong>.{' '}
            {t('admin.scholarship.cooloff.silentNote')}
          </p>
          <button onClick={doCancelDecline} disabled={busy === 'cooloff'}
            className="whitespace-nowrap rounded-lg border border-caution-300 bg-ground-0 px-3 py-1.5 text-sm font-medium text-caution-800 hover:bg-caution-100 disabled:opacity-50">
            {busy === 'cooloff' ? '…' : t('admin.scholarship.cooloff.cancelDecline')}
          </button>
        </div>
      )}
      {app.award_due_at && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3">
          <p className="text-sm text-caution-800">
            ⏳ {t('admin.scholarship.cooloff.awardScheduled')}{' '}
            <strong>{formatDate(app.award_due_at)}</strong>.{' '}
            {t('admin.scholarship.cooloff.silentNote')}
          </p>
          <button onClick={doHoldAward} disabled={busy === 'cooloff'}
            className="whitespace-nowrap rounded-lg border border-caution-300 bg-ground-0 px-3 py-1.5 text-sm font-medium text-caution-800 hover:bg-caution-100 disabled:opacity-50">
            {busy === 'cooloff' ? '…' : t('admin.scholarship.cooloff.holdAward')}
          </button>
        </div>
      )}

  </>)
}
