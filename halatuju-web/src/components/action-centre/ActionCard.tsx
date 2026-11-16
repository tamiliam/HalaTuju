'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  resolveResolutionItem,
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  type ResolutionItem,
  type ApplicantDocument,
} from '@/lib/api'
import {
  iconFor,
  titleSourceFor,
  attributionFor,
  confirmTargetFor,
  localiseParams,
  itemCopy,
  clusterMemberOf,
  latestDocFor,
  needsOfficerEye,
  profilePickerHref,
  onboardingAskFor,
  whyKeyFor,
  type ConfirmTarget,
} from '@/lib/actionCentre'
import DocumentHelpCoach, { CoachCard } from '@/components/DocumentHelpCoach'
import IncomeClusterCoach from '@/components/IncomeClusterCoach'
import { setOnboardingReturn } from '@/lib/scholarship'
import type { DocumentLimits } from '@/lib/api'; import { PHONE_SECTION } from '@/lib/phoneSection'; import { PHONE_PILL_SM } from '@/lib/phonePill'
import { KindIcon } from './KindIcon'
import { UploadButtons } from './UploadButtons'
import { SetAsideCard, DoneCard, OfficerHoldCard } from './StatusCards'

// Confirm-kind queries the student answers with a single tap (resolved in place via onAffirm) —
// the pathway confirmation and the household-size confirmation. Every other confirm jumps the
// student to the form tab that fixes the underlying fact (or, once locked, a typed reply).
const ONE_TAP_CONFIRM = new Set(['pathway_confirm', 'household_size_confirm', 'pathway_type_switch'])

// ── Per-ticket card ───────────────────────────────────────────────────────

export function ActionCard({
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
  limits = null,
  docsLocked = false,
  openDocTypes = [],
}: {
  /** H5: the documents stage lock (served with the list). Locked hides Upload and Take a photo,
   *  unless this item's type is one of `openDocTypes` (the post-lock asks stay uploadable). */
  docsLocked?: boolean
  openDocTypes?: string[]
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
  limits?: DocumentLimits | null   // served upload limits; the docs tab's early refusal, loaded on a pick (M4)
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

  // Returned: an upload arrived and did not clear the ask (the backend stamped `attempts`), or the
  // latest file we hold reads as a problem. Not a fresh ask: say so, with the reason.
  const returned = item.kind === 'doc'
    && (attempts > 0 || (!!coachDoc && !!coachDoc.vision_fields?.student_verdict && coachDoc.vision_fields.student_verdict !== 'ok'))

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
  // STPM CGPA C4: an ask answered on an onboarding page (the STPM results step), which then returns here.
  const onboardingAsk = onboardingAskFor(item.code)

  // #15a: re-surface the doc-anchored coach for a NON-cluster held task from the fetched
  // documents, so a page reload keeps Gopal's advice (not just the in-session upload).
  // DocumentHelpCoach self-hides if the latest doc actually reads clean. Cluster tasks use
  // the cluster coach instead, so clear any in-session coachDoc for them.
  useEffect(() => {
    if (isClusterTask) { setCoachDoc(null); return }
    setCoachDoc((prev) => prev ?? latestDocFor(docs, item.doc_type))
  }, [docs, isClusterTask, item.doc_type])

  // doc: refuse a file the server would (too big / not a photo or PDF — Mobile M4), else upload the named
  // doc_type, run its scan, re-fetch the tickets. A clean scan resolves the task server-side (this card
  // unmounts); a mismatch keeps it open and surfaces Gopal's advice for a clean re-upload.
  const onFile = async (file: File) => {
    const refusal = await import(/* webpackChunkName: 'mi' */ '@/lib/uploadCheck').then((m) => m.refusalFor(file, limits), () => null)
    if (!token || refusal) { setError(refusal ? t(refusal.key, refusal.params) : null); return }
    setBusy(true); setError(null)
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
    } catch (e) {
      const code = (e as { code?: string })?.code
      if (code === 'documents_locked') onResolved()   // the stage moved on: the list drops this card
      setError(
        code === 'documents_locked' ? ((e as Error).message || t('scholarship.actionCentre.uploadError'))
        : code === 'unsupported_format' || code === 'upload_incomplete' || code === 'bad_file'
          ? t('scholarship.actionCentre.badFile')
        : code === 'file_too_large' ? t('scholarship.docs.file_too_large',
            { mb: String((e as { fieldErrors?: { max_mb?: number } })?.fieldErrors?.max_mb ?? limits?.max_doc_size_mb ?? 8) })
        : t('scholarship.actionCentre.uploadError'),
      )
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

  if (setAside) return <SetAsideCard fromLabel={fromLabel} title={title} />

  if (done) return <DoneCard fromLabel={fromLabel} title={title} />

  if (needsOfficerEye(item)) return <OfficerHoldCard fromLabel={fromLabel} />

  return (
    <div className={PHONE_SECTION}>
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-shape">
          <KindIcon icon={iconFor(item.kind)} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-ground-400">{fromLabel}</p>
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-ground-900 whitespace-pre-line">{title}</h3>
            <span className={`shrink-0 rounded-full bg-caution-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-caution-800 ${PHONE_PILL_SM}`}>
              {t('scholarship.actionCentre.toDo')}
            </span>
          </div>
          {/* A returned document: it is back in "Needs you" with the reason (owner 15 Nov: the bar and
              the list show the true state). The reason is the retry note; with a coach verdict but no
              note, the coach beneath explains. */}
          {returned && (
            <div role="status" className="mt-2 rounded-lg border border-caution-200 bg-caution-50 px-3 py-2">
              <p className="text-sm font-semibold text-caution-800">{t('scholarship.actionCentre.needAgain')}</p>
              <p className="text-sm text-caution-800">{retryNote || t('scholarship.actionCentre.needAgainBody')}</p>
            </div>
          )}
          {desc && <p className="mt-1 text-sm text-ground-500">{desc}</p>}
          <p className="mt-1 text-sm text-ground-600">{t(whyKeyFor(item))}</p>

          {/* ── Action ─────────────────────────────────────────────── */}
          <div className="mt-4">
            {item.kind === 'doc' && (
              <>
                {!(docsLocked && !openDocTypes.includes(item.doc_type)) && <UploadButtons busy={busy} onFile={onFile} />}
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
                className="flex min-h-11 w-full items-center justify-center rounded-xl bg-brand-fill px-4 py-2.5 text-center text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover"
              >
                {t(isPismpSwitch
                  ? 'scholarship.actionCentre.confirmPathwaySwitchOnProfile'
                  : 'scholarship.actionCentre.updatePathwayOnProfile')}
              </a>
            )}

            {onboardingAsk && (
              <a
                href={onboardingAsk.path}
                onClick={() => setOnboardingReturn('/scholarship/application')}
                className="flex min-h-11 w-full items-center justify-center rounded-xl bg-brand-fill px-4 py-2.5 text-center text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover"
              >
                {t(onboardingAsk.buttonKey)}
              </a>
            )}

            {((item.kind === 'explanation' && item.code !== 'pathway_undeclared' && !onboardingAsk) || item.kind === 'clarify' ||
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
                  className="min-h-11 w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50"
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
                className="min-h-11 w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50"
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
                className="min-h-11 w-full rounded-xl border border-brand-shape px-4 py-2.5 text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-50"
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
