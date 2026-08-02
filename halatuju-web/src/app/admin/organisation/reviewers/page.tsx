'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { listReviewers, type AdminReviewer } from '@/lib/admin-api'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { isFree, orderedLanguages, turnaroundBand } from '@/lib/reviewerDetail'
import {
  DEFAULT_SORT, REVIEWER_SORT_LABEL, firstDirFor, sortReviewers,
  type ReviewerSortKey,
} from '@/lib/reviewerTable'
import { PAGE_SIZE_OPTIONS, nextSort, sortIndicator } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import { Pagination } from '@/components/Pagination'
import ReviewerEmailsCard from '@/components/reviewers/ReviewerEmailsCard'

// The reviewers directory (request #10). Staff invites and revokes; this is where you LOOK at
// somebody before handing them the next case. Sorted by open caseload on arrival, because that is
// the question the page is opened to answer.
//
// Two things are deliberately absent and must stay absent unless the owner says otherwise:
// a corrections count (it reads as a competence score — the reopens live on the detail page WITH
// their reasons) and a programmes column (with one programme it could only ever say one thing).

const roleBadge = (r: string) =>
  r === 'super' ? 'bg-purple-100 text-purple-700'
    : r === 'qc' ? 'bg-blue-100 text-blue-700'
      : 'bg-gray-100 text-gray-600'

/** A sortable header. Every column except Languages uses this, so none can drift. */
function SortHeader({ col, sort, onSort, align, t }: {
  col: ReviewerSortKey
  sort: { key: ReviewerSortKey; dir: 'asc' | 'desc' }
  onSort: (col: ReviewerSortKey) => void
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
        {t(REVIEWER_SORT_LABEL[col])}
        <span aria-hidden className="text-[9px] leading-none">
          {sortIndicator(active, sort.dir)}
        </span>
      </button>
    </th>
  )
}

export default function AdminReviewersList() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  // UX only — the endpoint is the fence. This just avoids rendering a table that would 403.
  const mayView = canAccess('/admin/organisation/reviewers', effectiveRole(role))
  // Two panels, the same pill idiom the Sponsors and Sources screens use, so the console has one
  // way of doing this. Reviewers is the default: the list is what the page is for, and editing
  // what volunteers are told is a deliberate second click.
  const [panel, setPanel] = useState<'reviewers' | 'emails'>('reviewers')
  // Editing what every reviewer is told is an editorial power, not a reading one — so the tab is
  // offered to the roles the endpoint admits and not to `finance`, which may read the list. The
  // endpoint is the authority; this only avoids offering a 403.
  const mayEditEmails = ['super', 'org_admin', 'admin'].includes(effectiveRole(role))
  const [reviewers, setReviewers] = useState<AdminReviewer[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const { sort, setSort } = useSort<ReviewerSortKey>(DEFAULT_SORT)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    listReviewers({ token })
      .then((d) => setReviewers(d.reviewers))
      .catch(() => setError(t('admin.reviewers.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => { load() }, [load])

  // Sort the whole list, then page the sorted result — the other order would sort one page at a
  // time and shuffle rows between pages.
  const sorted = sortReviewers(reviewers, sort.key, sort.dir)
  const paged = usePagedRows(sorted)
  const onSort = (col: ReviewerSortKey) => setSort(nextSort(sort, col, firstDirFor(col)))

  // Below every hook on purpose — an early return above them would change the hook order between
  // the signed-out render and the signed-in one.
  if (role && !mayView) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.reviewers.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-4">{t('admin.reviewers.desc')}</p>

      {mayEditEmails && (
        <div role="tablist" aria-label={t('admin.reviewers.tabsAria')}
          className="flex items-center gap-2 mb-6">
          {(['reviewers', 'emails'] as const).map((key) => {
            const on = panel === key
            return (
              <button key={key} type="button" role="tab" aria-selected={on}
                onClick={() => setPanel(key)}
                className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                  on ? 'border-blue-600 bg-blue-600 text-white'
                     : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}`}>
                {t(key === 'emails' ? 'admin.reviewers.tabEmails' : 'admin.reviewers.tabReviewers')}
              </button>
            )
          })}
        </div>
      )}

      {/* Mounted only while its tab is selected, so each reveal re-reads the templates and an
          emails hiccup can never take the reviewers table down with it. */}
      {panel === 'emails' && mayEditEmails && <ReviewerEmailsCard token={token} t={t} />}

      {panel === 'reviewers' && (<>
      {error && <div className="text-red-600 mb-3">{error}</div>}
      {/* ⚠ `error` is tested BEFORE the empty check, and that is not a style choice. A failed
          fetch also leaves the list empty, so the other order prints "No reviewers yet — invite
          one" underneath the error: it tells an org_admin they have nobody when the truth is we
          could not ask. "We don't know" and "there are none" must never render the same. */}
      {loading ? (
        <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
      ) : error ? null : reviewers.length === 0 ? (
        <div className="text-center text-gray-500 mt-8">{t('admin.reviewers.empty')}</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50/80 border-b">
              <tr>
                <SortHeader col="name" sort={sort} onSort={onSort} t={t} />
                <SortHeader col="role" sort={sort} onSort={onSort} t={t} />
                {/* Languages is the one unsortable column — a set has no order to put it in. */}
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  {t('admin.reviewers.colLanguages')}
                </th>
                <SortHeader col="openNow" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="completed" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="turnaround" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="status" sort={sort} onSort={onSort} t={t} />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {paged.rows.map((r) => {
                const band = turnaroundBand(r.turnaround_days)
                return (
                  <tr key={r.id} className="hover:bg-blue-50/40 transition-colors align-top">
                    <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                      {/* The name opens the whole record — credentials, outcomes, reopens. */}
                      <Link href={`/admin/organisation/reviewers/${r.id}`}
                        className="font-medium text-blue-600 hover:text-blue-800">
                        {r.name || '—'}
                      </Link>
                      <div className="text-xs text-gray-500 mt-0.5">{r.email || '—'}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${roleBadge(r.role)}`}>
                        {t(`admin.reviewers.role.${r.role}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {orderedLanguages(r).length === 0
                        ? <span className="text-gray-400">—</span>
                        : (
                          <span className="flex flex-wrap gap-1">
                            {orderedLanguages(r).map((code) => (
                              <span key={code}
                                className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 text-xs">
                                {t(`admin.reviewers.lang.${code}`)}
                              </span>
                            ))}
                          </span>
                        )}
                    </td>
                    {/* An empty caseload is the normal state of a volunteer between assignments —
                        it is greyed, never flagged. */}
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      isFree(r) ? 'text-gray-400' : 'text-gray-900 font-semibold'}`}>
                      {r.open_now}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-gray-700">
                      {r.completed > 0 ? r.completed : <span className="text-gray-400">—</span>}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      band === 'waiting' ? 'text-amber-700 font-semibold' : 'text-gray-700'}`}
                      title={band === 'unknown' ? t('admin.reviewers.noTurnaroundHint')
                        : t('admin.reviewers.turnaroundHint')}>
                      {band === 'unknown'
                        ? <span className="text-gray-400">{t('admin.reviewers.noTurnaround')}</span>
                        : t('admin.reviewers.days', { days: String(r.turnaround_days) })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        r.paused ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>
                        {t(`admin.reviewers.status.${r.paused ? 'paused' : 'active'}`)}
                      </span>
                    </td>
                  </tr>
                )
              })}
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
      <p className="text-xs text-gray-500 mt-4 max-w-3xl">{t('admin.reviewers.footnote')}</p>
      </>)}
    </div>
  )
}
