'use client'

/**
 * The apply form's step furniture on a phone (Mobile M4, owner-approved mock 2026-11-01):
 *
 *   * `ApplyProgress` — "Step n/5 · <step>", five thick bars and the quiet "Saved on this device only ·
 *     nothing is sent until you submit" line (`scholarship.apply.commitNote`). It replaced the 6 × 56 px
 *     icon tab bar with 10 px labels; the desktop keeps its left step rail.
 *   * `ApplyFooter` — Back / Continue (Submit on the last step). Below `lg` a STICKY bar, `sticky` not
 *     `fixed` so it rests above the page's end, padded clear of the home bar. From `lg` the same bar,
 *     inside the form's column (a sticky Continue suits a long form on any screen). (No `useBottomBarInset`: the apply page raises no toast, and the route
 *     has no bytes to spare — add it the day a toast appears here.)
 *
 * The note is TRUE by construction: the form keeps its draft in this tab only (`lib/applyDraft.ts`).
 */
import { useT } from '@/lib/i18n'
import { PHONE_BLEED } from '@/lib/phoneSection'

export function ApplyProgress({ index, total, label }: { index: number; total: number; label: string }) {
  const { t } = useT()
  return (
    <div className="mb-4" data-testid="apply-progress">
      <p className="text-sm font-semibold text-ground-700">
        {t('scholarship.apply.step')} {index + 1}/{total} · {label}
      </p>
      <div className="mt-2 flex gap-1.5" aria-hidden>
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full ${i <= index ? 'bg-brand-shape' : 'bg-ground-200'}`} />
        ))}
      </div>
      <p className="mt-2 text-xs text-ground-500" data-testid="apply-draft-note">{t('scholarship.apply.commitNote')}</p>
    </div>
  )
}

export function ApplyFooter({ first, last, submitting, onBack, onNext }: {
  first: boolean
  last: boolean
  submitting: boolean
  onBack: () => void
  onNext: () => void
}) {
  const { t } = useT()
  return (
    <div data-page-bar data-testid="apply-footer"
      className={`sticky bottom-0 z-10 ${PHONE_BLEED} mb-4 flex gap-3 border-t border-ground-200 bg-ground-0 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:mx-0 lg:px-0`}>
      {!first && (
        <button type="button" onClick={onBack} className="btn-secondary min-h-12 flex-1">{t('scholarship.apply.back')}</button>
      )}
      {last ? (
        <button type="submit" disabled={submitting} className="btn-primary min-h-12 flex-[2] disabled:opacity-50">
          {submitting ? t('scholarship.apply.submitting') : t('scholarship.apply.submit')}
        </button>
      ) : (
        <button type="button" onClick={onNext} className="btn-primary min-h-12 flex-[2]">{t('scholarship.apply.continue')}</button>
      )}
    </div>
  )
}
