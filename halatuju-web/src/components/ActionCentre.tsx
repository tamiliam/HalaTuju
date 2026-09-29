'use client'

/**
 * Student Action Centre (Sprint 4 of the verification-verdict roadmap).
 *
 * A friendly, self-service "things to finish" queue shown at the TOP of the
 * post-shortlist /application page. It consumes the resolution-ticket endpoints
 * and lets a student clear each gap in place:
 *   doc         → upload the named document
 *   explanation → type a short reply
 *   confirm     → jump to the right section to re-check a fact
 *
 * Pure logic lives in lib/actionCentre.ts (unit-tested). This file is just the
 * presentation + the three resolve flows.
 */

import { useEffect, useState, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import {
  getResolutionItems,
  resolveResolutionItem,
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  listDocuments,
  type ResolutionItem,
  type ApplicantDocument,
} from '@/lib/api'
import {
  computeProgress,
  iconFor,
  titleSourceFor,
  attributionFor,
  confirmTargetFor,
  localiseParams,
  itemCopy,
  sortByWeight,
  clusterMemberOf,
  latestDocFor,
  needsOfficerEye,
  profilePickerHref,
  type ActionIcon,
  type ConfirmTarget,
} from '@/lib/actionCentre'
import DocumentHelpCoach, { CoachCard } from '@/components/DocumentHelpCoach'
// The two POST-AWARD cards (bank details, Vircle) only an awarded student ever holds: fetched on
// demand so they stay out of every applicant's first-load JS. See the note in that file.
import PostAwardTask from '@/components/scholarship/LazyPostAwardTask'
import IncomeClusterCoach from '@/components/IncomeClusterCoach'
import IncomeRouteSwitch from '@/components/IncomeRouteSwitch'

// Confirm-kind queries the student answers with a single tap (resolved in place via onAffirm) —
// the pathway confirmation and the household-size confirmation. Every other confirm jumps the
// student to the form tab that fixes the underlying fact (or, once locked, a typed reply).
const ONE_TAP_CONFIRM = new Set(['pathway_confirm', 'household_size_confirm', 'pathway_type_switch'])

// ── Icons (inline SVG, blue circle bg set by the caller) ──────────────────

function KindIcon({ icon }: { icon: ActionIcon }) {
  const paths: Record<ActionIcon, string> = {
    document: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
    checklist: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7l2 2 4-4',
    chat: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
  }
  return (
    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" d={paths[icon]} />
    </svg>
  )
}

// ── Per-ticket card ───────────────────────────────────────────────────────

function ActionCard({
  item,
  token,
  onResolved,
  onConfirm,
  formLocked = false,
  done = false,
  setAside = false,
  docs = [],
  incomeRoute = '',
  incomeEarner = '',
  showClusterCoach = true,
}: {
  item: ResolutionItem
  token: string | null
  onResolved: () => void
  onConfirm: (target: ConfirmTarget) => void
  /** Post-submit: the application form is locked, so a `confirm` ticket can't
   *  send the student back to a form tab. They respond with a typed reply instead. */
  formLocked?: boolean
  /** A resolved item — stays on the page as a green "Done" card (no action), so the
   *  student sees what they've completed. */
  done?: boolean
  /** A funded student's leftover review-phase query — shown struck-through (amber) as
   *  "Set aside" (no longer needed now they're awarded); not actionable, not deleted. */
  setAside?: boolean
  /** The student's fetched documents — lets Gopal's coach survive a reload (audit #15a)
   *  and lets an income task mount the per-earner cluster coach (audit #15b). */
  docs?: ApplicantDocument[]
  /** Income route + STR-route earner, so an income doc-task can key the cluster coach. */
  incomeRoute?: string
  incomeEarner?: string
  /** One cluster coach per earner: true only on the FIRST open income task of a member, so
   *  two tasks for the same earner don't render duplicate coaches. */
  showClusterCoach?: boolean
}) {
  const { t, locale } = useT()
  const src = titleSourceFor(item)
  const tParams = localiseParams(item.params, t)
  const { title, desc } = src.kind === 'raw' ? { title: src.text, desc: '' } : itemCopy(t, src, tParams)
  // Human-aware re-ask (#83, owner 2026-07-08): the backend stamps `attempts` on a doc-task when
  // an upload arrived but did NOT clear it (the student re-sent the same file, or a different-but-
  // still-wrong one). Acknowledge what happened before repeating the ask, like a human would.
  const attempts = Number(item.params?.attempts || 0)
  const retryNote = item.kind === 'doc' && attempts > 0
    ? t(item.params?.attempt_same_file
        ? 'scholarship.actionCentre.retry.sameFile'
        : item.params?.attempt_rejected
          ? 'scholarship.actionCentre.retry.keptPrevious'
          : 'scholarship.actionCentre.retry.notAccepted')
    : ''
  // "From our review assistant" (system / Check 2) vs "From your reviewer" (officer) —
  // so the student knows who's asking, matching the tested Action-Centre design.
  const fromLabel = t(attributionFor(item) === 'reviewer'
    ? 'scholarship.actionCentre.fromReviewer'
    : 'scholarship.actionCentre.fromAssistant')

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [text, setText] = useState('')
  // After an upload that DIDN'T clear the task (the scan flagged a mismatch/unreadable),
  // hold the uploaded doc so Cikgu Gopal can advise inline — the same contextual coach
  // as the Documents tab. Cleared on a clean upload (the card then unmounts on refresh).
  const [coachDoc, setCoachDoc] = useState<ApplicantDocument | null>(null)
  // A rare 'pending' verdict — the upload arrived but its scan hasn't finished (a true
  // read failure; the interactive upload normally reads synchronously). The task stays
  // open; we reassure calmly rather than showing Gopal's "this is wrong" coach.
  const [stillChecking, setStillChecking] = useState(false)
  // Phase 2: when a typed answer comes back judged TOTALLY off-topic, Gopal's gentle
  // one-line steer; the task stays open. Cleared as soon as the student edits the text.
  const [nudge, setNudge] = useState<string | null>(null)

  // Income tasks speak with the single per-earner cluster coach, not the per-document one
  // (audit #15b). Membership is derived once (module helper); a member-less income task or a
  // non-income doc uses the doc-anchored coach instead.
  const clusterMember = clusterMemberOf(item, incomeRoute, incomeEarner)
  const isClusterTask = !!clusterMember

  // TD-161: a PISMP pathway can't be settled by a one-tap Yes — the offer letter never states the
  // aliran (SK/SJKT/SJKC), so the student pins the exact course on the profile Aliran/Bidang picker
  // (which reconciles chosen_pathway + the catalogue link and auto-clears this query). This applies to
  // BOTH a PISMP type-switch AND an undeclared-PISMP offer; every other type switch (STPM →
  // diploma/degree/asasi/matric) is a plain one-tap confirm. The inferred aliran (from the student's
  // SPM vernacular subject) rides along as ?aliran so the picker can pre-select it.
  // A PISMP switch routes to the profile Aliran picker ONLY when the offer's bidang did NOT resolve to
  // a unique course (multi-aliran — English/BM/Maths). When it DID resolve (a vernacular bidang like
  // Bahasa Tamil → course_id present), it's a plain one-tap confirm that pins the named course.
  const pismpResolved = typeof item.params?.course_id === 'string' && !!item.params.course_id
  const isPismpSwitch = item.code === 'pathway_type_switch'
    && item.params?.offer_pathway === 'pismp' && !pismpResolved
  const routesToPicker = item.code === 'pathway_undeclared' || isPismpSwitch
  const pickerHref = profilePickerHref(item)

  // #15a: re-surface the doc-anchored coach for a NON-cluster held task from the fetched
  // documents, so a page reload keeps Gopal's advice (not just the in-session upload).
  // DocumentHelpCoach self-hides if the latest doc actually reads clean. Cluster tasks use
  // the cluster coach instead, so clear any in-session coachDoc for them.
  useEffect(() => {
    if (isClusterTask) { setCoachDoc(null); return }
    setCoachDoc((prev) => prev ?? latestDocFor(docs, item.doc_type))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs, isClusterTask, item.doc_type])

  // doc: upload the named doc_type, run its scan, then re-fetch the tickets. A clean
  // scan resolves the task server-side (this card unmounts); a mismatch keeps it open
  // and surfaces Gopal's advice for a clean re-upload.
  const onFile = async (file: File) => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument(item.doc_type, { token })
      await uploadFileToSignedUrl(upload_url, file)
      // A per-person doc request (officer asked for e.g. the father's salary slip) carries
      // the target member in params — tag it so the upload lands in the right slot (closes
      // the salary-route Action-Centre tagging gap). STR-route income docs are re-tagged
      // server-side from income_earner regardless, so this only matters on the salary route.
      const member = typeof item.params?.household_member === 'string' ? item.params.household_member : ''
      // A reviewer (officer_N) request gets its own document slot keyed by its code, so
      // multiple "Other" requests — and cross-person income docs — don't overwrite each
      // other. System items (e.g. results_slip_missing) keep the shared slot (no code).
      const requestCode = item.code.startsWith('officer_') ? item.code : ''
      const doc = await recordDocument(
        { doc_type: item.doc_type, household_member: member, request_code: requestCode, storage_path, original_filename: file.name, content_type: file.type, size: file.size },
        { token },
      )
      if (doc.match_verdict === 'pending') {
        // Not scanned yet — hold the task open, reassure (no red coach).
        setStillChecking(true)
        setCoachDoc(null)
      } else {
        setStillChecking(false)
        setCoachDoc(doc.match_verdict && doc.match_verdict !== 'ok' ? doc : null)
      }
      onResolved()
    } catch {
      setError(t('scholarship.actionCentre.uploadError'))
    } finally {
      setBusy(false)
    }
  }

  // explanation: POST the typed reply (with the displayed question, for the relevance
  // check). A totally off-topic answer comes back with a Gopal nudge — keep the task
  // open and show his steer; otherwise it resolved and the card clears on re-fetch.
  const onSend = async () => {
    if (!token || !text.trim()) return
    setBusy(true)
    setError(null)
    try {
      const r = await resolveResolutionItem(item.id, text.trim(), { token }, title)
      if (r.nudge) setNudge(r.nudge || t('scholarship.actionCentre.relevanceNudge'))
      else onResolved()
    } catch {
      setError(t('scholarship.actionCentre.sendError'))
    } finally {
      setBusy(false)
    }
  }

  // pathway_confirm: the student answers Yes in place — the backend writes their
  // final chosen pathway (no navigate, no officer).
  const onAffirm = async () => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await resolveResolutionItem(item.id, 'confirmed', { token })
      onResolved()
    } catch {
      setError(t('scholarship.actionCentre.sendError'))
    } finally {
      setBusy(false)
    }
  }

  // A funded student's leftover review-phase query — shown struck-through in AMBER as
  // "Set aside": it belonged to the review and is no longer needed now they're awarded.
  // Not a to-do, not green/done, not deleted (the officer still sees it as unanswered).
  if (setAside) {
    return (
      <div className="rounded-2xl border border-caution-100 bg-caution-50/40 p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-caution-400">
            <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12h12" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-ground-400">{fromLabel}</p>
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-ground-500 line-through decoration-caution-300">{title}</h3>
              <span className="shrink-0 rounded-full bg-caution-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-caution-800">
                {t('scholarship.actionCentre.setAside')}
              </span>
            </div>
            <p className="mt-1 text-sm text-ground-500">{t('scholarship.actionCentre.setAsideNote')}</p>
          </div>
        </div>
      </div>
    )
  }

  // A completed item — stays on the page as a calm green "Done" card (no action),
  // so the student gets the satisfaction of seeing what they've cleared.
  if (done) {
    return (
      <div className="rounded-2xl border border-positive-100 bg-positive-50/40 p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-positive-500">
            <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-ground-400">{fromLabel}</p>
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-ground-500 line-through decoration-positive-300">{title}</h3>
              <span className="shrink-0 rounded-full bg-positive-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-positive-800">
                {t('scholarship.actionCentre.done')}
              </span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Circuit-breaker (Phase 2/4): after repeated not-usable re-uploads the loop was stopped and this
  // request handed to a person. Swap the upload prompt for a calm "we're reviewing this" state — no
  // upload button, no coach, no retry note — so a genuine student is never trapped re-uploading.
  if (needsOfficerEye(item)) {
    return (
      <div className="rounded-2xl border border-info-100 bg-info-50/40 p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-info-500">
            <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-ground-400">{fromLabel}</p>
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-ground-900">{t('scholarship.actionCentre.officerHold.title')}</h3>
              <span className="shrink-0 rounded-full bg-info-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-info-800">
                {t('scholarship.actionCentre.officerHold.chip')}
              </span>
            </div>
            <p className="mt-1 text-sm text-ground-600">{t('scholarship.actionCentre.officerHold.body')}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-ground-100 bg-ground-0 p-5 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-shape">
          <KindIcon icon={iconFor(item.kind)} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-ground-400">{fromLabel}</p>
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-ground-900">{title}</h3>
            <span className="shrink-0 rounded-full bg-caution-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-caution-800">
              {t('scholarship.actionCentre.toDo')}
            </span>
          </div>
          {retryNote && (
            <p className="mt-1 rounded-lg bg-caution-50 px-3 py-2 text-sm font-medium text-caution-800">
              {retryNote}
            </p>
          )}
          {desc && <p className="mt-1 text-sm text-ground-500">{desc}</p>}

          {/* ── Action ─────────────────────────────────────────────── */}
          <div className="mt-4">
            {item.kind === 'doc' && (
              <>
                <label className={`block w-full cursor-pointer rounded-xl bg-brand-fill px-4 py-2.5 text-center text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover ${busy ? 'opacity-50' : ''}`}>
                  {busy ? t('scholarship.actionCentre.uploading') : t('scholarship.actionCentre.upload')}
                  <input
                    type="file"
                    accept="image/*,.pdf"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) onFile(f)
                      e.target.value = ''
                    }}
                  />
                </label>
                {/* Contextual Cikgu Gopal. Income cluster docs (wrong-person slip/EPF, a
                    mismatching BC) speak through the single per-earner cluster coach — the
                    per-document coach returns null for them (audit #15b). Everything else uses
                    the doc-anchored coach, re-surfaced from the fetched docs on reload (#15a). */}
                {isClusterTask ? (
                  showClusterCoach && (
                    <div className="mt-3">
                      <IncomeClusterCoach
                        member={clusterMember}
                        route={incomeRoute || 'salary'}
                        docs={docs}
                        token={token}
                        t={t}
                        lang={locale}
                        coachLabelKey="scholarship.actionCentre.coachLabel"
                      />
                    </div>
                  )
                ) : coachDoc ? (
                  <DocumentHelpCoach doc={coachDoc} token={token} t={t} lang={locale} coachLabelKey="scholarship.actionCentre.coachLabel" />
                ) : null}
                {/* Rare: the upload landed but its scan hasn't finished yet — keep the task
                    open and reassure, rather than ticking it Done on an unchecked file. */}
                {stillChecking && (
                  <p className="mt-3 text-sm text-ground-500">{t('scholarship.actionCentre.stillChecking')}</p>
                )}
              </>
            )}

            {/* Typed reply — explanation/clarify always, and (post-submit only) a
                non-pathway `confirm` ticket too: the form is locked, so the student
                can't go back and edit it; they respond in writing instead. */}
            {/* pathway_undeclared (owner 2026-07-15): an ambiguous offer we can't pin (a PISMP offer
                with no aliran) — the student picks their exact course on the profile page rather than
                typing a reply. The query auto-clears once a real course lands. */}
            {/* pathway_undeclared, and a PISMP type-switch (TD-161): both need the profile Aliran/Bidang
                picker to pin an exact course — a one-tap Yes can't choose the aliran the offer omits.
                The inferred aliran rides along as ?aliran for the picker to pre-select. */}
            {routesToPicker && (
              <a
                href={pickerHref}
                className="block w-full rounded-xl bg-brand-fill px-4 py-2.5 text-center text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover"
              >
                {t(isPismpSwitch
                  ? 'scholarship.actionCentre.confirmPathwaySwitchOnProfile'
                  : 'scholarship.actionCentre.updatePathwayOnProfile')}
              </a>
            )}

            {((item.kind === 'explanation' && item.code !== 'pathway_undeclared') || item.kind === 'clarify' ||
              (formLocked && item.kind === 'confirm' && !ONE_TAP_CONFIRM.has(item.code))) && (
              <div className="space-y-2">
                <textarea
                  className="input"
                  rows={3}
                  placeholder={t('scholarship.actionCentre.explanationPlaceholder')}
                  value={text}
                  onChange={(e) => { setText(e.target.value); if (nudge) setNudge(null) }}
                  disabled={busy}
                />
                <button
                  type="button"
                  onClick={onSend}
                  disabled={busy || !text.trim()}
                  className="w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50"
                >
                  {busy ? t('scholarship.actionCentre.sending') : t('scholarship.actionCentre.send')}
                </button>
                {/* Phase 2: Gopal's gentle steer when the answer was totally off-topic. */}
                {nudge && <CoachCard t={t} loading={false} body={nudge} coachLabelKey="scholarship.actionCentre.coachLabel" />}
              </div>
            )}

            {/* One-tap confirm — but NOT a PISMP type-switch (that routes to the profile picker above). */}
            {item.kind === 'confirm' && ONE_TAP_CONFIRM.has(item.code) && !isPismpSwitch && (
              <button
                type="button"
                onClick={onAffirm}
                disabled={busy}
                className="w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50"
              >
                {busy ? t('scholarship.actionCentre.sending')
                  : t(item.code === 'household_size_confirm'
                      ? 'scholarship.actionCentre.confirmHouseholdSizeYes'
                      : item.code === 'pathway_type_switch'
                        ? 'scholarship.actionCentre.confirmPathwaySwitchYes'
                        : 'scholarship.actionCentre.confirmPathwayYes')}
              </button>
            )}

            {/* Pre-submit only: a `confirm` ticket jumps the student to the form tab
                that resolves it. Post-submit (formLocked) uses the typed reply above. */}
            {!formLocked && item.kind === 'confirm' && !ONE_TAP_CONFIRM.has(item.code) && (
              <button
                type="button"
                onClick={() => onConfirm(confirmTargetFor(item.fact))}
                className="w-full rounded-xl border border-brand-shape px-4 py-2.5 text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-50"
              >
                {t('scholarship.actionCentre.review')}
              </button>
            )}

            {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function ActionCentre({
  token,
  studentName,
  onConfirm,
  formLocked = false,
  funded = false,
  email = '',
  applicationId,
  incomeRoute = '',
  incomeEarner = '',
  contactPhone = '',
}: {
  token: string | null
  studentName?: string
  /** Send the student to the section that resolves a `confirm` ticket. */
  onConfirm?: (target: ConfirmTarget) => void
  /** Post-submit mount: the application is locked (no form). Confirm tickets become
   *  typed replies, and the empty state shows a calm "all set, we'll be in touch"
   *  message instead of rendering nothing. */
  formLocked?: boolean
  /** Funded student (awarded/active/maintenance). Switches the header to a warm,
   *  congratulatory tone matching the bank-details invitation email, rather than the
   *  "we're reviewing your application" copy used during the review phase. */
  funded?: boolean
  /** The address updates are sent to — shown in the locked empty-state message. */
  email?: string
  /** Post-submit only: enables the in-place income route switch on an income task
   *  (the form/wizard is locked, so this is the student's only way to change route). */
  applicationId?: number
  /** Income route + STR-route earner — let an income doc-task mount the per-earner
   *  cluster coach (audit #15b). Sourced from the application. */
  incomeRoute?: string
  incomeEarner?: string
  /** The student's phone on file — pre-fills the Vircle task's mobile field. They can
   *  correct it there if they registered with Vircle under a different number. */
  contactPhone?: string
}) {
  const { t } = useT()
  const [open, setOpen] = useState<ResolutionItem[]>([])
  const [resolved, setResolved] = useState<ResolutionItem[]>([])
  // Funded students: leftover review-phase queries shown struck-through amber ("set aside").
  const [setAside, setSetAside] = useState<ResolutionItem[]>([])
  // The student's documents — so Gopal's coach survives a reload and the cluster coach can
  // read the earner's cluster (audit #15). Fetched alongside the tickets; refreshed on every
  // resolve so an upload re-reads the cluster.
  const [docs, setDocs] = useState<ApplicantDocument[]>([])
  const [loaded, setLoaded] = useState(false)

  const fetchItems = useCallback(async () => {
    if (!token) return
    try {
      const [r, d] = await Promise.all([
        getResolutionItems({ token }),
        listDocuments({ token }).catch(() => ({ documents: [] as ApplicantDocument[] })),
      ])
      setOpen(r.open)
      setResolved(r.resolved)
      setSetAside(r.set_aside ?? [])
      setDocs(d.documents)
    } catch {
      // Treat a fetch failure as "nothing to show" — the Action Centre is
      // additive; it must never block the rest of the page.
      setOpen([])
      setResolved([])
      setSetAside([])
      setDocs([])
    } finally {
      setLoaded(true)
    }
  }, [token])

  useEffect(() => { fetchItems() }, [fetchItems])

  // Don't flash anything until we've checked.
  if (!loaded) return null

  const firstName = (studentName || '').trim().split(/\s+/)[0] || ''

  // The calm "all set — we'll be in touch" card (post-submit, nothing left to do).
  const awaitCard = (
    <div className="rounded-2xl border border-positive-200 bg-positive-50 p-6">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-positive-fill text-sm text-positive-fill-ink">✓</span>
        <h2 className="font-semibold text-ground-900">{t('scholarship.actionCentre.awaitTitle')}</h2>
      </div>
      <p className="mt-1 text-sm text-ground-700">
        {t('scholarship.actionCentre.awaitBody', { email: email || t('scholarship.nextSteps.whatNext.yourEmail') })}
      </p>
    </div>
  )

  // Resolved items stay on the page as green "Done" cards (the satisfaction of seeing
  // what you've cleared), shown beneath the open ones.
  const doneCards = resolved.length > 0 && (
    <div className="mt-4 space-y-4">
      {resolved.map((item) => (
        <ActionCard key={item.id} item={item} token={token} onResolved={fetchItems}
          onConfirm={(target) => onConfirm?.(target)} formLocked={formLocked} done />
      ))}
    </div>
  )

  // Funded students' set-aside review queries (struck-through amber), beneath the rest.
  const setAsideCards = setAside.length > 0 && (
    <div className="mt-4 space-y-4">
      {setAside.map((item) => (
        <ActionCard key={item.id} item={item} token={token} onResolved={fetchItems}
          onConfirm={(target) => onConfirm?.(target)} formLocked={formLocked} setAside />
      ))}
    </div>
  )

  // Nothing at all: post-submit → the await card; shortlisted → invisible.
  if (open.length === 0 && resolved.length === 0 && setAside.length === 0) {
    return formLocked ? <section className="mb-8">{awaitCard}</section> : null
  }

  const { done, total, pct } = computeProgress(open, resolved)

  // Post-submit, everything actionable cleared: the await card + set-aside + Done cards.
  if (formLocked && open.length === 0) {
    return <section className="mb-8">{awaitCard}{setAsideCards}{doneCards}</section>
  }

  // Pending tasks (or a shortlisted student with history).
  return (
    <section className="mb-8">
      {/* Header */}
      <h2 className="text-xl font-bold text-ground-900">
        {t(
          funded
            ? 'scholarship.actionCentre.fundedTitle'
            : formLocked ? 'scholarship.actionCentre.lockedTitle' : 'scholarship.actionCentre.title',
          { name: firstName },
        )}
      </h2>
      <p className="mt-1 text-sm text-ground-600">
        {t(
          funded
            ? 'scholarship.actionCentre.fundedIntro'
            : formLocked ? 'scholarship.actionCentre.lockedIntro' : 'scholarship.actionCentre.intro',
        )}
      </p>

      {/* Progress */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs font-medium text-ground-500">
          <span>{t('scholarship.actionCentre.progressDone', { done: String(done), total: String(total) })}</span>
          <span>{t('scholarship.actionCentre.percentComplete', { pct: String(pct) })}</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-ground-200">
          <div className="h-full rounded-full bg-brand-shape transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Open tasks first, then the completed ones as green Done cards. */}
      {open.length > 0 && (() => {
        // One cluster coach per earner: the FIRST open income task of each member is its
        // anchor; later tasks for the same earner suppress the (duplicate) coach.
        const sorted = sortByWeight(open)
        const clusterAnchor = new Map<string, number>()
        sorted.forEach((it) => {
          const m = clusterMemberOf(it, incomeRoute, incomeEarner)
          if (m && !clusterAnchor.has(m)) clusterAnchor.set(m, it.id)
        })
        return (
        <div className="mt-4 space-y-4">
          {sorted.map((item) => (
            // The post-award bank-details task is a bespoke upload-then-confirm card.
            item.code === 'bank_details_missing' ? (
              <PostAwardTask kind="bank" key={item.id} item={item} token={token} onResolved={fetchItems} />
            ) : item.code === 'vircle_setup_pending' ? (
              // Post-award Vircle setup: confirm the account is active + the mobile registered.
              <PostAwardTask
                kind="vircle" key={item.id} item={item} token={token}
                contactPhone={contactPhone} onResolved={fetchItems}
              />
            ) : (
              <ActionCard
                key={item.id}
                item={item}
                token={token}
                onResolved={fetchItems}
                onConfirm={(target) => onConfirm?.(target)}
                formLocked={formLocked}
                docs={docs}
                incomeRoute={incomeRoute}
                incomeEarner={incomeEarner}
                showClusterCoach={
                  clusterAnchor.get(clusterMemberOf(item, incomeRoute, incomeEarner)) === item.id
                }
              />
            )
          ))}
        </div>
        )
      })()}
      {/* Post-submit, when an income task is open, the student can change how they prove
          income (the form/wizard is locked, so this is their only route to switch). One
          entry for the whole income section, not per-ticket. */}
      {formLocked && applicationId && open.some((i) => i.fact === 'income') && (
        <div className="mt-4">
          <IncomeRouteSwitch token={token} applicationId={applicationId} onDone={fetchItems} />
        </div>
      )}
      {setAsideCards}
      {doneCards}
      {/* Shortlisted (pre-submit) all-done banner. */}
      {!formLocked && open.length === 0 && (
        <div className="mt-4 flex items-center gap-3 rounded-2xl border border-positive-200 bg-positive-50 p-5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-positive-fill text-sm text-positive-fill-ink">✓</span>
          <p className="font-medium text-positive-900">{t('scholarship.actionCentre.allDone')}</p>
        </div>
      )}
    </section>
  )
}
