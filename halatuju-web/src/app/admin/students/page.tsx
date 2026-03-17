'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getPartnerStudents,
  getExportUrl,
  type StudentListData,
} from '@/lib/admin-api'
import { useEffect, useState } from 'react'
import Link from 'next/link'

const PER_PAGE = 5

export default function AdminStudentList() {
  const { token, role } = useAdminAuth()
  const [data, setData] = useState<StudentListData | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)

  useEffect(() => {
    if (!token) return
    getPartnerStudents({ token })
      .then(setData)
      .catch(() => setError('Gagal memuat senarai pelajar.'))
  }, [token])

  if (error) {
    return <div className="text-red-600 mt-8">{error}</div>
  }

  if (!data) {
    return (
      <div className="mt-8 text-center text-gray-500">Loading...</div>
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

  const totalPages = Math.ceil(data.students.length / PER_PAGE)
  const paginated = data.students.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-2xl font-bold">Pelajar ({data.count})</h1>
          <p className="text-sm text-gray-500 mt-1">Senarai pendaftaran pelajar terkini di platform HalaTuju.</p>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Muat Turun CSV
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border overflow-x-auto mt-6">
        <table className="w-full text-sm">
          <thead className="bg-gray-50/80 border-b">
            <tr>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Nama</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">No. KP</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Jantina</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Peperiksaan</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Sekolah</th>
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Telefon</th>
              {role?.is_super_admin && (
                <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">
                  Sumber <span className="text-[10px] text-gray-400 ml-1 normal-case">[Super Admin]</span>
                </th>
              )}
              <th className="text-left px-4 py-3.5 font-semibold text-gray-600 text-xs uppercase tracking-wider">Tarikh</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {paginated.map((s) => (
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
                  {s.nric || '\u2014'}
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
                <td className="px-4 py-3.5 text-gray-600">{s.phone || '\u2014'}</td>
                {role?.is_super_admin && (
                  <td className="px-4 py-3.5">
                    <div className="text-gray-600">{s.referral_source || '\u2014'}</div>
                    {s.org_name && (
                      <div className="text-xs text-gray-400">{s.org_name}</div>
                    )}
                  </td>
                )}
                <td className="px-4 py-3.5 text-gray-500">
                  {new Date(s.created_at).toLocaleDateString('ms-MY')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
        <span>
          Papar {Math.min((page - 1) * PER_PAGE + 1, data.students.length)}{'\u2013'}{Math.min(page * PER_PAGE, data.students.length)} daripada {data.students.length} pelajar
        </span>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2.5 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              &lsaquo;
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                  p === page
                    ? 'bg-blue-600 text-white'
                    : 'hover:bg-gray-50 border border-gray-200'
                }`}
              >
                {p}
              </button>
            ))}
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-2.5 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              &rsaquo;
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
