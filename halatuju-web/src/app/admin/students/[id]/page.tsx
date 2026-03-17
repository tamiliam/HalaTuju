'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { getPartnerStudent, deleteStudent, type StudentDetailData } from '@/lib/admin-api'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function AdminStudentDetail() {
  const { id } = useParams<{ id: string }>()
  const { token, role } = useAdminAuth()
  const router = useRouter()
  const [data, setData] = useState<StudentDetailData | null>(null)
  const [error, setError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleting, setDeleting] = useState(false)

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
    return <div className="mt-8 text-center text-gray-500">Loading...</div>
  }

  const handleDelete = async () => {
    if (deleteConfirm !== 'delete') return
    setDeleting(true)
    try {
      await deleteStudent(data.supabase_user_id, { token: token! })
      router.replace('/admin/students')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
      setDeleting(false)
    }
  }

  const hasSpmGrades = data.grades && Object.keys(data.grades).length > 0
  const hasStpmGrades = data.stpm_grades && Object.keys(data.stpm_grades).length > 0

  // Extract field interests from student_signals
  const fieldInterest = (data.student_signals?.field_interest || {}) as Record<string, number>

  const getStrengthLabel = (value: number) => {
    if (value >= 0.7) return { text: 'Kuat', className: 'bg-green-100 text-green-700' }
    if (value >= 0.4) return { text: 'Sederhana', className: 'bg-yellow-100 text-yellow-700' }
    return { text: 'Rendah', className: 'bg-gray-100 text-gray-600' }
  }

  return (
    <div>
      <Link href="/admin/students" className="text-blue-600 text-sm hover:underline mb-4 block">
        &larr; Kembali ke senarai
      </Link>

      <h1 className="text-2xl font-bold mb-2">{data.name || 'Tiada Nama'}</h1>
      <p className="text-gray-500 mb-6">
        {data.nric} &middot; {data.exam_type?.toUpperCase()} &middot; {data.gender}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: Maklumat Peribadi */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Maklumat Peribadi</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Nama Penuh</dt><dd>{data.name || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">No. KP</dt><dd className="font-mono">{data.nric || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Angka Giliran</dt><dd className="font-mono">{data.angka_giliran || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Jantina</dt><dd>{data.gender || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Kewarganegaraan</dt><dd>{data.nationality || '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 2: Hubungi & Sekolah */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Hubungi &amp; Sekolah</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Telefon</dt><dd>{data.phone || '\u2014'}</dd></div>
            <div><dt className="text-gray-500">Alamat</dt><dd className="mt-1">{data.address || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Sekolah</dt><dd>{data.school || '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 3: Latar Belakang Keluarga */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Latar Belakang Keluarga</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Pendapatan Keluarga</dt><dd>{data.family_income || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Bilangan Adik-Beradik</dt><dd>{data.siblings ?? '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 4: Kesihatan & Kelayakan */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Kesihatan &amp; Kelayakan</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Buta Warna</dt><dd>{data.colorblind || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">OKU</dt><dd>{data.disability || '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 5: SPM Grades (shown if SPM grades exist) */}
        {hasSpmGrades && (
          <div className="bg-white rounded-lg p-6 shadow-sm border md:col-span-2">
            <h2 className="font-semibold mb-3">Keputusan SPM</h2>
            <dl className="grid grid-cols-3 gap-2 text-sm">
              {Object.entries(data.grades).map(([subject, grade]) => (
                <div key={subject}>
                  <dt className="text-gray-500">{subject.toUpperCase()}</dt>
                  <dd className="font-medium">{grade as string}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {/* Card 6: STPM Grades (shown if STPM grades exist) */}
        {hasStpmGrades && (
          <div className="bg-white rounded-lg p-6 shadow-sm border md:col-span-2">
            <h2 className="font-semibold mb-3">Keputusan STPM</h2>
            <div className="flex gap-6 mb-3 text-sm">
              {data.stpm_cgpa != null && (
                <div><span className="text-gray-500">CGPA:</span> <span className="font-medium">{data.stpm_cgpa.toFixed(2)}</span></div>
              )}
              {data.muet_band != null && (
                <div><span className="text-gray-500">MUET:</span> <span className="font-medium">Band {data.muet_band}</span></div>
              )}
            </div>
            <dl className="grid grid-cols-3 gap-2 text-sm">
              {Object.entries(data.stpm_grades).map(([subject, grade]) => (
                <div key={subject}>
                  <dt className="text-gray-500">{subject}</dt>
                  <dd className="font-medium">{grade as string}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {/* Show message if no grades at all */}
        {!hasSpmGrades && !hasStpmGrades && (
          <div className="bg-white rounded-lg p-6 shadow-sm border md:col-span-2">
            <h2 className="font-semibold mb-3">Keputusan Peperiksaan</h2>
            <p className="text-gray-400 text-sm">Belum diisi</p>
          </div>
        )}

        {/* Card 7: Keutamaan & Isyarat */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h2 className="font-semibold mb-3">Keutamaan &amp; Isyarat</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Negeri Pilihan</dt><dd>{data.preferred_state || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Tekanan Kewangan</dt><dd>{data.financial_pressure || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Kesanggupan Berpindah</dt><dd>{data.travel_willingness || '\u2014'}</dd></div>
          </dl>
          {Object.keys(fieldInterest).length > 0 && (
            <div className="mt-3">
              <p className="text-gray-500 text-sm mb-2">Minat Bidang</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(fieldInterest).map(([field, value]) => {
                  const strength = getStrengthLabel(value as number)
                  return (
                    <span key={field} className="flex items-center gap-1.5 text-sm">
                      {field}
                      <span className={`px-1.5 py-0.5 rounded text-xs ${strength.className}`}>{strength.text}</span>
                    </span>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Card 8: Kursus Disimpan */}
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

        {/* Card 9: Sumber Rujukan (super admin only) */}
        {role?.is_super_admin && (
          <div className="bg-white rounded-lg p-6 shadow-sm border">
            <h2 className="font-semibold mb-3">
              Sumber Rujukan
              <span className="text-xs text-gray-400 ml-2">[Super Admin]</span>
            </h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Sumber</dt><dd>{data.referral_source || '\u2014'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Organisasi</dt><dd>{data.org_name || '\u2014'}</dd></div>
            </dl>
          </div>
        )}
      </div>

      {/* Danger Zone - super admin only */}
      {role?.is_super_admin && (
        <div className="mt-8 border border-red-200 rounded-lg p-6 bg-red-50">
          <h2 className="font-semibold text-red-700 mb-1">
            Zon Bahaya
            <span className="text-xs text-red-400 ml-2">[Super Admin]</span>
          </h2>
          <p className="text-sm text-red-600 mb-4">
            Tindakan ini tidak boleh dibatalkan. Semua data pelajar akan dipadamkan.
          </p>
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder='Taip "delete" untuk mengesahkan'
              className="px-3 py-2 border border-red-300 rounded-lg text-sm w-64"
            />
            <button
              onClick={handleDelete}
              disabled={deleteConfirm !== 'delete' || deleting}
              className="px-4 py-2 border border-red-600 text-red-600 rounded-lg text-sm hover:bg-red-600 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deleting ? 'Memadamkan...' : 'Padam Pelajar Ini'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
