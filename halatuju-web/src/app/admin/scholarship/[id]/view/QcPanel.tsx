'use client'

/**
 * QUALITY CONTROL — the QC gate on an AWAITING-QC case: accept (or confirm a decline), reopen
 * with a gaps note, reject outright, or — for a super — override the V5 gap floor with a
 * written reason.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import type { Dispatch, SetStateAction } from 'react'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T, AdminRole } from './shared'

export function QcPanel({
  app, t, busy, canQc, role, doQcDecision,
  qcReopenOpen, setQcReopenOpen, qcComments, setQcComments,
  qcRejectMode, setQcRejectMode, qcOverrideOpen, setQcOverrideOpen,
  qcOverrideReason, setQcOverrideReason,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  canQc: boolean
  role: AdminRole
  doQcDecision: (decision: 'accept' | 'reopen' | 'reject', overrideReason?: string) => void
  qcReopenOpen: boolean
  setQcReopenOpen: Dispatch<SetStateAction<boolean>>
  qcComments: string
  setQcComments: Dispatch<SetStateAction<string>>
  qcRejectMode: boolean
  setQcRejectMode: Dispatch<SetStateAction<boolean>>
  qcOverrideOpen: boolean
  setQcOverrideOpen: Dispatch<SetStateAction<boolean>>
  qcOverrideReason: string
  setQcOverrideReason: Dispatch<SetStateAction<string>>
}) {
  return (<>

      {/* ── Quality Control — the QC gate on an AWAITING-QC ('interviewed') case (a `qc` role or
            super). Accept → Recommended; Reopen → back to the reviewer with a gaps note (emailed).
            Self-QC guard: a `qc` who reviewed this case cannot QC it (hidden here; backend blocks it too). ── */}
      {app.status === 'interviewed' && canQc
        && !((role?.role === 'qc' || role?.role === 'org_admin') && app.assigned_to_id === (role?.admin_id ?? null)) && (() => {
        // V5 gap floor (#5): a red/'gap' verdict fact blocks Accept. A super sees an override
        // affordance (reason recorded server-side); anyone else resolves the gap or reopens.
        const qcGapFacts = (app.verdict || []).filter((f) => f.status === 'gap').map((f) => f.fact)
        const qcGapLabels = qcGapFacts.map((f) => t(`admin.scholarship.verdict.fact.${f}`)).join(', ')
        // A DECLINE verdict at QC confirms a REJECTION, not a recommendation (owner 2026-07-19).
        // The gap floor does NOT apply — a declined case is EXPECTED to have red facts — and the
        // primary button reads "Confirm decline" (red), not "Accept".
        const isDeclineVerdict = app.officer_verdict?.overall === 'decline'
        const floorBlocked = qcGapFacts.length > 0 && !isDeclineVerdict
        return (
        <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.qcDecision.title')}</h2>
          <p className="text-xs text-ground-600">{t(isDeclineVerdict ? 'admin.scholarship.qcDecision.hintDecline' : 'admin.scholarship.qcDecision.hint')}</p>
          {floorBlocked && (
            <p className="rounded-lg border border-critical-200 bg-critical-50 p-2 text-xs text-critical-800">
              {t('admin.scholarship.qcDecision.gapFloor', { facts: qcGapLabels })}
              {canQc && <> {t('admin.scholarship.qcDecision.gapFloorSuper')}</>}
            </p>
          )}
          {!qcReopenOpen && !qcOverrideOpen ? (
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => {
                  if (!floorBlocked) { doQcDecision('accept'); return }
                  if (canQc) { setQcOverrideOpen(true); setQcOverrideReason('') }
                }}
                disabled={!!busy || (floorBlocked && !canQc)}
                /* ⚠ THE INK MOVED INSIDE THE BRANCHES (F7e). It was one shared `text-white`
                   outside the ternary, serving a decline button and an accept button; the codemod
                   could only pick one tone for it and chose `positive`, which rendered correctly
                   only because both tones resolve their ink to the same value today. A decline
                   button carrying positive ink is a trap for whoever next tunes one tone. */
                className={`rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${isDeclineVerdict ? 'border-critical-fill bg-critical-fill text-critical-fill-ink hover:bg-critical-fill-hover' : 'border-positive-fill bg-positive-fill text-positive-fill-ink hover:bg-positive-fill-hover'}`}>
                {busy === 'qc' ? t('common.loading')
                  : t(isDeclineVerdict ? 'admin.scholarship.qcDecision.confirmDecline' : 'admin.scholarship.qcDecision.accept')}
              </button>
              <button onClick={() => { setQcReopenOpen(true); setQcComments('') }} disabled={!!busy}
                className="rounded-lg border border-caution-600 bg-ground-0 px-4 py-2.5 text-sm font-medium text-caution-700 hover:bg-caution-50 disabled:opacity-50">
                {t(isDeclineVerdict ? 'admin.scholarship.qcDecision.reopenOnly' : 'admin.scholarship.qcDecision.reopen')}
              </button>
            </div>
          ) : qcOverrideOpen ? (
            <div className="rounded-lg border border-critical-200 bg-critical-50 p-3 space-y-2">
              <p className="text-xs font-medium text-critical-900">{t('admin.scholarship.qcDecision.overrideTitle')}</p>
              <textarea value={qcOverrideReason} rows={3} onChange={(e) => setQcOverrideReason(e.target.value)}
                placeholder={t('admin.scholarship.qcDecision.overridePlaceholder')}
                className="w-full rounded border border-critical-300 px-2 py-1.5 text-sm" />
              <div className="flex items-center gap-2">
                <button onClick={() => doQcDecision('accept', qcOverrideReason)}
                  disabled={!!busy || !qcOverrideReason.trim()}
                  className="rounded-lg bg-critical-fill px-3 py-1.5 text-xs font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
                  {busy === 'qc' ? t('common.loading') : t('admin.scholarship.qcDecision.overrideConfirm')}
                </button>
                <button onClick={() => { setQcOverrideOpen(false); setQcOverrideReason('') }}
                  className="text-xs text-ground-500 hover:text-ground-700">{t('common.cancel')}</button>
              </div>
            </div>
          ) : (
            <div className={`rounded-lg border p-3 space-y-2 ${qcRejectMode ? 'border-critical-200 bg-critical-50' : 'border-caution-200 bg-caution-50'}`}>
              <p className={`text-xs font-medium ${qcRejectMode ? 'text-critical-900' : 'text-caution-900'}`}>
                {t(isDeclineVerdict ? 'admin.scholarship.qcDecision.reopenTitleDecline'
                  : qcRejectMode ? 'admin.scholarship.qcDecision.rejectTitle' : 'admin.scholarship.qcDecision.reopenTitle')}
              </p>
              <textarea value={qcComments} rows={3} onChange={(e) => setQcComments(e.target.value)}
                placeholder={t(isDeclineVerdict ? 'admin.scholarship.qcDecision.commentsPlaceholderDecline'
                  : qcRejectMode ? 'admin.scholarship.qcDecision.rejectPlaceholder' : 'admin.scholarship.qcDecision.commentsPlaceholder')}
                className={`w-full rounded border px-2 py-1.5 text-sm ${qcRejectMode ? 'border-critical-300' : 'border-caution-300'}`} />
              {/* Reject toggle (default off): flip the reopen box into an outright rejection.
                  Hidden on the decline route — reject is already the primary "Confirm decline" button,
                  so offering it again here is redundant; the secondary path is reopen-only. */}
              {!isDeclineVerdict && (
              <label className="flex items-center gap-2 text-xs text-ground-700 select-none cursor-pointer">
                <input type="checkbox" checked={qcRejectMode} disabled={!!busy}
                  onChange={(e) => setQcRejectMode(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-ground-300 text-critical-600 focus:ring-critical-500" />
                {t('admin.scholarship.qcDecision.rejectToggle')}
              </label>
              )}
              <div className="flex items-center gap-2">
                <button onClick={() => doQcDecision(qcRejectMode ? 'reject' : 'reopen')} disabled={!!busy || !qcComments.trim()}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold text-caution-fill-ink disabled:opacity-50 ${qcRejectMode ? 'bg-critical-fill hover:bg-critical-fill-hover' : 'bg-caution-fill hover:bg-caution-fill-hover'}`}>
                  {busy === 'qc' ? t('common.loading')
                    : t(qcRejectMode ? 'admin.scholarship.qcDecision.rejectConfirm' : 'admin.scholarship.qcDecision.reopenConfirm')}
                </button>
                <button onClick={() => { setQcReopenOpen(false); setQcComments(''); setQcRejectMode(false) }}
                  className="text-xs text-ground-500 hover:text-ground-700">{t('common.cancel')}</button>
              </div>
            </div>
          )}
        </div>
        )
      })()}

  </>)
}
