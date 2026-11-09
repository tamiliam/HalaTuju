'use client'

/**
 * THE COCKPIT'S INTERVIEW STATE AND HANDLERS (audit A3.3 — moved out of `view.tsx`, code unchanged):
 * findings, rubric and note, and save / submit / reopen / delete-a-talking-point / suggest-gaps.
 */
import { useEffect, useState } from 'react'
import {
  suggestInterviewGaps, saveInterview, submitInterview, reopenInterview,
  type AdminScholarshipDetail,
} from '@/lib/admin-api'
import { interviewRefusalText } from '@/lib/interviewCompleteness'
import type { CockpitCtx } from './cockpitCtx'

export function useInterview(ctx: CockpitCtx) {
  const { id, token, t, setApp, setBusy, setError, refreshApp } = ctx
  const [findings, setFindings] = useState<Record<string, { verdict: string; rationale: string }>>({})
  const [rubric, setRubric] = useState<Record<string, number>>({})
  const [note, setNote] = useState('')
  const [interviewMsg, setInterviewMsg] = useState('')   // transient "Saved ✓" confirmation
  // ⚠ AN INTERVIEW SAVE/SUBMIT FAILURE IS SHOWN BESIDE ITS OWN BUTTON (case 254, 2026-11-07).
  // It used to go into the page `error`, which prints only in the Profile and Decision cards —
  // off-screen from the Submit button, so a refused submit looked like nothing happened.
  const [interviewError, setInterviewError] = useState('')
  // A refusal answers the findings as they WERE; once she answers or deletes an item it is stale,
  // and the live "still to answer" line under the buttons takes over.
  useEffect(() => { setInterviewError('') }, [findings])

  const loadInterviewState = (d: AdminScholarshipDetail) => {
    const s = d.interview_session
    setFindings(s?.findings ?? {})
    setRubric(s?.rubric ?? {})
    setNote(s?.overall_note ?? '')
  }

  // One button: always APPENDS (generates 3 more, excluding any already suggested) so it never
  // wipes questions the reviewer is still considering. On an empty list it just generates the
  // first 3. To start over, the reviewer deletes the ones they don't want, then clicks again.
  const doSuggestGaps = async () => {
    if (!token) return
    setBusy('gaps'); setError('')
    try {
      setApp(await suggestInterviewGaps(id, undefined, { token }, true))
    } catch { setError(t('admin.scholarship.gaps.error')) } finally { setBusy('') }
  }

  const doSaveInterview = async () => {
    if (!token) return
    setBusy('iv'); setError(''); setInterviewError(''); setInterviewMsg('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      await refreshApp()
      // Save confidence: an explicit "Saved ✓" so the reviewer knows it persisted
      // (the draft is still editable; re-saving overwrites it, until Submit).
      setInterviewMsg(t('admin.scholarship.interview.saved'))
      setTimeout(() => setInterviewMsg(''), 4000)
    } catch { setInterviewError(t('admin.scholarship.interview.saveError')) } finally { setBusy('') }
  }

  const doSubmitInterview = async () => {
    if (!token) return
    setBusy('ivs'); setError(''); setInterviewError(''); setInterviewMsg('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      const d = await submitInterview(id, { token })
      setApp(d); loadInterviewState(d)   // freeze to the read-only view
    } catch (e) {   // TD-253: an unanswered agenda item is refused, in words — beside the button
      setInterviewError(interviewRefusalText(e, t) ?? t('admin.scholarship.interview.submitError'))
    } finally { setBusy('') }
  }

  // Reviewer reopens a submitted interview (un-submits → both boxes editable again).
  const doReopenInterview = async () => {
    if (!token) return
    setBusy('ivreopen'); setError(''); setInterviewMsg('')
    try {
      const d = await reopenInterview(id, { token })
      setApp(d); loadInterviewState(d)
    } catch { setError(t('admin.scholarship.interview.reopenError')) } finally { setBusy('') }
  }

  // Deleting an agenda talking point (an AI gap or a flag) must STICK across a refresh —
  // the rest of the Interview Stage is a draft the officer saves on demand, but a Delete
  // is a decision, so it persists immediately (write the whole session with that one item
  // flipped to 'deleted'). Without this, the delete was local-only and the item reappeared
  // on reload.
  const doDeleteAgendaItem = async (code: string) => {
    if (!token) return
    const prev = findings[code] ?? { verdict: '', rationale: '' }
    const next = { ...findings, [code]: { ...prev, verdict: 'deleted' } }
    setFindings(next)
    setBusy('delgap'); setError('')
    try {
      await saveInterview(id, { findings: next, rubric, overall_note: note }, { token })
    } catch { setError(t('admin.scholarship.interview.saveError')) } finally { setBusy('') }
  }

  return {
    findings, setFindings, rubric, setRubric, note, setNote, interviewMsg, interviewError,
    loadInterviewState, doSuggestGaps, doSaveInterview, doSubmitInterview, doReopenInterview,
    doDeleteAgendaItem,
  }
}
