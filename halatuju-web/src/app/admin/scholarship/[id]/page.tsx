'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatPhone, formatAddress, isValidPhone, formatNric } from '@/lib/scholarship'
import {
  getScholarshipApplication,
  suggestInterviewGaps,
  verifyAcceptApplication,
  rejectApplication,
  addReferee,
  deleteReferee,
  reRunVision,
  assignApplication,
  getInterview,
  saveInterview,
  submitInterview,
  getAssignableAdmins,
  recordVerdict,
  setAwardAmount,
  raiseResolutionItem,
  actionResolutionItem,
  type AdminScholarshipDetail,
  type AdminSponsorProfile,
  type AdminApplicantDocument,
  type AdminInterviewSession,
  type AdminVerdictItem,
  type AdminResolutionItem,
} from '@/lib/admin-api'
import {
  factTileTone,
  TONE_BAND_KEY,
  groupDocumentsByFact,
  aiSuggestionFor,
  documentPill,
  documentFacts,
  incomeDocLayout,
  docIconFor,
  earnerMemberFor,
  viewerKind,
  isClearAccept,
  isQueryingLocked,
  isDecisionReady,
  isApproveReady,
  type FactStatus,
  type IncomeSlot,
} from '@/lib/officerCockpit'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import { localiseParams, titleSourceFor } from '@/lib/actionCentre'

const COMPLETENESS_PARTS = ['quiz_done', 'details_done', 'funding_done', 'documents_done', 'consent_done', 'address_done', 'guardian_docs_done', 'family_done'] as const

// Officer doc-request control (Check-2/Check-3 S2b): the 13 requestable slot types,
// the income types that also need a person, and each type's verdict fact.
const REQ_DOC_TYPES = ['ic', 'results_slip', 'offer_letter', 'parent_ic', 'str', 'salary_slip', 'epf', 'birth_certificate', 'guardianship_letter', 'water_bill', 'electricity_bill', 'statement_of_intent', 'photo', 'other'] as const
const REQ_MEMBER_DOCS = new Set(['parent_ic', 'str', 'salary_slip', 'epf'])
const REQ_MEMBERS = ['father', 'mother', 'guardian', 'brother', 'sister'] as const
const DOC_FACT: Record<string, string> = {
  ic: 'identity', results_slip: 'academic', offer_letter: 'pathway',
  parent_ic: 'income', str: 'income', salary_slip: 'income', epf: 'income',
  birth_certificate: 'income', guardianship_letter: 'income',
  water_bill: 'income', electricity_bill: 'income',
  statement_of_intent: 'other', photo: 'other', other: 'other',
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

// Status pill colour bands — amber = in-progress/under review, green = accepted/funded,
// red = closed (rejected/withdrawn/expired). The label itself is the real status (i18n).
const STATUS_TONE: Record<string, string> = {
  submitted: 'bg-amber-100 text-amber-700',
  shortlisted: 'bg-amber-100 text-amber-700',
  profile_complete: 'bg-amber-100 text-amber-700',
  interviewing: 'bg-amber-100 text-amber-700',
  interviewed: 'bg-amber-100 text-amber-700',
  accepted: 'bg-green-100 text-green-700',
  sponsored: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  withdrawn: 'bg-gray-100 text-gray-600',
  expired: 'bg-gray-100 text-gray-600',
}
const statusTone = (s: string) => STATUS_TONE[s] || 'bg-primary-100 text-primary-700'

// Non-parent guardian relationships — drive the dynamic "Parent" vs "Guardian" label (#5).
const NON_PARENT_RELATIONSHIPS = new Set([
  'legal_guardian', 'grandparent', 'older_sibling', 'brother', 'sister', 'relative', 'other_relative',
])
// Referees aren't in play yet — hide the capture UI (the handlers stay wired so this
// is a one-line re-enable, and so they don't become unused). Flip to true to restore.
const SHOW_REFEREES = false


function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-400 uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-gray-800 break-words">{value === null || value === undefined || value === '' ? '—' : value}</dd>
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
function Grades({ grades }: { grades?: Record<string, string> | null }) {
  const entries = Object.entries(grades || {}).filter(([, g]) => g)
  if (!entries.length) return <span className="text-gray-400 text-sm">—</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, g]) => (
        <span key={k} className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-xs">
          <span className="text-gray-500 uppercase">{k.replace(/_/g, ' ')}</span>
          <span className="font-semibold text-gray-800">{g}</span>
        </span>
      ))}
    </div>
  )
}

