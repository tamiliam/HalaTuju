'use client'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { getPartnerStudent, deleteStudent, type StudentDetailData } from '@/lib/admin-api'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'

export default function AdminStudentDetail() {
  const { id } = useParams<{ id: string }>()
  const { token, role } = useAdminAuth()
  const router = useRouter()
  const { t } = useT()
  const [data, setData] = useState<StudentDetailData | null>(null)
  const [error, setError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!token || !id) return
    getPartnerStudent(id, { token })
      .then(setData)
      .catch(() => setError(t('apiErrors.studentNotFound')))
  }, [token, id])

  if (error) {
    return <div className="text-red-600 mt-8">{error}</div>
  }

  if (!data) {
    return <div className="mt-8 text-center text-gray-500">{t('common.loading')}</div>
  }

  const handleDelete = async () => {
    if (deleteConfirm !== 'delete') return
    setDeleting(true)
    try {
      await deleteStudent(data.supabase_user_id, { token: token! })
      router.replace('/admin/students')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('admin.deleteFailed'))
      setDeleting(false)
    }
  }

  const hasSpmGrades = data.grades && Object.keys(data.grades).length > 0
  const hasStpmGrades = data.stpm_grades && Object.keys(data.stpm_grades).length > 0

  // Extract field interests from student_signals
  const fieldInterest = (data.student_signals?.field_interest || {}) as Record<string, number>

  const getStrengthLabel = (value: number) => {
    if (value >= 0.7) return { text: t('admin.strong'), className: 'bg-green-100 text-green-700' }
    if (value >= 0.4) return { text: t('admin.moderate'), className: 'bg-yellow-100 text-yellow-700' }
    return { text: t('admin.weak'), className: 'bg-gray-100 text-gray-600' }
  }

  const formatNric = (nric: string | null) => {
    if (!nric || nric.length !== 12) return nric || '\u2014'
    return `${nric.slice(0, 6)}-${nric.slice(6, 8)}-${nric.slice(8)}`
  }

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

  return (
    <div>
      <Link href="/admin/students" className="inline-flex items-center gap-1.5 text-blue-600 text-sm hover:underline mb-5">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        {t('admin.backToList')}
      </Link>

      <h1 className="text-2xl font-bold mb-1">{data.name || t('admin.noName')}</h1>
      <p className="text-gray-500 mb-8 text-sm">
        {formatNric(data.nric)} &middot; {data.exam_type?.toUpperCase()} &middot; {data.gender}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Card 1: Maklumat Peribadi */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <span className="text-lg">&#128100;</span> {t('admin.personalInfo')}
          </h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.fullName')}</dt><dd className="font-medium">{data.name || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('profile.angkaGiliran')}</dt><dd className="font-mono">{data.angka_giliran || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.nationality')}</dt><dd>{data.nationality || '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 2: Hubungi & Sekolah */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <span className="text-lg">&#128222;</span> {t('admin.contactSchool')}
          </h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.phone')}</dt><dd>{formatPhone(data.phone)}</dd></div>
            <div><dt className="text-gray-500">{t('admin.address')}</dt><dd className="mt-1">{[data.address, [data.postal_code, data.city].filter(Boolean).join(' '), data.preferred_state].filter(Boolean).join(', ') || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.school')}</dt><dd>{data.school || '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 3: Latar Belakang Keluarga */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <span className="text-lg">&#128106;</span> {t('admin.familyBackground')}
          </h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.familyIncome')}</dt><dd>{data.family_income || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.siblings')}</dt><dd>{data.siblings ?? '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 4: Kesihatan & Kelayakan */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <span className="text-lg">&#127973;</span> {t('admin.healthEligibility')}
          </h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.colorblind')}</dt><dd>{data.colorblind || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.disability')}</dt><dd>{data.disability || '\u2014'}</dd></div>
          </dl>
        </div>

        {/* Card 5: SPM Grades */}
        {hasSpmGrades && (
          <div className="bg-white rounded-xl p-6 shadow-sm border md:col-span-2">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <span className="text-lg">&#128202;</span> {t('admin.spmResults')}
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.grades).map(([subject, grade]) => (
                <span key={subject} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-200 text-sm">
                  <span className="text-gray-600">{subject.toUpperCase()}</span>
                  <span className="font-bold text-blue-700">{grade as string}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Card 6: STPM Grades */}
        {hasStpmGrades && (
          <div className="bg-white rounded-xl p-6 shadow-sm border md:col-span-2">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <span className="text-lg">&#128202;</span> {t('admin.stpmResults')}
            </h2>
            <div className="flex gap-4 mb-4 text-sm">
              {data.stpm_cgpa != null && (
                <span className="px-3 py-1.5 rounded-full bg-purple-50 border border-purple-200">
                  <span className="text-gray-600">CGPA:</span> <span className="font-bold text-purple-700">{data.stpm_cgpa.toFixed(2)}</span>
                </span>
              )}
              {data.muet_band != null && (
                <span className="px-3 py-1.5 rounded-full bg-purple-50 border border-purple-200">
                  <span className="text-gray-600">MUET:</span> <span className="font-bold text-purple-700">Band {data.muet_band}</span>
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.stpm_grades).map(([subject, grade]) => (
                <span key={subject} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-50 border border-purple-200 text-sm">
                  <span className="text-gray-600">{subject}</span>
                  <span className="font-bold text-purple-700">{grade as string}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* No grades */}
        {!hasSpmGrades && !hasStpmGrades && (
          <div className="bg-white rounded-xl p-6 shadow-sm border md:col-span-2">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <span className="text-lg">&#128202;</span> {t('admin.examResults')}
            </h2>
            <p className="text-gray-400 text-sm">{t('admin.notFilled')}</p>
          </div>
        )}

        {/* Card 7: Keutamaan & Isyarat */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <span className="text-lg">&#11088;</span> {t('admin.preferencesSignals')}
          </h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.preferredState')}</dt><dd>{data.preferred_state || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.financialPressure')}</dt><dd>{data.financial_pressure || '\u2014'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">{t('admin.travelWillingness')}</dt><dd>{data.travel_willingness || '\u2014'}</dd></div>
          </dl>
          {Object.keys(fieldInterest).length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <p className="text-gray-500 text-sm mb-2">{t('admin.fieldInterest')}</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(fieldInterest).map(([field, value]) => {
                  const strength = getStrengthLabel(value as number)
                  return (
                    <span key={field} className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm border ${strength.className}`}>
                      {field}
                      <span className="font-semibold">{strength.text}</span>
                    </span>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Card 8: Kursus Disimpan */}
        <div className="bg-white rounded-xl p-6 shadow-sm border">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <span className="text-lg">&#128218;</span> {t('admin.savedCourses')}
          </h2>
          {data.saved_courses?.length > 0 ? (
            <ul className="space-y-2.5 text-sm">
              {data.saved_courses.map((c) => (
                <li key={c.course_id} className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                  {c.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400 text-sm">{t('admin.noSavedCourses')}</p>
          )}
        </div>

        {/* Card 9: Sumber Rujukan (super admin only) */}
        {role?.is_super_admin && (
          <div className="bg-white rounded-xl p-6 shadow-sm border">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <span className="text-lg">&#128279;</span> {t('admin.referralSource')}
              <span className="text-[10px] text-gray-400 ml-1">[{t('admin.superAdmin')}]</span>
            </h2>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">{t('admin.source')}</dt><dd>{data.referral_source || '\u2014'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">{t('admin.orgLabel')}</dt><dd>{data.org_name || '\u2014'}</dd></div>
            </dl>
          </div>
        )}
      </div>

      {/* Danger Zone - super admin only */}
      {role?.is_super_admin && (
        <div className="mt-8 bg-white border border-red-200 rounded-xl overflow-hidden">
          <div className="px-6 py-4 bg-red-50 border-b border-red-200 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-red-700 flex items-center gap-2">
                <span className="text-lg">&#9888;&#65039;</span> {t('admin.dangerZone')}
                <span className="text-[10px] text-red-400 ml-1">[{t('admin.superAdmin')}]</span>
              </h2>
              <p className="text-sm text-red-500 mt-0.5">
                {t('admin.dangerWarning')}
              </p>
            </div>
          </div>
          <div className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder={t('admin.typeDeleteConfirm')}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-full sm:w-64 focus:border-red-400 focus:ring-1 focus:ring-red-400 outline-none"
            />
            <button
              onClick={handleDelete}
              disabled={deleteConfirm !== 'delete' || deleting}
              className="px-5 py-2 border-2 border-red-500 text-red-600 rounded-xl text-sm font-medium hover:bg-red-600 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {deleting ? t('admin.deleting') : t('admin.deleteStudent')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
