'use client'

/**
 * THE DECISION CARD — the reviewer's recommendation: the reopen prompt and banner, the recorded trail once
 * the decision is locked, and while it is open the justification, Recommend / Decline and Save.
 *
 * ⚠ Lifted out of `view.tsx` whole at Mobile M6b (the file sits on the oversize ledger and M6b adds to the
 * page). MOVES ONLY: every line below is the line it was; `view.tsx` hands it the same names it used.
 */
import type { Dispatch, SetStateAction } from 'react'
import { isQcAccepted, rejectionTrail, showsDecisionCards } from '@/lib/officerCockpit'
import { stageStatus } from '@/lib/closeOffer'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import { QcOverrideNote, type T } from './shared'
import { ReopenHeaderControl } from './ReopenHeaderControl'
import { ReasonBox } from './ReasonBox'
import { decisionBarShows } from './DecisionBar'

export function DecisionCard({
  app, t, busy, canWrite, isSuper, error, decisionLocked, decisionReopened, decisionRecorded, reopenOpen, setReopenOpen, reopenReason, setReopenReason, doReopenDecision, doCancelReopen, doCancelDecline, verdictReason, setVerdictReason, reviewerName, reviewerDate, hasQc, qcName, qcDate, recordedOutcome, doReject, stuckAfterVerdict, officerVerdict, selectApprove, selectDecline, approveReady, decisionReady, interviewSubmitted, interviewMissing, hasAssistance, doSave, canSave, verdictMsg, verdictMsgTone,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  canWrite: boolean
  isSuper: boolean
  error: string
  decisionLocked: boolean
  decisionReopened: boolean
  decisionRecorded: boolean
  reopenOpen: boolean
  setReopenOpen: Dispatch<SetStateAction<boolean>>
  reopenReason: string
  setReopenReason: Dispatch<SetStateAction<string>>
  doReopenDecision: () => void
  doCancelReopen: () => void
  doCancelDecline: () => void
  verdictReason: string
  setVerdictReason: Dispatch<SetStateAction<string>>
  reviewerName: string
  reviewerDate: string
  hasQc: boolean
  qcName: string
  qcDate: string
  recordedOutcome: string | null
  doReject: (category: 'interview' | 'contractual') => void
  stuckAfterVerdict: boolean
  officerVerdict: Record<string, string>
  selectApprove: () => void
  selectDecline: () => void
  approveReady: boolean
  decisionReady: boolean
  interviewSubmitted: boolean
  interviewMissing: unknown[]
  hasAssistance: boolean
  doSave: () => void
  canSave: boolean
  verdictMsg: string
  verdictMsgTone: 'ok' | 'warn'
}) {
  const saveShows = decisionBarShows({ app, decisionReopened, decisionRecorded, decisionLocked, canWrite })
  return (<>

      {/* ── Decision — audit the four facts (records the verdict) → verify identity →
           accept. The audit→accept gate is preserved (accept stays gated on a complete
           profile + every checklist box). ──────────────────────────────────────────── */}
      {/* Hidden at shortlisted (pre-submission): Approve/Decline need a submitted interview.
          Hidden on a CLOSED case with no verdict — there is no decision left to record, and the
          justification box invited writing one. WITH a verdict it stays: that is the frozen
          decision trail (21 rejected records on 2026-08-18), which must not disappear. */}
      {showsDecisionCards({ status: app.status, decisionReopened, decisionRecorded }) && (
      <div id="decision-section" className="scroll-mt-16 border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-ground-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.decision.title')}</h2>
          {/* Reopen = REVERSE a recorded decision (super-only; asks for a reason first). A pending
              decline offers its cancel instead — the api refuses that reopen (TD-349). */}
          <ReopenHeaderControl app={app} t={t} busy={busy} decisionLocked={decisionLocked} isSuper={isSuper}
            hidden={reopenOpen} onReopen={() => { setReopenOpen(true); setReopenReason('') }} onCancelDecline={doCancelDecline} />
        </div>

        {/* The "why are you reopening?" prompt — a reopen asserts a reviewer error, so a
            reason is required (logged + counted against the reviewer once a change is saved). */}
        {decisionLocked && isSuper && reopenOpen && (
          <ReasonBox
            title={t('admin.scholarship.recordVerdict.reopenTitle')}
            hint={t('admin.scholarship.recordVerdict.reopenHint')}
            placeholder={t('admin.scholarship.recordVerdict.reopenPlaceholder')}
            confirmLabel={t('admin.scholarship.recordVerdict.reopenConfirm')}
            workingLabel={t('common.loading')} cancelLabel={t('common.cancel')}
            value={reopenReason} onChange={setReopenReason} onConfirm={doReopenDecision}
            onCancel={() => { setReopenOpen(false); setReopenReason('') }}
            disabled={!!busy} working={busy === 'reopen'} />
        )}

        {/* Reopened banner — the decision is editable again and the profile is held from
            the pool. "Cancel reopen" restores it unchanged; saving the decision republishes. */}
        {decisionReopened && (
          <div className="rounded-lg border border-caution-300 bg-caution-50 p-3 space-y-2">
            <p className="text-sm font-medium text-caution-900">{t('admin.scholarship.recordVerdict.reopenedBanner')}</p>
            {app.decision_reopen_reason && (
              <p className="text-xs text-caution-800">
                <span className="font-medium">{t('admin.scholarship.recordVerdict.reopenReasonLabel')}:</span> {app.decision_reopen_reason}
              </p>
            )}
            {isSuper && (
              <button onClick={doCancelReopen} disabled={!!busy}
                className="px-3 py-1.5 border border-caution-400 text-caution-900 rounded-lg text-xs hover:bg-caution-100 disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
                {busy === 'reopen' ? t('common.loading') : t('admin.scholarship.recordVerdict.cancelReopen')}
              </button>
            )}
          </div>
        )}

        {decisionLocked ? (
          /* Decision recorded → read-only. Inputs/buttons are gone so it can't look
             editable; a superadmin can reopen via Edit. The post-accept contractual
             decline stays (a deliberate later action, not part of the frozen verdict). */
          <div className="space-y-3">
            {/* The recorded Pass/Fail + the bursary amount now live in the Rate-AI and
                Estimated-need cards above; this card keeps the justification + who/when. */}
            {(verdictReason || '').trim() && (
              <div>
                <p className="text-xs font-medium text-ground-600 mb-1">{t('admin.scholarship.recordVerdict.reasonLabel')}</p>
                <div className="rounded-lg border border-info-100 bg-info-50/50 p-3">
                  <p className="whitespace-pre-line text-sm text-ground-800">{verdictReason}</p>
                </div>
              </div>
            )}
            {isQcAccepted(stageStatus(app, 'recommended_at')) ? (
              <>
                <p className="flex items-start gap-1.5 text-sm text-positive-700">
                  <span aria-hidden>✓</span>
                  <span>
                    {t('admin.scholarship.interviewedRecommendedBy')} {reviewerName}{reviewerDate}
                    {hasQc && <>{', '}{t('admin.scholarship.qcAcceptedBy')} {qcName}{qcDate}</>}
                  </span>
                </p>
                <QcOverrideNote app={app} t={t} />
              </>
            ) : app.status === 'rejected' ? (
              /* Decision-history trail (rejectionTrail). A decline is a TWO-person decision just
                 like a recommend — the reviewer records it, a QC upholds it — so the record names
                 both, like the accepted card above. Earlier steps are muted; the step that
                 ENDED the case is red. */
              <div className="space-y-1.5">
                {rejectionTrail(app).map((step, i) => {
                  const stamp = step.date ? ` · ${formatDate(step.date)}` : ''
                  if (step.kind === 'reopened') {
                    return (
                      <div key={i} className="flex items-start gap-1.5 text-sm text-caution-800">
                        <span aria-hidden>↩</span>
                        <span>
                          {t('admin.scholarship.recordVerdict.reopenedBy')} {step.name}{stamp}
                          {step.reason && (
                            <span className="block whitespace-pre-line text-caution-700">“{step.reason}”</span>
                          )}
                        </span>
                      </div>
                    )
                  }
                  const ended = step.kind === 'declined' || step.kind === 'qcAcceptedDecline'
                  const label = step.kind === 'reviewerDeclined'
                    ? t('admin.scholarship.interviewedDeclinedBy')
                    : step.kind === 'reviewerRecommended'
                      ? t('admin.scholarship.interviewedRecommendedBy')
                      : step.kind === 'qcAcceptedRecommendation'
                        ? t('admin.scholarship.recordVerdict.recommendationAcceptedBy')
                        : step.kind === 'qcAcceptedDecline'
                          ? t('admin.scholarship.recordVerdict.declineAcceptedBy')
                          : t('admin.scholarship.recordVerdict.declinedBy')
                  const tick = step.kind === 'reviewerRecommended' || step.kind === 'qcAcceptedRecommendation'
                    ? '✓' : '✗'
                  return (
                    <p key={i} className={`flex items-start gap-1.5 text-sm ${ended ? 'text-critical-700' : 'text-ground-600'}`}>
                      <span aria-hidden>{tick}</span>
                      <span>{label} {step.name}{stamp}</span>
                    </p>
                  )
                })}
              </div>
            ) : (
              /* ⚠ THE LINE FOLLOWS THE RECORDED OUTCOME (owner, 2026-09-18). This is the
                 IN-FLIGHT case — which is exactly where a DECLINE awaiting QC sits — and it
                 read "Interviewed and recommended by" on a case the reviewer had declined.
                 Same family as the stuck banner beside it (BrightPath #24): one sentence
                 serving two outcomes. `interviewedDeclinedBy` already existed for the
                 rejection trail, so nothing new is minted here. */
              <p className="text-sm text-ground-600">
                {t(recordedOutcome === 'decline'
                     ? 'admin.scholarship.interviewedDeclinedBy'
                     : 'admin.scholarship.interviewedRecommendedBy')} {reviewerName}{reviewerDate}
              </p>
            )}
            {(app.status === 'active' || app.status === 'maintenance') && canWrite && (
              <button onClick={() => doReject('contractual')} disabled={!!busy}
                className="px-4 py-2 border border-critical-300 text-critical-700 rounded-lg text-sm disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
                {busy === 'reject' ? t('admin.scholarship.reject.running') : t('admin.scholarship.reject.declineContractual')}
              </button>
            )}
          </div>
        ) : (
        <>
        {/* Justification & conclusion — the officer's case. The AI-verification facts and the
            proposed bursary now live in their own cards above this one. */}
        {/* Reason textarea */}
        <div>
          <label className="block text-xs font-medium text-ground-600 mb-1">
            {t('admin.scholarship.recordVerdict.reasonLabel')}
          </label>
          <textarea
            value={verdictReason}
            rows={3}
            disabled={!canWrite}
            onChange={(e) => setVerdictReason(e.target.value)}
            placeholder={t('admin.scholarship.recordVerdict.reasonPlaceholder')}
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
        </div>

        {/* Decision actions — pick a REVERSIBLE outcome (Approve / Decline), then Save commits it. */}
        {isQcAccepted(stageStatus(app, 'recommended_at')) && !decisionReopened ? (
          /* Committed acceptance → read-only summary. A post-accept decline goes through a
             super's Reopen (→ interviewed, AWAITING QC) and then the QC decision (TD-481: the
             server's /reject/ refuses 'interview' at interviewed, code awaiting_qc; this card
             never offers that bucket); the direct 'contractual' decline is reserved for a
             genuinely post-award (sponsored) case. */
          <div className="space-y-2 border-t pt-3">
            <p className="flex items-start gap-1.5 text-sm text-positive-700">
              <span aria-hidden>✓</span>
              <span>
                {t('admin.scholarship.interviewedRecommendedBy')} {reviewerName}{reviewerDate}
                {hasQc && <>{', '}{t('admin.scholarship.qcAcceptedBy')} {qcName}{qcDate}</>}
              </span>
            </p>
            <QcOverrideNote app={app} t={t} />
            {(app.status === 'active' || app.status === 'maintenance') && canWrite && (
              <button onClick={() => doReject('contractual')} disabled={!!busy}
                className="px-4 py-2 border border-critical-300 text-critical-700 rounded-lg text-sm disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
                {busy === 'reject' ? t('admin.scholarship.reject.running') : t('admin.scholarship.reject.declineContractual')}
              </button>
            )}
          </div>
        ) : (decisionReopened || ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status)) ? (
          // ONE rule with the phone's decision bar (M6b review): here every other clause of `decisionBarShows` already
          // holds, so it answers exactly what `canWrite` answered — and the bar can never disagree with this card.
          saveShows && (
            <div className="space-y-2">
              {/* The old coarse "still owes: documents / consent" banner moved OUT to its own
                  Blockers card below this one (owner 2026-07-22) — it now names each item
                  from the consent gate instead of two categories. */}
              {/* ⚠ SAY THAT THE VERDICT IS ALREADY SAVED. Without this the panel looks untouched
                  on a fresh load, so a reviewer coming back to a half-completed Approve cannot
                  tell whether her decision was recorded — and the only clue she ever had was a
                  message that vanished with the page. */}
              {stuckAfterVerdict && (
                <p className="rounded-lg bg-caution-50 px-3 py-2 text-xs md:text-[11px] text-caution-800">
                  {t(recordedOutcome === 'decline'
                       ? 'admin.scholarship.recordVerdict.savedNotSubmittedDecline'
                       : 'admin.scholarship.recordVerdict.savedNotSubmitted',
                     { date: formatDate(app.verdict_decided_at) })}
                </p>
              )}
              {/* Reversible outcome selection. Approve needs an amount; Decline doesn't (and clears it). */}
              <div className="grid grid-cols-2 gap-2">
                <button onClick={selectApprove} disabled={!!busy || !approveReady}
                  className={`rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${
                    officerVerdict.overall === 'accept'
                      ? 'border-positive-fill bg-positive-fill text-positive-fill-ink'
                      : 'border-positive-600 bg-ground-0 text-positive-700 hover:bg-positive-50'} max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center`}>
                  {t('admin.scholarship.recordVerdict.approve')}
                </button>
                <button onClick={selectDecline} disabled={!!busy || !decisionReady}
                  className={`rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${
                    officerVerdict.overall === 'decline'
                      ? 'border-critical-fill bg-critical-fill text-critical-fill-ink'
                      : 'border-critical-500 bg-ground-0 text-critical-700 hover:bg-critical-50'} max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center`}>
                  {t('admin.scholarship.recordVerdict.decline')}
                </button>
              </div>
              {/* One contextual hint: what's still missing before Save. */}
              {!decisionReady ? (
                <p className="text-xs md:text-[11px] text-caution-700">{interviewSubmitted && interviewMissing.length > 0
                  ? t('admin.scholarship.recordVerdict.findingsIncomplete', { count: String(interviewMissing.length) })
                  : t('admin.scholarship.recordVerdict.saveNeedsReady')}</p>
              ) : !officerVerdict.overall ? (
                <p className="text-xs md:text-[11px] text-caution-700">{t('admin.scholarship.recordVerdict.chooseOutcome')}</p>
              ) : officerVerdict.overall === 'accept' && !hasAssistance ? (
                <p className="text-xs md:text-[11px] text-caution-700">{t(app.award_disqualifier
                  ? 'admin.scholarship.recordVerdict.approveNeedsReview'
                  : 'admin.scholarship.recordVerdict.approveNeedsAmount')}</p>
              ) : null}
              {/* Save is the final commit of the chosen outcome. */}
              <button onClick={doSave} disabled={!!busy || !canSave}
                className="w-full px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium disabled:opacity-50 max-md:min-h-11 max-md:inline-flex max-md:items-center max-md:justify-center">
                {/* ⚠ THE LABEL FOLLOWS THE CHOSEN OUTCOME (owner, BrightPath #24). One fixed
                    "Save & generate final profile" promised a profile on a DECLINE, which
                    generates none and should not — the reviewer was told the opposite of what
                    the button does. */}
                {(busy === 'verdict' || busy === 'reject')
                  ? t('common.loading')
                  : t(officerVerdict.overall === 'decline'
                        ? 'admin.scholarship.recordVerdict.saveDecline'
                        : 'admin.scholarship.recordVerdict.save')}
              </button>
            </div>
          )
        ) : (
          <p className="text-sm text-ground-400">{t('admin.scholarship.notShortlisted')}</p>
        )}
        </>
        )}

        {/* Feedback message */}
        {verdictMsg && (
          <p className={`text-xs rounded p-2 ${verdictMsgTone === 'ok' ? 'text-positive-700 bg-positive-50' : 'text-caution-800 bg-caution-50'}`}>{verdictMsg}</p>
        )}

        {error && <p className="text-critical-600 text-xs">{error}</p>}
      </div>
      )}

  </>)
}