export default function AdminScholarshipDetailPage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  // Execute (verify/verdict/etc.) is for super + reviewer only; admin is read-only.
  const effRole = role?.is_super_admin ? 'super' : (role?.role ?? 'reviewer')
  const canWrite = effRole === 'super' || effRole === 'reviewer'
  const isSuper = role?.role === 'super' || !!role?.is_super_admin
  const [app, setApp] = useState<AdminScholarshipDetail | null>(null)
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
  const [reqDocType, setReqDocType] = useState('')
  const [reqDocMember, setReqDocMember] = useState('')
  const [reqDocNote, setReqDocNote] = useState('')
  // Sprint 5 — Officer cockpit
  const [officerVerdict, setOfficerVerdict] = useState<Record<string, string>>({})
  const [verdictReason, setVerdictReason] = useState('')
  const [recAmount, setRecAmount] = useState<number | null>(null)  // recommended assistance (optimistic)
  const [verdictMsg, setVerdictMsg] = useState('')
  const [verdictMsgTone, setVerdictMsgTone] = useState<'ok' | 'warn'>('ok')
  // Consolidation: the student's own words (note/story/funding) are collapsed by
  // default under the Sponsor profile — the reviewer checks the AI draft first.
  const [showOwnWords, setShowOwnWords] = useState(false)

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
      })
      .catch(() => setError(t('admin.scholarship.loadFailed')))
    getAssignableAdmins({ token }).then((r) => setAdmins(r.admins)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  const doSuggestGaps = async (append = false) => {
    if (!token) return
    setBusy(append ? 'gapsMore' : 'gaps'); setError('')
    try {
      setApp(await suggestInterviewGaps(id, undefined, { token }, append))
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

  const doAssign = async (adminId: number | null) => {
    if (!token) return
    setBusy('assign'); setError('')
    try { setApp(await assignApplication(id, adminId, { token })) }
    catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['not_ready', 'not_reviewer', 'bad_assignee']
      setError(known.includes(code)
        ? t(`admin.scholarship.assign.error.${code}`)
        : t('admin.scholarship.assignError'))
    } finally { setBusy('') }
  }

  const doSaveInterview = async () => {
    if (!token) return
    setBusy('iv'); setError('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.interview.saveError')) } finally { setBusy('') }
  }

  const doSubmitInterview = async () => {
    if (!token) return
    setBusy('ivs'); setError('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      const d = await submitInterview(id, { token })
      setApp(d); loadInterviewState(d)
    } catch { setError(t('admin.scholarship.interview.submitError')) } finally { setBusy('') }
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

  // Approve = record the verdict + accept (the existing completeness/identity gate, now
  // explicit). Save = record the verdict + generate the final profile, WITHOUT accepting.
  const doApprove = () => doRecordVerdict(true, true)
  const doSaveVerdict = () => doRecordVerdict(true, false)

  const doSetAwardAmount = async (amount: number) => {
    if (!token) return
    setRecAmount(amount)  // optimistic
    setBusy('award'); setError('')
    try { setApp(await setAwardAmount(id, amount, { token })) }
    catch (e) { setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError')) }
    finally { setBusy('') }
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
  const onReqDocType = (dt: string) => {
    setReqDocType(dt)
    setReqDocNote(stdDocRequest(dt, REQ_MEMBER_DOCS.has(dt) ? reqDocMember : ''))
  }
  const onReqDocMember = (m: string) => {
    setReqDocMember(m)
    setReqDocNote(stdDocRequest(reqDocType, m))
  }
  const doRequestDoc = async () => {
    if (!token || !reqDocType) return
    const member = REQ_MEMBER_DOCS.has(reqDocType) ? reqDocMember : ''
    const prompt = reqDocNote.trim() || stdDocRequest(reqDocType, member)
    setBusy('reqdoc'); setError('')
    try {
      setApp(await raiseResolutionItem(
        id,
        { kind: 'doc', doc_type: reqDocType, household_member: member, prompt, fact: DOC_FACT[reqDocType] || 'other' },
        { token },
      ))
      setReqDocNote(''); setReqDocType(''); setReqDocMember('')
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

  // S4: once the interview is concluded it's decision time — querying (raise / Resolve /
  // Ask again / request a document) closes and Outstanding becomes a read-only record.
  const queryingLocked = isQueryingLocked(app.status, app.interview_session?.status)
  // #7: Approve/Decline activate only once the reviewer has (1) submitted interview
  // findings, (2) pressed Pass/Fail on all four facts, and (3) written a conclusion.
  // (Approve's actual accept is still backend-gated on a complete profile + identity.)
  const decisionReady = isDecisionReady(app.interview_session?.status, officerVerdict, verdictReason)
  // Approve also requires a recommended assistance amount (the slider, or an already-saved one).
  const hasAssistance = recAmount != null || app.award_amount != null
  const approveReady = isApproveReady(decisionReady, hasAssistance)

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
          <h1 className="text-xl font-bold tracking-tight text-gray-900 sm:text-2xl">{app.name || '—'}</h1>
          {/* The actual application status (Shortlisted, Rejected, …), colour-banded. */}
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusTone(app.status)}`}>
            {t(`admin.scholarship.statuses.${app.status}`)}
          </span>
          {/* Primary action button — scrolls to the Record Verdict panel */}
          {canWrite && ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status) && (
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
          <span>NRIC <span className="font-mono text-gray-700">{formatNric(app.nric || '') || '—'}</span></span>
          {app.submitted_at && (
            <span>{t('admin.scholarship.submitted')} {new Date(app.submitted_at).toLocaleDateString()}</span>
          )}
          {app.profile_completed_at && (
            <span>{t('admin.scholarship.applied')} {new Date(app.profile_completed_at).toLocaleDateString()}</span>
          )}
          <span>{t('admin.scholarship.assigned')} <span className="text-gray-700">{app.assigned_to_name || '—'}</span></span>
        </div>
      </header>

      {/* Applicant info — three explicit columns (About+Family / Academic / Support…) */}
      {(() => {
        const isStpm = app.qualification === 'stpm'
        // Pathway context: matric/stpm are INSTITUTION pathways (track + school);
        // everything else (asasi, university, poly, pismp…) is a PROGRAMME pathway
        // (a chosen course), so Pre-U track doesn't apply.
        const isInstitutionPathway = app.chosen_pathway === 'matric' || app.chosen_pathway === 'stpm'
        // Human labels for the stored codes — reuse the apply-form's own i18n maps so
        // the admin sees the same words the student did (matric→Matriculation, etc.).
        const callLangLabel = app.preferred_call_language ? t(`scholarship.apply.callLang.${app.preferred_call_language}`) : null
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
        const hasPlans = !!(app.chosen_pathway || app.chosen_programme?.course_name
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
                  <Field label={t('admin.scholarship.callLanguage')} value={callLangLabel} />
                  {/* Verified email only — shown once the student verifies it, else the
                      verified Google login email. Full-width rows. */}
                  <div className="col-span-2"><Field label={t('admin.scholarship.email')} value={app.verified_email
                    ? <a href={`mailto:${app.verified_email}`} className="text-primary-600 hover:underline">{app.verified_email}</a>
                    : null} /></div>
                  <div className="col-span-2"><Field label={t('admin.scholarship.address')} value={addr} /></div>
                </dl>
              </Card>

              {/* Family & finances — moved up under About (was below Academic) */}
              <Card title={t('admin.scholarship.sec.family')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.income')} value={app.household_income ? `RM ${Number(app.household_income).toLocaleString('en-US')}` : null} />
                  <Field label={t('admin.scholarship.householdSize')} value={app.household_size} />
                  <Field label="STR" value={yn(app.receives_str)} />
                  <Field label="JKM" value={yn(app.receives_jkm)} />
                  <Field label={personLabel} value={guardian?.name} />
                  <Field label={t('admin.scholarship.guardianPhone', { role: personLabel })} value={guardian?.phone ? formatPhone(guardian.phone) : null} />
                </dl>
              </Card>
              </div>

              {/* Right column — Academic (tall: grades + plans), then Support */}
              <div className="space-y-4">
              {/* Academic — school / merit / grades. Plans + notes are their own boxes below. */}
              <Card title={t('admin.scholarship.sec.academic')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.school')} value={app.school} />
                  <Field label={t('admin.scholarship.meritScore')} value={app.merit_score} />
                  {isStpm && <Field label="MUET" value={app.muet_band} />}
                </dl>
                <div className="mt-3">
                  <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">
                    {isStpm ? t('admin.scholarship.stpmGrades') : t('admin.scholarship.spmGrades')}
                  </dt>
                  <Grades grades={isStpm ? app.stpm_grades : app.grades} />
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
                          <Field label={t('admin.scholarship.preUInstitution')} value={app.pre_u_institution} />
                        </>
                      ) : (
                        <Field
                          label={t('admin.scholarship.chosenProgramme')}
                          value={app.chosen_programme?.course_name
                            ? courseLink(app.chosen_programme.course_id as string | undefined, app.chosen_programme.course_name as string)
                            : pathwayLabel(app.chosen_pathway)}
                        />
                      )}
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
              t(`admin.scholarship.verdict.item.${it.code}`,
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
        {/* Expanded evidence / unresolved — shown ONLY for facts that still need attention.
            A green fact is hidden here (its tile tick is the whole story). */}
        {(app.verdict || []).some((f) => factTileTone(f) !== 'green' && (f.evidence.length > 1 || f.unresolved.length > 0)) && (
          <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
            {(app.verdict || []).map((f) => {
              const resolve = (it: AdminVerdictItem) =>
                t(`admin.scholarship.verdict.item.${it.code}`,
                  localiseParams(it.params, t))
              if (factTileTone(f) === 'green' || (f.evidence.length <= 1 && f.unresolved.length === 0)) return null
              return (
                <div key={`detail-${f.fact}`} className="text-xs text-gray-600">
                  <span className="font-medium text-gray-500 uppercase text-[10px] tracking-wide">
                    {t(`admin.scholarship.verdict.fact.${f.fact}`)}
                  </span>
                  {f.evidence.slice(1).map((it, i) => (
                    <div key={`e${i}`} className="ml-2 flex items-start gap-1 mt-0.5">
                      <span className="text-green-600 shrink-0">✓</span>
                      <span>{resolve(it)}</span>
                    </div>
                  ))}
                  {f.unresolved.map((it, i) => (
                    <div key={`u${i}`} className="ml-2 flex items-start gap-1 mt-0.5">
                      <span className="text-amber-600 shrink-0">•</span>
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
          <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.profileTitle')}</h2>
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
          <span>{t('admin.scholarship.profileDraftHint')}</span>
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
                              <span className="font-semibold">{t('admin.scholarship.outstanding.questionLabel')}:</span> {question}
                              {' '}
                              <span className="ml-0.5 rounded bg-gray-200 px-1.5 py-0.5 text-[11px] text-gray-500 align-middle">{item.fact}</span>
                              {' '}
                              <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[11px] text-gray-500 align-middle">{item.kind}</span>
                            </p>
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
              <div className="flex flex-wrap items-center gap-2">
                <select value={reqDocType} onChange={(e) => onReqDocType(e.target.value)}
                  className="border rounded-lg px-2 py-1.5 text-sm">
                  <option value="">{t('admin.scholarship.requestDocAny')}</option>
                  {REQ_DOC_TYPES.map((dt) => (
                    <option key={dt} value={dt}>{t(`admin.scholarship.docsDrawer.type.${dt}`)}</option>
                  ))}
                </select>
                {REQ_MEMBER_DOCS.has(reqDocType) && (
                  <select value={reqDocMember} onChange={(e) => onReqDocMember(e.target.value)}
                    className="border rounded-lg px-2 py-1.5 text-sm">
                    <option value="">{t('admin.scholarship.requestDocWhose')}</option>
                    {REQ_MEMBERS.map((m) => (
                      <option key={m} value={m}>{t(`scholarship.docs.income.wizard.member.${m}`)}</option>
                    ))}
                  </select>
                )}
              </div>
              {reqDocType && (
                <>
                  <textarea value={reqDocNote} rows={2} onChange={(e) => setReqDocNote(e.target.value)}
                    placeholder={t('admin.scholarship.requestDocNotePlaceholder')}
                    className="w-full border rounded-lg px-3 py-2 text-sm" />
                  <button onClick={doRequestDoc} disabled={!!busy || !reqDocType || (reqDocType === 'other' && !reqDocNote.trim())}
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

      {/* Phase C: interview capture */}
      <div id="interview-section" className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.interview.title')}</h2>
            {app.interview_session?.status === 'submitted' && (
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-primary-100 text-primary-700">
                {t('admin.scholarship.interview.submitted')}
              </span>
            )}
          </div>
          {canWrite && (
            <div className="flex items-center gap-2">
              <button onClick={() => doSuggestGaps(false)} disabled={!!busy}
                className="px-2.5 py-1 rounded-lg text-xs bg-primary-600 text-white disabled:opacity-50">
                {busy === 'gaps' ? t('admin.scholarship.gaps.running') : t('admin.scholarship.gaps.button')}
              </button>
              {(app.interview_gaps?.length ?? 0) > 0 && (
                <button onClick={() => doSuggestGaps(true)} disabled={!!busy}
                  className="px-2.5 py-1 rounded-lg text-xs border border-primary-300 text-primary-700 disabled:opacity-50">
                  {busy === 'gapsMore' ? t('admin.scholarship.gaps.running') : t('admin.scholarship.gaps.more')}
                </button>
              )}
            </div>
          )}
        </div>
        <p className="text-xs text-gray-500">{t('admin.scholarship.interview.intro')}</p>
        {(() => {
          // #9: drop anomalies whose concern is already a Check-2 query (no repeat).
          const check2Codes = new Set((app.resolution_items ?? []).map((i) => i.code))
          const items = [
            // Reviewer asks these LIVE — show the question form (2nd-person), not the
            // internal flag description.
            ...app.anomalies
              .filter((a) => {
                const owner = ANOMALY_CHECK2_OWNER[a.code]
                return !(owner && check2Codes.has(owner))
              })
              .map((a) => ({
                code: a.code,
                label: t(`admin.scholarship.anomaly.${a.code}.question`, Object.fromEntries(Object.entries(a.params).map(([k, v]) => [k, String(v)]))),
                ai: false,
              })),
            ...(app.interview_gaps || []).map((g) => ({ code: g.code, label: g.question, ai: true })),
          ].filter((it) => findings[it.code]?.verdict !== 'deleted')  // a Deleted talking point drops off the agenda
          if (items.length === 0) {
            return <p className="text-sm text-gray-400 italic">{t('admin.scholarship.interview.noFlags')}</p>
          }
          return (
            <ul className="space-y-3">
              {items.map((it) => {
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
          )
        })()}
        <textarea value={note} disabled={!canWrite} rows={2}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t('admin.scholarship.interview.notePlaceholder')}
          className="w-full border rounded-lg px-3 py-2 text-sm" />
        {canWrite && (
          <div className="flex gap-2">
            <button onClick={doSaveInterview} disabled={!!busy}
              className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50">
              {busy === 'iv' ? t('common.loading') : t('admin.scholarship.interview.saveDraft')}
            </button>
            <button onClick={doSubmitInterview} disabled={!!busy}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm disabled:opacity-50">
              {busy === 'ivs' ? t('common.loading') : t('admin.scholarship.interview.submit')}
            </button>
          </div>
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
          const sectionKeys = ['identity', 'academic', 'pathway', 'income', 'other'] as const
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
            'salary_slip', 'epf', 'water_bill', 'electricity_bill', 'birth_certificate',
            'guardianship_letter', 'statement_of_intent', 'photo', 'other'])
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
          // Line 2: the coloured fact-labels — only the facts THIS document provides.
          const factLine = (d: AdminApplicantDocument) => {
            const facts = documentFacts(d)
            if (facts.length === 0) return null
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
                    {/* Capture confidence: was this read deterministically (fixed labels) or by AI? */}
                    {d.vision_fields?.capture && (
                      <span
                        title={t(`admin.scholarship.docsDrawer.capture.${d.vision_fields.capture}.hint`)}
                        className={`rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                          d.vision_fields.capture === 'deterministic'
                            ? 'bg-slate-100 text-slate-500' : 'bg-violet-50 text-violet-500'}`}>
                        {t(`admin.scholarship.docsDrawer.capture.${d.vision_fields.capture}.label`)}
                      </span>
                    )}
                  </div>
                  {d.original_filename && (
                    <p className="text-[11px] text-gray-400 truncate max-w-[230px]" title={d.original_filename}>
                      ({trunc(d.original_filename, 30)})
                    </p>
                  )}
                  {factLine(d)}
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
                  // Income: compulsory (route+selection aware) on top with placeholders for
                  // anything missing, then the optional household docs.
                  const layout = incomeDocLayout(app, docs)
                  if (docs.length === 0 && layout.required.length === 0) return null
                  return (
                    <div key={key}>
                      <p className={subLabel}>{t('admin.scholarship.docsDrawer.group.income')}</p>
                      {layout.required.length > 0 && (
                        <>
                          <p className="text-[9px] font-semibold uppercase tracking-wider text-gray-300 mb-1">
                            {t('admin.scholarship.docsDrawer.required')}
                          </p>
                          <ul className="space-y-1.5">
                            {layout.required.map((s) => (s.doc ? docRow(s.doc) : placeholderRow(s)))}
                          </ul>
                        </>
                      )}
                      {layout.optional.length > 0 && (
                        <>
                          <p className="text-[9px] font-semibold uppercase tracking-wider text-gray-300 mb-1 mt-2">
                            {t('admin.scholarship.docsDrawer.optional')}
                          </p>
                          <ul className="space-y-1.5">{layout.optional.map(docRow)}</ul>
                        </>
                      )}
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

      {/* ── Estimated need — beside Decision (award-sizing input; NOT raw narrative, so
           NOT hidden). Per-pathway estimated GAP after government coverage. ─────────── */}
      {(() => {
        const fe = app.funding_estimate
        if (!fe) return null
        return (
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="font-semibold mb-2">{t('admin.scholarship.estimate.title')}</h2>
            {fe.known ? (
              <>
                <p className="text-2xl font-semibold text-gray-900">
                  ≈ RM {fe.total.toLocaleString('en-US')}
                </p>
                <p className="text-xs text-gray-500 mb-2">
                  ~RM {fe.monthly.toLocaleString('en-US')}/{t('admin.scholarship.estimate.month')} × {fe.months} {t('admin.scholarship.estimate.months')}
                </p>
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
            )}
          </div>
        )
      })()}

      {/* ── Decision — audit the four facts (records the verdict) → verify identity →
           accept. The audit→accept gate is preserved (accept stays gated on a complete
           profile + every checklist box). ──────────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
        <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.decision.title')}</h2>

        <p className="text-xs font-medium text-gray-600">{t('admin.scholarship.recordVerdict.rateTitle')}</p>

        {/* Four fact rows — pass / fail toggle */}
        <div className="space-y-2">
          {(['identity', 'academic', 'pathway', 'income'] as const).map((fact) => (
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
          ))}
        </div>

        {/* AI verdict — sits right under the four facts (the officer decides). */}
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

        {/* #4: recommended assistance — 4-stop slider (RM1,500 / 2,000 / 2,500 / 3,000) */}
        {canWrite && (() => {
          const cur = recAmount ?? (app.award_amount != null ? Math.round(Number(app.award_amount)) : null)
          return (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {t('admin.scholarship.recordVerdict.assistanceLabel')}
                {cur != null && <span className="ml-1 font-semibold text-gray-800">RM{cur.toLocaleString()}</span>}
              </label>
              <input type="range" min={1500} max={3000} step={500}
                value={cur ?? 1500} disabled={!!busy}
                onChange={(e) => doSetAwardAmount(Number(e.target.value))}
                className="w-full accent-primary-500" />
              <div className="flex justify-between text-[11px] text-gray-400">
                <span>RM1,500</span><span>RM2,000</span><span>RM2,500</span><span>RM3,000</span>
              </div>
              {cur == null && <p className="mt-0.5 text-[11px] text-gray-400">{t('admin.scholarship.recordVerdict.assistanceNone')}</p>}
            </div>
          )
        })()}

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

        {/* Decision actions */}
        {app.status === 'accepted' ? (
          <div className="space-y-2 border-t pt-3">
            <p className="flex items-center gap-1.5 text-sm text-green-700">
              <span aria-hidden>✓</span>
              {t('admin.scholarship.acceptedBy')} {app.verified_by || '—'}
              {app.verified_at ? ` · ${new Date(app.verified_at).toLocaleDateString()}` : ''}
            </p>
            {canWrite && (
              <button onClick={() => doReject('contractual')} disabled={!!busy}
                className="px-4 py-2 border border-red-300 text-red-700 rounded-lg text-sm disabled:opacity-50">
                {busy === 'reject' ? t('admin.scholarship.reject.running') : t('admin.scholarship.reject.declineContractual')}
              </button>
            )}
          </div>
        ) : ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status) ? (
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
              <div className="grid grid-cols-2 gap-2">
                <button onClick={doApprove} disabled={!!busy || !approveReady}
                  className="rounded-lg border border-green-600 bg-white px-4 py-2.5 text-sm font-medium text-green-700 hover:bg-green-600 hover:text-white active:bg-green-600 active:text-white disabled:opacity-50">
                  {busy === 'verdict' ? t('common.loading') : t('admin.scholarship.recordVerdict.approve')}
                </button>
                <button onClick={() => doReject('interview')} disabled={!!busy || !decisionReady}
                  className="rounded-lg border border-red-500 bg-white px-4 py-2.5 text-sm font-medium text-red-700 hover:bg-red-600 hover:text-white active:bg-red-600 active:text-white disabled:opacity-50">
                  {busy === 'reject' ? t('admin.scholarship.reject.running') : t('admin.scholarship.recordVerdict.decline')}
                </button>
              </div>
              {decisionReady && !hasAssistance && (
                <p className="text-[11px] text-amber-600">{t('admin.scholarship.recordVerdict.approveNeedsAmount')}</p>
              )}
              <button onClick={doSaveVerdict} disabled={!!busy}
                className="w-full px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                {busy === 'verdict' ? t('common.loading') : t('admin.scholarship.recordVerdict.save')}
              </button>
            </div>
          )
        ) : (
          <p className="text-sm text-gray-400">{t('admin.scholarship.notShortlisted')}</p>
        )}

        {/* Feedback message */}
        {verdictMsg && (
          <p className={`text-xs rounded p-2 ${verdictMsgTone === 'ok' ? 'text-green-700 bg-green-50' : 'text-amber-800 bg-amber-50'}`}>{verdictMsg}</p>
        )}

        {error && <p className="text-red-600 text-xs">{error}</p>}
      </div>

      {/* ── Assign a reviewer (F7) — SUPER-ONLY + audited. First assignment is gated on
            readiness (no open queries OR the SLA lapsed); reassign is allowed any time. ─── */}
      {isSuper && (() => {
        const ready = app.query_sla?.ready_for_assignment ?? false
        const firstAssignBlocked = !app.assigned_to_id && !ready
        return (
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">{t('admin.scholarship.assignTitle')}</h2>
          {app.assigned_to_id && (
            <p className="text-xs text-gray-500">
              {t('admin.scholarship.assign.current', { name: app.assigned_to_name || '' })}
            </p>
          )}
          <select
            value={app.assigned_to_id ?? ''}
            disabled={!!busy || firstAssignBlocked}
            title={firstAssignBlocked ? t('admin.scholarship.assign.error.not_ready') : undefined}
            onChange={(e) => doAssign(e.target.value ? Number(e.target.value) : null)}
            className="border rounded-lg px-3 py-2 text-sm w-full disabled:bg-gray-100 disabled:text-gray-400"
          >
            <option value="">{t('admin.scholarship.unassigned')}</option>
            {admins.filter((a) => a.role === 'reviewer' || a.role === 'super')
              .map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          {firstAssignBlocked && (
            <p className="text-xs text-amber-600">{t('admin.scholarship.assign.notReadyHint')}</p>
          )}
        </div>
        )
      })()}

      </div>{/* end RIGHT column */}

      </div>{/* end cockpit grid */}
      </>)}
    </div>
  )
}
