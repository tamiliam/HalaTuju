'use client'

import { useAuth } from '@/lib/auth-context'
import { getPartnerStudent, type StudentDetailData } from '@/lib/admin-api'
import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function AdminStudentDetail() {
  const { id } = useParams<{ id: string }>()
  const { token } = useAuth()
  const [data, setData] = useState<StudentDetailData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token || !id) return
    getPartnerStudent(id, { token })
      .then(setData)
      .catch(() => setError('Pelajar tidak ditemui.'))
  }, [token, id])

  if (error) {
    return <div className="text-red-600 mt-8">{error}</div>
  }

  if (!data) {
    return (
      <div className="mt-8 text-center text-gray-500">Loading...</div>
    )
  }

  const grades =
    data.exam_type === 'stpm' ? data.stpm_grades : data.grades

  return (
    <div>
      <Link
        href="/admin/students"
        className="text-blue-600 text-sm hover:underline mb-4 block"
      >
        &larr; Kembali ke senarai
      </Link>

      <h1 className="text-2xl font-bold mb-2">
        {data.name || 'Tiada Nama'}
      </h1>
      <p className="text-gray-500 mb-6">
        {data.nric} &middot; {data.exam_type?.toUpperCase()} &middot;{' '}
        {data.gender}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Grades */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">
            Keputusan {data.exam_type?.toUpperCase()}
          </h2>
          {grades && Object.keys(grades).length > 0 ? (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              {Object.entries(grades).map(([subject, grade]) => (
                <div key={subject}>
                  <dt className="text-gray-500">{subject}</dt>
                  <dd className="font-medium">{grade as string}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-gray-400 text-sm">Belum diisi</p>
          )}
        </div>

        {/* Saved Courses */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Kursus Disimpan</h2>
          {data.saved_courses?.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {data.saved_courses.map((c) => (
                <li key={c.course_id} className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  {c.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400 text-sm">Tiada kursus disimpan</p>
          )}
        </div>

        {/* Other info */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Maklumat Lain</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Kewarganegaraan</dt>
              <dd>{data.nationality || '\u2014'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Negeri Pilihan</dt>
              <dd>{data.preferred_state || '\u2014'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Tarikh Daftar</dt>
              <dd>
                {new Date(data.created_at).toLocaleDateString('ms-MY')}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  )
}
