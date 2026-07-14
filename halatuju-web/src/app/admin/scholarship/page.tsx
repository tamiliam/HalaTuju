'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import {
  getScholarshipApplications,
  getAssignableAdmins,
  assignApplication,
  DEFAULT_ADMIN_PAGE_SIZE,
  type AdminScholarshipListData,
} from '@/lib/admin-api'
import { Pagination } from '@/components/Pagination'
// import AiReliabilityCard from '@/components/AiReliabilityCard' // hidden 2026-06-13 — re-add when placement is decided (component retained)
import { REFERRING_ORG_OPTIONS, referralAcronym } from '@/lib/scholarship'
import { APPLICATION_STATUSES, statusLabelKey, statusTone, displayStatus } from '@/lib/applicationStatus'

const bucketBadge = (b: string) =>
  b === 'A' ? 'bg-green-100 text-green-700'
    : b === 'B' ? 'bg-amber-100 text-amber-700'
      : 'bg-gray-100 text-gray-500'

// ── Reviewer language matching (assignment dropdown) ───────────────────────────
const LANG_LABEL: Record<string, string> = { en: 'EN', ms: 'BM', ta: 'TA' }
type Reviewer = { id: number; name: string; languages: string[] }
const langCodesLabel = (codes: string[]) => codes.map((c) => LANG_LABEL[c] ?? c.toUpperCase()).join(', ')
/** Order reviewers for a student's preferred call language: when it's a specific language
 *  (en/ms/ta), reviewers who speak it come first and each carries a match flag; otherwise
 *  ('mixed'/unset) the list is unchanged and nothing is flagged. */
function orderReviewersFor(reviewers: Reviewer[], lang: string): Array<{ rv: Reviewer; match: boolean; specific: boolean }> {
  const specific = lang === 'en' || lang === 'ms' || lang === 'ta'
  const out = reviewers.map((rv) => ({ rv, match: specific ? rv.languages.includes(lang) : true, specific }))
  if (specific) out.sort((a, b) => Number(b.match) - Number(a.match) || a.rv.name.localeCompare(b.rv.name))
  return out
}

const PAGE_SIZE_OPTIONS = [10, 25, 50]

