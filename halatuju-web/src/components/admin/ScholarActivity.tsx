'use client'

import { PHONE_CARD_XL } from '@/lib/phoneConsole'
import { PHONE_PILL } from '@/lib/phonePill'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useT } from '@/lib/i18n'
import { useToast } from '@/components/ToastContext'
import { ActivityComposer, ActivityRow } from '@/components/admin/ScholarActivityParts'
import {
  addScholarActivity, getScholarActivity, type ActivityShow, type ScholarActivity as Entry,
} from '@/lib/admin-api'

const SHOWS: ActivityShow[] = ['all', 'notes', 'system']

/** Newest first, one row per id — a page fetched after a Save can overlap the pages already read. */
function merge(have: Entry[], more: Entry[]): Entry[] {
  const byId = new Map<number, Entry>()
  for (const r of [...have, ...more]) byId.set(r.id, r)
  return Array.from(byId.values()).sort((a, b) =>
    Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id)
}

/**
 * A scholar's activity log (student maintenance Sprint 2; reshaped in sprint P1, owner 2026-11-09).
 *
 * The way Podio reads (P1-b): OLDEST AT THE TOP, NEWEST AT THE BOTTOM, the "Add a note…" box below the
 * list, inside a fixed-height list that scrolls by itself and opens scrolled to the newest (P1-c). The
 * server still pages newest first; this shows each page reversed, and "Show older (n)" at the top
 * fetches the next page and keeps the reader where they were. Side panel (`compact`): 6 per load,
 * mixed. Activity tab: 20 per load, with the All · Notes · System filter, applied ON THE SERVER (P1-f).
 *
 * ⚠ "Staff only" is the site `Toggle`, never a checkbox (house rule). Nothing in this log reaches a
 * student today — the flag is recorded now so the day a student view of the log exists, the rows an
 * officer meant for colleagues are already marked.
 * ⚠ A system row is a translated sentence from its event code (`lib/scholarActivity.activityText`), never
 * the raw meta, so a payment's run reference reads as a sentence and nothing internal leaks as JSON.
 * ⚠ The photo links are signed for about an hour; they are never kept beyond this page.
 */
export default function ScholarActivity({ id, token, compact = false, readOnly = false }: {
  id: number
  token: string | null
  /** The Overview's side panel: the latest 6 per load and no filter. */
  compact?: boolean
  /** A CLOSED file is read-only (owner ruling 2026-10-29): no composer — the server refuses a
   *  write too (409 `file_closed`). */
  readOnly?: boolean
}) {
  const { t } = useT()
  const { showToast } = useToast()
  const size = compact ? 6 : 20
  const [show, setShow] = useState<ActivityShow>('all')
  const [rows, setRows] = useState<Entry[] | null>(null)
  const [count, setCount] = useState(0)
  const [counts, setCounts] = useState<Record<ActivityShow, number> | null>(null)
  const [page, setPage] = useState(1)
  const [failed, setFailed] = useState(false)
  const [older, setOlder] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  /** Where to leave the scroll after the next render: the bottom, or as far from it as before. */
  const pin = useRef<'bottom' | { fromBottom: number } | null>(null)
  const asked = useRef(0)

  useLayoutEffect(() => {
    const el = scroller.current
    const p = pin.current
    if (!el || !p) return
    el.scrollTop = p === 'bottom' ? el.scrollHeight : el.scrollHeight - p.fromBottom
    pin.current = null
  }, [rows])

  /** Page 1 of `which`: replaces the list, or (after a Save) merges into what is already read. */
  const latest = useCallback(async (which: ActivityShow, keep: Entry[] | null) => {
    if (!token) return
    const ask = ++asked.current
    try {
      const p = await getScholarActivity(id, { token, page_size: size, show: which })
      if (ask !== asked.current) return
      pin.current = 'bottom'
      setRows(keep ? merge(keep, p.results) : p.results)
      setCount(p.count); setCounts(p.counts ?? null); setFailed(false)
      if (!keep) setPage(1)
    } catch {
      if (ask === asked.current) setFailed(true)
    }
  }, [id, token, size])
  useEffect(() => { latest(show, null) }, [latest, show])

  async function showOlder() {
    if (!token || !rows || older) return
    setOlder(true)
    const el = scroller.current
    try {
      const p = await getScholarActivity(id, { token, page: page + 1, page_size: size, show })
      pin.current = el ? { fromBottom: el.scrollHeight - el.scrollTop } : null
      setRows((have) => merge(have ?? [], p.results))
      setCount(p.count); setPage(page + 1)
    } catch {
      showToast(t('admin.scholars.activity.loadFailed'), 'error')
    } finally { setOlder(false) }
  }

  async function save(entry: { body: string; internal: boolean }) {
    if (!token) return false
    try {
      await addScholarActivity(id, { kind: 'note', ...entry }, { token })
    } catch {
      showToast(t('admin.scholars.activity.saveFailed'), 'error')
      return false
    }
    showToast(t('admin.scholars.activity.saved'), 'success')
    await latest(show, rows ?? [])
    return true
  }

  const remaining = rows ? Math.max(0, count - rows.length) : 0
  return (
    <section aria-label={t('admin.scholars.activity.title')} className={PHONE_CARD_XL}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-ground-900">{t('admin.scholars.activity.title')}</h2>
        {!compact && (
          <div role="group" aria-label={t('admin.scholars.activity.filterLabel')} className="flex flex-wrap gap-1.5">
            {SHOWS.map((s) => (
              <button key={s} type="button" aria-pressed={show === s} onClick={() => setShow(s)}
                className={`rounded-full border px-3 py-1 text-xs font-medium max-md:min-h-11 ${PHONE_PILL} ${show === s
                  ? 'border-info-600 bg-info-50 text-info-700'
                  : 'border-ground-300 bg-ground-0 text-ground-700 hover:bg-ground-50'}`}>
                {t(`admin.scholars.activity.filter.${s}`, { n: String(counts?.[s] ?? 0) })}
              </button>
            ))}
          </div>
        )}
      </div>

      {failed && <p className="mt-2 text-sm text-critical-600">{t('admin.scholars.activity.loadFailed')}</p>}
      {rows !== null && rows.length === 0 && (
        <p className="mt-2 text-sm text-ground-400" data-testid="activity-empty">
          {t('admin.scholars.activity.empty')}
        </p>
      )}
      <div ref={scroller} data-testid="activity-scroller"
        className={`overflow-y-auto overscroll-contain ${compact ? 'max-h-[420px]' : 'max-h-[560px]'} max-md:max-h-[55dvh]`}>
        {remaining > 0 && (
          <button type="button" onClick={showOlder} disabled={older} data-testid="activity-older"
            className="w-full rounded-lg py-2 text-sm font-medium text-info-700 hover:bg-ground-50 disabled:opacity-50 max-md:min-h-11">
            {older ? t('admin.scholars.activity.loadingOlder')
              : t('admin.scholars.activity.showOlder', { n: String(remaining) })}
          </button>
        )}
        <ol className="divide-y divide-ground-100">
          {[...(rows ?? [])].reverse().map((a) => <ActivityRow key={a.id} a={a} />)}
        </ol>
      </div>

      {readOnly ? (
        <p className="mt-3 border-t border-ground-100 pt-3 text-sm text-ground-500" data-testid="activity-read-only">
          {t('admin.scholars.activity.readOnly')}
        </p>
      ) : <ActivityComposer onSave={save} />}
    </section>
  )
}
