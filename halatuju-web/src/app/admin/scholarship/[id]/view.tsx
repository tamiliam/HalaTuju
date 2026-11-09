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
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
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
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const isSuper = effectiveRole(role) === 'super'
  // Assignment (F7) is a super or org_admin power — an org_admin assigns their own org's reviewers.
  const canAssign = isSuper || role?.role === 'org_admin'
  // Sources / witness-org management: super + admin + org_admin (owner 2026-07-19). Distinct from
  // canAssign (reviewer assignment stays super/org_admin) — the Admin role manages sources/witness.
  const canManageSources = isSuper || role?.role === 'org_admin' || role?.role === 'admin'
  // QC (2026-07): quality control acts on AWAITING-QC ('interviewed') cases — the `qc` permission
  // (#39 S3: super, a `qc`, an `org_admin`). The backend recorder guard stops anyone QC-ing
  // a verdict they themselves recorded (two-person control).
  const canQc = hasPerm(role, 'qc')
  const [app, setApp] = useState<AdminScholarshipDetail | null>(null)
  // ⚠ The crumb names THIS case's gift, from the payload — `app.programme` (the gift), never
  // `chosen_programme` (the course). A fresh tab opened from a run pins it too (2026-09-28).
  usePinProgramme(app?.programme)
  // Execute (verify/verdict/interview/etc.): super acts on any application; org_admin + qc (the
  // `qc` holders, #39 S3) act on any OWN-ORG application (the detail GET already 404s cross-org);
  // everyone else acts ONLY on applications assigned to them (mirrors backend _can_review_app).
  const canWrite = hasPerm(role, 'qc')
    || (app?.assigned_to_id != null && app.assigned_to_id === (role?.admin_id ?? null))
  const [caseSummary, setCaseSummary] = useState<VerdictCaseSummary | null>(null)
  const [profile, setProfile] = useState<AdminSponsorProfile | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [viewerDoc, setViewerDoc] = useState<ViewerDoc | null>(null)   // in-cockpit doc viewer
  const [genLang, setGenLang] = useState('en')
  const [admins, setAdmins] = useState<Array<{ id: number; name: string; role: string; gifts?: Array<{ id: number }> }>>([])
  // Consolidation: the student's own words (note/story/funding) are collapsed by
  // default under the Sponsor profile — the reviewer checks the AI draft first.
  const [showOwnWords, setShowOwnWords] = useState(true)

  const refreshApp = async () => {
    if (!token) return
    setApp(await getScholarshipApplication(id, { token }))
  }
  const ctx: CockpitCtx = { id, token, t, app, setApp, setProfile, setBusy, setError, refreshApp }
  const verdict = useVerdict(ctx, genLang)
  const interview = useInterview(ctx)
  const requests = useRequests(ctx)
  const postAward = usePostAward(ctx, canManageSources)
  const actions = useCaseActions(ctx)
  const { officerVerdict, loadVerdictState } = verdict
  const { findings, loadInterviewState } = interview

  useEffect(() => {
    if (!token || !id) return
    // ⚠ CLEAR THE INTERVIEW BOXES BEFORE FETCHING THE NEXT STUDENT (TD-216). The prev/next arrows
    // move between applicants WITHOUT remounting this page, so without this the previous student's
    // typed findings stay in state until their replacement arrives — and a save in that window
    // writes one student's interview onto another's record. The load below refills them.
    interview.setFindings({})
    interview.setRubric({})
    interview.setNote('')
    getScholarshipApplication(id, { token })
      .then((d) => {
        setApp(d)
        setProfile(d.sponsor_profile)
        loadInterviewState(d)
        loadVerdictState(d)
        // TD-144: seed the bursary panel from the real loaded agreement so the four-party
        // ticks are accurate on first paint (the action responses refresh it after a sign).
        postAward.setBursary(d.bursary_agreement ?? null)
      })
      .catch(() => setError(t('admin.scholarship.loadFailed')))
    getAssignableAdmins({ token }).then((r) => setAdmins(r.admins)).catch(() => {})
    // Check-2 case summary — fetched lazily (in parallel), server-cached; dark-flag aware.
    getVerdictCaseSummary(id, { token }).then(setCaseSummary).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  if (!app) return <RecordState loading={!error} />

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
        app={app} t={t} vtip={vtip} busy={busy} canWrite={canWrite}
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
          onChange={(s) => setApp((prev) => (prev ? { ...prev, interview_schedule: s } : prev))}
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
        app={app} t={t} busy={busy} setViewerDoc={setViewerDoc} doReRunVision={doReRunVision}
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
        app={app} t={t} busy={busy} isSuper={isSuper} role={role}
        rejectStep={rejectStep} setRejectStep={setRejectStep}
        rejectComments={rejectComments} setRejectComments={setRejectComments}
        rejectErr={rejectErr} closeReject={closeReject} doOrgReject={doOrgReject}
      />


      <AssignAndWitness
        app={app} t={t} busy={busy} isSuper={isSuper} canAssign={canAssign}
        decisionLocked={decisionLocked} admins={admins} doAssign={doAssign}
        witnessCardVisible={witnessCardVisible} activeSources={activeSources}
        witnessSel={witnessSel} setWitnessSel={setWitnessSel}
        witnessBusy={witnessBusy} witnessMsg={witnessMsg} setWitnessMsg={setWitnessMsg}
        witnessEditing={witnessEditing} setWitnessEditing={setWitnessEditing}
        doAssignWitness={doAssignWitness}
        notesCard={<ReviewerNotesCard appId={app.id} token={token} t={t} isWriter={canAssign}
          refreshKey={`${app.status}|${app.verdict_decided_at ?? ''}|${app.decision_reopened_at ?? ''}`} />}
      />


      </div>{/* end RIGHT column */}

      </div>{/* end cockpit grid */}

      <PostAwardPanels
        app={app} t={t} busy={busy} isSuper={isSuper} canWrite={canWrite} orgSuper={canAssign}
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

