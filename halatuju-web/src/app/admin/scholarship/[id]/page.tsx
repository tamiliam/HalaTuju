'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import InterviewScheduleCard from '@/components/admin/InterviewScheduleCard'
import VerifiedTick from '@/components/VerifiedTick'
import { formatPhone, formatAddress, isValidPhone, formatNric, referralAcronym, expandMatricInstitution } from '@/lib/scholarship'
import { statusLabelKey, statusTone, displayStatus } from '@/lib/applicationStatus'
import { fieldVerifications, type VerifiableField } from '@/lib/fieldVerification'
import {
  getScholarshipApplication,
  getVerdictCaseSummary,
  type VerdictCaseSummary,
  suggestInterviewGaps,
  verifyAcceptApplication,
  rejectApplication,
  cancelPendingDecline,
  holdPendingAward,
  addReferee,
  deleteReferee,
  reRunVision,
  assignApplication,
  getInterview,
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
  scheduleTranche,
  actOnDisbursement,
  setMaintenanceSubstate,
  closeApplication,
  type AdminDisbursement,
  type DisbursementAction,
  type MaintenanceSubstate,
  type ClosureReason,
  type AdminScholarshipDetail,
  type AdminSponsorProfile,
  type AdminApplicantDocument,
  type AdminInterviewSession,
  type AdminVerdictItem,
  type AdminResolutionItem,
  type AdminAgendaEntry,
} from '@/lib/admin-api'
import {
  factTileTone,
  TONE_BAND_KEY,
  groupDocumentsByFact,
  aiSuggestionFor,
  documentPill,
  documentFacts,
  utilityBillValues,
  schoolLeavingValues,
  incomeSubSections,
  docIconFor,
  earnerMemberFor,
  viewerKind,
  isClearAccept,
  isQueryingLocked,
  isDecisionReady,
  isApproveReady,
  verdictItemKey,
  headerTimeline,
  type FactStatus,
  type IncomeSlot,
} from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import { localiseParams, titleSourceFor } from '@/lib/actionCentre'
import { isFunded, disbursementTone, actionsFor, nextSequence, totalReleased } from '@/lib/disbursement'
import type { BursaryAgreement } from '@/lib/api'

const COMPLETENESS_PARTS = ['quiz_done', 'details_done', 'funding_done', 'documents_done', 'consent_done', 'address_done', 'guardian_docs_done', 'family_done'] as const

// Officer doc-request control: a friendly CATEGORY + a mandatory QUALIFIER that resolves to a
// concrete (doc_type, household_member). Every request is tagged at source — a "Whose?" category
// (STR / IC / salary / EPF) requires a person; a "Which?" category (results slip / utility / other)
// requires a sub-type. The Request button stays disabled until the qualifier is chosen.
type ReqCategory = {
  key: string
  qualifier: 'whose' | 'which' | null
  docType?: string                                          // 'whose' | null → fixed doc_type
  members?: readonly string[]                               // 'whose' → the person options
  options?: readonly { value: string; docType: string }[]  // 'which' → sub-type options
}
const REQUEST_CATEGORIES: readonly ReqCategory[] = [
  { key: 'ic', qualifier: null, docType: 'ic' },                                   // Applicant's IC
  { key: 'results_slip', qualifier: 'which', options: [
      { value: 'spm', docType: 'results_slip' },
      { value: 'cgpa', docType: 'semester_result' } ] },                            // SPM / current CGPA
  { key: 'offer_letter', qualifier: null, docType: 'offer_letter' },
  { key: 'str', qualifier: 'whose', docType: 'str', members: ['father', 'mother', 'guardian'] },
  { key: 'parent_ic', qualifier: 'whose', docType: 'parent_ic',
    members: ['father', 'mother', 'guardian', 'brother', 'sister'] },              // Family member's IC
  { key: 'salary_slip', qualifier: 'whose', docType: 'salary_slip',
    members: ['father', 'mother', 'guardian', 'brother', 'sister'] },
  { key: 'epf', qualifier: 'whose', docType: 'epf',
    members: ['father', 'mother', 'guardian', 'brother', 'sister'] },
  { key: 'birth_certificate', qualifier: null, docType: 'birth_certificate' },
  { key: 'utility', qualifier: 'which', options: [
      { value: 'water_bill', docType: 'water_bill' },
      { value: 'electricity_bill', docType: 'electricity_bill' } ] },
  { key: 'other', qualifier: 'which', options: [
      { value: 'school_leaving_cert', docType: 'school_leaving_cert' },
      { value: 'guardianship_letter', docType: 'guardianship_letter' },
      { value: 'statement_of_intent', docType: 'statement_of_intent' },
      { value: 'photo', docType: 'photo' },
      { value: 'other', docType: 'other' } ] },
]
const REQ_CAT = new Map(REQUEST_CATEGORIES.map((c) => [c.key, c]))
// Resolve a (category, qualifier) pick to a concrete request, or null when the qualifier is
// required but not yet chosen (→ keeps the Request button disabled).
function resolveReq(catKey: string, qual: string): { docType: string; member: string } | null {
  const c = REQ_CAT.get(catKey)
  if (!c) return null
  if (c.qualifier === null) return { docType: c.docType!, member: '' }
  if (c.qualifier === 'whose') return qual ? { docType: c.docType!, member: qual } : null
  const opt = c.options!.find((o) => o.value === qual)
  return opt ? { docType: opt.docType, member: '' } : null
}
const DOC_FACT: Record<string, string> = {
  ic: 'identity', results_slip: 'academic', semester_result: 'academic', offer_letter: 'pathway',
  parent_ic: 'income', str: 'income', salary_slip: 'income', epf: 'income',
  birth_certificate: 'income', guardianship_letter: 'income',
  water_bill: 'income', electricity_bill: 'income',
  school_leaving_cert: 'other', statement_of_intent: 'other', photo: 'other', other: 'other',
}

// #9 sync: an interview anomaly is SUPPRESSED from the agenda when the same concern is
// already a Check-2 query the student is being asked (Check-2 fires first; no repeat).
// Maps anomaly code → the owning Check-2 clarify code.
const ANOMALY_CHECK2_OWNER: Record<string, string> = {
  utility_holder_unknown: 'utility_holder_unknown',
  utility_address_mismatch: 'utility_address_mismatch',
  device_in_funding: 'device_status_unknown',
  first_in_family_with_siblings_studying: 'sibling_level_unknown',
}

const EMPTY_REFEREE = { name: '', role: '', relationship: '', phone: '', email: '' }

// Non-parent guardian relationships — drive the dynamic "Parent" vs "Guardian" label (#5).
const NON_PARENT_RELATIONSHIPS = new Set([
  'legal_guardian', 'grandparent', 'older_sibling', 'brother', 'sister', 'relative', 'other_relative',
])
// Referees aren't in play yet — hide the capture UI (the handlers stay wired so this
// is a one-line re-enable, and so they don't become unused). Flip to true to restore.
const SHOW_REFEREES = false


function Field({ label, value, verifiedLabel, note, noteTone = 'amber' }: { label: string; value: ReactNode; verifiedLabel?: string; note?: string; noteTone?: 'amber' | 'muted' }) {
  return (
    <div>
      <dt className="text-xs text-gray-400 uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-gray-800 break-words">
        {value === null || value === undefined || value === '' ? '—' : value}
        {verifiedLabel && <VerifiedTick label={verifiedLabel} />}
      </dd>
      {note && <p className={`mt-0.5 text-xs ${noteTone === 'muted' ? 'text-gray-400' : 'text-amber-600'}`}>{note}</p>}
    </div>
  )
}

