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
  listDocuments,
  type ResolutionItem,
  type ApplicantDocument,
  type DocumentLimits,
} from '@/lib/api'
import {
  computeProgress,
  sortByWeight,
  clusterMemberOf,
  type ConfirmTarget,
} from '@/lib/actionCentre'
// The two POST-AWARD cards (bank details, Vircle) only an awarded student ever holds: fetched on
// demand so they stay out of every applicant's first-load JS. See the note in that file.
import PostAwardTask from '@/components/scholarship/LazyPostAwardTask'
import IncomeRouteSwitch from '@/components/LazyIncomeRouteSwitch'   // TD-352: a minority's panel, on demand
import { ActionCard } from '@/components/action-centre/ActionCard'

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
  const [limits, setLimits] = useState<DocumentLimits | null>(null)
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
      setLimits('limits' in d ? d.limits ?? null : null)
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
              <PostAwardTask kind="bank" key={item.id} item={item} token={token} onResolved={fetchItems} limits={limits} />
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
                limits={limits}
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
