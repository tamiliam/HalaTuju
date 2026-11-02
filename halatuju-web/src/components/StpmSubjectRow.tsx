'use client'

import type { ReactNode } from 'react'
import { useT } from '@/lib/i18n'

/**
 * One STPM subject on the onboarding grades step: the subject, its grade, whether it counts towards
 * the PNGK, and a remove button (Mobile M2, Stitch M2c2).
 *
 * ⚠ TWO LINES ON A PHONE, ONE FROM `sm`. In one row the "not counted" tag took up to 176 px, so on a
 * 390 px phone the subject picker beside it was left about 12 px — the subject's name could not be
 * read. Now line 1 is the subject (with the 44 px remove button at its end) and line 2 the grade and
 * the tag, which may wrap onto two lines of its own. From `sm` the order is the desktop one: subject,
 * grade, tag, remove. Shown in the sandbox (`stpm-grade-rows`) so mobile-check measures it.
 */
export default function StpmSubjectRow({ subject, grade, tag, onRemove, dashed = false }: {
  /** The subject: a picker, or the compulsory subject's fixed name. */
  subject: ReactNode
  /** The grade picker — absent until a subject is chosen. */
  grade?: ReactNode
  /** `StpmCountTag`, once there is a PNGK to count towards. */
  tag?: ReactNode
  /** Absent for the compulsory subject. */
  onRemove?: () => void
  /** The optional elective's slot is drawn dashed. */
  dashed?: boolean
}) {
  const { t } = useT()
  // Rule 15 (Mobile M4c): a row divided by a hairline on a phone (its list is `PHONE_ROWS`); the card from md.
  return (
    <div className={`flex flex-wrap items-center gap-2 py-2 md:rounded-xl md:bg-ground-0 md:p-3 md:transition-shadow md:hover:shadow-md ${
      dashed ? 'md:border md:border-dashed md:border-ground-300' : 'md:border md:border-ground-200 md:shadow-sm'}`}>
      <div className={`order-1 min-w-0 flex-1 sm:basis-0 ${onRemove ? 'basis-[calc(100%-3.25rem)]' : 'basis-full'}`}>
        {subject}
      </div>
      {(grade || tag) && (
        <div className="order-3 flex w-full min-w-0 items-center gap-2 sm:w-auto">
          {grade}
          {tag}
        </div>
      )}
      {onRemove && (
        <button type="button" onClick={onRemove}
          className="order-2 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ground-400 hover:bg-ground-50 hover:text-critical-600 sm:order-4"
          aria-label={t('common.remove')}>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )
}

/** Whether a graded subject counts towards the PNGK — the server's `counted` list. */
export function StpmCountTag({ kind, testId }: { kind: 'always' | 'counted' | 'notCounted'; testId?: string }) {
  const { t } = useT()
  const label = kind === 'always' ? 'onboarding.stpmCountsAlways'
    : kind === 'counted' ? 'onboarding.stpmCounts' : 'onboarding.stpmNotCounted'
  return (
    <span data-testid={testId}
      className={`min-w-0 flex-1 text-xs sm:flex-none ${kind === 'notCounted' ? 'text-ground-500 sm:max-w-[11rem]' : 'text-primary-600'}`}>
      {t(label)}
    </span>
  )
}
