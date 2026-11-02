'use client'

/**
 * The case list's phone tools (Mobile M6a, owner-approved mock-up): a 44 px "Filters" button with the count
 * of active filters, which opens the shared Sheet, and a Sort select beside it — the table's sortable headers
 * are desktop-only.
 *
 * ⚠ IT OWNS NO FILTER AND NO SORT. The page hands it its ONE `filterControls` (the same nodes the desktop
 * row draws) and its sort state, so a filter set here shows in the desktop row and the other way round, and
 * Sort asks the server for exactly what a header click would. Lifted out of the page to keep it under the
 * 600-line standard.
 */
import { useState, type ReactNode } from 'react'

import Sheet from '@/components/Sheet'
import { useT } from '@/lib/i18n'

export type CaseSortKey = 'name' | 'merit' | 'source' | 'status' | 'submitted' | 'assigned'

/** The table's sortable columns, in the order a phone offers them; the words are the columns' own headings. */
const SORT_KEYS: CaseSortKey[] = ['name', 'merit', 'status', 'submitted', 'source', 'assigned']
const SORT_LABEL: Record<CaseSortKey, string> = {
  name: 'admin.scholarship.name', merit: 'admin.scholarship.merit', status: 'admin.scholarship.status',
  submitted: 'admin.scholarship.submitted', source: 'admin.scholarship.source', assigned: 'admin.scholarship.assigned',
}

export default function CaseListPhoneTools({ filters, activeFilters, sort, sortDir, onSort, canAssign, count }: {
  /** The page's ONE set of filter controls — also drawn in its desktop row. */
  filters: ReactNode
  activeFilters: number
  sort: '' | CaseSortKey
  sortDir: 'asc' | 'desc'
  /** '' is the server's default order (newest first). */
  onSort: (key: '' | CaseSortKey, dir: 'asc' | 'desc') => void
  /** "Assigned" is only a column for those who assign. */
  canAssign: boolean
  /** The list's count, for the Sheet's footer; null while loading. */
  count: number | null
}) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="flex w-full gap-2 md:hidden" data-testid="list-phone-tools">
        <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog"
          className="inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border border-ground-300 bg-ground-0 px-3 text-sm font-medium text-ground-700">
          {t('admin.scholarship.filters')}
          {activeFilters > 0 && <span className="rounded-full bg-brand-fill px-1.5 text-xs font-semibold text-brand-fill-ink">{activeFilters}</span>}
        </button>
        <select value={sort ? `${sort}:${sortDir}` : ''} aria-label={t('admin.scholarship.sortLabel')}
          onChange={(e) => {
            const [key, dir] = e.target.value.split(':') as ['' | CaseSortKey, 'asc' | 'desc' | undefined]
            onSort(key, dir ?? 'asc')
          }}
          className="min-h-11 min-w-0 flex-1 rounded-lg border border-ground-300 bg-ground-0 px-3 text-sm text-ground-700">
          <option value="">{t('admin.scholarship.sortNewest')}</option>
          {SORT_KEYS.filter((k) => k !== 'assigned' || canAssign).flatMap((k) => (['asc', 'desc'] as const).map((d) => (
            <option key={`${k}:${d}`} value={`${k}:${d}`}>{t(SORT_LABEL[k])} {d === 'asc' ? '↑' : '↓'}</option>
          )))}
        </select>
      </div>
      <Sheet open={open} onClose={() => setOpen(false)} title={t('admin.scholarship.filters')}
        footer={<button type="button" onClick={() => setOpen(false)} className="btn-primary w-full min-h-11">
          {count != null ? t('admin.scholarship.countSubtitle', { count: String(count) }) : t('common.continue')}
        </button>}>
        <div className="flex flex-col gap-3 [&_select]:min-h-11 [&_select]:w-full [&_select]:max-w-none [&>button]:min-h-11" data-testid="list-filter-sheet">
          {filters}
        </div>
      </Sheet>
    </>
  )
}
