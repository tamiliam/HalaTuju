'use client'

/**
 * THE PHONE'S DECISION BAR (Mobile M6b; owner, 2026-11-03: "shows the chosen outcome and JUMPS to the decision
 * section; Save stays there"). On a phone the decision card lands below every document, so this bar keeps the
 * reviewer's place in reach: what she has chosen (Recommend / Decline / nothing yet), whether it is ready to
 * save, and ONE button that scrolls to the decision section.
 *
 * ⚠ IT DECIDES NOTHING AND SENDS NOTHING. No request, no outcome button, no Save: a decision is only ever
 * saved from the card, under its justification and amount. The bar READS the page's own values (`officerVerdict`,
 * `canSave`) — the same ones the card's buttons read — and shows only while the card offers Save
 * (`decisionBarShows` — ONE rule: the card gates its Save controls on it too; `view.decisionBar.test.tsx` pins both).
 *
 * `sticky`, not `fixed`: it rests in the flow at the page's end, so it never covers the post-award panels for
 * good. `data-page-bar` (rule 6), so a tab bar would give way to it. Phones only (`md:hidden`).
 */
import { isQcAccepted, showsDecisionCards } from '@/lib/officerCockpit'
import { stageStatus } from '@/lib/closeOffer'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T } from './shared'

/**
 * True exactly when the decision card shows its Recommend / Decline / Save controls: the card shows, it is not
 * locked, it is not a committed acceptance, the status admits a decision, and this person may write. ONE rule —
 * DecisionCard.tsx gates those controls on this function (M6b review), and the phone's bar shows on it.
 */
export function decisionBarShows({ app, decisionReopened, decisionRecorded, decisionLocked, canWrite }: {
  app: AdminScholarshipDetail
  decisionReopened: boolean
  decisionRecorded: boolean
  decisionLocked: boolean
  canWrite: boolean
}): boolean {
  if (!showsDecisionCards({ status: app.status, decisionReopened, decisionRecorded })) return false
  if (decisionLocked) return false
  if (isQcAccepted(stageStatus(app, 'recommended_at')) && !decisionReopened) return false
  if (!(decisionReopened || ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status))) return false
  return canWrite
}

export function DecisionBar({ t, outcome, canSave }: {
  t: T
  /** The page's `officerVerdict.overall`: 'accept', 'decline' or nothing chosen yet. */
  outcome: string | undefined
  /** Ready to save NOW: the page passes `canSave && !busy`, so a Save in flight never reads "Ready" (M6b review). */
  canSave: boolean
}) {
  // Nothing chosen yet is a dash: the card itself says how to choose (its hint is a sentence, too tall for a bar).
  const chosen = outcome === 'accept'
    ? t('admin.scholarship.recordVerdict.approve')
    : outcome === 'decline'
      ? t('admin.scholarship.recordVerdict.decline')
      : '—'
  return (
    <div data-page-bar data-decision-bar
      className="sticky bottom-0 z-20 -mx-4 border-t border-ground-200 bg-ground-0 px-4 pt-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.06)] md:hidden">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-ground-500">{t('admin.scholarship.decision.title')}</p>
          <p className="break-words text-sm font-semibold text-ground-900" data-bar-outcome>{chosen}</p>
          <p className={`text-xs font-medium ${canSave ? 'text-positive-700' : 'text-caution-700'}`}>
            {t(canSave ? 'admin.scholarship.decisionBar.ready' : 'admin.scholarship.decisionBar.notReady')}
          </p>
        </div>
        <button type="button"
          onClick={() => document.getElementById('decision-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          className="inline-flex min-h-12 shrink-0 items-center justify-center gap-1 rounded-lg bg-brand-fill px-4 text-sm font-semibold text-brand-fill-ink">
          {t('admin.scholarship.decisionBar.go')} ↓
        </button>
      </div>
    </div>
  )
}
