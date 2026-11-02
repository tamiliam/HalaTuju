'use client'

import Link from 'next/link'
import { useRef } from 'react'
import { useT } from '@/lib/i18n'
import { useBottomBarInset } from '@/lib/bottomBarInset'
import { PHONE_SECTION_NO_GAP } from '@/lib/phoneSection'

/**
 * Shared building blocks for SPM and STPM course detail pages.
 */

export function LoadingSpinner() {
  return (
    <main className="min-h-screen bg-ground-50 flex items-center justify-center">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-brand-shape border-t-transparent mb-4" />
        <p className="text-ground-600">Loading course details...</p>
      </div>
    </main>
  )
}

export function CourseNotFound() {
  const { t } = useT()
  return (
    <main className="min-h-screen bg-ground-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-ground-900 mb-4">Course not found</h1>
        <p className="text-ground-600 mb-6">{t('courseDetail.notFound')}</p>
        <Link href="/dashboard" className="btn-primary">
          Back to Dashboard
        </Link>
      </div>
    </main>
  )
}

export function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-ground-500 text-sm">{label}</span>
      <span className="font-medium text-ground-900 text-sm">{value}</span>
    </div>
  )
}

interface CourseActionsProps {
  isSaved: boolean
  isHovering: boolean
  onSave: () => void
  onHoverStart: () => void
  onHoverEnd: () => void
}

export function CourseActions({ isSaved, isHovering, onSave, onHoverStart, onHoverEnd }: CourseActionsProps) {
  const { t } = useT()
  return (
    <section className={PHONE_SECTION_NO_GAP}>
      <h2 className="text-lg font-semibold text-ground-900 mb-4">
        {t('courseDetail.actions')}
      </h2>
      <div className="space-y-3">
        {/* ⚠ From `md` only: a phone saves from the sticky bar (`CourseSaveBar`, Mobile M3). */}
        <button
          onClick={onSave}
          // A MOUSE only (Mobile M1a): a phone tap fires a compatibility mouseenter, which flipped
          // "Saved" to "Remove from saved" the moment a student saved — and it stayed flipped.
          onPointerEnter={(e) => { if (e.pointerType === 'mouse') onHoverStart() }}
          onPointerLeave={(e) => { if (e.pointerType === 'mouse') onHoverEnd() }}
          className={`hidden md:block w-full min-h-11 px-4 py-2.5 rounded-lg font-medium text-sm transition-colors ${
            isSaved
              ? isHovering
                ? 'bg-critical-fill text-critical-fill-ink hover:bg-critical-fill-hover'
                : 'bg-positive-fill text-positive-fill-ink'
              : 'bg-brand-fill text-brand-fill-ink hover:bg-brand-fill-hover'
          }`}
        >
          {isSaved
            ? isHovering
              ? t('courseDetail.removeFromSaved')
              : t('courseDetail.saved')
            : t('courseDetail.saveCourse')}
        </button>
        <Link
          href="/dashboard"
          className="btn-secondary w-full text-center block"
        >
          {t('courseDetail.backToRecommendations')}
        </Link>
      </div>
    </section>
  )
}

/**
 * THE PHONE'S SAVE BUTTON (Mobile M3): a bar stuck to the bottom of the screen while the student
 * reads the course, below `md` only. Before, Save sat in the sidebar card, which a phone draws LAST
 * — under every institution: 6,800 px down on a polytechnic diploma with 18 colleges.
 *
 * `sticky`, not `fixed`: it rides at the screen's foot over the course and then comes to rest in
 * its place above the footer, so it never covers the footer or the page's last lines. It clears
 * the iPhone home bar, and tells the toast its height (`useBottomBarInset`) so a "saved" message
 * never sits on top of it. No hover state: a tap is never a hover (the M1a lesson).
 */
export function CourseSaveBar({ isSaved, onSave }: { isSaved: boolean; onSave: () => void }) {
  const { t } = useT()
  const bar = useRef<HTMLDivElement>(null)
  useBottomBarInset(bar)
  return (
    <div ref={bar} data-page-bar data-testid="course-save-bar"
      className="sticky bottom-0 z-10 border-t border-ground-200 bg-ground-0 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.06)] md:hidden">
      <button type="button" onClick={onSave} aria-pressed={isSaved}
        className={`flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-4 py-2 text-base font-semibold ${
          isSaved ? 'bg-positive-fill text-positive-fill-ink' : 'bg-brand-fill text-brand-fill-ink'}`}>
        <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill={isSaved ? 'currentColor' : 'none'}
          stroke="currentColor" strokeWidth={2} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
        </svg>
        {isSaved ? t('courseDetail.saved') : t('courseDetail.saveCourse')}
      </button>
    </div>
  )
}