export default function AdminScholarshipList() {
  const { token, role } = useAdminAuth()
  const isSuper = role?.role === 'super' || !!role?.is_super_admin
  // Only super + admin see every application, so only they benefit from the assignee filter.
  // A reviewer's list is already hard-scoped to their own assigned applicants server-side, so
  // the filter is redundant for them (and "Unassigned" would always return nothing).
  const canFilterByAssignee = isSuper || role?.role === 'admin'
  const { t } = useT()
  const [data, setData] = useState<AdminScholarshipListData | null>(null)
  // Super-only inline reviewer assignment (the "Assigned" column dropdown).
  const [reviewers, setReviewers] = useState<Array<{ id: number; name: string; languages: string[] }>>([])
  const [assignNote, setAssignNote] = useState<Record<number, string>>({})
  const [bucket, setBucket] = useState('')
  const [statusF, setStatusF] = useState('')
  const [source, setSource] = useState('')
  const [assignedF, setAssignedF] = useState('')
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced value actually sent to the API
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_ADMIN_PAGE_SIZE)
  // Column sorting (server-side). '' = default (newest submitted first).
  const [sort, setSort] = useState<'' | 'name' | 'merit' | 'source' | 'status' | 'submitted'>('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  // Click a sortable header: same column flips direction; a new column starts at a
  // sensible default (merit high→low; name/source/status A→Z). Resets to page 1.
  type SortKey = 'name' | 'merit' | 'source' | 'status' | 'submitted'
  const toggleSort = (key: SortKey) => {
    if (sort === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSort(key)
      setSortDir(key === 'merit' ? 'desc' : 'asc')
    }
    setPage(1)
  }
  const sortArrow = (key: SortKey) => (sort === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '')

  // Debounce the search box so a request doesn't fire on every keystroke.
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  useEffect(() => {
    if (!token) return
    setLoading(true)
    getScholarshipApplications(
      {
        bucket: bucket || undefined,
        status: statusF || undefined,
        source: source || undefined,
        assigned: assignedF || undefined,
        q: q || undefined,
        page,
        pageSize,
        sort: sort || undefined,
        dir: sort ? sortDir : undefined,
      },
      { token },
    )
      .then(setData)
      .catch(() => setError(t('admin.scholarship.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, bucket, statusF, source, assignedF, q, page, pageSize, sort, sortDir])

  const apps = data?.applications ?? []

  // Reviewers for the assignment dropdown — fetched once, super-admins only (the endpoint
  // itself is super-only on the backend).
  useEffect(() => {
    if (!token || !isSuper) return
    getAssignableAdmins({ token })
      .then((r) => setReviewers(r.admins.map((a) => ({ id: a.id, name: a.name, languages: a.languages || [] }))))
      .catch(() => {})
  }, [token, isSuper])

  // Inline (re)assign — option A: attempt and surface a 'not ready' / error inline. The
  // backend enforces super-only + reviewer-target; first-assign needs the app to be ready.
  const handleAssign = async (appId: number, reviewerId: number | null) => {
    if (!token) return
    setAssignNote((n) => ({ ...n, [appId]: '' }))
    try {
      const updated = await assignApplication(appId, reviewerId, { token })
      setData((d) => d && {
        ...d,
        applications: d.applications.map((a) => a.id === appId
          ? { ...a, assigned_to_id: updated.assigned_to_id, assigned_to_name: updated.assigned_to_name }
          : a),
      })
    } catch (e) {
      const code = e instanceof Error ? e.message : ''
      const known = ['not_ready', 'not_reviewer', 'bad_assignee', 'not_assignable',
                     'findings_submitted']
      setAssignNote((n) => ({ ...n, [appId]: known.includes(code)
        ? t(`admin.scholarship.assign.error.${code}`)
        : t('admin.scholarship.assignError') }))
    }
  }

  // #7: persist the current filtered/sorted page's ordered ids so the detail cockpit
  // can offer prev/next navigation that follows what the officer is looking at.
  useEffect(() => {
    if (typeof window === 'undefined' || !data) return
    try {
      sessionStorage.setItem(
        'halatuju_admin_scholarship_nav',
        JSON.stringify((data.applications ?? []).map((a) => a.id)),
      )
    } catch { /* sessionStorage unavailable — nav just won't show */ }
  }, [data])

  // Changing any filter resets to page 1 — otherwise you can land on a page
  // that no longer exists for the narrowed result set ("page 5 of 2").
  const changeFilter = (setter: (v: string) => void) => (value: string) => {
    setter(value)
    setPage(1)
  }

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.scholarship.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-4">
        {data ? t('admin.scholarship.countSubtitle', { count: String(data.count) }) : ' '}
      </p>

      {/* AI reliability card hidden 2026-06-13 — placement TBD by owner; component kept in components/AiReliabilityCard.tsx */}

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[180px] sm:flex-none sm:w-64">
          <svg className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.35-4.35M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('admin.searchPlaceholder')}
            className="w-full border rounded-lg pl-9 pr-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
        <select value={source} onChange={(e) => changeFilter(setSource)(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm w-40 truncate" title={t('admin.scholarship.allSources')}>
          <option value="">{t('admin.scholarship.allSources')}</option>
          {REFERRING_ORG_OPTIONS.map((code) => <option key={code} value={code}>{t(`scholarship.apply.org.${code}`)}</option>)}
        </select>
        <select value={bucket} onChange={(e) => changeFilter(setBucket)(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allBuckets')}</option>
          <option value="A">Bucket A</option>
          <option value="B">Bucket B</option>
        </select>
        <select value={statusF} onChange={(e) => changeFilter(setStatusF)(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allStatuses')}</option>
          {APPLICATION_STATUSES.map((s) => <option key={s} value={s}>{t(statusLabelKey(s))}</option>)}
        </select>
        {canFilterByAssignee && (
          // Admin/super view this filter (it's hidden for reviewers, whose list is self-scoped).
          // "Assigned to me" is dropped — applicants are assigned to reviewers, not to admins —
          // and replaced with each active reviewer, so an admin can filter by who's reviewing.
          <select value={assignedF} onChange={(e) => changeFilter(setAssignedF)(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
            <option value="">{t('admin.scholarship.allAssignees')}</option>
            <option value="none">{t('admin.scholarship.unassigned')}</option>
            {reviewers.length > 0 && (
              <optgroup label={t('admin.scholarship.byReviewer')}>
                {reviewers.map((rv) => <option key={rv.id} value={rv.id}>{rv.name}</option>)}
              </optgroup>
            )}
          </select>
        )}
      </div>

      {error && <div className="text-red-600">{error}</div>}
      {loading && !data ? (
        <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
      ) : apps.length === 0 ? (
        <div className="text-center text-gray-500 mt-8">{t('admin.scholarship.empty')}</div>
      ) : (
        <>
        <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50/80 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('name')}
                    className="uppercase tracking-wider hover:text-gray-900">
                    {t('admin.scholarship.name')}{sortArrow('name')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('source')}
                    className="uppercase tracking-wider hover:text-gray-900">
                    {t('admin.scholarship.source')}{sortArrow('source')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.bucket')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.qualShort')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('merit')}
                    className="uppercase tracking-wider hover:text-gray-900">
                    {t('admin.scholarship.merit')}{sortArrow('merit')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('status')}
                    className="uppercase tracking-wider hover:text-gray-900">
                    {t('admin.scholarship.status')}{sortArrow('status')}
                  </button>
                </th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  <button type="button" onClick={() => toggleSort('submitted')}
                    className="uppercase tracking-wider hover:text-gray-900">
                    {t('admin.scholarship.submitted')}{sortArrow('submitted')}
                  </button>
                </th>
                {isSuper && <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.assigned')}</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {apps.map((a) => (
                <tr key={a.id} className="hover:bg-blue-50/40 transition-colors">
                  <td className="px-4 py-3 border-l-[3px] border-l-blue-500">
                    <Link href={`/admin/scholarship/${a.id}`} className="text-blue-600 font-medium hover:underline">
                      {a.name || '—'}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600" title={a.referral_source ? t(`scholarship.apply.org.${a.referral_source}`) : ''}>{referralAcronym(a.referral_source) || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${bucketBadge(a.bucket)}`}>{a.bucket || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{a.qualification?.toUpperCase()}</td>
                  <td className="px-4 py-3 text-gray-700 tabular-nums">{a.merit_score ?? '—'}</td>
                  <td className="px-4 py-3">
                    {(() => {
                      // A super-reopened decision shows "Reopened", overriding the stored accepted/rejected.
                      const s = displayStatus(a)
                      return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusTone(s)}`}>{t(statusLabelKey(s))}</span>
                    })()}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(a.submitted_at)}</td>
                  {isSuper && (
                    <td className="px-4 py-3">
                      {LANG_LABEL[a.call_language] && (
                        <p className="mb-1 text-[11px] text-gray-500">
                          {t('admin.scholarship.prefersLang', { lang: LANG_LABEL[a.call_language] })}
                        </p>
                      )}
                      <select
                        value={a.assigned_to_id ?? ''}
                        onChange={(e) => handleAssign(a.id, e.target.value ? Number(e.target.value) : null)}
                        // A case may only change hands while there IS a review to do (Completed /
                        // interviewing). Shortlisted and rejected aren't ready; awaiting-QC and
                        // beyond are over. The server refuses either way — disabling here means the
                        // officer isn't invited to take an action that will bounce.
                        disabled={a.assignable === false}
                        title={a.assignable === false
                          ? t('admin.scholarship.assign.error.not_assignable') : undefined}
                        className="border rounded-lg px-2 py-1 text-sm bg-white max-w-[220px] disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
                      >
                        <option value="">{t('admin.scholarship.unassigned')}</option>
                        {/* keep the current assignee selectable even if not in the reviewer list */}
                        {a.assigned_to_id != null && !reviewers.some((rv) => rv.id === a.assigned_to_id) && (
                          <option value={a.assigned_to_id}>{a.assigned_to_name || a.assigned_to_id}</option>
                        )}
                        {orderReviewersFor(reviewers, a.call_language).map(({ rv, match, specific }) => (
                          <option key={rv.id} value={rv.id}>
                            {specific ? (match ? '✓ ' : '⚠ ') : ''}{rv.name}
                            {rv.languages.length ? ` — ${langCodesLabel(rv.languages)}` : ' — —'}
                          </option>
                        ))}
                      </select>
                      {assignNote[a.id] && <p className="text-xs text-red-500 mt-1 max-w-[180px]">{assignNote[a.id]}</p>}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.count}
            pageSize={data.page_size}
            onPageChange={setPage}
            pageSizeOptions={PAGE_SIZE_OPTIONS}
            onPageSizeChange={(size) => {
              setPageSize(size)
              setPage(1)
            }}
            rangeKey="admin.scholarship.showingRange"
          />
        )}
        </>
      )}
    </div>
  )
}
