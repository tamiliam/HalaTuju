'use client'

/** One engineer's analysis (TD-204), as the owner reads it.
 *
 * Moved VERBATIM out of `src/app/admin/requests/[id]/page.tsx` on 2026-10-29 (moves only, plus the
 * hours form this sprint adds): that page sits in the oversize ledger at 663 lines against a
 * 683-line allowance, and the standard asks for a SPLIT rather than for prose to be trimmed until
 * the number passes. The card is a coherent thing to split — a badge, the prose, the citations, the
 * published hours and the two draft actions all describe ONE analysis.
 *
 * ⚠ OWNER-ONLY, the whole card. The analysis reaches the requesting organisation as PROSE, through
 * the thread, authored `engineer`; the cited files and every hours figure stay on this side. Neither
 * is secrecy — see `OrgRequestAnalysis`'s own docstring, where the omission is a decision.
 */

import { formatDate, formatDateTime } from '@/lib/formatDate'
import type { OrgRequestAnalysis, OrgRequestDetail } from '@/lib/admin-api'
import {
  analysisBadge, analysisBadgeKey, analysisBadgeTone, analysisApproveCopy, analysisApproveKind,
} from '@/lib/requestStatus'

type T = (k: string, vars?: Record<string, string>) => string

export function RequestAnalysisCard({
  analysis: a, req, t, busy, predatesLastComment, onApprove, onWithdraw,
}: {
  analysis: OrgRequestAnalysis
  req: OrgRequestDetail
  t: T
  busy: boolean
  predatesLastComment: boolean
  onApprove: () => void
  onWithdraw: () => void
}) {
  const badge = analysisBadge(a)
  const copy = analysisApproveCopy(analysisApproveKind(a, req))

  return (
    <li className={`rounded-lg border p-3 text-sm ${
      a.is_current ? 'border-positive-200 bg-positive-50'
        : a.superseded_at ? 'border-ground-200 bg-ground-50 opacity-70'
        : 'border-caution-200 bg-caution-50'}`}>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${analysisBadgeTone(badge)}`}>
          {t(analysisBadgeKey(badge))}
        </span>
        {a.estimated_hours && (
          <span className="font-semibold text-ground-900">
            {t('admin.requests.owner.analysisHoursValue', { hours: a.estimated_hours })}
          </span>
        )}
        {/* Rendered in the same change that stores them — this project has five
            stored-but-never-surfaced fields already, and that cluster stops here. */}
        {a.authored_by && <span className="text-xs text-ground-500">{a.authored_by}</span>}
        {a.repo_sha && (
          <span className="text-xs text-ground-400 font-mono">{a.repo_sha.slice(0, 12)}</span>
        )}
        {/* TIME, not just the date: two drafts staged the same day were otherwise
            indistinguishable — same badge, same hours, same cited files. */}
        <span className="text-xs text-ground-400">{formatDateTime(a.created_at)}</span>
      </div>
      <p className="text-ground-800 whitespace-pre-wrap mt-2">{a.body}</p>
      {a.cited_files.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium text-ground-500">{t('admin.requests.owner.analysisFiles')}</p>
          <ul className="mt-1 space-y-0.5">
            {a.cited_files.map((f) => (
              <li key={f} className="text-xs font-mono text-ground-600 break-all">{f}</li>
            ))}
          </ul>
        </div>
      )}
      {a.approved_at && a.approved_by_name && (
        <p className="text-xs text-ground-400 mt-2">
          {t('admin.requests.owner.analysisApprovedBy', { name: a.approved_by_name })} · {formatDate(a.approved_at)}
        </p>
      )}
      {/* The amber staleness note: an ANSWER can change scope without triggering a
          supersede (only `modify` does), so say so rather than block. */}
      {a.is_current && predatesLastComment && (
        <p className="text-xs text-caution-700 mt-2">{t('admin.requests.owner.analysisStale')}</p>
      )}
      {badge === 'draft' && (<>
        <div className="mt-3 flex items-center gap-2">
          <button disabled={busy}
            onClick={() => { if (confirm(t(copy.confirm))) onApprove() }}
            className="px-4 bg-positive-fill text-positive-fill-ink py-2 rounded-lg text-sm font-medium hover:bg-positive-fill-hover disabled:opacity-50">
            {t(copy.label)}
          </button>
          {/* Retire a draft the engineer got wrong. Nothing here has reached the
              requester, so this is a tidy-up, not an undo — but without it a stale
              draft sits in this list one click from being approved as a duplicate. */}
          <button disabled={busy}
            onClick={() => { if (confirm(t('admin.requests.owner.analysisWithdrawConfirm'))) onWithdraw() }}
            className="px-4 border border-ground-300 text-ground-700 py-2 rounded-lg text-sm font-medium hover:bg-ground-50 disabled:opacity-50">
            {t('admin.requests.owner.analysisWithdraw')}
          </button>
        </div>
        <p className="text-xs text-ground-500 mt-2">{t(copy.next)}</p>
      </>)}
    </li>
  )
}
