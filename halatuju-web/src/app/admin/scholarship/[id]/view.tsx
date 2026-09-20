'use client'

/**
 * THE OFFICER COCKPIT — the screen itself: its state, the actions an officer can take, and the
 * layout that arranges the panels.
 *
 * ⚠ THE PANELS MOVED TO `./view/` AT CODE HEALTH H14, AND NOTHING ELSE HAPPENED TO THEM. This
 * file was 3,599 lines; thirteen panel modules and one shared-furniture module now sit beside
 * it, and every moved line is byte-identical to the line it was. The FILE stayed at its own
 * path deliberately (H13's rule): `./page.tsx`, `@/sandbox/surfaces` and `@/test/renderCockpit`
 * still import `AdminScholarshipDetailView` from here, unchanged, and the oversize ledger's key
 * still names a real file.
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
import InterviewScheduleCard from '@/components/admin/InterviewScheduleCard'
import { formatNric } from '@/lib/scholarship'
import { isValidPhone } from '@/lib/scholarship'
import { fieldVerifications, type VerifiableField } from '@/lib/fieldVerification'
import {
  getScholarshipApplication,
  getVerdictCaseSummary,
  type VerdictCaseSummary,
  suggestInterviewGaps,
  verifyAcceptApplication,
  rejectApplication,
  submitDeclineApplication,
  cancelPendingDecline,
  holdPendingAward,
  addReferee,
  deleteReferee,
  reRunVision,
  assignApplication,
  orgRejectApplication,
  nudgeStudent,
  setReportingDate,
  saveInterview,
  submitInterview,
  reopenInterview,
  getAssignableAdmins,
  recordVerdict,
  reopenDecision,
  cancelReopen,
  recordQcDecision,
  raiseResolutionItem,
  actionResolutionItem,
  adminCountersignBursary,
  adminWitnessBursary,
  getSources,
  assignWitness,
  type SourceItem,
  scheduleTranche,
  actOnDisbursement,
  setMaintenanceSubstate,
  closeApplication,
  type DisbursementAction,
  type MaintenanceSubstate,
  type ClosureReason,
  type AdminScholarshipDetail,
  type AdminSponsorProfile,
  type AdminAgendaEntry,
} from '@/lib/admin-api'
import {
  isClearAccept,
  isStuckAfterVerdict,
  verdictSaveOutcome,
  isQcAccepted,
  isQueryingLocked,
  isDecisionReady,
  isApproveReady,
  queryingLockReason,
  rejectionTrail,
  showsDecisionCards,
  showsWitnessCard,
} from '@/lib/officerCockpit'
import { docTypeToRequestFact } from '@/lib/docCategory'
import { formatDate } from '@/lib/formatDate'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import { nextSequence } from '@/lib/disbursement'
import type { BursaryAgreement } from '@/lib/api'

import {
  GroupLabel,
  QcOverrideNote,
  EMPTY_REFEREE,
  ANOMALY_CHECK2_OWNER,
  NON_PARENT_RELATIONSHIPS,
  resolveReq,
} from './view/shared'
import { CockpitHeader } from './view/CockpitHeader'
import { ApplicantCards } from './view/ApplicantCards'
import { VerificationVerdict } from './view/VerificationVerdict'
import { GeneratedProfile } from './view/GeneratedProfile'
import { OutstandingPanel } from './view/OutstandingPanel'
import { RefereesPanel, InterviewStage } from './view/InterviewPanels'
import { DocumentsDrawer } from './view/DocumentsDrawer'
import { RateAndEstimate } from './view/RateAndEstimate'
import { BlockersPanel } from './view/BlockersPanel'
import { QcPanel } from './view/QcPanel'
import { OrgRejectPanel } from './view/OrgRejectPanel'
import { AssignAndWitness } from './view/AssignAndWitness'
import { PostAwardPanels } from './view/PostAwardPanels'


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
  // QC (2026-07): quality control acts on AWAITING-QC ('interviewed') cases — super, a `qc`, or
  // an `org_admin` (the organisation superadmin). The backend recorder guard stops anyone QC-ing
  // a verdict they themselves recorded (two-person control).
  const canQc = isSuper || role?.role === 'qc' || role?.role === 'org_admin'
  const [app, setApp] = useState<AdminScholarshipDetail | null>(null)
  // Execute (verify/verdict/interview/etc.): super acts on any application; org_admin + qc (the
  // org-wide roles) act on any OWN-ORG application (the detail GET already 404s cross-org);
  // admin/reviewer act ONLY on applications assigned to them (mirrors backend _can_review_app).
  const canWrite = isSuper || role?.role === 'org_admin' || role?.role === 'qc'
    || (app?.assigned_to_id != null && app.assigned_to_id === (role?.admin_id ?? null))
  const [caseSummary, setCaseSummary] = useState<VerdictCaseSummary | null>(null)
  const [profile, setProfile] = useState<AdminSponsorProfile | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [viewerDoc, setViewerDoc] = useState<ViewerDoc | null>(null)   // in-cockpit doc viewer
  const [refForm, setRefForm] = useState({ ...EMPTY_REFEREE })
  const [genLang, setGenLang] = useState('en')
  // #7 prev/next: the ordered id list the list page last rendered (current filters).
  // Read once from sessionStorage; if this id isn't in it (e.g. a direct link), nav hides.
  const [navIds, setNavIds] = useState<number[]>([])
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem('halatuju_admin_scholarship_nav')
      if (raw) setNavIds(JSON.parse(raw))
    } catch { /* sessionStorage unavailable — nav just won't show */ }
  }, [])
  const navIdx = navIds.indexOf(id)
  const prevId = navIdx > 0 ? navIds[navIdx - 1] : null
  const nextId = navIdx >= 0 && navIdx < navIds.length - 1 ? navIds[navIdx + 1] : null
  // Phase C
  const [admins, setAdmins] = useState<Array<{ id: number; name: string; role: string }>>([])
  const [findings, setFindings] = useState<Record<string, { verdict: string; rationale: string }>>({})
  const [rubric, setRubric] = useState<Record<string, number>>({})
  const [note, setNote] = useState('')
  const [infoNote, setInfoNote] = useState('')
  const [reqCategory, setReqCategory] = useState('')
  const [reqQualifier, setReqQualifier] = useState('')   // the 'whose' member OR the 'which' sub-value
  const [reqDocNote, setReqDocNote] = useState('')
  // Sprint 5 — Officer cockpit
  const [officerVerdict, setOfficerVerdict] = useState<Record<string, string>>({})
  const [verdictReason, setVerdictReason] = useState('')
  const [verdictMsg, setVerdictMsg] = useState('')
  const [verdictMsgTone, setVerdictMsgTone] = useState<'ok' | 'warn'>('ok')
  const [interviewMsg, setInterviewMsg] = useState('')   // transient "Saved ✓" confirmation
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
  // Consolidation: the student's own words (note/story/funding) are collapsed by
  // default under the Sponsor profile — the reviewer checks the AI draft first.
  const [showOwnWords, setShowOwnWords] = useState(true)
  // Conditional Bursary Award Agreement (flag-gated, dark by default). The admin
  // detail GET does not carry the agreement, so the card's state is populated by
  // the countersign/witness action responses (each returns the full agreement).
  const [bursary, setBursary] = useState<BursaryAgreement | null>(null)
  const [bursaryMsg, setBursaryMsg] = useState('')

  // Witness-organisation assignment (go-live transition, T2). Shown for a SOURCELESS student
  // (no referred_by_org) so a super/org_admin can assign a witness org — usable BEFORE the flag
  // flips (runbook step 2 precedes the flip), so it is NOT gated behind bursary_agreement_enabled.
  const [activeSources, setActiveSources] = useState<SourceItem[]>([])
  const [witnessSel, setWitnessSel] = useState<string>('')
  const [witnessBusy, setWitnessBusy] = useState(false)
  const [witnessMsg, setWitnessMsg] = useState('')
  // Once a witness org is on file the card SETTLES (names the org, no dropdown) — the assign
  // copy would otherwise keep asking for something already done (owner 2026-07-25). Reassigning
  // is still one click away: "Change" flips this back to the picker.
  const [witnessEditing, setWitnessEditing] = useState(false)
  const sourceless = !!app && !app.referred_by_org
  // Only fetch the organisation list when the witness card can actually render — same three
  // gates as the card itself, so a pre-QC or off-ramp case makes no needless request (most
  // sourceless students today are at 'shortlisted', where the card never appears).
  const witnessCardVisible = canManageSources && sourceless && showsWitnessCard(app?.status)
  useEffect(() => {
    if (!token || !witnessCardVisible) return
    getSources({ token }).then((d) => setActiveSources(d.sources.filter((s) => s.show_in_apply && s.is_active))).catch(() => {})
  }, [token, witnessCardVisible])
  useEffect(() => { setWitnessSel(app?.witness_org?.code || '') }, [app?.witness_org?.code])

  const doAssignWitness = async () => {
    if (!token || !app) return
    setWitnessBusy(true); setWitnessMsg('')
    try {
      const res = await assignWitness(id, witnessSel || null, { token })
      setApp({ ...app, witness_org: res.witness_org ? { id: 0, code: res.witness_org, name: res.witness_org_name || res.witness_org } : null })
      setWitnessMsg(t('admin.sources.witness.assigned'))
      setWitnessEditing(false)   // settle back to the named-org state
    } catch {
      setWitnessMsg(t('admin.actionFailed'))
    } finally { setWitnessBusy(false) }
  }

  const doCountersignBursary = async () => {
    if (!token) return
    setBusy('bursary'); setBursaryMsg('')
    try {
      setBursary(await adminCountersignBursary(id, { token }))
    } catch (e) {
      setBursaryMsg(t('admin.scholarship.bursary.actionError'))
    } finally { setBusy('') }
  }

  const doWitnessBursary = async () => {
    if (!token) return
    setBusy('bursary'); setBursaryMsg('')
    try {
      setBursary(await adminWitnessBursary(id, undefined, { token }))
    } catch (e) {
      const status = (e as Error & { status?: number }).status
      setBursaryMsg(status === 403
        ? t('admin.scholarship.bursary.witnessForbidden')
        : t('admin.scholarship.bursary.actionError'))
    } finally { setBusy('') }
  }

  // Post-award S4: disbursement (tranche) ledger.
  const [disbAmount, setDisbAmount] = useState('')
  const [disbLabel, setDisbLabel] = useState('')
  const [disbMsg, setDisbMsg] = useState('')

  // The backend raises a machine code as the Error message (adminMutate throws new Error(body.error)).
  const DISB_CODES = new Set(['bad_amount', 'not_in_programme', 'bad_state', 'bad_action', 'bad_sequence', 'on_hold', 'not_in_maintenance', 'bad_substate'])
  const disbError = (e: unknown) => {
    const code = (e as Error)?.message
    return t(`admin.disbursement.error.${code && DISB_CODES.has(code) ? code : 'generic'}`)
  }

  const doScheduleTranche = async () => {
    if (!token) return
    const amount = parseFloat(disbAmount)
    if (!amount || amount <= 0) { setDisbMsg(t('admin.disbursement.error.bad_amount')); return }
    setBusy('disbursement'); setDisbMsg('')
    try {
      const seq = nextSequence(app?.disbursements ?? [])
      setApp(await scheduleTranche(id, { amount, sequence: seq, label: disbLabel.trim() }, { token }))
      setDisbAmount(''); setDisbLabel('')
    } catch (e) {
      setDisbMsg(disbError(e))
    } finally { setBusy('') }
  }

  const doDisbursementAction = async (disbursementId: number, action: DisbursementAction) => {
    if (!token) return
    setBusy('disbursement'); setDisbMsg('')
    try {
      setApp(await actOnDisbursement(disbursementId, action, undefined, { token }))
    } catch (e) {
      setDisbMsg(disbError(e))
    } finally { setBusy('') }
  }

  // Post-award S5: maintenance sub-state (on_track / probation / on_hold / ready_to_close).
  const doSetSubstate = async (substate: MaintenanceSubstate) => {
    if (!token) return
    setBusy('disbursement'); setDisbMsg('')
    try {
      setApp(await setMaintenanceSubstate(id, substate, { token }))
    } catch (e) {
      setDisbMsg(disbError(e))
    } finally { setBusy('') }
  }

  // Post-award S6: manual closure.
  const [closeReason, setCloseReason] = useState<ClosureReason | ''>('')
  const [closeMsg, setCloseMsg] = useState('')
  const doClose = async () => {
    if (!token || !closeReason) return
    setBusy('close'); setCloseMsg('')
    try {
      setApp(await closeApplication(id, closeReason, { token }))
      setCloseReason('')
    } catch (e) {
      const code = (e as Error)?.message
      setCloseMsg(t(`admin.closure.error.${code === 'bad_reason' || code === 'not_closeable' ? code : 'generic'}`))
    } finally { setBusy('') }
  }

  const loadInterviewState = (d: AdminScholarshipDetail) => {
    const s = d.interview_session
    setFindings(s?.findings ?? {})
    setRubric(s?.rubric ?? {})
    setNote(s?.overall_note ?? '')
  }

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

  useEffect(() => {
    if (!token || !id) return
    // ⚠ CLEAR THE INTERVIEW BOXES BEFORE FETCHING THE NEXT STUDENT (TD-216). The prev/next arrows
    // move between applicants WITHOUT remounting this page, so without this the previous student's
    // typed findings stay in state until their replacement arrives — and a save in that window
    // writes one student's interview onto another's record. The load below refills them.
    setFindings({})
    setRubric({})
    setNote('')
    getScholarshipApplication(id, { token })
      .then((d) => {
        setApp(d)
        setProfile(d.sponsor_profile)
        loadInterviewState(d)
        loadVerdictState(d)
        // TD-144: seed the bursary panel from the real loaded agreement so the four-party
        // ticks are accurate on first paint (the action responses refresh it after a sign).
        setBursary(d.bursary_agreement ?? null)
      })
      .catch(() => setError(t('admin.scholarship.loadFailed')))
    getAssignableAdmins({ token }).then((r) => setAdmins(r.admins)).catch(() => {})
    // Check-2 case summary — fetched lazily (in parallel), server-cached; dark-flag aware.
    getVerdictCaseSummary(id, { token }).then(setCaseSummary).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

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

  const doReject = async (category: 'interview' | 'contractual') => {
    if (!token) return
    const confirmKey = category === 'contractual'
      ? 'admin.scholarship.reject.confirmContractual' : 'admin.scholarship.reject.confirmReview'
    if (!window.confirm(t(confirmKey))) return
    setBusy('reject'); setError('')
    try {
      setApp(await rejectApplication(id, category, { token }))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.reject.error'))
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

  // "You haven't submitted yet" reminder — org-admin manual re-send (the auto nudge fires once,
  // ~30 min after consent; this is the human follow-up). Confirms first, then refreshes the
  // nudge state (new sent_at + cooldown) from the returned detail.
  const [nudgeMsg, setNudgeMsg] = useState('')
  const doNudge = async () => {
    if (!token || !window.confirm(t('admin.scholarship.blockers.nudge.confirm'))) return
    setBusy('nudge'); setNudgeMsg('')
    try {
      setApp(await nudgeStudent(id, { token }))
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
  const doCancelDecline = async () => {
    if (!token || !window.confirm(t('admin.scholarship.cooloff.cancelConfirm'))) return
    setBusy('cooloff'); setError('')
    try { setApp(await cancelPendingDecline(id, { token })) }
    catch { setError(t('admin.scholarship.cooloff.error')) } finally { setBusy('') }
  }
  const doHoldAward = async () => {
    if (!token || !window.confirm(t('admin.scholarship.cooloff.holdConfirm'))) return
    setBusy('cooloff'); setError('')
    try { setApp(await holdPendingAward(id, { token })) }
    catch { setError(t('admin.scholarship.cooloff.error')) } finally { setBusy('') }
  }

  const doAssign = async (adminId: number | null) => {
    if (!token) return
    setBusy('assign'); setError('')
    try { setApp(await assignApplication(id, adminId, { token })) }
    catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['not_ready', 'not_reviewer', 'reviewer_paused', 'bad_assignee',
                     'findings_submitted']
      setError(known.includes(code)
        ? t(`admin.scholarship.assign.error.${code}`)
        : t('admin.scholarship.assignError'))
    } finally { setBusy('') }
  }

  const doSaveInterview = async () => {
    if (!token) return
    setBusy('iv'); setError(''); setInterviewMsg('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      await refreshApp()
      // Save confidence: an explicit "Saved ✓" so the reviewer knows it persisted
      // (the draft is still editable; re-saving overwrites it, until Submit).
      setInterviewMsg(t('admin.scholarship.interview.saved'))
      setTimeout(() => setInterviewMsg(''), 4000)
    } catch { setError(t('admin.scholarship.interview.saveError')) } finally { setBusy('') }
  }

  const doSubmitInterview = async () => {
    if (!token) return
    setBusy('ivs'); setError(''); setInterviewMsg('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      const d = await submitInterview(id, { token })
      setApp(d); loadInterviewState(d)   // freeze to the read-only view
    } catch { setError(t('admin.scholarship.interview.submitError')) } finally { setBusy('') }
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

  const doRecordVerdict = async (finalise: boolean, accept = false) => {
    if (!token) return
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
          setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError'))
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
          // The ONLY truly-complete outcome: verdict recorded AND final profile generated.
          setVerdictMsg(t('admin.scholarship.recordVerdict.finaliseOk')); setVerdictMsgTone('ok')
        } else {
          // Saved, but NOT finalised — work is incomplete. Amber, not green.
          setVerdictMsg(fr?.code === 'no_interview'
            ? t('admin.scholarship.recordVerdict.finaliseNoInterview')
            : t('admin.scholarship.recordVerdict.finaliseNoDraft'))
          setVerdictMsgTone('warn')
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError'))
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
      await doRecordVerdict(false, false)
      if (app?.status === 'recommended') {
        await doReject('contractual')
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
      setError(code === 'self_verdict_qc_forbidden'
        ? t('admin.scholarship.qcDecision.selfVerdictForbidden')
        : e instanceof Error ? e.message : t('admin.scholarship.qcDecision.error'))
    } finally { setBusy('') }
  }

  const doRaiseQuery = async () => {
    if (!token || !infoNote.trim()) return
    setBusy('raise'); setError('')
    try {
      setApp(await raiseResolutionItem(id, { kind: 'explanation', prompt: infoNote.trim(), fact: 'identity' }, { token }))
      setInfoNote('')
    } catch { setError(t('admin.scholarship.requestInfoError')) } finally { setBusy('') }
  }

  // A standard request line for the selected (doc, person) — prefills the note box so the
  // reviewer can elaborate, and is the fallback if they clear it.
  const stdDocRequest = (dt: string, m: string) => {
    if (!dt) return ''
    // "Other document" has no standard clause — the reviewer types exactly what they need,
    // so leave the box empty (the generic "the requested document …" prefill was unhelpful).
    if (dt === 'other') return ''
    // Rich per-document clause (says what we look for) — clarity for the student.
    const docTxt = t(`admin.scholarship.requestDocStd.${dt}`)
    const memberTxt = m ? t(`scholarship.docs.income.wizard.member.${m}`) : ''
    return m
      ? t('admin.scholarship.requestDocPromptMember', { member: memberTxt, doc: docTxt })
      : t('admin.scholarship.requestDocPrompt', { doc: docTxt })
  }
  // The concrete (doc_type, member) the current category+qualifier resolves to — null until a
  // required qualifier is chosen (which keeps the Request button disabled).
  const reqResolved = resolveReq(reqCategory, reqQualifier)
  const onReqCategory = (key: string) => {
    setReqCategory(key)
    setReqQualifier('')                                  // reset the qualifier when the category changes
    const r = resolveReq(key, '')                         // prefills only for a no-qualifier category
    setReqDocNote(r ? stdDocRequest(r.docType, r.member) : '')
  }
  const onReqQualifier = (q: string) => {
    setReqQualifier(q)
    const r = resolveReq(reqCategory, q)
    setReqDocNote(r ? stdDocRequest(r.docType, r.member) : '')
  }
  const doRequestDoc = async () => {
    if (!token || !reqResolved) return
    const { docType, member } = reqResolved
    const prompt = reqDocNote.trim() || stdDocRequest(docType, member)
    setBusy('reqdoc'); setError('')
    try {
      setApp(await raiseResolutionItem(
        id,
        { kind: 'doc', doc_type: docType, household_member: member, prompt, fact: docTypeToRequestFact(docType) },
        { token },
      ))
      setReqDocNote(''); setReqCategory(''); setReqQualifier('')
    } catch { setError(t('admin.scholarship.requestInfoError')) } finally { setBusy('') }
  }

  const doActionResolution = async (itemId: number, action: 'waive' | 'resolve' | 'reopen') => {
    if (!token) return
    setBusy(`res${itemId}`); setError('')
    try {
      setApp(await actionResolutionItem(itemId, action, { token }))
    } catch { setError(t('admin.scholarship.requestInfoError')) } finally { setBusy('') }
  }

  const refreshApp = async () => {
    if (!token) return
    setApp(await getScholarshipApplication(id, { token }))
  }

  const doAddReferee = async () => {
    if (!token || !refForm.name.trim()) return
    // Referee phone is optional, but if given it must be a valid Malaysian number.
    if (refForm.phone.trim() && !isValidPhone(refForm.phone)) {
      setError(t('scholarship.apply.error.phone')); return
    }
    setBusy('ref'); setError('')
    try {
      await addReferee(id, refForm, { token })
      setRefForm({ ...EMPTY_REFEREE })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doDeleteReferee = async (refId: number) => {
    if (!token) return
    setBusy('ref'); setError('')
    try {
      await deleteReferee(id, refId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doReRunVision = async (docId: number) => {
    if (!token) return
    setBusy('vision'); setError('')
    try {
      await reRunVision(id, docId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.visionError')) } finally { setBusy('') }
  }

  if (error && !app) return <div className="text-critical-600 mt-8">{error}</div>
  if (!app) return <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>

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

  // Household income + size from the backend document-vs-stated reconciliation (household_check).
  // Non-mutating throughout — the stored declared value is never overwritten, only the DISPLAY
  // leads with the document-verified figure.
  const _hc = app.household_check
  const _fmtRm = (n: number) => `RM ${Number(n).toLocaleString('en-US')}`
  // Income: when we've read every earner's income (confident), the DOCUMENT-VERIFIED total leads
  // with a tick; the student's declared figure drops to a muted "Declared: RMx" note when it
  // differs. Otherwise fall back to the declared value (no tick).
  const _incConfident = !!_hc?.income.all_known && _hc.income.documented_total != null
  const incomeValue = _incConfident
    ? _fmtRm(_hc!.income.documented_total!)
    : (app.household_income ? _fmtRm(app.household_income) : null)
  const incomeTip = _incConfident
    ? t('admin.scholarship.verified.tooltip', { source: t('admin.scholarship.verified.source.incomeProof') })
    : undefined
  const incomeNote = _incConfident && !_hc!.income.matches && app.household_income
    ? t('admin.scholarship.verified.declaredNote', { value: _fmtRm(app.household_income) })
    : undefined
  // Household size: once the student CONFIRMS the roster count (household_size_confirm query), lead
  // with the roster count + a tick and drop the stated figure to a muted "Declared: M" note — the
  // same document-on-top pattern as income (non-mutating). Otherwise: a tick when fully accounted,
  // or an amber "Roster counts N" prompt on an unconfirmed over-count.
  const _sizeConfirmed = !!_hc?.size.confirmed
  const _effectiveSize = _sizeConfirmed ? _hc!.size.described : app.household_size
  const sizeValue = _effectiveSize
  const sizeTip = (_sizeConfirmed || _hc?.size.accounted) ? t('admin.scholarship.verified.sizeAccounted') : undefined
  const sizeNote = _sizeConfirmed
    ? (app.household_size ? t('admin.scholarship.verified.declaredNote', { value: String(app.household_size) }) : undefined)
    : (_hc?.size.overcount ? t('admin.scholarship.verified.rosterNote', { count: String(_hc.size.described) }) : undefined)
  const sizeNoteTone: 'amber' | 'muted' = _sizeConfirmed ? 'muted' : 'amber'
  // Per capita income = the DOCUMENT-VERIFIED household income (when confident) ÷ the effective size
  // (confirmed roster count, else stated). (Replaces the always-"No" JKM field.)
  const _pcBase = _incConfident ? _hc!.income.documented_total! : app.household_income
  const perCapita = _pcBase && _effectiveSize ? _pcBase / _effectiveSize : null

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
  const queryingLocked = isQueryingLocked(app.status, app.interview_session?.status) && !decisionReopened
  const lockReason = queryingLockReason(app.status, app.interview_session?.status)
  // #7: Approve/Decline activate only once the reviewer has (1) submitted interview
  // findings, (2) pressed Pass/Fail on all four facts, and (3) written a conclusion.
  // (Approve's actual accept is still backend-gated on a complete profile + identity.)
  const decisionReady = isDecisionReady(app.interview_session?.status, officerVerdict, verdictReason)
  // The bursary is fixed by pathway type and always present (award.py) — so approve just needs a
  // complete decision. hasAssistance stays in the gate for safety (award_amount or the by-type
  // figure); it is effectively always true now.
  const hasAssistance = app.award_amount != null || app.proposed_award_amount != null
  const approveReady = isApproveReady(decisionReady, hasAssistance)
  // Save (the commit) is enabled once a reversible outcome is chosen AND its preconditions hold:
  // Approve → all of approveReady (incl. amount); Decline → decisionReady (no amount needed).
  const canSave = (officerVerdict.overall === 'accept' && approveReady)
    || (officerVerdict.overall === 'decline' && decisionReady)

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
        label: t(`admin.scholarship.anomaly.${a.code}.question`,
          Object.fromEntries(Object.entries(a.params).map(([k, v]) => [k, String(v)]))),
      })),
    ...(app.interview_agenda || [])
      .filter((e) => e.kind !== 'anomaly')
      .map((e) => ({ code: `${e.kind}:${e.code}`, ai: false, label: agendaEntryLabel(e) })),
    ...(app.interview_gaps || []).map((g) => ({ code: g.code, label: g.question, ai: true })),
  ]
  const editableAgenda = agendaItems.filter((it) => findings[it.code]?.verdict !== 'deleted')

  return (
    <div className="space-y-4 pb-10">
      <DocViewer doc={viewerDoc} onClose={() => setViewerDoc(null)} />
      <CockpitHeader
        app={app} t={t} vtip={vtip} busy={busy} canWrite={canWrite}
        prevId={prevId} nextId={nextId}
        doCancelDecline={doCancelDecline} doHoldAward={doHoldAward}
      />


      <ApplicantCards
        app={app} t={t} vtip={vtip}
        incomeValue={incomeValue} incomeTip={incomeTip} incomeNote={incomeNote}
        sizeValue={sizeValue} sizeTip={sizeTip} sizeNote={sizeNote} sizeNoteTone={sizeNoteTone}
        perCapita={perCapita}
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


      {/* ── Decision — audit the four facts (records the verdict) → verify identity →
           accept. The audit→accept gate is preserved (accept stays gated on a complete
           profile + every checklist box). ──────────────────────────────────────────── */}
      {/* Hidden at shortlisted (pre-submission): Approve/Decline need a submitted interview.
          Hidden on a CLOSED case with no verdict — there is no decision left to record, and the
          justification box invited writing one. WITH a verdict it stays: that is the frozen
          decision trail (21 rejected records on 2026-08-18), which must not disappear. */}
      {showsDecisionCards({ status: app.status, decisionReopened, decisionRecorded }) && (
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">{t('admin.scholarship.decision.title')}</h2>
          {/* Reopen = REVERSE a recorded decision (super-only). Asks for a reason first;
              reopening holds the profile from the pool and unlocks the panel. */}
          {decisionLocked && isSuper && !reopenOpen && (
            <button onClick={() => { setReopenOpen(true); setReopenReason('') }}
              className="rounded-lg border border-ground-300 px-2.5 py-1 text-xs text-ground-600 hover:bg-ground-100">
              {t('admin.scholarship.recordVerdict.reopen')}
            </button>
          )}
        </div>

        {/* The "why are you reopening?" prompt — a reopen asserts a reviewer error, so a
            reason is required (logged + counted against the reviewer once a change is saved). */}
        {decisionLocked && isSuper && reopenOpen && (
          <div className="rounded-lg border border-caution-200 bg-caution-50 p-3 space-y-2">
            <p className="text-xs font-medium text-caution-900">{t('admin.scholarship.recordVerdict.reopenTitle')}</p>
            <p className="text-[11px] text-caution-800">{t('admin.scholarship.recordVerdict.reopenHint')}</p>
            <textarea value={reopenReason} rows={2} onChange={(e) => setReopenReason(e.target.value)}
              placeholder={t('admin.scholarship.recordVerdict.reopenPlaceholder')}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
            <div className="flex items-center gap-2">
              <button onClick={doReopenDecision} disabled={!!busy || !reopenReason.trim()}
                className="px-3 py-1.5 bg-critical-fill text-critical-fill-ink rounded-lg text-sm disabled:opacity-50">
                {busy === 'reopen' ? t('common.loading') : t('admin.scholarship.recordVerdict.reopenConfirm')}
              </button>
              <button onClick={() => { setReopenOpen(false); setReopenReason('') }} disabled={!!busy}
                className="px-3 py-1.5 border rounded-lg text-sm text-ground-600 disabled:opacity-50">
                {t('common.cancel')}
              </button>
            </div>
          </div>
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
                className="px-3 py-1.5 border border-caution-400 text-caution-900 rounded-lg text-xs hover:bg-caution-100 disabled:opacity-50">
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
            {isQcAccepted(app.status) ? (
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
                 both, mirroring the accepted card above. Earlier steps are muted; the step that
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
                className="px-4 py-2 border border-critical-300 text-critical-700 rounded-lg text-sm disabled:opacity-50">
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
        {isQcAccepted(app.status) && !decisionReopened ? (
          /* Committed acceptance → read-only summary. A post-accept decline goes through
             Reopen (→ interviewed → declined as 'interview'); the direct 'contractual'
             decline is reserved for a genuinely post-award (sponsored) case. */
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
                className="px-4 py-2 border border-critical-300 text-critical-700 rounded-lg text-sm disabled:opacity-50">
                {busy === 'reject' ? t('admin.scholarship.reject.running') : t('admin.scholarship.reject.declineContractual')}
              </button>
            )}
          </div>
        ) : (decisionReopened || ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status)) ? (
          canWrite && (
            <div className="space-y-2">
              {/* The old coarse "still owes: documents / consent" banner moved OUT to its own
                  Blockers card below this one (owner 2026-07-22) — it now names each item
                  from the consent gate instead of two categories. */}
              {/* ⚠ SAY THAT THE VERDICT IS ALREADY SAVED. Without this the panel looks untouched
                  on a fresh load, so a reviewer coming back to a half-completed Approve cannot
                  tell whether her decision was recorded — and the only clue she ever had was a
                  message that vanished with the page. */}
              {stuckAfterVerdict && (
                <p className="rounded-lg bg-caution-50 px-3 py-2 text-[11px] text-caution-800">
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
                      : 'border-positive-600 bg-ground-0 text-positive-700 hover:bg-positive-50'}`}>
                  {t('admin.scholarship.recordVerdict.approve')}
                </button>
                <button onClick={selectDecline} disabled={!!busy || !decisionReady}
                  className={`rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${
                    officerVerdict.overall === 'decline'
                      ? 'border-critical-fill bg-critical-fill text-critical-fill-ink'
                      : 'border-critical-500 bg-ground-0 text-critical-700 hover:bg-critical-50'}`}>
                  {t('admin.scholarship.recordVerdict.decline')}
                </button>
              </div>
              {/* One contextual hint: what's still missing before Save. */}
              {!decisionReady ? (
                <p className="text-[11px] text-caution-700">{t('admin.scholarship.recordVerdict.saveNeedsReady')}</p>
              ) : !officerVerdict.overall ? (
                <p className="text-[11px] text-caution-700">{t('admin.scholarship.recordVerdict.chooseOutcome')}</p>
              ) : officerVerdict.overall === 'accept' && !hasAssistance ? (
                <p className="text-[11px] text-caution-700">{t(app.award_disqualifier
                  ? 'admin.scholarship.recordVerdict.approveNeedsReview'
                  : 'admin.scholarship.recordVerdict.approveNeedsAmount')}</p>
              ) : null}
              {/* Save is the final commit of the chosen outcome. */}
              <button onClick={doSave} disabled={!!busy || !canSave}
                className="w-full px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium disabled:opacity-50">
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

      <BlockersPanel
        app={app} t={t} busy={busy} isSuper={isSuper} role={role}
        nudgeMsg={nudgeMsg} doNudge={doNudge}
      />


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
      />


      </div>{/* end RIGHT column */}

      </div>{/* end cockpit grid */}

      <PostAwardPanels
        app={app} t={t} busy={busy} isSuper={isSuper} canWrite={canWrite}
        bursary={bursary} bursaryMsg={bursaryMsg}
        doCountersignBursary={doCountersignBursary} doWitnessBursary={doWitnessBursary}
        disbAmount={disbAmount} setDisbAmount={setDisbAmount}
        disbLabel={disbLabel} setDisbLabel={setDisbLabel} disbMsg={disbMsg}
        doScheduleTranche={doScheduleTranche} doDisbursementAction={doDisbursementAction}
        doSetSubstate={doSetSubstate}
        closeReason={closeReason} setCloseReason={setCloseReason}
        closeMsg={closeMsg} doClose={doClose}
      />

      </>)}
    </div>
  )
}

