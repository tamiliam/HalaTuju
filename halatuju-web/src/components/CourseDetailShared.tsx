'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'

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
    <section className="bg-ground-0 rounded-xl border border-ground-200 p-6">
      <h2 className="text-lg font-semibold text-ground-900 mb-4">
        {t('courseDetail.actions')}
      </h2>
      <div className="space-y-3">
        <button
          onClick={onSave}
          onMouseEnter={onHoverStart}
          onMouseLeave={onHoverEnd}
          className={`w-full px-4 py-2.5 rounded-lg font-medium text-sm transition-colors ${
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
