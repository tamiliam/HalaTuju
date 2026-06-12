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
  sortByWeight,
  type ActionIcon,
  type ConfirmTarget,
} from '@/lib/actionCentre'
import DocumentHelpCoach, { CoachCard } from '@/components/DocumentHelpCoach'
import IncomeRouteSwitch from '@/components/IncomeRouteSwitch'

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
}) {
  const { t, locale } = useT()
  const src = titleSourceFor(item)
  const tParams = localiseParams(item.params, t)
  const title = src.kind === 'raw' ? src.text : t(src.titleKey, tParams)
  const desc = src.kind === 'i18n' ? t(src.descKey, tParams) : ''
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
      const doc = await recordDocument(
        { doc_type: item.doc_type, storage_path, original_filename: file.name, content_type: file.type, size: file.size },
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

  // A completed item — stays on the page as a calm green "Done" card (no action),
  // so the student gets the satisfaction of seeing what they've cleared.
  if (done) {
    return (
      <div className="rounded-2xl border border-green-100 bg-green-50/40 p-5 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-500">
            <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-gray-400">{fromLabel}</p>
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold text-gray-500 line-through decoration-green-300">{title}</h3>
              <span className="shrink-0 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-green-800">
                {t('scholarship.actionCentre.done')}
              </span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-500">
          <KindIcon icon={iconFor(item.kind)} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-gray-400">{fromLabel}</p>
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <span className="shrink-0 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-800">
              {t('scholarship.actionCentre.toDo')}
            </span>
          </div>
          {desc && <p className="mt-1 text-sm text-gray-500">{desc}</p>}

          {/* ── Action ─────────────────────────────────────────────── */}
          <div className="mt-4">
            {item.kind === 'doc' && (
              <>
                <label className={`block w-full cursor-pointer rounded-xl bg-primary-500 px-4 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-primary-600 ${busy ? 'opacity-50' : ''}`}>
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
                {/* Contextual Cikgu Gopal — appears only when the just-uploaded document
                    didn't pass its scan; advises the fix, then the student re-uploads. */}
                {coachDoc && (
                  <DocumentHelpCoach doc={coachDoc} token={token} t={t} lang={locale} />
                )}
                {/* Rare: the upload landed but its scan hasn't finished yet — keep the task
                    open and reassure, rather than ticking it Done on an unchecked file. */}
                {stillChecking && (
                  <p className="mt-3 text-sm text-gray-500">{t('scholarship.actionCentre.stillChecking')}</p>
                )}
              </>
            )}

            {/* Typed reply — explanation/clarify always, and (post-submit only) a
                non-pathway `confirm` ticket too: the form is locked, so the student
                can't go back and edit it; they respond in writing instead. */}
            {(item.kind === 'explanation' || item.kind === 'clarify' ||
              (formLocked && item.kind === 'confirm' && item.code !== 'pathway_confirm')) && (
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
                  className="w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
                >
                  {busy ? t('scholarship.actionCentre.sending') : t('scholarship.actionCentre.send')}
                </button>
                {/* Phase 2: Gopal's gentle steer when the answer was totally off-topic. */}
                {nudge && <CoachCard t={t} loading={false} body={nudge} />}
              </div>
            )}

            {item.kind === 'confirm' && item.code === 'pathway_confirm' && (
              <button
                type="button"
                onClick={onAffirm}
                disabled={busy}
                className="w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
              >
                {busy ? t('scholarship.actionCentre.sending') : t('scholarship.actionCentre.confirmPathwayYes')}
              </button>
            )}

            {/* Pre-submit only: a `confirm` ticket jumps the student to the form tab
                that resolves it. Post-submit (formLocked) uses the typed reply above. */}
            {!formLocked && item.kind === 'confirm' && item.code !== 'pathway_confirm' && (
              <button
                type="button"
                onClick={() => onConfirm(confirmTargetFor(item.fact))}
                className="w-full rounded-xl border border-primary-500 px-4 py-2.5 text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-50"
              >
                {t('scholarship.actionCentre.review')}
              </button>
            )}

            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
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
  email = '',
  applicationId,
}: {
  token: string | null
  studentName?: string
  /** Send the student to the section that resolves a `confirm` ticket. */
  onConfirm?: (target: ConfirmTarget) => void
  /** Post-submit mount: the application is locked (no form). Confirm tickets become
   *  typed replies, and the empty state shows a calm "all set, we'll be in touch"
   *  message instead of rendering nothing. */
  formLocked?: boolean
  /** The address updates are sent to — shown in the locked empty-state message. */
  email?: string
  /** Post-submit only: enables the in-place income route switch on an income task
   *  (the form/wizard is locked, so this is the student's only way to change route). */
  applicationId?: number
}) {
  const { t } = useT()
  const [open, setOpen] = useState<ResolutionItem[]>([])
  const [resolved, setResolved] = useState<ResolutionItem[]>([])
  const [loaded, setLoaded] = useState(false)

  const fetchItems = useCallback(async () => {
    if (!token) return
    try {
      const r = await getResolutionItems({ token })
      setOpen(r.open)
      setResolved(r.resolved)
    } catch {
      // Treat a fetch failure as "nothing to show" — the Action Centre is
      // additive; it must never block the rest of the page.
      setOpen([])
      setResolved([])
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
    <div className="rounded-2xl border border-green-200 bg-green-50 p-6">
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-green-600 text-sm text-white">✓</span>
        <h2 className="font-semibold text-gray-900">{t('scholarship.actionCentre.awaitTitle')}</h2>
      </div>
      <p className="mt-1 text-sm text-gray-700">
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

  // Nothing at all: post-submit → the await card; shortlisted → invisible.
  if (open.length === 0 && resolved.length === 0) {
    return formLocked ? <section className="mb-8">{awaitCard}</section> : null
  }

  const { done, total, pct } = computeProgress(open, resolved)

  // Post-submit, everything cleared: the await card + the completed Done cards.
  if (formLocked && open.length === 0) {
    return <section className="mb-8">{awaitCard}{doneCards}</section>
  }

  // Pending tasks (or a shortlisted student with history).
  return (
    <section className="mb-8">
      {/* Header */}
      <h2 className="text-xl font-bold text-gray-900">
        {t(formLocked ? 'scholarship.actionCentre.lockedTitle' : 'scholarship.actionCentre.title', { name: firstName })}
      </h2>
      <p className="mt-1 text-sm text-gray-600">
        {t(formLocked ? 'scholarship.actionCentre.lockedIntro' : 'scholarship.actionCentre.intro')}
      </p>

      {/* Progress */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs font-medium text-gray-500">
          <span>{t('scholarship.actionCentre.progressDone', { done: String(done), total: String(total) })}</span>
          <span>{t('scholarship.actionCentre.percentComplete', { pct: String(pct) })}</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
          <div className="h-full rounded-full bg-primary-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Open tasks first, then the completed ones as green Done cards. */}
      {open.length > 0 && (
        <div className="mt-4 space-y-4">
          {sortByWeight(open).map((item) => (
            <ActionCard
              key={item.id}
              item={item}
              token={token}
              onResolved={fetchItems}
              onConfirm={(target) => onConfirm?.(target)}
              formLocked={formLocked}
            />
          ))}
        </div>
      )}
      {/* Post-submit, when an income task is open, the student can change how they prove
          income (the form/wizard is locked, so this is their only route to switch). One
          entry for the whole income section, not per-ticket. */}
      {formLocked && applicationId && open.some((i) => i.fact === 'income') && (
        <div className="mt-4">
          <IncomeRouteSwitch token={token} applicationId={applicationId} onDone={fetchItems} />
        </div>
      )}
      {doneCards}
      {/* Shortlisted (pre-submit) all-done banner. */}
      {!formLocked && open.length === 0 && (
        <div className="mt-4 flex items-center gap-3 rounded-2xl border border-green-200 bg-green-50 p-5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-600 text-sm text-white">✓</span>
          <p className="font-medium text-green-900">{t('scholarship.actionCentre.allDone')}</p>
        </div>
      )}
    </section>
  )
}
