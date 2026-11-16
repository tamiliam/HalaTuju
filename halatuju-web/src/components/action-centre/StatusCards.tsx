import { useT } from '@/lib/i18n'
import { PHONE_PILL_SM } from '@/lib/phonePill'

// The three non-actionable card states of an Action Centre ticket (moved verbatim out of
// ActionCard; H4 of the student-help run). Each is a pure view of the strings it is given.

type CardProps = { fromLabel: string; title?: string }

/** A funded student's leftover review-phase query — shown struck-through in AMBER as
 *  "Set aside": it belonged to the review and is no longer needed now they're awarded.
 *  Not a to-do, not green/done, not deleted (the officer still sees it as unanswered). */
export function SetAsideCard({ fromLabel, title }: CardProps) {
  const { t } = useT()
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
              <h3 className="font-semibold text-ground-500 line-through decoration-caution-300 whitespace-pre-line">{title}</h3>
              <span className={`shrink-0 rounded-full bg-caution-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-caution-800 ${PHONE_PILL_SM}`}>
                {t('scholarship.actionCentre.setAside')}
              </span>
            </div>
            <p className="mt-1 text-sm text-ground-500">{t('scholarship.actionCentre.setAsideNote')}</p>
          </div>
        </div>
      </div>
  )
}

/** A completed item — stays on the page as a calm green "Done" card (no action),
 *  so the student gets the satisfaction of seeing what they've cleared. */
export function DoneCard({ fromLabel, title, children }: CardProps & { children?: React.ReactNode }) {
  const { t } = useT()
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
              <h3 className="font-semibold text-ground-500 line-through decoration-positive-300 whitespace-pre-line">{title}</h3>
              <span className={`shrink-0 rounded-full bg-positive-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-positive-800 ${PHONE_PILL_SM}`}>
                {t('scholarship.actionCentre.done')}
              </span>
            </div>
            {children}
          </div>
        </div>
      </div>
  )
}

/** Circuit-breaker (Phase 2/4): after repeated not-usable re-uploads the loop was stopped and this
 *  request handed to a person. Swap the upload prompt for a calm "we're reviewing this" state — no
 *  upload button, no coach, no retry note — so a genuine student is never trapped re-uploading. */
export function OfficerHoldCard({ fromLabel }: CardProps) {
  const { t } = useT()
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
            <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
              <h3 className="font-semibold text-ground-900">{t('scholarship.actionCentre.officerHold.title')}</h3>
              <span className={`max-w-full rounded-full bg-info-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-info-800 ${PHONE_PILL_SM}`}>
                {t('scholarship.actionCentre.officerHold.chip')}
              </span>
            </div>
            <p className="mt-1 text-sm text-ground-600">{t('scholarship.actionCentre.officerHold.body')}</p>
          </div>
        </div>
      </div>
  )
}

/** A "Sent, we are checking" item (H5): the student has done their part. A typed answer quotes what was sent
 *  and says a reviewer reads it. No button:
 *  changing a sent document is the Replace of a later sprint. */
export function SentCard({ fromLabel, title, why, detail }: CardProps & { why: string; detail: string }) {
  const { t } = useT()
  return (
    <div className="rounded-2xl border border-info-100 bg-info-50/40 p-5 shadow-sm">
      <p className="text-xs font-medium text-ground-400">{fromLabel}</p>
      <h3 className="font-semibold text-ground-900 whitespace-pre-line">{title}</h3>
      {why && <p className="mt-1 text-sm text-ground-600">{why}</p>}
      {detail && <p className="mt-3 break-words rounded-lg bg-ground-50 px-3 py-2 text-sm text-ground-700">{detail}</p>}
      <p className="mt-2 text-sm text-ground-600">
        {t('scholarship.actionCentre.sentAnswer')}
      </p>
    </div>
  )
}

/** The Action Centre could not load (H5, the approved load-error design): one calm card and a retry. */
export function LoadErrorCard({ onRetry }: { onRetry: () => void }) {
  const { t } = useT()
  return (
    <div role="alert" className="rounded-2xl border border-ground-200 bg-white p-6 text-center shadow-sm">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-info-50">
        <svg className="h-8 w-8 text-info-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18M8.5 8.5A5 5 0 007 18h10.5M17 14.5A3.5 3.5 0 0015 8a5 5 0 00-2-.5" />
        </svg>
      </div>
      <h3 className="mt-4 text-lg font-bold text-ground-900">{t('scholarship.actionCentre.loadError.title')}</h3>
      <p className="mt-1 text-sm text-ground-600">{t('scholarship.actionCentre.loadError.body')}</p>
      <button type="button" onClick={onRetry} 
        className="mt-4 min-h-11 w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover">
        {t('scholarship.actionCentre.loadError.retry')}
      </button>
    </div>
  )
}
