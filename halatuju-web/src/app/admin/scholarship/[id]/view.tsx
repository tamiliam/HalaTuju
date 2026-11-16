'use client'

/**
 * THE OFFICER COCKPIT — the screen itself: the case it loads and the layout that arranges the panels.
 *
 * ⚠ THE PANELS MOVED TO `./view/` AT CODE HEALTH H14, AND NOTHING ELSE HAPPENED TO THEM. This
 * file was 3,599 lines; thirteen panel modules and one shared-furniture module now sit beside
 * it, and every moved line is byte-identical to the line it was. The FILE stayed at its own
 * path deliberately (H13's rule): `./page.tsx`, `@/sandbox/surfaces` and `@/test/renderCockpit`
 * still import `AdminScholarshipDetailView` from here, unchanged.
 *
 * ⚠ AUDIT A3.3 THEN MOVED THE STATE AND THE HANDLERS OUT TOO, by concern, with no change to them:
 * `view/useVerdict` (the decision, QC and the org reject), `view/useInterview`,
 * `view/useRequests` (queries, document requests, referees, vision), `view/usePostAward`
 * (witness, bursary, disbursement, closure) and `view/useCaseActions` (remind, cool-off, assign,
 * reporting date); what the page works out from the case is `view/deriveCockpit`. They share one
 * `CockpitCtx`. What stays here is the case itself, its load, and the layout.
 *
 * ⚠ THE DECISION / RECOMMENDATION PANEL DID NOT MOVE, AND THAT IS A RULING, NOT AN OVERSIGHT.
 * It reads thirty-five names out of this component and writes through nine handlers; the
 * roadmap's Phase 4 says untangling it is DESIGN work, not a move, so it is still drawn inline
 * below. Do not lift it out without that design.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import { useLatest } from '@/lib/useLatest'
import { useParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import { holdsDoor, mayOpen } from '@/lib/pageGuard'
import { hasPerm } from '@/lib/staffPermissions'
import { usePinProgramme } from '@/lib/programmeScopeCore'
import InterviewScheduleCard from '@/components/admin/InterviewScheduleCard'
import RecordState from '@/components/admin/RecordState'
import {
  getScholarshipApplication,
  getVerdictCaseSummary,
  type VerdictCaseSummary,
  getAssignableAdmins,
  type AdminScholarshipDetail,
  type AdminSponsorProfile,
} from '@/lib/admin-api'
import { nudgeButton } from '@/lib/blockers'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'

import { GroupLabel } from './view/shared'
import { CockpitHeader } from './view/CockpitHeader'
import { ApplicantCards, householdFigures } from './view/ApplicantCards'
import { VerificationVerdict } from './view/VerificationVerdict'
import { GeneratedProfile } from './view/GeneratedProfile'
import { OutstandingPanel } from './view/OutstandingPanel'
import { RefereesPanel, InterviewStage } from './view/InterviewPanels'
import { DocumentsDrawer } from './view/DocumentsDrawer'
import { RateAndEstimate } from './view/RateAndEstimate'
import { BlockersPanel } from './view/BlockersPanel'
import { QcPanel } from './view/QcPanel'
import { ReverifyIcCard } from './view/ReverifyIcCard'   // TD-378
import { OrgRejectPanel } from './view/OrgRejectPanel'
import { AssignAndWitness } from './view/AssignAndWitness'
import { PreInterviewOption, PreInterviewRecord } from './view/PreInterviewReject'   // request #75
import { ReviewerNotesCard } from './view/ReviewerNotesCard'
import { PostAwardPanels } from './view/PostAwardPanels'
import { WithdrawAwardCard } from './view/WithdrawAwardCard'
import { DecisionCard } from './view/DecisionCard'
import { DecisionBar, decisionBarShows } from './view/DecisionBar'
import { ConfirmSheet } from './view/ConfirmSheet'
import { deriveCockpit } from './view/deriveCockpit'
import { askCopy, useCaseActions } from './view/useCaseActions'
import { useInterview } from './view/useInterview'
import { usePostAward } from './view/usePostAward'
import { useRequests } from './view/useRequests'
import { useVerdict } from './view/useVerdict'
import type { CockpitCtx } from './view/cockpitCtx'

/**
 * ⚠ `applicationId` EXISTS SO THE SANDBOX CAN MOUNT THIS PAGE (Layer 1 F7c), and it is the only
 * concession made for it. The route supplies the id in production and always wins; the sandbox
 * lives at `/sandbox/[surface]`, where `useParams()` has no `id` at all and `Number(undefined)` is
 * NaN. The alternative was stubbing `useParams` — mocking the framework, which would mean the
 * sandbox exercised a different code path from production and could no longer prove anything.
 *
 * That is the sandbox's own rule applied: fix the component so it can be MOUNTED rather than
 * re-implementing it, and keep the concession to the one thing the route cannot provide.
 *
 * ⚠ AND IT IS A NAMED EXPORT WITH A THIN DEFAULT WRAPPER, which `next build` insisted on and no
 * other gate would have. Next type-checks a page's default export against its own `PageProps` and
 * rejects BOTH a defaulted parameter (`= {}` makes the type `… | undefined`) and any extra prop at
 * all (`OmitWithTag<…, keyof PageProps>` must be empty). So the id cannot ride on the page — the
 * component takes it, and the route hands it nothing. **The body below is untouched: this is a
 * rename plus a four-line wrapper at the end of the file, not the section extraction F5 declined.**
 * All three of `tsc --noEmit`, `jest` and `next lint` were green while this was still broken.
 */
