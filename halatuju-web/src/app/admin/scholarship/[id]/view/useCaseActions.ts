'use client'

/**
 * THE COCKPIT'S ONE-SHOT ACTIONS (audit A3.3 — moved out of `view.tsx`): remind the student,
 * record a reporting date, cancel a scheduled decline / hold a pending award, and assign a reviewer.
 *
 * ⚠ THE THREE QUESTIONS ARE ASKED IN THE SITE'S DIALOG NOW (TD-480), not in `window.confirm`. The
 * `do…` handlers only RAISE the question (`ask`); `confirmAsk` runs what was asked, with the api
 * calls exactly as they were.
 */
import { useState } from 'react'
import {
  getScholarshipApplication, cancelPendingDecline, holdPendingAward, assignApplication,
  nudgeStudent, setReportingDate,
} from '@/lib/admin-api'
import type { CockpitCtx } from './cockpitCtx'

export type CockpitAsk = 'nudge' | 'cancelDecline' | 'holdAward'

/** The words of each question — the labels and the question each one always had. */
export function askCopy(ask: CockpitAsk, nudgeLabel: string) {
  const s = 'admin.scholarship'
  if (ask === 'nudge') {
    return { title: `${s}.blockers.nudge.${nudgeLabel}`, question: `${s}.blockers.nudge.confirm`, dismissible: true }
  }
  return ask === 'cancelDecline'
    ? { title: `${s}.cooloff.cancelDecline`, question: `${s}.cooloff.cancelConfirm`, dismissible: false }
    : { title: `${s}.cooloff.holdAward`, question: `${s}.cooloff.holdConfirm`, dismissible: false }
}

/** `admins` = the picker's list, to NAME somebody the server refused as `not_signed_in` (M2d A1). */
export function useCaseActions(ctx: CockpitCtx, admins: ReadonlyArray<{ id: number; name: string }> = []) {
  const { id, token, t, setApp, setBusy, setError } = ctx
  const [ask, setAsk] = useState<CockpitAsk | null>(null)

  // "You haven't submitted yet" reminder — org-admin manual re-send (the auto nudge fires once,
  // ~30 min after consent; this is the human follow-up). Asks first, then refreshes the
  // nudge state (new sent_at + cooldown) from the returned detail.
  const [nudgeMsg, setNudgeMsg] = useState('')
  const runNudge = async () => {
    setBusy('nudge'); setNudgeMsg('')
    try {
      setApp(await nudgeStudent(id, { token: token! }))
      setNudgeMsg(t('admin.scholarship.blockers.nudge.done'))
    } catch (e) {
      setNudgeMsg(e instanceof Error ? e.message : t('admin.scholarship.blockers.nudge.error'))
    } finally { setBusy('') }
  }

  // Reporting date — recorded by hand when the offer letter carries no readable one. QC refuses
  // to accept without it, so this is how a blocked case gets cleared (owner 2026-07-23).
  const [reportingDateInput, setReportingDateInput] = useState('')
  const [reportingDateMsg, setReportingDateMsg] = useState('')
  const doSetReportingDate = async () => {
    if (!token || !reportingDateInput) return
    setBusy('reportingDate'); setReportingDateMsg('')
    try {
      setApp(await setReportingDate(id, reportingDateInput, { token }))
      setReportingDateInput('')
    } catch (e) {
      setReportingDateMsg(e instanceof Error ? e.message : t('admin.actionFailed'))
    } finally { setBusy('') }
  }

  // Cool-off controls: cancel a scheduled decline / hold a pending award before it reveals.
  const runCancelDecline = async () => {
    setBusy('cooloff'); setError('')
    try { setApp(await cancelPendingDecline(id, { token: token! })) }
    catch { setError(t('admin.scholarship.cooloff.error')) } finally { setBusy('') }
  }
  const runHoldAward = async () => {
    setBusy('cooloff'); setError('')
    try { setApp(await holdPendingAward(id, { token: token! })) }
    catch { setError(t('admin.scholarship.cooloff.error')) } finally { setBusy('') }
  }
  const raise = (q: CockpitAsk) => () => { if (token) setAsk(q) }
  const doNudge = raise('nudge')
  const doCancelDecline = raise('cancelDecline')
  const doHoldAward = raise('holdAward')
  /** The officer answered Yes: close the question and run what it asked. */
  const confirmAsk = async () => {
    const q = ask
    setAsk(null)
    if (q === 'nudge') await runNudge()
    else if (q === 'cancelDecline') await runCancelDecline()
    else if (q === 'holdAward') await runHoldAward()
  }

  const doAssign = async (adminId: number | null) => {
    if (!token) return
    setBusy('assign'); setError('')
    // A2.3: the assign reply is slim (who holds it now), so the case is reloaded for the page.
    try { await assignApplication(id, adminId, { token }); setApp(await getScholarshipApplication(id, { token })) }
    catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['not_ready', 'not_reviewer', 'reviewer_paused', 'bad_assignee',
                     'findings_submitted', 'gift_mismatch', 'not_signed_in']
      setError(known.includes(code)
        ? t(`admin.scholarship.assign.error.${code}`, code === 'not_signed_in'
          ? { name: admins.find((a) => a.id === adminId)?.name ?? '' } : undefined)
        : t('admin.scholarship.assignError'))
    } finally { setBusy('') }
  }

  return {
    ask, setAsk, confirmAsk, nudgeMsg, doNudge, doCancelDecline, doHoldAward,
    reportingDateInput, setReportingDateInput, reportingDateMsg, doSetReportingDate, doAssign,
  }
}
