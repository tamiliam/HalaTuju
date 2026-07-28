'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { seenBand } from '@/lib/sponsorDetail'
import { listSponsors, reviewSponsor, type AdminSponsor } from '@/lib/admin-api'
import { effectiveRole } from '@/lib/navigation'
import {
  DEFAULT_SORT, SPONSOR_SORT_LABEL, firstDirFor, sortSponsors,
  type SponsorSortKey,
} from '@/lib/sponsorTable'
import { PAGE_SIZE_OPTIONS, nextSort, sortIndicator } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import { Pagination } from '@/components/Pagination'
import SponsorEmailsCard from '@/components/sponsors/SponsorEmailsCard'
import SponsorTermsCard from '@/components/sponsors/SponsorTermsCard'

// The ORGANISATION column was dropped on 2026-07-27: empty on all nine prod rows, and it cost
// a quarter of the table's width. Its space pays for GIVEN + LAST SEEN — what an admin
// actually scans a funder list for. `given` is org-fenced server-side (a tenant sees its own
// share); `last_seen_at` had no home at all before this sprint.
const seenTone: Record<string, string> = {
  never: 'text-amber-700 font-semibold',
  dormant: 'text-amber-700',
  recent: 'text-gray-500',
  today: 'text-gray-500',
}

const statusBadge = (s: string) =>
  s === 'approved' ? 'bg-green-100 text-green-700'
    : s === 'pending' ? 'bg-amber-100 text-amber-700'
      : s === 'suspended' ? 'bg-orange-100 text-orange-700'
        : 'bg-red-100 text-red-600'

const STATUS_OPTIONS = ['pending', 'approved', 'rejected', 'suspended']

// TWO PANELS, one badge each — the same idiom as the Sources page, so the console has one way of
// doing this. Sponsors is the default: the list is what the page is for, and Emails is a
// deliberate second click. The badges were held back from S1 on purpose (a badge that opens
// nothing is the failure the partner-comms card exists to avoid); the Emails panel IS this sprint.
const PANELS = ['sponsors', 'emails', 'terms'] as const
type Panel = (typeof PANELS)[number]

const panelLabel: Record<Panel, string> = {
  sponsors: 'admin.sponsors.tabSponsors',
  emails: 'admin.sponsors.tabEmails',
  terms: 'admin.sponsors.tabTerms',
}

// Editing what every donor is told is an editorial power, not a reading one — so the badge is
// shown to the roles the endpoint admits (super / org_admin / admin) and not to finance, which
// may read the sponsor list. The endpoint is the authority; this only avoids offering a 403.
const CAN_EDIT_EMAILS = ['super', 'org_admin', 'admin']

// Which review actions to offer for a sponsor in a given status.
const actionsFor = (status: string): Array<'approve' | 'reject' | 'suspend'> =>
  status === 'pending' ? ['approve', 'reject']
    : status === 'approved' ? ['suspend']
      : ['approve'] // rejected / suspended → reconsider

/** A sortable header. Every column except Actions uses this, so none can drift. */
function SortHeader({ col, sort, onSort, align, t }: {
  col: SponsorSortKey
  sort: { key: SponsorSortKey; dir: 'asc' | 'desc' }
  onSort: (col: SponsorSortKey) => void
  align?: 'right'
  t: (k: string) => string
}) {
  const active = sort.key === col
  return (
    <th className={`px-4 py-3 ${align === 'right' ? 'text-right' : 'text-left'}`}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onSort(col)}
        className={`inline-flex items-center gap-1 font-semibold text-xs uppercase tracking-wider hover:text-blue-600 ${
          active ? 'text-blue-600' : 'text-gray-600'}`}>
        {t(SPONSOR_SORT_LABEL[col])}
        <span aria-hidden className="text-[9px] leading-none">
          {sortIndicator(active, sort.dir)}
        </span>
      </button>
    </th>
  )
}

const actionStyle: Record<string, string> = {
  approve: 'bg-green-600 hover:bg-green-700',
  reject: 'bg-red-600 hover:bg-red-700',
  suspend: 'bg-orange-600 hover:bg-orange-700',
}

