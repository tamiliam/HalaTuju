'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { getScholarshipApplications, type AdminScholarshipListItem } from '@/lib/admin-api'

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

export default function AdminScholarshipList() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [apps, setApps] = useState<AdminScholarshipListItem[]>([])
  const [bucket, setBucket] = useState('')
  const [statusF, setStatusF] = useState('')
  const [assignedF, setAssignedF] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    getScholarshipApplications(
      { bucket: bucket || undefined, status: statusF || undefined, assigned: assignedF || undefined },
      { token },
    )
      .then((d) => setApps(d.applications))
      .catch(() => setError(t('admin.scholarship.loadFailed')))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, bucket, statusF, assignedF])

  return (
    <div>
      <h1 className="text-xl sm:text-2xl font-bold">{t('admin.scholarship.title')}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-4">{t('admin.scholarship.desc')}</p>

      <div className="flex flex-wrap gap-3 mb-4">
        <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allStatuses')}</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={bucket} onChange={(e) => setBucket(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allBuckets')}</option>
          <option value="A">Bucket A</option>
          <option value="B">Bucket B</option>
        </select>
        <select value={assignedF} onChange={(e) => setAssignedF(e.target.value)} className="border rounded-lg px-3 py-2 text-sm">
          <option value="">{t('admin.scholarship.allAssignees')}</option>
          <option value="me">{t('admin.scholarship.assignedToMe')}</option>
          <option value="none">{t('admin.scholarship.unassigned')}</option>
        </select>
      </div>

      {error && <div className="text-red-600">{error}</div>}
      {loading ? (
        <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>
      ) : apps.length === 0 ? (
        <div className="text-center text-gray-500 mt-8">{t('admin.scholarship.empty')}</div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50/80 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.name')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.qualification')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.status')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.bucket')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.assigned')}</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600 text-xs uppercase tracking-wider">{t('admin.scholarship.submitted')}</th>
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
                  <td className="px-4 py-3 text-gray-600">{a.qualification?.toUpperCase()}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusBadge(a.status)}`}>{a.status}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${bucketBadge(a.bucket)}`}>{a.bucket || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{a.assigned_to_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(a.submitted_at).toLocaleDateString('ms-MY')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
