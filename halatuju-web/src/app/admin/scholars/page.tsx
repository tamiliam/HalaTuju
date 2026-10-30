'use client'
// Scholars — every funded student from award acceptance to closure (student maintenance Sprint 2).
// Design of record: the owner-approved canvas, 2026-10-29 (list artboard).
//
// ⚠ WHO IS LISTED, AND WHO MAY SEE IT, ARE THE SERVER'S (`views_admin/scholars.py`): the maintenance
// predicate decides the population, and the Applications rule decides the reader — see_all reads the
// organisation, a reviewer only their assigned scholars, finance never. This page draws what it is
// handed and filters on the server, so a page of 25 is the right 25 of the whole list.
//
// ⚠ NO STANDING IS JUDGED HERE. The server's `standing` (S4a, `standing.py`: the latest ACCEPTED
// result against the organisation's thresholds) is drawn as it comes; "Underperforming" asks the
// server (`standing=below_minimum`). "Results overdue" (S4b) and "Wants a mentor" (S7) stay
// DISABLED (PanelTabs' rule: a tab not built yet is shown, never hidden) rather than faked.

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import PanelTabs, { type PanelTab } from '@/components/admin/PanelTabs'
import SortHeader from '@/components/admin/SortHeader'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { Pagination } from '@/components/Pagination'
import { ChooseFromScope } from '@/components/admin/ChooseProgramme'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { useProgrammeParam } from '@/lib/programmeScope'
import { useGiftGate } from '@/lib/useGiftGate'
import { formatDate } from '@/lib/formatDate'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, nextSort, type SortDir } from '@/lib/tableView'
import { getScholars, type ScholarList, type ScholarRow } from '@/lib/admin-api'
import { lazySource } from '@/components/source/LazySource'

import { STANDING_TONE, SUBSTATE_TONE } from '@/lib/scholars'

const SourceScholars = lazySource(() => import('@/components/source/SourceScholars').then((m) => m.default))

type Filter = 'all' | 'on_track' | 'probation' | 'on_hold' | 'ready_to_close' | 'closed'
  | 'underperforming' | 'overdue' | 'wantsMentor'
type SortKey = 'name' | 'cgpa' | 'due' | 'activity'

const FIRST_DIR: Record<SortKey, SortDir> = { name: 'asc', cgpa: 'desc', due: 'asc', activity: 'desc' }

// ⚠ A SOURCE USER GETS ITS OWN SCREEN (source sign-in, 2026-10-30), chosen BEFORE any staff hook
// runs: the staff body calls staff endpoints, which refuse the role. The source component calls
// `admin/source/` only (`components/source/noStaffCalls.test.tsx`).
export default function ScholarsPage() {
  const { role } = useAdminAuth()
  return role?.role === 'source_partner' ? <SourceScholars /> : <StaffScholarsPage />
}

function StaffScholarsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = canAccess('/admin/scholars', effectiveRole(role), role?.permissions)
  const programme = useProgrammeParam()
  const gate = useGiftGate(role)

  const [filter, setFilter] = useState<Filter>('all')
  const [typed, setTyped] = useState('')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'name', dir: 'asc' })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [data, setData] = useState<ScholarList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // The search box settles before it asks (a request per keystroke would race itself).
  useEffect(() => {
    const id = setTimeout(() => { setSearch(typed); setPage(1) }, 300)
    return () => clearTimeout(id)
  }, [typed])

  // ⚠ ONLY THE NEWEST READ MAY LAND (the TD-298 ticket): a slow reply for a filter you left must
  // never overwrite the one you are looking at.
  const latest = useRef(0)
  // The words for a failed read, held in a ref so a re-created `t` never re-runs the read.
  const failedText = useRef('')
  failedText.current = t('admin.scholars.loadFailed')
  useEffect(() => {
    const ticket = ++latest.current
    if (!token || !allowed || gate !== 'open') { setLoading(false); return }
    setLoading(true); setError('')
    const substate = ['on_track', 'probation', 'on_hold', 'ready_to_close'].includes(filter)
      ? filter as ScholarRow['maintenance_substate'] : ''
    getScholars({
      programme, closed: filter === 'closed', substate, search,
      standing: filter === 'underperforming' ? 'below_minimum' : filter === 'overdue' ? 'results_overdue' : '',
      sort: `${sort.dir === 'desc' ? '-' : ''}${sort.key}`, page, page_size: pageSize,
    }, { token })
      .then((d) => { if (ticket === latest.current) setData(d) })
      .catch(() => { if (ticket === latest.current) setError(failedText.current) })
      .finally(() => { if (ticket === latest.current) setLoading(false) })
  }, [token, allowed, gate, programme, filter, search, sort, page, pageSize])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (gate === 'wait') return <p className="text-ground-400" data-testid="gift-wait">{t('common.loading')}</p>
  if (gate === 'ask') {
    return (
      <div data-testid="scholars-choose">
        <h1 className="text-2xl font-semibold text-ground-900">{t('admin.scholars.title')}</h1>
        <ChooseFromScope />
      </div>
    )
  }

  const s = data?.summary
  const tabs: readonly PanelTab<Filter>[] = [
    { key: 'all', labelKey: 'admin.scholars.filter.all', count: s?.in_programme },
    { key: 'on_track', labelKey: 'admin.maintenance.substate.on_track' },
    { key: 'probation', labelKey: 'admin.maintenance.substate.probation', count: s?.probation },
    { key: 'on_hold', labelKey: 'admin.maintenance.substate.on_hold', count: s?.on_hold },
    { key: 'ready_to_close', labelKey: 'admin.maintenance.substate.ready_to_close', count: s?.ready_to_close },
    { key: 'underperforming', labelKey: 'admin.scholars.filter.underperforming', count: s?.below_minimum },
    { key: 'overdue', labelKey: 'admin.scholars.filter.overdue', count: s?.results_overdue },
    { key: 'wantsMentor', labelKey: 'admin.scholars.filter.wantsMentor', disabled: true },
    { key: 'closed', labelKey: 'admin.scholars.filter.closed', count: s?.closed },
  ]
  const tiles: { key: string; value: number | undefined; tone: string }[] = [
    { key: 'inProgramme', value: s?.in_programme, tone: 'text-ground-900' },
    { key: 'onHold', value: s?.on_hold, tone: s?.on_hold ? 'text-critical-700' : 'text-ground-900' },
    { key: 'probation', value: s?.probation, tone: s?.probation ? 'text-caution-700' : 'text-ground-900' },
    { key: 'readyToClose', value: s?.ready_to_close, tone: 'text-ground-900' },
    { key: 'belowMinimum', value: s?.below_minimum, tone: s?.below_minimum ? 'text-caution-700' : 'text-ground-900' },
    { key: 'resultsOverdue', value: s?.results_overdue, tone: s?.results_overdue ? 'text-critical-700' : 'text-ground-900' },
  ]
  const rows = data?.results ?? []
  const total = data?.count ?? 0
  const onSort = (col: SortKey) => { setSort(nextSort(sort, col, FIRST_DIR[col])); setPage(1) }

  return (
    <div>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t('admin.scholars.title')}</h1>
          <p className="mt-1 text-sm text-ground-600">{t('admin.scholars.subtitle')}</p>
        </div>
        <label className="flex flex-col gap-1 text-xs text-ground-600">
          {t('admin.scholars.search')}
          <input type="search" value={typed} onChange={(e) => setTyped(e.target.value)}
            placeholder={t('admin.scholars.searchPlaceholder')}
            className="h-10 w-72 max-w-full rounded-lg border border-ground-300 px-3 text-sm focus:border-info-500 focus:ring-2 focus:ring-info-500" />
        </label>
      </header>

      <section aria-label={t('admin.scholars.summary')} className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-6">
        {tiles.map((tile) => (
          <div key={tile.key} className="rounded-xl border border-ground-200 bg-ground-0 p-4">
            <div className="text-sm text-ground-600">{t(`admin.scholars.tile.${tile.key}`)}</div>
            <div className={`mt-1 text-2xl font-semibold tabular-nums ${tile.tone}`}>
              {tile.value ?? '—'}
            </div>
          </div>
        ))}
      </section>

      <PanelTabs tabs={tabs} active={filter} ariaLabelKey="admin.scholars.filtersLabel"
        onSelect={(k) => { setFilter(k); setPage(1) }} />

      {error && <p className="mb-3 text-sm text-critical-600">{error}</p>}

      {/* PHONE: one card per scholar — the name and the status lead, the course under them. The
          whole card is the link: every column was only ever a way into the file. */}
      <div className="space-y-2.5 md:hidden" data-testid="scholar-cards">
        {rows.map((r) => (
          <Link key={r.id} href={`/admin/scholars/${r.id}`}
            className="block rounded-xl border border-ground-200 bg-ground-0 p-3 hover:border-info-300">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-semibold text-primary-600">{r.name || '—'}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                r.status === 'closed' ? 'bg-ground-100 text-ground-600' : SUBSTATE_TONE[r.maintenance_substate]}`}>
                {r.status === 'closed' ? t('admin.scholars.closed')
                  : t(`admin.maintenance.substate.${r.maintenance_substate}`)}
              </span>
            </div>
            <p className="mt-1 text-xs text-ground-600">
              {[r.course, r.institution].filter(Boolean).join(' · ') || '—'}
            </p>
            <p className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] text-ground-600">
              <span>#{r.id}</span>
              <span>{t('admin.scholars.col.cgpa')} {r.latest_result?.cgpa ?? '—'}</span>
              <span>{t(`admin.scholars.standing.${r.standing}`)}</span>
              {r.next_due && <span>{t('admin.scholars.col.nextDue')} {formatDate(r.next_due)}</span>}
            </p>
          </Link>
        ))}
      </div>

      <TableFrame className="hidden md:block" minWidth={1080} label={t('admin.scholars.title')}>
        <table className="w-full text-sm">
          <thead className="border-b bg-ground-50">
            <tr>
              <SortHeader col="name" label={t('admin.scholars.col.name')} sort={sort} onSort={onSort} />
              <th className={TH}>{t('admin.scholars.col.course')}</th>
              <th className={TH}>{t('admin.scholars.col.status')}</th>
              <SortHeader col="cgpa" label={t('admin.scholars.col.cgpa')} sort={sort} onSort={onSort} align="right" />
              <th className={TH}>{t('admin.scholars.col.standing')}</th>
              <SortHeader col="due" label={t('admin.scholars.col.nextDue')} sort={sort} onSort={onSort} />
              <th className={TH}>{t('admin.scholars.col.mentor')}</th>
              <SortHeader col="activity" label={t('admin.scholars.col.lastActivity')} sort={sort} onSort={onSort} />
            </tr>
          </thead>
          <tbody className="divide-y divide-ground-100">
            {rows.map((r) => (
              <tr key={r.id} className="hover:bg-primary-50/40">
                <td className="px-4 py-3">
                  <Link href={`/admin/scholars/${r.id}`} className="font-medium text-primary-600 hover:underline">
                    {r.name || '—'}
                  </Link>
                  <div className="text-xs text-ground-500">#{r.id}</div>
                </td>
                <td className="px-4 py-3 text-ground-700">
                  {r.course || '—'}
                  {r.institution && <div className="text-xs text-ground-500">{r.institution}</div>}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    r.status === 'closed' ? 'bg-ground-100 text-ground-600' : SUBSTATE_TONE[r.maintenance_substate]}`}>
                    {r.status === 'closed' ? t('admin.scholars.closed')
                      : t(`admin.maintenance.substate.${r.maintenance_substate}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ground-900">
                  {r.latest_result?.cgpa ?? '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STANDING_TONE[r.standing]}`}>
                    {t(`admin.scholars.standing.${r.standing}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-ground-600" data-testid="next-due">
                  {r.next_due ? formatDate(r.next_due) : '—'}
                </td>
                <td className="px-4 py-3 text-ground-500">—</td>
                <td className="px-4 py-3 text-ground-600">
                  {r.last_activity_at ? formatDate(r.last_activity_at) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-ground-500" data-testid="scholars-empty">
            {search ? t('admin.scholars.emptySearch') : t('admin.scholars.empty')}
          </p>
        )}
        {loading && rows.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-ground-400">{t('common.loading')}</p>
        )}
      </TableFrame>

      <Pagination page={data?.page ?? page} totalPages={Math.max(1, Math.ceil(total / pageSize))}
        total={total} pageSize={pageSize} onPageChange={setPage}
        pageSizeOptions={PAGE_SIZE_OPTIONS}
        onPageSizeChange={(n) => { setPageSize(n); setPage(1) }} />
    </div>
  )
}