export function AdminScholarshipDetailView({ applicationId }: { applicationId?: number }) {
  const params = useParams()
  const id = applicationId ?? Number(params?.id)
  // ⚠ ONE MOUNT PER CASE (#75 re-check 4, TD-216; wording corrected in re-check 5). In production a
  // new `[id]` already remounts this page: Next 15's layout-router keys each segment by
  // `createRouterCacheKey`, and prev/next (arrows and arrow keys) navigate to `/admin/scholarship/<id>`.
  // The `applicationId` prop (the tests, the sandbox) changes `id` in place, and there every form,
  // message and choice below carried to the next student (a half-made reject sent for case 8 with case
  // 7's reason). Keyed on the id, the case's tree starts fresh on every path, shows its loading state
  // until its own record arrives, and a reply for the case before lands on an unmounted tree: defence
  // in depth for the prop path and any future in-place navigation. The two viewing preferences live
  // out here, so an in-place change keeps them; a production route change resets them, as it always has.
  const [genLang, setGenLang] = useState('en')
  // Consolidation: the student's own words (note/story/funding) are collapsed by
  // default under the Sponsor profile — the reviewer checks the AI draft first.
  const [showOwnWords, setShowOwnWords] = useState(true)
  const prefs = { genLang, setGenLang, showOwnWords, setShowOwnWords }
  return <CaseCockpit key={id} id={id} prefs={prefs} />
}

