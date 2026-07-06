'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import {
  getPartnerStudents,
  getExportUrl,
  DEFAULT_ADMIN_PAGE_SIZE,
  type StudentListData,
} from '@/lib/admin-api'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { formatNricDisplay } from '@/lib/scholarship'
import { Pagination } from '@/components/Pagination'

const PAGE_SIZE_OPTIONS = [10, 25, 50]

const formatPhone = (phone: string | null) => {
  if (!phone) return '\u2014'
  const digits = phone.replace(/\D/g, '')
  let local: string
  if (digits.startsWith('60')) {
    local = digits.slice(2)
  } else if (digits.startsWith('0')) {
    local = digits.slice(1)
  } else {
    return phone
  }
  if (local.startsWith('11') && local.length === 10) {
    return `+60 ${local.slice(0, 2)}-${local.slice(2, 6)} ${local.slice(6)}`
  }
  if (local.length === 9) {
    return `+60 ${local.slice(0, 2)}-${local.slice(2, 5)} ${local.slice(5)}`
  }
  return phone
}

export default function AdminStudentList() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<StudentListData | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_ADMIN_PAGE_SIZE)
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced value actually sent to the API
  const [exam, setExam] = useState('')
  const [source, setSource] = useState('')

  // Debounce the search box so a request doesn't fire on every keystroke.
  // Resetting to page 1 here keeps a narrowed result set from landing on a
  // page that no longer exists.
  useEffect(() => {
    const id = setTimeout(() => {
      setQ(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(id)
  }, [search])

  useEffect(() => {
    if (!token) return
    getPartnerStudents(
      { page, pageSize, q: q || undefined, exam: exam || undefined, source: source || undefined },
      { token },
    )
      .then(setData)
      .catch(() => setError(t('admin.loadStudentsFailed')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, page, pageSize, q, exam, source])

  if (error) {
    return <div className="text-red-600 mt-8">{error}</div>
  }

  if (!data) {
    return (
      <div className="mt-8 text-center text-gray-500">{t('common.loading')}</div>
    )
  }

  const handleExport = async () => {
    if (!token) return
    const url = getExportUrl()
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'students.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const rows = data.students

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">{t('admin.studentsTitle')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('admin.studentsCount', { count: String(data.count) })}</p>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm self-start sm:self-auto"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {t('admin.downloadCsv')}
        </button>
      </div>

      {/* Filters: search · exam · source */}
      <div className="flex flex-col sm:flex-row gap-3 mt-4">
        <div className="relative flex-1 sm:max-w-xs">
          <svg className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.35-4.35M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('admin.searchPlaceholder')}
            className="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
        <select
          value={exam}
          onChange={(e) => { setExam(e.target.value); setPage(1) }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white text-gray-600"
        >
          <option value="">{t('admin.allExams')}</option>
          <option value="spm">SPM</option>
          <option value="stpm">STPM</option>
        </select>
        <select
          value={source}
          onChange={(e) => { setSource(e.target.value); setPage(1) }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white text-gray-600"
        >
          <option value="">{t('admin.allSources')}</option>
          {data.source_options.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Mobile: card layout */}
      <div className="md:hidden space-y-3 mt-6">
        {rows.map((s) => (
          <Link
            key={s.supabase_user_id}
            href={`/admin/students/${s.supabase_user_id}`}
            className="block bg-white rounded-xl shadow-sm border p-4 hover:border-blue-300 transition-colors border-l-[3px] border-l-blue-500"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium text-blue-600">{s.name || '\u2014'}</p>
                <p className="text-xs text-gray-500 font-mono mt-0.5">{formatNricDisplay(s.nric)}</p>
              </div>
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${
                  s.exam_type === 'stpm'
                    ? 'bg-purple-100 text-purple-700'
                    : 'bg-blue-100 text-blue-700'
                }`}
              >
                {s.exam_type?.toUpperCase()}
              </span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
              {s.gender && <span>{s.gender}</span>}
              {s.contact_phone && <span>{formatPhone(s.contact_phone)}</span>}
              <span>{formatDate(s.created_at)}</span>
            </div>
          </Link>
        ))}
      </div>

      {/* Desktop: table layout */}
      <div className="hidden md:block bg-white rounded-xl shadow-sm border overflow-x-auto mt-6">
        <table className="w-full text-sm">
          <thead className="bg-gray-50/80 border-b">
            <tr>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.nameHeader')}</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.nricHeader')}</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.genderHeader')}</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.examHeader')}</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.schoolHeader')}</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.phoneHeader')}</th>
              {role?.is_super_admin && (
                <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  {t('admin.sourceHeader')} <span className="text-[10px] text-gray-400 ml-1 normal-case">[{t('admin.superAdmin')}]</span>
                </th>
              )}
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.dateHeader')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((s) => (
              <tr
                key={s.supabase_user_id}
                className="hover:bg-blue-50/40 transition-colors"
              >
                <td className="px-4 py-3.5 border-l-[3px] border-l-blue-500">
                  <Link
                    href={`/admin/students/${s.supabase_user_id}`}
                    className="text-blue-600 font-medium hover:underline"
                  >
                    {s.name || '\u2014'}
                  </Link>
                </td>
                <td className="px-4 py-3.5 font-mono text-xs text-gray-600">
                  {formatNricDisplay(s.nric)}
                </td>
                <td className="px-4 py-3.5 text-gray-600">{s.gender || '\u2014'}</td>
                <td className="px-4 py-3.5">
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                      s.exam_type === 'stpm'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {s.exam_type?.toUpperCase()}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-gray-600">{s.school || '\u2014'}</td>
                <td className="px-4 py-3.5 text-gray-600">{formatPhone(s.contact_phone)}</td>
                {role?.is_super_admin && (
                  <td className="px-4 py-3.5">
                    <div className="text-gray-600">{s.referral_source || '\u2014'}</div>
                    {s.org_name && (
                      <div className="text-xs text-gray-400">{s.org_name}</div>
                    )}
                  </td>
                )}
                <td className="px-4 py-3.5 text-gray-500">
                  {formatDate(s.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
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
      />
    </div>
  )
}
