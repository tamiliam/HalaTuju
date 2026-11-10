'use client'

/**
 * THE COCKPIT'S DECISION STATE AND HANDLERS (audit A3.3 — moved out of `view.tsx`, code unchanged):
 * the officer's verdict, save / decline / reject, reopen, the QC gate and the org-admin reject.
 */
import { useState } from 'react'
import {
  verifyAcceptApplication, rejectApplication, submitDeclineApplication, orgRejectApplication,
  recordVerdict, reopenDecision, cancelReopen, recordQcDecision,
  type AdminScholarshipDetail,
} from '@/lib/admin-api'
import { isClearAccept, verdictSaveOutcome, verdictSaveErrorText } from '@/lib/officerCockpit'
import { interviewRefusalText } from '@/lib/interviewCompleteness'
import { qcRefusalText } from './QcPanel'
import type { CockpitCtx } from './cockpitCtx'

export function useVerdict(ctx: CockpitCtx, genLang: string) {
  const { id, token, t, app, setApp, setProfile, setBusy, setError } = ctx
  // Sprint 5 — Officer cockpit
  const [officerVerdict, setOfficerVerdict] = useState<Record<string, string>>({})
  const [verdictReason, setVerdictReason] = useState('')
  const [verdictMsg, setVerdictMsg] = useState('')
  const [verdictMsgTone, setVerdictMsgTone] = useState<'ok' | 'warn'>('ok')
  // Decision reopen (reverse a recorded decision). The reopened STATE is server-driven
  // (app.decision_reopened_at) so it survives a reload; these only drive the reason input.
  const [reopenOpen, setReopenOpen] = useState(false)    // the "why are you reopening?" box is showing
  const [reopenReason, setReopenReason] = useState('')
  // QC gate (on an AWAITING-QC 'interviewed' case): Accept, or Reopen with a gaps note.
  const [qcReopenOpen, setQcReopenOpen] = useState(false)
  const [qcComments, setQcComments] = useState('')
  // Reject toggle inside the reopen box (default off): on → the case is rejected outright
  // instead of returned to the reviewer (owner 2026-07-19).
  const [qcRejectMode, setQcRejectMode] = useState(false)
  // V5 gap floor: super-only override panel state (reason recorded server-side).
  const [qcOverrideOpen, setQcOverrideOpen] = useState(false)
  const [qcOverrideReason, setQcOverrideReason] = useState('')

  const loadVerdictState = (d: AdminScholarshipDetail) => {
    const v = d.officer_verdict ?? {}
    setOfficerVerdict({
      identity: v.identity ?? '',
      academic: v.academic ?? '',
      income: v.income ?? '',
      pathway: v.pathway ?? '',
      overall: v.overall ?? '',
    })
    setVerdictReason(d.verdict_reason ?? '')
  }

  // TD-227 (A1.11a): the decline needs a reason (stored on the case; the server answers 400
  // comments_required without one). The confirm became a prompt; Cancel still does nothing.
  const doReject = async (category: 'interview' | 'contractual', preset = '') => {
    if (!token) return
    const confirmKey = category === 'contractual'
      ? 'admin.scholarship.reject.confirmContractual' : 'admin.scholarship.reject.confirmReview'
    const answer = window.prompt(`${t(confirmKey)}\n\n${t('admin.scholarship.reject.reasonPrompt')}`, preset)
    if (answer === null) return
    const comments = answer.trim()
    if (!comments) { setError(t('admin.scholarship.reject.reasonRequired')); return }
    setBusy('reject'); setError('')
    try {
      setApp(await rejectApplication(id, category, comments, { token }))
    } catch (e) {
      const code = (e as { code?: string } | null)?.code
      setError(code === 'comments_required' ? t('admin.scholarship.reject.reasonRequired')
        : e instanceof Error ? e.message : t('admin.scholarship.reject.error'))
    } finally { setBusy('') }
  }

  // Org-admin reject of a stuck SHORTLISTED applicant. Three deliberate steps — idle → form
  // (mandatory reason) → confirm — because unlike every other decline this one is IMMEDIATE and
  // IRREVERSIBLE: there is no cool-off and therefore no Cancel banner to undo it. The confirm
  // step IS the safety net, so it is in-page (not a window.confirm the browser can suppress).
  const [rejectStep, setRejectStep] = useState<'idle' | 'form' | 'confirm'>('idle')
  const [rejectComments, setRejectComments] = useState('')
  const [rejectErr, setRejectErr] = useState('')
  const closeReject = () => { setRejectStep('idle'); setRejectComments(''); setRejectErr('') }
  const doOrgReject = async () => {
    if (!token) return
    setBusy('orgReject'); setRejectErr('')
    try {
      setApp(await orgRejectApplication(id, rejectComments.trim(), { token }))
      closeReject()
    } catch (e) {
      // Stay on the confirm step so the typed reason isn't lost on a transient failure.
      setRejectErr(e instanceof Error ? e.message : t('admin.scholarship.orgReject.error'))
    } finally { setBusy('') }
  }

  /** True when the verdict was recorded — a refusal must stop the decline chain below (review F5). */
  const doRecordVerdict = async (finalise: boolean, accept = false): Promise<boolean> => {
    if (!token) return false
    setBusy('verdict'); setError(''); setVerdictMsg('')
    try {
      const result = await recordVerdict(id, {
        officer_verdict: officerVerdict,
        reason: verdictReason || undefined,
        finalise,
        language: genLang,
      }, { token })
      // Save verdict IS the decision: when the officer's verdict is a clear accept
      // (Identity = Pass, nothing failed), the profile is complete, and the case is
      // still live, accept in the same click. No separate IC-verify/lock step —
      // identity was already verified at the consent gate.
      let finalApp: AdminScholarshipDetail = result
      let accepted = false
      const clearAccept = isClearAccept(!!result.completeness?.complete, result.status)
      if (accept && clearAccept) {
        try {
          finalApp = await verifyAcceptApplication(id, {}, { token })
          accepted = true
        } catch (e) {
          // The verdict is saved; only the accept failed (e.g. an NRIC clash) — surface it.
          setError(verdictSaveErrorText(e, t, 'admin.scholarship.acceptError'))
        }
      }
      setApp(finalApp)
      setProfile(finalApp.sponsor_profile)
      loadVerdictState(finalApp)
      // ⚠ EVERY OUTCOME GETS A LINE — BrightPath #20 was this block staying silent. The reviewer
      // asked to submit, the submit was skipped, and the screen said nothing, so the case sat for
      // fourteen days. `verdictSaveOutcome` is a closed set precisely so a new branch cannot be
      // added without a message. The not-submitted lines come BEFORE `finalise`: "your case did
      // not move" outranks "the profile was regenerated".
      const outcome = verdictSaveOutcome({
        acceptRequested: !!accept,
        accepted,
        completenessComplete: !!result.completeness?.complete,
        status: result.status,
      })
      if (outcome === 'accepted') {
        setVerdictMsg(t('admin.scholarship.decision.savedAndAccepted')); setVerdictMsgTone('ok')
      } else if (outcome === 'not_submitted_incomplete') {
        setVerdictMsg(t('admin.scholarship.decision.notSubmittedIncomplete')); setVerdictMsgTone('warn')
      } else if (outcome === 'not_submitted_status') {
        setVerdictMsg(t('admin.scholarship.decision.notSubmittedStatus')); setVerdictMsgTone('warn')
      } else if (finalise) {
        const fr = result.finalise_result
        if (fr && fr.ok) {
          // Verdict recorded and the final profile queued (A2.1: written in the background, `pending`).
          setVerdictMsg(t(fr.pending ? 'admin.scholarship.recordVerdict.finalisePending' : 'admin.scholarship.recordVerdict.finaliseOk')); setVerdictMsgTone('ok')
        } else {
          // Saved, but NOT finalised — work is incomplete. Amber, not green.
          // `engine_error` = the AI step failed; it is not a missing draft (request #61).
          setVerdictMsg(t(fr?.code === 'no_interview' ? 'admin.scholarship.recordVerdict.finaliseNoInterview'
            : fr?.code === 'engine_error' ? 'admin.scholarship.recordVerdict.finaliseEngineError'
              : 'admin.scholarship.recordVerdict.finaliseNoDraft'))
          setVerdictMsgTone('warn')
        }
      }
      return true
    } catch (e) {
      setError(interviewRefusalText(e, t) ?? verdictSaveErrorText(e, t, 'admin.scholarship.acceptError'))
      return false
    } finally { setBusy('') }
  }

  // Decision = pick a REVERSIBLE outcome (Approve / Decline), then Save commits it. The
  // chosen outcome lives in officerVerdict.overall ('' | 'accept' | 'decline').
  const selectApprove = () => setOfficerVerdict((v) => ({ ...v, overall: 'accept' }))
  // The amount is now managed backend-side by record-verdict (accept → auto-apply the
  // pathway-standard amount; decline → clear), so the UI no longer pokes the award endpoint.
  const selectDecline = () => setOfficerVerdict((v) => ({ ...v, overall: 'decline' }))
  // Send a recorded DECLINE verdict to QC (→ AWAITING QC) instead of rejecting directly. A second
  // reviewer then CONFIRMS the decline (→ rejected) or reopens it (owner 2026-07-19).
  const doSubmitDecline = async () => {
    if (!token) return
    setBusy('verdict'); setError('')
    try {
      const updated = await submitDeclineApplication(id, { token })
      setApp(updated); setProfile(updated.sponsor_profile); loadVerdictState(updated)
      setVerdictMsg(t('admin.scholarship.decision.declineSentToQc')); setVerdictMsgTone('ok')
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError'))
    } finally { setBusy('') }
  }
  const doSave = async () => {
    const outcome = officerVerdict.overall
    if (outcome === 'accept') {
      await doRecordVerdict(true, true)                 // record (overall=accept) + finalise + accept + publish
    } else if (outcome === 'decline') {
      // Record the decline verdict, then route to QC. A post-award (recommended) case still
      // declines via the contractual path (that decline is already post-QC); an in-review case
      // goes to AWAITING QC for a second pair of eyes before it becomes a rejection.
      if (!(await doRecordVerdict(false, false))) return   // refused: sending on would 400 over it
      if (app?.status === 'recommended') {
        await doReject('contractual', verdictReason)
      } else {
        await doSubmitDecline()
      }
    }
  }

  // Reverse a recorded decision (super-only). Reopening HOLDS the sponsor profile from
  // the pool and unlocks the panel; a reason is required (it asserts a reviewer error).
  const doReopenDecision = async () => {
    if (!token || !reopenReason.trim()) return
    setBusy('reopen'); setError(''); setVerdictMsg('')
    try {
      const result = await reopenDecision(id, reopenReason.trim(), { token })
      setApp(result)
      setProfile(result.sponsor_profile)
      loadVerdictState(result)
      setReopenOpen(false); setReopenReason('')
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.recordVerdict.reopenError'))
    } finally { setBusy('') }
  }

  // Close a reopen with NO change — restore the profile to its prior published state.
  const doCancelReopen = async () => {
    if (!token) return
    setBusy('reopen'); setError(''); setVerdictMsg('')
    try {
      const result = await cancelReopen(id, { token })
      setApp(result)
      setProfile(result.sponsor_profile)
      loadVerdictState(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.recordVerdict.reopenError'))
    } finally { setBusy('') }
  }

  // QC gate on an AWAITING-QC ('interviewed') case. Accept → Recommended; Reopen → back to the
  // reviewer at 'interviewing' with the gaps comments (emailed to the assigned reviewer).
  // V5 gap floor: while a verdict fact is red the server refuses accept (verdict_gap_floor);
  // a super passes it with overrideReason, which the server records.
  const doQcDecision = async (decision: 'accept' | 'reopen' | 'reject', overrideReason?: string) => {
    if (!token) return
    // Reopen AND reject both carry the shared-with-reviewer comment (the gaps / the reject reason).
    const carriesComments = decision === 'reopen' || decision === 'reject'
    if (carriesComments && !qcComments.trim()) return
    setBusy('qc'); setError(''); setVerdictMsg('')
    try {
      const result = await recordQcDecision(
        id, { decision, comments: carriesComments ? qcComments.trim() : undefined,
              override_reason: overrideReason?.trim() || undefined }, { token })
      setApp(result)
      setProfile(result.sponsor_profile)
      loadVerdictState(result)
      setQcReopenOpen(false); setQcComments(''); setQcRejectMode(false)
      setQcOverrideOpen(false); setQcOverrideReason('')
    } catch (e) {
      const code = (e as { code?: string })?.code
      // TD-483: every separation code in en / ms / ta (was only `self_verdict_qc_forbidden`).
      setError(qcRefusalText(code, t)
        || (e instanceof Error ? e.message : t('admin.scholarship.qcDecision.error')))
    } finally { setBusy('') }
  }

  return {
    officerVerdict, setOfficerVerdict, verdictReason, setVerdictReason, verdictMsg, verdictMsgTone,
    reopenOpen, setReopenOpen, reopenReason, setReopenReason,
    qcReopenOpen, setQcReopenOpen, qcComments, setQcComments, qcRejectMode, setQcRejectMode,
    qcOverrideOpen, setQcOverrideOpen, qcOverrideReason, setQcOverrideReason,
    rejectStep, setRejectStep, rejectComments, setRejectComments, rejectErr, closeReject,
    loadVerdictState, doReject, doOrgReject, selectApprove, selectDecline, doSave,
    doReopenDecision, doCancelReopen, doQcDecision,
  }
}
