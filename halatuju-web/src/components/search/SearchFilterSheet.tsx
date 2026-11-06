'use client'

import { useRef, useState, type RefObject } from 'react'
import clsx from 'clsx'
import Sheet from '@/components/Sheet'
import { useT } from '@/lib/i18n'
import { PHONE_PILL_LG } from '@/lib/phonePill'

/**
 * THE COURSE SEARCH FILTERS ON A PHONE (Mobile M3) — the shared `Sheet` holding one group of chips
 * per facet, so the search page's first screen is the search box and the results, not five
 * dropdowns. From `md` the page keeps its row of `FilterPill`s; this sheet is never shown there.
 *
 * Behaviour, as the page's filters always behaved:
 *   - ONE value per facet. Tapping a chip picks it; tapping the picked chip clears that facet.
 *   - A tap APPLIES at once (the page searches again behind the sheet); the footer button only
 *     closes the sheet, and says how many courses the student will see.
 *   - "Clear" clears every facet. The search words and the "eligible only" switch live on the
 *     page, not here (a signed-out tap on that switch opens the sign-in sheet, and a sheet over a
 *     sheet is the wrong shape).
 *   - Focus opens on the FIRST CHIP (`initialFocus`) — never a text field, so no keyboard rises.
 *   - Long facets (states, fields) show their first few chips and a "Show all (N)" button; the
 *     picked chip is always among those shown.
 *
 * Mounted in the page entry (no `import()`): it is the only way to filter on a phone, and a lazy
 * chunk that failed would leave none (docs/lessons.md, Mobile M2). Its words come from the
 * `discovery` slice, which every route that mounts it loads from its page.
 */

export interface FacetOption {
  value: string
  label: string
}

export interface FacetGroup {
  key: string
  title: string
  options: FacetOption[]
  value: string
  onChange: (value: string) => void
  /** Show this many chips until "Show all" is pressed (the picked chip is always shown). */
  collapseAfter?: number
}

interface Props {
  open: boolean
  onClose: () => void
  groups: FacetGroup[]
  /** How many courses the current filters show; null while a search is in the air. */
  resultCount: number | null
  onClear: () => void
  canClear: boolean
}

export default function SearchFilterSheet({ open, onClose, groups, resultCount, onClear, canClear }: Props) {
  const { t } = useT()
  const firstChip = useRef<HTMLButtonElement>(null)
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={t('discovery.filters')}
      initialFocus={firstChip as RefObject<HTMLElement | null>}
      testId="search-filter-sheet"
      footer={(
        <>
          <button type="button" onClick={onClear} disabled={!canClear}
            className="min-h-12 flex-1 rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
            {t('search.clearFilters')}
          </button>
          <button type="button" onClick={onClose}
            className="min-h-12 flex-[1.4] rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
            {resultCount === null ? t('common.loading') : t(resultCount === 1 ? 'discovery.showCourse' : 'discovery.showCourses', { count: String(resultCount) })}
          </button>
        </>
      )}
    >
      <div className="space-y-6">
        {groups.map((group, i) => (
          <FacetChips key={group.key} group={group} firstRef={i === 0 ? firstChip : undefined} />
        ))}
      </div>
    </Sheet>
  )
}

function FacetChips({ group, firstRef }: { group: FacetGroup; firstRef?: RefObject<HTMLButtonElement | null> }) {
  const { t } = useT()
  const [expanded, setExpanded] = useState(false)
  const limit = group.collapseAfter
  const collapsed = !!limit && !expanded && group.options.length > limit
  let shown = collapsed ? group.options.slice(0, limit) : group.options
  // The picked chip is never hidden behind "Show all".
  if (collapsed && group.value && !shown.some((o) => o.value === group.value)) {
    const picked = group.options.find((o) => o.value === group.value)
    if (picked) shown = [...shown, picked]
  }
  const headingId = `facet-${group.key}`
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="mb-2 text-sm font-semibold text-ground-600">{group.title}</h3>
      <div className="flex flex-wrap gap-2">
        {shown.map((o, i) => {
          const on = group.value === o.value
          return (
            <button key={o.value} type="button" ref={i === 0 ? firstRef : undefined}
              aria-pressed={on}
              onClick={() => group.onChange(on ? '' : o.value)}
              className={clsx(
                'inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-full border px-4 py-2 text-left text-sm font-medium break-words',
                PHONE_PILL_LG,
                on
                  ? 'border-brand-shape bg-primary-50 text-primary-700'
                  : 'border-ground-300 bg-ground-0 text-ground-700 hover:bg-ground-50',
              )}>
              {on && (
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5} aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              )}
              <span className="min-w-0">{o.label}</span>
            </button>
          )
        })}
        {collapsed && (
          <button type="button" onClick={() => setExpanded(true)}
            className="inline-flex min-h-11 items-center rounded-full px-3 text-sm font-medium text-primary-600 hover:bg-primary-50">
            {t('discovery.showAll', { count: String(group.options.length) })}
          </button>
        )}
      </div>
    </section>
  )
}
