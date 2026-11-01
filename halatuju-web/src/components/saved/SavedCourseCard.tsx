'use client'

import Link from 'next/link'
import type { SavedCourseWithStatus } from '@/lib/api'
import { useT } from '@/lib/i18n'

/**
 * One saved course (Mobile M3): its name, a 44 px remove button, the two status pills — which WRAP,
 * because in Tamil "நான் விண்ணப்பித்தேன்!" and "எனக்குத் தேர்வு கிடைத்தது!" do not fit one row at
 * 360 — and a "Compare" tick box with its word beside it, on every width (it was desktop-only and
 * explained only by a hover `title=`).
 *
 * Pure: the page owns the data and the writes, so the design sandbox mounts the real card.
 */
export default function SavedCourseCard({
  course, subtitle, href, selected, updating, onToggleSelect, onRemove, onStatus,
}: {
  course: SavedCourseWithStatus
  /** "Institution · level · field", already worded by the page. */
  subtitle: string
  href: string
  selected: boolean
  updating: boolean
  onToggleSelect: () => void
  onRemove: () => void
  onStatus: (status: 'applied' | 'got_offer') => void
}) {
  const { t } = useT()
  const isApplied = course.interest_status === 'applied' || course.interest_status === 'got_offer'
  const hasOffer = course.interest_status === 'got_offer'
  const pill = 'inline-flex min-h-11 max-w-full items-center rounded-full px-4 py-2 text-left text-sm font-medium transition-colors disabled:opacity-50'
  const check = (
    <svg className="mr-1 h-3.5 w-3.5 shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden>
      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
    </svg>
  )

  return (
    <div className={`rounded-xl border bg-ground-0 p-4 transition-colors sm:p-5 ${
      selected ? 'border-primary-400 ring-1 ring-primary-200' : 'border-ground-200'}`}>
      <div className="flex items-start gap-2">
        <Link href={href} className="min-w-0 flex-1">
          <h3 className="break-words font-semibold text-ground-900">{course.course || course.course_id}</h3>
          <p className="mt-0.5 break-words text-sm text-ground-500">{subtitle}</p>
          <p className="mt-0.5 break-all font-mono text-xs text-ground-400">{course.course_id}</p>
        </Link>
        <button type="button" onClick={onRemove} aria-label={t('saved.remove')}
          className="-mr-2 -mt-2 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ground-400 transition-colors hover:text-critical-600">
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => onStatus('applied')} disabled={updating} aria-pressed={isApplied}
          className={`${pill} ${isApplied
            ? 'border border-primary-300 bg-primary-100 text-primary-700'
            : 'border border-ground-300 text-ground-600 hover:bg-ground-50'}`}>
          {isApplied && check}
          <span className="min-w-0">{t('outcomes.iApplied')}</span>
        </button>
        <button type="button" onClick={() => onStatus('got_offer')} disabled={updating} aria-pressed={hasOffer}
          className={`${pill} ${hasOffer
            ? 'border border-positive-300 bg-positive-100 text-positive-700'
            : 'border border-ground-300 text-ground-600 hover:bg-ground-50'}`}>
          {hasOffer && check}
          <span className="min-w-0">{t('outcomes.iGotOffer')}</span>
        </button>
        <label className="ml-auto inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm font-medium text-ground-600 hover:bg-ground-50">
          <input type="checkbox" checked={selected} onChange={onToggleSelect}
            className="h-5 w-5 rounded border-ground-300 text-primary-600 focus:ring-brand-shape" />
          {t('discovery.compareSelect')}
        </label>
      </div>
    </div>
  )
}
