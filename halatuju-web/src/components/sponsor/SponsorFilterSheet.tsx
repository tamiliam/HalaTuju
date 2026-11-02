'use client'

/**
 * The sponsor's Students filters on a phone (Mobile M5) — rule 5's "filters on a phone go in a Sheet",
 * the shape of `search/SearchFilterSheet.tsx`: one group of 44 px chips per facet, a tap applies at
 * once (tap the picked chip again to clear it), focus opens on the first chip, and the footer says how
 * many students the filters leave and closes. The desktop keeps its row of selects; both read the SAME
 * state and the SAME facet lists in `students/page.tsx`, so they can never disagree.
 *
 * Its own file rather than SearchFilterSheet: that one speaks the `discovery` slice's words, which no
 * sponsor route loads. Eager on the Students page: it is the only way to filter on a phone.
 */
import { useRef, type RefObject } from 'react'
import Sheet from '@/components/Sheet'
import { useT } from '@/lib/i18n'

export interface SponsorFacet {
  key: string
  title: string
  options: { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
}

export default function SponsorFilterSheet({ open, onClose, groups, count, onClear }: {
  open: boolean
  onClose: () => void
  groups: SponsorFacet[]
  count: number
  onClear: () => void
}) {
  const { t } = useT()
  const firstChip = useRef<HTMLButtonElement>(null)
  const canClear = groups.some((g) => g.value)
  return (
    <Sheet open={open} onClose={onClose} title={t('sponsorPortal.students.filters')}
      initialFocus={firstChip as RefObject<HTMLElement>} testId="sponsor-filter-sheet"
      footer={(
        <>
          <button type="button" onClick={onClear} disabled={!canClear}
            className="min-h-12 flex-1 rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
            {t('common.clear')}
          </button>
          <button type="button" onClick={onClose}
            className="min-h-12 flex-[1.4] rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
            {t('sponsorPortal.students.showResults', { count: String(count) })}
          </button>
        </>
      )}>
      <div className="space-y-6">
        {groups.map((g, gi) => (
          <section key={g.key} aria-labelledby={`sponsor-facet-${g.key}`}>
            <h3 id={`sponsor-facet-${g.key}`} className="mb-2 text-sm font-semibold text-ground-600">{g.title}</h3>
            <div className="flex flex-wrap gap-2">
              {g.options.map((o, i) => {
                const on = g.value === o.value
                return (
                  <button key={o.value} type="button" ref={gi === 0 && i === 0 ? firstChip : undefined}
                    aria-pressed={on} onClick={() => g.onChange(on ? '' : o.value)}
                    className={`inline-flex min-h-11 max-w-full items-center rounded-full border px-4 py-2 text-left text-sm font-medium break-words ${
                      on ? 'border-brand-shape bg-primary-50 text-primary-700' : 'border-ground-300 bg-ground-0 text-ground-700 hover:bg-ground-50'}`}>
                    {on && <span aria-hidden className="mr-1.5">✓</span>}
                    {o.label}
                  </button>
                )
              })}
            </div>
          </section>
        ))}
      </div>
    </Sheet>
  )
}
