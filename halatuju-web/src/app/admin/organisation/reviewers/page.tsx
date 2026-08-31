'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import PanelTabs from '@/components/admin/PanelTabs'
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
import { roleBadgeClass } from '@/lib/roleBadge'

// The reviewers directory (request #10). Staff invites and revokes; this is where you LOOK at
// somebody before handing them the next case. Sorted by open caseload on arrival, because that is
// the question the page is opened to answer.
//
// Two things are deliberately absent and must stay absent unless the owner says otherwise:
// a corrections count (it reads as a competence score — the reopens live on the detail page WITH
// their reasons) and a programmes column (with one programme it could only ever say one thing).

const roleBadge = (r: string) => roleBadgeClass(r)

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
        className={`inline-flex items-center gap-1 font-semibold text-xs uppercase tracking-wider hover:text-info-600 ${
          active ? 'text-info-600' : 'text-ground-600'}`}>
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
  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.reviewers.title')}</h1>
      <p className="text-sm text-ground-500 mt-1 mb-4">{t('admin.reviewers.desc')}</p>

      {mayEditEmails && (
        <PanelTabs ariaLabelKey="admin.reviewers.tabsAria" active={panel}
          onSelect={(k) => setPanel(k as 'reviewers' | 'emails')}
          tabs={[
            { key: 'reviewers', labelKey: 'admin.reviewers.tabReviewers' },
            { key: 'emails', labelKey: 'admin.reviewers.tabEmails' },
            // Reviewers sign nothing today. Shown disabled so the three surfaces look alike and
            // the panel reads as coming rather than as missing (owner, 2026-08-04).
            { key: 'terms', labelKey: 'admin.reviewers.tabTerms', disabled: true },
          ]} />
      )}

      {/* Mounted only while its tab is selected, so each reveal re-reads the templates and an
          emails hiccup can never take the reviewers table down with it. */}
      {panel === 'emails' && mayEditEmails && <ReviewerEmailsCard token={token} t={t} />}

      {panel === 'reviewers' && (<>
      {error && <div className="text-critical-600 mb-3">{error}</div>}
      {/* ⚠ `error` is tested BEFORE the empty check, and that is not a style choice. A failed
          fetch also leaves the list empty, so the other order prints "No reviewers yet — invite
          one" underneath the error: it tells an org_admin they have nobody when the truth is we
          could not ask. "We don't know" and "there are none" must never render the same. */}
      {loading ? (
        <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>
      ) : error ? null : reviewers.length === 0 ? (
        <div className="text-center text-ground-500 mt-8">{t('admin.reviewers.empty')}</div>
      ) : (
        <div className="bg-ground-0 rounded-xl shadow-sm border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-ground-50/80 border-b">
              <tr>
                <SortHeader col="name" sort={sort} onSort={onSort} t={t} />
                <SortHeader col="role" sort={sort} onSort={onSort} t={t} />
                {/* Languages is the one unsortable column — a set has no order to put it in. */}
                <th className="text-left px-4 py-3 font-semibold text-ground-600 text-xs uppercase tracking-wider">
                  {t('admin.reviewers.colLanguages')}
                </th>
                <SortHeader col="openNow" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="completed" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="turnaround" sort={sort} onSort={onSort} align="right" t={t} />
                <SortHeader col="status" sort={sort} onSort={onSort} t={t} />
              </tr>
            </thead>
            <tbody className="divide-y divide-ground-100">
              {paged.rows.map((r) => {
                const band = turnaroundBand(r.turnaround_days)
                return (
                  <tr key={r.id} className="hover:bg-info-50/40 transition-colors align-top">
                    <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                      {/* The name opens the whole record — credentials, outcomes, reopens. */}
                      <Link href={`/admin/organisation/reviewers/${r.id}`}
                        className="font-medium text-info-600 hover:text-info-800">
                        {r.name || '—'}
                      </Link>
                      <div className="text-xs text-ground-500 mt-0.5">{r.email || '—'}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${roleBadge(r.role)}`}>
                        {t(`admin.reviewers.role.${r.role}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-ground-700">
                      {orderedLanguages(r).length === 0
                        ? <span className="text-ground-400">—</span>
                        : (
                          <span className="flex flex-wrap gap-1">
                            {orderedLanguages(r).map((code) => (
                              <span key={code}
                                className="px-1.5 py-0.5 rounded bg-ground-100 text-ground-600 text-xs">
                                {t(`admin.reviewers.lang.${code}`)}
                              </span>
                            ))}
                          </span>
                        )}
                    </td>
                    {/* An empty caseload is the normal state of a volunteer between assignments —
                        it is greyed, never flagged. */}
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      isFree(r) ? 'text-ground-400' : 'text-ground-900 font-semibold'}`}>
                      {r.open_now}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ground-700">
                      {r.completed > 0 ? r.completed : <span className="text-ground-400">—</span>}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${
                      band === 'waiting' ? 'text-caution-700 font-semibold' : 'text-ground-700'}`}
                      title={band === 'unknown' ? t('admin.reviewers.noTurnaroundHint')
                        : t('admin.reviewers.turnaroundHint')}>
                      {band === 'unknown'
                        ? <span className="text-ground-400">{t('admin.reviewers.noTurnaround')}</span>
                        : t('admin.reviewers.days', { days: String(r.turnaround_days) })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        r.paused ? 'bg-caution-100 text-caution-700' : 'bg-positive-100 text-positive-700'}`}>
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
      <p className="text-xs text-ground-500 mt-4 max-w-3xl">{t('admin.reviewers.footnote')}</p>
      </>)}
    </div>
  )
}