function Card({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-gray-200 bg-white p-5 shadow-sm ${className}`}>
      <h2 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{title}</h2>
      {children}
    </div>
  )
}

/** Section heading for a group of panels (e.g. "Review & actions"). */
function GroupLabel({ children }: { children: ReactNode }) {
  return <h2 className="mb-2 mt-2 text-xs font-semibold uppercase tracking-wider text-gray-500">{children}</h2>
}

const yn = (v: boolean | null | undefined) => (v === true ? 'Yes' : v === false ? 'No' : '—')
const joinOr = (a?: string[] | null) => (a && a.length ? a.join(', ') : '—')

/** Grade dict → readable chips (subject key uppercased · grade). */
function Grades({ grades, trailing }: { grades?: Record<string, string> | null; trailing?: ReactNode }) {
  const entries = Object.entries(grades || {}).filter(([, g]) => g)
  if (!entries.length) return <span className="text-gray-400 text-sm">—</span>
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {entries.map(([k, g]) => (
        <span key={k} className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-xs">
          <span className="text-gray-500 uppercase">{k.replace(/_/g, ' ')}</span>
          <span className="font-semibold text-gray-800">{g}</span>
        </span>
      ))}
      {trailing}
    </div>
  )
}

export default function AdminScholarshipDetailPage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const isSuper = role?.role === 'super' || !!role?.is_super_admin
  // Assignment (F7) is a super or org_admin power — an org_admin assigns their own org's reviewers.
  const canAssign = isSuper || role?.role === 'org_admin'
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
  // V5 gap floor: super-only override panel state (reason recorded server-side).
  const [qcOverrideOpen, setQcOverrideOpen] = useState(false)
  const [qcOverrideReason, setQcOverrideReason] = useState('')
  // Consolidation: the student's own words (note/story/funding) are collapsed by
  // default under the Sponsor profile — the reviewer checks the AI draft first.
  const [showOwnWords, setShowOwnWords] = useState(false)
  // Conditional Bursary Award Agreement (flag-gated, dark by default). The admin
  // detail GET does not carry the agreement, so the card's state is populated by
  // the countersign/witness action responses (each returns the full agreement).
  const [bursary, setBursary] = useState<BursaryAgreement | null>(null)
  const [bursaryMsg, setBursaryMsg] = useState('')

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
      const known = ['not_ready', 'not_reviewer', 'bad_assignee', 'findings_submitted']
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
      const clearAccept = isClearAccept(officerVerdict, !!result.completeness?.complete, result.status)
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
      if (accepted) {
        setVerdictMsg(t('admin.scholarship.decision.savedAndAccepted')); setVerdictMsgTone('ok')
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
  const doSave = async () => {
    const outcome = officerVerdict.overall
    if (outcome === 'accept') {
      await doRecordVerdict(true, true)                 // record (overall=accept) + finalise + accept + publish
    } else if (outcome === 'decline') {
      await doRecordVerdict(false, false)               // record the verdict (overall=decline), no profile gen
      await doReject(app?.status === 'recommended' ? 'contractual' : 'interview')
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
  const doQcDecision = async (decision: 'accept' | 'reopen', overrideReason?: string) => {
    if (!token) return
    if (decision === 'reopen' && !qcComments.trim()) return
    setBusy('qc'); setError(''); setVerdictMsg('')
    try {
      const result = await recordQcDecision(
        id, { decision, comments: decision === 'reopen' ? qcComments.trim() : undefined,
              override_reason: overrideReason?.trim() || undefined }, { token })
      setApp(result)
      setProfile(result.sponsor_profile)
      loadVerdictState(result)
      setQcReopenOpen(false); setQcComments('')
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
        { kind: 'doc', doc_type: docType, household_member: member, prompt, fact: DOC_FACT[docType] || 'other' },
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

  if (error && !app) return <div className="text-red-600 mt-8">{error}</div>
  if (!app) return <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>

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
  const decisionLocked = decisionRecorded && !decisionReopened

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
    <div className="mx-auto max-w-6xl space-y-4 pb-10">
      <DocViewer doc={viewerDoc} onClose={() => setViewerDoc(null)} />
      {/* Header — applicant identity, status, and key facts at a glance */}
      <header className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <Link href="/admin/scholarship" className="text-xs text-gray-400 hover:text-gray-600">‹ {t('admin.scholarship.back')}</Link>
          {(prevId != null || nextId != null) && (
            <div className="flex items-center gap-1 text-xs">
              {prevId != null ? (
                <Link href={`/admin/scholarship/${prevId}`} className="rounded px-2 py-1 font-medium text-gray-600 hover:bg-gray-100">‹ {t('admin.scholarship.prev')}</Link>
              ) : (
                <span className="rounded px-2 py-1 text-gray-300">‹ {t('admin.scholarship.prev')}</span>
              )}
              {nextId != null ? (
                <Link href={`/admin/scholarship/${nextId}`} className="rounded px-2 py-1 font-medium text-gray-600 hover:bg-gray-100">{t('admin.scholarship.next')} ›</Link>
              ) : (
                <span className="rounded px-2 py-1 text-gray-300">{t('admin.scholarship.next')} ›</span>
              )}
            </div>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-xl font-bold tracking-tight text-gray-900 sm:text-2xl">{app.name || '—'}{vtip('name') && <VerifiedTick label={vtip('name')!} />}</h1>
          {/* Status pill — a super-reopened decision shows "Reopened" (overrides accepted/rejected). */}
          {(() => {
            const s = displayStatus(app)
            return (
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusTone(s)}`}>
                {t(statusLabelKey(s))}
              </span>
            )
          })()}
          {/* Primary action button — scrolls to the Record Verdict panel. Not shown once
              'interviewed' (awaiting QC): the verdict is submitted, panel is read-only. */}
          {canWrite && ['shortlisted', 'profile_complete', 'interviewing'].includes(app.status) && (
            <button
              onClick={() => document.getElementById('record-verdict-panel')?.scrollIntoView({ behavior: 'smooth' })}
              className="ml-auto rounded-lg bg-primary-500 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-primary-600"
            >
              {t('admin.scholarship.recordVerdict.title')}
            </button>
          )}
          {app.status === 'rejected' && app.rejection_category && (
            <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">
              {t(`admin.scholarship.reject.category.${app.rejection_category}`)}
            </span>
          )}
          {app.bucket && (
            <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-100 px-1.5 text-xs font-bold text-amber-700">{app.bucket}</span>
          )}
          {app.qualification && (
            <span className="rounded-full border border-gray-200 px-2 py-0.5 text-xs font-medium text-gray-500">{app.qualification.toUpperCase()}</span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
          <span>NRIC <span className="font-mono text-gray-700">{formatNric(app.nric || '') || '—'}</span>{vtip('nric') && <VerifiedTick label={vtip('nric')!} />}</span>
          {referralAcronym(app.referral_source) && (
            <span
              title={app.referral_source ? t(`scholarship.apply.org.${app.referral_source}`) : ''}
              className="rounded-full border border-gray-200 px-2 py-0.5 font-medium text-gray-600"
            >
              {referralAcronym(app.referral_source)}
            </span>
          )}
          {(() => {
            // Post-recommendation, the header shows a lifecycle timeline (Submitted·Recommended·
            // Awarded, then Awarded·Active·Maintenance). Earlier states keep the original
            // Submitted·Applied·Assigned line (Assigned carries the reviewer, not a date).
            const timeline = headerTimeline(app)
            if (timeline) {
              return timeline.map((step) => (
                <span key={step.labelKey}>
                  {t(`admin.scholarship.statuses.${step.labelKey}`)}{' '}
                  <span className="text-gray-700">{step.at ? formatDate(step.at) : '—'}</span>
                </span>
              ))
            }
            return (
              <>
                {app.submitted_at && (
                  <span>{t('admin.scholarship.submitted')} {formatDate(app.submitted_at)}</span>
                )}
                {app.profile_completed_at && (
                  <span>{t('admin.scholarship.applied')} {formatDate(app.profile_completed_at)}</span>
                )}
                <span>{t('admin.scholarship.assigned')} <span className="text-gray-700">{app.assigned_to_name || '—'}</span></span>
              </>
            )
          })()}
        </div>
      </header>

      {/* Cool-off (#13/#14): a decision recorded but held silently — the student sees nothing
          until the reveal date, so it can be cancelled/held in the window. Admin-only. */}
      {app.decline_due_at && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm text-amber-800">
            ⏳ {t('admin.scholarship.cooloff.declineScheduled')}{' '}
            <strong>{formatDate(app.decline_due_at)}</strong>.{' '}
            {t('admin.scholarship.cooloff.silentNote')}
          </p>
          <button onClick={doCancelDecline} disabled={busy === 'cooloff'}
            className="whitespace-nowrap rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50">
            {busy === 'cooloff' ? '…' : t('admin.scholarship.cooloff.cancelDecline')}
          </button>
        </div>
      )}
      {app.award_due_at && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm text-amber-800">
            ⏳ {t('admin.scholarship.cooloff.awardScheduled')}{' '}
            <strong>{formatDate(app.award_due_at)}</strong>.{' '}
            {t('admin.scholarship.cooloff.silentNote')}
          </p>
          <button onClick={doHoldAward} disabled={busy === 'cooloff'}
            className="whitespace-nowrap rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50">
            {busy === 'cooloff' ? '…' : t('admin.scholarship.cooloff.holdAward')}
          </button>
        </div>
      )}

      {/* Applicant info — three explicit columns (About+Family / Academic / Support…) */}
      {(() => {
        const isStpm = app.qualification === 'stpm'
        // Pathway context: matric/stpm are INSTITUTION pathways (track + school);
        // everything else (asasi, university, poly, pismp…) is a PROGRAMME pathway
        // (a chosen course), so Pre-U track doesn't apply.
        const isInstitutionPathway = app.chosen_pathway === 'matric' || app.chosen_pathway === 'stpm'
        // Human labels for the stored codes — reuse the apply-form's own i18n maps so
        // the admin sees the same words the student did (matric→Matriculation, etc.).
        const pathwayLabel = (code?: string | null) => (code ? t(`scholarship.apply.plan.pathway.${code}`) : null)
        // pre_u_track holds a matric TRACK (sains/kejuruteraan…) for matric, or an STPM
        // STREAM (sains/sains_sosial/not_sure) for STPM — both under scholarship.apply.plan.
        const preUTrackLabel = app.pre_u_track
          ? t(`scholarship.apply.plan.${app.chosen_pathway === 'stpm' ? 'stream' : 'track'}.${app.pre_u_track}`)
          : null
        // Help answers: render the apply-form's own words (Yes / No / Not sure) rather
        // than the raw 'yes'/'no'/'unsure' codes.
        const helpLabel = (v?: string | null) => (v ? t(`scholarship.apply.help.${v}`) : null)
        // Link a course back to its HalaTuju public page (opens in a new tab so
        // the admin doesn't lose the application). STPM degrees live under /stpm.
        const courseHref = (cid?: string) => (cid ? (isStpm ? `/stpm/${cid}` : `/course/${cid}`) : null)
        const courseLink = (cid: string | undefined, name: string) => {
          const href = courseHref(cid)
          return href
            ? <a href={href} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">{name}</a>
            : name
        }
        // Course start: the offer letter's report/registration date — surfaced in the Academic card
        // so the officer sees when the student must report. Prefer the offer that actually carries a
        // reporting date; fall back to the first offer.
        // LIVE offers only — a replaced (superseded) offer's reporting date must not show (owner
        // 2026-07-16): the value shown has to come from the same current offer the tick verifies, so
        // the two can never disagree. (The course-switch note below deliberately reads superseded
        // offers separately — that's history, not the current pathway.)
        const _offers = (app.documents || []).filter((d) => d.doc_type === 'offer_letter' && !d.superseded_at)
        const _offer = _offers.find((d) => d.pathway_check?.reporting_date) || _offers[0]
        const reportingDate = _offer?.pathway_check?.reporting_date || ''
        const hasPlans = !!(app.chosen_pathway || app.chosen_programme?.course_name || reportingDate
          || app.top_choices?.length || app.pathways_considered?.length || app.uncertainty_reasons?.length)
        const addr = formatAddress([
          app.address,
          [app.postal_code, app.city].filter(Boolean).join(' '),
          app.preferred_state,
        ])
        const guardian = (app.guardians && app.guardians[0]) || null
        // #5: name the relationship precisely. The minor-consent record carries the
        // real relationship; a non-parent guardian (legal_guardian/grandparent/sibling/
        // relative) → "Guardian", father/mother (or an adult self-consent) → "Parent".
        const activeConsent = (app.consents || []).find((c) => c.is_active) || null
        const isNonParentGuardian = activeConsent?.granted_by === 'guardian'
          && NON_PARENT_RELATIONSHIPS.has(activeConsent?.guardian_relationship || '')
        const personLabel = isNonParentGuardian
          ? t('admin.scholarship.guardianLabel')
          : t('admin.scholarship.parentLabel')
        return (
          <div className="space-y-4">
            {/* Two independent columns rather than a row-major grid, so each column
                packs its cards top-down (masonry-style). Family floats up directly
                under the shorter About card instead of waiting for the taller
                Academic card opposite it. */}
            <div className="grid gap-4 md:grid-cols-2 md:items-start">
              {/* Left column — About, then Family */}
              <div className="space-y-4">
              {/* About — contact details (NRIC is in the header above) */}
              <Card title={t('admin.scholarship.sec.contact')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.phone')} value={app.contact_phone ? formatPhone(app.contact_phone) : null} />
                  {/* Email takes the old Call-language slot (call language hidden — owner 2026-07-15).
                      Verified email only: shown once the student verifies it, else the verified
                      Google login email. */}
                  <Field label={t('admin.scholarship.email')} value={app.verified_email
                    ? <a href={`mailto:${app.verified_email}`} className="text-primary-600 hover:underline">{app.verified_email}</a>
                    : null} />
                  <div className="col-span-2"><Field label={t('admin.scholarship.address')} value={addr} verifiedLabel={vtip('address')} /></div>
                </dl>
              </Card>

              {/* Family & finances — moved up under About (was below Academic) */}
              <Card title={t('admin.scholarship.sec.family')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.income')} value={incomeValue} verifiedLabel={incomeTip} note={incomeNote} noteTone="muted" />
                  <Field label={t('admin.scholarship.householdSize')} value={sizeValue} verifiedLabel={sizeTip} note={sizeNote} noteTone={sizeNoteTone} />
                  <Field label="STR" value={yn(app.receives_str)} verifiedLabel={vtip('str')} />
                  <Field label={t('admin.scholarship.perCapita')} value={perCapita != null ? `RM ${Number(perCapita).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : null} />
                  <Field label={personLabel} value={guardian?.name} verifiedLabel={vtip('parentName')} />
                  <Field label={t('admin.scholarship.guardianPhone', { role: personLabel })} value={guardian?.phone ? formatPhone(guardian.phone) : null} />
                </dl>
              </Card>
              </div>

              {/* Right column — Academic (tall: grades + plans), then Support */}
              <div className="space-y-4">
              {/* Academic — school / merit / grades. Plans + notes are their own boxes below. */}
              <Card title={t('admin.scholarship.sec.academic')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.school')} value={app.school} verifiedLabel={vtip('school')} />
                  <Field label={t('admin.scholarship.meritScore')} value={app.merit_score} />
                  {isStpm && <Field label="MUET" value={app.muet_band} />}
                </dl>
                <div className="mt-3">
                  <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">
                    {isStpm ? t('admin.scholarship.stpmGrades') : t('admin.scholarship.spmGrades')}
                  </dt>
                  {/* The tick renders AFTER the subject chips (item 1). It verifies the SPM slip
                      against the SPM `grades`, so it only belongs to an SPM student's grades — an
                      STPM student's STPM grades are NOT what academic_check verifies (it would sit
                      on a match against the separate SPM slip → misattribution, #132). */}
                  <Grades
                    grades={isStpm ? app.stpm_grades : app.grades}
                    trailing={!isStpm && vtip('grades') ? <VerifiedTick label={vtip('grades')!} /> : undefined}
                  />
                  {isStpm && Object.keys(app.spm_prereq_grades || {}).length > 0 && (
                    <div className="mt-2">
                      <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('admin.scholarship.spmPrereq')}</dt>
                      <Grades grades={app.spm_prereq_grades} />
                    </div>
                  )}
                </div>

                {/* Plans — chosen programme/pathway nested into Academic (no sub-label;
                    the divider sets it off). The free-text memos live in Student's note. */}
                {hasPlans && (
                  <div className="mt-4 border-t border-gray-100 pt-3">
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                      {isInstitutionPathway ? (
                        <>
                          <Field label={t('admin.scholarship.chosenPathway')} value={pathwayLabel(app.chosen_pathway)} />
                          <Field label={t('admin.scholarship.preUTrack')} value={preUTrackLabel} />
                          <Field label={t('admin.scholarship.preUInstitution')} value={expandMatricInstitution(app.pre_u_institution)} verifiedLabel={vtip('preUInstitution')} />
                        </>
                      ) : (
                        <Field
                          label={t('admin.scholarship.chosenProgramme')}
                          value={app.chosen_programme?.course_name
                            ? courseLink(app.chosen_programme.course_id as string | undefined, app.chosen_programme.course_name as string)
                            : pathwayLabel(app.chosen_pathway)}
                          verifiedLabel={vtip('chosenProgramme')}
                        />
                      )}
                      {reportingDate && <Field label={t('admin.scholarship.reportingDate')} value={reportingDate} verifiedLabel={vtip('reportingDate')} />}
                    </dl>
                    {app.top_choices?.length > 0 && (
                      <div className="mt-3">
                        <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('admin.scholarship.topChoices')}</dt>
                        <ol className="list-decimal ml-5 text-sm text-gray-800">
                          {app.top_choices.map((c) => <li key={c.rank}>{courseLink(c.course_id, c.course_name)}{c.institution ? ` — ${c.institution}` : ''}</li>)}
                        </ol>
                      </div>
                    )}
                    {app.pathways_considered?.length > 0 && <div className="mt-2"><Field label={t('admin.scholarship.pathwaysConsidered')} value={joinOr(app.pathways_considered)} /></div>}
                    {/* "Still deciding" reasons are hidden once the pathway is settled
                        (e.g. a verified offer letter auto-confirmed it) — they'd contradict
                        the now-shown chosen pathway/programme. */}
                    {app.pathway_certainty !== 'sure' && app.uncertainty_reasons?.length > 0 && <div className="mt-2"><Field label={t('admin.scholarship.uncertaintyReasons')} value={joinOr(app.uncertainty_reasons)} /></div>}
                  </div>
                )}
              </Card>

              {/* Support required — help only. Consent-to-contact is omitted: it's a
                  hard requirement to submit, so it's always "Yes" and adds no signal. */}
              <Card title={t('admin.scholarship.sec.support')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.helpUniversity')} value={helpLabel(app.help_university)} />
                  <Field label={t('admin.scholarship.helpScholarship')} value={helpLabel(app.help_scholarship)} />
                </dl>
              </Card>
              </div>
            </div>

            {/* Student's note · Your story · Funding moved into the left column,
                under the Sponsor profile (the "show the student's own words" reveal). */}

            {/* Estimated need relocated to the right column, beside Decision (award sizing). */}
          </div>
        )
      })()}

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

      {/* ── Verification verdict — four horizontal tiles ───────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.verdict.title')}</h2>
            <p className="text-xs text-gray-500">{t('admin.scholarship.verdict.intro')}</p>
          </div>
        </div>
        {/* Horizontal tile row */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(app.verdict || []).map((f) => {
            const tone = factTileTone(f)
            const tileColour = {
              green: 'border-green-200 bg-green-50',
              amber: 'border-amber-200 bg-amber-50',
              blue: 'border-primary-200 bg-primary-50',
              red: 'border-red-200 bg-red-50',
            }[tone]
            const dotColour = {
              green: 'bg-green-500',
              amber: 'bg-amber-500',
              blue: 'bg-primary-500',
              red: 'bg-red-500',
            }[tone]
            const labelColour = {
              green: 'text-green-700',
              amber: 'text-amber-700',
              blue: 'text-primary-700',
              red: 'text-red-700',
            }[tone]
            // Subtitle: first evidence item text, or first unresolved item text.
            const resolve = (it: AdminVerdictItem) =>
              t(`admin.scholarship.verdict.item.${verdictItemKey(it)}`,
                localiseParams(it.params, t))
            const subtitle = f.unresolved.length > 0
              ? resolve(f.unresolved[0])
              : f.evidence.length > 0
              ? resolve(f.evidence[0])
              : t(`admin.scholarship.verdict.status.${f.status}`)
            // A green (verified) fact is done — the tick says it all, so we drop the
            // description (and its detail block below). Amber/red keep the lead line.
            const isGreen = tone === 'green'
            return (
              <div key={f.fact} className={`min-w-0 rounded-lg border p-3 flex flex-col gap-1.5 ${tileColour}`}>
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={`h-2 w-2 rounded-full shrink-0 ${dotColour}`} aria-hidden />
                  <span className={`truncate text-xs font-semibold uppercase tracking-wide ${labelColour}`}>
                    {t(`admin.scholarship.verdict.fact.${f.fact}`)}
                  </span>
                  {isGreen && (
                    <span className="ml-auto shrink-0 text-green-600 text-sm font-bold"
                      aria-label={t('admin.scholarship.verdict.status.verified')}>✓</span>
                  )}
                </div>
                {/* The estimative-probability band (Kent scale) the colour stands for. */}
                <p className={`text-[10px] font-semibold uppercase tracking-wide ${labelColour}`}>
                  {t(`admin.scholarship.verdict.band.${TONE_BAND_KEY[tone]}`)}
                </p>
                {!isGreen && (
                  <p className="text-[11px] text-gray-700 leading-tight line-clamp-2 break-words">{subtitle}</p>
                )}
              </div>
            )
          })}
          {(app.verdict || []).length === 0 && (
            <p className="col-span-4 text-sm text-gray-400 italic">{t('admin.scholarship.none')}</p>
          )}
        </div>
        {/* Legend — the confidence scale the tile colours encode (green→red). */}
        {(app.verdict || []).length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-gray-400">
            {(['green', 'blue', 'amber', 'red'] as const).map((tn) => (
              <span key={tn} className="flex items-center gap-1">
                <span className={`h-2 w-2 rounded-full ${ {green:'bg-green-500',blue:'bg-primary-500',amber:'bg-amber-500',red:'bg-red-500'}[tn] }`} aria-hidden />
                {t(`admin.scholarship.verdict.band.${TONE_BAND_KEY[tn]}`)}
              </span>
            ))}
          </div>
        )}
        {/* Course-switch banner (owner 2026-07-10): the live offer replaced a genuinely different
            prior offer (any→any). ALWAYS shown — survives the green-collapse — so a switch is never
            missed. Info (blue) not warning: a PUBLIC switch is acceptable; the pathway tile itself
            (red if it landed on a private/IPTS arm) carries the accept/reject. */}
        {(() => {
          const sw = (app.documents || []).find(
            (d) => d.doc_type === 'offer_letter' && d.pathway_check?.switched_from)
          const from = sw?.pathway_check?.switched_from
          if (!from) return null
          const pc = sw!.pathway_check!
          return (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-primary-100 bg-primary-50 p-2.5 text-xs text-primary-800">
              <span aria-hidden>⇄</span>
              <span>{t('admin.scholarship.verdict.item.pathway_switched', {
                from_programme: from.programme || '—',
                from_institution: from.institution || '—',
                to_programme: pc.programme || '—',
                to_institution: pc.institution || '—',
              })}</span>
            </div>
          )
        })()}
        {/* Check-2 case summary — the LLM briefing that "talks to the reviewer" (dark-flag aware;
            empty when every fact is Certain). Sits above the checklist, which is the audit trail. */}
        {caseSummary?.enabled && (caseSummary.summary || '').trim() && (
          <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/60 p-3 text-sm text-gray-700">
            {caseSummary.summary}
          </div>
        )}
        {/* Expanded evidence / unresolved — shown ONLY for facts that still need attention.
            A green fact is hidden here (its tile tick is the whole story). */}
        {(app.verdict || []).some((f) => factTileTone(f) !== 'green' && (f.evidence.length > 1 || f.unresolved.length > 0)) && (
          <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
            {(app.verdict || []).map((f) => {
              const resolve = (it: AdminVerdictItem) =>
                t(`admin.scholarship.verdict.item.${verdictItemKey(it)}`,
                  localiseParams(it.params, t))
              if (factTileTone(f) === 'green' || (f.evidence.length <= 1 && f.unresolved.length === 0)) return null
              return (
                <div key={`detail-${f.fact}`} className="text-xs text-gray-600">
                  <span className="font-medium text-gray-500 uppercase text-[10px] tracking-wide">
                    {t(`admin.scholarship.verdict.fact.${f.fact}`)}
                  </span>
                  {/* Findings first (the active reasoning — e.g. the STR verdict leads the
                      income story), then the supporting confirmations. */}
                  {f.unresolved.map((it, i) => (
                    <div key={`u${i}`} className="ml-2 flex items-start gap-1 mt-0.5">
                      <span className="text-amber-600 shrink-0">•</span>
                      <span>{resolve(it)}</span>
                    </div>
                  ))}
                  {f.evidence.slice(1).map((it, i) => (
                    <div key={`e${i}`} className="ml-2 flex items-start gap-1 mt-0.5">
                      <span className="text-green-600 shrink-0">✓</span>
                      <span>{resolve(it)}</span>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Student profile (system-generated: draft at handoff → final at verdict) ── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">
            {t(profile?.final_markdown ? 'admin.scholarship.profileFinalTitle' : 'admin.scholarship.profileTitle')}
          </h2>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">{t('admin.scholarship.genLang')}</label>
            <select value={genLang} onChange={(e) => setGenLang(e.target.value)} disabled={!!busy}
              className="border rounded-lg px-2 py-1 text-sm">
              <option value="en">English</option>
              <option value="ms">Bahasa Melayu</option>
            </select>
          </div>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-primary-100 bg-primary-50 p-2 text-xs text-primary-800">
          <span aria-hidden>ⓘ</span>
          <span>{t(profile?.final_markdown ? 'admin.scholarship.profileFinalHint' : 'admin.scholarship.profileDraftHint')}</span>
        </div>

        {!profile || !(profile.final_markdown || profile.current_markdown) ? (
          <p className="text-sm text-gray-400">{t('admin.scholarship.profilePending')}</p>
        ) : (
          <>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
              {profile.final_markdown || profile.current_markdown}
            </div>
            <p className="text-xs text-gray-400">
              {profile.final_markdown
                ? `${t('admin.scholarship.finalProfile.title')} · ${profile.final_model_used || '—'}`
                : `${t('admin.scholarship.model')}: ${profile.model_used || '—'}`}
            </p>
          </>
        )}
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </div>

      {/* ── The student's own words — collapsed by default. The reviewer's job is to
           check & sign off the AI profile above; the raw note/story/funding is the
           safety valve, revealed on demand. ──────────────────────────────────────── */}
      {(() => {
        const hasStory = !!(app.aspirations || app.plans || app.fears || app.justification
          || app.daily_life || app.first_in_family || app.parents_occupation
          || app.siblings_studying_count || app.siblings_in_school || app.siblings_in_tertiary
          || app.family_context)
        // #6: the legacy single "siblings studying" count is superseded by the
        // school/tertiary split. Show it ONLY as a fallback for old rows that have a
        // positive legacy count but no split yet (migration 0044 left those null) —
        // captioned so the officer knows to confirm the breakdown at interview.
        const showLegacySiblings = app.siblings_in_school == null
          && app.siblings_in_tertiary == null
          && (app.siblings_studying_count ?? 0) > 0
        if (!(app.uncertainty_note || app.anything_else || hasStory || app.funding_need)) return null
        return (
        <div className="space-y-4">
          <button
            onClick={() => setShowOwnWords((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-primary-600 hover:underline"
          >
            <span aria-hidden>{showOwnWords ? '▾' : '▸'}</span>
            {t('admin.scholarship.ownWords.toggle')}
          </button>
          {showOwnWords && (<>
            {/* Student's note — both free-text memos in one box, each question labelled. */}
            {(app.uncertainty_note || app.anything_else) && (
              <Card title={t('admin.scholarship.studentNote')}>
                <div className="space-y-3">
                  {app.uncertainty_note && (
                    <div>
                      <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('scholarship.apply.plan.uncertainNoteLabel')}</dt>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{app.uncertainty_note}</p>
                    </div>
                  )}
                  {app.anything_else && (
                    <div>
                      <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('scholarship.apply.anythingElseLabel')}</dt>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{app.anything_else}</p>
                    </div>
                  )}
                </div>
              </Card>
            )}

            {/* Your story — post-shortlist; hidden until the student fills it */}
            {hasStory && (
              <Card title={t('admin.scholarship.sec.story')}>
                <div className="space-y-2">
                  <Field label={t('admin.scholarship.aspirations')} value={app.aspirations} />
                  <Field label={t('admin.scholarship.plans')} value={app.plans} />
                  <Field label={t('admin.scholarship.fears')} value={app.fears} />
                  <Field label={t('admin.scholarship.dailyLife')} value={app.daily_life} />
                  <Field label={t('admin.scholarship.justification')} value={app.justification} />
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 pt-1 md:grid-cols-3">
                    <Field label={t('admin.scholarship.firstInFamily')} value={yn(app.first_in_family)} />
                    <Field label={t('admin.scholarship.parentsOccupation')} value={app.parents_occupation} />
                    <Field label={t('admin.scholarship.siblingsInSchool')} value={app.siblings_in_school} />
                    <Field label={t('admin.scholarship.siblingsInTertiary')} value={app.siblings_in_tertiary} />
                    {showLegacySiblings && (
                      <Field label={t('admin.scholarship.siblingsStudying')} value={`${app.siblings_studying_count} — ${t('admin.scholarship.siblingsLegacyNote')}`} />
                    )}
                  </dl>
                  <Field label={t('admin.scholarship.familyContext')} value={app.family_context} />
                </div>
              </Card>
            )}

            {/* Funding — hidden when empty */}
            {app.funding_need && (
              <Card title={t('admin.scholarship.sec.funding')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 md:grid-cols-3">
                  <Field label={t('admin.scholarship.funding')} value={joinOr(app.funding_need.categories)} />
                  <Field label={t('admin.scholarship.programmeMonths')} value={app.funding_need.programme_months} />
                </dl>
                {app.funding_need.funding_note && <div className="mt-2"><Field label={t('admin.scholarship.fundingNote')} value={app.funding_need.funding_note} /></div>}
              </Card>
            )}
          </>)}
        </div>
        )
      })()}

      {/* ── Check 2 — Outstanding: student-facing tasks only (queries + doc requests).
           Interview flags + AI gaps now live in the Interview Stage box below. ─────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.outstanding.title')}</h2>
            <p className="text-xs text-gray-500">{t('admin.scholarship.outstanding.subtitle')}</p>
          </div>
          {(() => {
            const n = app.resolution_items?.length ?? 0
            return n > 0 ? (
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">
                {n} {n === 1 ? t('admin.scholarship.outstanding.itemOne') : t('admin.scholarship.outstanding.itemMany')}
              </span>
            ) : null
          })()}
        </div>
        {queryingLocked && (
          <p className="rounded-md bg-gray-100 px-3 py-2 text-xs text-gray-500">
            {t('admin.scholarship.outstanding.locked')}
          </p>
        )}
        {/* V3 (#7): a higher-priority query crowded out by the clarify cap stays visible here,
            so a capped-out gap isn't silently dropped. */}
        {(app.query_sla?.clarify_overflow ?? 0) > 0 && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700">
            {t('admin.scholarship.outstanding.overflow', { n: String(app.query_sla.clarify_overflow) })}
          </p>
        )}
        {(() => {
          const caveats: AdminResolutionItem[] = app.resolution_items ?? []
          if (caveats.length === 0) {
            return <p className="text-sm text-gray-400 italic">{t('admin.scholarship.outstanding.empty')}</p>
          }
          return (
                  <ul className="space-y-2">
                    {caveats.map((item) => {
                      const answered = item.status === 'resolved'  // student answered; awaiting officer review
                      // Show the ACTUAL question the student was asked (same source as their
                      // Action Centre), not the internal caveat description.
                      const src = titleSourceFor(item)
                      const question = src.kind === 'raw'
                        ? (src.text || item.code)
                        : t(src.titleKey, localiseParams(item.params, t))
                      // The FULL instruction the STUDENT actually saw (auto items carry a detailed
                      // description; a manual request's raw `text` above already IS the full ask). Show
                      // it so the reviewer sees EXACTLY what was asked, next to the student's answer.
                      // Strip markdown emphasis (*…*) for a clean plain-text read; hide when there's no
                      // desc key (t() echoes the key path) or it just repeats the title.
                      let detail = ''
                      if (src.kind === 'i18n') {
                        const d = t(src.descKey, localiseParams(item.params, t))
                        if (d && d !== src.descKey && d !== question) {
                          detail = d.replace(/\*([^*]+)\*/g, '$1')
                        }
                      }
                      return (
                        <li key={item.id} className="flex items-start gap-2.5 rounded-lg border border-gray-100 bg-gray-50 p-3">
                          {answered ? (
                            <svg className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" viewBox="0 0 20 20" fill="currentColor" aria-label="Answered">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                            </svg>
                          ) : (
                            <svg className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" viewBox="0 0 20 20" fill="currentColor" aria-label="Awaiting student">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-13a.75.75 0 00-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 000-1.5h-3.25V5z" clipRule="evenodd" />
                            </svg>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-800 break-words">
                              {/* A document request is a task ("Upload"), not a "Question" — label by kind. */}
                              <span className="font-semibold">{item.kind === 'doc' ? t('admin.scholarship.outstanding.uploadLabel') : t('admin.scholarship.outstanding.questionLabel')}:</span> {question}
                              {' '}
                              <span className="ml-0.5 rounded bg-gray-200 px-1.5 py-0.5 text-[11px] text-gray-500 align-middle">{item.fact}</span>
                              {' '}
                              <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[11px] text-gray-500 align-middle">{item.kind}</span>
                              {/* Circuit-breaker (Phase 2/4): the student re-uploaded past the limit
                                  without a usable doc — the loop was stopped and their best copy kept
                                  live. A HOLD for a human, not an auto-resolve. */}
                              {item.params?.needs_officer_eye === true && (
                                <>
                                  {' '}
                                  <span
                                    title={t('admin.scholarship.outstanding.holdTip')}
                                    className="rounded bg-orange-100 px-1.5 py-0.5 text-[11px] font-semibold text-orange-700 align-middle"
                                  >
                                    {t('admin.scholarship.outstanding.hold')}
                                  </span>
                                </>
                              )}
                            </p>
                            {detail && (
                              <p className="mt-1 text-xs text-gray-500 break-words">{detail}</p>
                            )}
                            {answered && item.resolution_text && (
                              <div className="mt-2 rounded-md border border-primary-100 bg-primary-50 p-2">
                                <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-700">
                                  {t('admin.scholarship.caveats.studentAnswer')}
                                </p>
                                <p className="mt-0.5 text-sm text-gray-800 break-words">{item.resolution_text}</p>
                              </div>
                            )}
                          </div>
                          {/* Answered items are auto-accepted (the Q&A is the record — no
                              officer action). Only an unanswered item offers Delete, for
                              the reviewer to drop an irrelevant / poorly-worded query so
                              they can raise a better one. */}
                          {canWrite && !queryingLocked && !answered && (
                            <div className="flex shrink-0">
                              <button
                                onClick={() => doActionResolution(item.id, 'waive')}
                                disabled={!!busy}
                                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:border-red-300 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                              >
                                {t('admin.scholarship.caveats.delete')}
                              </button>
                            </div>
                          )}
                        </li>
                      )
                    })}
                  </ul>
          )
        })()}
        {/* Raise work for the student — merged into the Check-2 box with a clear divider.
            Two roles: (1) raise a query, (2) request a document. Each adds a to-do to the
            student's Action Centre (they're notified there — no separate per-item email). */}
        {canWrite && !queryingLocked && (
          <div className="border-t border-gray-200 pt-3 mt-1 space-y-3">
            <p className="text-xs text-gray-500">{t('admin.scholarship.raiseSectionHint')}</p>
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-gray-600">{t('admin.scholarship.raiseQueryTitle')}</p>
              <textarea name="infoNote" value={infoNote} rows={2} onChange={(e) => setInfoNote(e.target.value)}
                placeholder={t('admin.scholarship.raiseQueryPlaceholder')}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
              <button onClick={doRaiseQuery} disabled={!!busy || !infoNote.trim()}
                className="px-3 py-1.5 border border-primary-300 text-primary-700 rounded-lg text-sm disabled:opacity-50">
                {busy === 'raise' ? t('common.loading') : t('admin.scholarship.raiseQuerySend')}
              </button>
            </div>
            <div className="space-y-1.5 border-t border-gray-100 pt-3">
              <p className="text-xs font-medium text-gray-600">{t('admin.scholarship.requestDocTitle')}</p>
              {(() => {
                const cat = REQ_CAT.get(reqCategory)
                return (
              <div className="flex flex-wrap items-center gap-2">
                <select value={reqCategory} onChange={(e) => onReqCategory(e.target.value)}
                  className="border rounded-lg px-2 py-1.5 text-sm">
                  <option value="">{t('admin.scholarship.requestDocAny')}</option>
                  {REQUEST_CATEGORIES.map((c) => (
                    <option key={c.key} value={c.key}>{t(`admin.scholarship.requestCat.${c.key}`)}</option>
                  ))}
                </select>
                {/* Context-aware qualifier: "Whose?" (person) or "Which?" (sub-type). Required. */}
                {cat?.qualifier === 'whose' && (
                  <select value={reqQualifier} onChange={(e) => onReqQualifier(e.target.value)}
                    className="border rounded-lg px-2 py-1.5 text-sm">
                    <option value="">{t('admin.scholarship.requestDocWhose')}</option>
                    {cat.members!.map((m) => (
                      <option key={m} value={m}>{t(`scholarship.docs.income.wizard.member.${m}`)}</option>
                    ))}
                  </select>
                )}
                {cat?.qualifier === 'which' && (
                  <select value={reqQualifier} onChange={(e) => onReqQualifier(e.target.value)}
                    className="border rounded-lg px-2 py-1.5 text-sm">
                    <option value="">{t('admin.scholarship.requestDocWhich')}</option>
                    {cat.options!.map((o) => (
                      <option key={o.value} value={o.value}>{t(`admin.scholarship.requestWhich.${o.value}`)}</option>
                    ))}
                  </select>
                )}
              </div>
                )
              })()}
              {reqCategory && (
                <>
                  <textarea value={reqDocNote} rows={2} onChange={(e) => setReqDocNote(e.target.value)}
                    placeholder={t('admin.scholarship.requestDocNotePlaceholder')}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                  {/* Enabled ONLY once the request resolves (qualifier chosen where required); a
                      generic "Other" still needs a note describing exactly what's wanted. */}
                  <button onClick={doRequestDoc}
                    disabled={!!busy || !reqResolved || (reqResolved.docType === 'other' && !reqDocNote.trim())}
                    className="px-3 py-1.5 border border-primary-300 text-primary-700 rounded-lg text-sm disabled:opacity-50">
                    {busy === 'reqdoc' ? t('common.loading') : t('admin.scholarship.requestDocSend')}
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Referees (consent panel removed — the consent RECORD + sponsor-share gating
           stay untouched; only the cockpit status line is gone). Behind SHOW_REFEREES. ── */}
      {SHOW_REFEREES && (
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-sm mb-1">{t('admin.scholarship.referees')}</h3>
        <p className="text-xs text-gray-400 mb-2">{t('admin.scholarship.refHint')}</p>
        <ul className="text-sm text-gray-600 space-y-1">
          {app.referees.map((r) => (
            <li key={r.id} className="flex items-start justify-between gap-2">
              <span>
                {r.name}{r.role ? ` (${r.role})` : ''}{r.relationship ? ` · ${r.relationship}` : ''}
                {r.phone ? ` — ${r.phone}` : ''}{r.email ? ` · ${r.email}` : ''}
              </span>
              <button onClick={() => doDeleteReferee(r.id)} disabled={!!busy}
                className="text-red-500 hover:underline text-xs shrink-0 disabled:opacity-50">
                {t('admin.scholarship.refRemove')}
              </button>
            </li>
          ))}
          {app.referees.length === 0 && <li className="text-gray-400">{t('admin.scholarship.none')}</li>}
        </ul>
        {/* Add referee (coordinator records it at verify-&-accept) */}
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input value={refForm.name} onChange={(e) => setRefForm((f) => ({ ...f, name: e.target.value }))}
            placeholder={t('admin.scholarship.refName')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.role} onChange={(e) => setRefForm((f) => ({ ...f, role: e.target.value }))}
            placeholder={t('admin.scholarship.refRole')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.relationship} onChange={(e) => setRefForm((f) => ({ ...f, relationship: e.target.value }))}
            placeholder={t('admin.scholarship.refRelationship')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.phone} onChange={(e) => setRefForm((f) => ({ ...f, phone: formatPhone(e.target.value) }))}
            placeholder={t('admin.scholarship.refPhone')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.email} onChange={(e) => setRefForm((f) => ({ ...f, email: e.target.value }))}
            placeholder={t('admin.scholarship.refEmail')} className="border rounded-lg px-2 py-1 text-sm sm:col-span-2" />
        </div>
        <button onClick={doAddReferee} disabled={!!busy || !refForm.name.trim()}
          className="mt-2 px-3 py-1.5 bg-primary-500 text-white rounded-lg text-sm disabled:opacity-50">
          {busy === 'ref' ? t('admin.scholarship.refAdding') : t('admin.scholarship.refAdd')}
        </button>
      </div>
      )}

      {/* Interview scheduling — the assigned reviewer proposes times (dark behind the flag) */}
      {app.interview_schedule?.enabled && app.assigned_to_id != null &&
        ['profile_complete', 'interviewing'].includes(app.status) && (
        <InterviewScheduleCard
          appId={id} token={token || ''} schedule={app.interview_schedule}
          onChange={(s) => setApp((prev) => (prev ? { ...prev, interview_schedule: s } : prev))}
        />
      )}

      {/* Phase C: interview capture */}
      <div id="interview-section" className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.interview.title')}</h2>
          </div>
          {interviewLocked
            ? (canWrite && !decisionRecorded && (
                /* Reviewer reopens a submitted interview to add a forgotten finding — un-submits
                   (reopens this box AND Check 2; Approve/Decline switch off until re-submitted).
                   Post-decision, the Decision panel's Reopen is used instead. */
                <button onClick={doReopenInterview} disabled={!!busy}
                  className="rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-100 disabled:opacity-50">
                  {busy === 'ivreopen' ? t('common.loading') : t('admin.scholarship.interview.reopen')}
                </button>
              ))
            : (canWrite && (
                <button onClick={doSuggestGaps} disabled={!!busy}
                  className="px-2.5 py-1 rounded-lg text-xs bg-primary-600 text-white disabled:opacity-50">
                  {busy === 'gaps' ? t('admin.scholarship.gaps.running')
                    : (app.interview_gaps?.length ?? 0) > 0 ? t('admin.scholarship.gaps.more')
                    : t('admin.scholarship.gaps.button')}
                </button>
              ))}
        </div>

        {/* S4: the sponsor's interviewer guide — the three "what we need to know" buckets +
            their key probes, as a collapsible reference. The AI gaps above target whichever
            buckets the record leaves unanswered; this is the human checklist behind them. */}
        {canWrite && !interviewLocked && (
          <details className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
            <summary className="cursor-pointer text-xs font-medium text-gray-600">
              {t('admin.scholarship.interviewGuide.title')}
            </summary>
            <div className="mt-2 space-y-2">
              {(['academic', 'financial', 'pathway'] as const).map((b) => (
                <div key={b}>
                  <p className="text-xs font-semibold text-gray-700">{t(`admin.scholarship.interviewGuide.${b}.title`)}</p>
                  <ul className="ml-4 list-disc text-[11px] text-gray-500">
                    {[0, 1, 2].map((i) => {
                      const key = `admin.scholarship.interviewGuide.${b}.q${i}`
                      const txt = t(key)
                      return txt === key ? null : <li key={i}>{txt}</li>
                    })}
                  </ul>
                </div>
              ))}
              <p className="text-[11px] text-gray-400">{t('admin.scholarship.interviewGuide.note')}</p>
            </div>
          </details>
        )}

        {interviewLocked ? (
          /* Submitted → read-only record (Check-2 style blue boxes). Questions with no
             answer are dropped; the open-ended findings show in their own box. */
          (() => {
            const answered = agendaItems.filter((it) => {
              const f = findings[it.code]
              return f && f.verdict !== 'deleted' && ((f.rationale || '').trim() || f.verdict === 'resolved')
            })
            const hasNote = (note || '').trim().length > 0
            if (answered.length === 0 && !hasNote) {
              return <p className="text-sm text-gray-400 italic">{t('admin.scholarship.interview.noneRecorded')}</p>
            }
            return (
              <div className="space-y-3">
                {/* Q&A organised like Check 2: ✓ tick · bold "Question:" · the finding under
                    a "Reviewer's finding" header (the label sits ABOVE the box, not inside). */}
                {answered.map((it) => {
                  const f = findings[it.code]
                  return (
                    <div key={it.code} className="flex items-start gap-2.5 rounded-lg border border-gray-100 bg-gray-50 p-3">
                      <svg className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" viewBox="0 0 20 20" fill="currentColor" aria-label="Answered">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                      </svg>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-800 break-words">
                          <span className="font-semibold">{t('admin.scholarship.outstanding.questionLabel')}:</span> {it.label}
                          {it.ai && <span className="ml-1 rounded bg-primary-600 px-1.5 py-0.5 text-[10px] font-semibold text-white align-middle">{t('admin.scholarship.gaps.aiBadge')}</span>}
                        </p>
                        <p className="mt-1.5 text-xs font-medium text-gray-600">{t('admin.scholarship.interview.answerLabel')}</p>
                        <div className="mt-0.5 rounded-md border border-blue-100 bg-blue-50/50 p-2">
                          <p className="text-sm text-gray-800 break-words">
                            {(f.rationale || '').trim() || `${t('admin.scholarship.interview.verdict.resolved')} ✓`}
                          </p>
                        </div>
                      </div>
                    </div>
                  )
                })}
                {hasNote && (
                  <div>
                    <p className="text-xs font-medium text-gray-600 mb-1">{t('admin.scholarship.interview.findingsLabel')}</p>
                    <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-3">
                      <p className="whitespace-pre-line text-sm text-gray-800">{note}</p>
                    </div>
                  </div>
                )}
                {app.interview_session?.submitted_at && (
                  <p className="text-[11px] text-gray-400">
                    {t('admin.scholarship.interview.submittedOn')} {formatDate(app.interview_session.submitted_at)}
                  </p>
                )}
              </div>
            )
          })()
        ) : (
          <>
            <p className="text-xs text-gray-500">{t('admin.scholarship.interview.intro')}</p>
            {editableAgenda.length === 0 ? (
              <p className="text-sm text-gray-400 italic">{t('admin.scholarship.interview.noFlags')}</p>
            ) : (
              <ul className="space-y-3">
                {editableAgenda.map((it) => {
                  const f = findings[it.code] ?? { verdict: '', rationale: '' }
                  const setF = (patch: Partial<{ verdict: string; rationale: string }>) =>
                    setFindings((prev) => ({ ...prev, [it.code]: { ...f, ...patch } }))
                  const resolved = f.verdict === 'resolved'
                  return (
                    <li key={it.code} className="border rounded-lg p-3">
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm text-gray-800 min-w-0">
                          {it.ai && <span className="mr-1 rounded bg-primary-600 px-1.5 py-0.5 text-[10px] font-semibold text-white align-middle">{t('admin.scholarship.gaps.aiBadge')}</span>}
                          {it.label}
                        </p>
                        {canWrite && (
                          <div className="flex shrink-0 gap-1.5">
                            <button onClick={() => doDeleteAgendaItem(it.code)} disabled={!!busy}
                              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:border-red-300 hover:bg-red-50 hover:text-red-700 disabled:opacity-50">
                              {t('admin.scholarship.caveats.delete')}
                            </button>
                            <button onClick={() => setF({ verdict: resolved ? '' : 'resolved' })}
                              className={`rounded px-2 py-1 text-xs font-medium ${resolved ? 'bg-emerald-600 text-white hover:bg-emerald-700' : 'border border-gray-300 text-gray-700 hover:bg-gray-100'}`}>
                              {t('admin.scholarship.interview.verdict.resolved')}
                            </button>
                          </div>
                        )}
                      </div>
                      <input
                        value={f.rationale} maxLength={140} disabled={!canWrite}
                        onChange={(e) => setF({ rationale: e.target.value })}
                        placeholder={t('admin.scholarship.interview.rationalePlaceholder')}
                        className="mt-2 w-full border rounded-lg px-3 py-1.5 text-sm"
                      />
                    </li>
                  )
                })}
              </ul>
            )}
            <textarea value={note} disabled={!canWrite} rows={2}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t('admin.scholarship.interview.notePlaceholder')}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
            {canWrite && (
              <div className="flex items-center gap-2">
                <button onClick={doSaveInterview} disabled={!!busy}
                  className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50">
                  {busy === 'iv' ? t('common.loading') : t('admin.scholarship.interview.saveDraft')}
                </button>
                <button onClick={doSubmitInterview} disabled={!!busy}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm disabled:opacity-50">
                  {busy === 'ivs' ? t('common.loading') : t('admin.scholarship.interview.submit')}
                </button>
                {interviewMsg && <span className="text-sm font-medium text-green-600">{interviewMsg}</span>}
              </div>
            )}
          </>
        )}
      </div>


      {/* ── Documents drawer — grouped by fact ────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-3">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.docsDrawer.title')} ({app.documents.length})</h2>
          <p className="text-xs text-gray-400">{t('admin.scholarship.docsDrawer.subtitle')}</p>
        </div>
        {(() => {
          const groups = groupDocumentsByFact(app.documents)
          const sectionKeys = ['identity', 'academic', 'pathway', 'income', 'additional', 'other'] as const
          const pillClass = (p: 'verified' | 'check' | 'unread') => {
            if (p === 'verified') return 'bg-green-100 text-green-700'
            if (p === 'check') return 'bg-amber-100 text-amber-700'
            return 'bg-gray-100 text-gray-500'
          }
          // The doc-type icon sits in a badge tinted by the SAME verdict as the pill.
          const iconBadge = (p: 'verified' | 'check' | 'unread') =>
            p === 'verified' ? 'bg-green-50' : p === 'check' ? 'bg-amber-50' : 'bg-gray-100'
          const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)
          // Standard, student-independent label per doc type (the actual filename is shown
          // muted in brackets below). parent_ic → "Mother's IC" etc. when the earner is known.
          const TYPE_KEYS = new Set(['ic', 'parent_ic', 'results_slip', 'offer_letter', 'str',
            'salary_slip', 'epf', 'income_support_doc', 'school_leaving_cert', 'semester_result',
            'water_bill', 'electricity_bill', 'birth_certificate', 'guardianship_letter',
            'statement_of_intent', 'photo', 'bank_statement', 'other'])
          // Income-earner docs are person-qualified from their slot ("Mother's STR proof",
          // "Father's salary slip"); the IC keeps its own possessive ("Mother's IC").
          const INCOME_MEMBER_DOCS = new Set(['parent_ic', 'str', 'salary_slip', 'epf'])
          const docLabel = (d: AdminApplicantDocument) => {
            if (INCOME_MEMBER_DOCS.has(d.doc_type)) {
              const m = earnerMemberFor(d.doc_type, d.household_member || '',
                app.income_route || '', app.income_earner || '')
              const base = t(`admin.scholarship.docsDrawer.type.${d.doc_type}`)
              if (!m) return base
              const member = t(`scholarship.docs.income.wizard.member.${m}`)
              return d.doc_type === 'parent_ic'
                ? t('admin.scholarship.docsDrawer.parentIcOf', { member })
                : t('admin.scholarship.docsDrawer.ofMember', { member, doc: base })
            }
            return TYPE_KEYS.has(d.doc_type)
              ? t(`admin.scholarship.docsDrawer.type.${d.doc_type}`)
              : (d.original_filename || d.doc_type)
          }
          // Open the document in the in-cockpit viewer (embedded, never a download).
          const openViewer = (d: AdminApplicantDocument) => {
            if (!d.download_url) return
            setViewerDoc({
              label: docLabel(d), filename: d.original_filename || '', url: d.download_url,
              kind: viewerKind(d.content_type || '', d.original_filename || ''),
            })
          }
          const factClass = (s: FactStatus) =>
            s === 'verified' ? 'text-green-600' : s === 'partial' ? 'text-amber-600'
              : s === 'not' ? 'text-red-600' : 'text-gray-400'
          const subLabel = 'text-[10px] font-semibold uppercase tracking-widest text-gray-400 mb-1.5'
          // Line 2: the coloured fact-labels — only the facts THIS document provides. A results slip
          // also surfaces the SPM exam YEAR, an offer letter its intake (course-start) YEAR — coloured
          // by currency vs the cohort (green = current, amber = off), so the officer sees at a glance
          // whether the slip/offer belongs to this round.
          const yearChip = (d: AdminApplicantDocument): { text: string; status: string } | null => {
            if (d.doc_type === 'results_slip' && d.academic_check?.exam_year)
              return { text: t('admin.scholarship.docsDrawer.examYear', { year: d.academic_check.exam_year }),
                       status: d.academic_check.exam_year_status || '' }
            if (d.doc_type === 'offer_letter' && d.pathway_check?.intake_year)
              return { text: t('admin.scholarship.docsDrawer.intakeYear', { year: d.pathway_check.intake_year }),
                       status: d.pathway_check.intake_year_status || '' }
            return null
          }
          const yearClass = (s: string) =>
            s === 'current' ? 'text-green-600' : s === 'off' ? 'text-amber-600' : 'text-gray-500'
          const factLine = (d: AdminApplicantDocument) => {
            const facts = documentFacts(d)
            const yc = yearChip(d)
            if (facts.length === 0 && !yc) return null
            return (
              <p className="mt-0.5 flex flex-wrap items-center text-[11px]">
                {facts.map((f, i) => (
                  <span key={`${f.key}-${i}`} className="flex items-center">
                    {i > 0 && <span className="text-gray-300 mx-1.5">·</span>}
                    <span className={`font-medium ${factClass(f.status)}`}>
                      {t(`admin.scholarship.docsDrawer.fact.${f.key}`)}
                    </span>
                  </span>
                ))}
                {yc && (
                  <span className="flex items-center">
                    {facts.length > 0 && <span className="text-gray-300 mx-1.5">·</span>}
                    <span className={`font-medium ${yearClass(yc.status)}`}>{yc.text}</span>
                  </span>
                )}
              </p>
            )
          }
          // Placeholder label for a missing compulsory income doc (+ the member, salary route).
          const slotLabel = (docType: string, member: string) => {
            const base = t(`admin.scholarship.docsDrawer.type.${docType}`)
            if (!member) return base
            const m = t(`scholarship.docs.income.wizard.member.${member}`)
            return docType === 'parent_ic'
              ? t('admin.scholarship.docsDrawer.parentIcOf', { member: m })
              : t('admin.scholarship.docsDrawer.ofMember', { member: m, doc: base })
          }
          const docRow = (d: AdminApplicantDocument) => {
            const p = documentPill(d)
            return (
              <li key={d.id} className="flex items-start gap-2 rounded-lg border border-gray-100 p-2.5 hover:bg-gray-50">
                <span className={`shrink-0 mt-0.5 flex h-7 w-7 items-center justify-center rounded-md text-sm ${iconBadge(p)}`} aria-hidden>
                  {docIconFor(d.doc_type)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {d.download_url ? (
                      <button type="button" onClick={() => openViewer(d)}
                        title={t('admin.scholarship.docsDrawer.view')}
                        className="text-left text-sm font-medium text-gray-800 hover:text-primary-600 hover:underline truncate max-w-[200px]">
                        {docLabel(d)} <span aria-hidden className="text-[10px] text-gray-400">↗</span>
                      </button>
                    ) : (
                      <span className="text-sm font-medium text-gray-800 truncate max-w-[200px]">
                        {docLabel(d)}
                      </span>
                    )}
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${pillClass(p)}`}>
                      {t(`admin.scholarship.docsDrawer.pill.${p}`)}
                    </span>
                    {/* Capture confidence: read deterministically (fixed labels) or by AI? Shown on
                        every read doc — field-extracted docs AND the identity ICs (read via the MyKad
                        OCR path). The stored `capture` tag wins; when absent (older extractions) the
                        default is doc-type-aware: an IC/parent_ic is deterministic Vision OCR → 'Exact',
                        everything else → 'AI' (the safe "please verify" label). So no read doc is ever
                        unlabelled, and a later Re-run stamps the precise tag. */}
                    {(d.vision_fields?.fields || d.doc_type === 'ic' || d.doc_type === 'parent_ic') && (() => {
                      const stored = d.vision_fields?.capture
                      // The stored tag always wins. When absent (older extractions), default by the
                      // doc type's PRIMARY read method: the deterministic-first types (a label/positional
                      // parser runs before any Gemini fallback) default to 'Exact'; the rest — read by
                      // Gemini — default to 'AI'. A Re-run stamps the precise tag either way.
                      const DETERMINISTIC_FIRST = ['ic', 'parent_ic', 'results_slip', 'birth_certificate', 'str', 'epf', 'school_leaving_cert']
                      const cap = stored === 'deterministic' ? 'deterministic'
                        : stored === 'ai' ? 'ai'
                        : DETERMINISTIC_FIRST.includes(d.doc_type) ? 'deterministic' : 'ai'
                      return (
                        <span
                          title={t(`admin.scholarship.docsDrawer.capture.${cap}.hint`)}
                          className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                            cap === 'deterministic'
                              ? 'bg-slate-100 text-slate-500' : 'bg-violet-50 text-violet-500'}`}>
                          {t(`admin.scholarship.docsDrawer.capture.${cap}.label`)}
                        </span>
                      )
                    })()}
                  </div>
                  {d.original_filename && (
                    <p className="text-[11px] text-gray-400 truncate max-w-[230px]" title={d.original_filename}>
                      ({trunc(d.original_filename, 30)})
                    </p>
                  )}
                  {factLine(d)}
                  {/* Key values FIRST (directly under the facts), so every note falls below them —
                      consistent for both water and electricity. */}
                  {(() => {
                    const vals = utilityBillValues(d)
                    return vals.length > 0 ? (
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        {vals.map((v, i) => (
                          <span key={v.labelKey}>
                            {i > 0 && <span className="text-gray-300"> · </span>}
                            <span className="text-gray-400">{t(`admin.scholarship.docsDrawer.billValue.${v.labelKey}`)} </span>
                            {v.value ?? t(`admin.scholarship.docsDrawer.billValue.${v.valueKey}`)}
                          </span>
                        ))}
                      </p>
                    ) : null
                  })()}
                  {/* School-leaving cert values (owner 2026-07-15): the school name, the conduct
                      rating, and the co-curricular / leadership notes — under the School/Name/IC/
                      Behaviour chips. */}
                  {(() => {
                    const vals = schoolLeavingValues(d)
                    return vals.length > 0 ? (
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        {vals.map((v, i) => (
                          <span key={v.labelKey}>
                            {i > 0 && <span className="text-gray-300"> · </span>}
                            <span className="text-gray-400">{t(`admin.scholarship.docsDrawer.certValue.${v.labelKey}`)} </span>
                            {v.value}
                          </span>
                        ))}
                      </p>
                    ) : null
                  })()}
                  {d.utility_check?.name_note === 'unrelated' && (
                    <p className="text-[11px] text-orange-600 mt-0.5">
                      {t('admin.scholarship.docsDrawer.utilityNote.unrelated', { name: d.utility_check.name })}
                    </p>
                  )}
                  {(d.utility_check?.reasonable_detail === 'water_only'
                    || d.utility_check?.reasonable_detail === 'electricity_only') && (
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {t(`admin.scholarship.docsDrawer.utilityNote.${d.utility_check.reasonable_detail}`)}
                    </p>
                  )}
                  {d.vision_fields?.warnings && d.vision_fields.warnings.length > 0 && (
                    <p className="text-[11px] text-amber-600 mt-0.5">{d.vision_fields.warnings.join('; ')}</p>
                  )}
                </div>
                <div className="shrink-0 flex flex-col items-end gap-0.5 mt-0.5">
                  <button onClick={() => doReRunVision(d.id)} disabled={busy === 'vision'}
                    className="text-[11px] text-gray-500 hover:text-gray-700 hover:underline disabled:opacity-50">
                    {busy === 'vision' ? t('common.loading') : t('admin.scholarship.docsDrawer.rerun')}
                  </button>
                </div>
              </li>
            )
          }
          const placeholderRow = (s: IncomeSlot) => (
            <li key={`ph-${s.docType}-${s.member}`}
              className="flex items-center gap-2 rounded-lg border border-dashed border-gray-200 p-2.5">
              <span className="shrink-0 text-gray-300 text-base" aria-hidden>
                {s.docType === 'parent_ic' ? '🪪' : '📄'}
              </span>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-gray-500">{slotLabel(s.docType, s.member)}</span>
                <span className="text-[11px] text-gray-400"> — {t('admin.scholarship.docsDrawer.notUploaded')}</span>
              </div>
              <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold bg-red-100 text-red-600">
                {t('admin.scholarship.docsDrawer.pill.missing')}
              </span>
            </li>
          )
          return (
            // Fixed-height, scrollable: a long document list (11+) no longer pushes the
            // rest of the cockpit down — the header stays put and the groups scroll.
            <div className="space-y-4 max-h-[28rem] overflow-y-auto pr-1">
              {sectionKeys.map((key) => {
                const docs = groups[key]
                if (key === 'income') {
                  // Income splits into STR ROUTE / SALARY ROUTE / UTILITY sub-sections. STR is
                  // shown only on the STR route with an STR doc; SALARY + UTILITY always (when
                  // they have content). A missing compulsory slot renders a "Missing" placeholder.
                  const sub = incomeSubSections(app, docs)
                  const subHead = 'text-[9px] font-semibold uppercase tracking-wider text-gray-300 mb-1 mt-2'
                  const subSection = (headKey: string, slots: IncomeSlot[]) => (
                    slots.length === 0 ? null : (
                      <div key={headKey}>
                        <p className={subHead}>{t(`admin.scholarship.docsDrawer.group.${headKey}`)}</p>
                        <ul className="space-y-1.5">
                          {slots.map((s) => (s.doc ? docRow(s.doc) : placeholderRow(s)))}
                        </ul>
                      </div>
                    )
                  )
                  if (docs.length === 0 && !sub.str && sub.salary.length === 0 && sub.utility.length === 0) return null
                  return (
                    <div key={key}>
                      <p className={subLabel}>{t('admin.scholarship.docsDrawer.group.income')}</p>
                      {sub.str && subSection('incomeStr', sub.str)}
                      {subSection('incomeSalary', sub.salary)}
                      {subSection('incomeUtility', sub.utility)}
                    </div>
                  )
                }
                if (docs.length === 0) return null
                return (
                  <div key={key}>
                    <p className={subLabel}>{t(`admin.scholarship.docsDrawer.group.${key}`)}</p>
                    <ul className="space-y-1.5">{docs.map(docRow)}</ul>
                  </div>
                )
              })}
              {/* Phase 2: replaced documents — version history, muted, kept out of every fact
                  group so a superseded doc never reads as a live verification input. */}
              {groups.superseded.length > 0 && (
                <div key="superseded" className="pt-2 mt-2 border-t border-gray-100">
                  <p className={subLabel}>{t('admin.scholarship.docsDrawer.group.superseded')}</p>
                  <ul className="space-y-1.5 opacity-60">{groups.superseded.map(docRow)}</ul>
                </div>
              )}
              {app.documents.length === 0 && (
                <p className="text-sm text-gray-400">{t('admin.scholarship.none')}</p>
              )}
            </div>
          )
        })()}
      </div>

      </div>{/* end LEFT column */}

      {/* ═══════════════════════ RIGHT COLUMN (sticky) ══════════════════════════ */}
      <div id="record-verdict-panel" className="space-y-4 lg:sticky lg:top-4">

      {/* ── Rate AI verification — the officer's Pass/Fail over the AI's four-fact read +
           the AI's suggested verdict. Split out of the old Decision card (2026-07-04) into its
           own topmost box. Both modes: buttons while deciding, badges once recorded. ───────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.recordVerdict.rateTitle')}</h2>
        <div className="space-y-2">
          {(['identity', 'academic', 'pathway', 'income'] as const).map((fact) => (
            decisionLocked ? (
              <div key={fact} className="flex items-center justify-between gap-2 rounded-lg border border-gray-100 p-2.5">
                <span className="text-sm font-medium text-gray-700">{t(`admin.scholarship.verdict.fact.${fact}`)}</span>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  officerVerdict[fact] === 'pass' ? 'bg-green-100 text-green-700'
                  : officerVerdict[fact] === 'fail' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'}`}>
                  {officerVerdict[fact] === 'pass' ? t('admin.scholarship.recordVerdict.factPass')
                    : officerVerdict[fact] === 'fail' ? t('admin.scholarship.recordVerdict.factFail') : '—'}
                </span>
              </div>
            ) : (
              <div key={fact} className="flex items-center justify-between gap-2 rounded-lg border border-gray-100 p-2.5">
                <span className="text-sm font-medium text-gray-700">{t(`admin.scholarship.verdict.fact.${fact}`)}</span>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => setOfficerVerdict((v) => ({ ...v, [fact]: officerVerdict[fact] === 'pass' ? '' : 'pass' }))}
                    disabled={!canWrite}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      officerVerdict[fact] === 'pass'
                        ? 'border-green-500 bg-green-500 text-white'
                        : 'border-gray-300 text-gray-600 hover:border-green-400'
                    } disabled:opacity-50`}
                  >
                    {t('admin.scholarship.recordVerdict.factPass')}
                  </button>
                  <button
                    onClick={() => setOfficerVerdict((v) => ({ ...v, [fact]: officerVerdict[fact] === 'fail' ? '' : 'fail' }))}
                    disabled={!canWrite}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      officerVerdict[fact] === 'fail'
                        ? 'border-red-500 bg-red-500 text-white'
                        : 'border-gray-300 text-gray-600 hover:border-red-400'
                    } disabled:opacity-50`}
                  >
                    {t('admin.scholarship.recordVerdict.factFail')}
                  </button>
                </div>
              </div>
            )
          ))}
        </div>
        {/* AI's suggested verdict — the officer decides; this is the AI's read. */}
        {(() => {
          const sugg = aiSuggestionFor(app.verdict || [])
          const facts = ['identity', 'academic', 'pathway', 'income'] as const
          return (
            <p className="text-[11px] text-gray-400">
              {t('admin.scholarship.recordVerdict.aiSuggested')}{' '}
              {facts.map((f, i) => (
                <span key={f}>
                  {i > 0 && ', '}
                  {t(`admin.scholarship.verdict.fact.${f}`)}{' '}
                  <span className={
                    sugg[f] === 'yes' ? 'text-green-600 font-medium'
                    : sugg[f] === 'no' ? 'text-red-600 font-medium'
                    : 'text-amber-600 font-medium'
                  }>
                    {t(`admin.scholarship.recordVerdict.suggest.${sugg[f]}`)}
                  </span>
                </span>
              ))}{'.'}
            </p>
          )
        })()}
      </div>

      {/* ── Estimated need & proposed bursary — per-pathway estimated GAP after government
           coverage, PLUS the proposed bursary amount (moved out of the old Decision card). ── */}
      {(() => {
        const fe = app.funding_estimate
        const showBursary = app.award_amount != null || app.proposed_award_amount != null
        if (!fe && !showBursary) return null
        return (
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
            <h2 className="font-semibold">{t('admin.scholarship.estimate.title')}</h2>
            {fe ? (fe.known ? (
              <>
                {/* Total + its monthly breakdown are one tight unit — grouped so the card's
                    space-y doesn't push them apart. */}
                <div>
                  <p className="text-2xl font-semibold text-gray-900">
                    ≈ RM {fe.total.toLocaleString('en-US')}
                  </p>
                  <p className="text-xs text-gray-500">
                    ~RM {fe.monthly.toLocaleString('en-US')}/{t('admin.scholarship.estimate.month')} × {fe.months} {t('admin.scholarship.estimate.months')}
                  </p>
                </div>
                <p className="text-sm text-gray-600">
                  {t(`admin.scholarship.estimate.pathway.${fe.pathway}`)}
                </p>
                {fe.variable && (
                  <p className="mt-2 text-xs text-amber-700">{t('admin.scholarship.estimate.variableNote')}</p>
                )}
                {fe.practical && (
                  <p className="mt-1 text-xs text-gray-500">{t('admin.scholarship.estimate.practicalNote')}</p>
                )}
              </>
            ) : (
              <p className="text-sm text-gray-500">{t('admin.scholarship.estimate.none')}</p>
            )) : null}
            {/* Standard bursary — FIXED by pathway type (RM2k · RM3k STPM · RM1k continuing STPM),
                the same figure for everyone incl. a likely-declined student. No slider: the amount
                is not a reviewer choice (award.py). Prefer the committed award_amount, else the
                pathway figure. A confident disqualifier no longer zeroes it — it shows as a red
                fact in Rate AI verification instead. */}
            {(() => {
              const amt = app.award_amount != null
                ? Math.round(Number(app.award_amount))
                : (app.proposed_award_amount != null ? Math.round(Number(app.proposed_award_amount)) : null)
              if (amt == null) return null
              return (
                <div className="flex items-center justify-between border-t pt-3 text-sm">
                  <span className="font-medium text-gray-600">{t('admin.scholarship.recordVerdict.assistanceLabel')}</span>
                  <span className="font-semibold text-gray-900">RM{amt.toLocaleString()}</span>
                </div>
              )
            })()}
          </div>
        )
      })()}

      {/* ── Decision — audit the four facts (records the verdict) → verify identity →
           accept. The audit→accept gate is preserved (accept stays gated on a complete
           profile + every checklist box). ──────────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.decision.title')}</h2>
          {/* Reopen = REVERSE a recorded decision (super-only). Asks for a reason first;
              reopening holds the profile from the pool and unlocks the panel. */}
          {decisionLocked && isSuper && !reopenOpen && (
            <button onClick={() => { setReopenOpen(true); setReopenReason('') }}
              className="rounded-lg border border-gray-300 px-2.5 py-1 text-xs text-gray-600 hover:bg-gray-100">
              {t('admin.scholarship.recordVerdict.reopen')}
            </button>
          )}
        </div>

        {/* The "why are you reopening?" prompt — a reopen asserts a reviewer error, so a
            reason is required (logged + counted against the reviewer once a change is saved). */}
        {decisionLocked && isSuper && reopenOpen && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2">
            <p className="text-xs font-medium text-amber-900">{t('admin.scholarship.recordVerdict.reopenTitle')}</p>
            <p className="text-[11px] text-amber-800">{t('admin.scholarship.recordVerdict.reopenHint')}</p>
            <textarea value={reopenReason} rows={2} onChange={(e) => setReopenReason(e.target.value)}
              placeholder={t('admin.scholarship.recordVerdict.reopenPlaceholder')}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
            <div className="flex items-center gap-2">
              <button onClick={doReopenDecision} disabled={!!busy || !reopenReason.trim()}
                className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm disabled:opacity-50">
                {busy === 'reopen' ? t('common.loading') : t('admin.scholarship.recordVerdict.reopenConfirm')}
              </button>
              <button onClick={() => { setReopenOpen(false); setReopenReason('') }} disabled={!!busy}
                className="px-3 py-1.5 border rounded-lg text-sm text-gray-600 disabled:opacity-50">
                {t('common.cancel')}
              </button>
            </div>
          </div>
        )}

        {/* Reopened banner — the decision is editable again and the profile is held from
            the pool. "Cancel reopen" restores it unchanged; saving the decision republishes. */}
        {decisionReopened && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 space-y-2">
            <p className="text-sm font-medium text-amber-900">{t('admin.scholarship.recordVerdict.reopenedBanner')}</p>
            {app.decision_reopen_reason && (
              <p className="text-xs text-amber-800">
                <span className="font-medium">{t('admin.scholarship.recordVerdict.reopenReasonLabel')}:</span> {app.decision_reopen_reason}
              </p>
            )}
            {isSuper && (
              <button onClick={doCancelReopen} disabled={!!busy}
                className="px-3 py-1.5 border border-amber-400 text-amber-900 rounded-lg text-xs hover:bg-amber-100 disabled:opacity-50">
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
                <p className="text-xs font-medium text-gray-600 mb-1">{t('admin.scholarship.recordVerdict.reasonLabel')}</p>
                <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-3">
                  <p className="whitespace-pre-line text-sm text-gray-800">{verdictReason}</p>
                </div>
              </div>
            )}
            {app.status === 'recommended' ? (
              <p className="flex items-start gap-1.5 text-sm text-green-700">
                <span aria-hidden>✓</span>
                <span>
                  {t('admin.scholarship.interviewedRecommendedBy')} {reviewerName}{reviewerDate}
                  {hasQc && <>{', '}{t('admin.scholarship.qcAcceptedBy')} {qcName}{qcDate}</>}
                </span>
              </p>
            ) : app.status === 'rejected' ? (
              /* Decision-history trail. A straight reviewer decline is one line; a case that a
                 QC reopened before it was declined shows the full thread so the record no longer
                 hides the reviewer's recommendation behind a lone "Declined by …" line. */
              (() => {
                const ro = app.last_decision_reopen
                const declined = (
                  <p key="declined" className="flex items-start gap-1.5 text-sm text-red-700">
                    <span aria-hidden>✗</span>
                    <span>
                      {t('admin.scholarship.recordVerdict.declinedBy')} {app.rejected_by_name || app.rejected_by || '—'}
                      {app.rejected_at ? ` · ${formatDate(app.rejected_at)}` : ''}
                    </span>
                  </p>
                )
                if (!ro) return declined
                return (
                  <div className="space-y-1.5">
                    {ro.reviewer_name && (
                      <p className="flex items-start gap-1.5 text-sm text-gray-600">
                        <span aria-hidden>✓</span>
                        <span>{t('admin.scholarship.interviewedRecommendedBy')} {ro.reviewer_name}</span>
                      </p>
                    )}
                    <div className="flex items-start gap-1.5 text-sm text-amber-800">
                      <span aria-hidden>↩</span>
                      <span>
                        {t('admin.scholarship.recordVerdict.reopenedBy')} {ro.reopened_by_name || ro.reopened_by || '—'}
                        {ro.created_at ? ` · ${formatDate(ro.created_at)}` : ''}
                        {(ro.reason || '').trim() && (
                          <span className="block whitespace-pre-line text-amber-700">“{ro.reason.trim()}”</span>
                        )}
                      </span>
                    </div>
                    {declined}
                  </div>
                )
              })()
            ) : (
              <p className="text-sm text-gray-600">
                {t('admin.scholarship.interviewedRecommendedBy')} {reviewerName}{reviewerDate}
              </p>
            )}
            {(app.status === 'active' || app.status === 'maintenance') && canWrite && (
              <button onClick={() => doReject('contractual')} disabled={!!busy}
                className="px-4 py-2 border border-red-300 text-red-700 rounded-lg text-sm disabled:opacity-50">
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
          <label className="block text-xs font-medium text-gray-600 mb-1">
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
        {(app.status === 'recommended' || app.status === 'active' || app.status === 'maintenance') && !decisionReopened ? (
          /* Committed acceptance → read-only summary. A post-accept decline goes through
             Reopen (→ interviewed → declined as 'interview'); the direct 'contractual'
             decline is reserved for a genuinely post-award (sponsored) case. */
          <div className="space-y-2 border-t pt-3">
            <p className="flex items-start gap-1.5 text-sm text-green-700">
              <span aria-hidden>✓</span>
              <span>
                {t('admin.scholarship.interviewedRecommendedBy')} {reviewerName}{reviewerDate}
                {hasQc && <>{', '}{t('admin.scholarship.qcAcceptedBy')} {qcName}{qcDate}</>}
              </span>
            </p>
            {(app.status === 'active' || app.status === 'maintenance') && canWrite && (
              <button onClick={() => doReject('contractual')} disabled={!!busy}
                className="px-4 py-2 border border-red-300 text-red-700 rounded-lg text-sm disabled:opacity-50">
                {busy === 'reject' ? t('admin.scholarship.reject.running') : t('admin.scholarship.reject.declineContractual')}
              </button>
            )}
          </div>
        ) : (decisionReopened || ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status)) ? (
          canWrite && (
            <div className="space-y-2">
              {!app.completeness.complete && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
                  <p className="font-medium text-amber-900">{t('admin.scholarship.incompleteTitle')}</p>
                  <ul className="mt-1 list-disc ml-5 text-amber-800">
                    {COMPLETENESS_PARTS.filter((p) => !app.completeness[p]).map((p) => (
                      <li key={p}>{t(`admin.scholarship.completeness.${p}`)}</li>
                    ))}
                  </ul>
                </div>
              )}
              {/* Reversible outcome selection. Approve needs an amount; Decline doesn't (and clears it). */}
              <div className="grid grid-cols-2 gap-2">
                <button onClick={selectApprove} disabled={!!busy || !approveReady}
                  className={`rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${
                    officerVerdict.overall === 'accept'
                      ? 'border-green-600 bg-green-600 text-white'
                      : 'border-green-600 bg-white text-green-700 hover:bg-green-50'}`}>
                  {t('admin.scholarship.recordVerdict.approve')}
                </button>
                <button onClick={selectDecline} disabled={!!busy || !decisionReady}
                  className={`rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 ${
                    officerVerdict.overall === 'decline'
                      ? 'border-red-600 bg-red-600 text-white'
                      : 'border-red-500 bg-white text-red-700 hover:bg-red-50'}`}>
                  {t('admin.scholarship.recordVerdict.decline')}
                </button>
              </div>
              {/* One contextual hint: what's still missing before Save. */}
              {!decisionReady ? (
                <p className="text-[11px] text-amber-600">{t('admin.scholarship.recordVerdict.saveNeedsReady')}</p>
              ) : !officerVerdict.overall ? (
                <p className="text-[11px] text-amber-600">{t('admin.scholarship.recordVerdict.chooseOutcome')}</p>
              ) : officerVerdict.overall === 'accept' && !hasAssistance ? (
                <p className="text-[11px] text-amber-600">{t(app.award_disqualifier
                  ? 'admin.scholarship.recordVerdict.approveNeedsReview'
                  : 'admin.scholarship.recordVerdict.approveNeedsAmount')}</p>
              ) : null}
              {/* Save is the final commit of the chosen outcome. */}
              <button onClick={doSave} disabled={!!busy || !canSave}
                className="w-full px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                {(busy === 'verdict' || busy === 'reject') ? t('common.loading') : t('admin.scholarship.recordVerdict.save')}
              </button>
            </div>
          )
        ) : (
          <p className="text-sm text-gray-400">{t('admin.scholarship.notShortlisted')}</p>
        )}
        </>
        )}

        {/* Feedback message */}
        {verdictMsg && (
          <p className={`text-xs rounded p-2 ${verdictMsgTone === 'ok' ? 'text-green-700 bg-green-50' : 'text-amber-800 bg-amber-50'}`}>{verdictMsg}</p>
        )}

        {error && <p className="text-red-600 text-xs">{error}</p>}
      </div>

      {/* ── Quality Control — the QC gate on an AWAITING-QC ('interviewed') case (a `qc` role or
            super). Accept → Recommended; Reopen → back to the reviewer with a gaps note (emailed).
            Self-QC guard: a `qc` who reviewed this case cannot QC it (hidden here; backend blocks it too). ── */}
      {app.status === 'interviewed' && canQc
        && !((role?.role === 'qc' || role?.role === 'org_admin') && app.assigned_to_id === (role?.admin_id ?? null)) && (() => {
        // V5 gap floor (#5): a red/'gap' verdict fact blocks Accept. A super sees an override
        // affordance (reason recorded server-side); anyone else resolves the gap or reopens.
        const qcGapFacts = (app.verdict || []).filter((f) => f.status === 'gap').map((f) => f.fact)
        const qcGapLabels = qcGapFacts.map((f) => t(`admin.scholarship.verdict.fact.${f}`)).join(', ')
        const floorBlocked = qcGapFacts.length > 0
        return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.qcDecision.title')}</h2>
          <p className="text-xs text-gray-600">{t('admin.scholarship.qcDecision.hint')}</p>
          {floorBlocked && (
            <p className="rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-800">
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
                className="rounded-lg border border-green-600 bg-green-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50">
                {busy === 'qc' ? t('common.loading') : t('admin.scholarship.qcDecision.accept')}
              </button>
              <button onClick={() => { setQcReopenOpen(true); setQcComments('') }} disabled={!!busy}
                className="rounded-lg border border-amber-600 bg-white px-4 py-2.5 text-sm font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50">
                {t('admin.scholarship.qcDecision.reopen')}
              </button>
            </div>
          ) : qcOverrideOpen ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
              <p className="text-xs font-medium text-red-900">{t('admin.scholarship.qcDecision.overrideTitle')}</p>
              <textarea value={qcOverrideReason} rows={3} onChange={(e) => setQcOverrideReason(e.target.value)}
                placeholder={t('admin.scholarship.qcDecision.overridePlaceholder')}
                className="w-full rounded border border-red-300 px-2 py-1.5 text-sm" />
              <div className="flex items-center gap-2">
                <button onClick={() => doQcDecision('accept', qcOverrideReason)}
                  disabled={!!busy || !qcOverrideReason.trim()}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50">
                  {busy === 'qc' ? t('common.loading') : t('admin.scholarship.qcDecision.overrideConfirm')}
                </button>
                <button onClick={() => { setQcOverrideOpen(false); setQcOverrideReason('') }}
                  className="text-xs text-gray-500 hover:text-gray-700">{t('common.cancel')}</button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2">
              <p className="text-xs font-medium text-amber-900">{t('admin.scholarship.qcDecision.reopenTitle')}</p>
              <textarea value={qcComments} rows={3} onChange={(e) => setQcComments(e.target.value)}
                placeholder={t('admin.scholarship.qcDecision.commentsPlaceholder')}
                className="w-full rounded border border-amber-300 px-2 py-1.5 text-sm" />
              <div className="flex items-center gap-2">
                <button onClick={() => doQcDecision('reopen')} disabled={!!busy || !qcComments.trim()}
                  className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-50">
                  {busy === 'qc' ? t('common.loading') : t('admin.scholarship.qcDecision.reopenConfirm')}
                </button>
                <button onClick={() => { setQcReopenOpen(false); setQcComments('') }}
                  className="text-xs text-gray-500 hover:text-gray-700">{t('common.cancel')}</button>
              </div>
            </div>
          )}
        </div>
        )
      })()}

      {/* ── Assign a reviewer (F7) — SUPER or org_admin + audited. First assignment is gated on
            readiness (no open queries OR the SLA lapsed); reassign is allowed any time. ─── */}
      {canAssign && (() => {
        const ready = app.query_sla?.ready_for_assignment ?? false
        const firstAssignBlocked = !app.assigned_to_id && !ready
        // Once a decision is recorded the reviewer is fixed (it's a finished case) — the
        // dropdown locks. It unlocks again only if a superadmin REOPENS the decision.
        const assignLocked = decisionLocked
        const assigned = !!app.assigned_to_id
        return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">
            {assigned ? t('admin.scholarship.assign.assignedTitle') : t('admin.scholarship.assignTitle')}
          </h2>
          <select
            value={app.assigned_to_id ?? ''}
            disabled={!!busy || firstAssignBlocked || assignLocked}
            title={assignLocked ? t('admin.scholarship.assign.lockedHint')
              : firstAssignBlocked ? t('admin.scholarship.assign.error.not_ready') : undefined}
            onChange={(e) => doAssign(e.target.value ? Number(e.target.value) : null)}
            className="border rounded-lg px-3 py-2 text-sm w-full disabled:bg-gray-100 disabled:text-gray-400"
          >
            <option value="">{t('admin.scholarship.unassigned')}</option>
            {/* Assignable options. The backend already returns the org-fenced, review-capable set
                (services.REVIEW_ROLES; AdminAssignableAdminsView). A super may pick any of them; a
                non-super (org_admin) delegates only to their own org's reviewers (the assign endpoint
                rejects anything else as bad_assignee). The CURRENT assignee always renders so a later
                role change never hides them (#66: assigned as qc → promoted to org_admin → was
                showing "Unassigned"). Role suffixed so a senior assignee is distinguishable. */}
            {admins.filter((a) => a.id === app.assigned_to_id || isSuper || a.role === 'reviewer')
              .map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}{a.role !== 'reviewer' ? ` (${a.role})` : ''}
                </option>
              ))}
          </select>
          {assignLocked ? (
            <p className="text-xs text-gray-400">{t('admin.scholarship.assign.lockedHint')}</p>
          ) : firstAssignBlocked && (
            <p className="text-xs text-amber-600">{t('admin.scholarship.assign.notReadyHint')}</p>
          )}
        </div>
        )
      })()}

      </div>{/* end RIGHT column */}

      </div>{/* end cockpit grid */}

      {/* ── Conditional Bursary Award Agreement (flag-gated; dark by default) ──
          Shown once the award has been accepted (the student + guarantor have
          signed in-session). The Foundation countersignature + the partner-org
          witness are recorded here. The admin detail GET doesn't carry the
          agreement, so the four states resolve from the action responses. */}
      {app.bursary_agreement_enabled && (app.status === 'awarded' || app.status === 'active' || app.status === 'maintenance') && (() => {
        // TD-144 FIXED: all four states come from the REAL loaded agreement (seeded from the
        // detail GET, refreshed by the action responses) — no optimistic default. No agreement
        // yet (awarded but the student hasn't signed) → every tick is correctly "–".
        const hasAgreement = !!bursary
        const studentDone = !!bursary?.student_signed_at
        const guarantorDone = !!bursary?.guarantor_signed_at
        const foundationDone = !!bursary?.foundation_signed_at
        const witnessDone = !!bursary?.witness_signed_at
        const stateRow = (label: string, done: boolean) => (
          <div className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2">
            <span className="text-sm text-gray-700">{label}</span>
            <span className={done ? 'text-green-600' : 'text-gray-300'} aria-hidden>
              {done ? '✓' : '–'}
            </span>
          </div>
        )
        return (
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-gray-900">
                {t('admin.scholarship.bursary.title')}
              </h2>
              {bursary?.status && (
                <span className="rounded-full border border-gray-200 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                  {bursary.status}
                </span>
              )}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {stateRow(t('admin.scholarship.bursary.student'), studentDone)}
              {stateRow(t('admin.scholarship.bursary.guarantor'), guarantorDone)}
              {stateRow(t('admin.scholarship.bursary.foundation'), foundationDone)}
              {stateRow(t('admin.scholarship.bursary.witness'), witnessDone)}
            </div>
            {!hasAgreement && (
              <p className="text-xs text-gray-500">{t('admin.scholarship.bursary.awaitingSignature')}</p>
            )}
            {bursaryMsg && <p className="text-xs text-amber-600">{bursaryMsg}</p>}
            <div className="flex flex-wrap items-center gap-2">
              {isSuper && (
                <button
                  type="button"
                  onClick={doCountersignBursary}
                  disabled={busy === 'bursary' || !hasAgreement || foundationDone}
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                >
                  {t('admin.scholarship.bursary.countersign')}
                </button>
              )}
              <button
                type="button"
                onClick={doWitnessBursary}
                disabled={busy === 'bursary' || !hasAgreement || witnessDone}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              >
                {t('admin.scholarship.bursary.witnessAction')}
              </button>
              {bursary?.pdf_url && (
                <a
                  href={bursary.pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  {t('admin.scholarship.bursary.download')}
                </a>
              )}
            </div>
            <p className="text-xs text-gray-400">{t('admin.scholarship.bursary.note')}</p>
          </div>
        )
      })()}

      {/* ── Post-award S4: disbursement (tranche) ledger ──
          Money OUT to the student, paid in tranches. Shown once the student is funded
          (active / maintenance). Marking the FIRST tranche disbursed flips the
          application active → maintenance. Mock ledger — real toyyibPay is deferred (TD-075). */}
      {isFunded(app.status) && (() => {
        const rows = app.disbursements ?? []
        const released = totalReleased(rows)
        return (
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-gray-900">
                {t('admin.disbursement.title')}
              </h2>
              {released > 0 && (
                <span className="rounded-full border border-green-200 bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
                  {t('admin.disbursement.totalReleased')} RM{released.toLocaleString()}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400">{t('admin.disbursement.note')}</p>

            {/* S5: maintenance sub-state — only once funded into the recurring loop. */}
            {app.status === 'maintenance' && (
              <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-gray-600">{t('admin.maintenance.title')}</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    app.maintenance_substate === 'on_track' ? 'bg-green-100 text-green-700'
                    : app.maintenance_substate === 'probation' ? 'bg-amber-100 text-amber-700'
                    : app.maintenance_substate === 'on_hold' ? 'bg-red-100 text-red-700'
                    : 'bg-blue-100 text-blue-700'}`}>
                    {t(`admin.maintenance.substate.${app.maintenance_substate}`)}
                  </span>
                </div>
                {canWrite && (
                  <div className="flex flex-wrap gap-1.5">
                    {(['on_track', 'probation', 'on_hold', 'ready_to_close'] as const)
                      .filter((s) => s !== app.maintenance_substate)
                      .map((s) => (
                        <button key={s} type="button"
                          onClick={() => doSetSubstate(s)}
                          disabled={busy === 'disbursement'}
                          className="rounded-lg border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50">
                          {t(`admin.maintenance.action.${s}`)}
                        </button>
                      ))}
                  </div>
                )}
                {app.maintenance_substate === 'on_hold' && (
                  <p className="text-[11px] text-red-600">{t('admin.maintenance.onHoldHint')}</p>
                )}
              </div>
            )}

            {rows.length === 0 ? (
              <p className="text-sm text-gray-400">{t('admin.disbursement.empty')}</p>
            ) : (
              <div className="space-y-2">
                {rows.map((d: AdminDisbursement) => {
                  const tone = disbursementTone(d.status)
                  const toneClass = tone === 'green' ? 'bg-green-100 text-green-700'
                    : tone === 'amber' ? 'bg-amber-100 text-amber-700'
                    : tone === 'red' ? 'bg-red-100 text-red-700'
                    : tone === 'grey' ? 'bg-gray-100 text-gray-600'
                    : 'bg-blue-100 text-blue-700'
                  return (
                    <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-100 p-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-700">
                          {d.label || `${t('admin.disbursement.tranche')} ${d.sequence}`}
                        </span>
                        <span className="text-sm font-semibold text-gray-900">RM{Math.round(Number(d.amount)).toLocaleString()}</span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${toneClass}`}>
                          {t(`admin.disbursement.status.${d.status}`)}
                        </span>
                      </div>
                      {canWrite && (
                        <div className="flex flex-wrap gap-1.5">
                          {actionsFor(d.status).map((action) => (
                            <button key={action} type="button"
                              onClick={() => doDisbursementAction(d.id, action)}
                              disabled={busy === 'disbursement'}
                              className="rounded-lg border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50">
                              {t(`admin.disbursement.action.${action}`)}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {canWrite && (
              <div className="flex flex-wrap items-end gap-2 border-t pt-3">
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-1">{t('admin.disbursement.amountLabel')}</label>
                  <input type="number" min={1} step={50} value={disbAmount}
                    onChange={(e) => setDisbAmount(e.target.value)}
                    placeholder="500"
                    className="w-28 rounded-lg border px-3 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-1">{t('admin.disbursement.labelLabel')}</label>
                  <input type="text" value={disbLabel} maxLength={100}
                    onChange={(e) => setDisbLabel(e.target.value)}
                    placeholder={t('admin.disbursement.labelPlaceholder')}
                    className="w-40 rounded-lg border px-3 py-1.5 text-sm" />
                </div>
                <button type="button" onClick={doScheduleTranche}
                  disabled={busy === 'disbursement'}
                  className="rounded-lg bg-primary-500 px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50">
                  {t('admin.disbursement.schedule')}
                </button>
              </div>
            )}
            {disbMsg && <p className="text-xs text-amber-600">{disbMsg}</p>}
          </div>
        )
      })()}

      {/* ── Post-award S6: manual closure ──
          Close a funded student's file with a reason. Terminal. Shows the closed summary
          once closed (the graduation thank-you relay stays open after closure). */}
      {(app.status === 'active' || app.status === 'maintenance' || app.status === 'closed') && (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">
            {t('admin.closure.title')}
          </h2>
          {app.status === 'closed' ? (
            <div className="space-y-1">
              <p className="flex items-center gap-1.5 text-sm text-gray-700">
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  app.closure_reason === 'graduated' || app.closure_reason === 'completed'
                    ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>
                  {t(`admin.closure.reason.${app.closure_reason}`)}
                </span>
              </p>
              <p className="text-xs text-gray-500">
                {t('admin.closure.closedBy')} {app.closed_by || '—'}
                {app.closed_at ? ` · ${formatDate(app.closed_at)}` : ''}
              </p>
            </div>
          ) : canWrite ? (
            <>
              <p className="text-xs text-gray-500">{t('admin.closure.note')}</p>
              {/* Offboarding checklist — informational guidance before closing. */}
              <ul className="list-disc ml-5 text-xs text-gray-500 space-y-0.5">
                {(['finalDisbursement', 'thankYou', 'records'] as const).map((k) => (
                  <li key={k}>{t(`admin.closure.checklist.${k}`)}</li>
                ))}
              </ul>
              <div className="flex flex-wrap items-end gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-1">{t('admin.closure.reasonLabel')}</label>
                  <select value={closeReason}
                    onChange={(e) => setCloseReason(e.target.value as ClosureReason | '')}
                    className="rounded-lg border px-3 py-1.5 text-sm">
                    <option value="">{t('admin.closure.reasonUnset')}</option>
                    {(['graduated', 'completed', 'withdrawn', 'lapsed', 'terminated'] as const).map((r) => (
                      <option key={r} value={r}>{t(`admin.closure.reason.${r}`)}</option>
                    ))}
                  </select>
                </div>
                <button type="button" onClick={doClose}
                  disabled={busy === 'close' || !closeReason}
                  className="rounded-lg border border-red-300 px-4 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50">
                  {busy === 'close' ? t('common.loading') : t('admin.closure.close')}
                </button>
              </div>
              {closeMsg && <p className="text-xs text-amber-600">{closeMsg}</p>}
            </>
          ) : null}
        </div>
      )}
      </>)}
    </div>
  )
}
