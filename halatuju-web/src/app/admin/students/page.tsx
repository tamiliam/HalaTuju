'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import {
  getPartnerStudents,
  getExportUrl,
  type StudentListData,
} from '@/lib/admin-api'
import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function AdminStudentList() {
  const { token } = useAdminAuth()
  const [data, setData] = useState<StudentListData | null>(null)
  const [error, setError] = useState('')

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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Pelajar ({data.count})</h1>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          Muat Turun CSV
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium">Nama</th>
              <th className="text-left p-3 font-medium">No. KP</th>
              <th className="text-left p-3 font-medium">Jantina</th>
              <th className="text-left p-3 font-medium">Peperiksaan</th>
              <th className="text-left p-3 font-medium">Tarikh</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {data.students.map((s) => (
              <tr
                key={s.supabase_user_id}
                className="hover:bg-gray-50"
              >
                <td className="p-3">
                  <Link
                    href={`/admin/students/${s.supabase_user_id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {s.name || '\u2014'}
                  </Link>
                </td>
                <td className="p-3 font-mono text-xs">
                  {s.nric || '\u2014'}
                </td>
                <td className="p-3">{s.gender || '\u2014'}</td>
                <td className="p-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      s.exam_type === 'stpm'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {s.exam_type?.toUpperCase()}
                  </span>
                </td>
                <td className="p-3 text-gray-500">
                  {new Date(s.created_at).toLocaleDateString('ms-MY')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