export default function AdminSponsorsList() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const [panel, setPanel] = useState<Panel>('sponsors')
  const mayEditEmails = CAN_EDIT_EMAILS.includes(effectiveRole(role))
  const [sponsors, setSponsors] = useState<AdminSponsor[]>([])
  const [statusF, setStatusF] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const { sort, setSort } = useSort<SponsorSortKey>(DEFAULT_SORT)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    listSponsors(statusF || undefined, { token })
      .then((d) => setSponsors(d.sponsors))
      .catch(() => setError(t('admin.sponsors.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, statusF])

  useEffect(() => { load() }, [load])

  // Sort the whole list, then page the sorted result — the other order would sort one page at a
  // time and shuffle rows between pages.
  const sorted = sortSponsors(sponsors, sort.key, sort.dir)
  const paged = usePagedRows(sorted)
  const onSort = (col: SponsorSortKey) =>
    setSort(nextSort(sort, col, firstDirFor(col)))

  const handleReview = async (id: number, action: 'approve' | 'reject' | 'suspend') => {
    if (!token) return
    setBusyId(id)
    setError('')
    try {
      const updated = await reviewSponsor(id, action, { token })
      setSponsors((prev) => prev.map((s) => (s.id === id ? updated : s)))
    } catch {
      setError(t('admin.sponsors.actionFailed'))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.sponsors.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-4">{t('admin.sponsors.desc')}</p>

      {mayEditEmails && (
        <div role="tablist" aria-label={t('admin.sponsors.tabsAria')} className="flex items-center gap-2 mb-6">
          {PANELS.map((key) => {
            const on = panel === key
            return (
              <button key={key} type="button" role="tab" aria-selected={on}
                onClick={() => setPanel(key)}
                className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                  on ? 'border-blue-600 bg-blue-600 text-white'
                     : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}`}>
                {t(panelLabel[key])}
              </button>
            )
          })}
        </div>
      )}

      {/* Mounted only while its badge is selected, so each reveal re-reads the templates and an
          emails hiccup can never take the vetting list down with it. */}
      {panel === 'emails' && mayEditEmails && <SponsorEmailsCard token={token} t={t} />}

      {/* Terms — authoring only. A sponsor does not meet this document until T3. */}
      {panel === 'terms' && mayEditEmails && (
        <SponsorTermsCard token={token} isSuper={Boolean(role?.is_super_admin)} t={t} />
      )}

      {panel === 'sponsors' && (<>
      <div className="flex flex-wrap gap-3 mb-4">
        <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.sponsors.allStatuses')}</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {error && <div className="text-red-600 mb-3">{error}</div>}
      {loading ? (
        <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
      ) : sponsors.length === 0 ? (
        <div className="text-center text-gray-500 mt-8">{t('admin.sponsors.empty')}</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50/80 border-b">
              <tr>
                <SortHeader col="name" sort={sort} onSort={onSort} t={t} />
                <SortHeader col="status" sort={sort} onSort={onSort} t={t} />
                <SortHeader col="given" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="students" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="lastSeen" sort={sort} onSort={onSort} t={t} />
                <SortHeader col="registered" sort={sort} onSort={onSort} t={t} />
                {/* Actions is the one unsortable column — there is nothing to order it by. */}
                <th className="text-right px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.sponsors.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {paged.rows.map((s) => (
                <tr key={s.id} className="hover:bg-blue-50/40 transition-colors align-top">
                  <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                    {/* The name opens the whole record — everything the flat table could not show. */}
                    <Link href={`/admin/sponsors/${s.id}`} className="font-medium text-blue-600 hover:text-blue-800">
                      {s.name || '—'}
                    </Link>
                    <div className="text-xs text-gray-500 mt-0.5">{s.email || '—'}</div>
                    {s.note && <div className="text-xs text-gray-500 mt-0.5 max-w-xs whitespace-pre-wrap">{s.note}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadge(s.status)}`}>{s.status}</span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                    {Number(s.given) > 0 ? Number(s.given).toLocaleString('en-MY', { minimumFractionDigits: 2 }) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                    {s.students > 0 ? s.students : '—'}
                  </td>
                  <td
                    className={`px-4 py-3 text-sm ${seenTone[seenBand(s.last_seen_at)]}`}
                    title={s.last_seen_at ? undefined : t('admin.sponsors.seen.neverHint')}
                  >
                    {s.last_seen_at
                      ? t(`admin.sponsors.seen.${seenBand(s.last_seen_at)}`, { date: formatDate(s.last_seen_at) })
                      : t('admin.sponsors.seen.never')}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(s.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      {actionsFor(s.status).map((a) => (
                        <button
                          key={a}
                          onClick={() => handleReview(s.id, a)}
                          disabled={busyId === s.id}
                          className={`text-white text-xs font-semibold px-3 py-1.5 rounded-lg disabled:opacity-50 ${actionStyle[a]}`}
                        >
                          {t(`admin.sponsors.action.${a}`)}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {paged.visible && (
            <div className="px-4 sm:px-5 pb-4">
              <Pagination
                page={paged.page} totalPages={paged.totalPages} pageSize={paged.pageSize}
                onPageChange={paged.setPage}
                pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={paged.setPageSize}
              />
            </div>
          )}
        </div>
      )}
      </>)}
    </div>
  )
}
