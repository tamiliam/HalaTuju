'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
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
import { REFERRING_ORG_OPTIONS } from '@/lib/scholarship'

const bucketBadge = (b: string) =>
  b === 'A' ? 'bg-green-100 text-green-700'
    : b === 'B' ? 'bg-amber-100 text-amber-700'
      : 'bg-gray-100 text-gray-500'

const statusBadge = (s: string) =>
  s === 'shortlisted' ? 'bg-blue-100 text-blue-700'
    : s === 'profile_complete' ? 'bg-emerald-100 text-emerald-700'
      : s === 'interviewing' ? 'bg-violet-100 text-violet-700'
        : s === 'interviewed' ? 'bg-indigo-100 text-indigo-700'
          : s === 'accepted' ? 'bg-green-100 text-green-700'
            : s === 'rejected' ? 'bg-red-100 text-red-600'
              : 'bg-gray-100 text-gray-600'

const STATUS_OPTIONS = [
  'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'accepted', 'rejected',
]

const PAGE_SIZE_OPTIONS = [10, 25, 50]

export default function AdminScholarshipList() {
  const { token, role } = useAdminAuth()
  const isSuper = role?.role === 'super' || !!role?.is_super_admin
  const { t } = useT()
  const [data, setData] = useState<AdminScholarshipListData | null>(null)
  // Super-only inline reviewer assignment (the "Assigned" column dropdown).
  const [reviewers, setReviewers] = useState<Array<{ id: number; name: string }>>([])
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
      },
      { token },
    )
      .then(setData)
      .catch(() => setError(t('admin.scholarship.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, bucket, statusF, source, assignedF, q, page, pageSize])

  const apps = data?.applications ?? []

  // Reviewers for the assignment dropdown — fetched once, super-admins only (the endpoint
  // itself is super-only on the backend).
  useEffect(() => {
    if (!token || !isSuper) return
    getAssignableAdmins({ token })
      .then((r) => setReviewers(r.admins.map((a) => ({ id: a.id, name: a.name }))))
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
      const known = ['not_ready', 'not_reviewer', 'bad_assignee']
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
        <select value={source} onChange={(e) => changeFilter(setSource)(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
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
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={assignedF} onChange={(e) => changeFilter(setAssignedF)(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allAssignees')}</option>
          <option value="me">{t('admin.scholarship.assignedToMe')}</option>
          <option value="none">{t('admin.scholarship.unassigned')}</option>
        </select>
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
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.name')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.source')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.bucket')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.qualShort')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.merit')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.status')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.submitted')}</th>
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
                  <td className="px-4 py-3 text-gray-600">{a.referral_source ? t(`scholarship.apply.org.${a.referral_source}`) : '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${bucketBadge(a.bucket)}`}>{a.bucket || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{a.qualification?.toUpperCase()}</td>
                  <td className="px-4 py-3 text-gray-700 tabular-nums">{a.merit_score ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadge(a.status)}`}>{a.status}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{new Date(a.submitted_at).toLocaleDateString('ms-MY')}</td>
                  {isSuper && (
                    <td className="px-4 py-3">
                      <select
                        value={a.assigned_to_id ?? ''}
                        onChange={(e) => handleAssign(a.id, e.target.value ? Number(e.target.value) : null)}
                        className="border rounded-lg px-2 py-1 text-sm bg-white max-w-[160px]"
                      >
                        <option value="">{t('admin.scholarship.unassigned')}</option>
                        {/* keep the current assignee selectable even if not in the reviewer list */}
                        {a.assigned_to_id != null && !reviewers.some((rv) => rv.id === a.assigned_to_id) && (
                          <option value={a.assigned_to_id}>{a.assigned_to_name || a.assigned_to_id}</option>
                        )}
                        {reviewers.map((rv) => (
                          <option key={rv.id} value={rv.id}>{rv.name}</option>
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
