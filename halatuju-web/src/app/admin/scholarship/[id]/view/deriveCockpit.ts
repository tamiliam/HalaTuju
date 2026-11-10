/**
 * EVERYTHING THE COCKPIT WORKS OUT FROM THE CASE (audit A3.3 — moved out of `view.tsx`, logic
 * unchanged, now a plain function so it reads without a component around it).
 *
 * Inputs are the loaded case plus the three things an officer has typed or chosen (`findings`,
 * `officerVerdict`, `verdictReason`); outputs are the locks, gates and labels the panels read.
 */
import { fieldVerifications, type VerifiableField } from '@/lib/fieldVerification'
import {
  isStuckAfterVerdict, isDecisionReady, isApproveReady, isQueryingLocked, queryingLockReason,
} from '@/lib/officerCockpit'
import { interviewGateApplies, missingAgendaItems } from '@/lib/interviewCompleteness'
import { formatDate } from '@/lib/formatDate'
import { anomalyParams } from '@/lib/docSeen'
import type { AdminScholarshipDetail, AdminAgendaEntry } from '@/lib/admin-api'
import { ANOMALY_CHECK2_OWNER } from './shared'
import type { TFn } from './cockpitCtx'

export function deriveCockpit(
  app: AdminScholarshipDetail,
  t: TFn,
  findings: Record<string, { verdict: string; rationale: string }>,
  officerVerdict: Record<string, string>,
  verdictReason: string,
) {
  // Field-level "verified" ticks — a small badge beside a value that MATCHES an uploaded,
  // machine-read document (see lib/fieldVerification). vtip() → the hover tooltip naming the source
  // doc, or undefined when the field isn't corroborated (then no tick renders). Declared here (not
  // in the cards block) so the header name/NRIC can use it too.
  const _fv = fieldVerifications(app)
  const vtip = (field: VerifiableField): string | undefined =>
    _fv[field]
      ? t('admin.scholarship.verified.tooltip', {
          source: t(`admin.scholarship.verified.source.${_fv[field]!.source}`),
        })
      : undefined

  // A superadmin has REOPENED the recorded decision (server-driven; held from sponsors).
  // A reopen reopens the WHOLE case for revision — Check 2 + Interview Stage + Decision all
  // unlock for the assigned reviewer (and super), not just the decision panel.
  const decisionReopened = !!app.decision_reopened_at

  // Attribution lines on the Recommendation card. The reviewer INTERVIEWED & recommended
  // (verdict_decided_*); the QC ACCEPTED (recommended_*). The "accepted by" clause shows ONLY
  // when a real QC identity was captured — we never fall back to the reviewer's own verify stamp,
  // because the reviewer is not the QC and that would misattribute. Cases recommended before the
  // QC gate existed (no QC step) simply omit the clause.
  const reviewerName = app.verdict_decided_by_name || app.verdict_decided_by || '—'
  const reviewerDate = app.verdict_decided_at ? ` · ${formatDate(app.verdict_decided_at)}` : ''
  const hasQc = !!app.recommended_by
  const qcName = app.recommended_by_name || app.recommended_by || '—'
  const qcDate = app.recommended_at ? ` · ${formatDate(app.recommended_at)}` : ''

  // S4: once the interview is concluded it's decision time — querying (raise / Resolve /
  // Ask again / request a document) closes and Outstanding becomes a read-only record.
  // A reopen re-opens it (the backend querying_locked mirrors this).
  // drift-test: halatuju-web/src/lib/__tests__/appMirrorDrift.test.ts
  const queryingLocked = isQueryingLocked(app.status, app.interview_session?.status) && !decisionReopened
  const lockReason = queryingLockReason(app.status, app.interview_session?.status)
  // Freeze model (the owner's): Save persists a draft and stays editable (re-saving
  // overwrites the same draft); Submit / recording the decision disables editing →
  // read-only. A reopen unlocks the interview again (for the assigned reviewer too).
  const interviewSubmitted = app.interview_session?.status === 'submitted'
  const interviewLocked = interviewSubmitted && !decisionReopened
  const decisionRecorded = !!app.verdict_decided_at
  // ⚠ A HALF-COMPLETED APPROVE MUST NOT LOCK THE PANEL. Saving the verdict is the FIRST of the
  // two things one Approve press does; locking on it stranded application 144 for six days with
  // no button its own reviewer could press. While the case is still waiting to be submitted, the
  // controls stay live so she can finish it herself — see `isStuckAfterVerdict`.
  const recordedOutcome = (app.officer_verdict as { overall?: string } | null)?.overall ?? null
  const stuckAfterVerdict = isStuckAfterVerdict({
    status: app.status,
    verdictDecidedAt: app.verdict_decided_at,
    verifiedAt: app.verified_at,
    outcome: recordedOutcome,
  })
  const decisionLocked = decisionRecorded && !decisionReopened && !stuckAfterVerdict

  // The interview agenda (questions): deterministic flags not already a Check-2 query +
  // AI gaps. Computed once; the editable view drops 'deleted' items, the read-only view
  // shows only the answered ones.
  const check2Owned = new Set((app.resolution_items ?? []).map((i) => i.code))
  // V3 (#9): the folded agenda entries (open carried-over queries + the needs-interview verdict
  // ambers + a standing Motivation & grit section) — so nothing raised at Check 1/2 evaporates at
  // the interview. Anomalies are still sourced from app.anomalies above (to keep the
  // ANOMALY_CHECK2_OWNER suppression), so the folded list drops kind==='anomaly'.
  const agendaEntryLabel = (e: AdminAgendaEntry): string => {
    const p = Object.fromEntries(Object.entries(e.params).map(([k, v]) => [k, String(v)]))
    if (e.kind === 'motivation') {
      return e.params.seeded
        ? t('admin.scholarship.agenda.motivation.seeded')
        : t('admin.scholarship.agenda.motivation.standing')
    }
    if (e.kind === 'needs_interview') return t(`admin.scholarship.agenda.needsInterview.${e.code}`, p)
    return t('admin.scholarship.agenda.openQuery')   // a carried-over query — confirm verbally
  }
  const agendaItems = [
    ...app.anomalies
      .filter((a) => { const o = ANOMALY_CHECK2_OWNER[a.code]; return !(o && check2Owned.has(o)) })
      .map((a) => ({
        code: a.code, ai: false,
        label: t(`admin.scholarship.anomaly.${a.code}.question`, anomalyParams(t, a.params)),   // M4b: no raw doc_seen
      })),
    ...(app.interview_agenda || [])
      .filter((e) => e.kind !== 'anomaly')
      .map((e) => ({ code: `${e.kind}:${e.code}`, ai: false, label: agendaEntryLabel(e) })),
    ...(app.interview_gaps || []).map((g) => ({ code: g.code, label: g.question, ai: true })),
  ]
  const editableAgenda = agendaItems.filter((it) => findings[it.code]?.verdict !== 'deleted')
  // The live count under Submit (case 254): the questions still unanswered in what she has typed
  // so far — the same "answered" rule the api applies at submit, read from the UNSAVED findings,
  // so she is told before she presses rather than after.
  const interviewUnansweredCount = missingAgendaItems(agendaItems.map((it) => it.code), findings).length

  // #7: Approve/Decline activate only once the reviewer has (1) submitted interview findings that
  // answer EVERY agenda item (TD-253 — read from the SAVED session, which is what the api checks),
  // (2) pressed Pass/Fail on all four facts, and (3) written a conclusion.
  // (Approve's actual accept is still backend-gated on a complete profile + identity.)
  const interviewMissing = interviewGateApplies({ status: app.status, recordedOutcome, decisionReopened })
    ? missingAgendaItems(agendaItems.map((it) => it.code), app.interview_session?.findings) : []
  const decisionReady = isDecisionReady(
    app.interview_session?.status, officerVerdict, verdictReason, interviewMissing.length === 0)
  // The bursary is fixed by pathway type and always present (award.py) — so approve just needs a
  // complete decision. hasAssistance stays in the gate for safety (award_amount or the by-type
  // figure); it is effectively always true now.
  const hasAssistance = app.award_amount != null || app.proposed_award_amount != null
  const approveReady = isApproveReady(decisionReady, hasAssistance)
  // Save (the commit) is enabled once a reversible outcome is chosen AND its preconditions hold:
  // Approve → all of approveReady (incl. amount); Decline → decisionReady (no amount needed).
  const canSave = (officerVerdict.overall === 'accept' && approveReady)
    || (officerVerdict.overall === 'decline' && decisionReady)

  return {
    vtip, decisionReopened, reviewerName, reviewerDate, hasQc, qcName, qcDate,
    queryingLocked, lockReason, interviewSubmitted, interviewLocked, decisionRecorded,
    recordedOutcome, stuckAfterVerdict, decisionLocked, agendaItems, editableAgenda,
    interviewUnansweredCount, interviewMissing, decisionReady, hasAssistance, approveReady, canSave,
  }
}
