'use client'
/**
 * Request #75 (analysis 172, 2026-11-16): the Overview funnel's count of students REJECTED BEFORE
 * INTERVIEW, in total and by main reason. It sits under the funnel, where the decline count already
 * shows (that "Rejected" tile includes these; this says how many of them never had an interview,
 * and why). The server counts (`services/pre_interview.counts`): every reason zero-filled, in the
 * panel's order; a cancelled one is not counted. Like the funnel, nothing shows at zero.
 *
 * Its own file because `OverviewSections.tsx` sits at the 600-line standard; its own markup (not
 * `Tile`) so the two files do not import each other.
 */
import type { OverviewFunnel } from '@/lib/admin-api'

/** ⚠ The i18n guard resolves `${K}.` templates by this LITERAL name. */
const K = 'admin.programmeOverview'
const R = 'admin.scholarship.preInterview.reasons'

export function PreInterviewCounts({ funnel, t }: {
  funnel: OverviewFunnel
  t: (key: string, params?: Record<string, string>) => string
}) {
  const counts = funnel.pre_interview
  if (!counts || counts.total <= 0) return null
  const reasons = Object.entries(counts.by_reason).filter(([, n]) => n > 0)
  return (
    <div className="mt-2.5 rounded-xl border border-critical-200 bg-ground-0 p-3.5 max-md:p-3"
      data-testid="overview-pre-interview">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11px] font-medium text-ground-500">{t(`${K}.funnel.preInterview`)}</span>
        <span className="text-xl font-semibold tabular-nums text-ground-900 max-md:text-base">{counts.total}</span>
      </div>
      <div className="mt-2 text-[11px] font-medium text-ground-500">{t(`${K}.funnel.preInterviewByReason`)}</div>
      <dl className="mt-1 text-sm">
        {reasons.map(([code, n]) => (
          <div key={code} className="flex items-center justify-between border-b border-ground-100 py-1 last:border-b-0">
            <dt className="text-ground-700">{t(`${R}.${code}`)}</dt>
            <dd className="tabular-nums font-semibold text-ground-900">{n}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