type SetPref<T> = Dispatch<SetStateAction<T>>
function CaseCockpit({ id, prefs }: { id: number; prefs: {
  genLang: string; setGenLang: SetPref<string>; showOwnWords: boolean; setShowOwnWords: SetPref<boolean>
} }) {
  const { genLang, setGenLang, showOwnWords, setShowOwnWords } = prefs
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const isSuper = effectiveRole(role) === 'super'
  // Assignment (F7): the server's door `assign` (`students.edit`, M3c list W) — an org admin's own reviewers.
  const canAssign = holdsDoor(role, 'assign')
  // Sources / witness-org management: super + admin + org_admin (owner 2026-07-19). Distinct from
  // canAssign (reviewer assignment stays super/org_admin) — the Admin role manages sources/witness.
  // Sprint M2b (D11): on the server's door — the witness endpoint is `_SourcesBase` (door `sources`,
  // `sources.edit`), read from the served `page_keys`. TD-623: no role fallback.
  const canManageSources = holdsDoor(role, 'sources')
  // QC (2026-07): quality control acts on AWAITING-QC ('interviewed') cases — the `qc` permission
  // (#39 S3: super, a `qc`, an `org_admin`). The backend recorder guard stops anyone QC-ing
  // a verdict they themselves recorded (two-person control).
  const canQc = hasPerm(role, 'qc')
  const [app, setRawApp] = useState<AdminScholarshipDetail | null>(null)
  // ⚠ #75 re-check 3 (TD-216 class): where `id` changes in place (the prop path; production remounts on a
  // new `[id]`, see above), a request sent for the case before could land after the next one loaded.
  // Every write of `app` goes through this setter, which drops a payload for any case but the live one
  // (`liveId` is read when the update lands). Defence in depth: within one keyed mount it always passes.
  // Re-check 4 (L1): the page's own ref, set after commit, so no render that is thrown away moves it.
  const liveId = useRef(id)
  useLayoutEffect(() => { liveId.current = id }, [id])
  const isLive = useCallback((d: { id: number }) => d.id === liveId.current, [liveId])
  const setApp: CockpitCtx['setApp'] = useCallback((next) => setRawApp((prev) => {
    const d = typeof next === 'function' ? next(prev) : next
    return d && !isLive(d) ? prev : d
  }), [isLive])
  // ⚠ The crumb names THIS case's gift, from the payload — `app.programme` (the gift), never
  // `chosen_programme` (the course). A fresh tab opened from a run pins it too (2026-09-28).
  usePinProgramme(app?.programme)
  // Execute (verify/verdict/interview/etc.): SERVED, never derived here — `can_write` is the server's one
  // rule (`views_admin.base.may_write_case`, POST-AWARD-CUT: an open case is super, `qc` org-wide or the
  // assignee; past the award super or a `scholars` holder; ended before it super or a `students.approve`
  // holder). A write reply that omits it keeps the last value served; so do `can_cancel_decline` and
  // `can_tranche` (the tranche steps). drift-test: halatuju-web/src/lib/__tests__/appMirrorDrift.test.ts
  const served = useRef({ write: false, cancelDecline: false, tranche: false })
  if (typeof app?.can_write === 'boolean') served.current = { write: app.can_write, cancelDecline: app.can_cancel_decline === true, tranche: app.can_tranche === true }
  const canWrite = served.current.write, canTranche = served.current.tranche
  const [caseSummary, setCaseSummary] = useState<VerdictCaseSummary | null>(null)
  const [profile, setProfile] = useState<AdminSponsorProfile | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [viewerDoc, setViewerDoc] = useState<ViewerDoc | null>(null)   // in-cockpit doc viewer
  const [admins, setAdmins] = useState<Array<{ id: number; name: string; role: string; gifts?: Array<{ id: number }> }>>([])
  // #75 re-check: the reject-before-interview refusal lives HERE, so it survives the reload that a
  // stale refusal triggers even when that reload takes the door (and its component) away. It is
  // kept WITH its case, so it never follows to another one even where `id` changes in place (the prop
  // path; defence in depth, as the key above already starts each case afresh).
  const [preInterviewRefusal, setPreInterviewRefusal] = useState<{ appId: number; text: string } | null>(null)
  const preInterviewErr = app && preInterviewRefusal?.appId === app.id ? preInterviewRefusal.text : ''
  const setPreInterviewErr = (text: string) => setPreInterviewRefusal(text && app ? { appId: app.id, text } : null)
  // #75 re-check 3 (L-a): the page's refusal takes focus only on the reload its own refusal asked for
  // (`onStale`), for that one commit; any other reload, and a success, clears the words.
  const focusRefusal = useRef(false)
  useEffect(() => { focusRefusal.current = false })
  const focusOnArrival = useCallback((el: HTMLElement | null) => {
    if (el && focusRefusal.current) { focusRefusal.current = false; el.focus() }
  }, [])
  const reload = async (afterRefusal: boolean) => {
    if (!token) return
    const d = await getScholarshipApplication(liveId.current, { token })
    if (!isLive(d)) return   // re-check 4 (L2): a dropped payload leaves the refusal as it was
    focusRefusal.current = afterRefusal
    if (!afterRefusal) setPreInterviewRefusal(null)
    setApp(d)
  }
  const refreshApp = () => reload(false)
  const onPreInterviewDone = (next: AdminScholarshipDetail) => { setPreInterviewRefusal(null); setApp(next) }
  // The hooks' handlers keep the ctx of the render they were made in, so these drop what a request
  // for an earlier case brings back (busy is never guarded: it must always clear).
  const forThisCase = <A,>(set: (a: A) => void) => (a: A) => { if (id === liveId.current) set(a) }
  const ctx: CockpitCtx = {
    id, token, t, app, setApp, isLive, setProfile: forThisCase(setProfile), setBusy,
    setError: forThisCase(setError), refreshApp,
  }
  const verdict = useVerdict(ctx, genLang)
  const interview = useInterview(ctx)
  const requests = useRequests(ctx)
  const postAward = usePostAward(ctx, canManageSources)
  const actions = useCaseActions(ctx, admins)
  const { officerVerdict, loadVerdictState } = verdict
  const { findings, loadInterviewState } = interview
  // The load below needs the CURRENT hooks' handlers and `t`, but must fire on `token`/`id` alone: the
  // hook objects are new every render, so listing them would re-read the case on every keystroke.
  const live = useLatest({ interview, loadInterviewState, loadVerdictState, postAward, t })

  useEffect(() => {
    if (!token || !id) return
    const { interview, loadInterviewState, loadVerdictState, postAward, t } = live.current
    // ⚠ CLEAR THE INTERVIEW BOXES BEFORE FETCHING THE NEXT STUDENT (TD-216). The prev/next arrows
    // move between applicants WITHOUT remounting this page, so without this the previous student's
    // typed findings stay in state until their replacement arrives — and a save in that window
    // writes one student's interview onto another's record. The load below refills them.
    interview.setFindings({})
    interview.setRubric({})
    interview.setNote('')
    setPreInterviewRefusal(null)
    setError('')
    getScholarshipApplication(id, { token })
      .then((d) => {
        if (id !== liveId.current) return   // a later prev/next superseded this load
        setApp(d)
        setProfile(d.sponsor_profile)
        loadInterviewState(d)
        loadVerdictState(d)
        // TD-144: seed the bursary panel from the real loaded agreement so the four-party
        // ticks are accurate on first paint (the action responses refresh it after a sign).
        postAward.setBursary(d.bursary_agreement ?? null)
      })
      .catch(() => { if (id === liveId.current) setError(t('admin.scholarship.loadFailed')) })
    getAssignableAdmins({ token }).then((r) => setAdmins(r.admins)).catch(() => {})
    // Check-2 case summary — fetched lazily (in parallel), server-cached; dark-flag aware.
    getVerdictCaseSummary(id, { token })
      .then((s) => { if (id === liveId.current) setCaseSummary(s) }).catch(() => {})
  }, [token, id, live, liveId, setApp])

  // Re-check 4: nothing is drawn against a record that is not this case's (the key makes it so).
  if (!app || app.id !== id) return <RecordState loading={!error} />

  const d = deriveCockpit(app, t, findings, officerVerdict, verdict.verdictReason)
  const { vtip, decisionReopened, decisionLocked, decisionRecorded } = d
  // Household income + size (request #54: the declared figures, ticked on a document match).
  const household = householdFigures(app, t)
  const q = actions.ask ? askCopy(actions.ask, nudgeButton(app.nudge, true).label) : null
  const {
    verdictReason, setVerdictReason, verdictMsg, verdictMsgTone, reopenOpen, setReopenOpen,
    reopenReason, setReopenReason, qcReopenOpen, setQcReopenOpen, qcComments, setQcComments,
    qcRejectMode, setQcRejectMode, qcOverrideOpen, setQcOverrideOpen, qcOverrideReason,
    setQcOverrideReason, rejectStep, setRejectStep, rejectComments, setRejectComments, rejectErr,
    closeReject, doReject, doOrgReject, selectApprove, selectDecline, doSave, doReopenDecision,
    doCancelReopen, doQcDecision, setOfficerVerdict,
  } = verdict
  const {
    note, setNote, setFindings, interviewMsg, interviewError, doSuggestGaps,
    doSaveInterview, doSubmitInterview, doReopenInterview, doDeleteAgendaItem,
  } = interview
  const {
    requestError, refForm, setRefForm, infoNote, setInfoNote, reqCategory, reqQualifier, reqDocNote,
    setReqDocNote, reqResolved, onReqCategory, onReqQualifier, doRaiseQuery, doRequestDoc,
    doActionResolution, doAddReferee, doDeleteReferee, doReRunVision,
  } = requests
  const {
    nudgeMsg, doNudge, doCancelDecline, doHoldAward, reportingDateInput, setReportingDateInput,
    reportingDateMsg, doSetReportingDate, doAssign,
  } = actions
  const {
    reviewerName, reviewerDate, hasQc, qcName, qcDate, queryingLocked, lockReason, interviewSubmitted,
    interviewLocked, recordedOutcome, stuckAfterVerdict, agendaItems, editableAgenda,
    interviewUnansweredCount, interviewMissing, decisionReady, hasAssistance, approveReady, canSave,
  } = d
  const {
    bursary, bursaryMsg, doCountersignBursary, doWitnessBursary, witnessCardVisible, activeSources,
    witnessSel, setWitnessSel, witnessBusy, witnessMsg, setWitnessMsg, witnessEditing,
    setWitnessEditing, doAssignWitness, disbAmount, setDisbAmount, disbLabel, setDisbLabel, disbMsg,
    doScheduleTranche, doDisbursementAction, doSetSubstate, closeReason, setCloseReason, closeMsg,
    doClose,
  } = postAward
  return (
    <div className="space-y-4 pb-10">
      <DocViewer doc={viewerDoc} onClose={() => setViewerDoc(null)} />
      {q && (
        <ConfirmSheet
          t={t} title={t(q.title)} question={t(q.question)} confirmLabel={t(q.title)}
          busy={!!busy} dismissible={q.dismissible}
          onCancel={() => actions.setAsk(null)} onConfirm={actions.confirmAsk}
        />
      )}
      <CockpitHeader
        app={app} t={t} vtip={vtip} busy={busy} canWrite={canWrite} canCancelDecline={served.current.cancelDecline}
        doCancelDecline={doCancelDecline} doHoldAward={doHoldAward}
      />


      <ApplicantCards
        app={app} t={t} vtip={vtip} {...household}
        canCorrectGuardian={canAssign} onGuardianCorrected={refreshApp}
      />


      {/* Review & actions — interactive panels. Hidden only for PRE-shortlist
          rejections (merit/need/ineligible): those applicants were declined by the
          engine before any human review, so documents/verify/interview/profile are
          irrelevant. Post-shortlist rejections (interview/contractual) KEEP the
          panel so the documents + interview record that justified the decision stay
          visible. The summary cards above always show. */}
      {!(app.status === 'rejected' && ['merit', 'need', 'ineligible'].includes(app.rejection_category)) && (<>
      <GroupLabel>{t('admin.scholarship.reviewActions')}</GroupLabel>

      {/* ── COCKPIT: two-column layout — left (wider) + right sticky ───────────── */}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">

      {/* ═══════════════════════ LEFT COLUMN ═══════════════════════════════════ */}
      {/* min-w-0 (via minmax(0,1fr) above + here): long verdict text must not stop
          the column shrinking, or it pushes the 340px Record panel off-screen. */}
      <div className="space-y-4 min-w-0">

      <VerificationVerdict app={app} t={t} caseSummary={caseSummary} />


      <GeneratedProfile
        app={app} t={t} profile={profile} genLang={genLang} setGenLang={setGenLang}
        busy={busy} error={error} decisionReopened={decisionReopened}
        showOwnWords={showOwnWords} setShowOwnWords={setShowOwnWords}
      />


      <OutstandingPanel
        app={app} t={t} busy={busy} canWrite={canWrite} decisionReopened={decisionReopened}
        queryingLocked={queryingLocked} lockReason={lockReason}
        infoNote={infoNote} setInfoNote={setInfoNote} doRaiseQuery={doRaiseQuery}
        doActionResolution={doActionResolution}
        reqCategory={reqCategory} reqQualifier={reqQualifier} reqDocNote={reqDocNote}
        setReqDocNote={setReqDocNote} reqResolved={reqResolved}
        onReqCategory={onReqCategory} onReqQualifier={onReqQualifier} doRequestDoc={doRequestDoc}
        requestError={requestError}
      />


      <RefereesPanel
        app={app} t={t} busy={busy} refForm={refForm} setRefForm={setRefForm}
        doAddReferee={doAddReferee} doDeleteReferee={doDeleteReferee}
      />


      {/* Interview scheduling — the assigned reviewer proposes times (dark behind the flag) */}
      {app.interview_schedule?.enabled && app.assigned_to_id != null &&
        ['profile_complete', 'interviewing'].includes(app.status) && (
        <InterviewScheduleCard
          appId={id} token={token || ''} schedule={app.interview_schedule}
          onChange={(s) => setApp((prev) => (prev?.id === app.id ? { ...prev, interview_schedule: s } : prev))}
        />
      )}

      <InterviewStage
        app={app} t={t} busy={busy} canWrite={canWrite}
        decisionReopened={decisionReopened} decisionRecorded={decisionRecorded}
        interviewLocked={interviewLocked} interviewMsg={interviewMsg}
        interviewError={interviewError} interviewUnansweredCount={interviewUnansweredCount}
        agendaItems={agendaItems} editableAgenda={editableAgenda}
        findings={findings} setFindings={setFindings} note={note} setNote={setNote}
        doSuggestGaps={doSuggestGaps} doReopenInterview={doReopenInterview}
        doDeleteAgendaItem={doDeleteAgendaItem}
        doSaveInterview={doSaveInterview} doSubmitInterview={doSubmitInterview}
      />



      <DocumentsDrawer
        app={app} t={t} busy={busy} canWrite={canWrite} setViewerDoc={setViewerDoc} doReRunVision={doReRunVision}
      />


      </div>{/* end LEFT column */}

      {/* ═══════════════════════ RIGHT COLUMN (sticky) ══════════════════════════ */}
      <div id="record-verdict-panel" className="space-y-4 lg:sticky lg:top-4">

      <RateAndEstimate
        app={app} t={t} busy={busy} canWrite={canWrite}
        decisionReopened={decisionReopened} decisionRecorded={decisionRecorded}
        decisionLocked={decisionLocked}
        officerVerdict={officerVerdict} setOfficerVerdict={setOfficerVerdict}
        reportingDateInput={reportingDateInput} setReportingDateInput={setReportingDateInput}
        reportingDateMsg={reportingDateMsg} doSetReportingDate={doSetReportingDate}
      />


      <DecisionCard
        app={app} t={t} busy={busy} canWrite={canWrite} isSuper={isSuper} error={error}
        decisionLocked={decisionLocked} decisionReopened={decisionReopened} decisionRecorded={decisionRecorded}
        reopenOpen={reopenOpen} setReopenOpen={setReopenOpen} reopenReason={reopenReason}
        setReopenReason={setReopenReason} doReopenDecision={doReopenDecision} doCancelReopen={doCancelReopen}
        doCancelDecline={doCancelDecline} verdictReason={verdictReason} setVerdictReason={setVerdictReason}
        reviewerName={reviewerName} reviewerDate={reviewerDate} hasQc={hasQc} qcName={qcName} qcDate={qcDate}
        recordedOutcome={recordedOutcome} doReject={doReject} stuckAfterVerdict={stuckAfterVerdict}
        officerVerdict={officerVerdict} selectApprove={selectApprove} selectDecline={selectDecline}
        approveReady={approveReady} decisionReady={decisionReady} interviewSubmitted={interviewSubmitted}
        interviewMissing={interviewMissing} hasAssistance={hasAssistance} doSave={doSave} canSave={canSave}
        verdictMsg={verdictMsg} verdictMsgTone={verdictMsgTone}
      />

      <BlockersPanel
        app={app} t={t} busy={busy} isSuper={isSuper} role={role}
        nudgeMsg={nudgeMsg} doNudge={doNudge}
      />


      <ReverifyIcCard app={app} t={t} token={token} busy={busy} canQc={canQc} onDone={(a) => { setApp(a); loadVerdictState(a) }} />
      <QcPanel
        app={app} t={t} busy={busy} canQc={canQc} role={role} doQcDecision={doQcDecision}
        qcReopenOpen={qcReopenOpen} setQcReopenOpen={setQcReopenOpen}
        qcComments={qcComments} setQcComments={setQcComments}
        qcRejectMode={qcRejectMode} setQcRejectMode={setQcRejectMode}
        qcOverrideOpen={qcOverrideOpen} setQcOverrideOpen={setQcOverrideOpen}
        qcOverrideReason={qcOverrideReason} setQcOverrideReason={setQcOverrideReason}
      />


      <OrgRejectPanel
        app={app} t={t} busy={busy} role={role}
        rejectStep={rejectStep} setRejectStep={setRejectStep}
        rejectComments={rejectComments} setRejectComments={setRejectComments}
        rejectErr={rejectErr} closeReject={closeReject} doOrgReject={doOrgReject}
      />
      <PreInterviewRecord app={app} t={t} />
      {preInterviewErr && !app.pre_interview && (
        <p className="text-sm text-critical-600" role="alert" data-testid="pre-interview-refused"
          tabIndex={-1} ref={focusOnArrival}>{preInterviewErr}</p>
      )}


      <AssignAndWitness
        app={app} t={t} busy={busy} isSuper={isSuper} canAssign={canAssign}
        decisionLocked={decisionLocked} admins={admins} doAssign={doAssign}
        witnessCardVisible={witnessCardVisible} activeSources={activeSources}
        witnessSel={witnessSel} setWitnessSel={setWitnessSel}
        witnessBusy={witnessBusy} witnessMsg={witnessMsg} setWitnessMsg={setWitnessMsg}
        witnessEditing={witnessEditing} setWitnessEditing={setWitnessEditing}
        doAssignWitness={doAssignWitness}
        notesCard={<ReviewerNotesCard appId={app.id} token={token} t={t}
          refreshKey={`${app.status}|${app.verdict_decided_at ?? ''}|${app.decision_reopened_at ?? ''}`} />}
        preInterview={<PreInterviewOption key={app.id} app={app} t={t} token={token} busy={busy} canAssign={canAssign}
          err={preInterviewErr} setErr={setPreInterviewErr} onDone={onPreInterviewDone} onStale={() => reload(true)} />}
      />


      </div>{/* end RIGHT column */}

      </div>{/* end cockpit grid */}

      <PostAwardPanels
        app={app} t={t} busy={busy} isSuper={isSuper} canWrite={canWrite} canTranche={canTranche} orgSuper={holdsDoor(role, 'decide')} mayOpenFile={mayOpen('/admin/scholars', role)}
        bursary={bursary} bursaryMsg={bursaryMsg}
        doCountersignBursary={doCountersignBursary} doWitnessBursary={doWitnessBursary}
        disbAmount={disbAmount} setDisbAmount={setDisbAmount}
        disbLabel={disbLabel} setDisbLabel={setDisbLabel} disbMsg={disbMsg}
        doScheduleTranche={doScheduleTranche} doDisbursementAction={doDisbursementAction}
        doSetSubstate={doSetSubstate}
        closeReason={closeReason} setCloseReason={setCloseReason}
        closeMsg={closeMsg} doClose={doClose}
      />
      <WithdrawAwardCard app={app} t={t} token={token} onChanged={setApp} />

      {/* Mobile M6b: a phone's way back to the decision. It jumps; it never saves (see DecisionBar). */}
      {decisionBarShows({ app, decisionReopened, decisionRecorded, decisionLocked, canWrite }) && (
        <DecisionBar t={t} outcome={officerVerdict.overall} canSave={canSave && !busy} />
      )}
      </>)}
    </div>
  )
}

