'use client'

import { useRef, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useBottomBarInset } from '@/lib/bottomBarInset'

/**
 * SAVED-COURSE COMPARE (Mobile M3). Until M3 a phone could not compare at all — the tick boxes
 * and the compare bar were `hidden md:…`. The owner chose layout B (2026-11-01): on a phone TWO
 * columns, each row's label as a heading line above the two values, so a label never squeezes them;
 * with three courses picked, a "Compare with" chooser picks the second column. No "best" marks:
 * which merit or fee is better is the student's judgement, not ours. From `md` the table stays.
 *
 * Pure: the page fetches the details and hands them in, so the design sandbox can mount the real
 * view with fixtures and no network. Words from the `discovery` slice (loaded by `/saved`'s page).
 */

export interface CompareData {
  course_id: string
  name: string
  level: string
  field: string
  institution: string
  state: string
  type: string
  fees: string
  allowance: string
  merit: string
  requirements: string[]
  semesters: string
  courseType: 'spm' | 'stpm'
}

type RowKey = 'institution' | 'state' | 'type' | 'level' | 'field' | 'semesters' | 'fees' | 'allowance' | 'merit'
const ROWS: RowKey[] = ['institution', 'state', 'type', 'level', 'field', 'semesters', 'fees', 'allowance', 'merit']

const hrefOf = (c: CompareData) => (c.courseType === 'stpm' ? `/stpm/${c.course_id}` : `/course/${c.course_id}`)

/**
 * The bar that appears once a course is ticked. A phone: stuck to the screen's foot above the home
 * bar (and the toast rises above it). A desktop: the floating pill, from two picks as before.
 */
