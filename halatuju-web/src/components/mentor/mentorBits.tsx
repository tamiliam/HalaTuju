'use client'

import { STANDING_TONE } from '@/lib/scholars'
import type { MyStudentCard, MyStudentResult } from '@/lib/admin-api'

type T = (k: string, p?: Record<string, string>) => string

/** The latest result as one chip: "CGPA 3.21 · Performing", or the standing alone ("No result yet"). */
export function ResultChip({ t, result, standing }: {
  t: T; result: MyStudentResult | null; standing: MyStudentCard['standing']
}) {
  const words = t(`admin.scholars.standing.${standing}`)
  const text = result ? `${t('admin.myStudents.cgpa', { cgpa: result.cgpa })} · ${words}` : words
  return (
    <span className={`self-start rounded-full px-2.5 py-0.5 text-xs font-medium ${STANDING_TONE[standing] ?? STANDING_TONE.no_result_yet}`}
      data-testid="my-student-result">
      {text}
    </span>
  )
}

/** What the student asked for help with when applying, as the chip's words ('' when nothing). */
export function helpWords(t: T, h: MyStudentCard['asked_for_help']): string {
  const what = [h.university && t('admin.scholars.mentoring.help.university'),
    h.scholarship && t('admin.scholars.mentoring.help.scholarship')].filter(Boolean).join(t('admin.scholars.mentoring.help.and'))
  if (what) return t('admin.scholars.mentoring.help.chip', { what })
  return h.flagged ? t('admin.scholars.mentoring.help.flaggedChip') : ''
}

/** A phone number a `tel:` link can dial (digits and a leading +). */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, '')}`
}

export const PRIMARY = 'inline-flex h-11 items-center justify-center rounded-lg bg-brand-fill px-4 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50'
export const SECONDARY = 'inline-flex h-11 items-center justify-center rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm text-ground-800 hover:bg-ground-50'
