'use client'

/**
 * The Applications list's address-bar filters (`?status=&assigned=&ready=1&band=`), pulled out of the page
 * (owner 2026-11-05: the Overview's cards open the list already filtered). `ready` / `band` have no control of
 * their own, so they show as a removable chip. Read ONCE on mount, then the controls own the state and the
 * address bar follows (replace, no history entry; defaults left out).
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'

export type UrlBand = '' | 'overdue' | 'due_soon' | 'open'

const BAND_LABEL: Record<Exclude<UrlBand, ''>, string> = {
  overdue: 'admin.scholarship.chip.overdue',
  due_soon: 'admin.scholarship.chip.dueSoon',
  open: 'admin.scholarship.chip.open',
}

export function useApplicationUrlFilters(
  statusF: string, setStatusF: (v: string) => void,
  assignedF: string, setAssignedF: (v: string) => void,
) {
  const [readyF, setReadyF] = useState(false)
  const [bandF, setBandF] = useState<UrlBand>('')
  const [urlFiltersRead, setUrlFiltersRead] = useState(false)

  // Same effect flush as the gift read, so the first list request already carries them.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search)
    const st = p.get('status')
    if (st && (APPLICATION_STATUSES as readonly string[]).includes(st)) setStatusF(st)
    const as = p.get('assigned')
    if (as && (as === 'me' || as === 'none' || /^\d+$/.test(as))) setAssignedF(as)
    if (p.get('ready') === '1') setReadyF(true)
    const b = p.get('band')
    if (b === 'overdue' || b === 'due_soon' || b === 'open') setBandF(b)
    setUrlFiltersRead(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read once on mount; the setters are state setters from the page
  }, [])

  useEffect(() => {
    if (!urlFiltersRead) return
    const p = new URLSearchParams(window.location.search)
    const want: Record<string, string> = { status: statusF, assigned: assignedF, ready: readyF ? '1' : '', band: bandF }
    let changed = false
    for (const [k, v] of Object.entries(want)) {
      if ((p.get(k) ?? '') !== v) { changed = true; if (v) p.set(k, v); else p.delete(k) }
    }
    if (!changed) return
    const qs = p.toString()
    window.history.replaceState(window.history.state, '', window.location.pathname + (qs ? `?${qs}` : ''))
  }, [urlFiltersRead, statusF, assignedF, readyF, bandF])

  return { readyF, setReadyF, bandF, setBandF, urlFiltersRead }
}

/** A removable label for a filter that has no control of its own (ready / band). */
function FilterChip({ label, remove, onRemove, testId }:
  { label: string; remove: string; onRemove: () => void; testId: string }) {
  return (
    <span data-testid={testId} className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-3 py-1 text-sm text-primary-800">
      {label}
      <button type="button" aria-label={remove} onClick={onRemove}
        className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-primary-100">×</button>
    </span>
  )
}

export function ApplicationUrlChips({ readyF, bandF, onClearReady, onClearBand }:
  { readyF: boolean; bandF: UrlBand; onClearReady: () => void; onClearBand: () => void }) {
  const { t } = useT()
  if (!readyF && !bandF) return null
  const remove = t('admin.scholarship.chip.remove')
  return (
    <div className="mb-3 flex flex-wrap gap-2" data-testid="url-filter-chips">
      {readyF && <FilterChip label={t('admin.scholarship.chip.ready')} remove={remove} onRemove={onClearReady} testId="chip-ready" />}
      {bandF && <FilterChip label={t(BAND_LABEL[bandF])} remove={remove} onRemove={onClearBand} testId="chip-band" />}
    </div>
  )
}