export function CompareBar({ count, onCancel, onCompare }: {
  count: number
  onCancel: () => void
  onCompare: () => void
}) {
  const { t } = useT()
  const bar = useRef<HTMLDivElement>(null)
  useBottomBarInset(bar, count > 0)
  if (count === 0) return null
  return (
    <>
      <div ref={bar} data-page-bar data-testid="compare-bar-phone"
        className="sticky bottom-0 z-10 -mx-4 mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-ground-200 bg-ground-0 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_12px_rgba(0,0,0,0.06)] sm:-mx-6 sm:px-6 md:hidden">
        {/* Its natural width, never squeezed: in Tamil "தேர்ந்தெடுக்கப்பட்டன" is one long word that
            cannot break, and a shrinking span let "Cancel" paint over it at 360. The row wraps instead. */}
        <span className="mr-auto text-sm font-medium text-ground-700">
          {t('discovery.selectedCount', { count: String(count) })}
        </span>
        {/* The two buttons travel together: when the row wraps they move to a line of their own, right-aligned. */}
        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={onCancel}
            className="min-h-11 rounded-lg px-3 text-sm font-medium text-ground-600 hover:bg-ground-50">
            {t('common.cancel')}
          </button>
          <button type="button" onClick={onCompare} disabled={count < 2}
            className="min-h-12 rounded-lg bg-brand-fill px-5 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {t('discovery.compare')}
          </button>
        </div>
      </div>
      {count >= 2 && (
        <div className="fixed bottom-6 left-1/2 z-50 hidden -translate-x-1/2 md:block">
          <div className="flex items-center gap-4 rounded-full bg-ground-900 px-6 py-3 text-white shadow-lg">
            <span className="text-sm">{t('discovery.selectedCount', { count: String(count) })}</span>
            <button type="button" onClick={onCompare}
              className="min-h-11 rounded-full bg-brand-fill px-5 text-sm font-medium text-brand-fill-ink transition-colors hover:bg-brand-fill-hover">
              {t('discovery.compare')}
            </button>
            <button type="button" onClick={onCancel} className="min-h-11 px-2 text-sm text-ground-400 hover:text-white">
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}
    </>
  )
}

export default function SavedCompareView({ data, loading, onBack }: {
  data: CompareData[]
  loading: boolean
  onBack: () => void
}) {
  const { t } = useT()
  // Phone: the first pick is always column one; column two is any of the others.
  const [second, setSecond] = useState(1)
  const a = data[0]
  const b = data[Math.min(second, data.length - 1)]
  const label = (key: RowKey | 'requirements' | 'course') => t(`discovery.row.${key}`)

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 md:mb-6">
        <h2 className="text-xl font-bold text-ground-900">{t('discovery.compareTitle')}</h2>
        <button type="button" onClick={onBack}
          className="-mx-2 inline-flex min-h-11 items-center gap-1 px-2 text-sm font-medium text-primary-600 hover:text-primary-800">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          {t('discovery.backToSaved')}
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-brand-shape border-t-transparent" />
          <p className="mt-3 text-ground-500">{t('discovery.loadingDetails')}</p>
        </div>
      ) : a && b ? (
        <>
          {/* ── Phone: layout B ── */}
          <div className="md:hidden" data-testid="compare-phone">
            {data.length > 2 && (
              <div className="mb-3">
                <p className="mb-1 text-sm font-medium text-ground-600">{t('discovery.compareWith')}</p>
                <div className="flex flex-wrap gap-2">
                  {data.slice(1).map((c, i) => {
                    const on = second === i + 1
                    return (
                      <button key={c.course_id} type="button" aria-pressed={on} onClick={() => setSecond(i + 1)}
                        className={`inline-flex min-h-11 max-w-full items-center rounded-full border px-4 py-2 text-left text-sm font-medium ${
                          on ? 'border-brand-shape bg-primary-50 text-primary-700' : 'border-ground-300 bg-ground-0 text-ground-700'}`}>
                        <span className="min-w-0 break-words">{c.name}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
            <div className="sticky top-[calc(4.25rem+env(safe-area-inset-top))] z-[5] grid grid-cols-2 gap-2 bg-ground-50 pb-2">
              {[a, b].map((c) => (
                <Link key={c.course_id} href={hrefOf(c)}
                  className="flex min-h-11 min-w-0 items-center rounded-lg border border-primary-100 bg-primary-50 p-2 text-sm font-semibold text-primary-700">
                  <span className="line-clamp-3 break-words">{c.name}</span>
                </Link>
              ))}
            </div>
            <dl className="space-y-2">
              {ROWS.map((key) => (
                <div key={key} className="rounded-lg border border-ground-200 bg-ground-0 p-3">
                  <dt className="mb-1 text-xs font-semibold uppercase tracking-wide text-ground-500">{label(key)}</dt>
                  <dd className="grid grid-cols-2 gap-2 text-sm text-ground-900">
                    <span className="min-w-0 break-words">{a[key]}</span>
                    <span className="min-w-0 break-words">{b[key]}</span>
                  </dd>
                </div>
              ))}
              <div className="rounded-lg border border-ground-200 bg-ground-0 p-3">
                <dt className="mb-1 text-xs font-semibold uppercase tracking-wide text-ground-500">{label('requirements')}</dt>
                <dd className="grid grid-cols-2 gap-2">
                  {[a, b].map((c) => (
                    <ul key={c.course_id} className="min-w-0 list-disc space-y-0.5 pl-4 text-xs text-ground-800">
                      {c.requirements.map((r, i) => <li key={i} className="break-words">{r}</li>)}
                    </ul>
                  ))}
                </dd>
              </div>
            </dl>
          </div>

          {/* ── Desktop: every pick side by side ── */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="w-32 border border-ground-200 bg-ground-50 p-3 text-left text-sm font-medium text-ground-500">
                    {label('course')}
                  </th>
                  {data.map((c) => (
                    <th key={c.course_id} className="min-w-[220px] border border-ground-200 bg-primary-50 p-3 text-left">
                      <Link href={hrefOf(c)} className="block text-sm font-semibold text-primary-700 hover:underline">
                        {c.name}
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((key) => (
                  <tr key={key}>
                    <td className="border border-ground-200 bg-ground-50 p-3 text-sm font-medium text-ground-500">{label(key)}</td>
                    {data.map((c) => (
                      <td key={c.course_id} className="border border-ground-200 p-3 text-sm text-ground-900">{c[key]}</td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <td className="border border-ground-200 bg-ground-50 p-3 text-sm font-medium text-ground-500">{label('requirements')}</td>
                  {data.map((c) => (
                    <td key={c.course_id} className="border border-ground-200 p-3 text-sm text-ground-900">
                      <ul className="list-inside list-disc space-y-0.5">
                        {c.requirements.map((r, i) => <li key={i} className="text-xs">{r}</li>)}
                      </ul>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
